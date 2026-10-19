"""
Automatic Stress Test Trigger Service.

Monitors incoming RiskSignal objects and automatically executes deterministic
stress simulations on portfolios when the signal's impact_score exceeds the
configured threshold (default: impact_score > 7).
"""

from typing import List, Optional
import uuid
import json
import datetime
from sqlalchemy.orm import Session, joinedload
from app.config import settings
from app.models.db_models import RiskSignal, Portfolio, PortfolioAsset, StressTestRun
from app.services.stress_testing.scenarios import map_signal_to_scenario
from app.services.stress_testing.engine import PortfolioStressEngine
from app.core.logger import logger


def evaluate_and_trigger_stress_test(
    signal: RiskSignal,
    db: Session,
    portfolio_ids: Optional[List[str]] = None
) -> List[StressTestRun]:
    """
    Evaluates whether a risk signal qualifies as a high-impact event (impact_score > threshold).
    If qualified, runs deterministic portfolio stress tests and persists StressTestRun records.
    Prevents duplicate automatic runs for the same event and portfolio.
    """
    threshold = getattr(settings, "AUTO_TRIGGER_IMPACT_THRESHOLD", 7)

    # 1. High-impact filter check: must be strictly > threshold
    if signal.impact_score <= threshold:
        logger.info(
            f"Signal '{signal.id}' impact_score={signal.impact_score} <= {threshold}. "
            f"Auto-trigger skipped (non-high-impact event)."
        )
        return []

    logger.info(
        f"High-impact signal detected: '{signal.id}' with impact_score={signal.impact_score} > {threshold}. "
        f"Initiating automatic portfolio stress tests..."
    )

    # 2. Select target portfolios
    query = db.query(Portfolio).options(
        joinedload(Portfolio.assets).joinedload(PortfolioAsset.entity)
    )
    if portfolio_ids:
        query = query.filter(Portfolio.id.in_(portfolio_ids))
    portfolios = query.all()

    if not portfolios:
        logger.warning("No portfolios found for auto-trigger stress simulation.")
        return []

    # 3. Determine Scenario and Targets
    scenario = map_signal_to_scenario(signal)
    target_tickers = [ea.ticker for ea in signal.entity_associations] if signal.entity_associations else []

    created_runs = []
    now = datetime.datetime.now(datetime.timezone.utc)

    for portfolio in portfolios:
        if not portfolio.assets:
            continue

        # Prevent duplicate auto-trigger run for the same event and portfolio
        existing = db.query(StressTestRun).filter(
            StressTestRun.portfolio_id == portfolio.id,
            StressTestRun.trigger_signal_id == signal.id
        ).first()

        if existing:
            logger.info(
                f"Auto-trigger duplicate prevented: Portfolio '{portfolio.id}' already tested against signal '{signal.id}' (Run: {existing.id})."
            )
            continue

        # Prepare assets data
        assets_data = []
        for a in portfolio.assets:
            attrs = {}
            if a.attributes_json:
                try:
                    attrs = json.loads(a.attributes_json)
                except Exception:
                    attrs = {}

            assets_data.append({
                "ticker": a.ticker,
                "name": a.entity.name if a.entity else a.ticker,
                "asset_type": a.asset_type or "equity",
                "sector": a.entity.sector if a.entity else "General",
                "currency": a.currency or "USD",
                "shares": a.shares,
                "current_price": a.current_price,
                "purchase_price": a.purchase_price,
                "notional": a.notional,
                "sector_beta": a.sector_beta,
                "attributes": attrs
            })

        # Run stress engine
        stress_res = PortfolioStressEngine.run_stress_test(
            assets=assets_data,
            scenario=scenario,
            severity_multiplier=1.0,
            target_tickers=target_tickers,
            run_var_simulation=True
        )

        sim_id = f"sim_auto_{uuid.uuid4().hex[:10]}"
        run_record = StressTestRun(
            id=sim_id,
            portfolio_id=portfolio.id,
            trigger_signal_id=signal.id,
            scenario_id=scenario.scenario_id,
            scenario_version=scenario.version,
            scenario_name=f"[AUTO] {scenario.name}",
            baseline_value=stress_res.baseline_value,
            stressed_value=stress_res.stressed_value,
            total_loss=stress_res.total_loss,
            loss_percentage=stress_res.loss_percentage,
            credit_loss=stress_res.credit_loss,
            market_loss=stress_res.market_loss,
            var_95=stress_res.var_95,
            var_99=stress_res.var_99,
            cvar_95=stress_res.cvar_95,
            cvar_99=stress_res.cvar_99,
            details_json=json.dumps([s.model_dump() for s in stress_res.asset_shocks]),
            assumptions_json=json.dumps(stress_res.assumptions),
            simulated_at=now
        )
        db.add(run_record)
        created_runs.append(run_record)

    try:
        if created_runs:
            db.commit()
            for r in created_runs:
                db.refresh(r)
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to commit auto-triggered stress test runs: {exc}")
        raise

    return created_runs
