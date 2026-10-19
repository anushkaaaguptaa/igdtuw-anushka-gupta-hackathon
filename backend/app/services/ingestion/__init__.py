"""RiskLens AI - News & Social Data Ingestion Engine"""
from app.services.ingestion.base import (
    BaseSourceAdapter,
    canonicalize_url,
    compute_dedup_key,
    parse_datetime_utc
)
from app.services.ingestion.gdelt_adapter import GDELTAdapter
from app.services.ingestion.rss_adapter import FinancialRSSAdapter
from app.services.ingestion.replay_adapter import ReplayFixtureAdapter
from app.services.ingestion.service import IngestionCoordinator

__all__ = [
    "BaseSourceAdapter",
    "canonicalize_url",
    "compute_dedup_key",
    "parse_datetime_utc",
    "GDELTAdapter",
    "FinancialRSSAdapter",
    "ReplayFixtureAdapter",
    "IngestionCoordinator",
]
