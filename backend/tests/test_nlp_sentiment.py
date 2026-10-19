import pytest
from unittest.mock import MagicMock, patch
from app.services.nlp.sentiment import (
    LexiconSentimentModel,
    FinBertSentimentModel,
    SentimentPrediction
)


def test_lexicon_positive_sentiment():
    model = LexiconSentimentModel()
    text = "NVIDIA reports record quarterly profit surge and beats revenue guidance"
    pred = model.predict(text)

    assert pred.label == "positive"
    assert pred.score > 0.2
    assert pred.score <= 1.0
    assert pred.inference_mode == "lexicon_fallback"
    assert "positive" in pred.probabilities
    assert pred.probabilities["positive"] > pred.probabilities["negative"]


def test_lexicon_negative_sentiment():
    model = LexiconSentimentModel()
    text = "FTC files antitrust lawsuit against company alleging monopoly abuse and imposing fines"
    pred = model.predict(text)

    assert pred.label == "negative"
    assert pred.score < -0.2
    assert pred.score >= -1.0
    assert pred.inference_mode == "lexicon_fallback"
    assert pred.probabilities["negative"] > pred.probabilities["positive"]


def test_lexicon_neutral_sentiment():
    model = LexiconSentimentModel()
    text = "The Federal Reserve scheduled an ordinary committee meeting for next Tuesday"
    pred = model.predict(text)

    assert pred.label == "neutral"
    assert -0.2 <= pred.score <= 0.2
    assert pred.probabilities["neutral"] >= 0.5


def test_lexicon_negation_handling():
    model = LexiconSentimentModel()
    # Negated positive should skew negative
    negated_pos = "The corporation failed to achieve profit growth and did not meet quarterly targets"
    pred_neg = model.predict(negated_pos)
    assert pred_neg.score < 0.0

    # Negated negative should not trigger negative panic
    negated_neg = "The business suffered no losses and resolved the probe without penalty"
    pred_clear = model.predict(negated_neg)
    assert pred_clear.score >= -0.1


def test_lexicon_bounds_and_probabilities_sum():
    model = LexiconSentimentModel()
    test_cases = [
        "Catastrophic losses, default, bankruptcy, fraud probe, subpoenas, disaster",
        "Tremendous record profit, breakthrough surge, explosive growth, huge dividend",
        "Random ordinary text without any specific financial buzzwords",
        ""
    ]
    for text in test_cases:
        pred = model.predict(text)
        assert -1.0 <= pred.score <= 1.0
        prob_sum = sum(pred.probabilities.values())
        assert 0.98 <= prob_sum <= 1.02


def test_finbert_score_formula_and_mocked_inference():
    """Verify that FinBERT correctly computes score = P(positive) - P(negative)."""
    finbert = FinBertSentimentModel()

    # Mock the internal tokenizer and model
    mock_tokenizer = MagicMock()
    mock_model = MagicMock()
    mock_model.config.id2label = {0: "positive", 1: "negative", 2: "neutral"}

    # Mock logits outputting probs: [0.85, 0.05, 0.10] -> score = 0.85 - 0.05 = 0.80
    import torch
    mock_outputs = MagicMock()
    mock_outputs.logits = torch.tensor([[3.0, -1.0, 0.5]])  # Raw logits

    mock_model.return_value = mock_outputs

    finbert._tokenizer = mock_tokenizer
    finbert._model = mock_model
    finbert._device = torch.device("cpu")
    finbert._load_attempted = True
    finbert._load_successful = True

    pred = finbert.predict("Strong positive earnings update")

    assert pred.inference_mode == "neural_live"
    assert pred.model_version == "ProsusAI/finbert"
    assert -1.0 <= pred.score <= 1.0
    # Expected: P(pos) > P(neg)
    assert pred.probabilities["positive"] > pred.probabilities["negative"]
    expected_score = round(pred.probabilities["positive"] - pred.probabilities["negative"], 4)
    assert pred.score == expected_score


def test_finbert_graceful_fallback_on_model_failure():
    """Verify that if FinBERT fails to load or raises an exception, it falls back to lexicon."""
    finbert = FinBertSentimentModel()
    finbert._load_attempted = True
    finbert._load_successful = False  # Simulating failed weight load

    pred = finbert.predict("Huge profit and explosive growth")
    assert pred.inference_mode == "lexicon_fallback"
    assert pred.label == "positive"
    assert pred.model_version == "loughran-mcdonald-lexicon-v1"
