import pytest
import httpx
from unittest.mock import MagicMock
from app.services.ingestion.gdelt_adapter import GDELTAdapter
from app.services.ingestion.rss_adapter import FinancialRSSAdapter
from app.services.ingestion.replay_adapter import ReplayFixtureAdapter


def test_gdelt_adapter_valid_response():
    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.text = '{"articles": [{"url": "https://reuters.com/news/123", "title": "FTC antitrust probe", "seendate": "20240125T140000Z", "domain": "reuters.com", "language": "English", "sourcecountry": "United States"}]}'
    mock_response.json.return_value = {
        "articles": [
            {
                "url": "https://reuters.com/news/123?utm_source=twitter",
                "title": "FTC launches antitrust probe into tech investments",
                "seendate": "20240125T140000Z",
                "domain": "reuters.com",
                "language": "English",
                "sourcecountry": "United States"
            }
        ]
    }
    mock_client.get.return_value = mock_response

    adapter = GDELTAdapter(client=mock_client)
    articles = adapter.fetch_articles(limit=5)

    assert len(articles) == 1
    art = articles[0]
    assert art.source == "gdelt"
    assert art.title == "FTC launches antitrust probe into tech investments"
    assert "utm_source" not in art.url
    assert art.publisher == "reuters.com"
    assert art.published_at.year == 2024
    assert adapter.last_status == "healthy"


def test_gdelt_adapter_handles_rate_limiting_429():
    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 429
    mock_response.text = "Please limit requests to one every 5 seconds"
    mock_client.get.return_value = mock_response

    adapter = GDELTAdapter(client=mock_client)
    articles = adapter.fetch_articles(limit=5)

    assert len(articles) == 0
    assert adapter.last_status == "rate_limited"
    assert "rate limit exceeded" in adapter.last_error


def test_gdelt_adapter_handles_timeout():
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.side_effect = httpx.TimeoutException("Connection timed out")

    adapter = GDELTAdapter(client=mock_client)
    articles = adapter.fetch_articles(limit=5)

    assert len(articles) == 0
    assert adapter.last_status == "degraded"
    assert "timed out" in adapter.last_error


def test_rss_adapter_valid_feed_parsing():
    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Yahoo Finance Top Headlines</title>
            <link>https://finance.yahoo.com</link>
            <description>Market Headlines</description>
            <item>
                <title>&lt;b&gt;NVIDIA&lt;/b&gt; Surges After Blowout AI Revenue Beat</title>
                <link>https://finance.yahoo.com/news/nvidia-blowout-earnings-12345.html?utm_campaign=feed</link>
                <description>&lt;p&gt;Quarterly profit exceeded expectations as cloud spending jumped.&lt;/p&gt;</description>
                <pubDate>Wed, 21 Feb 2024 21:05:00 GMT</pubDate>
                <guid>yahoo_12345</guid>
            </item>
        </channel>
    </rss>
    """
    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.text = sample_xml
    mock_client.get.return_value = mock_response

    adapter = FinancialRSSAdapter(feed_urls=["https://test.feed.com/rss"], client=mock_client)
    articles = adapter.fetch_articles(limit=5)

    assert len(articles) == 1
    art = articles[0]
    assert art.source == "financial_rss"
    assert art.title == "NVIDIA Surges After Blowout AI Revenue Beat"
    assert "<p>" not in art.raw_content
    assert "Quarterly profit exceeded expectations" in art.raw_content
    assert "utm_campaign" not in art.url
    assert art.published_at.year == 2024
    assert adapter.last_status == "healthy"


def test_rss_adapter_handles_http_failure_gracefully():
    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 503
    mock_response.text = "Service Unavailable"
    mock_client.get.return_value = mock_response

    adapter = FinancialRSSAdapter(feed_urls=["https://failing.feed.com/rss"], client=mock_client)
    articles = adapter.fetch_articles(limit=5)

    assert len(articles) == 0
    assert adapter.last_status == "error"


def test_replay_fixture_adapter_loads_historical_fixtures():
    adapter = ReplayFixtureAdapter()
    articles = adapter.fetch_articles(limit=10)

    assert len(articles) >= 5
    for art in articles:
        assert art.source == "replay_fixture"
        assert art.publisher is not None
        assert len(art.title) > 10
        assert art.metadata.get("is_replay_fixture") is True
    assert adapter.last_status == "healthy"
