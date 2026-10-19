/**
 * RiskLens AI - TypeScript API Type Definitions
 * Strictly mirrored from FastAPI Pydantic schemas in backend/app/models/schemas.py.
 */

// ---------------------------------------------------------------------------
// System Health
// ---------------------------------------------------------------------------
export interface HealthResponse {
  status: 'healthy' | 'degraded' | string;
  app_name: string;
  version: string;
  environment: string;
  database_status: string;
  inference_mode: string;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Article & Source Schemas
// ---------------------------------------------------------------------------
export interface ArticleRead {
  id: string;
  source: string;
  source_id?: string | null;
  title: string;
  url: string;
  publisher?: string | null;
  published_at: string;
  fetched_at?: string | null;
  raw_content: string;
  language: string;
  metadata_json?: string | null;
  ingestion_status: string;
  error_message?: string | null;
  created_at: string;
}

export interface ArticleListResponse {
  total: number;
  limit: number;
  offset: number;
  items: ArticleRead[];
}

// ---------------------------------------------------------------------------
// Entity Schemas
// ---------------------------------------------------------------------------
export interface EntityRead {
  ticker: string;
  name: string;
  sector: string;
  asset_class: string;
}

export interface AffectedEntityRead {
  ticker: string;
  name: string;
  sector: string;
  asset_class: string;
  relevance_score: number;
  is_primary_target: boolean;
}

// ---------------------------------------------------------------------------
// Risk Signals Schemas
// ---------------------------------------------------------------------------
export interface SentimentProbabilities {
  positive?: number;
  neutral?: number;
  negative?: number;
  [key: string]: number | undefined;
}

export interface RiskSignalRead {
  id: string;
  article_id: string;
  sentiment_score: number; // FinBERT score bounded [-1.0, +1.0]
  sentiment_label: 'positive' | 'neutral' | 'negative' | string;
  sentiment_probabilities?: SentimentProbabilities | null;
  event_category: string;
  event_confidence: number;
  impact_score: number; // Deterministic scale 1-10
  impact_rationale: string;
  evidence?: string | null;
  inference_mode: string; // neural_live, lexicon_fallback, or mock
  model_version: string;
  created_at: string;
  article?: ArticleRead | null;
  affected_entities: AffectedEntityRead[];
}

export interface SignalListResponse {
  total: number;
  limit: number;
  offset: number;
  items: RiskSignalRead[];
}

export interface TextAnalysisRequest {
  title: string;
  content?: string;
  save_to_db?: boolean;
  source?: string;
  url?: string;
}

export interface TextAnalysisResponse {
  signal: RiskSignalRead;
  processing_status: string;
  execution_time_ms: number;
}

// ---------------------------------------------------------------------------
// Portfolio & Asset Schemas
// ---------------------------------------------------------------------------
export interface AssetAttributes {
  // Loans
  ead?: number;
  pd?: number;
  lgd?: number;
  maturity_years?: number;
  accounting?: string;
  // Bonds
  modified_duration?: number;
  convexity?: number;
  credit_spread_bps?: number;
  coupon?: number;
  rating?: string;
  // Derivatives
  delta?: number;
  underlying?: string;
  underlying_notional?: number;
  strike?: number;
  maturity_days?: number;
  hedge_type?: string;
  // Equities
  market_cap?: string;
  [key: string]: unknown;
}

export interface PortfolioAssetRead {
  id: string;
  portfolio_id: string;
  ticker: string;
  asset_type: 'equity' | 'corporate_loan' | 'government_bond' | 'corporate_bond' | 'derivative' | string;
  issuer?: string | null;
  currency: string;
  shares: number;
  purchase_price: number;
  current_price: number;
  notional?: number | null;
  sector_beta: number;
  attributes?: AssetAttributes | null;
  entity?: EntityRead | null;
  market_value: number;
  weight: number;
}

export interface PortfolioRead {
  id: string;
  name: string;
  description?: string | null;
  base_currency: string;
  initial_value: number;
  created_at: string;
  assets: PortfolioAssetRead[];
  current_total_value: number;
}

export interface SectorExposureItem {
  sector: string;
  value: number;
  weight: number;
}

export interface PortfolioExposureRead {
  portfolio_id: string;
  portfolio_name: string;
  total_value: number;
  sector_exposures: SectorExposureItem[];
  holdings_count: number;
}

// ---------------------------------------------------------------------------
// Stress Testing Schemas
// ---------------------------------------------------------------------------
export interface AssetShockDetail {
  ticker: string;
  name: string;
  asset_type: string;
  sector: string;
  currency: string;
  shares: number;
  notional?: number | null;
  baseline_price: number;
  stressed_price: number;
  pct_change: number;
  baseline_value: number;
  stressed_value: number;
  asset_loss: number; // Negative value indicates hedge gain
  credit_loss: number;
  market_loss: number;
  valuation_methodology: string;
  shock_applied: string;
}

export interface ScenarioFactorShocks {
  equity_market_shock?: number;
  rate_shock_bps?: number;
  credit_spread_bps?: number;
  loan_pd_multiplier?: number;
  loan_lgd_add?: number;
  target_equity_haircut?: number;
  sector_equity_shocks?: Record<string, number>;
  notes?: string;
  [key: string]: unknown;
}

export interface StressScenarioDefinition {
  scenario_id: string;
  name: string;
  description: string;
  target_event_categories: string[];
  factor_shocks: ScenarioFactorShocks;
}

export interface StressTestSimulationRequest {
  portfolio_id: string;
  signal_id?: string | null;
  scenario_id?: string | null;
  scenario_name?: string | null;
  severity_multiplier?: number;
  var_simulations?: number | null;
  allow_duplicate?: boolean;
}

export interface StressTestSimulationResponse {
  simulation_id: string;
  portfolio_id: string;
  scenario_id: string;
  scenario_name: string;
  scenario_version: string;
  baseline_value: number;
  stressed_value: number;
  total_loss: number;
  loss_percentage: number;
  credit_loss: number;
  market_loss: number;
  loss_by_asset_type: Record<string, number>;
  loss_by_sector: Record<string, number>;
  var_95?: number | null;
  var_99?: number | null;
  cvar_95?: number | null;
  cvar_99?: number | null;
  var_methodology?: string | null;
  trigger_signal?: RiskSignalRead | null;
  scenario_assumptions: Record<string, unknown>;
  asset_shocks: AssetShockDetail[];
  simulated_at: string;
}

export interface StressTestRunRead {
  id: string;
  portfolio_id: string;
  trigger_signal_id?: string | null;
  scenario_id?: string | null;
  scenario_version: string;
  scenario_name: string;
  baseline_value: number;
  stressed_value: number;
  total_loss: number;
  loss_percentage: number;
  credit_loss: number;
  market_loss: number;
  var_95?: number | null;
  var_99?: number | null;
  cvar_95?: number | null;
  cvar_99?: number | null;
  details_json: string;
  assumptions_json?: string | null;
  simulated_at: string;
}

// ---------------------------------------------------------------------------
// Ingestion Schemas
// ---------------------------------------------------------------------------
export interface IngestTriggerRequest {
  sources?: string[];
  keywords?: string[] | null;
  limit_per_source?: number;
  run_nlp?: boolean;
  mode?: 'live' | 'replay';
}

export interface IngestSummaryResponse {
  batch_id: string;
  mode: string;
  sources_attempted: string[];
  articles_fetched: number;
  articles_persisted: number;
  duplicates_skipped: number;
  signals_generated: number;
  errors_count: number;
  details: string[];
  started_at: string;
  completed_at: string;
  duration_ms: number;
}

export interface SourceHealthItem {
  source: string;
  status: 'healthy' | 'rate_limited' | 'degraded' | 'error' | string;
  last_fetched_at?: string | null;
  articles_fetched_count: number;
  last_error?: string | null;
}

export interface IngestStatusResponse {
  overall_status: string;
  sources: SourceHealthItem[];
  total_articles_stored: number;
  total_signals_stored: number;
  last_ingest_run_at?: string | null;
}
