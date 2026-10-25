"""
ESGPilot — UN SDG Crawler.

Crawls the UN SDG knowledge base, indicator framework, and related documents.
Sources:
  - UN SDGs: https://sdgs.un.org/goals
  - UN Stats SDG Indicators: https://unstats.un.org/sdgs/indicators/indicators-list/
  - India SDG NIF (MoSPI): https://mospi.gov.in
  - NITI Aayog SDG Index: https://www.niti.gov.in
"""

import httpx
from bs4 import BeautifulSoup

from .base_crawler import BaseCrawler


# Curated list of SDG documents
UN_SDG_DOCS = [
    # SDG Goals and Targets PDF
    {
        "url": "https://sdgs.un.org/sites/default/files/2021-10/Chapter%202%20-%20Transforming%20our%20world-%20the%202030%20Agenda%20for%20Sustainable%20Development.pdf",
        "title": "2030 Agenda for Sustainable Development — UN (2015)",
        "framework": "SDG",
        "doc_type": "standard",
        "issuer": "United Nations",
        "version": "2015",
        "effective_from": "2016-01-01",
        "lang": "en",
    },
    # SDG indicators global list
    {
        "url": "https://unstats.un.org/sdgs/indicators/Global%20Indicator%20Framework%20after%202023%20refinement_Eng.pdf",
        "title": "Global SDG Indicator Framework (2023 Refinement)",
        "framework": "SDG",
        "doc_type": "standard",
        "issuer": "UN Statistics Division",
        "version": "2023",
        "effective_from": "2023-01-01",
        "lang": "en",
    },
    # India SDG Localisation
    {
        "url": "https://mospi.gov.in/documents/213904/0/NIF+3.0+Dashboard.pdf",
        "title": "India National Indicator Framework (NIF) 3.0 — MoSPI",
        "framework": "SDG",
        "doc_type": "standard",
        "issuer": "MoSPI",
        "version": "NIF-3.0",
        "effective_from": "2023-01-01",
        "lang": "en",
    },
    # GHG Protocol Corporate Standard
    {
        "url": "https://ghgprotocol.org/sites/default/files/standards/ghg-protocol-revised.pdf",
        "title": "GHG Protocol Corporate Accounting and Reporting Standard (Revised 2015)",
        "framework": "GHG_PROTOCOL",
        "doc_type": "standard",
        "issuer": "GHG Protocol",
        "version": "2015",
        "effective_from": "2015-01-01",
        "lang": "en",
    },
    # IPCC AR6 Summary (relevant for emission factors / GWP)
    {
        "url": "https://www.ipcc.ch/report/ar6/wg1/downloads/report/IPCC_AR6_WGI_SPM.pdf",
        "title": "IPCC Sixth Assessment Report — Summary for Policymakers (AR6 WG1)",
        "framework": "GHG_PROTOCOL",
        "doc_type": "guidance",
        "issuer": "IPCC",
        "version": "AR6-2021",
        "effective_from": "2021-08-09",
        "lang": "en",
    },
]


class UNSDGCrawler(BaseCrawler):
    """Crawler for UN SDG and related global standard documents."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def discover_urls(self) -> list[dict]:
        """Return UN SDG document list (curated + live SDG goals page)."""
        docs = list(UN_SDG_DOCS)

        # Attempt to discover SDG goal descriptions from UN website
        try:
            goal_docs = await self._discover_sdg_goals()
            existing_urls = {d["url"] for d in docs}
            for doc in goal_docs:
                if doc["url"] not in existing_urls:
                    docs.append(doc)
        except Exception:
            pass  # Curated list is sufficient

        return docs

    async def _discover_sdg_goals(self) -> list[dict]:
        """Scrape SDG goals page for individual goal fact sheets."""
        discovered = []

        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:
            response = await client.get("https://sdgs.un.org/goals")
            if response.status_code != 200:
                return []

        soup = BeautifulSoup(response.text, "html.parser")

        # Look for goal links
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "/goals/goal" in href.lower():
                full_url = (
                    href if href.startswith("http") else f"https://sdgs.un.org{href}"
                )
                title = link.get_text(strip=True) or f"UN SDG Goal - {href}"
                if title and len(title) > 3:
                    discovered.append({
                        "url": full_url,
                        "title": f"UN SDG — {title}",
                        "framework": "SDG",
                        "doc_type": "standard",
                        "issuer": "United Nations",
                        "version": "2030Agenda",
                        "effective_from": "2016-01-01",
                    })

        return discovered
