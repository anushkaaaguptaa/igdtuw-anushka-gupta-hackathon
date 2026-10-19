import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from app.core.logger import logger


class EventCategory(str, Enum):
    GEOPOLITICAL = "GEOPOLITICAL"
    MACROECONOMIC = "MACROECONOMIC"
    CREDIT_EVENT = "CREDIT_EVENT"
    REGULATORY_ACTION = "REGULATORY_ACTION"
    MERGERS_AND_ACQUISITIONS = "MERGERS_AND_ACQUISITIONS"
    EARNINGS_FINANCIAL_RESULTS = "EARNINGS_FINANCIAL_RESULTS"
    PRODUCT_OPERATIONAL = "PRODUCT_OPERATIONAL"
    OTHER_UNCERTAIN = "OTHER_UNCERTAIN"


# Baseline severity scale (1.0 to 5.0) reflecting the systemic transmission risk of each event type
CATEGORY_SEVERITY_WEIGHTS: Dict[EventCategory, float] = {
    EventCategory.GEOPOLITICAL: 4.5,
    EventCategory.REGULATORY_ACTION: 4.0,
    EventCategory.CREDIT_EVENT: 4.0,
    EventCategory.PRODUCT_OPERATIONAL: 3.5,
    EventCategory.MACROECONOMIC: 3.5,
    EventCategory.EARNINGS_FINANCIAL_RESULTS: 2.5,
    EventCategory.MERGERS_AND_ACQUISITIONS: 2.5,
    EventCategory.OTHER_UNCERTAIN: 1.0,
}


@dataclass
class EventClassificationResult:
    category: EventCategory
    confidence: float  # Calibrated score 0.0 to 1.0
    evidence: str
    inference_mode: str  # 'rule_taxonomy', 'neural_live', 'fallback'
    model_version: str


class KeywordTaxonomyClassifier:
    """
    Deterministic financial event classifier using curated multi-token pattern dictionaries.
    Provides fast, reproducible, and calibrated risk taxonomy categorization.
    """

    PATTERNS: Dict[EventCategory, List[str]] = {
        EventCategory.GEOPOLITICAL: [
            "sanction", "sanctions", "tariff", "tariffs", "trade war", "embargo",
            "export control", "military", "geopolitical", "conflict", "taiwan strait",
            "middle east tension", "national security risk", "foreign policy"
        ],
        EventCategory.MACROECONOMIC: [
            "interest rate", "rate hike", "rate cut", "federal reserve", "central bank",
            "inflation", "cpi", "stagflation", "recession", "gdp contraction",
            "unemployment", "monetary policy", "quantitative tightening", "treasury yield"
        ],
        EventCategory.CREDIT_EVENT: [
            "default", "defaults", "downgrade", "credit rating", "junk bond",
            "insolvency", "bankruptcy", "debt restructuring", "liquidity crisis",
            "bank run", "debt ceiling", "credit default swap", "distressed debt"
        ],
        EventCategory.REGULATORY_ACTION: [
            "sec investigation", "probe", "antitrust", "ftc", "lawsuit", "sued",
            "subpoena", "regulatory enforcement", "monopoly", "injunction", "doj probe",
            "insider trading", "compliance violation", "fine", "penalties"
        ],
        EventCategory.MERGERS_AND_ACQUISITIONS: [
            "acquisition", "acquires", "merger", "buyout", "takeover", "hostile bid",
            "tender offer", "spin-off", "divestiture", "deal agreed", "private equity buyout"
        ],
        EventCategory.EARNINGS_FINANCIAL_RESULTS: [
            "quarterly results", "earnings miss", "revenue beat", "guidance cut",
            "profit warning", "eps miss", "q1", "q2", "q3", "q4", "fiscal year",
            "operating margin", "sales slump", "topline growth", "guidance lowered",
            "quarterly revenue", "quarterly earnings", "earnings report", "earnings",
            "profit growth", "revenue surge", "financial results", "quarterly profit",
            "beat expectations", "missed expectations", "net income", "operating profit"
        ],
        EventCategory.PRODUCT_OPERATIONAL: [
            "cyberattack", "data breach", "ransomware", "it outage", "system halt",
            "supply chain halt", "factory explosion", "grounded fleet", "chip shortage",
            "product recall", "safety warning", "plant shutdown", "service interruption"
        ],
    }

    def predict(self, text: str, headline: Optional[str] = None) -> EventClassificationResult:
        full_text = f"{headline or ''} {text}".lower()
        headline_lower = (headline or "").lower()

        scores: Dict[EventCategory, float] = {cat: 0.0 for cat in EventCategory}
        evidence_snippets: Dict[EventCategory, List[str]] = {cat: [] for cat in EventCategory}

        for cat, patterns in self.PATTERNS.items():
            for pat in patterns:
                # Match whole phrase/token
                regex = r"\b" + re.escape(pat) + r"\b"
                body_matches = len(re.findall(regex, full_text))
                headline_matches = len(re.findall(regex, headline_lower))

                if headline_matches > 0 or body_matches > 0:
                    # Weight headline matches 2.5x higher than body mentions
                    match_score = (headline_matches * 2.5) + (body_matches * 1.0)
                    scores[cat] += match_score
                    evidence_snippets[cat].append(pat)

        # Find category with maximum score
        best_cat = EventCategory.OTHER_UNCERTAIN
        best_score = 0.0

        for cat, sc in scores.items():
            if sc > best_score:
                best_score = sc
                best_cat = cat

        if best_score == 0.0:
            return EventClassificationResult(
                category=EventCategory.OTHER_UNCERTAIN,
                confidence=0.20,
                evidence="No distinctive financial risk taxonomy keywords matched.",
                inference_mode="rule_taxonomy",
                model_version="keyword-taxonomy-v1"
            )

        # Calibrate confidence based on match count and specificity
        # Cap confidence at 0.88 for rule-based classifier (avoid claiming 1.0 certainty)
        confidence = min(0.88, 0.45 + (best_score * 0.10))
        matched_terms = ", ".join(evidence_snippets[best_cat][:3])
        evidence = f"Matched event markers: [{matched_terms}]"

        return EventClassificationResult(
            category=best_cat,
            confidence=round(confidence, 4),
            evidence=evidence,
            inference_mode="rule_taxonomy",
            model_version="keyword-taxonomy-v1"
        )
