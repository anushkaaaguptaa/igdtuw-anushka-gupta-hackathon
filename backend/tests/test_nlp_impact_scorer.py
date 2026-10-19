import pytest
from app.services.nlp.classifier import EventCategory
from app.services.nlp.entity_resolver import ResolvedEntity
from app.services.nlp.impact_scorer import calculate_impact_score


def _make_entity(ticker: str, is_primary: bool = True) -> ResolvedEntity:
    return ResolvedEntity(
        ticker=ticker,
        name=f"{ticker} Corp",
        sector="Information Technology",
        asset_class="Equity",
        relevance_score=1.0 if is_primary else 0.7,
        is_primary_target=is_primary,
        matched_text=ticker
    )


def test_high_impact_regulatory_event():
    # Regulatory Action (base 4.0) + Strong negative (-0.9 -> mag 2.7) + 2 entities (1.5) = 8.2 -> Impact 8
    entities = [_make_entity("MSFT", is_primary=True), _make_entity("GOOGL", is_primary=False)]
    result = calculate_impact_score(
        category=EventCategory.REGULATORY_ACTION,
        sentiment_score=-0.90,
        entities=entities
    )

    assert result.score >= 8
    assert result.score <= 10
    assert "REGULATORY_ACTION" in result.rationale
    assert result.base_severity == 4.0
    assert result.sentiment_magnitude == 2.7


def test_moderate_impact_earnings_event():
    # Earnings (base 2.5) + Mild negative (-0.3 -> mag 0.9) + 1 entity (1.0) = 4.4 -> Impact 4
    entities = [_make_entity("AAPL", is_primary=True)]
    result = calculate_impact_score(
        category=EventCategory.EARNINGS_FINANCIAL_RESULTS,
        sentiment_score=-0.30,
        entities=entities
    )

    assert result.score == 4
    assert result.base_severity == 2.5
    assert result.sentiment_magnitude == 0.9


def test_low_impact_uncertain_event():
    # Other/Uncertain (base 1.0) + Neutral sentiment (0.05 -> mag 0.15) + 0 entities (0.0) = 1.15 -> Impact 1
    result = calculate_impact_score(
        category=EventCategory.OTHER_UNCERTAIN,
        sentiment_score=0.05,
        entities=[]
    )

    assert result.score == 1
    assert result.base_severity == 1.0
    assert result.entity_scope == 0.0


def test_polarity_symmetry_sentiment_magnitude():
    """Event severity and magnitude should be symmetric between positive and negative surprises."""
    entities = [_make_entity("NVDA", is_primary=True)]
    neg_res = calculate_impact_score(EventCategory.PRODUCT_OPERATIONAL, -0.8, entities)
    pos_res = calculate_impact_score(EventCategory.PRODUCT_OPERATIONAL, +0.8, entities)

    # Magnitude is equal for |score| = 0.8
    assert neg_res.sentiment_magnitude == pos_res.sentiment_magnitude
    assert neg_res.score == pos_res.score


def test_score_never_exceeds_bounds():
    entities = [_make_entity(f"T{i}") for i in range(10)]
    # Extreme hypothetical max
    max_res = calculate_impact_score(EventCategory.GEOPOLITICAL, -1.0, entities)
    assert max_res.score <= 10

    # Extreme hypothetical min
    min_res = calculate_impact_score(EventCategory.OTHER_UNCERTAIN, 0.0, [])
    assert min_res.score >= 1
