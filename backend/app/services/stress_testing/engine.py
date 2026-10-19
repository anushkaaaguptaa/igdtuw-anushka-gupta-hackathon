"""
Portfolio Stress Engine for RiskLens AI.

Coordinates asset-level valuation, factor transmission, loss reconciliation,
sector and asset-class aggregations, and VaR/CVaR risk simulations.
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from app.models.schemas import (
    AssetShockDetail,
    StressTestSimulationResponse,
    RiskSignalRead
)
from app.services.stress_testing.scenarios import StressScenario
from app.services.stress_testing.valuation import value_asset_under_stress
from app.services.stress_testing.var_engine import run_portfolio_var_cvar_simulation
from app.core.logger import logger


@dataclass
class PortfolioStressResult:
    baseline_value: float
    stressed_value: float
    total_loss: float
    loss_percentage: float
    credit_loss: float
    market_loss: float
    loss_by_asset_type: Dict[str, float]
    loss_by_sector: Dict[str, float]
    asset_shocks: List[AssetShockDetail]
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    var_methodology: str
    assumptions: Dict[str, Any]


class PortfolioStressEngine:
    """
    Deterministic stress-testing calculation engine.
    Ensures mathematical reconciliation across asset classes, accounting conventions,
    and portfolio aggregates.
    """

    @classmethod
    def run_stress_test(
        cls,
        assets: List[Dict[str, Any]],
        scenario: StressScenario,
        severity_multiplier: float = 1.0,
        target_tickers: Optional[List[str]] = None,
        run_var_simulation: bool = True,
        n_var_simulations: int = 1000
    ) -> PortfolioStressResult:
        """
        Executes a deterministic stress test on a list of portfolio assets.
        
        Reconciliation Guarantees:
        1. total_loss == baseline_value - stressed_value
        2. total_loss == credit_loss + market_loss
        3. sum(asset_shocks.asset_loss) == total_loss
        4. sum(loss_by_sector.values()) == total_loss
        5. sum(loss_by_asset_type.values()) == total_loss
        """
        targets = [t.upper() for t in (target_tickers or [])]
        asset_shocks: List[AssetShockDetail] = []

        total_baseline = 0.0
        total_stressed = 0.0
        total_credit_loss = 0.0
        total_market_loss = 0.0

        raw_loss_by_asset_type: Dict[str, float] = {}
        raw_loss_by_sector: Dict[str, float] = {}

        for asset in assets:
            val_res = value_asset_under_stress(
                asset_data=asset,
                scenario=scenario,
                severity_multiplier=severity_multiplier,
                target_tickers=targets
            )

            ticker = str(asset.get("ticker", "UNKNOWN")).upper()
            name = str(asset.get("name") or ticker)
            asset_type = str(asset.get("asset_type", "equity")).lower()
            sector = str(asset.get("sector") or "General")
            currency = str(asset.get("currency", "USD"))
            shares = float(asset.get("shares", 1.0))
            notional = float(asset.get("notional") or (shares * float(asset.get("current_price", 100.0))))

            shock_detail = AssetShockDetail(
                ticker=ticker,
                name=name,
                asset_type=asset_type,
                sector=sector,
                currency=currency,
                shares=shares,
                notional=notional,
                baseline_price=val_res.baseline_price,
                stressed_price=val_res.stressed_price,
                pct_change=val_res.pct_change,
                baseline_value=val_res.baseline_value,
                stressed_value=val_res.stressed_value,
                asset_loss=val_res.asset_loss,
                credit_loss=val_res.credit_loss,
                market_loss=val_res.market_loss,
                valuation_methodology=val_res.valuation_methodology,
                shock_applied=val_res.shock_applied
            )
            asset_shocks.append(shock_detail)

            total_baseline += val_res.baseline_value
            total_stressed += val_res.stressed_value
            total_credit_loss += val_res.credit_loss
            total_market_loss += val_res.market_loss

            raw_loss_by_asset_type[asset_type] = raw_loss_by_asset_type.get(asset_type, 0.0) + val_res.asset_loss
            raw_loss_by_sector[sector] = raw_loss_by_sector.get(sector, 0.0) + val_res.asset_loss

        total_loss = round(total_baseline - total_stressed, 2)
        loss_pct = round((total_loss / total_baseline * 100.0), 2) if total_baseline > 0 else 0.0

        loss_by_asset_type = {k: round(v, 2) for k, v in raw_loss_by_asset_type.items()}
        loss_by_sector = {k: round(v, 2) for k, v in raw_loss_by_sector.items()}

        # --- Strict Reconciliation Checks (Fail Clearly on Discrepancy) ---
        # 1. Total loss matches sum of asset losses
        sum_asset_losses = round(sum(s.asset_loss for s in asset_shocks), 2)
        if abs(total_loss - sum_asset_losses) >= 0.05:
            raise ValueError(
                f"Loss reconciliation failure: total_loss={total_loss} != sum_asset_losses={sum_asset_losses}"
            )

        # 2. Total loss matches credit loss + market loss
        sum_components = round(total_credit_loss + total_market_loss, 2)
        if abs(total_loss - sum_components) >= 0.05:
            raise ValueError(
                f"Component reconciliation failure: total_loss={total_loss} != credit_loss({total_credit_loss}) + market_loss({total_market_loss})"
            )

        # 3. Sum of asset type losses reconciles to total loss
        sum_type_losses = round(sum(loss_by_asset_type.values()), 2)
        if abs(total_loss - sum_type_losses) >= 0.05:
            raise ValueError(
                f"Asset type breakdown reconciliation failure: total_loss={total_loss} != sum_type_losses={sum_type_losses}"
            )

        # 4. Sum of sector losses reconciles to total loss
        sum_sector_losses = round(sum(loss_by_sector.values()), 2)
        if abs(total_loss - sum_sector_losses) >= 0.05:
            raise ValueError(
                f"Sector breakdown reconciliation failure: total_loss={total_loss} != sum_sector_losses={sum_sector_losses}"
            )

        # 5. VaR / CVaR Monte Carlo simulation
        var_res = None
        if run_var_simulation and assets:
            var_res = run_portfolio_var_cvar_simulation(
                assets_data=assets,
                n_simulations=n_var_simulations,
                seed=42,
                stress_multiplier=severity_multiplier
            )

        assumptions = {
            "scenario_id": scenario.scenario_id,
            "scenario_name": scenario.name,
            "scenario_version": scenario.version,
            "severity_multiplier": severity_multiplier,
            "equity_market_shock": scenario.factor_shocks.equity_market_shock * severity_multiplier,
            "rate_shock_bps": scenario.factor_shocks.rate_shock_bps * severity_multiplier,
            "credit_spread_bps": scenario.factor_shocks.credit_spread_bps * severity_multiplier,
            "loan_pd_multiplier": scenario.factor_shocks.loan_pd_multiplier * severity_multiplier,
            "loan_lgd_add": scenario.factor_shocks.loan_lgd_add * severity_multiplier,
            "target_tickers": targets,
            "notes": scenario.factor_shocks.notes
        }

        return PortfolioStressResult(
            baseline_value=round(total_baseline, 2),
            stressed_value=round(total_stressed, 2),
            total_loss=total_loss,
            loss_percentage=loss_pct,
            credit_loss=round(total_credit_loss, 2),
            market_loss=round(total_market_loss, 2),
            loss_by_asset_type=loss_by_asset_type,
            loss_by_sector=loss_by_sector,
            asset_shocks=asset_shocks,
            var_95=var_res.var_95 if var_res else 0.0,
            var_99=var_res.var_99 if var_res else 0.0,
            cvar_95=var_res.cvar_95 if var_res else 0.0,
            cvar_99=var_res.cvar_99 if var_res else 0.0,
            var_methodology=var_res.methodology if var_res else "None",
            assumptions=assumptions
        )
