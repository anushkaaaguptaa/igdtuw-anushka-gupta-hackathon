import json
from typing import Dict, Any, Tuple
from dataclasses import dataclass
from app.models.schemas import AssetShockDetail
from app.services.stress_testing.scenarios import StressScenario


@dataclass
class AssetValuationResult:
    baseline_value: float
    stressed_value: float
    asset_loss: float
    credit_loss: float
    market_loss: float
    baseline_price: float
    stressed_price: float
    pct_change: float
    valuation_methodology: str
    shock_applied: str


def value_asset_under_stress(
    asset_data: Dict[str, Any],
    scenario: StressScenario,
    severity_multiplier: float = 1.0,
    target_tickers: list = None
) -> AssetValuationResult:
    """
    Asset-class appropriate valuation engine implementing deterministic
    before-and-after stress testing.
    
    Accounting Convention:
    1. Market-to-Market (MtM) instruments (Equities, Bonds, Derivatives):
       Loss = Baseline Value - Stressed Value
    2. Amortized Cost / Banking Book loans:
       Credit Loss = Stressed ECL - Baseline ECL
       Valuation Loss = Baseline Carrying Value - Stressed Carrying Value = Credit Loss
       (Zero double-counting: no market haircut is applied on top of credit loss).
    """
    targets = [t.upper() for t in (target_tickers or [])]
    asset_type = asset_data.get("asset_type", "equity").lower()
    ticker = asset_data.get("ticker", "UNKNOWN").upper()
    sector = asset_data.get("sector", "General")
    shares = float(asset_data.get("shares", 1.0))
    if shares < 0:
        raise ValueError(f"Invalid holding quantity for asset {ticker}: {shares}. Quantity cannot be negative.")

    current_price = float(asset_data.get("current_price", 100.0))
    if current_price < 0:
        raise ValueError(f"Invalid price for asset {ticker}: {current_price}. Price cannot be negative.")

    sector_beta = float(asset_data.get("sector_beta", 1.0))
    notional = float(asset_data.get("notional") or (shares * current_price))
    if notional < 0:
        raise ValueError(f"Invalid notional for asset {ticker}: {notional}. Notional cannot be negative.")
    
    # Parse attributes json if present
    attrs = asset_data.get("attributes") or {}
    if isinstance(attrs, str):
        try:
            attrs = json.loads(attrs)
        except Exception:
            attrs = {}

    shocks = scenario.factor_shocks
    mult = severity_multiplier

    # -------------------------------------------------------------------------
    # 1. Equity Valuation
    # -------------------------------------------------------------------------
    if asset_type == "equity":
        base_value = shares * current_price
        
        # Check target entity specific shock first
        if ticker in targets and shocks.target_equity_haircut != 0.0:
            pct_shock = shocks.target_equity_haircut * mult
            shock_desc = f"Direct Target Haircut ({pct_shock * 100:+.2f}%)"
        elif sector in shocks.sector_equity_shocks:
            pct_shock = shocks.sector_equity_shocks[sector] * mult
            shock_desc = f"Sector Specific Shock ({pct_shock * 100:+.2f}%)"
        else:
            pct_shock = shocks.equity_market_shock * sector_beta * mult
            shock_desc = f"Beta-Adjusted Market Shock ({pct_shock * 100:+.2f}%, beta={sector_beta:.2f})"

        # Equity price cannot fall below 0
        stressed_price = max(0.0, current_price * (1.0 + pct_shock))
        stressed_value = shares * stressed_price
        loss = base_value - stressed_value
        pct_change = (pct_shock * 100.0) if current_price > 0 else 0.0

        return AssetValuationResult(
            baseline_value=round(base_value, 2),
            stressed_value=round(stressed_value, 2),
            asset_loss=round(loss, 2),
            credit_loss=0.0,
            market_loss=round(loss, 2),
            baseline_price=round(current_price, 2),
            stressed_price=round(stressed_price, 2),
            pct_change=round(pct_change, 2),
            valuation_methodology="equity_mtm",
            shock_applied=shock_desc
        )

    # -------------------------------------------------------------------------
    # 2. Government Bond Valuation (Duration Approximation)
    # -------------------------------------------------------------------------
    elif asset_type in ("government_bond", "sovereign_bond"):
        base_value = shares * current_price
        mod_duration = float(attrs.get("modified_duration", 7.5))
        if mod_duration < 0:
            raise ValueError(f"Invalid modified duration for bond {ticker}: {mod_duration}. Duration cannot be negative.")
        convexity = float(attrs.get("convexity", 50.0))

        # Interest rate change in decimal: rate_shock_bps / 10,000
        delta_y = (shocks.rate_shock_bps / 10_000.0) * mult

        # Bond pricing approximation: dP/P ≈ -D_mod * dy + 0.5 * C * (dy)^2
        pct_bond_change = (-mod_duration * delta_y) + (0.5 * convexity * (delta_y ** 2))
        stressed_price = max(0.0, current_price * (1.0 + pct_bond_change))
        stressed_value = max(0.0, base_value * (1.0 + pct_bond_change))
        loss = base_value - stressed_value

        shock_desc = f"Rate Shift {shocks.rate_shock_bps * mult:+.1f} bps (D_mod={mod_duration:.1f})"

        return AssetValuationResult(
            baseline_value=round(base_value, 2),
            stressed_value=round(stressed_value, 2),
            asset_loss=round(loss, 2),
            credit_loss=0.0,
            market_loss=round(loss, 2),
            baseline_price=round(current_price, 2),
            stressed_price=round(stressed_price, 2),
            pct_change=round(pct_bond_change * 100.0, 2),
            valuation_methodology="bond_modified_duration_convexity",
            shock_applied=shock_desc
        )

    # -------------------------------------------------------------------------
    # 3. Corporate Bond Valuation (Duration + Credit Spread Widening)
    # -------------------------------------------------------------------------
    elif asset_type == "corporate_bond":
        base_value = shares * current_price
        mod_duration = float(attrs.get("modified_duration", 4.5))
        if mod_duration < 0:
            raise ValueError(f"Invalid modified duration for corporate bond {ticker}: {mod_duration}. Duration cannot be negative.")

        delta_y = (shocks.rate_shock_bps / 10_000.0) * mult
        delta_s = (shocks.credit_spread_bps / 10_000.0) * mult
        total_yield_shift = delta_y + delta_s

        # dP/P ≈ -D_mod * (dy + ds)
        pct_bond_change = -mod_duration * total_yield_shift
        stressed_price = max(0.0, current_price * (1.0 + pct_bond_change))
        stressed_value = max(0.0, base_value * (1.0 + pct_bond_change))
        loss = base_value - stressed_value

        shock_desc = f"Rate {shocks.rate_shock_bps * mult:+.0f} bps + Spread {shocks.credit_spread_bps * mult:+.0f} bps"

        return AssetValuationResult(
            baseline_value=round(base_value, 2),
            stressed_value=round(stressed_value, 2),
            asset_loss=round(loss, 2),
            credit_loss=0.0,
            market_loss=round(loss, 2),
            baseline_price=round(current_price, 2),
            stressed_price=round(stressed_price, 2),
            pct_change=round(pct_bond_change * 100.0, 2),
            valuation_methodology="corporate_bond_spread_duration",
            shock_applied=shock_desc
        )

    # -------------------------------------------------------------------------
    # 4. Corporate Loan (Amortized Cost ECL Model)
    # -------------------------------------------------------------------------
    elif asset_type in ("corporate_loan", "commercial_loan"):
        # EAD (Exposure at Default)
        ead = float(attrs.get("ead") or notional or (shares * current_price))
        if ead < 0:
            raise ValueError(f"Invalid EAD for loan {ticker}: {ead}. Exposure at default cannot be negative.")
        pd_base = float(attrs.get("pd", 0.025))   # Baseline 2.5% PD
        if not (0.0 <= pd_base <= 1.0):
            raise ValueError(f"Invalid baseline PD for loan {ticker}: {pd_base}. Probability of default must be within [0, 1].")
        lgd_base = float(attrs.get("lgd", 0.45))  # Baseline 45% LGD
        if not (0.0 <= lgd_base <= 1.0):
            raise ValueError(f"Invalid baseline LGD for loan {ticker}: {lgd_base}. Loss given default must be within [0, 1].")

        # Baseline Expected Credit Loss: ECL = EAD * PD * LGD
        ecl_base = ead * pd_base * lgd_base
        carrying_base = ead - ecl_base

        # Stressed PD and LGD
        pd_stressed = min(1.0, pd_base * (shocks.loan_pd_multiplier * mult))
        lgd_stressed = min(1.0, lgd_base + (shocks.loan_lgd_add * mult))
        ecl_stressed = ead * pd_stressed * lgd_stressed
        carrying_stressed = max(0.0, ead - ecl_stressed)

        credit_loss = ecl_stressed - ecl_base
        pct_change = -((credit_loss / carrying_base) * 100.0) if carrying_base > 0 else 0.0

        shock_desc = f"PD {pd_base * 100:.1f}%->{pd_stressed * 100:.1f}%, LGD {lgd_base * 100:.1f}%->{lgd_stressed * 100:.1f}%"

        return AssetValuationResult(
            baseline_value=round(carrying_base, 2),
            stressed_value=round(carrying_stressed, 2),
            asset_loss=round(credit_loss, 2),
            credit_loss=round(credit_loss, 2),
            market_loss=0.0,
            baseline_price=round(carrying_base / shares if shares > 0 else current_price, 2),
            stressed_price=round(carrying_stressed / shares if shares > 0 else current_price, 2),
            pct_change=round(pct_change, 2),
            valuation_methodology="ecl_amortized_cost",
            shock_applied=shock_desc
        )

    # -------------------------------------------------------------------------
    # 5. Derivative Position (Hedge / Option Delta Model)
    # -------------------------------------------------------------------------
    elif asset_type == "derivative":
        # Current derivative market value (premium)
        base_value = shares * current_price
        underlying_notional = float(attrs.get("underlying_notional") or notional or 10_000_000.0)
        if underlying_notional < 0:
            raise ValueError(f"Invalid underlying notional for derivative {ticker}: {underlying_notional}. Underlying notional cannot be negative.")
        delta = float(attrs.get("delta", -0.35))  # Negative delta for protective put option
        
        # Underlying equity market shock
        underlying_shock = shocks.equity_market_shock * mult

        # Delta hedging approximation: dV ≈ delta * (dS/S) * Notional
        # For a protective put (delta < 0), equity decline (underlying_shock < 0) yields a positive dV gain.
        delta_v = delta * underlying_shock * underlying_notional
        stressed_value = max(0.0, base_value + delta_v)
        loss = base_value - stressed_value  # Negative loss represents hedging gain

        stressed_price = (stressed_value / shares) if shares > 0 else current_price
        pct_change = ((stressed_value - base_value) / base_value * 100.0) if base_value > 0 else 0.0
        shock_desc = f"Delta {delta:+.2f} hedge on {underlying_shock * 100:+.1f}% underlying move"

        return AssetValuationResult(
            baseline_value=round(base_value, 2),
            stressed_value=round(stressed_value, 2),
            asset_loss=round(loss, 2),
            credit_loss=0.0,
            market_loss=round(loss, 2),
            baseline_price=round(current_price, 2),
            stressed_price=round(stressed_price, 2),
            pct_change=round(pct_change, 2),
            valuation_methodology="derivative_delta_hedge",
            shock_applied=shock_desc
        )

    # -------------------------------------------------------------------------
    # Fallback Generic MtM
    # -------------------------------------------------------------------------
    else:
        base_value = shares * current_price
        pct_shock = shocks.equity_market_shock * mult
        stressed_value = max(0.0, base_value * (1.0 + pct_shock))
        loss = base_value - stressed_value
        return AssetValuationResult(
            baseline_value=round(base_value, 2),
            stressed_value=round(stressed_value, 2),
            asset_loss=round(loss, 2),
            credit_loss=0.0,
            market_loss=round(loss, 2),
            baseline_price=round(current_price, 2),
            stressed_price=round(current_price * (1.0 + pct_shock), 2),
            pct_change=round(pct_shock * 100.0, 2),
            valuation_methodology="generic_mtm",
            shock_applied=f"Generic Flat Shock ({pct_shock * 100:+.1f}%)"
        )
