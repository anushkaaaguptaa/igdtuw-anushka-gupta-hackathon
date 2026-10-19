import datetime
import pytest
from unittest.mock import MagicMock
from sqlalchemy.orm import Session

from app.models.db_models import Article, RiskSignal, Entity, SignalEntity
from app.models.schemas import NormalizedArticle
from app.services.ingestion.service import IngestionCoordinator
from app.services.ingestion.base import BaseSourceAdapter


class MockSourceAdapter(BaseSourceAdapter):
    def __init__(self, articles: list, status: str = "healthy"):
        self._articles = articles
        self.last_status = status
        self.last_error = None
        self.last_fetched_count = len(articles)

    def fetch_articles(self, limit: int = 10, keywords = None):
        return self._articles[:limit]


def test_idempotent_ingestion_and_deduplication(db_session: Session):
    now = datetime.datetime.now(datetime.timezone.utc)
    mock_articles = [
        NormalizedArticle(
            source="financial_rss",
            source_id="item_001",
            title="CrowdStrike issues fix for global IT outage",
            raw_content="A faulty update triggered system halts worldwide. CrowdStrike issued remediation scripts.",
            url="https://example.com/crwd-outage-fix",
            publisher="Tech News",
            published_at=now,
            fetched_at=now,
            dedup_key="dedup_crwd_001"
        ),
        NormalizedArticle(
            source="financial_rss",
            source_id="item_002",
            title="Federal Reserve announces interest rate hike to 5.5%",
            raw_content="Central bank raises rates amid persistent CPI inflation.",
            url="https://example.com/fed-rate-hike-55",
            publisher="Economics Daily",
            published_at=now,
            fetched_at=now,
            dedup_key="dedup_fed_002"
        )
    ]

    mock_rss = MockSourceAdapter(mock_articles)
    coordinator = IngestionCoordinator(rss_adapter=mock_rss)

    # 1. First Run: Inserts 2 articles and generates 2 signals
    res1 = coordinator.run_ingestion(
        db=db_session,
        sources=["financial_rss"],
        mode="live",
        run_nlp=True
    )
    assert res1.articles_fetched == 2
    assert res1.articles_persisted == 2
    assert res1.duplicates_skipped == 0
    assert res1.signals_generated == 2

    # Verify in DB
    db_articles_count = db_session.query(Article).count()
    db_signals_count = db_session.query(RiskSignal).count()
    assert db_articles_count == 2
    assert db_signals_count == 2

    # 2. Second Run with identical articles: Idempotency check
    res2 = coordinator.run_ingestion(
        db=db_session,
        sources=["financial_rss"],
        mode="live",
        run_nlp=True
    )
    assert res2.articles_fetched == 2
    assert res2.articles_persisted == 0
    assert res2.duplicates_skipped == 2
    assert res2.signals_generated == 0

    # DB counts MUST NOT grow
    assert db_session.query(Article).count() == 2
    assert db_session.query(RiskSignal).count() == 2


def test_cross_provider_deduplication(db_session: Session):
    now = datetime.datetime.now(datetime.timezone.utc)
    shared_url = "https://reuters.com/business/tech-merger-deal-agreed"

    # GDELT and RSS report the same story with same canonical URL
    gdelt_art = NormalizedArticle(
        source="gdelt",
        source_id="gdelt_100",
        title="Major Tech Merger Deal Agreed in $15B Buyout",
        raw_content="Major Tech Merger Deal Agreed in $15B Buyout",
        url=shared_url,
        publisher="reuters.com",
        published_at=now,
        fetched_at=now,
        dedup_key="dedup_shared_100"
    )
    rss_art = NormalizedArticle(
        source="financial_rss",
        source_id="rss_200",
        title="Major Tech Merger Deal Agreed in $15B Buyout",
        raw_content="Companies signed definitive buyout and tender offer agreement.",
        url=shared_url,
        publisher="Reuters RSS",
        published_at=now,
        fetched_at=now,
        dedup_key="dedup_shared_100"
    )

    coordinator = IngestionCoordinator(
        gdelt_adapter=MockSourceAdapter([gdelt_art]),
        rss_adapter=MockSourceAdapter([rss_art])
    )

    res = coordinator.run_ingestion(
        db=db_session,
        sources=["gdelt", "financial_rss"],
        mode="live",
        run_nlp=True
    )

    # 2 fetched, but only 1 persisted due to URL collision
    assert res.articles_fetched == 2
    assert res.articles_persisted == 1
    assert res.duplicates_skipped == 1
    assert res.signals_generated == 1


def test_replay_mode_labelling_and_provenance(db_session: Session):
    coordinator = IngestionCoordinator()
    res = coordinator.run_ingestion(
        db=db_session,
        mode="replay",
        limit_per_source=3,
        run_nlp=True
    )

    assert res.articles_persisted >= 3
    assert res.signals_generated >= 3

    # Check signals in DB
    replay_signals = db_session.query(RiskSignal).all()
    for sig in replay_signals:
        assert sig.article.source == "replay_fixture"
        assert sig.inference_mode == "synthetic"
        assert "Archive" in sig.article.publisher or "DOJ" in sig.article.publisher


def test_one_provider_failing_while_other_succeeds(db_session: Session):
    now = datetime.datetime.now(datetime.timezone.utc)
    good_art = NormalizedArticle(
        source="financial_rss",
        source_id="rss_ok",
        title="Apple reports quarterly earnings beat",
        raw_content="Apple reported profit growth and higher iPhone sales.",
        url="https://example.com/aapl-beat",
        publisher="MarketWatch",
        published_at=now,
        fetched_at=now,
        dedup_key="dedup_aapl_ok"
    )

    # Failing GDELT adapter
    mock_gdelt = MockSourceAdapter([], status="error")
    mock_gdelt.fetch_articles = MagicMock(side_effect=Exception("GDELT connection failed"))

    mock_rss = MockSourceAdapter([good_art], status="healthy")

    coordinator = IngestionCoordinator(gdelt_adapter=mock_gdelt, rss_adapter=mock_rss)
    res = coordinator.run_ingestion(
        db=db_session,
        sources=["gdelt", "financial_rss"],
        mode="live",
        run_nlp=True
    )

    # Should not crash; RSS article should still be persisted
    assert res.articles_persisted == 1
    assert res.signals_generated == 1
    assert any("GDELT exception" in d for d in res.details)
