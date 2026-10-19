import uuid
import json
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.models.db_models import Portfolio, PortfolioAsset, Entity
from app.models.schemas import (
    PortfolioRead,
    PortfolioCreate,
    PortfolioAssetRead,
    PortfolioExposureRead,
    SectorExposureItem,
    EntityRead
)
from app.core.logger import logger

router = APIRouter(prefix="/portfolios", tags=["Portfolios"])


def _calculate_portfolio_details(portfolio: Portfolio) -> PortfolioRead:
    """Computes asset market values, portfolio total value, and weights."""
    total_val = 0.0
    asset_reads = []

    for a in portfolio.assets:
        mv = a.shares * a.current_price
        total_val += mv

    for a in portfolio.assets:
        mv = a.shares * a.current_price
        weight = (mv / total_val) if total_val > 0 else 0.0
        entity_read = EntityRead.model_validate(a.entity) if a.entity else None
        
        attrs = None
        if a.attributes_json:
            try:
                attrs = json.loads(a.attributes_json)
            except Exception:
                attrs = None

        asset_reads.append(
            PortfolioAssetRead(
                id=a.id,
                portfolio_id=a.portfolio_id,
                ticker=a.ticker,
                asset_type=a.asset_type or "equity",
                issuer=a.issuer,
                currency=a.currency or "USD",
                shares=a.shares,
                purchase_price=a.purchase_price,
                current_price=a.current_price,
                notional=a.notional,
                sector_beta=a.sector_beta,
                attributes=attrs,
                entity=entity_read,
                market_value=round(mv, 2),
                weight=round(weight, 4)
            )
        )

    return PortfolioRead(
        id=portfolio.id,
        name=portfolio.name,
        description=portfolio.description,
        base_currency=portfolio.base_currency,
        initial_value=portfolio.initial_value,
        created_at=portfolio.created_at,
        assets=asset_reads,
        current_total_value=round(total_val, 2)
    )


@router.get("", response_model=List[PortfolioRead])
def list_portfolios(db: Session = Depends(get_db)):
    """List all portfolios with current total values and asset allocations."""
    portfolios = db.query(Portfolio).options(
        joinedload(Portfolio.assets).joinedload(PortfolioAsset.entity)
    ).all()
    return [_calculate_portfolio_details(p) for p in portfolios]


@router.post("", response_model=PortfolioRead, status_code=status.HTTP_201_CREATED)
def create_portfolio(portfolio_in: PortfolioCreate, db: Session = Depends(get_db)):
    """Create a new portfolio with asset allocations."""
    port_id = portfolio_in.id or f"port_{uuid.uuid4().hex[:12]}"
    
    existing = db.query(Portfolio).filter(Portfolio.id == port_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Portfolio with ID '{port_id}' already exists."
        )

    new_portfolio = Portfolio(
        id=port_id,
        name=portfolio_in.name,
        description=portfolio_in.description,
        base_currency=portfolio_in.base_currency,
        initial_value=portfolio_in.initial_value
    )
    db.add(new_portfolio)
    db.flush()

    for item in portfolio_in.assets:
        # Check or auto-register entity
        entity = db.query(Entity).filter(Entity.ticker == item.ticker.upper()).first()
        if not entity:
            entity = Entity(
                ticker=item.ticker.upper(),
                name=item.issuer or item.ticker.upper(),
                sector="General",
                asset_class=item.asset_type.capitalize()
            )
            db.add(entity)
            db.flush()

        attrs_str = json.dumps(item.attributes) if item.attributes else None

        asset_obj = PortfolioAsset(
            id=f"pa_{uuid.uuid4().hex[:12]}",
            portfolio_id=port_id,
            ticker=entity.ticker,
            asset_type=item.asset_type,
            issuer=item.issuer,
            currency=item.currency,
            shares=item.shares,
            purchase_price=item.purchase_price,
            current_price=item.current_price,
            notional=item.notional,
            sector_beta=item.sector_beta,
            attributes_json=attrs_str
        )
        db.add(asset_obj)

    db.commit()
    db.refresh(new_portfolio)
    return _calculate_portfolio_details(new_portfolio)


@router.get("/{portfolio_id}", response_model=PortfolioRead)
def get_portfolio(portfolio_id: str, db: Session = Depends(get_db)):
    """Get single portfolio details by ID."""
    portfolio = db.query(Portfolio).options(
        joinedload(Portfolio.assets).joinedload(PortfolioAsset.entity)
    ).filter(Portfolio.id == portfolio_id).first()

    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio with ID '{portfolio_id}' not found."
        )

    return _calculate_portfolio_details(portfolio)


@router.get("/{portfolio_id}/exposure", response_model=PortfolioExposureRead)
def get_portfolio_exposure(portfolio_id: str, db: Session = Depends(get_db)):
    """Calculate aggregated sector exposure and weighting for a given portfolio."""
    portfolio = db.query(Portfolio).options(
        joinedload(Portfolio.assets).joinedload(PortfolioAsset.entity)
    ).filter(Portfolio.id == portfolio_id).first()

    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio with ID '{portfolio_id}' not found."
        )

    total_val = sum(a.shares * a.current_price for a in portfolio.assets)
    sector_totals: Dict[str, float] = {}

    for a in portfolio.assets:
        mv = a.shares * a.current_price
        sector_name = a.entity.sector if a.entity else "Unclassified"
        sector_totals[sector_name] = sector_totals.get(sector_name, 0.0) + mv

    sector_exposures = []
    for sector, val in sector_totals.items():
        w = (val / total_val) if total_val > 0 else 0.0
        sector_exposures.append(
            SectorExposureItem(
                sector=sector,
                value=round(val, 2),
                weight=round(w, 4)
            )
        )

    # Sort descending by weight
    sector_exposures.sort(key=lambda x: x.weight, reverse=True)

    return PortfolioExposureRead(
        portfolio_id=portfolio.id,
        portfolio_name=portfolio.name,
        total_value=round(total_val, 2),
        sector_exposures=sector_exposures,
        holdings_count=len(portfolio.assets)
    )


@router.post("/sample/seed", response_model=PortfolioRead, status_code=status.HTTP_201_CREATED)
def seed_sample_portfolio(db: Session = Depends(get_db)):
    """Seed a representative multi-asset test portfolio with diversified equities."""
    sample_id = "port_multi_asset_sample"
    existing = db.query(Portfolio).filter(Portfolio.id == sample_id).first()
    if existing:
        return _calculate_portfolio_details(existing)

    # 1. Seed standard entities
    sample_entities = [
        {"ticker": "NVDA", "name": "NVIDIA Corporation", "sector": "Information Technology", "asset_class": "Equity"},
        {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Information Technology", "asset_class": "Equity"},
        {"ticker": "JPM", "name": "JPMorgan Chase & Co.", "sector": "Financials", "asset_class": "Equity"},
        {"ticker": "XOM", "name": "Exxon Mobil Corporation", "sector": "Energy", "asset_class": "Equity"},
        {"ticker": "LLY", "name": "Eli Lilly and Company", "sector": "Healthcare", "asset_class": "Equity"},
        {"ticker": "AMZN", "name": "Amazon.com Inc.", "sector": "Consumer Discretionary", "asset_class": "Equity"},
    ]

    for e in sample_entities:
        ent = db.query(Entity).filter(Entity.ticker == e["ticker"]).first()
        if not ent:
            db.add(Entity(**e))
    db.flush()

    # 2. Seed portfolio
    portfolio = Portfolio(
        id=sample_id,
        name="Global Multi-Asset Alpha Portfolio",
        description="Balanced high-conviction growth portfolio spanning Tech, Financials, Healthcare, and Energy.",
        base_currency="USD",
        initial_value=1_000_000.00
    )
    db.add(portfolio)
    db.flush()

    # 3. Seed portfolio assets
    sample_holdings = [
        {"ticker": "NVDA", "shares": 2000, "purchase_price": 115.00, "current_price": 130.00, "sector_beta": 1.45},
        {"ticker": "AAPL", "shares": 1500, "purchase_price": 210.00, "current_price": 230.00, "sector_beta": 1.05},
        {"ticker": "JPM", "shares": 800, "purchase_price": 195.00, "current_price": 215.00, "sector_beta": 1.10},
        {"ticker": "XOM", "shares": 1000, "purchase_price": 110.00, "current_price": 118.00, "sector_beta": 0.85},
        {"ticker": "LLY", "shares": 200, "purchase_price": 820.00, "current_price": 900.00, "sector_beta": 0.70},
        {"ticker": "AMZN", "shares": 800, "purchase_price": 175.00, "current_price": 185.00, "sector_beta": 1.20},
    ]

    for h in sample_holdings:
        pa = PortfolioAsset(
            id=f"pa_{uuid.uuid4().hex[:12]}",
            portfolio_id=sample_id,
            ticker=h["ticker"],
            shares=h["shares"],
            purchase_price=h["purchase_price"],
            current_price=h["current_price"],
            sector_beta=h["sector_beta"]
        )
        db.add(pa)

    db.commit()
    db.refresh(portfolio)
    return _calculate_portfolio_details(portfolio)


@router.post("/sample/wholesale", response_model=PortfolioRead, status_code=status.HTTP_201_CREATED)
def seed_wholesale_banking_portfolio(db: Session = Depends(get_db)):
    """
    Seed a representative wholesale-banking synthetic portfolio encompassing:
    - Corporate loans (amortized cost Basel II / IFRS 9 ECL model)
    - Sovereign government bonds (duration and convexity sensitivity)
    - Corporate bonds (duration and credit spread widening)
    - Public equities (beta-adjusted equity market shocks)
    - Derivative hedges (protective put delta hedge decoupling notional from market value)
    """
    sample_id = "port_wholesale_banking"
    existing = db.query(Portfolio).filter(Portfolio.id == sample_id).first()
    if existing:
        return _calculate_portfolio_details(existing)

    # 1. Register Entities
    entities = [
        {"ticker": "ACME_CORP_LOAN", "name": "Acme Industrial Holdings", "sector": "Industrials", "asset_class": "Loan"},
        {"ticker": "US_TREASURY_10Y", "name": "US Department of the Treasury", "sector": "Government", "asset_class": "Government Bond"},
        {"ticker": "MS_CORP_BOND_5Y", "name": "Morgan Stanley", "sector": "Financials", "asset_class": "Corporate Bond"},
        {"ticker": "NVDA", "name": "NVIDIA Corporation", "sector": "Information Technology", "asset_class": "Equity"},
        {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Information Technology", "asset_class": "Equity"},
        {"ticker": "SPX_PUT_HEDGE", "name": "CBOE SPX Protective Put Option", "sector": "Financials", "asset_class": "Derivative"}
    ]
    for e in entities:
        ent = db.query(Entity).filter(Entity.ticker == e["ticker"]).first()
        if not ent:
            db.add(Entity(**e))
    db.flush()

    # 2. Create Portfolio Record
    portfolio = Portfolio(
        id=sample_id,
        name="Synthetic Wholesale Banking Credit & Treasury Portfolio",
        description="Comprehensive wholesale banking portfolio modeling commercial loans, sovereign treasuries, corporate bonds, public equities, and derivative macro hedges.",
        base_currency="USD",
        initial_value=16_993_750.00
    )
    db.add(portfolio)
    db.flush()

    # 3. Create Multi-Asset Holdings
    # EAD=$5M, PD=2.5%, LGD=45% => ECL = $5M * 0.025 * 0.45 = $56,250 => Carrying Value = $4,943,750
    holdings = [
        {
            "ticker": "ACME_CORP_LOAN",
            "asset_type": "corporate_loan",
            "issuer": "Acme Industrial Holdings",
            "currency": "USD",
            "shares": 1.0,
            "purchase_price": 4_943_750.00,
            "current_price": 4_943_750.00,
            "notional": 5_000_000.00,
            "sector_beta": 1.0,
            "attributes": {"ead": 5_000_000.0, "pd": 0.025, "lgd": 0.45, "maturity_years": 3.5, "accounting": "amortized_cost"}
        },
        {
            "ticker": "US_TREASURY_10Y",
            "asset_type": "government_bond",
            "issuer": "US Department of the Treasury",
            "currency": "USD",
            "shares": 40_000.0,
            "purchase_price": 100.00,
            "current_price": 100.00,
            "notional": 4_000_000.00,
            "sector_beta": 0.0,
            "attributes": {"modified_duration": 7.8, "convexity": 65.0, "coupon": 0.0425, "rating": "AAA"}
        },
        {
            "ticker": "MS_CORP_BOND_5Y",
            "asset_type": "corporate_bond",
            "issuer": "Morgan Stanley",
            "currency": "USD",
            "shares": 30_000.0,
            "purchase_price": 100.00,
            "current_price": 100.00,
            "notional": 3_000_000.00,
            "sector_beta": 0.85,
            "attributes": {"modified_duration": 4.2, "credit_spread_bps": 120.0, "coupon": 0.0510, "rating": "A"}
        },
        {
            "ticker": "NVDA",
            "asset_type": "equity",
            "issuer": "NVIDIA Corporation",
            "currency": "USD",
            "shares": 20_000.0,
            "purchase_price": 115.00,
            "current_price": 130.00,
            "notional": 2_600_000.00,
            "sector_beta": 1.45,
            "attributes": {"market_cap": "mega_cap"}
        },
        {
            "ticker": "AAPL",
            "asset_type": "equity",
            "issuer": "Apple Inc.",
            "currency": "USD",
            "shares": 10_000.0,
            "purchase_price": 210.00,
            "current_price": 220.00,
            "notional": 2_200_000.00,
            "sector_beta": 1.05,
            "attributes": {"market_cap": "mega_cap"}
        },
        {
            "ticker": "SPX_PUT_HEDGE",
            "asset_type": "derivative",
            "issuer": "CBOE Exchange",
            "currency": "USD",
            "shares": 1_000.0,
            "purchase_price": 250.00,
            "current_price": 250.00,
            "notional": 10_000_000.00,  # Underlying exposure is $10M, market value is 1,000 * $250 = $250,000
            "sector_beta": -0.35,
            "attributes": {"delta": -0.35, "underlying": "SPX", "underlying_notional": 10_000_000.0, "strike": 5200.0, "maturity_days": 90, "hedge_type": "protective_put"}
        }
    ]

    for h in holdings:
        pa = PortfolioAsset(
            id=f"pa_{uuid.uuid4().hex[:12]}",
            portfolio_id=sample_id,
            ticker=h["ticker"],
            asset_type=h["asset_type"],
            issuer=h["issuer"],
            currency=h["currency"],
            shares=h["shares"],
            purchase_price=h["purchase_price"],
            current_price=h["current_price"],
            notional=h["notional"],
            sector_beta=h["sector_beta"],
            attributes_json=json.dumps(h["attributes"])
        )
        db.add(pa)

    db.commit()
    db.refresh(portfolio)
    return _calculate_portfolio_details(portfolio)
