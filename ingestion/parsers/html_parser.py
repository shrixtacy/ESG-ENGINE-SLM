"""
ESGPilot — HTML Parser.

Parses regulatory HTML pages (SEBI circulars, MCA pages, UN SDG website).
Extracts structured text, preserving heading hierarchy.
Converts tables to Markdown.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup, Tag


@dataclass
class ParsedHTML:
    """Result of parsing an HTML document."""
    url: str
    title: Optional[str] = None
    text: str = ""
    headings: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)  # {text, url}
    indicators: list[str] = field(default_factory=list)
    lang: str = "en"
    error: Optional[str] = None

    def as_sections(self) -> list[dict]:
        return [{"page": 1, "text": self.text, "headings": self.headings, "tables": self.tables}]


# Tags to strip entirely
STRIP_TAGS = {
    "script", "style", "noscript", "head", "meta", "link",
    "footer", "nav", "header", "aside", "form", "button",
    "iframe", "svg", "img",
}

# Tags that imply a heading
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

# ESG indicator patterns (same as PDF parser)
INDICATOR_PATTERNS = [
    re.compile(r"P\d[-\s]?[EL]I[-\s]?\d+[a-z]?", re.IGNORECASE),
    re.compile(r"Principle\s+\d+", re.IGNORECASE),
    re.compile(r"Section\s+[A-C]", re.IGNORECASE),
    re.compile(r"GRI\s+\d{3}-\d+", re.IGNORECASE),
    re.compile(r"SDG\s+\d+\.?\d*", re.IGNORECASE),
    re.compile(r"BRSR Core\s+KPI[-\s]?\d+", re.IGNORECASE),
]


class HTMLParser:
    """
    HTML parser using BeautifulSoup.

    Targets regulatory document HTML pages — strips chrome (nav, footer, ads)
    and extracts the main content body.
    """

    def __init__(self, base_url: str = ""):
        self.base_url = base_url

    def parse(self, html: str, url: str = "") -> ParsedHTML:
        """Parse an HTML string and return a ParsedHTML."""
        result = ParsedHTML(url=url)

        try:
            soup = BeautifulSoup(html, "html.parser")

            # Extract title
            title_tag = soup.find("title")
            result.title = title_tag.get_text(strip=True) if title_tag else None

            # Detect language
            html_tag = soup.find("html")
            if html_tag:
                result.lang = html_tag.get("lang", "en").split("-")[0]

            # Remove unwanted tags
            for tag in soup.find_all(STRIP_TAGS):
                tag.decompose()

            # Find main content area
            main = self._find_main_content(soup)

            # Extract text, headings, tables
            result.headings = self._extract_headings(main)
            result.tables = self._extract_tables(main)
            result.links = self._extract_links(main, url)

            # Remove table tags before text extraction to avoid duplication
            for tbl in main.find_all("table"):
                tbl.decompose()

            result.text = self._extract_text(main)
            result.indicators = self._extract_indicators(result.text)

        except Exception as e:
            result.error = str(e)

        return result

    def parse_file(self, filepath: str, url: str = "") -> ParsedHTML:
        """Parse an HTML file."""
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
        return self.parse(html, url=url)

    def _find_main_content(self, soup: BeautifulSoup) -> Tag:
        """Find the main content container."""
        # Try semantic HTML5 landmarks first
        for selector in [
            "main",
            "article",
            '[role="main"]',
            ".main-content",
            "#main-content",
            ".content",
            "#content",
            ".circular-content",    # SEBI-specific
            ".notification-content",
        ]:
            el = soup.select_one(selector)
            if el:
                return el

        # Fallback to body
        body = soup.find("body")
        return body if body else soup

    def _extract_headings(self, element: Tag) -> list[str]:
        """Extract heading texts."""
        headings = []
        for tag in element.find_all(HEADING_TAGS):
            text = tag.get_text(strip=True)
            if text:
                level = int(tag.name[1])
                headings.append(f"{'#' * level} {text}")
        return headings

    def _extract_tables(self, element: Tag) -> list[str]:
        """Convert HTML tables to Markdown."""
        tables_md = []
        for table in element.find_all("table"):
            md = self._table_to_markdown(table)
            if md:
                tables_md.append(md)
        return tables_md

    @staticmethod
    def _table_to_markdown(table: Tag) -> str:
        """Convert a BeautifulSoup table to Markdown."""
        rows = []
        all_rows = table.find_all("tr")
        if not all_rows:
            return ""

        for row in all_rows:
            cells = row.find_all(["th", "td"])
            row_text = [c.get_text(" ", strip=True) for c in cells]
            rows.append(row_text)

        if not rows:
            return ""

        # Determine max columns
        max_cols = max(len(r) for r in rows)

        # Pad rows
        padded = [r + [""] * (max_cols - len(r)) for r in rows]

        # Build markdown
        header = padded[0]
        separator = ["---"] * max_cols
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(separator) + " |",
        ]
        for row in padded[1:]:
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def _extract_links(self, element: Tag, base_url: str) -> list[dict]:
        """Extract links — useful for discovering linked PDFs."""
        links = []
        for a in element.find_all("a", href=True):
            href = a.get("href", "").strip()
            text = a.get_text(strip=True)
            if not href or href.startswith("#"):
                continue
            if not href.startswith("http"):
                href = self.base_url + href
            links.append({"text": text, "url": href})
        return links

    @staticmethod
    def _extract_text(element: Tag) -> str:
        """Extract clean text from element."""
        # Replace block elements with newlines
        for br in element.find_all("br"):
            br.replace_with("\n")
        for p in element.find_all(["p", "li", "div", "section"]):
            p.append("\n")

        text = element.get_text(" ")

        # Clean up
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        lines = [line.strip() for line in text.splitlines()]
        text = "\n".join(lines).strip()
        return text

    @staticmethod
    def _extract_indicators(text: str) -> list[str]:
        """Extract ESG indicator IDs."""
        indicators = []
        for pattern in INDICATOR_PATTERNS:
            indicators.extend(pattern.findall(text))
        return list(set(indicators))
