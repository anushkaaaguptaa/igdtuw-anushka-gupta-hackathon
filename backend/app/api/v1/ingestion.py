from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.models.db_models import Article
from app.models.schemas import (
    IngestTriggerRequest,
    IngestSummaryResponse,
    IngestStatusResponse,
    ArticleListResponse,
    ArticleRead
)
from app.services.ingestion.service import IngestionCoordinator
from app.core.logger import logger

router = APIRouter(prefix="/ingest", tags=["Data Ingestion"])

# Global coordinator instance
coordinator = IngestionCoordinator()


@router.post("/trigger", response_model=IngestSummaryResponse, status_code=status.HTTP_200_OK)
def trigger_ingestion(
    req: IngestTriggerRequest,
    db: Session = Depends(get_db)
):
    """
    Trigger a bounded news ingestion run across configured sources (GDELT, Financial RSS, Replay).
    Deduplicates incoming articles and automatically generates risk signals via the NLP engine.
    """
    summary = coordinator.run_ingestion(
        db=db,
        sources=req.sources,
        keywords=req.keywords,
        limit_per_source=req.limit_per_source,
        run_nlp=req.run_nlp,
        mode=req.mode
    )
    return summary


@router.get("/status", response_model=IngestStatusResponse)
def get_ingestion_status(db: Session = Depends(get_db)):
    """Retrieve operational health, error telemetry, and record counts for all ingestion providers."""
    return coordinator.get_ingest_status(db=db)


@router.get("/articles", response_model=ArticleListResponse)
def list_ingested_articles(
    limit: int = Query(20, ge=1, le=100, description="Number of articles to retrieve"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    source: Optional[str] = Query(None, description="Filter by source ('gdelt', 'financial_rss', 'replay_fixture')"),
    status: Optional[str] = Query(None, description="Filter by status ('processed', 'pending_nlp', 'error')"),
    search: Optional[str] = Query(None, description="Keyword search in title"),
    db: Session = Depends(get_db)
):
    """List raw ingested articles with pagination, source filtering, and text search."""
    query = db.query(Article)

    if source:
        query = query.filter(Article.source == source)
    if status:
        query = query.filter(Article.ingestion_status == status)
    if search:
        query = query.filter(Article.title.ilike(f"%{search}%"))

    total = query.count()
    articles_orm = query.order_by(desc(Article.published_at)).offset(offset).limit(limit).all()

    items = [ArticleRead.model_validate(art) for art in articles_orm]
    return ArticleListResponse(total=total, limit=limit, offset=offset, items=items)
