import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.config import settings
from app.models.schemas import HealthResponse
from app.core.logger import logger

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def get_health_status(db: Session = Depends(get_db)):
    """System health check endpoint verifying database connectivity and configuration."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error(f"Database health check failed: {exc}")
        db_status = f"unhealthy: {str(exc)}"

    # Determine truthful active NLP inference capability
    active_mode = settings.INFERENCE_MODE
    try:
        from app.services.nlp.sentiment import FinBertSentimentModel
        finbert = FinBertSentimentModel.get_instance()
        if finbert._load_successful:
            active_mode = "neural_live"
        elif finbert._load_attempted and not finbert._load_successful:
            active_mode = "lexicon_fallback"
        else:
            # Check availability of neural model dependencies without triggering eager download
            import torch
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            active_mode = "neural_live"
    except Exception:
        active_mode = "lexicon_fallback"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        app_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        database_status=db_status,
        inference_mode=active_mode,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
