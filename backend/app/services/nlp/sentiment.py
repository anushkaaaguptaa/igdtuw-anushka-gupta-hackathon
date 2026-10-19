import re
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from app.core.logger import logger


@dataclass
class SentimentPrediction:
    score: float  # Bounded between -1.0 and +1.0: P(pos) - P(neg)
    label: str    # 'positive', 'neutral', or 'negative'
    probabilities: Dict[str, float]  # {'positive': ..., 'neutral': ..., 'negative': ...}
    inference_mode: str  # 'neural_live' or 'lexicon_fallback'
    model_version: str


class LexiconSentimentModel:
    """
    Deterministic rule-based financial sentiment analyzer using
    the Loughran & McDonald financial sentiment lexicon.
    Acts as a guaranteed offline fallback whenever neural models cannot be loaded.
    """

    NEGATIVE_TERMS = {
        "loss", "losses", "default", "defaults", "defaulted", "defaulting",
        "probe", "probes", "probed", "investigation", "lawsuit", "lawsuits",
        "sued", "suing", "breach", "breached", "subpoena", "fraud", "fraudulent",
        "downgrade", "downgrades", "downgraded", "slump", "slumps", "slumped",
        "crash", "crashes", "crashed", "bankruptcy", "bankrupt", "insolvent",
        "insolvency", "deficit", "liability", "liabilities", "sanction", "sanctions",
        "fine", "fined", "fines", "penalty", "penalties", "halt", "halted",
        "miss", "misses", "missed", "decline", "declines", "declined", "warning",
        "drop", "drops", "dropped", "outage", "outages", "vulnerability", "plunge",
        "plunges", "plunged", "antitrust", "curb", "curbs", "curbed", "layoffs"
    }

    POSITIVE_TERMS = {
        "profit", "profits", "profitable", "gain", "gains", "gained",
        "surge", "surges", "surged", "growth", "growing", "grew", "record",
        "beat", "beats", "beating", "exceed", "exceeds", "exceeded",
        "outperform", "outperforms", "breakthrough", "upgrade", "upgrades",
        "upgraded", "expansion", "expanded", "dividend", "dividends", "rally",
        "rallies", "rallied", "recovery", "recovered", "soar", "soars", "soared",
        "strong", "bullish", "approval", "approved", "revenue", "innovative",
        "synergy", "synergies", "inflow", "inflows", "milestone"
    }

    NEGATORS = {
        "not", "never", "no", "without", "hardly", "barely",
        "failed", "fails", "fail", "lack", "lacks", "lacking", "neither", "nor", "cannot"
    }

    def predict(self, text: str) -> SentimentPrediction:
        tokens = re.findall(r"\b[a-zA-Z\-']+\b", text.lower())
        pos_count = 0.0
        neg_count = 0.0

        for i, word in enumerate(tokens):
            is_negated = False
            # Check previous 3 words for negation
            start_window = max(0, i - 3)
            for prev_word in tokens[start_window:i]:
                if prev_word in self.NEGATORS:
                    is_negated = True
                    break

            if word in self.NEGATIVE_TERMS:
                if is_negated:
                    pos_count += 0.5
                else:
                    neg_count += 1.0
            elif word in self.POSITIVE_TERMS:
                if is_negated:
                    neg_count += 1.2
                else:
                    pos_count += 1.0

        total_matches = pos_count + neg_count
        if total_matches == 0:
            p_pos, p_neu, p_neg = 0.15, 0.70, 0.15
            score = 0.0
            label = "neutral"
        else:
            diff = pos_count - neg_count
            norm_diff = diff / max(total_matches, 3.0)
            score = max(-1.0, min(1.0, norm_diff))

            if score > 0.15:
                label = "positive"
                p_pos = min(0.90, 0.40 + abs(score) * 0.50)
                p_neg = max(0.05, 0.20 - abs(score) * 0.15)
                p_neu = max(0.05, 1.0 - (p_pos + p_neg))
            elif score < -0.15:
                label = "negative"
                p_neg = min(0.90, 0.40 + abs(score) * 0.50)
                p_pos = max(0.05, 0.20 - abs(score) * 0.15)
                p_neu = max(0.05, 1.0 - (p_pos + p_neg))
            else:
                label = "neutral"
                p_neu = 0.65
                p_pos = 0.175
                p_neg = 0.175

        return SentimentPrediction(
            score=round(score, 4),
            label=label,
            probabilities={
                "positive": round(p_pos, 4),
                "neutral": round(p_neu, 4),
                "negative": round(p_neg, 4)
            },
            inference_mode="lexicon_fallback",
            model_version="loughran-mcdonald-lexicon-v1"
        )


class FinBertSentimentModel:
    """
    Financial sentiment analyzer powered by ProsusAI/finbert.
    Uses singleton lazy-loading to ensure model weights are loaded exactly once.
    Falls back to LexiconSentimentModel if weights cannot be loaded or inference fails.
    """

    _instance: Optional["FinBertSentimentModel"] = None
    _tokenizer = None
    _model = None
    _device = None
    _load_attempted = False
    _load_successful = False

    def __init__(self, fallback_model: Optional[LexiconSentimentModel] = None):
        self.fallback = fallback_model or LexiconSentimentModel()

    @classmethod
    def get_instance(cls) -> "FinBertSentimentModel":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_model(self) -> bool:
        if self._load_attempted:
            return self._load_successful

        self._load_attempted = True
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForSequenceClassification

            model_name = "ProsusAI/finbert"
            logger.info(f"Loading {model_name} for financial sentiment analysis...")

            # Check Apple Silicon MPS or fallback to CPU
            if torch.backends.mps.is_available():
                self._device = torch.device("mps")
            else:
                self._device = torch.device("cpu")

            self._tokenizer = AutoTokenizer.from_pretrained(model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(model_name)
            self._model.to(self._device)
            self._model.eval()

            self._load_successful = True
            logger.info(f"Successfully loaded {model_name} on device: {self._device}")
            return True
        except Exception as exc:
            logger.warning(
                f"Failed to load FinBERT ({exc}). Activating Loughran-McDonald lexicon fallback."
            )
            self._load_successful = False
            return False

    def predict(self, text: str) -> SentimentPrediction:
        """
        Calculates sentiment_score = P(positive) - P(negative) in [-1.0, +1.0].
        Returns class probabilities alongside label and score.
        """
        if not text or not text.strip():
            return SentimentPrediction(
                score=0.0,
                label="neutral",
                probabilities={"positive": 0.0, "neutral": 1.0, "negative": 0.0},
                inference_mode="lexicon_fallback",
                model_version="empty_input"
            )

        if not self._load_model():
            return self.fallback.predict(text)

        try:
            import torch
            import torch.nn.functional as F

            # FinBERT tokenizer truncated to 512 tokens max
            inputs = self._tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            ).to(self._device)

            with torch.no_grad():
                outputs = self._model(**inputs)
                logits = outputs.logits
                probs = F.softmax(logits, dim=1).squeeze().cpu().tolist()

            # FinBERT label order: [positive, negative, neutral]
            # Verify id2label from config
            id2label = self._model.config.id2label
            prob_map = {id2label[i].lower(): float(probs[i]) for i in range(len(probs))}

            p_pos = round(prob_map.get("positive", 0.0), 4)
            p_neg = round(prob_map.get("negative", 0.0), 4)
            p_neu = round(prob_map.get("neutral", 0.0), 4)

            # Continuous sentiment score: P(pos) - P(neg) bounded between -1.0 and +1.0
            score = round(max(-1.0, min(1.0, p_pos - p_neg)), 4)

            # Determine dominant label
            if p_pos > p_neg and p_pos > p_neu:
                label = "positive"
            elif p_neg > p_pos and p_neg > p_neu:
                label = "negative"
            else:
                label = "neutral"

            return SentimentPrediction(
                score=score,
                label=label,
                probabilities={
                    "positive": p_pos,
                    "neutral": p_neu,
                    "negative": p_neg
                },
                inference_mode="neural_live",
                model_version="ProsusAI/finbert"
            )
        except Exception as exc:
            logger.error(f"Inference error in FinBERT ({exc}). Using lexicon fallback.")
            return self.fallback.predict(text)
