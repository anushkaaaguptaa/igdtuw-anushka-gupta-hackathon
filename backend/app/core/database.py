from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings
from app.core.logger import logger

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=(settings.LOG_LEVEL.upper() == "DEBUG")
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for yielding database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables according to declared models."""
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    
    # Safe lightweight SQLite migration for added columns
    from sqlalchemy import text
    with engine.connect() as conn:
        # risk_signals migration
        try:
            conn.execute(text("ALTER TABLE risk_signals ADD COLUMN probabilities_json TEXT"))
            conn.commit()
        except Exception:
            pass

        # raw_articles migrations
        raw_article_cols = [
            ("publisher", "TEXT"),
            ("source_id", "TEXT"),
            ("fetched_at", "TIMESTAMP"),
            ("metadata_json", "TEXT"),
            ("ingestion_status", "TEXT DEFAULT 'pending_nlp'"),
            ("error_message", "TEXT"),
        ]
        for col_name, col_type in raw_article_cols:
            try:
                conn.execute(text(f"ALTER TABLE raw_articles ADD COLUMN {col_name} {col_type}"))
                conn.commit()
            except Exception:
                pass
        # portfolio_assets migrations
        portfolio_asset_cols = [
            ("asset_type", "TEXT DEFAULT 'equity'"),
            ("issuer", "TEXT"),
            ("currency", "TEXT DEFAULT 'USD'"),
            ("notional", "REAL"),
            ("attributes_json", "TEXT"),
        ]
        for col_name, col_type in portfolio_asset_cols:
            try:
                conn.execute(text(f"ALTER TABLE portfolio_assets ADD COLUMN {col_name} {col_type}"))
                conn.commit()
            except Exception:
                pass

        # stress_test_runs migrations
        stress_run_cols = [
            ("scenario_id", "TEXT"),
            ("scenario_version", "TEXT DEFAULT 'v1.0'"),
            ("credit_loss", "REAL DEFAULT 0.0"),
            ("market_loss", "REAL DEFAULT 0.0"),
            ("var_95", "REAL"),
            ("var_99", "REAL"),
            ("cvar_95", "REAL"),
            ("cvar_99", "REAL"),
            ("assumptions_json", "TEXT"),
        ]
        for col_name, col_type in stress_run_cols:
            try:
                conn.execute(text(f"ALTER TABLE stress_test_runs ADD COLUMN {col_name} {col_type}"))
                conn.commit()
            except Exception:
                pass
            
    logger.info("Database tables initialized successfully.")
