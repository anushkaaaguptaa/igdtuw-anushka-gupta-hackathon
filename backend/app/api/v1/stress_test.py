import uuid
import json
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.config import settings
from app.core.database import get_db
from app.models.db_models import StressTestRun, Portfolio, RiskSignal, PortfolioAsset
from app.models.schemas import (
    StressTestSimulationRequest,
    StressTestSimulationResponse,
    StressTestRunRead,
    StressScenarioDefinition,
    RiskSignalRead
)
from app.services.stress_testing.scenarios import SCENARIO_CATALOG, map_signal_to_scenario, StressScenario
from app.services.stress_testing.engine import PortfolioStressEngine
from app.core.logger import logger

router = APIRouter(prefix="/stress-test", tags=["Stress Testing"])


@router.get("/scenarios", response_model=List[StressScenarioDefinition])
def list_available_scenarios():
    """
    Returns the catalog of 5 canonical financial stress scenarios with documented factor shocks:
    1. Geopolitical Escalation
    2. Central Bank Rate Hike
    3. Credit Event or Default
    4. Banking Sector Crisis
    5. Macroeconomic Recession
    """
    scenarios = []
    for s_id, s in SCENARIO_CATALOG.items():
        shocks = s.factor_shocks
        shocks_dict = {
            "equity_market_shock": shocks.equity_market_shock,
            "rate_shock_bps": shocks.rate_shock_bps,
            "credit_spread_bps": shocks.credit_spread_bps,
            "loan_pd_multiplier": shocks.loan_pd_multiplier,
            "loan_lgd_add": shocks.loan_lgd_add,
            "target_equity_haircut": shocks.target_equity_haircut,
            "sector_equity_shocks": shocks.sector_equity_shocks,
            "notes": shocks.notes
        }
        scenarios.append(
            StressScenarioDefinition(
                scenario_id=s.scenario_id,
                name=s.name,
                description=s.description,
                target_event_categories=s.target_categories,
                factor_shocks=shocks_dict
            )
        )
    return scenarios


@router.get("/runs", response_model=List[StressTestRunRead])
def list_stress_test_runs(db: Session = Depends(get_db)):
    """List historical stress-test runs stored in the database."""
    runs = db.query(StressTestRun).order_by(StressTestRun.simulated_at.desc()).limit(50).all()
    return [StressTestRunRead.model_validate(r) for r in runs]


@router.get("/runs/{run_id}", response_model=StressTestRunRead)
def get_stress_test_run(run_id: str, db: Session = Depends(get_db)):
    """Retrieve full breakdown and parameters of a specific historical stress-test run."""
    run = db.query(StressTestRun).filter(StressTestRun.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stress-test run with ID '{run_id}' not found."
        )
    return StressTestRunRead.model_validate(run)


@router.post("/simulate", response_model=StressTestSimulationResponse)
def simulate_stress_test(req: StressTestSimulationRequest, db: Session = Depends(get_db)):
    """
    Executes a deterministic before-and-after stress test on a synthetic portfolio.
    
    Features:
    - Multi-asset factor transmission (loans, treasuries, corp bonds, equities, derivatives)
    - Full mathematical loss reconciliation with zero double-counting
    - Value-at-Risk (VaR) and Conditional Value-at-Risk (CVaR) via 1,000-draw Monte Carlo
    - Duplicate run prevention for automatic triggers
    - Full persistence of asset shocks and scenario assumptions
    """
    # 1. Fetch Portfolio
    portfolio = db.query(Portfolio).options(
        joinedload(Portfolio.assets).joinedload(PortfolioAsset.entity)
    ).filter(Portfolio.id == req.portfolio_id).first()

    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio with ID '{req.portfolio_id}' does not exist."
        )

    if not portfolio.assets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Portfolio '{req.portfolio_id}' contains no assets to simulate."
        )

    # 2. Resolve Trigger Signal and Duplicate Prevention
    signal = None
    target_tickers = []
    if req.signal_id:
        signal = db.query(RiskSignal).options(
            joinedload(RiskSignal.entity_associations)
        ).filter(RiskSignal.id == req.signal_id).first()

        if not signal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Risk signal with ID '{req.signal_id}' not found."
            )

        # Duplicate trigger prevention
        if not req.allow_duplicate:
            existing_run = db.query(StressTestRun).filter(
                StressTestRun.portfolio_id == portfolio.id,
                StressTestRun.trigger_signal_id == signal.id
            ).first()
            if existing_run:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Simulation for signal '{signal.id}' on portfolio '{portfolio.id}' has already been recorded (Run ID: {existing_run.id}). Set allow_duplicate=true to force a manual rerun."
                )

        target_tickers = [ea.ticker for ea in signal.entity_associations]

    # 3. Determine Stress Scenario
    if req.scenario_id:
        s_id = req.scenario_id.upper()
        if s_id in SCENARIO_CATALOG:
            scenario = SCENARIO_CATALOG[s_id]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Scenario '{req.scenario_id}' not found. Available scenarios: {list(SCENARIO_CATALOG.keys())}"
            )
        resolved_scenario_name = req.scenario_name or scenario.name
    elif signal:
        # Deterministically map signal to scenario
        scenario = map_signal_to_scenario(signal)
        resolved_scenario_name = req.scenario_name or scenario.name
    else:
        # Default or named scenario
        if req.scenario_name:
            matched = next((s for s in SCENARIO_CATALOG.values() if s.name.lower() == req.scenario_name.lower()), None)
            scenario = matched or SCENARIO_CATALOG["MACROECONOMIC_RECESSION"]
            resolved_scenario_name = req.scenario_name
        else:
            scenario = SCENARIO_CATALOG["MACROECONOMIC_RECESSION"]
            resolved_scenario_name = scenario.name

    # 4. Prepare Asset Inputs
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

    # 5. Run Portfolio Stress Engine
    n_var_sims = req.var_simulations or getattr(settings, "DEFAULT_VAR_SIMULATION_DRAWS", 1000)
    stress_res = PortfolioStressEngine.run_stress_test(
        assets=assets_data,
        scenario=scenario,
        severity_multiplier=req.severity_multiplier,
        target_tickers=target_tickers,
        run_var_simulation=True,
        n_var_simulations=n_var_sims
    )

    # 6. Persist Simulation Run
    sim_id = f"sim_{uuid.uuid4().hex[:12]}"
    now = datetime.datetime.now(datetime.timezone.utc)

    run_record = StressTestRun(
        id=sim_id,
        portfolio_id=portfolio.id,
        trigger_signal_id=signal.id if signal else None,
        scenario_id=scenario.scenario_id,
        scenario_version=scenario.version,
        scenario_name=resolved_scenario_name,
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
    db.commit()

    # 7. Construct Response
    signal_read = RiskSignalRead.model_validate(signal) if signal else None

    return StressTestSimulationResponse(
        simulation_id=sim_id,
        portfolio_id=portfolio.id,
        scenario_id=scenario.scenario_id,
        scenario_name=resolved_scenario_name,
        scenario_version=scenario.version,
        baseline_value=stress_res.baseline_value,
        stressed_value=stress_res.stressed_value,
        total_loss=stress_res.total_loss,
        loss_percentage=stress_res.loss_percentage,
        credit_loss=stress_res.credit_loss,
        market_loss=stress_res.market_loss,
        loss_by_asset_type=stress_res.loss_by_asset_type,
        loss_by_sector=stress_res.loss_by_sector,
        var_95=stress_res.var_95,
        var_99=stress_res.var_99,
        cvar_95=stress_res.cvar_95,
        cvar_99=stress_res.cvar_99,
        var_methodology=stress_res.var_methodology,
        trigger_signal=signal_read,
        scenario_assumptions=stress_res.assumptions,
        asset_shocks=stress_res.asset_shocks,
        simulated_at=now
    )
