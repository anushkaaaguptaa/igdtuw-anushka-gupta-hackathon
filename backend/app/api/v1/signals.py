import json
import uuid
import datetime
import hashlib
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from app.core.database import get_db
from app.models.db_models import RiskSignal, Article, Entity, SignalEntity
from app.models.schemas import (
    RiskSignalRead,
    RiskSignalCreate,
    SignalListResponse,
    AffectedEntityRead,
    ArticleRead,
    TextAnalysisRequest,
    TextAnalysisResponse
)
from app.services.nlp.pipeline import RiskLensNLPEngine
from app.core.logger import logger

router = APIRouter(prefix="/signals", tags=["Risk Signals"])


def _format_signal_read(sig: RiskSignal) -> RiskSignalRead:
    """Helper to convert ORM RiskSignal to Pydantic RiskSignalRead with associations."""
    affected_entities = []
    for assoc in sig.entity_associations:
        if assoc.entity:
            affected_entities.append(
                AffectedEntityRead(
                    ticker=assoc.entity.ticker,
                    name=assoc.entity.name,
                    sector=assoc.entity.sector,
                    asset_class=assoc.entity.asset_class,
                    relevance_score=assoc.relevance_score,
                    is_primary_target=assoc.is_primary_target
                )
            )

    article_read = None
    if sig.article:
        article_read = ArticleRead.model_validate(sig.article)

    # Deserialize probabilities if stored
    probabilities = None
    if getattr(sig, "probabilities_json", None):
        try:
            probabilities = json.loads(sig.probabilities_json)
        except Exception:
            probabilities = None

    return RiskSignalRead(
        id=sig.id,
        article_id=sig.article_id,
        sentiment_score=sig.sentiment_score,
        sentiment_label=sig.sentiment_label,
        sentiment_probabilities=probabilities,
        event_category=sig.event_category,
        event_confidence=sig.event_confidence,
        impact_score=sig.impact_score,
        impact_rationale=sig.impact_rationale,
        evidence=sig.evidence,
        inference_mode=sig.inference_mode,
        model_version=sig.model_version,
        created_at=sig.created_at,
        article=article_read,
        affected_entities=affected_entities
    )



@router.get("", response_model=SignalListResponse)
def list_signals(
    limit: int = Query(20, ge=1, le=100, description="Number of signals to retrieve"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    min_impact: Optional[int] = Query(None, ge=1, le=10, description="Minimum impact score (1-10)"),
    max_impact: Optional[int] = Query(None, ge=1, le=10, description="Maximum impact score (1-10)"),
    category: Optional[str] = Query(None, description="Filter by event category"),
    ticker: Optional[str] = Query(None, description="Filter by affected entity ticker"),
    inference_mode: Optional[str] = Query(None, description="Filter by inference mode ('neural_live', 'mock', etc.)"),
    db: Session = Depends(get_db)
):
    """Retrieve paginated risk signals with optional filtering by impact, category, ticker, and mode."""
    query = db.query(RiskSignal).options(
        joinedload(RiskSignal.article),
        joinedload(RiskSignal.entity_associations).joinedload(SignalEntity.entity)
    )

    if min_impact is not None:
        query = query.filter(RiskSignal.impact_score >= min_impact)
    if max_impact is not None:
        query = query.filter(RiskSignal.impact_score <= max_impact)
    if category:
        query = query.filter(RiskSignal.event_category.ilike(f"%{category}%"))
    if inference_mode:
        query = query.filter(RiskSignal.inference_mode == inference_mode)
    if ticker:
        query = query.join(RiskSignal.entity_associations).filter(SignalEntity.ticker == ticker.upper())

    total = query.count()
    items_orm = query.order_by(desc(RiskSignal.created_at)).offset(offset).limit(limit).all()

    items = [_format_signal_read(sig) for sig in items_orm]
    return SignalListResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/{signal_id}", response_model=RiskSignalRead)
def get_signal(signal_id: str, db: Session = Depends(get_db)):
    """Retrieve details for a single risk signal by ID."""
    sig = db.query(RiskSignal).options(
        joinedload(RiskSignal.article),
        joinedload(RiskSignal.entity_associations).joinedload(SignalEntity.entity)
    ).filter(RiskSignal.id == signal_id).first()

    if not sig:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Risk signal with ID '{signal_id}' not found."
        )

    return _format_signal_read(sig)


@router.post("", response_model=RiskSignalRead, status_code=status.HTTP_201_CREATED)
def create_signal(signal_in: RiskSignalCreate, db: Session = Depends(get_db)):
    """Persist a new risk signal and associate it with target entities."""
    # Ensure article exists
    article = db.query(Article).filter(Article.id == signal_in.article_id).first()
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent article with ID '{signal_in.article_id}' does not exist."
        )

    sig_id = signal_in.id or f"sig_{uuid.uuid4().hex[:12]}"
    new_signal = RiskSignal(
        id=sig_id,
        article_id=signal_in.article_id,
        sentiment_score=signal_in.sentiment_score,
        sentiment_label=signal_in.sentiment_label,
        event_category=signal_in.event_category,
        event_confidence=signal_in.event_confidence,
        impact_score=signal_in.impact_score,
        impact_rationale=signal_in.impact_rationale,
        evidence=signal_in.evidence,
        probabilities_json=json.dumps(signal_in.sentiment_probabilities) if signal_in.sentiment_probabilities else None,
        inference_mode=signal_in.inference_mode,
        model_version=signal_in.model_version
    )
    db.add(new_signal)
    db.flush()

    # Link entities
    for ticker in signal_in.entity_tickers:
        entity = db.query(Entity).filter(Entity.ticker == ticker.upper()).first()
        if entity:
            assoc = SignalEntity(
                signal_id=sig_id,
                ticker=entity.ticker,
                relevance_score=1.0,
                is_primary_target=True
            )
            db.add(assoc)

    db.commit()
    db.refresh(new_signal)
    return _format_signal_read(new_signal)


@router.post("/analyze", response_model=TextAnalysisResponse)
def analyze_text(req: TextAnalysisRequest, db: Session = Depends(get_db)):
    """
    Run end-to-end NLP analysis (Sentiment, Event Taxonomy, NER Tickers, Impact Score).
    Optionally saves the raw article and structured signal directly to the database.
    """
    engine = RiskLensNLPEngine()
    result = engine.analyze(title=req.title, content=req.content or "")

    now = datetime.datetime.now(datetime.timezone.utc)
    article_url = req.url or f"https://direct-input.risklens.ai/{hashlib.sha256(req.title.encode()).hexdigest()[:16]}"
    art_id = f"art_{hashlib.sha256(article_url.encode()).hexdigest()[:16]}"
    sig_id = f"sig_{uuid.uuid4().hex[:12]}"

    article_read = None

    if req.save_to_db:
        # Check if article already exists
        article = db.query(Article).filter(Article.url == article_url).first()
        if not article:
            article = Article(
                id=art_id,
                source=req.source,
                title=req.title,
                url=article_url,
                published_at=now,
                raw_content=req.content or req.title,
                language="en"
            )
            db.add(article)
            db.flush()
        else:
            art_id = article.id

        article_read = ArticleRead.model_validate(article)

        # Save entities
        for ent in result.affected_entities:
            existing_ent = db.query(Entity).filter(Entity.ticker == ent.ticker).first()
            if not existing_ent:
                new_ent = Entity(
                    ticker=ent.ticker,
                    name=ent.name,
                    sector=ent.sector,
                    asset_class=ent.asset_class
                )
                db.add(new_ent)
        db.flush()

        # Save risk signal
        new_signal = RiskSignal(
            id=sig_id,
            article_id=art_id,
            sentiment_score=result.sentiment_score,
            sentiment_label=result.sentiment_label,
            event_category=result.event_category,
            event_confidence=result.event_confidence,
            impact_score=result.impact_score,
            impact_rationale=result.impact_rationale,
            evidence=result.evidence,
            probabilities_json=json.dumps(result.sentiment_probabilities),
            inference_mode=result.inference_mode,
            model_version=result.model_version,
            created_at=now
        )
        db.add(new_signal)
        db.flush()

        for ent in result.affected_entities:
            assoc = SignalEntity(
                signal_id=sig_id,
                ticker=ent.ticker,
                relevance_score=ent.relevance_score,
                is_primary_target=ent.is_primary_target
            )
            db.add(assoc)

        db.commit()
        db.refresh(new_signal)
        signal_read = _format_signal_read(new_signal)
    else:
        # Ephemeral / Transient analysis without DB commit
        affected_reads = [
            AffectedEntityRead(
                ticker=ent.ticker,
                name=ent.name,
                sector=ent.sector,
                asset_class=ent.asset_class,
                relevance_score=ent.relevance_score,
                is_primary_target=ent.is_primary_target
            )
            for ent in result.affected_entities
        ]
        signal_read = RiskSignalRead(
            id=f"preview_{sig_id}",
            article_id=art_id,
            sentiment_score=result.sentiment_score,
            sentiment_label=result.sentiment_label,
            sentiment_probabilities=result.sentiment_probabilities,
            event_category=result.event_category,
            event_confidence=result.event_confidence,
            impact_score=result.impact_score,
            impact_rationale=result.impact_rationale,
            evidence=result.evidence,
            inference_mode=result.inference_mode,
            model_version=result.model_version,
            created_at=now,
            article=ArticleRead(
                id=art_id,
                source=req.source,
                title=req.title,
                url=article_url,
                published_at=now,
                raw_content=req.content or req.title,
                language="en",
                created_at=now
            ),
            affected_entities=affected_reads
        )

    return TextAnalysisResponse(
        signal=signal_read,
        processing_status=result.processing_status,
        execution_time_ms=result.execution_time_ms
    )

