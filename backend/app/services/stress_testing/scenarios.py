import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from app.models.db_models import RiskSignal
from app.services.nlp.classifier import EventCategory
from app.core.logger import logger


@dataclass
class ScenarioFactorShocks:
    equity_market_shock: float  # e.g. -0.08 = -8%
    rate_shock_bps: float       # e.g. +100 bps = +0.0100
    credit_spread_bps: float    # e.g. +150 bps = +0.0150
    loan_pd_multiplier: float   # e.g. 1.8x baseline PD
    loan_lgd_add: float         # e.g. +0.10 (45% -> 55%)
    target_equity_haircut: float = 0.0 # Specific target entity shock
    sector_equity_shocks: Dict[str, float] = field(default_factory=dict)
    notes: str = ""


@dataclass
class StressScenario:
    scenario_id: str
    name: str
    description: str
    target_categories: List[str]
    factor_shocks: ScenarioFactorShocks
    version: str = "v1.0"


# Canonical Stress Scenarios Catalog
SCENARIO_CATALOG: Dict[str, StressScenario] = {
    "GEOPOLITICAL_ESCALATION": StressScenario(
        scenario_id="GEOPOLITICAL_ESCALATION",
        name="Geopolitical Escalation & Supply Chain Shock",
        description="Armed conflict escalation or trade sanctions triggering flight to quality, energy price spikes, and tech supply disruptions.",
        target_categories=[EventCategory.GEOPOLITICAL.value],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=-0.08,  # -8% broad market
            rate_shock_bps=-25.0,       # -25 bps flight to safe government bonds
            credit_spread_bps=45.0,     # +45 bps corporate spread widening
            loan_pd_multiplier=1.40,    # +40% increase in loan defaults
            loan_lgd_add=0.05,          # +5% LGD reduction in recoveries
            sector_equity_shocks={
                "Information Technology": -0.11,
                "Industrials": -0.09,
                "Energy": +0.04,        # Energy equities resilient/gain
                "Financials": -0.07
            },
            notes="Flight-to-safety drops Treasury yields while supply-chain disruption contracts tech margins."
        )
    ),
    "CENTRAL_BANK_RATE_HIKE": StressScenario(
        scenario_id="CENTRAL_BANK_RATE_HIKE",
        name="Central Bank Aggressive Monetary Tightening",
        description="Emergency 100 bps policy rate hike to combat resurgent inflation, depressing bond prices and compressing equity multiples.",
        target_categories=[EventCategory.MACROECONOMIC.value],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=-0.065, # -6.5% equity decline
            rate_shock_bps=100.0,       # +100 bps interest rate increase
            credit_spread_bps=35.0,     # +35 bps corporate spread widening
            loan_pd_multiplier=1.30,    # +30% higher borrower debt-service stress
            loan_lgd_add=0.03,
            sector_equity_shocks={
                "Information Technology": -0.09,
                "Financials": -0.02,    # Banks partially insulated by net interest margins
                "Real Estate": -0.12,
                "Utilities": -0.08
            },
            notes="Sharp yield curve shift damages long-duration sovereign and corporate bond holdings."
        )
    ),
    "CREDIT_EVENT_OR_DEFAULT": StressScenario(
        scenario_id="CREDIT_EVENT_OR_DEFAULT",
        name="Systemic Corporate Credit Event & Default",
        description="Major corporate borrower insolvency or debt restructuring triggering broad credit spread blowouts and loan impairment.",
        target_categories=[EventCategory.CREDIT_EVENT.value],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=-0.05,
            rate_shock_bps=-10.0,
            credit_spread_bps=225.0,    # +225 bps credit spread widening
            loan_pd_multiplier=3.50,    # Severe jump in default probabilities
            loan_lgd_add=0.18,          # Severe drop in collateral recovery values
            target_equity_haircut=-0.35,# Targeted entities plunge 35%
            sector_equity_shocks={
                "Financials": -0.09,
                "Industrials": -0.06
            },
            notes="Direct ECL surge on corporate loan exposures and steep corporate bond haircuts."
        )
    ),
    "BANKING_SECTOR_CRISIS": StressScenario(
        scenario_id="BANKING_SECTOR_CRISIS",
        name="Wholesale Banking & Liquidity Run Crisis",
        description="Interbank liquidity freeze and deposit outflows reminiscent of the SVB / Credit Suisse regional banking turmoil.",
        target_categories=[EventCategory.CREDIT_EVENT.value, EventCategory.REGULATORY_ACTION.value],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=-0.095,
            rate_shock_bps=-60.0,       # -60 bps safe-haven treasury surge
            credit_spread_bps=180.0,    # +180 bps corporate spread blowout
            loan_pd_multiplier=2.60,
            loan_lgd_add=0.12,
            target_equity_haircut=-0.30,
            sector_equity_shocks={
                "Financials": -0.18,    # Bank equities collapse 18%
                "Information Technology": -0.06
            },
            notes="Bank equity rout and severe spread widening offset partially by Treasury rally."
        )
    ),
    "MACROECONOMIC_RECESSION": StressScenario(
        scenario_id="MACROECONOMIC_RECESSION",
        name="Severe Macroeconomic Stagflation & Recession",
        description="Broad GDP contraction and corporate earnings recession across multiple business cycles.",
        target_categories=[EventCategory.MACROECONOMIC.value, EventCategory.EARNINGS_FINANCIAL_RESULTS.value],
        factor_shocks=ScenarioFactorShocks(
            equity_market_shock=-0.14,  # -14% broad market contraction
            rate_shock_bps=-40.0,       # -40 bps rate cuts priced in
            credit_spread_bps=140.0,    # +140 bps credit spread widening
            loan_pd_multiplier=2.20,    # Corporate defaults more than double
            loan_lgd_add=0.10,          # Collateral asset values drop
            sector_equity_shocks={
                "Consumer Discretionary": -0.18,
                "Industrials": -0.15,
                "Information Technology": -0.14,
                "Consumer Staples": -0.05
            },
            notes="Widespread cyclical asset decline across both credit portfolios and equity books."
        )
    )
}


def map_signal_to_scenario(signal: RiskSignal) -> StressScenario:
    """
    Deterministically maps a persisted RiskSignal to one of the 5 canonical stress scenarios.
    Uses event category and headline/evidence keyword markers.
    """
    category = signal.event_category
    text_corpus = f"{signal.impact_rationale or ''} {signal.evidence or ''}".lower()

    if category == EventCategory.GEOPOLITICAL.value or re.search(r"\b(war|sanction|tariff|conflict|taiwan|military)\b", text_corpus):
        return SCENARIO_CATALOG["GEOPOLITICAL_ESCALATION"]

    if category == EventCategory.MACROECONOMIC.value:
        if re.search(r"\b(rate|fed|hike|monetary|tightening|powell|cpi|inflation)\b", text_corpus):
            return SCENARIO_CATALOG["CENTRAL_BANK_RATE_HIKE"]
        return SCENARIO_CATALOG["MACROECONOMIC_RECESSION"]

    if category == EventCategory.CREDIT_EVENT.value:
        if re.search(r"\b(bank|liquidity|deposit|svb|run|contagion)\b", text_corpus):
            return SCENARIO_CATALOG["BANKING_SECTOR_CRISIS"]
        return SCENARIO_CATALOG["CREDIT_EVENT_OR_DEFAULT"]

    if category == EventCategory.EARNINGS_FINANCIAL_RESULTS.value:
        return SCENARIO_CATALOG["MACROECONOMIC_RECESSION"]

    if category == EventCategory.REGULATORY_ACTION.value:
        if re.search(r"\b(bank|capital|fdic|liquidity)\b", text_corpus):
            return SCENARIO_CATALOG["BANKING_SECTOR_CRISIS"]
        return SCENARIO_CATALOG["CREDIT_EVENT_OR_DEFAULT"]

    # Fallback to default macroeconomic recession scenario
    return SCENARIO_CATALOG["MACROECONOMIC_RECESSION"]
