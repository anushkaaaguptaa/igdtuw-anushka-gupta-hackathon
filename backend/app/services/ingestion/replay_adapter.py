import json
import os
import datetime
from pathlib import Path
from typing import List, Optional

from app.models.schemas import NormalizedArticle
from app.services.ingestion.base import (
    BaseSourceAdapter,
    canonicalize_url,
    compute_dedup_key,
    parse_datetime_utc
)
from app.core.logger import logger


class ReplayFixtureAdapter(BaseSourceAdapter):
    """
    Offline historical replay adapter reading verified historical fixtures from disk.
    Guarantees reliable, deterministic demonstration without external network dependencies.
    All articles are explicitly stamped source='replay_fixture'.
    """

    def __init__(self, fixture_path: Optional[str] = None):
        if fixture_path:
            self.fixture_file = Path(fixture_path)
        else:
            current_dir = Path(__file__).resolve().parent
            app_fixture = current_dir.parent.parent / "data" / "fixtures" / "historical_news.json"
            root_fixture = current_dir.parent.parent.parent.parent / "data" / "fixtures" / "historical_news.json"
            if root_fixture.exists():
                self.fixture_file = root_fixture
            else:
                self.fixture_file = app_fixture
        
        self.last_status: str = "healthy"
        self.last_error: Optional[str] = None
        self.last_fetched_count: int = 0

    def fetch_articles(
        self,
        limit: int = 10,
        keywords: Optional[List[str]] = None
    ) -> List[NormalizedArticle]:
        bounded_limit = max(1, min(limit, 50))
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        if not self.fixture_file.exists():
            self.last_status = "error"
            self.last_error = f"Fixture file not found: {self.fixture_file}"
            logger.error(self.last_error)
            return []

        try:
            with open(self.fixture_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            articles: List[NormalizedArticle] = []
            for item in data[:bounded_limit]:
                raw_url = item.get("url", "")
                canonical_url = canonicalize_url(raw_url)
                title = item.get("title", "").strip()
                content = item.get("raw_content", title).strip()
                pub_date = parse_datetime_utc(item.get("published_at"))
                dedup_key = compute_dedup_key(canonical_url, title, pub_date)

                articles.append(
                    NormalizedArticle(
                        source="replay_fixture",
                        source_id=item.get("source_id", f"replay_{dedup_key[:12]}"),
                        title=title,
                        raw_content=content,
                        url=canonical_url,
                        publisher=item.get("publisher", "Historical Archive"),
                        published_at=pub_date,
                        fetched_at=now_utc,
                        language=item.get("language", "en"),
                        metadata={
                            **(item.get("metadata") or {}),
                            "is_replay_fixture": True,
                            "replay_loaded_at": now_utc.isoformat()
                        },
                        dedup_key=dedup_key
                    )
                )

            self.last_status = "healthy"
            self.last_error = None
            self.last_fetched_count = len(articles)
            logger.info(f"Loaded {len(articles)} historical replay fixtures from {self.fixture_file}.")
            return articles

        except Exception as exc:
            self.last_status = "error"
            self.last_error = f"Failed to load replay fixtures: {exc}"
            logger.error(self.last_error)
            return []
