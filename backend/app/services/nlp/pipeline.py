import re
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from app.services.nlp.sentiment import FinBertSentimentModel, SentimentPrediction
from app.services.nlp.classifier import (
    KeywordTaxonomyClassifier,
    EventCategory,
    EventClassificationResult
)
from app.services.nlp.entity_resolver import EntityResolver, ResolvedEntity
from app.services.nlp.impact_scorer import calculate_impact_score, ImpactResult
from app.core.logger import logger


@dataclass
class NLPAnalysisResult:
    sentiment_score: float
    sentiment_label: str
    sentiment_probabilities: Dict[str, float]
    event_category: str
    event_confidence: float
    impact_score: int
    impact_rationale: str
    evidence: str
    affected_entities: List[ResolvedEntity]
    inference_mode: str  # 'neural_live' or 'lexicon_fallback'
    model_version: str
    processing_status: str  # 'success', 'fallback'
    execution_time_ms: float


class RiskLensNLPEngine:
    """
    Master coordinator for RiskLens AI NLP inference.
    Executes sentiment analysis, event taxonomy classification, entity resolution,
    and impact scoring with end-to-end provenance tracking.
    """

    def __init__(
        self,
        sentiment_model: Optional[FinBertSentimentModel] = None,
        event_classifier: Optional[KeywordTaxonomyClassifier] = None,
        entity_resolver: Optional[EntityResolver] = None
    ):
        self.sentiment_model = sentiment_model or FinBertSentimentModel.get_instance()
        self.event_classifier = event_classifier or KeywordTaxonomyClassifier()
        self.entity_resolver = entity_resolver or EntityResolver()

    def _extract_evidence_snippet(self, text: str, headline: str, classifier_evidence: str) -> str:
        """Extracts the most salient sentence as evidence."""
        if headline and len(headline.strip()) > 10:
            return headline.strip()

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 15]
        if sentences:
            return sentences[0]
        return classifier_evidence

    def analyze(self, title: str, content: str = "") -> NLPAnalysisResult:
        start_time = time.perf_counter()
        clean_title = (title or "").strip()
        clean_content = (content or "").strip()
        full_text = f"{clean_title}. {clean_content}".strip()

        # 1. Financial Sentiment Inference
        sentiment_pred: SentimentPrediction = self.sentiment_model.predict(full_text)

        # 2. Event Classification
        classification: EventClassificationResult = self.event_classifier.predict(
            text=clean_content,
            headline=clean_title
        )

        # 3. Entity Extraction & Resolution
        entities: List[ResolvedEntity] = self.entity_resolver.resolve(
            text=clean_content,
            headline=clean_title
        )

        # 4. Deterministic Impact Scoring
        impact: ImpactResult = calculate_impact_score(
            category=classification.category,
            sentiment_score=sentiment_pred.score,
            entities=entities
        )

        # 5. Extract Evidence Snippet
        evidence = self._extract_evidence_snippet(clean_content, clean_title, classification.evidence)

        # 6. Provenance & Execution Timing
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        model_version = f"{sentiment_pred.model_version}+{classification.model_version}"
        processing_status = "success" if sentiment_pred.inference_mode == "neural_live" else "fallback"

        return NLPAnalysisResult(
            sentiment_score=sentiment_pred.score,
            sentiment_label=sentiment_pred.label,
            sentiment_probabilities=sentiment_pred.probabilities,
            event_category=classification.category.value,
            event_confidence=classification.confidence,
            impact_score=impact.score,
            impact_rationale=impact.rationale,
            evidence=evidence,
            affected_entities=entities,
            inference_mode=sentiment_pred.inference_mode,
            model_version=model_version,
            processing_status=processing_status,
            execution_time_ms=elapsed_ms
        )
