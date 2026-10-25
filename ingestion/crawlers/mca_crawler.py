"""
ESGPilot — MCA / NGRBC Crawler.

Crawls Ministry of Corporate Affairs (MCA) and NGRBC documents.
Sources:
  - MCA: https://www.mca.gov.in (Companies Act, CSR rules)
  - MoCA / NGRBC: https://www.mca.gov.in/MinistryV2/nationalguidelinesbrs.html
  - BIS / GRI India: guidance notes
"""

from .base_crawler import BaseCrawler


MCA_DOCS = [
    # Companies Act Section 135 — CSR
    {
        "url": "https://www.mca.gov.in/Ministry/pdf/CompaniesAct2013.pdf",
        "title": "Companies Act 2013 (Consolidated) — MCA",
        "framework": "CSR",
        "doc_type": "law",
        "issuer": "MCA",
        "version": "2013-consolidated",
        "effective_from": "2013-04-01",
        "lang": "en",
    },
    # CSR Rules 2014 amended
    {
        "url": "https://www.mca.gov.in/Ministry/pdf/CSR_rules_2014.pdf",
        "title": "Companies (CSR Policy) Rules 2014 — MCA",
        "framework": "CSR",
        "doc_type": "law",
        "issuer": "MCA",
        "version": "2014-amended",
        "effective_from": "2014-04-01",
        "lang": "en",
    },
    # NGRBC 2019
    {
        "url": "https://www.mca.gov.in/Ministry/pdf/NationalGuidelinesBRS_2019.pdf",
        "title": "National Guidelines on Responsible Business Conduct (NGRBC) 2019 — MCA",
        "framework": "NGRBC",
        "doc_type": "standard",
        "issuer": "MCA",
        "version": "2019",
        "effective_from": "2019-03-15",
        "lang": "en",
    },
    # BRSR FAQs / Technical Guidance
    {
        "url": "https://www.mca.gov.in/Ministry/pdf/BRSR_FAQ.pdf",
        "title": "BRSR Technical Guidance and FAQs — MCA/SEBI",
        "framework": "BRSR",
        "doc_type": "guidance",
        "issuer": "MCA",
        "version": "2022",
        "effective_from": "2022-04-01",
        "lang": "en",
    },
    # India Corporate Governance Voluntary Guidelines
    {
        "url": "https://www.mca.gov.in/Ministry/pdf/CG_Voluntary_Guidelines_2009.pdf",
        "title": "Corporate Governance Voluntary Guidelines 2009 — MCA",
        "framework": "NGRBC",
        "doc_type": "guidance",
        "issuer": "MCA",
        "version": "2009",
        "effective_from": "2009-01-01",
        "lang": "en",
    },
    # CEA CO2 Baseline Database (emission factors)
    {
        "url": "https://cea.nic.in/wp-content/uploads/pdm/2023/07/CO2_Baseline_Database_Ver_18.pdf",
        "title": "CEA CO2 Baseline Database for Indian Power Sector (v18 2023)",
        "framework": "GHG_PROTOCOL",
        "doc_type": "standard",
        "issuer": "CEA",
        "version": "v18-2023",
        "effective_from": "2023-01-01",
        "lang": "en",
    },
    # Environment Protection Act 1986
    {
        "url": "https://www.indiacode.nic.in/bitstream/123456789/2191/1/A1986-29.pdf",
        "title": "Environment (Protection) Act 1986 — India Code",
        "framework": "BRSR",
        "doc_type": "law",
        "issuer": "MoEFCC",
        "version": "1986",
        "effective_from": "1986-11-19",
        "lang": "en",
    },
    # Plastic Waste Management Rules (EPR)
    {
        "url": "https://www.mca.gov.in/Ministry/pdf/PlasticWasteManagement_2022.pdf",
        "title": "Plastic Waste Management (Amendment) Rules 2022 — EPR Framework",
        "framework": "BRSR",
        "doc_type": "law",
        "issuer": "MoEFCC",
        "version": "2022",
        "effective_from": "2022-02-16",
        "lang": "en",
    },
]


class MCACrawler(BaseCrawler):
    """Crawler for MCA, NGRBC, and related Indian regulatory documents."""

    async def discover_urls(self) -> list[dict]:
        """Return curated MCA/NGRBC document list."""
        # MCA website doesn't have a structured scrape-friendly API
        # Use curated list; update manually or via n8n watchers
        return list(MCA_DOCS)
