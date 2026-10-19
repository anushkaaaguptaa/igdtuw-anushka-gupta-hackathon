import pytest
from sqlalchemy.orm import Session
from app.models.db_models import RiskSignal, Portfolio, Entity, PortfolioAsset
from app.services.nlp.classifier import EventCategory
from app.services.stress_testing.scenarios import (
    SCENARIO_CATALOG,
    map_signal_to_scenario
)
from app.services.stress_testing.auto_trigger import evaluate_and_trigger_stress_test


def test_scenario_catalog_coverage():
    """Verify all 5 required canonical scenario types are defined."""
    required_scenarios = [
        "GEOPOLITICAL_ESCALATION",
        "CENTRAL_BANK_RATE_HIKE",
        "CREDIT_EVENT_OR_DEFAULT",
        "BANKING_SECTOR_CRISIS",
        "MACROECONOMIC_RECESSION"
    ]
    for s_id in required_scenarios:
        assert s_id in SCENARIO_CATALOG
        scen = SCENARIO_CATALOG[s_id]
        assert scen.scenario_id == s_id
        assert len(scen.name) > 0
        assert len(scen.description) > 0
        assert scen.version == "v1.0"
        # Each scenario must have documented factor shocks
        assert hasattr(scen.factor_shocks, "equity_market_shock")
        assert hasattr(scen.factor_shocks, "rate_shock_bps")
        assert hasattr(scen.factor_shocks, "credit_spread_bps")
        assert hasattr(scen.factor_shocks, "loan_pd_multiplier")
        assert hasattr(scen.factor_shocks, "loan_lgd_add")


def test_geopolitical_scenario_multi_sector_shocks():
    """Verify geopolitical escalation models diverging sector shocks."""
    geopol = SCENARIO_CATALOG["GEOPOLITICAL_ESCALATION"]
    shocks = geopol.factor_shocks

    # Flight to quality: Treasury yield falls (-25 bps)
    assert shocks.rate_shock_bps < 0
    # Corporate credit spreads widen (+45 bps)
    assert shocks.credit_spread_bps > 0
    # Energy sector is resilient / gains (+4%)
    assert shocks.sector_equity_shocks.get("Energy", 0) > 0
    # Tech sector suffers supply chain contractions (-11%)
    assert shocks.sector_equity_shocks.get("Information Technology", 0) < 0


def test_event_to_scenario_mapping():
    """Test deterministic mapping from RiskSignal to appropriate StressScenario."""
    # 1. Geopolitical signal
    geo_sig = RiskSignal(
        id="sig_geo",
        event_category=EventCategory.GEOPOLITICAL.value,
        impact_score=9,
        impact_rationale="Military conflict escalation and sanctions.",
        evidence="Sanctions enacted on critical semiconductor supply."
    )
    assert map_signal_to_scenario(geo_sig).scenario_id == "GEOPOLITICAL_ESCALATION"

    # 2. Central Bank / Fed Rate Hike
    rate_sig = RiskSignal(
        id="sig_rate",
        event_category=EventCategory.MACROECONOMIC.value,
        impact_score=8,
        impact_rationale="Fed hikes benchmark interest rate by 50 bps.",
        evidence="Federal Reserve announces aggressive monetary tightening."
    )
    assert map_signal_to_scenario(rate_sig).scenario_id == "CENTRAL_BANK_RATE_HIKE"

    # 3. Corporate Default
    default_sig = RiskSignal(
        id="sig_default",
        event_category=EventCategory.CREDIT_EVENT.value,
        impact_score=9,
        impact_rationale="Major corporate debt restructuring and missed coupon payment.",
        evidence="Borrower defaulted on $500M bond tranche."
    )
    assert map_signal_to_scenario(default_sig).scenario_id == "CREDIT_EVENT_OR_DEFAULT"

    # 4. Banking crisis
    bank_sig = RiskSignal(
        id="sig_bank",
        event_category=EventCategory.CREDIT_EVENT.value,
        impact_score=10,
        impact_rationale="Regional bank deposit run and interbank liquidity freeze.",
        evidence="Depositors withdraw liquidity amid contagion fears."
    )
    assert map_signal_to_scenario(bank_sig).scenario_id == "BANKING_SECTOR_CRISIS"


def test_high_impact_auto_trigger_and_low_impact_skip(db_session: Session):
    """
    Verify:
    1. impact_score <= 7 does NOT trigger automatic simulation runs.
    2. impact_score > 7 triggers automatic simulation runs.
    3. Duplicate automatic runs are strictly prevented for the same signal.
    """
    # 1. Create a test portfolio in db
    port = Portfolio(
        id="port_trigger_test",
        name="Auto-Trigger Test Portfolio",
        initial_value=100000.0
    )
    db_session.add(port)
    db_session.flush()

    ent = Entity(ticker="TEST_CO", name="Test Co", sector="Technology", asset_class="Equity")
    db_session.add(ent)
    db_session.flush()

    asset = PortfolioAsset(
        id="pa_trig_01",
        portfolio_id="port_trigger_test",
        ticker="TEST_CO",
        shares=100,
        purchase_price=100.0,
        current_price=100.0,
        sector_beta=1.0
    )
    db_session.add(asset)
    db_session.commit()

    # 2. Low-impact signal (impact_score = 6 <= 7) -> Should NOT trigger
    low_sig = RiskSignal(
        id="sig_low_impact",
        article_id="art_dummy",
        sentiment_score=-0.2,
        sentiment_label="negative",
        event_category=EventCategory.MACROECONOMIC.value,
        event_confidence=0.8,
        impact_score=6,
        impact_rationale="Minor macroeconomic consumer sentiment dip.",
        evidence="Consumer sentiment slipped marginally.",
        inference_mode="mock",
        model_version="finbert-v1"
    )
    db_session.add(low_sig)
    db_session.commit()

    low_runs = evaluate_and_trigger_stress_test(low_sig, db_session, portfolio_ids=["port_trigger_test"])
    assert len(low_runs) == 0, "Low-impact signal (<= 7) must not trigger automatic stress test"

    # 3. High-impact signal (impact_score = 9 > 7) -> Should trigger
    high_sig = RiskSignal(
        id="sig_high_impact",
        article_id="art_dummy",
        sentiment_score=-0.9,
        sentiment_label="negative",
        event_category=EventCategory.CREDIT_EVENT.value,
        event_confidence=0.95,
        impact_score=9,
        impact_rationale="Systemic corporate default wave announced.",
        evidence="Default declarations submitted.",
        inference_mode="mock",
        model_version="finbert-v1"
    )
    db_session.add(high_sig)
    db_session.commit()

    high_runs = evaluate_and_trigger_stress_test(high_sig, db_session, portfolio_ids=["port_trigger_test"])
    assert len(high_runs) == 1, "High-impact signal (> 7) must trigger automatic stress test"
    assert high_runs[0].portfolio_id == "port_trigger_test"
    assert high_runs[0].trigger_signal_id == "sig_high_impact"
    assert high_runs[0].total_loss > 0

    # 4. Duplicate prevention test: Invoking again with the same signal must NOT create a duplicate run
    duplicate_runs = evaluate_and_trigger_stress_test(high_sig, db_session, portfolio_ids=["port_trigger_test"])
    assert len(duplicate_runs) == 0, "Duplicate automatic run must be prevented"


def test_impact_score_exact_boundary_threshold_7_and_8(db_session: Session):
    """
    Test exact boundary condition around the configurable threshold (default 7):
    - impact_score == 7 -> MUST NOT trigger (non-high-impact boundary)
    - impact_score == 8 -> MUST trigger (high-impact trigger boundary)
    """
    port = Portfolio(
        id="port_boundary_test",
        name="Boundary Test Portfolio",
        initial_value=50000.0
    )
    db_session.add(port)
    db_session.flush()

    ent = Entity(ticker="BND_CO", name="Boundary Co", sector="Financials", asset_class="Equity")
    db_session.add(ent)
    db_session.flush()

    asset = PortfolioAsset(
        id="pa_bnd_01",
        portfolio_id="port_boundary_test",
        ticker="BND_CO",
        shares=500,
        purchase_price=100.0,
        current_price=100.0,
        sector_beta=1.0
    )
    db_session.add(asset)
    db_session.commit()

    # Score = 7: Exactly at the threshold -> Should NOT trigger (> 7 required)
    sig_7 = RiskSignal(
        id="sig_score_7",
        article_id="art_bnd_7",
        sentiment_score=-0.4,
        sentiment_label="negative",
        event_category=EventCategory.MACROECONOMIC.value,
        event_confidence=0.85,
        impact_score=7,
        impact_rationale="Moderate inflationary pressures recorded.",
        evidence="CPI print comes in slightly above target.",
        inference_mode="mock",
        model_version="finbert-v1"
    )
    db_session.add(sig_7)
    db_session.commit()

    runs_7 = evaluate_and_trigger_stress_test(sig_7, db_session, portfolio_ids=["port_boundary_test"])
    assert len(runs_7) == 0, "Signal with impact_score=7 must NOT trigger auto stress test (threshold is strictly > 7)"

    # Score = 8: Immediately above the threshold -> MUST trigger
    sig_8 = RiskSignal(
        id="sig_score_8",
        article_id="art_bnd_8",
        sentiment_score=-0.8,
        sentiment_label="negative",
        event_category=EventCategory.MACROECONOMIC.value,
        event_confidence=0.90,
        impact_score=8,
        impact_rationale="Substantial central bank policy rate acceleration.",
        evidence="Emergency rate hike signaled by governing council.",
        inference_mode="mock",
        model_version="finbert-v1"
    )
    db_session.add(sig_8)
    db_session.commit()

    runs_8 = evaluate_and_trigger_stress_test(sig_8, db_session, portfolio_ids=["port_boundary_test"])
    assert len(runs_8) == 1, "Signal with impact_score=8 MUST trigger auto stress test"
    assert runs_8[0].portfolio_id == "port_boundary_test"
    assert runs_8[0].trigger_signal_id == "sig_score_8"
    assert runs_8[0].total_loss > 0
