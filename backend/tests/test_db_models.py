import datetime
import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.db_models import Article, Entity, RiskSignal, SignalEntity, Portfolio, PortfolioAsset, StressTestRun


def test_article_persistence_and_unique_constraint(db_session: Session):
    now = datetime.datetime.now(datetime.timezone.utc)
    art1 = Article(
        id="art_1",
        source="gdelt",
        title="NVIDIA announces next-generation Blackwell architecture",
        url="https://example.com/nvda-blackwell",
        published_at=now,
        raw_content="NVIDIA has unveiled its new AI acceleration chips...",
        language="en"
    )
    db_session.add(art1)
    db_session.commit()

    retrieved = db_session.query(Article).filter(Article.id == "art_1").first()
    assert retrieved is not None
    assert retrieved.title == "NVIDIA announces next-generation Blackwell architecture"
    assert retrieved.source == "gdelt"

    # Test unique constraint on URL
    art_dup = Article(
        id="art_2",
        source="rss_yahoo",
        title="Duplicate URL Article",
        url="https://example.com/nvda-blackwell",
        published_at=now,
        raw_content="Content...",
        language="en"
    )
    db_session.add(art_dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_signal_and_entity_associations(db_session: Session):
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # 1. Create Article
    article = Article(
        id="art_ftc_msft",
        source="gdelt",
        title="FTC probes tech partnership over antitrust concerns",
        url="https://example.com/ftc-probe",
        published_at=now,
        raw_content="Regulators opened an inquiry into major cloud AI agreements...",
        language="en"
    )
    db_session.add(article)

    # 2. Create Entities
    msft = Entity(ticker="MSFT", name="Microsoft Corporation", sector="Information Technology", asset_class="Equity")
    googl = Entity(ticker="GOOGL", name="Alphabet Inc.", sector="Communication Services", asset_class="Equity")
    db_session.add_all([msft, googl])
    db_session.flush()

    # 3. Create Risk Signal
    signal = RiskSignal(
        id="sig_ftc_001",
        article_id="art_ftc_msft",
        sentiment_score=-0.75,
        sentiment_label="negative",
        event_category="REGULATORY_INVESTIGATION",
        event_confidence=0.92,
        impact_score=8,
        impact_rationale="High-severity antitrust inquiry targeting cloud market leaders.",
        evidence="Regulators opened an inquiry into major cloud AI agreements",
        inference_mode="mock",
        model_version="finbert-v1+distilbart"
    )
    db_session.add(signal)
    db_session.flush()

    # 4. Associate Entities
    assoc_msft = SignalEntity(signal_id="sig_ftc_001", ticker="MSFT", relevance_score=0.95, is_primary_target=True)
    assoc_googl = SignalEntity(signal_id="sig_ftc_001", ticker="GOOGL", relevance_score=0.80, is_primary_target=False)
    db_session.add_all([assoc_msft, assoc_googl])
    db_session.commit()

    # Query signal and verify relationships
    saved_sig = db_session.query(RiskSignal).filter(RiskSignal.id == "sig_ftc_001").first()
    assert saved_sig is not None
    assert saved_sig.article.title == "FTC probes tech partnership over antitrust concerns"
    assert len(saved_sig.entity_associations) == 2
    tickers = [assoc.entity.ticker for assoc in saved_sig.entity_associations]
    assert "MSFT" in tickers
    assert "GOOGL" in tickers


def test_portfolio_and_holdings(db_session: Session):
    port = Portfolio(
        id="port_alpha",
        name="Alpha Hedge",
        description="Market neutral portfolio",
        base_currency="USD",
        initial_value=500_000.0
    )
    db_session.add(port)

    # Create entity
    aapl = Entity(ticker="AAPL", name="Apple Inc.", sector="Information Technology", asset_class="Equity")
    db_session.add(aapl)
    db_session.flush()

    # Add holding
    asset = PortfolioAsset(
        id="pa_001",
        portfolio_id="port_alpha",
        ticker="AAPL",
        shares=1000,
        purchase_price=220.0,
        current_price=230.0,
        sector_beta=1.1
    )
    db_session.add(asset)
    db_session.commit()

    saved_port = db_session.query(Portfolio).filter(Portfolio.id == "port_alpha").first()
    assert saved_port is not None
    assert len(saved_port.assets) == 1
    assert saved_port.assets[0].ticker == "AAPL"
    assert saved_port.assets[0].shares == 1000
    assert saved_port.assets[0].current_price == 230.0


def test_cascade_delete_article_removes_signals(db_session: Session):
    now = datetime.datetime.now(datetime.timezone.utc)
    art = Article(
        id="art_temp",
        source="fixture",
        title="Temporary Notice",
        url="https://example.com/temp",
        published_at=now,
        raw_content="Content",
        language="en"
    )
    db_session.add(art)
    db_session.flush()

    sig = RiskSignal(
        id="sig_temp",
        article_id="art_temp",
        sentiment_score=-0.2,
        sentiment_label="negative",
        event_category="MACRO_INTEREST_RATE_SHOCK",
        event_confidence=0.8,
        impact_score=4,
        impact_rationale="Moderate macro pressure",
        inference_mode="mock",
        model_version="finbert"
    )
    db_session.add(sig)
    db_session.commit()

    # Delete article
    db_session.delete(art)
    db_session.commit()

    # Signal should be cascade deleted
    remaining_sig = db_session.query(RiskSignal).filter(RiskSignal.id == "sig_temp").first()
    assert remaining_sig is None
