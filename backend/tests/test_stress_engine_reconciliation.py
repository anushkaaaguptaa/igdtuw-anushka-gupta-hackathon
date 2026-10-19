import pytest
from app.services.stress_testing.scenarios import SCENARIO_CATALOG
from app.services.stress_testing.engine import PortfolioStressEngine


@pytest.fixture
def wholesale_portfolio_assets():
    """Representative multi-asset wholesale banking portfolio fixture."""
    return [
        {
            "ticker": "ACME_CORP_LOAN",
            "name": "Acme Industrial Holdings",
            "asset_type": "corporate_loan",
            "sector": "Industrials",
            "shares": 1.0,
            "current_price": 4_943_750.00,
            "notional": 5_000_000.00,
            "attributes": {"ead": 5_000_000.0, "pd": 0.025, "lgd": 0.45}
        },
        {
            "ticker": "US_TREASURY_10Y",
            "name": "US Department of the Treasury",
            "asset_type": "government_bond",
            "sector": "Government",
            "shares": 40_000.0,
            "current_price": 100.00,
            "attributes": {"modified_duration": 7.8, "convexity": 65.0}
        },
        {
            "ticker": "MS_CORP_BOND_5Y",
            "name": "Morgan Stanley",
            "asset_type": "corporate_bond",
            "sector": "Financials",
            "shares": 30_000.0,
            "current_price": 100.00,
            "attributes": {"modified_duration": 4.2}
        },
        {
            "ticker": "NVDA",
            "name": "NVIDIA Corporation",
            "asset_type": "equity",
            "sector": "Information Technology",
            "shares": 20_000.0,
            "current_price": 130.00,
            "sector_beta": 1.45
        },
        {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "asset_type": "equity",
            "sector": "Information Technology",
            "shares": 10_000.0,
            "current_price": 220.00,
            "sector_beta": 1.05
        },
        {
            "ticker": "SPX_PUT_HEDGE",
            "name": "CBOE SPX Protective Put Option",
            "asset_type": "derivative",
            "sector": "Financials",
            "shares": 1_000.0,
            "current_price": 250.00,
            "notional": 10_000_000.00,
            "attributes": {"delta": -0.35, "underlying_notional": 10_000_000.0}
        }
    ]


def test_wholesale_portfolio_loss_reconciliation(wholesale_portfolio_assets):
    """
    Strict mathematical loss reconciliation across all 5 canonical stress scenarios:
    1. total_loss == baseline_value - stressed_value
    2. total_loss == credit_loss + market_loss
    3. sum(asset_shocks.asset_loss) == total_loss
    4. sum(loss_by_sector.values()) == total_loss
    5. sum(loss_by_asset_type.values()) == total_loss
    6. loss_percentage == (total_loss / baseline_value) * 100
    """
    for scenario_id, scenario in SCENARIO_CATALOG.items():
        res = PortfolioStressEngine.run_stress_test(
            assets=wholesale_portfolio_assets,
            scenario=scenario,
            severity_multiplier=1.2,
            run_var_simulation=False
        )

        # Baseline value must equal sum of individual baseline values
        expected_baseline = sum(
            a["shares"] * a["current_price"] for a in wholesale_portfolio_assets
        )
        assert abs(res.baseline_value - expected_baseline) < 0.05

        # 1. Total loss matches baseline - stressed
        assert abs(res.total_loss - (res.baseline_value - res.stressed_value)) < 0.05

        # 2. Total loss matches credit_loss + market_loss
        assert abs(res.total_loss - (res.credit_loss + res.market_loss)) < 0.05

        # 3. Sum of asset losses reconciles to total loss
        sum_asset_losses = round(sum(s.asset_loss for s in res.asset_shocks), 2)
        assert abs(res.total_loss - sum_asset_losses) < 0.05

        # 4. Sum of sector losses reconciles to total loss
        sum_sector_losses = round(sum(res.loss_by_sector.values()), 2)
        assert abs(res.total_loss - sum_sector_losses) < 0.05

        # 5. Sum of asset type losses reconciles to total loss
        sum_type_losses = round(sum(res.loss_by_asset_type.values()), 2)
        assert abs(res.total_loss - sum_type_losses) < 0.05

        # 6. Loss percentage uses documented baseline denominator
        expected_pct = round((res.total_loss / res.baseline_value) * 100.0, 2)
        assert abs(res.loss_percentage - expected_pct) < 0.05


def test_zero_double_counting_in_wholesale_portfolio(wholesale_portfolio_assets):
    """
    Verify that credit losses and market losses do not double-count:
    - Loans contribute exclusively to credit_loss (market_loss == 0.0).
    - Bonds, equities, and derivatives contribute exclusively to market_loss (credit_loss == 0.0).
    """
    credit_scen = SCENARIO_CATALOG["CREDIT_EVENT_OR_DEFAULT"]
    res = PortfolioStressEngine.run_stress_test(
        assets=wholesale_portfolio_assets,
        scenario=credit_scen,
        severity_multiplier=1.0,
        run_var_simulation=False
    )

    for shock in res.asset_shocks:
        if shock.asset_type == "corporate_loan":
            assert shock.credit_loss > 0, "Loan under credit event must have credit loss"
            assert shock.market_loss == 0.0, "Loan under amortized cost must NOT have market loss haircut"
            assert shock.asset_loss == shock.credit_loss
        elif shock.asset_type in ("equity", "government_bond", "corporate_bond", "derivative"):
            assert shock.credit_loss == 0.0, f"{shock.asset_type} must not have credit loss"
            assert shock.asset_loss == shock.market_loss


def test_simulation_determinism_and_reproducibility(wholesale_portfolio_assets):
    """Verify that repeated simulations with identical inputs produce identical results."""
    scenario = SCENARIO_CATALOG["BANKING_SECTOR_CRISIS"]

    res_1 = PortfolioStressEngine.run_stress_test(
        assets=wholesale_portfolio_assets,
        scenario=scenario,
        severity_multiplier=1.5,
        run_var_simulation=True
    )

    res_2 = PortfolioStressEngine.run_stress_test(
        assets=wholesale_portfolio_assets,
        scenario=scenario,
        severity_multiplier=1.5,
        run_var_simulation=True
    )

    assert res_1.baseline_value == res_2.baseline_value
    assert res_1.stressed_value == res_2.stressed_value
    assert res_1.total_loss == res_2.total_loss
    assert res_1.credit_loss == res_2.credit_loss
    assert res_1.market_loss == res_2.market_loss
    assert res_1.var_95 == res_2.var_95
    assert res_1.cvar_95 == res_2.cvar_95
    assert res_1.loss_by_sector == res_2.loss_by_sector
    assert res_1.loss_by_asset_type == res_2.loss_by_asset_type


def test_hedge_gains_represented_as_negative_losses_in_aggregates(wholesale_portfolio_assets):
    """
    Verify that hedge gains from derivatives are represented consistently as negative losses
    and reduce the total portfolio loss.
    """
    scen = SCENARIO_CATALOG["GEOPOLITICAL_ESCALATION"]
    res = PortfolioStressEngine.run_stress_test(
        assets=wholesale_portfolio_assets,
        scenario=scen,
        severity_multiplier=1.0,
        run_var_simulation=False
    )

    deriv_shock = next(s for s in res.asset_shocks if s.asset_type == "derivative")
    # For protective put under equity market decline (-8%), delta = -0.35
    # dV = -0.35 * -0.08 * $10,000,000 = +$280,000.00 gain
    assert deriv_shock.asset_loss < 0, "Put option hedge gain must be negative loss"
    assert deriv_shock.asset_loss == -280000.00
    assert deriv_shock.market_loss == -280000.00
    assert deriv_shock.credit_loss == 0.0

    # Ensure derivative negative loss reduces total loss
    non_deriv_loss = sum(s.asset_loss for s in res.asset_shocks if s.asset_type != "derivative")
    assert res.total_loss == round(non_deriv_loss + deriv_shock.asset_loss, 2)
    assert res.total_loss < non_deriv_loss


def test_reconciliation_failure_raises_explicit_value_error(monkeypatch):
    """
    Verify that if a calculation cannot reconcile, PortfolioStressEngine raises ValueError
    and fails clearly instead of silently adjusting the result.
    """
    from app.services.stress_testing import valuation
    from app.services.stress_testing.valuation import AssetValuationResult

    # Monkeypatch value_asset_under_stress to return a non-reconciling asset result
    def mock_broken_valuation(*args, **kwargs):
        return AssetValuationResult(
            baseline_value=1000.0,
            stressed_value=500.0,
            asset_loss=999.0,  # Corrupt loss: 1000 - 500 = 500 != 999
            credit_loss=0.0,
            market_loss=500.0,
            baseline_price=100.0,
            stressed_price=50.0,
            pct_change=-50.0,
            valuation_methodology="broken",
            shock_applied="broken"
        )

    import app.services.stress_testing.engine as engine_mod
    monkeypatch.setattr(engine_mod, "value_asset_under_stress", mock_broken_valuation)

    with pytest.raises(ValueError, match="Loss reconciliation failure"):
        PortfolioStressEngine.run_stress_test(
            assets=[{"ticker": "TEST", "asset_type": "equity", "shares": 10, "current_price": 100.0}],
            scenario=SCENARIO_CATALOG["CENTRAL_BANK_RATE_HIKE"],
            run_var_simulation=False
        )


def test_exact_central_bank_rate_hike_reconciliation(wholesale_portfolio_assets):
    """
    Authoritative test verifying exact dollar-and-cent financial reconciliation for
    CENTRAL_BANK_RATE_HIKE against the 6-holding wholesale banking portfolio:
    - Baseline: $16,993,750.00
    - Stressed: $16,298,400.00
    - Total Loss: $695,350.00 (Credit: $21,750.00, Market: $673,600.00)
    - ACME_CORP_LOAN: +$21,750.00 (Credit only, zero market markdown)
    - US_TREASURY_10Y: +$299,000.00 (Duration-convexity)
    - MS_CORP_BOND_5Y: +$170,100.00 (Spread duration)
    - NVDA: +$234,000.00 (Tech -9%)
    - AAPL: +$198,000.00 (Tech -9%)
    - SPX_PUT_HEDGE: -$227,500.00 (Delta -0.35 on -6.5% market move -> hedge gain)
    """
    scenario = SCENARIO_CATALOG["CENTRAL_BANK_RATE_HIKE"]
    res = PortfolioStressEngine.run_stress_test(
        assets=wholesale_portfolio_assets,
        scenario=scenario,
        severity_multiplier=1.0,
        run_var_simulation=False
    )

    # 1. Total aggregates
    assert res.baseline_value == 16993750.00
    assert res.stressed_value == 16298400.00
    assert res.total_loss == 695350.00
    assert res.loss_percentage == 4.09
    assert res.credit_loss == 21750.00
    assert res.market_loss == 673600.00

    # 2. Asset shocks map
    shocks = {s.ticker: s for s in res.asset_shocks}
    assert shocks["ACME_CORP_LOAN"].asset_loss == 21750.00
    assert shocks["ACME_CORP_LOAN"].credit_loss == 21750.00
    assert shocks["ACME_CORP_LOAN"].market_loss == 0.00

    assert shocks["US_TREASURY_10Y"].asset_loss == 299000.00
    assert shocks["US_TREASURY_10Y"].credit_loss == 0.00
    assert shocks["US_TREASURY_10Y"].market_loss == 299000.00

    assert shocks["MS_CORP_BOND_5Y"].asset_loss == 170100.00
    assert shocks["MS_CORP_BOND_5Y"].credit_loss == 0.00
    assert shocks["MS_CORP_BOND_5Y"].market_loss == 170100.00

    assert shocks["NVDA"].asset_loss == 234000.00
    assert shocks["NVDA"].credit_loss == 0.00
    assert shocks["NVDA"].market_loss == 234000.00

    assert shocks["AAPL"].asset_loss == 198000.00
    assert shocks["AAPL"].credit_loss == 0.00
    assert shocks["AAPL"].market_loss == 198000.00

    assert shocks["SPX_PUT_HEDGE"].asset_loss == -227500.00
    assert shocks["SPX_PUT_HEDGE"].credit_loss == 0.00
    assert shocks["SPX_PUT_HEDGE"].market_loss == -227500.00

    # 3. Sum of asset losses matches total loss
    sum_losses = sum(s.asset_loss for s in res.asset_shocks)
    assert sum_losses == 695350.00
    assert res.credit_loss + res.market_loss == 695350.00
    assert res.baseline_value - res.stressed_value == 695350.00


