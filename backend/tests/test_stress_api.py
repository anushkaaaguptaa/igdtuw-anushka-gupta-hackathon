import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.db_models import RiskSignal
from app.services.nlp.classifier import EventCategory


def test_list_stress_scenarios_api(client: TestClient):
    """Verify GET /api/v1/stress-test/scenarios lists all 5 canonical scenarios."""
    resp = client.get("/api/v1/stress-test/scenarios")
    assert resp.status_code == 200
    scenarios = resp.json()
    assert len(scenarios) == 5
    scenario_ids = [s["scenario_id"] for s in scenarios]
    assert "GEOPOLITICAL_ESCALATION" in scenario_ids
    assert "CENTRAL_BANK_RATE_HIKE" in scenario_ids
    assert "CREDIT_EVENT_OR_DEFAULT" in scenario_ids
    assert "BANKING_SECTOR_CRISIS" in scenario_ids
    assert "MACROECONOMIC_RECESSION" in scenario_ids


def test_wholesale_banking_portfolio_seeding_and_simulation(client: TestClient):
    """
    Test end-to-end wholesale portfolio seeding and stress test simulation:
    1. Seed wholesale banking portfolio
    2. Run simulation with CENTRAL_BANK_RATE_HIKE scenario
    3. Verify asset-class results, VaR/CVaR, and persistence
    """
    # 1. Seed wholesale portfolio
    seed_resp = client.post("/api/v1/portfolios/sample/wholesale")
    assert seed_resp.status_code == 201
    port = seed_resp.json()
    assert port["id"] == "port_wholesale_banking"
    assert len(port["assets"]) == 6
    assert port["current_total_value"] > 16_000_000.0

    # 2. Simulate stress test
    sim_payload = {
        "portfolio_id": port["id"],
        "scenario_id": "CENTRAL_BANK_RATE_HIKE",
        "severity_multiplier": 1.0
    }
    sim_resp = client.post("/api/v1/stress-test/simulate", json=sim_payload)
    assert sim_resp.status_code == 200
    sim = sim_resp.json()

    assert sim["simulation_id"].startswith("sim_")
    assert sim["portfolio_id"] == "port_wholesale_banking"
    assert sim["scenario_id"] == "CENTRAL_BANK_RATE_HIKE"
    assert sim["baseline_value"] > 16_000_000.0
    assert sim["stressed_value"] < sim["baseline_value"]
    assert sim["total_loss"] > 0
    assert sim["credit_loss"] >= 0
    assert sim["market_loss"] > 0
    assert abs(sim["total_loss"] - (sim["credit_loss"] + sim["market_loss"])) < 0.05

    # Check breakdown by asset type
    assert "equity" in sim["loss_by_asset_type"]
    assert "government_bond" in sim["loss_by_asset_type"]
    assert "corporate_bond" in sim["loss_by_asset_type"]
    assert "corporate_loan" in sim["loss_by_asset_type"]
    assert "derivative" in sim["loss_by_asset_type"]

    # Check VaR / CVaR
    assert sim["var_95"] > 0
    assert sim["var_99"] >= sim["var_95"]
    assert sim["cvar_95"] >= sim["var_95"]

    # 3. Retrieve historical run
    run_id = sim["simulation_id"]
    get_run_resp = client.get(f"/api/v1/stress-test/runs/{run_id}")
    assert get_run_resp.status_code == 200
    run_data = get_run_resp.json()
    assert run_data["id"] == run_id
    assert run_data["scenario_id"] == "CENTRAL_BANK_RATE_HIKE"
    assert run_data["total_loss"] == sim["total_loss"]


def test_api_duplicate_prevention_and_manual_rerun(client: TestClient, db_session: Session):
    """
    Test that the simulate endpoint prevents accidental duplicate automatic runs
    for the same event and portfolio when allow_duplicate=False, but allows manual rerun
    when allow_duplicate=True.
    """
    # 1. Ensure portfolio is seeded
    client.post("/api/v1/portfolios/sample/wholesale")

    # 2. Persist a test signal
    sig = RiskSignal(
        id="sig_dup_test_001",
        article_id="art_test",
        sentiment_score=-0.85,
        sentiment_label="negative",
        event_category=EventCategory.CREDIT_EVENT.value,
        event_confidence=0.92,
        impact_score=9,
        impact_rationale="Systemic corporate credit downgrade wave.",
        evidence="Rating agency downgrades 40 corporate issuers.",
        inference_mode="mock",
        model_version="finbert-v1"
    )
    db_session.add(sig)
    db_session.commit()

    # 3. First simulation run (allowed)
    req_1 = {
        "portfolio_id": "port_wholesale_banking",
        "signal_id": "sig_dup_test_001",
        "allow_duplicate": False
    }
    resp_1 = client.post("/api/v1/stress-test/simulate", json=req_1)
    assert resp_1.status_code == 200
    run_1_id = resp_1.json()["simulation_id"]

    # 4. Second simulation run with allow_duplicate=False -> MUST return 409 Conflict
    resp_2 = client.post("/api/v1/stress-test/simulate", json=req_1)
    assert resp_2.status_code == 409
    assert "already been recorded" in resp_2.json()["detail"]

    # 5. Third simulation run with allow_duplicate=True -> MUST succeed with separate run ID
    req_3 = {
        "portfolio_id": "port_wholesale_banking",
        "signal_id": "sig_dup_test_001",
        "allow_duplicate": True
    }
    resp_3 = client.post("/api/v1/stress-test/simulate", json=req_3)
    assert resp_3.status_code == 200
    run_3_id = resp_3.json()["simulation_id"]
    assert run_3_id != run_1_id


def test_api_invalid_requests_and_error_handling(client: TestClient, db_session: Session):
    """Verify that invalid inputs return appropriate HTTP status codes."""
    # 1. Nonexistent portfolio -> 404
    resp_bad_port = client.post("/api/v1/stress-test/simulate", json={
        "portfolio_id": "port_nonexistent_12345",
        "scenario_id": "CENTRAL_BANK_RATE_HIKE"
    })
    assert resp_bad_port.status_code == 404
    assert "does not exist" in resp_bad_port.json()["detail"]

    # 2. Nonexistent signal -> 404
    client.post("/api/v1/portfolios/sample/wholesale")
    resp_bad_sig = client.post("/api/v1/stress-test/simulate", json={
        "portfolio_id": "port_wholesale_banking",
        "signal_id": "sig_nonexistent_99999"
    })
    assert resp_bad_sig.status_code == 404
    assert "not found" in resp_bad_sig.json()["detail"]

    # 3. Nonexistent scenario -> 400 with list of available scenarios
    resp_bad_scen = client.post("/api/v1/stress-test/simulate", json={
        "portfolio_id": "port_wholesale_banking",
        "scenario_id": "ALIEN_INVASION_CRASH"
    })
    assert resp_bad_scen.status_code == 400
    assert "Available scenarios" in resp_bad_scen.json()["detail"]

    # 4. Nonexistent run lookup -> 404
    resp_bad_run = client.get("/api/v1/stress-test/runs/run_does_not_exist")
    assert resp_bad_run.status_code == 404


def test_api_configurable_var_draws(client: TestClient):
    """Verify that clients can optionally specify custom Monte Carlo draw counts."""
    client.post("/api/v1/portfolios/sample/wholesale")
    resp = client.post("/api/v1/stress-test/simulate", json={
        "portfolio_id": "port_wholesale_banking",
        "scenario_id": "CENTRAL_BANK_RATE_HIKE",
        "var_simulations": 500
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "500 draws" in data["var_methodology"]
    assert data["var_95"] > 0
    assert data["var_99"] >= data["var_95"]


def test_authoritative_wholesale_portfolio_exact_reconciliation(client: TestClient):
    """
    Authoritative QA Regression Test:
    Verify the 6-holding wholesale banking portfolio ($16,993,750 baseline)
    and exact penny-level financial loss reconciliation under CENTRAL_BANK_RATE_HIKE.
    """
    # 1. Seed or fetch wholesale portfolio
    seed_resp = client.post("/api/v1/portfolios/sample/wholesale")
    assert seed_resp.status_code in (200, 201)
    port = seed_resp.json()
    assert port["id"] == "port_wholesale_banking"
    assert port["current_total_value"] == 16993750.00
    assert len(port["assets"]) == 6

    # Verify each holding market value
    holdings_by_ticker = {a["ticker"]: a for a in port["assets"]}
    assert set(holdings_by_ticker.keys()) == {
        "ACME_CORP_LOAN", "US_TREASURY_10Y", "MS_CORP_BOND_5Y", "NVDA", "AAPL", "SPX_PUT_HEDGE"
    }
    assert holdings_by_ticker["ACME_CORP_LOAN"]["market_value"] == 4943750.00
    assert holdings_by_ticker["US_TREASURY_10Y"]["market_value"] == 4000000.00
    assert holdings_by_ticker["MS_CORP_BOND_5Y"]["market_value"] == 3000000.00
    assert holdings_by_ticker["NVDA"]["market_value"] == 2600000.00
    assert holdings_by_ticker["AAPL"]["market_value"] == 2200000.00
    assert holdings_by_ticker["SPX_PUT_HEDGE"]["market_value"] == 250000.00

    sum_mv = sum(a["market_value"] for a in port["assets"])
    assert sum_mv == 16993750.00

    # 2. Simulate CENTRAL_BANK_RATE_HIKE (severity 1.0)
    sim_resp = client.post("/api/v1/stress-test/simulate", json={
        "portfolio_id": "port_wholesale_banking",
        "scenario_id": "CENTRAL_BANK_RATE_HIKE",
        "severity_multiplier": 1.0,
        "allow_duplicate": True
    })
    assert sim_resp.status_code == 200
    sim = sim_resp.json()

    # Exact Portfolio Aggregates
    assert sim["baseline_value"] == 16993750.00
    assert sim["stressed_value"] == 16298400.00
    assert sim["total_loss"] == 695350.00
    assert sim["loss_percentage"] == 4.09
    assert sim["credit_loss"] == 21750.00
    assert sim["market_loss"] == 673600.00

    # Exact Penny Mathematical Reconciliations
    assert abs(sim["total_loss"] - (sim["baseline_value"] - sim["stressed_value"])) < 0.01
    assert abs(sim["total_loss"] - (sim["credit_loss"] + sim["market_loss"])) < 0.01

    # Exact Asset-Level Shocks
    shocks_by_ticker = {s["ticker"]: s for s in sim["asset_shocks"]}
    
    # 1. ACME_CORP_LOAN (Amortized Cost ECL)
    loan = shocks_by_ticker["ACME_CORP_LOAN"]
    assert loan["baseline_value"] == 4943750.00
    assert loan["stressed_value"] == 4922000.00
    assert loan["asset_loss"] == 21750.00
    assert loan["credit_loss"] == 21750.00
    assert loan["market_loss"] == 0.00  # Zero double-counting!
    assert loan["valuation_methodology"] == "ecl_amortized_cost"

    # 2. US_TREASURY_10Y (Duration-Convexity)
    ust = shocks_by_ticker["US_TREASURY_10Y"]
    assert ust["baseline_value"] == 4000000.00
    assert ust["stressed_value"] == 3701000.00
    assert ust["asset_loss"] == 299000.00
    assert ust["credit_loss"] == 0.00
    assert ust["market_loss"] == 299000.00
    assert ust["valuation_methodology"] == "bond_modified_duration_convexity"

    # 3. MS_CORP_BOND_5Y (Spread Duration)
    corp = shocks_by_ticker["MS_CORP_BOND_5Y"]
    assert corp["baseline_value"] == 3000000.00
    assert corp["stressed_value"] == 2829900.00
    assert corp["asset_loss"] == 170100.00
    assert corp["credit_loss"] == 0.00
    assert corp["market_loss"] == 170100.00
    assert corp["valuation_methodology"] == "corporate_bond_spread_duration"

    # 4. NVDA (Tech Equity)
    nvda = shocks_by_ticker["NVDA"]
    assert nvda["baseline_value"] == 2600000.00
    assert nvda["stressed_value"] == 2366000.00
    assert nvda["asset_loss"] == 234000.00
    assert nvda["credit_loss"] == 0.00
    assert nvda["market_loss"] == 234000.00

    # 5. AAPL (Tech Equity)
    aapl = shocks_by_ticker["AAPL"]
    assert aapl["baseline_value"] == 2200000.00
    assert aapl["stressed_value"] == 2002000.00
    assert aapl["asset_loss"] == 198000.00
    assert aapl["credit_loss"] == 0.00
    assert aapl["market_loss"] == 198000.00

    # 6. SPX_PUT_HEDGE (Protective Put Delta)
    put = shocks_by_ticker["SPX_PUT_HEDGE"]
    assert put["baseline_value"] == 250000.00
    assert put["stressed_value"] == 477500.00
    assert put["asset_loss"] == -227500.00  # Negative loss == hedge gain
    assert put["credit_loss"] == 0.00
    assert put["market_loss"] == -227500.00
    assert put["valuation_methodology"] == "derivative_delta_hedge"

    # Sum of Asset Losses
    sum_asset_losses = sum(s["asset_loss"] for s in sim["asset_shocks"])
    assert sum_asset_losses == 695350.00


