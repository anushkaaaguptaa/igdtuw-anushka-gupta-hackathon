import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.services.nlp.pipeline import RiskLensNLPEngine


def test_nlp_engine_full_analysis():
    engine = RiskLensNLPEngine()
    title = "FTC launches formal antitrust probe into Microsoft cloud partnership with OpenAI"
    content = "Federal regulators issued subpoenas seeking details on exclusive agreements and AI market monopolization."
    
    result = engine.analyze(title=title, content=content)

    assert result.event_category == "REGULATORY_ACTION"
    assert result.sentiment_score < 0.0  # Probe/antitrust/subpoena
    assert result.impact_score >= 7
    assert len(result.affected_entities) >= 1
    assert any(e.ticker == "MSFT" for e in result.affected_entities)
    assert result.inference_mode in ["neural_live", "lexicon_fallback"]
    assert "positive" in result.sentiment_probabilities
    assert "negative" in result.sentiment_probabilities
    assert result.execution_time_ms > 0


def test_api_analyze_endpoint_transient(client: TestClient):
    """Test POST /api/v1/signals/analyze with save_to_db=False (ephemeral preview)."""
    payload = {
        "title": "CrowdStrike releases remediation update after global IT outage and system crash",
        "content": "A faulty sensor deployment disrupted airlines and enterprise operations worldwide.",
        "save_to_db": False
    }

    response = client.post("/api/v1/signals/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "signal" in data
    assert "execution_time_ms" in data
    sig = data["signal"]
    assert sig["id"].startswith("preview_")
    assert sig["event_category"] == "PRODUCT_OPERATIONAL"
    assert sig["sentiment_score"] < 0
    assert sig["impact_score"] >= 6
    assert any(e["ticker"] == "CRWD" for e in sig["affected_entities"])
    assert sig["sentiment_probabilities"] is not None

    # Verify NOT saved in DB
    list_resp = client.get(f"/api/v1/signals/{sig['id']}")
    assert list_resp.status_code == 404


def test_api_analyze_endpoint_persistent(client: TestClient):
    """Test POST /api/v1/signals/analyze with save_to_db=True (committed to SQLite)."""
    payload = {
        "title": "NVIDIA posts record quarterly revenue surging 120% on AI chip demand",
        "content": "The company reported massive profit growth and beat Wall Street expectations.",
        "save_to_db": True,
        "source": "manual_test"
    }

    response = client.post("/api/v1/signals/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    sig = data["signal"]
    assert not sig["id"].startswith("preview_")
    assert sig["event_category"] == "EARNINGS_FINANCIAL_RESULTS"
    assert sig["sentiment_score"] > 0
    assert any(e["ticker"] == "NVDA" for e in sig["affected_entities"])

    # Verify it IS saved in DB and queryable via GET /signals/{id}
    fetch_resp = client.get(f"/api/v1/signals/{sig['id']}")
    assert fetch_resp.status_code == 200
    fetched_data = fetch_resp.json()
    assert fetched_data["id"] == sig["id"]
    assert fetched_data["article"]["title"] == payload["title"]
    assert fetched_data["sentiment_probabilities"] is not None


def test_nlp_pipeline_fallback_provenance_when_model_load_fails():
    """Verify that when FinBERT loading fails, pipeline degrades safely to lexicon_fallback with full provenance."""
    from unittest.mock import patch
    from app.services.nlp.sentiment import FinBertSentimentModel, LexiconSentimentModel

    isolated_sentiment = FinBertSentimentModel(fallback_model=LexiconSentimentModel())
    with patch.object(isolated_sentiment, "_load_model", return_value=False):
        engine = RiskLensNLPEngine(sentiment_model=isolated_sentiment)
        result = engine.analyze(
            title="Acme Industrial Enters Debt Restructuring After Defaulting on $500M Notes",
            content="Credit rating agency downgrades company to selective default following missed obligations."
        )

        assert result.inference_mode == "lexicon_fallback"
        assert result.processing_status == "fallback"
        assert "loughran-mcdonald-lexicon" in result.model_version
        assert result.sentiment_label == "negative"
        assert -1.0 <= result.sentiment_score <= 1.0
        assert sum(result.sentiment_probabilities.values()) == pytest.approx(1.0, abs=0.02)
        assert result.event_category == "CREDIT_EVENT"
        assert 1 <= result.impact_score <= 10


def test_replay_fixture_ingestion_labels_synthetic_provenance(client: TestClient):
    """Verify that historical replay fixtures are strictly labeled with inference_mode='synthetic'."""
    trigger_resp = client.post("/api/v1/ingest/trigger", json={
        "mode": "replay",
        "sources": ["replay_fixture"],
        "limit_per_source": 5,
        "run_nlp": True
    })
    assert trigger_resp.status_code == 200

    # Query signals from replay
    sig_resp = client.get("/api/v1/signals", params={"limit": 10})
    assert sig_resp.status_code == 200
    signals = sig_resp.json()["items"]
    
    # Check that any replay-sourced signal is labeled synthetic
    replay_signals = [s for s in signals if s.get("article") and s["article"].get("source") == "replay_fixture"]
    for s in replay_signals:
        assert s["inference_mode"] == "synthetic", f"Signal {s['id']} from replay must be synthetic, got {s['inference_mode']}"


def test_health_endpoint_reports_truthful_inference_mode(client: TestClient):
    """Verify that GET /health truthfully reports neural_live or lexicon_fallback, not mock."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["inference_mode"] in ("neural_live", "lexicon_fallback")
    assert data["inference_mode"] != "mock"

