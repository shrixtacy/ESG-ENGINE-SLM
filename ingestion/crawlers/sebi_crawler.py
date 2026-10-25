"""
ESGPilot — SEBI Crawler.

Crawls SEBI circulars and notifications related to BRSR, ESG, and sustainability reporting.
Source: https://www.sebi.gov.in

Key documents:
  - BRSR disclosure format (circular SEBI/HO/CFD/CMD-2/P/CIR/2023/168)
  - BRSR Core circular (2023)
  - ESG Ratings circular
  - CG Listing Obligations (LODR)
"""

import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .base_crawler import BaseCrawler, CrawlResult


# Known BRSR/ESG SEBI documents with direct URLs
# Populated from SEBI circular archive — update as new circulars are issued
SEBI_ESG_DOCS = [
    {
        "url": "https://www.sebi.gov.in/legal/circulars/may-2021/business-responsibility-and-sustainability-reporting-by-listed-entities_50096.html",
        "title": "SEBI BRSR Circular (May 2021) — SEBI/HO/CFD/CMD-2/CIR/P/2021/562",
        "framework": "BRSR",
        "doc_type": "circular",
        "issuer": "SEBI",
        "version": "2021-05-10",
        "effective_from": "2022-04-01",
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/jul-2023/environmental-social-and-governance-esg-rating-providers-for-securities-markets_74082.html",
        "title": "SEBI ESG Rating Providers Circular (Jul 2023)",
        "framework": "BRSR",
        "doc_type": "circular",
        "issuer": "SEBI",
        "version": "2023-07-12",
        "effective_from": "2023-07-12",
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/jul-2023/revised-format-for-business-responsibility-and-sustainability-report-brsr_73953.html",
        "title": "SEBI Revised BRSR Format (Jul 2023) — BRSR Core",
        "framework": "BRSR",
        "doc_type": "circular",
        "issuer": "SEBI",
        "version": "2023-07-12",
        "effective_from": "2023-04-01",
    },
    {
        "url": "https://www.sebi.gov.in/legal/circulars/dec-2023/disclosure-requirements-for-esg-schemes-by-mutual-funds-and-amendment-to-circulars-pertaining-to-esg-schemes_79818.html",
        "title": "SEBI ESG Schemes Disclosure (Dec 2023)",
        "framework": "BRSR",
        "doc_type": "circular",
        "issuer": "SEBI",
        "version": "2023-12-01",
        "effective_from": "2024-01-01",
    },
    {
        "url": "https://www.sebi.gov.in/sebi_data/attachdocs/may-2021/1620898907670.pdf",
        "title": "BRSR Format Annexure (PDF) — SEBI 2021",
        "framework": "BRSR",
        "doc_type": "standard",
        "issuer": "SEBI",
        "version": "2021-05-10",
        "effective_from": "2022-04-01",
    },
    {
        "url": "https://www.sebi.gov.in/sebi_data/attachdocs/jul-2023/16887344831.pdf",
        "title": "BRSR Core KPI Format (PDF) — SEBI 2023",
        "framework": "BRSR",
        "doc_type": "standard",
        "issuer": "SEBI",
        "version": "2023-07-12",
        "effective_from": "2024-04-01",
    },
]

# SEBI circulars search page for new ESG documents
SEBI_CIRCULARS_SEARCH = (
    "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?"
    "doListingSearch=yes&category=13&subCategory=24"
)


class SEBICrawler(BaseCrawler):
    """
    Crawler for SEBI circulars and notifications.

    Fetches both the known curated list and attempts to discover
    new circulars from the SEBI search page.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_url = "https://www.sebi.gov.in"

    async def discover_urls(self) -> list[dict]:
        """Return SEBI ESG document list (curated + discovered)."""
        docs = list(SEBI_ESG_DOCS)

        # Attempt live discovery from SEBI circulars page
        try:
            discovered = await self._discover_from_search()
            # Merge — avoid URL duplicates
            existing_urls = {d["url"] for d in docs}
            for doc in discovered:
                if doc["url"] not in existing_urls:
                    docs.append(doc)
        except Exception as e:
            # Fallback to curated list only; log the error
            import logging
            logging.getLogger(__name__).warning(
                f"SEBI live discovery failed: {e}. Using curated list."
            )

        return docs

    async def _discover_from_search(self) -> list[dict]:
        """
        Attempt to scrape SEBI circulars search page for new ESG-related circulars.
        Returns list of doc dicts.
        """
        discovered = []

        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:
            response = await client.get(SEBI_CIRCULARS_SEARCH)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # SEBI table rows contain circular links
        for row in soup.select("table tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            link_tag = row.find("a", href=True)
            if not link_tag:
                continue

            href = link_tag.get("href", "")
            title = link_tag.get_text(strip=True)

            # Filter for ESG/BRSR relevance
            if not any(
                kw in title.upper()
                for kw in ["BRSR", "ESG", "SUSTAINABILITY", "BUSINESS RESPONSIBILITY"]
            ):
                continue

            url = href if href.startswith("http") else self.base_url + href

            # Extract date from cell text
            date_text = cells[0].get_text(strip=True) if cells else ""
            date_match = re.search(r"\d{2}[/-]\d{2}[/-]\d{4}", date_text)
            version = date_match.group(0).replace("/", "-") if date_match else None

            discovered.append({
                "url": url,
                "title": title,
                "framework": "BRSR",
                "doc_type": "circular",
                "issuer": "SEBI",
                "version": version,
            })

        return discovered
