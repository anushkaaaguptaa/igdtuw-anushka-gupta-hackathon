from typing import List
from dataclasses import dataclass
from app.services.nlp.classifier import EventCategory, CATEGORY_SEVERITY_WEIGHTS
from app.services.nlp.entity_resolver import ResolvedEntity


@dataclass
class ImpactResult:
    score: int  # Discrete scale: 1 to 10
    raw_score: float
    rationale: str
    base_severity: float
    sentiment_magnitude: float
    entity_scope: float


def calculate_impact_score(
    category: EventCategory,
    sentiment_score: float,
    entities: List[ResolvedEntity]
) -> ImpactResult:
    """
    Calculates a deterministic financial risk impact score (1 to 10).
    
    Principles:
    1. Event severity is derived strictly from event taxonomy type (e.g. regulatory, credit, geopolitical).
    2. Sentiment polarity (-1 to +1) is treated symmetrically via magnitude |score|; polarity is stored
       separately and does not artificially inflate or deflate the impact calculation.
    3. Portfolio exposure is decoupled and evaluated separately in the Portfolio Stress Engine.
    4. Entity scope reflects systemic relevance based on verified target count and headline salience.
    """
    # 1. Base Event Severity (1.0 to 4.5)
    base_severity = CATEGORY_SEVERITY_WEIGHTS.get(category, 1.0)

    # 2. Sentiment Magnitude Contribution (0.0 to 3.0)
    # Uses absolute magnitude so market-moving surprises (positive or negative) scale impact appropriately
    bounded_sentiment = max(-1.0, min(1.0, sentiment_score))
    sentiment_magnitude = abs(bounded_sentiment) * 3.0

    # 3. Entity Scope Contribution (0.0 to 2.5)
    # Measures the breadth and salience of verified corporate targets
    num_entities = len(entities)
    primary_targets = sum(1 for e in entities if e.is_primary_target)

    if num_entities == 0:
        entity_scope = 0.0
    else:
        # 0.5 per verified entity (up to 3) + 0.5 bonus if primary entity in headline
        base_entity_score = min(num_entities, 3) * 0.5
        primary_bonus = 0.5 if primary_targets > 0 else 0.0
        entity_scope = min(2.5, base_entity_score + primary_bonus)

    # 4. Composite Raw Score (Range ~1.0 to 10.0)
    raw_composite = base_severity + sentiment_magnitude + entity_scope
    discrete_score = max(1, min(10, round(raw_composite)))

    # 5. Formulate transparent audit rationale
    entity_summary = f"{num_entities} targets ({', '.join(e.ticker for e in entities[:3])})" if num_entities > 0 else "0 specific targets"
    rationale = (
        f"Event severity: {base_severity:.1f}/4.5 ({category.value}); "
        f"Sentiment magnitude: {sentiment_magnitude:.2f}/3.0 (|score| = {abs(bounded_sentiment):.2f}); "
        f"Entity scope: {entity_scope:.1f}/2.5 ({entity_summary}). "
        f"Raw sum: {raw_composite:.2f} -> Calibrated Impact: {discrete_score}/10."
    )

    return ImpactResult(
        score=discrete_score,
        raw_score=round(raw_composite, 4),
        rationale=rationale,
        base_severity=round(base_severity, 2),
        sentiment_magnitude=round(sentiment_magnitude, 2),
        entity_scope=round(entity_scope, 2)
    )
