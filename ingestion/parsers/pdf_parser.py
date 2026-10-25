"""
ESGPilot — PDF Parser.

Extracts structured text from PDFs using PyMuPDF (fitz).
Handles:
  - Multi-column layouts (regulatory PDFs often use 2-col)
  - Tables (extracted as Markdown)
  - Headers/headings (font-size heuristic)
  - Page numbers (stripped)
  - OCR fallback via Tesseract for scanned documents
  - BRSR/GRI indicator ID extraction
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ParsedPage:
    """A single parsed page."""
    page_num: int
    text: str
    headings: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    indicators: list[str] = field(default_factory=list)
    is_scanned: bool = False


@dataclass
class ParsedDocument:
    """Full parsed document."""
    filepath: str
    pages: list[ParsedPage] = field(default_factory=list)
    total_pages: int = 0
    title: Optional[str] = None
    language: str = "en"
    has_ocr: bool = False
    error: Optional[str] = None

    def full_text(self) -> str:
        """Concatenate all page texts."""
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    def as_sections(self) -> list[dict]:
        """Return pages as section dicts."""
        return [
            {
                "page": p.page_num,
                "text": p.text,
                "headings": p.headings,
                "tables": p.tables,
                "indicators": p.indicators,
            }
            for p in self.pages
        ]


# Regex patterns for ESG indicator IDs
INDICATOR_PATTERNS = [
    re.compile(r"P\d[-\s]?[EL]I[-\s]?\d+[a-z]?", re.IGNORECASE),   # BRSR: P6-EI-7
    re.compile(r"Principle\s+\d+", re.IGNORECASE),                    # BRSR Principle N
    re.compile(r"Section\s+[A-C]", re.IGNORECASE),                   # BRSR Section A/B/C
    re.compile(r"GRI\s+\d{3}-\d+", re.IGNORECASE),                   # GRI 305-1
    re.compile(r"SDG\s+\d+\.?\d*", re.IGNORECASE),                   # SDG 13.2
    re.compile(r"Target\s+\d+\.\d+[a-z]?", re.IGNORECASE),           # Target 13.2a
    re.compile(r"BRSR Core\s+KPI[-\s]?\d+", re.IGNORECASE),          # BRSR Core KPI-1
]

# Minimum text length to consider a page non-scanned
MIN_TEXT_CHARS_PER_PAGE = 100

# Font size threshold for headings (relative to body size)
HEADING_SIZE_RATIO = 1.2


class PDFParser:
    """
    PDF parser using PyMuPDF.

    Falls back to Tesseract OCR for scanned/image-only PDFs.
    """

    def __init__(
        self,
        ocr_fallback: bool = True,
        extract_tables: bool = True,
        lang: str = "eng",
    ):
        self.ocr_fallback = ocr_fallback
        self.extract_tables = extract_tables
        self.lang = lang  # Tesseract language code

    def parse(self, filepath: str) -> ParsedDocument:
        """Parse a PDF file and return a ParsedDocument."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return ParsedDocument(
                filepath=filepath,
                error="PyMuPDF (fitz) not installed. Run: pip install pymupdf",
            )

        doc = ParsedDocument(filepath=filepath)

        try:
            pdf = fitz.open(filepath)
            doc.total_pages = len(pdf)

            # Try to extract title from metadata
            metadata = pdf.metadata
            doc.title = metadata.get("title") or Path(filepath).stem

            pages = []
            for page_num in range(len(pdf)):
                page = pdf[page_num]
                parsed_page = self._parse_page(page, page_num + 1)
                pages.append(parsed_page)

            # OCR fallback for scanned pages
            if self.ocr_fallback:
                scanned_pages = [p for p in pages if p.is_scanned]
                if scanned_pages:
                    doc.has_ocr = True
                    for sp in scanned_pages:
                        idx = sp.page_num - 1
                        ocr_text = self._ocr_page(pdf[idx])
                        if ocr_text:
                            pages[idx].text = ocr_text
                            pages[idx].is_scanned = False

            pdf.close()
            doc.pages = pages

        except Exception as e:
            doc.error = str(e)

        return doc

    def _parse_page(self, page, page_num: int) -> ParsedPage:
        """Parse a single PDF page."""
        try:
            # Extract text with layout preservation
            text = page.get_text("text")
            text = self._clean_text(text)

            is_scanned = len(text.strip()) < MIN_TEXT_CHARS_PER_PAGE

            headings = []
            tables_md = []

            if not is_scanned:
                # Extract headings via font-size analysis
                headings = self._extract_headings(page)

                # Extract tables
                if self.extract_tables:
                    tables_md = self._extract_tables(page)
                    # Append tables to text
                    if tables_md:
                        text += "\n\n" + "\n\n".join(tables_md)

            # Extract indicator IDs
            indicators = self._extract_indicators(text)

            return ParsedPage(
                page_num=page_num,
                text=text,
                headings=headings,
                tables=tables_md,
                indicators=indicators,
                is_scanned=is_scanned,
            )

        except Exception:
            return ParsedPage(page_num=page_num, text="", is_scanned=True)

    def _extract_headings(self, page) -> list[str]:
        """Extract headings by identifying large/bold text spans."""
        headings = []
        try:
            blocks = page.get_text("dict").get("blocks", [])
            # Collect all font sizes
            sizes = []
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        sizes.append(span.get("size", 0))

            if not sizes:
                return []

            median_size = sorted(sizes)[len(sizes) // 2]
            threshold = median_size * HEADING_SIZE_RATIO

            for block in blocks:
                for line in block.get("lines", []):
                    line_text = ""
                    is_heading = False
                    for span in line.get("spans", []):
                        span_text = span.get("text", "").strip()
                        span_size = span.get("size", 0)
                        if span_size >= threshold and span_text:
                            is_heading = True
                        line_text += span_text + " "

                    line_text = line_text.strip()
                    if is_heading and line_text and len(line_text) < 200:
                        headings.append(line_text)

        except Exception:
            pass

        return headings

    def _extract_tables(self, page) -> list[str]:
        """Extract tables from a PDF page as Markdown strings."""
        tables_md = []
        try:
            # PyMuPDF 1.23+ supports find_tables()
            tab_finder = page.find_tables()
            for table in tab_finder.tables:
                df = table.to_pandas()
                if df.empty:
                    continue
                md = df.to_markdown(index=False)
                tables_md.append(md)
        except AttributeError:
            # Older PyMuPDF — skip table extraction
            pass
        except Exception:
            pass

        return tables_md

    def _ocr_page(self, page) -> str:
        """Run Tesseract OCR on a page image."""
        try:
            import pytesseract
            from PIL import Image
            import io

            pix = page.get_pixmap(dpi=300)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            text = pytesseract.image_to_string(img, lang=self.lang)
            return self._clean_text(text)
        except ImportError:
            return ""
        except Exception:
            return ""

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean extracted text — remove excessive whitespace, fix hyphenation."""
        if not text:
            return ""
        # Fix soft-hyphen line breaks
        text = re.sub(r"-\n(\w)", r"\1", text)
        # Collapse multiple newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove page number patterns like "Page 1 of 24" or just lone digits
        text = re.sub(r"(?m)^\s*\d+\s*$", "", text)
        # Strip leading/trailing whitespace per line
        lines = [line.rstrip() for line in text.splitlines()]
        return "\n".join(lines).strip()

    @staticmethod
    def _extract_indicators(text: str) -> list[str]:
        """Extract ESG indicator IDs from text."""
        indicators = []
        for pattern in INDICATOR_PATTERNS:
            matches = pattern.findall(text)
            indicators.extend(matches)
        return list(set(indicators))
