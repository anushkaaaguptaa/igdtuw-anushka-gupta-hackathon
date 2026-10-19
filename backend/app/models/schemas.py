import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# -------------------------------------------------------------------------
# Health Schemas
# -------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str = Field(..., examples=["healthy"])
    app_name: str
    version: str
    environment: str
    database_status: str
    inference_mode: str
    timestamp: datetime.datetime


# -------------------------------------------------------------------------
# Article Schemas
# -------------------------------------------------------------------------
class ArticleBase(BaseModel):
    source: str = Field(..., examples=["gdelt"])
    source_id: Optional[str] = None
    title: str
    url: str
    publisher: Optional[str] = None
    published_at: datetime.datetime
    fetched_at: Optional[datetime.datetime] = None
    raw_content: str
    language: str = "en"
    metadata_json: Optional[str] = None
    ingestion_status: str = "pending_nlp"
    error_message: Optional[str] = None


class ArticleCreate(ArticleBase):
    id: Optional[str] = None


class ArticleRead(ArticleBase):
    id: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------------
# Entity Schemas
# -------------------------------------------------------------------------
class EntityBase(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=16, examples=["NVDA"])
    name: str = Field(..., examples=["NVIDIA Corporation"])
    sector: str = Field(..., examples=["Information Technology"])
    asset_class: str = Field(default="Equity", examples=["Equity"])


class EntityCreate(EntityBase):
    pass


class EntityRead(EntityBase):
    model_config = ConfigDict(from_attributes=True)


class AffectedEntityRead(BaseModel):
    ticker: str
    name: str
    sector: str
    asset_class: str
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    is_primary_target: bool = True

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------------
# Risk Signal Schemas
# -------------------------------------------------------------------------
class RiskSignalBase(BaseModel):
    sentiment_score: float = Field(..., ge=-1.0, le=1.0, description="FinBERT continuous score: P(pos) - P(neg)")
    sentiment_label: str = Field(..., examples=["negative"])
    sentiment_probabilities: Optional[Dict[str, float]] = Field(
        default=None,
        description="Probability distribution across positive, neutral, negative classes"
    )
    event_category: str = Field(..., examples=["REGULATORY_INVESTIGATION"])
    event_confidence: float = Field(..., ge=0.0, le=1.0)
    impact_score: int = Field(..., ge=1, le=10, description="Deterministic severity impact scale 1-10")
    impact_rationale: str
    evidence: Optional[str] = None
    inference_mode: str = Field(..., description="neural_live, lexicon_fallback, or mock")
    model_version: str


class RiskSignalCreate(RiskSignalBase):
    id: Optional[str] = None
    article_id: str
    entity_tickers: List[str] = Field(default_factory=list)


class RiskSignalRead(RiskSignalBase):
    id: str
    article_id: str
    created_at: datetime.datetime
    article: Optional[ArticleRead] = None
    affected_entities: List[AffectedEntityRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class SignalListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[RiskSignalRead]


class TextAnalysisRequest(BaseModel):
    title: str = Field(..., min_length=1, examples=["FTC launches antitrust probe into Microsoft cloud partnership"])
    content: Optional[str] = Field(default="", examples=["The Federal Trade Commission announced an inquiry into market exclusivity."])
    save_to_db: bool = Field(default=False, description="Persist the resulting article and signal to database")
    source: str = Field(default="direct_input", examples=["direct_input"])
    url: Optional[str] = None


class TextAnalysisResponse(BaseModel):
    signal: RiskSignalRead
    processing_status: str = Field(..., examples=["success"])
    execution_time_ms: float



# -------------------------------------------------------------------------
# Portfolio Schemas
# -------------------------------------------------------------------------
class PortfolioAssetBase(BaseModel):
    ticker: str
    asset_type: str = Field(default="equity", examples=["equity", "corporate_loan", "government_bond", "corporate_bond", "derivative"])
    issuer: Optional[str] = None
    currency: str = "USD"
    shares: float = Field(..., gt=0, description="Quantity / Unit count / Contracts")
    purchase_price: float = Field(..., gt=0)
    current_price: float = Field(..., gt=0)
    notional: Optional[float] = Field(default=None, description="Notional principal for bonds, loans, and derivatives")
    sector_beta: float = Field(default=1.0, description="Beta sensitivity to market factor (negative for hedges)")
    attributes: Optional[Dict[str, Any]] = Field(default=None, description="Asset attributes: ead, pd, lgd, duration, spread, delta")


class PortfolioAssetCreate(PortfolioAssetBase):
    pass


class PortfolioAssetRead(PortfolioAssetBase):
    id: str
    portfolio_id: str
    entity: Optional[EntityRead] = None
    market_value: float = 0.0
    weight: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class PortfolioBase(BaseModel):
    name: str = Field(..., examples=["Tech Growth Alpha"])
    description: Optional[str] = None
    base_currency: str = "USD"
    initial_value: float = Field(..., gt=0)


class PortfolioCreate(PortfolioBase):
    id: Optional[str] = None
    assets: List[PortfolioAssetCreate] = Field(default_factory=list)


class PortfolioRead(PortfolioBase):
    id: str
    created_at: datetime.datetime
    assets: List[PortfolioAssetRead] = Field(default_factory=list)
    current_total_value: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class SectorExposureItem(BaseModel):
    sector: str
    value: float
    weight: float


class PortfolioExposureRead(BaseModel):
    portfolio_id: str
    portfolio_name: str
    total_value: float
    sector_exposures: List[SectorExposureItem]
    holdings_count: int


# -------------------------------------------------------------------------
# Stress Test Schemas
# -------------------------------------------------------------------------
class AssetShockDetail(BaseModel):
    ticker: str
    name: str
    asset_type: str
    sector: str
    currency: str = "USD"
    shares: float
    notional: Optional[float] = None
    baseline_price: float
    stressed_price: float
    pct_change: float
    baseline_value: float
    stressed_value: float
    asset_loss: float
    credit_loss: float = 0.0
    market_loss: float = 0.0
    valuation_methodology: str
    shock_applied: str


class StressTestSimulationRequest(BaseModel):
    portfolio_id: str
    signal_id: Optional[str] = None
    scenario_id: Optional[str] = None
    scenario_name: Optional[str] = None
    severity_multiplier: float = Field(default=1.0, ge=0.1, le=5.0)
    var_simulations: Optional[int] = Field(default=None, ge=100, le=10000, description="Optional Monte Carlo draw count (default: 1000)")
    allow_duplicate: bool = Field(default=False, description="When false, prevents duplicate auto-runs for the same signal and portfolio")


class StressTestSimulationResponse(BaseModel):
    simulation_id: str
    portfolio_id: str
    scenario_id: str
    scenario_name: str
    scenario_version: str = "v1.0"
    baseline_value: float
    stressed_value: float
    total_loss: float
    loss_percentage: float
    credit_loss: float
    market_loss: float
    loss_by_asset_type: Dict[str, float]
    loss_by_sector: Dict[str, float]
    var_95: Optional[float] = None
    var_99: Optional[float] = None
    cvar_95: Optional[float] = None
    cvar_99: Optional[float] = None
    var_methodology: Optional[str] = None
    trigger_signal: Optional[RiskSignalRead] = None
    scenario_assumptions: Dict[str, Any]
    asset_shocks: List[AssetShockDetail]
    simulated_at: datetime.datetime


class StressScenarioDefinition(BaseModel):
    scenario_id: str
    name: str
    description: str
    target_event_categories: List[str]
    factor_shocks: Dict[str, Any]


class StressTestRunRead(BaseModel):
    id: str
    portfolio_id: str
    trigger_signal_id: Optional[str]
    scenario_id: Optional[str] = None
    scenario_version: str = "v1.0"
    scenario_name: str
    baseline_value: float
    stressed_value: float
    total_loss: float
    loss_percentage: float
    credit_loss: float = 0.0
    market_loss: float = 0.0
    var_95: Optional[float] = None
    var_99: Optional[float] = None
    cvar_95: Optional[float] = None
    cvar_99: Optional[float] = None
    details_json: str
    assumptions_json: Optional[str] = None
    simulated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------------
# Ingestion Schemas
# -------------------------------------------------------------------------
class NormalizedArticle(BaseModel):
    source: str
    source_id: Optional[str] = None
    title: str
    raw_content: str
    url: str
    publisher: Optional[str] = None
    published_at: datetime.datetime
    fetched_at: datetime.datetime
    language: str = "en"
    metadata: Optional[Dict[str, Any]] = None
    dedup_key: str


class IngestTriggerRequest(BaseModel):
    sources: List[str] = Field(default_factory=lambda: ["gdelt", "financial_rss"], examples=[["gdelt", "financial_rss"]])
    keywords: Optional[List[str]] = Field(default=None, examples=[["antitrust", "earnings", "default"]])
    limit_per_source: int = Field(default=10, ge=1, le=50)
    run_nlp: bool = Field(default=True, description="Immediately generate risk signals for ingested articles")
    mode: str = Field(default="live", description="'live' news fetch or 'replay' historical fixtures")


class SourceHealthItem(BaseModel):
    source: str
    status: str  # 'healthy', 'rate_limited', 'degraded', 'error'
    last_fetched_at: Optional[datetime.datetime] = None
    articles_fetched_count: int = 0
    last_error: Optional[str] = None


class IngestStatusResponse(BaseModel):
    overall_status: str
    sources: List[SourceHealthItem]
    total_articles_stored: int
    total_signals_stored: int
    last_ingest_run_at: Optional[datetime.datetime] = None


class IngestSummaryResponse(BaseModel):
    batch_id: str
    mode: str
    sources_attempted: List[str]
    articles_fetched: int
    articles_persisted: int
    duplicates_skipped: int
    signals_generated: int
    errors_count: int
    details: List[str]
    started_at: datetime.datetime
    completed_at: datetime.datetime
    duration_ms: float


class ArticleListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[ArticleRead]

