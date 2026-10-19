import pytest
import numpy as np
from app.services.stress_testing.var_engine import (
    calculate_empirical_var_cvar,
    run_portfolio_var_cvar_simulation
)


def test_var_cvar_against_known_analytical_normal_distribution():
    """
    Benchmark test against standard normal distribution N(0, 1).
    Analytical values:
    VaR_95 = 1.64485
    CVaR_95 = phi(1.64485) / (1 - 0.95) = 0.103135 / 0.05 ≈ 2.0627
    VaR_99 = 2.32635
    CVaR_99 = phi(2.32635) / (1 - 0.99) ≈ 2.6652
    """
    rng = np.random.RandomState(12345)
    # Generate large sample to test convergence
    sample = rng.randn(100_000)

    # 95% Confidence
    var_95, cvar_95 = calculate_empirical_var_cvar(sample, alpha=0.95)
    assert 1.62 <= var_95 <= 1.67, f"VaR_95={var_95} diverged from 1.645"
    assert 2.03 <= cvar_95 <= 2.10, f"CVaR_95={cvar_95} diverged from 2.063"

    # 99% Confidence
    var_99, cvar_99 = calculate_empirical_var_cvar(sample, alpha=0.99)
    assert 2.29 <= var_99 <= 2.36, f"VaR_99={var_99} diverged from 2.326"
    assert 2.60 <= cvar_99 <= 2.73, f"CVaR_99={cvar_99} diverged from 2.665"


def test_var_cvar_finite_samples_and_ties():
    """Verify behavior on small samples, constant values, and quantile ties."""
    # 1. Constant losses: All observations equal 500.0
    constant_losses = np.array([500.0] * 100)
    var_const, cvar_const = calculate_empirical_var_cvar(constant_losses, alpha=0.95)
    assert var_const == 500.00
    assert cvar_const == 500.00

    # 2. Known discrete ranking
    # 100 discrete losses: 1 to 100
    ranked_losses = np.arange(1.0, 101.0)
    var_discrete, cvar_discrete = calculate_empirical_var_cvar(ranked_losses, alpha=0.95)
    # 95th percentile of 1..100 with linear method is ~95.05
    assert 94.5 <= var_discrete <= 96.0
    # Tail is [96, 97, 98, 99, 100], mean is 98.0
    assert 97.0 <= cvar_discrete <= 98.5


def test_portfolio_var_cvar_simulation_properties_and_determinism():
    """
    Verify portfolio risk simulation:
    - VaR_99 >= VaR_95 > 0
    - CVaR_95 >= VaR_95
    - CVaR_99 >= VaR_99
    - Repeated runs with identical seed produce bit-for-bit identical outputs.
    """
    assets = [
        {"ticker": "NVDA", "asset_type": "equity", "shares": 1000, "current_price": 130.0, "sector_beta": 1.4},
        {"ticker": "UST_10Y", "asset_type": "government_bond", "shares": 500, "current_price": 100.0, "attributes": {"modified_duration": 7.5}},
        {"ticker": "CORP_LOAN", "asset_type": "corporate_loan", "shares": 1, "current_price": 490000.0, "attributes": {"ead": 500000.0, "pd": 0.02, "lgd": 0.45}}
    ]

    # Run 1
    res1 = run_portfolio_var_cvar_simulation(assets, n_simulations=1000, seed=42)
    # Run 2 with same seed
    res2 = run_portfolio_var_cvar_simulation(assets, n_simulations=1000, seed=42)

    # Determinism
    assert res1.var_95 == res2.var_95
    assert res1.var_99 == res2.var_99
    assert res1.cvar_95 == res2.cvar_95
    assert res1.cvar_99 == res2.cvar_99
    assert res1.mean_simulated_loss == res2.mean_simulated_loss
    assert res1.max_simulated_loss == res2.max_simulated_loss

    # Risk metric hierarchy
    assert res1.var_95 > 0
    assert res1.var_99 >= res1.var_95
    assert res1.cvar_95 >= res1.var_95
    assert res1.cvar_99 >= res1.var_99
    assert res1.max_simulated_loss >= res1.cvar_99


def test_var_cvar_empty_portfolio_handling():
    """Verify empty asset list handled cleanly without exception."""
    res = run_portfolio_var_cvar_simulation([], n_simulations=500)
    assert res.var_95 == 0.0
    assert res.var_99 == 0.0
    assert res.cvar_95 == 0.0
    assert res.cvar_99 == 0.0
    assert res.observations_count == 0


def test_cvar_averaging_with_ties_at_boundary():
    """
    Test that CVaR correctly averages the worst-tail losses without diluting the tail
    when multiple identical values exist at the VaR boundary.
    Fixture:
    100 observations:
    - 90 values of 0.0
    - 8 values of 50.0
    - 2 values of 100.0
    At alpha = 0.95, the worst 5% (5 observations) should be [100, 100, 50, 50, 50].
    Mean of the worst 5% tail = (100 + 100 + 50 + 50 + 50) / 5 = 70.00.
    A naive filter (losses >= 50.0) would erroneously include all 8 of the 50.0 observations,
    yielding (200 + 400) / 10 = 60.00.
    """
    sample = np.array([0.0] * 90 + [50.0] * 8 + [100.0] * 2)
    var_95, cvar_95 = calculate_empirical_var_cvar(sample, alpha=0.95)
    assert var_95 == 50.00
    assert cvar_95 == 70.00, f"Expected CVaR_95=70.00 with proper tail slice, got {cvar_95}"

