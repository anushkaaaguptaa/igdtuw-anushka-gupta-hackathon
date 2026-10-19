import pytest
from fastapi.testclient import TestClient


def test_api_ingest_trigger_replay_mode(client: TestClient):
    payload = {
        "sources": ["replay_fixture"],
        "limit_per_source": 3,
        "run_nlp": True,
        "mode": "replay"
    }

    resp = client.post("/api/v1/ingest/trigger", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["mode"] == "replay"
    assert data["articles_persisted"] >= 3
    assert data["signals_generated"] >= 3
    assert "batch_id" in data
    assert data["duration_ms"] > 0


def test_api_ingest_status_endpoint(client: TestClient):
    resp = client.get("/api/v1/ingest/status")
    assert resp.status_code == 200
    data = resp.json()

    assert "overall_status" in data
    assert "sources" in data
    assert len(data["sources"]) == 3
    source_names = [s["source"] for s in data["sources"]]
    assert "gdelt" in source_names
    assert "financial_rss" in source_names
    assert "replay_fixture" in source_names


def test_api_ingest_articles_list_and_filters(client: TestClient):
    # 1. Trigger replay to seed data
    client.post("/api/v1/ingest/trigger", json={"mode": "replay", "limit_per_source": 4, "run_nlp": True})

    # 2. Query all articles
    list_resp = client.get("/api/v1/ingest/articles")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 4
    assert len(data["items"]) >= 4

    # 3. Query with search filter
    search_resp = client.get("/api/v1/ingest/articles?search=CrowdStrike")
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert search_data["total"] >= 1
    assert "CrowdStrike" in search_data["items"][0]["title"]

    # 4. Check that generated signals appear in signals API
    sig_resp = client.get("/api/v1/signals")
    assert sig_resp.status_code == 200
    sig_data = sig_resp.json()
    assert sig_data["total"] >= 4
