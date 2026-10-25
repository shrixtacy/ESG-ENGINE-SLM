"""
ESGPilot — Base Crawler.

Abstract base class for all document source crawlers.
Handles download, SHA-256 deduplication, retry logic, and rate limiting.
"""

import asyncio
import hashlib
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Storage directory for downloaded raw documents
RAW_DOCS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "kb", "sources", "raw"
)


@dataclass
class CrawlResult:
    """Result of crawling a single document."""
    url: str
    title: str
    local_path: Optional[str] = None
    sha256: Optional[str] = None
    content_type: Optional[str] = None
    size_bytes: int = 0
    already_exists: bool = False
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class BaseCrawler(ABC):
    """
    Abstract base crawler.

    Subclasses implement `discover_urls()` to return the list of
    documents to fetch, and optionally `extract_metadata()` to
    attach framework/version/section data to each discovered URL.
    """

    def __init__(
        self,
        output_dir: str = None,
        rate_limit_delay: float = 1.5,
        max_retries: int = 3,
        timeout: float = 60.0,
        user_agent: str = "ESGPilotBot/1.0 (+https://esgpilot.io/bot)",
    ):
        self.output_dir = output_dir or RAW_DOCS_DIR
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.timeout = timeout
        self.headers = {"User-Agent": user_agent}
        self._seen_hashes: set[str] = set()

        os.makedirs(self.output_dir, exist_ok=True)

    @abstractmethod
    async def discover_urls(self) -> list[dict]:
        """
        Discover and return a list of documents to crawl.

        Each dict must have at least:
            url: str
            title: str
        Optional keys:
            framework, doc_type, version, effective_from, issuer
        """
        ...

    async def crawl_all(self) -> list[CrawlResult]:
        """Discover and download all documents."""
        logger.info(f"{self.__class__.__name__}: discovering URLs...")
        docs = await self.discover_urls()
        logger.info(f"{self.__class__.__name__}: found {len(docs)} documents")

        results = []
        for i, doc in enumerate(docs):
            url = doc.get("url", "")
            if not url:
                continue

            result = await self._download(url, doc)
            results.append(result)

            if i < len(docs) - 1:
                await asyncio.sleep(self.rate_limit_delay)

        successes = sum(1 for r in results if not r.error)
        logger.info(
            f"{self.__class__.__name__}: crawled {successes}/{len(results)} documents"
        )
        return results

    async def _download(self, url: str, doc_meta: dict) -> CrawlResult:
        """Download a single URL with retry logic."""
        title = doc_meta.get("title", urlparse(url).path.split("/")[-1])
        result = CrawlResult(url=url, title=title, metadata=doc_meta)

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    headers=self.headers,
                    follow_redirects=True,
                ) as client:
                    response = await client.get(url)
                    response.raise_for_status()

                content = response.content
                content_type = response.headers.get("content-type", "")
                result.content_type = content_type.split(";")[0].strip()
                result.size_bytes = len(content)

                # Compute hash
                sha256 = hashlib.sha256(content).hexdigest()
                result.sha256 = sha256

                # Deduplicate
                if sha256 in self._seen_hashes:
                    result.already_exists = True
                    return result
                self._seen_hashes.add(sha256)

                # Check if file already on disk
                local_path = self._get_local_path(url, sha256, result.content_type)
                if os.path.exists(local_path):
                    result.local_path = local_path
                    result.already_exists = True
                    return result

                # Write to disk
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(content)

                result.local_path = local_path
                logger.debug(f"Downloaded: {title} → {local_path}")
                return result

            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP {e.response.status_code} for {url} (attempt {attempt})")
                if e.response.status_code in (403, 404, 410):
                    result.error = f"HTTP {e.response.status_code}"
                    return result
            except httpx.RequestError as e:
                logger.warning(f"Request error for {url} (attempt {attempt}): {e}")
            except Exception as e:
                logger.error(f"Unexpected error for {url} (attempt {attempt}): {e}")

            if attempt < self.max_retries:
                await asyncio.sleep(2 ** attempt)

        result.error = f"Failed after {self.max_retries} attempts"
        return result

    def _get_local_path(self, url: str, sha256: str, content_type: str) -> str:
        """Determine local file path from URL and content type."""
        parsed = urlparse(url)
        filename = parsed.path.split("/")[-1] or "index"

        # Ensure correct extension
        if "pdf" in content_type and not filename.endswith(".pdf"):
            filename += ".pdf"
        elif "html" in content_type and not filename.endswith((".html", ".htm")):
            filename += ".html"

        # Use SHA256 prefix to avoid collisions
        safe_name = f"{sha256[:8]}_{filename}"
        return os.path.join(self.output_dir, safe_name)

    def compute_sha256_file(self, filepath: str) -> str:
        """Compute SHA-256 of an existing file."""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                sha256.update(block)
        return sha256.hexdigest()
