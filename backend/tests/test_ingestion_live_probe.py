import pytest
from app.services.ingestion.rss_adapter import FinancialRSSAdapter
from app.services.ingestion.gdelt_adapter import GDELTAdapter


@pytest.mark.integration
def test_live_financial_rss_fetch():
    """Live probe verifying real financial RSS feeds parse genuine incoming news."""
    adapter = FinancialRSSAdapter()
    articles = adapter.fetch_articles(limit=5)

    # In network-connected environment, this returns genuine articles
    assert len(articles) > 0, "Expected at least 1 article from live financial RSS feed"
    first = articles[0]
    assert first.source == "financial_rss"
    assert len(first.title) > 5
    assert first.url.startswith("http")
    assert first.published_at is not None
    assert adapter.last_status == "healthy"


@pytest.mark.integration
def test_live_gdelt_fetch_or_rate_limit_handling():
    """
    Live probe verifying GDELT adapter against live GDELT 2.0 API.
    Must either successfully retrieve articles OR cleanly report rate_limited without raising an unhandled exception.
    """
    adapter = GDELTAdapter(timeout=10.0)
    articles = adapter.fetch_articles(limit=3, keywords=["stocks", "finance"])

    # If GDELT succeeds, articles > 0 and status == 'healthy'
    # If GDELT rate limits (common on shared IPs), status == 'rate_limited' or 'degraded'
    assert adapter.last_status in ["healthy", "rate_limited", "degraded"]
    if adapter.last_status == "healthy":
        assert len(articles) > 0
    else:
        assert len(articles) == 0
        assert adapter.last_error is not None
