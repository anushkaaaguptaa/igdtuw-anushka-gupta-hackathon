import json
import time
import uuid
import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.db_models import Article, RiskSignal, Entity, SignalEntity
from app.models.schemas import (
    NormalizedArticle,
    IngestSummaryResponse,
    SourceHealthItem,
    IngestStatusResponse
)
from app.services.ingestion.base import BaseSourceAdapter
from app.services.ingestion.gdelt_adapter import GDELTAdapter
from app.services.ingestion.rss_adapter import FinancialRSSAdapter
from app.services.ingestion.replay_adapter import ReplayFixtureAdapter
from app.services.nlp.pipeline import RiskLensNLPEngine
from app.core.logger import logger


class IngestionCoordinator:
    """
    Orchestrates news ingestion from independent sources (GDELT, RSS, Replay),
    enforces deduplication, persists raw articles, and triggers NLP signal extraction.
    """

    _last_run_at: Optional[datetime.datetime] = None

    def __init__(
        self,
        gdelt_adapter: Optional[GDELTAdapter] = None,
        rss_adapter: Optional[FinancialRSSAdapter] = None,
        replay_adapter: Optional[ReplayFixtureAdapter] = None,
        nlp_engine: Optional[RiskLensNLPEngine] = None
    ):
        self.gdelt = gdelt_adapter or GDELTAdapter()
        self.rss = rss_adapter or FinancialRSSAdapter()
        self.replay = replay_adapter or ReplayFixtureAdapter()
        self.nlp_engine = nlp_engine or RiskLensNLPEngine()

    def get_source_health(self) -> List[SourceHealthItem]:
        """Returns health status, last fetch time, and error telemetry for each source adapter."""
        return [
            SourceHealthItem(
                source="gdelt",
                status=self.gdelt.last_status,
                last_fetched_at=IngestionCoordinator._last_run_at,
                articles_fetched_count=self.gdelt.last_fetched_count,
                last_error=self.gdelt.last_error
            ),
            SourceHealthItem(
                source="financial_rss",
                status=self.rss.last_status,
                last_fetched_at=IngestionCoordinator._last_run_at,
                articles_fetched_count=self.rss.last_fetched_count,
                last_error=self.rss.last_error
            ),
            SourceHealthItem(
                source="replay_fixture",
                status=self.replay.last_status,
                last_fetched_at=IngestionCoordinator._last_run_at,
                articles_fetched_count=self.replay.last_fetched_count,
                last_error=self.replay.last_error
            )
        ]

    def get_ingest_status(self, db: Session) -> IngestStatusResponse:
        """Returns overall ingestion diagnostics, database counts, and source health."""
        sources = self.get_source_health()
        
        # Overall status evaluation
        if any(s.status == "healthy" for s in sources):
            overall = "operational"
        elif any(s.status == "rate_limited" for s in sources):
            overall = "degraded_rate_limit"
        else:
            overall = "degraded"

        total_articles = db.query(func.count(Article.id)).scalar() or 0
        total_signals = db.query(func.count(RiskSignal.id)).scalar() or 0

        return IngestStatusResponse(
            overall_status=overall,
            sources=sources,
            total_articles_stored=total_articles,
            total_signals_stored=total_signals,
            last_ingest_run_at=IngestionCoordinator._last_run_at
        )

    def run_ingestion(
        self,
        db: Session,
        sources: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        limit_per_source: int = 10,
        run_nlp: bool = True,
        mode: str = "live"
    ) -> IngestSummaryResponse:
        start_time = time.perf_counter()
        batch_id = f"batch_{uuid.uuid4().hex[:10]}"
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        IngestionCoordinator._last_run_at = now_utc

        requested_sources = sources or (["replay_fixture"] if mode == "replay" else ["gdelt", "financial_rss"])
        details: List[str] = []
        collected_articles: List[NormalizedArticle] = []

        logger.info(f"Initiating ingestion batch {batch_id} (mode={mode}, sources={requested_sources})...")

        # 1. Fetch articles from requested providers
        if mode == "replay" or "replay_fixture" in requested_sources:
            try:
                rep_articles = self.replay.fetch_articles(limit=limit_per_source, keywords=keywords)
                collected_articles.extend(rep_articles)
                details.append(f"Replay Fixtures: fetched {len(rep_articles)} historical items.")
            except Exception as e:
                details.append(f"Replay Fixtures failed: {e}")

        if mode == "live":
            if "gdelt" in requested_sources:
                try:
                    gdelt_articles = self.gdelt.fetch_articles(limit=limit_per_source, keywords=keywords)
                    collected_articles.extend(gdelt_articles)
                    details.append(f"GDELT: fetched {len(gdelt_articles)} items.")
                except Exception as e:
                    details.append(f"GDELT exception: {e}")

            if "financial_rss" in requested_sources:
                try:
                    rss_articles = self.rss.fetch_articles(limit=limit_per_source, keywords=keywords)
                    collected_articles.extend(rss_articles)
                    details.append(f"Financial RSS: fetched {len(rss_articles)} items.")
                except Exception as e:
                    details.append(f"Financial RSS exception: {e}")

        articles_fetched = len(collected_articles)
        articles_persisted = 0
        duplicates_skipped = 0
        signals_generated = 0
        errors_count = 0

        # 2. Normalize, Deduplicate, Persist, and Trigger NLP
        seen_batch_urls = set()

        for a in collected_articles:
            # Check within-batch duplication
            if a.url in seen_batch_urls:
                duplicates_skipped += 1
                continue
            seen_batch_urls.add(a.url)

            # Check database for pre-existing article by dedup_key (id) or canonical url
            existing_art = db.query(Article).filter(
                (Article.id == a.dedup_key) | (Article.url == a.url)
            ).first()

            if existing_art:
                duplicates_skipped += 1
                continue

            # Create and persist new raw article
            new_art = Article(
                id=a.dedup_key,
                source=a.source,
                source_id=a.source_id,
                title=a.title,
                url=a.url,
                publisher=a.publisher,
                published_at=a.published_at,
                fetched_at=a.fetched_at,
                raw_content=a.raw_content,
                language=a.language,
                metadata_json=json.dumps(a.metadata) if a.metadata else None,
                ingestion_status="pending_nlp" if run_nlp else "raw_only",
                created_at=now_utc
            )
            db.add(new_art)
            db.flush()
            articles_persisted += 1

            # Trigger NLP Pipeline if requested
            if run_nlp:
                try:
                    nlp_res = self.nlp_engine.analyze(title=a.title, content=a.raw_content)

                    # Ensure entities exist in entities table
                    for ent in nlp_res.affected_entities:
                        db_ent = db.query(Entity).filter(Entity.ticker == ent.ticker).first()
                        if not db_ent:
                            db.add(
                                Entity(
                                    ticker=ent.ticker,
                                    name=ent.name,
                                    sector=ent.sector,
                                    asset_class=ent.asset_class
                                )
                            )
                    db.flush()

                    # Label inference mode cleanly: if from replay fixture, preserve synthetic tag
                    inference_mode = "synthetic" if a.source == "replay_fixture" else nlp_res.inference_mode

                    sig_id = f"sig_{uuid.uuid4().hex[:12]}"
                    new_sig = RiskSignal(
                        id=sig_id,
                        article_id=new_art.id,
                        sentiment_score=nlp_res.sentiment_score,
                        sentiment_label=nlp_res.sentiment_label,
                        event_category=nlp_res.event_category,
                        event_confidence=nlp_res.event_confidence,
                        impact_score=nlp_res.impact_score,
                        impact_rationale=nlp_res.impact_rationale,
                        evidence=nlp_res.evidence,
                        probabilities_json=json.dumps(nlp_res.sentiment_probabilities),
                        inference_mode=inference_mode,
                        model_version=nlp_res.model_version,
                        created_at=now_utc
                    )
                    db.add(new_sig)
                    db.flush()

                    # Associate entities
                    for ent in nlp_res.affected_entities:
                        assoc = SignalEntity(
                            signal_id=sig_id,
                            ticker=ent.ticker,
                            relevance_score=ent.relevance_score,
                            is_primary_target=ent.is_primary_target
                        )
                        db.add(assoc)

                    new_art.ingestion_status = "processed"
                    signals_generated += 1

                except Exception as nlp_exc:
                    logger.error(f"Failed NLP extraction for article '{a.title}': {nlp_exc}")
                    new_art.ingestion_status = "nlp_error"
                    new_art.error_message = str(nlp_exc)
                    errors_count += 1

        db.commit()
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            f"Batch {batch_id} finished in {duration_ms}ms: {articles_persisted} stored, "
            f"{duplicates_skipped} duplicates skipped, {signals_generated} signals generated."
        )

        return IngestSummaryResponse(
            batch_id=batch_id,
            mode=mode,
            sources_attempted=requested_sources,
            articles_fetched=articles_fetched,
            articles_persisted=articles_persisted,
            duplicates_skipped=duplicates_skipped,
            signals_generated=signals_generated,
            errors_count=errors_count,
            details=details,
            started_at=now_utc,
            completed_at=datetime.datetime.now(datetime.timezone.utc),
            duration_ms=duration_ms
        )
