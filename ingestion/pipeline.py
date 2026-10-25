"""
ESGPilot — Document Ingestion Pipeline.

Implements ARCHITECTURE.md §2.9:
  Sources → Crawl → Download+Hash+Dedupe → Parse → Structure → Metadata → Review → Chunk+Embed → Qdrant

Features:
  - Structure-aware chunking (by clause/section/table)
  - Parent-child chunks (retrieve child, feed parent)
  - Metadata extraction (framework, indicator, version)
  - SHA-256 for provenance
  - Version linking (supersedes/superseded_by)
"""

import hashlib
import os
import re
import uuid
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import yaml


@dataclass
class DocumentMeta:
    """Metadata for an ingested document."""
    doc_id: str
    title: str
    issuer: Optional[str] = None
    doc_type: str = "guidance"  # law | circular | standard | guidance | example
    version: Optional[str] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    superseded_by: Optional[str] = None
    url: Optional[str] = None
    sha256: Optional[str] = None
    scope: str = "global"
    lang: str = "en"
    licence: Optional[str] = None
    framework: Optional[str] = None


@dataclass
class Chunk:
    """A single chunk ready for embedding."""
    chunk_id: str
    doc_id: str
    text: str
    section_path: Optional[str] = None
    page: Optional[int] = None
    parent_chunk_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class DocumentParser:
    """Parse documents into structured text."""

    @staticmethod
    def parse_pdf(filepath: str) -> dict:
        """
        Parse a PDF file into structured sections.
        Uses PyMuPDF for text extraction.
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return {"pages": [], "error": "PyMuPDF not installed"}

        doc = fitz.open(filepath)
        pages = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            pages.append({
                "page": page_num + 1,
                "text": text.strip(),
            })

        doc.close()
        return {"pages": pages, "total_pages": len(pages)}

    @staticmethod
    def parse_text(filepath: str) -> dict:
        """Parse a plain text or markdown file."""
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        return {"text": text, "pages": [{"page": 1, "text": text}]}

    @staticmethod
    def parse_yaml(filepath: str) -> dict:
        """Parse a YAML file (e.g., field catalogue)."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data

    def parse(self, filepath: str) -> dict:
        """Auto-detect format and parse."""
        ext = Path(filepath).suffix.lower()
        if ext == ".pdf":
            return self.parse_pdf(filepath)
        elif ext in (".txt", ".md"):
            return self.parse_text(filepath)
        elif ext in (".yaml", ".yml"):
            return self.parse_yaml(filepath)
        else:
            return self.parse_text(filepath)


class StructureExtractor:
    """Extract structure (sections, clauses, tables, indicator IDs) from parsed text."""

    # Patterns for BRSR clause/indicator IDs
    BRSR_PATTERNS = [
        r"(P\d+[-\s]?E?I[-\s]?\d+[a-z]?)",     # P6-EI-7, P3-EI-1a
        r"(Section\s+[A-C])",                      # Section A, B, C
        r"(Principle\s+\d+)",                       # Principle 1-9
        r"(Essential\s+Indicator\s+\d+)",           # Essential Indicator 1
        r"(Leadership\s+Indicator\s+\d+)",          # Leadership Indicator 1
    ]

    # GRI patterns
    GRI_PATTERNS = [
        r"(GRI\s+\d+-\d+)",                        # GRI 305-1
        r"(Disclosure\s+\d+-\d+)",                  # Disclosure 305-1
    ]

    # SDG patterns
    SDG_PATTERNS = [
        r"(SDG\s+\d+\.?\d*)",                      # SDG 13.2
        r"(Goal\s+\d+)",                            # Goal 13
        r"(Target\s+\d+\.\d+)",                     # Target 13.2
    ]

    def extract_indicators(self, text: str) -> list[str]:
        """Extract framework indicator IDs from text."""
        indicators = []
        for pattern_list in [self.BRSR_PATTERNS, self.GRI_PATTERNS, self.SDG_PATTERNS]:
            for pattern in pattern_list:
                matches = re.findall(pattern, text, re.IGNORECASE)
                indicators.extend(matches)
        return list(set(indicators))

    def extract_sections(self, text: str) -> list[dict]:
        """
        Split text into sections based on heading patterns.
        Returns list of {heading, level, text, indicators}.
        """
        # Markdown-style headings
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        sections = []
        last_pos = 0
        last_heading = None
        last_level = 0

        for match in heading_pattern.finditer(text):
            if last_heading is not None:
                section_text = text[last_pos:match.start()].strip()
                sections.append({
                    "heading": last_heading,
                    "level": last_level,
                    "text": section_text,
                    "indicators": self.extract_indicators(section_text),
                })
            last_heading = match.group(2)
            last_level = len(match.group(1))
            last_pos = match.end()

        # Last section
        if last_heading is not None:
            section_text = text[last_pos:].strip()
            sections.append({
                "heading": last_heading,
                "level": last_level,
                "text": section_text,
                "indicators": self.extract_indicators(section_text),
            })

        if not sections:
            # No headings found — treat entire text as one section
            sections.append({
                "heading": "Document",
                "level": 1,
                "text": text,
                "indicators": self.extract_indicators(text),
            })

        return sections


class Chunker:
    """
    Structure-aware chunking.
    Chunks by clause/section, 300-600 tokens.
    Creates parent-child relationships (retrieve child, feed parent).
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_document(
        self,
        parsed: dict,
        doc_meta: DocumentMeta,
    ) -> list[Chunk]:
        """Chunk a parsed document."""
        all_chunks = []
        extractor = StructureExtractor()

        pages = parsed.get("pages", [])
        if not pages and "text" in parsed:
            pages = [{"page": 1, "text": parsed["text"]}]

        for page_data in pages:
            page_num = page_data.get("page", 1)
            text = page_data.get("text", "")

            if not text.strip():
                continue

            # Extract sections
            sections = extractor.extract_sections(text)

            for section in sections:
                section_text = section["text"]
                if len(section_text) < self.min_chunk_size:
                    # Too small — include as single chunk
                    chunk = Chunk(
                        chunk_id=uuid.uuid4().hex,
                        doc_id=doc_meta.doc_id,
                        text=section_text,
                        section_path=section["heading"],
                        page=page_num,
                        metadata={
                            "doc_title": doc_meta.title,
                            "issuer": doc_meta.issuer,
                            "doc_type": doc_meta.doc_type,
                            "version": doc_meta.version,
                            "effective_from": doc_meta.effective_from,
                            "framework": doc_meta.framework,
                            "indicators": section["indicators"],
                            "url": doc_meta.url,
                            "lang": doc_meta.lang,
                            "tenant_scope": doc_meta.scope,
                        },
                    )
                    all_chunks.append(chunk)
                else:
                    # Split into overlapping chunks
                    sub_chunks = self._split_text(
                        section_text, section["heading"], page_num, doc_meta
                    )
                    all_chunks.extend(sub_chunks)

        return all_chunks

    def _split_text(
        self,
        text: str,
        section_path: str,
        page: int,
        doc_meta: DocumentMeta,
    ) -> list[Chunk]:
        """Split text into overlapping chunks."""
        words = text.split()
        chunks = []

        # Create parent chunk (full section)
        parent_id = uuid.uuid4().hex
        parent_chunk = Chunk(
            chunk_id=parent_id,
            doc_id=doc_meta.doc_id,
            text=text[:2000],  # Truncate very long parents
            section_path=section_path,
            page=page,
            metadata={
                "doc_title": doc_meta.title,
                "issuer": doc_meta.issuer,
                "doc_type": doc_meta.doc_type,
                "version": doc_meta.version,
                "framework": doc_meta.framework,
                "url": doc_meta.url,
                "lang": doc_meta.lang,
                "tenant_scope": doc_meta.scope,
                "is_parent": True,
            },
        )
        chunks.append(parent_chunk)

        # Create child chunks
        start = 0
        while start < len(words):
            end = min(start + self.chunk_size, len(words))
            chunk_text = " ".join(words[start:end])

            if len(chunk_text) >= self.min_chunk_size:
                child = Chunk(
                    chunk_id=uuid.uuid4().hex,
                    doc_id=doc_meta.doc_id,
                    text=chunk_text,
                    section_path=section_path,
                    page=page,
                    parent_chunk_id=parent_id,
                    metadata={
                        "doc_title": doc_meta.title,
                        "issuer": doc_meta.issuer,
                        "doc_type": doc_meta.doc_type,
                        "version": doc_meta.version,
                        "framework": doc_meta.framework,
                        "url": doc_meta.url,
                        "lang": doc_meta.lang,
                        "tenant_scope": doc_meta.scope,
                        "parent_chunk_id": parent_id,
                    },
                )
                chunks.append(child)

            start = end - self.chunk_overlap
            if start >= len(words) - self.chunk_overlap:
                break

        return chunks


class IngestionPipeline:
    """
    End-to-end ingestion pipeline.
    Takes a file, parses, chunks, embeds, and indexes in Qdrant.
    """

    def __init__(self, retrieval_service=None):
        self.parser = DocumentParser()
        self.chunker = Chunker()
        self.retrieval = retrieval_service

    def compute_sha256(self, filepath: str) -> str:
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                sha256.update(block)
        return sha256.hexdigest()

    def ingest_file(
        self,
        filepath: str,
        doc_meta: DocumentMeta,
        collection: str = "kb_global",
    ) -> dict:
        """
        Ingest a single file:
          1. Compute hash
          2. Parse
          3. Extract structure
          4. Chunk
          5. Index in Qdrant
        """
        # 1. Hash
        doc_meta.sha256 = self.compute_sha256(filepath)

        # 2. Parse
        parsed = self.parser.parse(filepath)

        # 3 & 4. Chunk
        chunks = self.chunker.chunk_document(parsed, doc_meta)

        # 5. Index
        if self.retrieval:
            qdrant_chunks = [
                {
                    "id": c.chunk_id,
                    "text": c.text,
                    "metadata": c.metadata,
                }
                for c in chunks
            ]
            self.retrieval.index_chunks(qdrant_chunks, collection)

        return {
            "doc_id": doc_meta.doc_id,
            "title": doc_meta.title,
            "sha256": doc_meta.sha256,
            "chunks_created": len(chunks),
            "collection": collection,
        }

    def ingest_directory(
        self,
        directory: str,
        framework: str = "BRSR",
        collection: str = "kb_global",
    ) -> list[dict]:
        """Ingest all supported files from a directory."""
        results = []
        supported_exts = {".pdf", ".txt", ".md", ".yaml", ".yml"}

        for root, dirs, files in os.walk(directory):
            for filename in files:
                ext = Path(filename).suffix.lower()
                if ext not in supported_exts:
                    continue

                filepath = os.path.join(root, filename)
                doc_meta = DocumentMeta(
                    doc_id=uuid.uuid4().hex,
                    title=filename,
                    framework=framework,
                    scope="global",
                )

                try:
                    result = self.ingest_file(filepath, doc_meta, collection)
                    results.append(result)
                except Exception as e:
                    results.append({
                        "doc_id": doc_meta.doc_id,
                        "title": filename,
                        "error": str(e),
                    })

        return results
