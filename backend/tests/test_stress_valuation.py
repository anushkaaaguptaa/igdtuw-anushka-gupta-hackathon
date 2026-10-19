import pytest
from app.services.stress_testing.scenarios import StressScenario, ScenarioFactorShocks
from app.services.stress_testing.valuation import value_asset_under_stress, AssetValuationResult


def test_baseline_valuation_with_zero_shocks():
    """Verify that a zero-shock scenario leaves all asset values completely unchanged."""
    zero_scenario = StressScenario(
        scenario_id="ZERO_SHOCK",
        name="Zero Shock Baseline",
        description="No shocks applied",
        target_categories=[],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=0.0,
            rate_shock_bps=0.0,
            credit_spread_bps=0.0,
            loan_pd_multiplier=1.0,
            loan_lgd_add=0.0
        )
    )

    # 1. Equity
    eq_asset = {
        "ticker": "NVDA", "asset_type": "equity", "sector": "Information Technology",
        "shares": 100, "current_price": 50.0, "sector_beta": 1.2
    }
    eq_res = value_asset_under_stress(eq_asset, zero_scenario)
    assert eq_res.baseline_value == 5000.0
    assert eq_res.stressed_value == 5000.0
    assert eq_res.asset_loss == 0.0
    assert eq_res.pct_change == 0.0

    # 2. Government Bond
    govt_asset = {
        "ticker": "UST_10Y", "asset_type": "government_bond", "sector": "Government",
        "shares": 100, "current_price": 100.0,
        "attributes": {"modified_duration": 8.0, "convexity": 60.0}
    }
    govt_res = value_asset_under_stress(govt_asset, zero_scenario)
    assert govt_res.baseline_value == 10000.0
    assert govt_res.stressed_value == 10000.0
    assert govt_res.asset_loss == 0.0

    # 3. Corporate Loan
    loan_asset = {
        "ticker": "LOAN_01", "asset_type": "corporate_loan", "sector": "Industrials",
        "shares": 1, "current_price": 992000.0,
        "attributes": {"ead": 1000000.0, "pd": 0.02, "lgd": 0.40}
    }
    loan_res = value_asset_under_stress(loan_asset, zero_scenario)
    # ECL = 1M * 0.02 * 0.40 = 8000; Carrying = 992000
    assert loan_res.baseline_value == 992000.0
    assert loan_res.stressed_value == 992000.0
    assert loan_res.credit_loss == 0.0
    assert loan_res.asset_loss == 0.0


def test_equity_market_decline_hand_calculation():
    """
    Hand-calculated fixture:
    100 shares @ $150.00 = $15,000.00 baseline
    Beta = 1.20
    Market shock = -10% (-0.10)
    pct_shock = -10% * 1.20 = -12.0%
    Stressed price = $150.00 * (1 - 0.12) = $132.00
    Stressed value = 100 * $132.00 = $13,200.00
    Asset loss = $15,000.00 - $13,200.00 = $1,800.00
    """
    scenario = StressScenario(
        scenario_id="TEST_EQ_DROP",
        name="Equity Drop",
        description="Market drops 10%",
        target_categories=[],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=-0.10,
            rate_shock_bps=0.0,
            credit_spread_bps=0.0,
            loan_pd_multiplier=1.0,
            loan_lgd_add=0.0
        )
    )

    asset = {
        "ticker": "TECH_CO", "asset_type": "equity", "sector": "General",
        "shares": 100, "current_price": 150.0, "sector_beta": 1.20
    }
    res = value_asset_under_stress(asset, scenario)

    assert res.baseline_value == 15000.00
    assert res.stressed_value == 13200.00
    assert res.asset_loss == 1800.00
    assert res.market_loss == 1800.00
    assert res.credit_loss == 0.00
    assert res.stressed_price == 132.00
    assert res.pct_change == -12.00


def test_government_bond_duration_and_convexity_repricing():
    """
    Hand-calculated fixture:
    100 units @ $100.00 = $10,000.00 baseline
    Modified Duration D_mod = 8.0, Convexity C = 60.0
    Rate shock = +100 bps (+0.0100 decimal)
    dP/P ≈ -D_mod * dy + 0.5 * C * (dy)^2
         = -8.0 * 0.0100 + 0.5 * 60.0 * (0.000100)
         = -0.0800 + 0.0030 = -0.0770 (-7.70%)
    Stressed price = $100.00 * (1 - 0.0770) = $92.30
    Stressed value = 100 * $92.30 = $9,230.00
    Asset loss = $10,000.00 - $9,230.00 = $770.00
    """
    scenario = StressScenario(
        scenario_id="TEST_RATE_HIKE",
        name="Rate Hike +100bps",
        description="Policy rate jumps 100 bps",
        target_categories=[],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=0.0,
            rate_shock_bps=100.0,
            credit_spread_bps=0.0,
            loan_pd_multiplier=1.0,
            loan_lgd_add=0.0
        )
    )

    asset = {
        "ticker": "UST_10Y", "asset_type": "government_bond", "sector": "Government",
        "shares": 100, "current_price": 100.0,
        "attributes": {"modified_duration": 8.0, "convexity": 60.0}
    }
    res = value_asset_under_stress(asset, scenario)

    assert res.baseline_value == 10000.00
    assert res.stressed_value == 9230.00
    assert res.asset_loss == 770.00
    assert res.market_loss == 770.00
    assert res.credit_loss == 0.00
    assert res.stressed_price == 92.30
    assert res.pct_change == -7.70


def test_corporate_bond_spread_widening():
    """
    Hand-calculated fixture:
    100 units @ $100.00 = $10,000.00 baseline
    Modified Duration D_mod = 5.0
    Rate shock = +50 bps (0.0050), Spread shock = +150 bps (0.0150)
    Total yield shift dy + ds = 200 bps (0.0200)
    dP/P ≈ -5.0 * 0.0200 = -0.1000 (-10.00%)
    Stressed value = $10,000.00 * 0.90 = $9,000.00
    Loss = $1,000.00
    """
    scenario = StressScenario(
        scenario_id="TEST_SPREAD_BLOWOUT",
        name="Credit Spread Blowout",
        description="Spreads widen 150 bps, rates rise 50 bps",
        target_categories=[],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=0.0,
            rate_shock_bps=50.0,
            credit_spread_bps=150.0,
            loan_pd_multiplier=1.0,
            loan_lgd_add=0.0
        )
    )

    asset = {
        "ticker": "CORP_BOND", "asset_type": "corporate_bond", "sector": "Financials",
        "shares": 100, "current_price": 100.0,
        "attributes": {"modified_duration": 5.0}
    }
    res = value_asset_under_stress(asset, scenario)

    assert res.baseline_value == 10000.00
    assert res.stressed_value == 9000.00
    assert res.asset_loss == 1000.00
    assert res.market_loss == 1000.00
    assert res.credit_loss == 0.00
    assert res.pct_change == -10.00


def test_corporate_loan_credit_loss_and_zero_double_counting():
    """
    Hand-calculated fixture:
    EAD = $1,000,000.00
    Baseline PD = 2.0% (0.02), Baseline LGD = 40% (0.40)
    ECL_base = $1,000,000 * 0.02 * 0.40 = $8,000.00
    Carrying_base = $1,000,000 - $8,000 = $992,000.00

    Stressed Shocks:
    PD multiplier = 2.5x => PD_stressed = 2.0% * 2.5 = 5.0% (0.05)
    LGD addition = +0.10 => LGD_stressed = 40% + 10% = 50.0% (0.50)
    ECL_stressed = $1,000,000 * 0.05 * 0.50 = $25,000.00
    Carrying_stressed = $1,000,000 - $25,000 = $975,000.00

    Credit Loss = $25,000 - $8,000 = $17,000.00
    Total Loss = Carrying_base - Carrying_stressed = $17,000.00
    Market Loss = $0.00 (Amortized cost convention: zero double counting)
    """
    scenario = StressScenario(
        scenario_id="TEST_CREDIT_SHOCK",
        name="Loan Impairment Surge",
        description="Borrower distress",
        target_categories=[],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=-0.15,  # Should NOT affect loan carrying value
            rate_shock_bps=100.0,       # Should NOT affect loan carrying value
            credit_spread_bps=120.0,
            loan_pd_multiplier=2.5,
            loan_lgd_add=0.10
        )
    )

    asset = {
        "ticker": "TERM_LOAN_B", "asset_type": "corporate_loan", "sector": "Industrials",
        "shares": 1, "current_price": 992000.0,
        "attributes": {"ead": 1000000.0, "pd": 0.02, "lgd": 0.40}
    }
    res = value_asset_under_stress(asset, scenario)

    assert res.baseline_value == 992000.00
    assert res.stressed_value == 975000.00
    assert res.credit_loss == 17000.00
    assert res.market_loss == 0.00
    assert res.asset_loss == 17000.00
    assert res.valuation_methodology == "ecl_amortized_cost"


def test_derivative_protective_put_delta_hedging():
    """
    Hand-calculated fixture:
    Put option position: 1,000 contracts @ $200.00 = $200,000.00 market value (premium)
    Underlying Notional = $5,000,000.00
    Option Delta = -0.40 (protective put)
    Equity shock = -8.0% (-0.08)

    dV ≈ delta * (dS/S) * Notional
       = (-0.40) * (-0.08) * $5,000,000.00
       = +0.032 * $5,000,000.00 = +$160,000.00 gain
    Stressed value = $200,000.00 + $160,000.00 = $360,000.00
    Loss = $200,000.00 - $360,000.00 = -$160,000.00 (hedging gain offsets portfolio loss)
    """
    scenario = StressScenario(
        scenario_id="TEST_DERIVATIVE_HEDGE",
        name="Market Drop with Hedge",
        description="Equities drop 8%",
        target_categories=[],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=-0.08,
            rate_shock_bps=0.0,
            credit_spread_bps=0.0,
            loan_pd_multiplier=1.0,
            loan_lgd_add=0.0
        )
    )

    asset = {
        "ticker": "SPX_PUT", "asset_type": "derivative", "sector": "Financials",
        "shares": 1000, "current_price": 200.0, "notional": 5000000.0,
        "attributes": {"delta": -0.40, "underlying_notional": 5000000.0}
    }
    res = value_asset_under_stress(asset, scenario)

    assert res.baseline_value == 200000.00
    assert res.stressed_value == 360000.00
    assert res.asset_loss == -160000.00  # Negative loss = hedging gain
    assert res.market_loss == -160000.00
    assert res.credit_loss == 0.00


def test_asset_types_unaffected_by_irrelevant_shocks():
    """Verify that shocks are only applied to economically relevant asset classes."""
    # Scenario with ONLY interest rate shock (+200 bps)
    rate_scenario = StressScenario(
        scenario_id="ONLY_RATES",
        name="Rate Shock Only",
        description="+200 bps rates, zero equity or loan shocks",
        target_categories=[],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=0.0,
            rate_shock_bps=200.0,
            credit_spread_bps=0.0,
            loan_pd_multiplier=1.0,
            loan_lgd_add=0.0
        )
    )

    # 1. Equity holding must be completely unaffected by rate shock
    eq_asset = {"ticker": "AAPL", "asset_type": "equity", "shares": 50, "current_price": 200.0}
    eq_res = value_asset_under_stress(eq_asset, rate_scenario)
    assert eq_res.asset_loss == 0.0

    # 2. Corporate loan must be completely unaffected by rate shock
    loan_asset = {
        "ticker": "CORP_LOAN", "asset_type": "corporate_loan", "shares": 1, "current_price": 100000.0,
        "attributes": {"ead": 100000.0, "pd": 0.01, "lgd": 0.30}
    }
    loan_res = value_asset_under_stress(loan_asset, rate_scenario)
    assert loan_res.asset_loss == 0.0
    assert loan_res.credit_loss == 0.0

    # Scenario with ONLY equity shock (-10%)
    equity_scenario = StressScenario(
        scenario_id="ONLY_EQUITY",
        name="Equity Shock Only",
        description="-10% equity decline, zero rate or credit shocks",
        target_categories=[],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=-0.10,
            rate_shock_bps=0.0,
            credit_spread_bps=0.0,
            loan_pd_multiplier=1.0,
            loan_lgd_add=0.0
        )
    )

    # 3. Government bond must be completely unaffected by equity decline
    govt_asset = {
        "ticker": "UST_5Y", "asset_type": "government_bond", "shares": 100, "current_price": 100.0,
        "attributes": {"modified_duration": 4.5}
    }
    govt_res = value_asset_under_stress(govt_asset, equity_scenario)
    assert govt_res.asset_loss == 0.0


def test_invalid_financial_parameters_raise_explicit_errors():
    """Verify that invalid financial parameters trigger informative ValueErrors."""
    scenario = StressScenario(
        scenario_id="TEST",
        name="Test",
        description="",
        target_categories=[],
        factor_shocks=ScenarioFactorShocks(0.0, 0.0, 0.0, 1.0, 0.0)
    )

    # Negative shares
    with pytest.raises(ValueError, match="Quantity cannot be negative"):
        value_asset_under_stress({"ticker": "BAD", "shares": -10, "current_price": 100.0}, scenario)

    # Negative price
    with pytest.raises(ValueError, match="Price cannot be negative"):
        value_asset_under_stress({"ticker": "BAD", "shares": 10, "current_price": -50.0}, scenario)

    # Negative bond duration
    with pytest.raises(ValueError, match="Duration cannot be negative"):
        value_asset_under_stress({
            "ticker": "BAD_BOND", "asset_type": "government_bond", "shares": 10, "current_price": 100.0,
            "attributes": {"modified_duration": -3.5}
        }, scenario)

    # Invalid loan PD (> 1.0)
    with pytest.raises(ValueError, match="Probability of default must be within"):
        value_asset_under_stress({
            "ticker": "BAD_LOAN", "asset_type": "corporate_loan", "shares": 1, "current_price": 100.0,
            "attributes": {"ead": 1000.0, "pd": 1.5, "lgd": 0.40}
        }, scenario)

    # Negative notional
    with pytest.raises(ValueError, match="Notional cannot be negative"):
        value_asset_under_stress({
            "ticker": "BAD_NOTIONAL", "asset_type": "equity", "shares": 10, "current_price": 100.0,
            "notional": -5000.0
        }, scenario)

    # Negative EAD
    with pytest.raises(ValueError, match="Exposure at default cannot be negative"):
        value_asset_under_stress({
            "ticker": "BAD_EAD", "asset_type": "corporate_loan", "shares": 1, "current_price": 100.0,
            "attributes": {"ead": -100000.0, "pd": 0.02, "lgd": 0.40}
        }, scenario)

    # Invalid LGD (> 1.0)
    with pytest.raises(ValueError, match="Loss given default must be within"):
        value_asset_under_stress({
            "ticker": "BAD_LGD", "asset_type": "corporate_loan", "shares": 1, "current_price": 100.0,
            "attributes": {"ead": 100000.0, "pd": 0.02, "lgd": 1.45}
        }, scenario)

    # Negative underlying notional for derivative
    with pytest.raises(ValueError, match="Underlying notional cannot be negative"):
        value_asset_under_stress({
            "ticker": "BAD_DERIV", "asset_type": "derivative", "shares": 10, "current_price": 100.0,
            "attributes": {"delta": -0.3, "underlying_notional": -10000.0}
        }, scenario)


def test_equity_positive_shocks_and_direct_target_haircut():
    """Test equity gains under positive sector shocks and targeted direct entity haircut."""
    scenario = StressScenario(
        scenario_id="TEST_TARGET_AND_SECTOR",
        name="Target and Sector Scenario",
        description="",
        target_categories=[],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=-0.05,
            rate_shock_bps=0.0,
            credit_spread_bps=0.0,
            loan_pd_multiplier=1.0,
            loan_lgd_add=0.0,
            target_equity_haircut=-0.35,  # -35% target haircut
            sector_equity_shocks={"Energy": +0.06}  # +6% energy gain
        )
    )

    # 1. Target entity: NVDA (should receive -35% direct haircut regardless of sector)
    nvda_asset = {
        "ticker": "NVDA", "asset_type": "equity", "sector": "Information Technology",
        "shares": 100, "current_price": 200.0, "sector_beta": 1.5
    }
    nvda_res = value_asset_under_stress(nvda_asset, scenario, target_tickers=["NVDA"])
    assert nvda_res.baseline_value == 20000.0
    assert nvda_res.stressed_price == 130.0  # 200 * (1 - 0.35)
    assert nvda_res.stressed_value == 13000.0
    assert nvda_res.asset_loss == 7000.0
    assert nvda_res.pct_change == -35.0

    # 2. Positive sector shock: XOM Energy (should gain +6%)
    xom_asset = {
        "ticker": "XOM", "asset_type": "equity", "sector": "Energy",
        "shares": 100, "current_price": 100.0, "sector_beta": 0.8
    }
    xom_res = value_asset_under_stress(xom_asset, scenario)
    assert xom_res.baseline_value == 10000.0
    assert xom_res.stressed_price == 106.0  # 100 * (1 + 0.06)
    assert xom_res.stressed_value == 10600.0
    assert xom_res.asset_loss == -600.0  # Negative loss represents gain
    assert xom_res.pct_change == 6.0


def test_government_bond_negative_yield_change_with_convexity():
    """
    Test government bond price rise under negative yield shift (-50 bps).
    D_mod = 8.0, Convexity C = 60.0
    dy = -50 bps = -0.0050
    dP/P ≈ -8.0 * (-0.0050) + 0.5 * 60.0 * (-0.0050)^2
         = +0.0400 + 30.0 * 0.000025 = +0.0400 + 0.00075 = +0.04075 (+4.075%)
    Baseline: 100 units @ $100 = $10,000.00
    Stressed: $10,000.00 * 1.04075 = $10,407.50
    Loss: -$407.50 (gain)
    """
    scenario = StressScenario(
        scenario_id="TEST_RATE_DROP",
        name="Rate Cut -50bps",
        description="",
        target_categories=[],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=0.0,
            rate_shock_bps=-50.0,
            credit_spread_bps=0.0,
            loan_pd_multiplier=1.0,
            loan_lgd_add=0.0
        )
    )

    asset = {
        "ticker": "UST_10Y", "asset_type": "government_bond", "sector": "Government",
        "shares": 100, "current_price": 100.0,
        "attributes": {"modified_duration": 8.0, "convexity": 60.0}
    }
    res = value_asset_under_stress(asset, scenario)
    assert res.baseline_value == 10000.00
    assert res.stressed_value == 10407.50
    assert res.asset_loss == -407.50
    assert res.market_loss == -407.50
    assert res.credit_loss == 0.00
    assert res.pct_change == 4.08


def test_corporate_loan_capped_pd_and_lgd_extreme_shock():
    """
    Verify that extreme stress shocks on loans are properly capped at PD=1.0 and LGD=1.0.
    EAD = $1,000,000.00
    PD_base = 0.40, LGD_base = 0.70
    ECL_base = 1,000,000 * 0.40 * 0.70 = $280,000.00
    Carrying_base = $720,000.00

    Extreme Multipliers:
    PD_multiplier = 4.0x => 0.40 * 4.0 = 1.60 -> Capped at 1.00
    LGD_add = +0.50 => 0.70 + 0.50 = 1.20 -> Capped at 1.00
    ECL_stressed = 1,000,000 * 1.00 * 1.00 = $1,000,000.00
    Carrying_stressed = max(0.0, 1,000,000 - 1,000,000) = $0.00
    Credit Loss = $1,000,000 - $280,000 = $720,000.00
    """
    extreme_scenario = StressScenario(
        scenario_id="EXTREME_DEFAULT",
        name="Total Default Wipeout",
        description="",
        target_categories=[],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=0.0,
            rate_shock_bps=0.0,
            credit_spread_bps=0.0,
            loan_pd_multiplier=4.0,
            loan_lgd_add=0.50
        )
    )

    loan = {
        "ticker": "DISTRESSED_LOAN", "asset_type": "corporate_loan", "shares": 1, "current_price": 720000.0,
        "attributes": {"ead": 1000000.0, "pd": 0.40, "lgd": 0.70}
    }
    res = value_asset_under_stress(loan, extreme_scenario)
    assert res.baseline_value == 720000.00
    assert res.stressed_value == 0.00
    assert res.credit_loss == 720000.00
    assert res.asset_loss == 720000.00
    assert res.market_loss == 0.00


def test_derivative_put_option_under_market_rise_limited_liability():
    """
    Test protective put when underlying equity rises +20%:
    Base value (premium paid) = $100,000.00
    Underlying notional = $2,000,000.00, Delta = -0.35
    Equity shock = +20% (+0.20)
    dV = delta * (dS/S) * Notional = (-0.35) * (+0.20) * 2,000,000 = -$140,000.00
    Stressed value: max(0.0, $100,000 - $140,000) = $0.00 (limited liability: cannot be negative)
    Loss: $100,000.00 - $0.00 = $100,000.00 (capped at premium paid)
    """
    bull_scenario = StressScenario(
        scenario_id="BULL_MARKET",
        name="Equity Rally",
        description="",
        target_categories=[],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=+0.20,
            rate_shock_bps=0.0,
            credit_spread_bps=0.0,
            loan_pd_multiplier=1.0,
            loan_lgd_add=0.0
        )
    )

    deriv = {
        "ticker": "PUT_HEDGE", "asset_type": "derivative", "shares": 1000, "current_price": 100.0,
        "notional": 2000000.0, "attributes": {"delta": -0.35, "underlying_notional": 2000000.0}
    }
    res = value_asset_under_stress(deriv, bull_scenario)
    assert res.baseline_value == 100000.00
    assert res.stressed_value == 0.00
    assert res.asset_loss == 100000.00
    assert res.market_loss == 100000.00
    assert res.credit_loss == 0.00


def test_zero_valued_asset_edge_cases():
    """Test assets with zero shares or zero price evaluate cleanly without division by zero."""
    scenario = StressScenario(
        scenario_id="TEST",
        name="Test",
        description="",
        target_categories=[],
        factor_shocks=ScenarioFactorShocks(-0.10, 50.0, 50.0, 1.5, 0.05)
    )

    # 1. Zero shares equity
    zero_shares_eq = {"ticker": "ZERO_SHR", "asset_type": "equity", "shares": 0.0, "current_price": 100.0}
    res_eq = value_asset_under_stress(zero_shares_eq, scenario)
    assert res_eq.baseline_value == 0.0
    assert res_eq.stressed_value == 0.0
    assert res_eq.asset_loss == 0.0

    # 2. Zero price equity
    zero_px_eq = {"ticker": "ZERO_PX", "asset_type": "equity", "shares": 100.0, "current_price": 0.0}
    res_px = value_asset_under_stress(zero_px_eq, scenario)
    assert res_px.baseline_value == 0.0
    assert res_px.stressed_value == 0.0
    assert res_px.asset_loss == 0.0

    # 3. Zero EAD loan
    zero_loan = {
        "ticker": "ZERO_LOAN", "asset_type": "corporate_loan", "shares": 1.0, "current_price": 0.0,
        "attributes": {"ead": 0.0, "pd": 0.05, "lgd": 0.40}
    }
    res_loan = value_asset_under_stress(zero_loan, scenario)
    assert res_loan.baseline_value == 0.0
    assert res_loan.stressed_value == 0.0
    assert res_loan.asset_loss == 0.0
    assert res_loan.credit_loss == 0.0

