import pytest
from app.services.nlp.entity_resolver import EntityResolver


def test_explicit_dollar_ticker_resolution():
    resolver = EntityResolver()
    text = "Traders are buying calls on $NVDA and $AAPL ahead of market open"
    entities = resolver.resolve(text)

    tickers = [e.ticker for e in entities]
    assert "NVDA" in tickers
    assert "AAPL" in tickers
    for e in entities:
        assert e.asset_class == "Equity"
        assert e.sector == "Information Technology"


def test_company_name_alias_resolution():
    resolver = EntityResolver()
    headline = "CrowdStrike releases remediation script following outage"
    content = "JPMorgan analysts commented on the global impact."
    entities = resolver.resolve(content, headline=headline)

    tickers = [e.ticker for e in entities]
    assert "CRWD" in tickers
    assert "JPM" in tickers

    # CrowdStrike was in headline, so is_primary_target should be True
    crwd_entity = next(e for e in entities if e.ticker == "CRWD")
    assert crwd_entity.is_primary_target is True
    assert crwd_entity.relevance_score == 1.0

    # JPMorgan was in content, so is_primary_target should be False
    jpm_entity = next(e for e in entities if e.ticker == "JPM")
    assert jpm_entity.is_primary_target is False
    assert jpm_entity.relevance_score < 1.0


def test_avoids_false_positive_common_words():
    resolver = EntityResolver()
    # "ALL", "IT", "CAN", "ON" should not resolve to fake companies
    text = "It can be all or nothing when investors go to Wall Street on Monday morning"
    entities = resolver.resolve(text)
    assert len(entities) == 0


def test_avoids_apple_fruit_false_positive():
    resolver = EntityResolver()
    text = "Autumn harvest brings fresh apple pie and cider to local orchard market"
    entities = resolver.resolve(text)
    assert len(entities) == 0

    # But Apple in corporate context resolves correctly:
    corp_text = "Apple reports strong iPhone demand across European markets"
    entities_corp = resolver.resolve(corp_text)
    assert any(e.ticker == "AAPL" for e in entities_corp)


def test_deduplication_of_repeated_mentions():
    resolver = EntityResolver()
    text = "NVIDIA CEO Jensen Huang said NVIDIA will accelerate AI. Buy $NVDA now."
    entities = resolver.resolve(text)

    # Should only produce one NVDA record
    assert len(entities) == 1
    assert entities[0].ticker == "NVDA"
