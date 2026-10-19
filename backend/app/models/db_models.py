import datetime
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    Index,
    func
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class Article(Base):
    __tablename__ = "raw_articles"

    id = Column(String(64), primary_key=True, index=True)
    source = Column(String(32), nullable=False, index=True)  # 'gdelt', 'financial_rss', 'replay_fixture', etc.
    source_id = Column(String(128), nullable=True)  # External GUID or GDELT record ID
    title = Column(String(512), nullable=False)
    url = Column(String(1024), unique=True, nullable=False, index=True)
    publisher = Column(String(128), nullable=True)
    published_at = Column(DateTime, nullable=False, index=True)
    fetched_at = Column(DateTime, default=func.now(), nullable=False)
    raw_content = Column(Text, nullable=False)
    language = Column(String(10), default="en", nullable=False)
    metadata_json = Column(Text, nullable=True)  # Serialized tags/category dictionary
    ingestion_status = Column(String(32), default="pending_nlp", nullable=False, index=True)  # 'processed', 'pending_nlp', 'error'
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    signals = relationship("RiskSignal", back_populates="article", cascade="all, delete-orphan")


class Entity(Base):
    __tablename__ = "entities"

    ticker = Column(String(16), primary_key=True, index=True)
    name = Column(String(256), nullable=False)
    sector = Column(String(128), nullable=False, index=True)
    asset_class = Column(String(64), default="Equity", nullable=False)

    # Relationships
    signal_associations = relationship("SignalEntity", back_populates="entity")
    portfolio_holdings = relationship("PortfolioAsset", back_populates="entity")


class RiskSignal(Base):
    __tablename__ = "risk_signals"

    id = Column(String(64), primary_key=True, index=True)
    article_id = Column(String(64), ForeignKey("raw_articles.id", ondelete="CASCADE"), nullable=False, index=True)
    sentiment_score = Column(Float, nullable=False)  # Range -1.0 to +1.0
    sentiment_label = Column(String(16), nullable=False)  # 'positive', 'neutral', 'negative'
    event_category = Column(String(64), nullable=False, index=True)
    event_confidence = Column(Float, nullable=False)
    impact_score = Column(Integer, nullable=False, index=True)  # Range 1 to 10
    impact_rationale = Column(Text, nullable=False)
    evidence = Column(Text, nullable=True)  # Excerpt/quote supporting classification
    probabilities_json = Column(Text, nullable=True)  # JSON-serialized probability distribution
    inference_mode = Column(String(32), nullable=False)  # 'neural_live', 'lexicon_fallback', 'mock'
    model_version = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)

    # Relationships
    article = relationship("Article", back_populates="signals")
    entity_associations = relationship("SignalEntity", back_populates="signal", cascade="all, delete-orphan")
    stress_test_runs = relationship("StressTestRun", back_populates="trigger_signal")


class SignalEntity(Base):
    __tablename__ = "signal_entities"

    signal_id = Column(String(64), ForeignKey("risk_signals.id", ondelete="CASCADE"), primary_key=True)
    ticker = Column(String(16), ForeignKey("entities.ticker", ondelete="CASCADE"), primary_key=True)
    relevance_score = Column(Float, default=1.0, nullable=False)
    is_primary_target = Column(Boolean, default=True, nullable=False)

    # Relationships
    signal = relationship("RiskSignal", back_populates="entity_associations")
    entity = relationship("Entity", back_populates="signal_associations")


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    base_currency = Column(String(8), default="USD", nullable=False)
    initial_value = Column(Float, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    assets = relationship("PortfolioAsset", back_populates="portfolio", cascade="all, delete-orphan")
    stress_test_runs = relationship("StressTestRun", back_populates="portfolio", cascade="all, delete-orphan")


class PortfolioAsset(Base):
    __tablename__ = "portfolio_assets"

    id = Column(String(64), primary_key=True)
    portfolio_id = Column(String(64), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker = Column(String(16), ForeignKey("entities.ticker"), nullable=False, index=True)
    asset_type = Column(String(32), default="equity", nullable=False)  # 'equity', 'corporate_loan', 'government_bond', 'corporate_bond', 'derivative'
    issuer = Column(String(128), nullable=True)
    currency = Column(String(8), default="USD", nullable=False)
    shares = Column(Float, nullable=False)  # Quantity / Contract count / Units
    purchase_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)  # Price or Unit Carrying Value
    notional = Column(Float, nullable=True)  # Notional principal (for loans/bonds/derivatives)
    sector_beta = Column(Float, default=1.0, nullable=False)
    attributes_json = Column(Text, nullable=True)  # Stores EAD, PD, LGD, Duration, Credit Spread, Delta, etc.

    # Relationships
    portfolio = relationship("Portfolio", back_populates="assets")
    entity = relationship("Entity", back_populates="portfolio_holdings")


class StressTestRun(Base):
    __tablename__ = "stress_test_runs"

    id = Column(String(64), primary_key=True, index=True)
    portfolio_id = Column(String(64), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    trigger_signal_id = Column(String(64), ForeignKey("risk_signals.id", ondelete="SET NULL"), nullable=True, index=True)
    scenario_id = Column(String(64), nullable=True, index=True)
    scenario_version = Column(String(16), default="v1.0", nullable=False)
    scenario_name = Column(String(128), nullable=False)
    baseline_value = Column(Float, nullable=False)
    stressed_value = Column(Float, nullable=False)
    total_loss = Column(Float, nullable=False)
    loss_percentage = Column(Float, nullable=False)
    credit_loss = Column(Float, default=0.0, nullable=False)
    market_loss = Column(Float, default=0.0, nullable=False)
    var_95 = Column(Float, nullable=True)
    var_99 = Column(Float, nullable=True)
    cvar_95 = Column(Float, nullable=True)
    cvar_99 = Column(Float, nullable=True)
    details_json = Column(Text, nullable=False)  # JSON-serialized asset-level shock results
    assumptions_json = Column(Text, nullable=True)  # JSON-serialized shock parameters
    simulated_at = Column(DateTime, default=func.now(), nullable=False, index=True)

    # Relationships
    portfolio = relationship("Portfolio", back_populates="stress_test_runs")
    trigger_signal = relationship("RiskSignal", back_populates="stress_test_runs")
