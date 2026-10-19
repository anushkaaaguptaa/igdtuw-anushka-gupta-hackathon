"""
VaR and CVaR Calculation Engine for RiskLens AI.

Methodology Documentation:
1. Loss Variable:
   L = -(V_sim - V_0) = V_0 - V_sim, where V_0 is baseline portfolio carrying value
   and V_sim is the revalued portfolio under a simulated risk-factor realization.
   Positive L indicates a financial loss; negative L indicates a gain.

2. Risk Metric Definitions:
   - Value-at-Risk (VaR_alpha): The alpha-quantile of the loss distribution L over horizon T.
     VaR_alpha = inf { l in R : P(L <= l) >= alpha }
     For discrete empirical or simulated samples of size N sorted in ascending order:
     VaR_alpha = Quantile_alpha(L)
   - Conditional Value-at-Risk (CVaR_alpha / Expected Shortfall):
     The conditional expectation of losses exceeding the VaR_alpha threshold:
     CVaR_alpha = E[L | L >= VaR_alpha]
     Finite-sample convention: Mean of all observations L_k such that L_k >= VaR_alpha.
     If all tail observations are equal (quantile ties), CVaR collapses to VaR_alpha.

3. Simulation Methodology:
   - Type: Multi-factor Monte Carlo simulation.
   - Horizon: 10-day risk horizon (T = 10 / 252 business days).
   - Sample Size: N = 1,000 observations generated via correlated multivariate factor draws.
   - Core Risk Factors:
     1. Equity Market Index Return (mu=0.0, sigma=0.16 annualized)
     2. Benchmark Sovereign Yield Shift (sigma=80 bps annualized)
     3. Investment Grade Credit Spread Shift (sigma=75 bps annualized)
     4. High-Yield / Loan Default Distress Factor (mu=0.0, sigma=1.0 standard normal)
   - Factor Correlation Structure:
     [ Equity, Rate, Spread, Credit ] calibrated to stylized historical wholesale-banking regimes:
     corr(Equity, Spread) = -0.55
     corr(Equity, Rate) = -0.15
     corr(Spread, Credit) = +0.65
   - Pricing Formulas:
     Strictly identical to the deterministic Phase 4 valuation engine:
     - Equities: Beta-adjusted market returns.
     - Government Bonds: Modified duration + convexity.
     - Corporate Bonds: Modified duration + spread sensitivity.
     - Corporate Loans: Basel II / IFRS 9 ECL simulation (EAD * PD * LGD).
     - Derivatives: First-order Delta approximation on underlying notional.
   - Reproducibility: Deterministic NumPy RandomState(seed=42) ensuring exact repeatability.
"""

from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
import numpy as np
from app.services.stress_testing.valuation import value_asset_under_stress
from app.services.stress_testing.scenarios import StressScenario, ScenarioFactorShocks


@dataclass
class VaRResult:
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    observations_count: int
    horizon_days: int
    methodology: str
    mean_simulated_loss: float
    max_simulated_loss: float


def calculate_empirical_var_cvar(
    losses: np.ndarray,
    alpha: float = 0.95
) -> Tuple[float, float]:
    """
    Computes discrete VaR and CVaR from an array of simulated losses.
    
    Parameters:
    - losses: 1D array of portfolio losses L = V_0 - V_sim
    - alpha: Confidence level (e.g. 0.95 or 0.99)
    
    Convention:
    - VaR_alpha: alpha-quantile of the empirical loss distribution.
    - CVaR_alpha (Expected Shortfall): Conditional expectation of losses in the worst (1 - alpha) tail.
      For discrete samples of size N, the tail contains exactly k = max(1, ceil(N * (1 - alpha)))
      observations. Evaluated as the mean of the top k worst losses, properly preserving tail
      expectation even when ties occur at the VaR boundary.
    """
    if len(losses) == 0:
        return 0.0, 0.0

    # Loss quantile at alpha
    var_val = float(np.percentile(losses, alpha * 100.0, method="linear"))

    # Tail losses: worst k observations in descending order
    # Round to avoid floating point precision artifacts (e.g. 100 * (1 - 0.95) = 5.0000000000000044)
    k = max(1, int(np.ceil(round(len(losses) * (1.0 - alpha), 7))))
    sorted_losses = np.sort(losses)[::-1]
    cvar_val = float(np.mean(sorted_losses[:k]))

    # Enforce finite-sample monotonicity: CVaR >= VaR
    cvar_val = max(var_val, cvar_val)

    return round(var_val, 2), round(cvar_val, 2)


def run_portfolio_var_cvar_simulation(
    assets_data: List[Dict[str, Any]],
    n_simulations: int = 1000,
    seed: int = 42,
    horizon_days: int = 10,
    stress_multiplier: float = 1.0
) -> VaRResult:
    """
    Executes a multi-factor Monte Carlo simulation for wholesale-banking portfolio risk.
    Uses an illustrative synthetic 4-factor correlation matrix.
    """
    if not assets_data:
        return VaRResult(
            var_95=0.0,
            var_99=0.0,
            cvar_95=0.0,
            cvar_99=0.0,
            observations_count=0,
            horizon_days=horizon_days,
            methodology="multi_factor_monte_carlo_empty",
            mean_simulated_loss=0.0,
            max_simulated_loss=0.0
        )

    # 1. Illustrative 4-factor correlation matrix [Equity, Rate, Spread, Credit]
    corr_matrix = np.array([
        [ 1.00, -0.15, -0.55, -0.45],
        [-0.15,  1.00, -0.10, -0.05],
        [-0.55, -0.10,  1.00,  0.65],
        [-0.45, -0.05,  0.65,  1.00]
    ])

    # Annualized volatilities scaled to horizon T = 10 / 252
    time_scale = np.sqrt(horizon_days / 252.0)
    sigma_equity = 0.16 * time_scale * stress_multiplier
    sigma_rate = 0.0080 * time_scale * stress_multiplier    # 80 bps annual vol
    sigma_spread = 0.0075 * time_scale * stress_multiplier  # 75 bps annual vol
    sigma_credit = 1.0 * stress_multiplier

    # Cholesky decomposition for correlated normal draws
    rng = np.random.RandomState(seed)
    l_chol = np.linalg.cholesky(corr_matrix)
    uncorrelated_draws = rng.randn(n_simulations, 4)
    correlated_draws = uncorrelated_draws @ l_chol.T

    simulated_losses = np.zeros(n_simulations)

    # 2. Simulate revaluation for each draw
    for k in range(n_simulations):
        z_eq, z_rate, z_spread, z_credit = correlated_draws[k]

        # Factor shocks for this scenario realization
        eq_shock = float(z_eq * sigma_equity)
        rate_bps = float(z_rate * sigma_rate * 10_000.0)
        spread_bps = float(z_spread * sigma_spread * 10_000.0)
        # Credit multiplier: standard log-normal shift
        pd_mult = float(max(0.5, np.exp(z_credit * 0.25)))
        lgd_add = float(max(0.0, z_credit * 0.03))

        draw_scenario = StressScenario(
            scenario_id=f"MC_DRAW_{k}",
            name=f"Monte Carlo Draw {k}",
            description="Synthetic correlated factor realization",
            target_categories=[],
            factor_shocks=ScenarioFactorShocks(
                equity_market_shock=eq_shock,
                rate_shock_bps=rate_bps,
                credit_spread_bps=spread_bps,
                loan_pd_multiplier=pd_mult,
                loan_lgd_add=lgd_add,
                target_equity_haircut=0.0,
                sector_equity_shocks={}
            )
        )

        # Revalue each asset and sum asset losses directly (consistent with valuation engine)
        draw_loss = 0.0
        for a in assets_data:
            res = value_asset_under_stress(a, draw_scenario, severity_multiplier=1.0)
            draw_loss += res.asset_loss

        simulated_losses[k] = draw_loss

    # 3. Compute VaR and CVaR at 95% and 99%
    var_95, cvar_95 = calculate_empirical_var_cvar(simulated_losses, alpha=0.95)
    var_99, cvar_99 = calculate_empirical_var_cvar(simulated_losses, alpha=0.99)

    return VaRResult(
        var_95=var_95,
        var_99=var_99,
        cvar_95=cvar_95,
        cvar_99=cvar_99,
        observations_count=n_simulations,
        horizon_days=horizon_days,
        methodology=f"Multi-Factor Monte Carlo ({n_simulations} draws, {horizon_days}-day horizon, illustrative synthetic Cholesky correlation matrix)",
        mean_simulated_loss=round(float(np.mean(simulated_losses)), 2),
        max_simulated_loss=round(float(np.max(simulated_losses)), 2)
    )
