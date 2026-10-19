from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    PROJECT_NAME: str = "RiskLens AI"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment
    ENVIRONMENT: str = Field(default="development", description="development, testing, production")
    LOG_LEVEL: str = Field(default="INFO", description="DEBUG, INFO, WARNING, ERROR")
    
    # Database
    DATABASE_URL: str = Field(default="sqlite:///./risklens.db", description="Database connection string")
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://risklens-ai-snowy.vercel.app",
    ]
    
    # Model & Ingestion configuration
    INFERENCE_MODE: str = Field(
        default="neural_live",
        description="Active inference mode: 'neural_live', 'lexicon_fallback', or 'mock'"
    )
    DEFAULT_MODEL_VERSION: str = "ProsusAI/finbert+keyword-taxonomy-v1"
    
    # Ingestion configuration
    GDELT_BASE_URL: str = Field(
        default="https://api.gdeltproject.org/api/v2/doc/doc",
        description="GDELT 2.0 Doc API base URL"
    )
    DEFAULT_FINANCIAL_RSS_FEEDS: List[str] = [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=NVDA,AAPL,MSFT,GOOGL,AMZN,JPM",
        "https://feeds.content.dowjones.io/public/rss/mw_topstories"
    ]
    INGESTION_REQUEST_TIMEOUT: float = 12.0
    INGESTION_MAX_RETRIES: int = 2
    INGESTION_BACKOFF_FACTOR: float = 1.5
    GDELT_MIN_INTERVAL_SECONDS: float = 5.5
    DEFAULT_INGESTION_LIMIT: int = 10
    ENABLE_AUTO_NLP_INGESTION: bool = True
    
    # Stress Testing Configuration
    AUTO_TRIGGER_IMPACT_THRESHOLD: int = Field(default=7, description="Signals with impact_score > threshold trigger automatic portfolio stress simulations")
    ENABLE_AUTO_STRESS_TEST: bool = Field(default=True, description="Automatically run stress tests on portfolios for high-impact signals")
    DEFAULT_VAR_SIMULATION_DRAWS: int = Field(default=1000, ge=100, le=10000, description="Default Monte Carlo simulation draws for VaR/CVaR")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
