import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.db_models import Article, Entity


def test_portfolio_seeding_and_exposure_api(client: TestClient):
    # 1. Seed sample portfolio
    seed_resp = client.post("/api/v1/portfolios/sample/seed")
    assert seed_resp.status_code == 201
    port_data = seed_resp.json()
    assert port_data["id"] == "port_multi_asset_sample"
    assert port_data["name"] == "Global Multi-Asset Alpha Portfolio"
    assert len(port_data["assets"]) >= 5
    assert port_data["current_total_value"] > 0

    # 2. Verify portfolio listed in GET /portfolios
    list_resp = client.get("/api/v1/portfolios")
    assert list_resp.status_code == 200
    all_ports = list_resp.json()
    assert len(all_ports) >= 1
    assert any(p["id"] == "port_multi_asset_sample" for p in all_ports)

    # 3. Test exposure breakdown endpoint
    exposure_resp = client.get(f"/api/v1/portfolios/{port_data['id']}/exposure")
    assert exposure_resp.status_code == 200
    exp_data = exposure_resp.json()
    assert exp_data["portfolio_id"] == port_data["id"]
    assert len(exp_data["sector_exposures"]) >= 3
    # Check that sector weights sum up to approximately 1.0
    total_weight = sum(item["weight"] for item in exp_data["sector_exposures"])
    assert 0.99 <= total_weight <= 1.01


def test_signals_crud_and_filters(client: TestClient, db_session: Session):
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # 1. Direct DB seed for Article and Entity
    art = Article(
        id="art_news_1",
        source="rss_yahoo",
        title="CrowdStrike update causes widespread IT outage",
        url="https://example.com/crowdstrike-incident",
        published_at=now,
        raw_content="A software update deployed globally triggered system halts...",
        language="en"
    )
    crwd = Entity(ticker="CRWD", name="CrowdStrike Holdings", sector="Information Technology", asset_class="Equity")
    db_session.add_all([art, crwd])
    db_session.commit()

    # 2. Create signal via POST /api/v1/signals
    signal_payload = {
        "id": "sig_crwd_001",
        "article_id": "art_news_1",
        "sentiment_score": -0.92,
        "sentiment_label": "negative",
        "event_category": "CYBERSECURITY_BREACH",
        "event_confidence": 0.96,
        "impact_score": 9,
        "impact_rationale": "Global enterprise disruption directly attributed to faulty sensor update.",
        "evidence": "A software update deployed globally triggered system halts",
        "inference_mode": "mock",
        "model_version": "finbert-v1",
        "entity_tickers": ["CRWD"]
    }
    create_resp = client.post("/api/v1/signals", json=signal_payload)
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["id"] == "sig_crwd_001"
    assert created_data["impact_score"] == 9
    assert len(created_data["affected_entities"]) == 1
    assert created_data["affected_entities"][0]["ticker"] == "CRWD"

    # 3. Query signals with filter min_impact=8
    filt_resp = client.get("/api/v1/signals?min_impact=8")
    assert filt_resp.status_code == 200
    filt_data = filt_resp.json()
    assert filt_data["total"] >= 1
    assert filt_data["items"][0]["id"] == "sig_crwd_001"

    # 4. Query signals with filter min_impact=10 (should be empty)
    empty_resp = client.get("/api/v1/signals?min_impact=10")
    assert empty_resp.status_code == 200
    assert empty_resp.json()["total"] == 0

    # 5. Fetch single signal by ID
    single_resp = client.get("/api/v1/signals/sig_crwd_001")
    assert single_resp.status_code == 200
    assert single_resp.json()["article"]["title"] == "CrowdStrike update causes widespread IT outage"

    # 6. Fetch nonexistent signal (404)
    not_found_resp = client.get("/api/v1/signals/sig_nonexistent")
    assert not_found_resp.status_code == 404


def test_stress_test_simulation_contract(client: TestClient):
    # 1. Seed portfolio
    seed_resp = client.post("/api/v1/portfolios/sample/seed")
    port_id = seed_resp.json()["id"]

    # 2. Trigger simulation
    sim_payload = {
        "portfolio_id": port_id,
        "scenario_name": "Cybersecurity Global Disruption Shock",
        "severity_multiplier": 1.5
    }
    sim_resp = client.post("/api/v1/stress-test/simulate", json=sim_payload)
    assert sim_resp.status_code == 200
    sim_data = sim_resp.json()
    assert sim_data["portfolio_id"] == port_id
    assert sim_data["baseline_value"] > 0
    assert "asset_shocks" in sim_data
    assert len(sim_data["asset_shocks"]) > 0

    # 3. Check simulation run history
    runs_resp = client.get("/api/v1/stress-test/runs")
    assert runs_resp.status_code == 200
    runs = runs_resp.json()
    assert len(runs) >= 1
    assert runs[0]["scenario_name"] == "Cybersecurity Global Disruption Shock"
