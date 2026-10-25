"""Ingestion crawlers package."""
from .sebi_crawler import SEBICrawler
from .un_sdg_crawler import UNSDGCrawler
from .mca_crawler import MCACrawler
from .base_crawler import BaseCrawler

__all__ = ["BaseCrawler", "SEBICrawler", "UNSDGCrawler", "MCACrawler"]
