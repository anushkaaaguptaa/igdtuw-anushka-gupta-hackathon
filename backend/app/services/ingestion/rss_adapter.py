import re
import html
import httpx
import datetime
import feedparser
from typing import List, Optional, Dict, Any

from app.config import settings
from app.models.schemas import NormalizedArticle
from app.services.ingestion.base import (
    BaseSourceAdapter,
    canonicalize_url,
    compute_dedup_key,
    parse_datetime_utc
)
from app.core.logger import logger


def _strip_html_tags(text: str) -> str:
    """Removes HTML markup and unescapes entities."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = html.unescape(clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


class FinancialRSSAdapter(BaseSourceAdapter):
    """
    Ingestion adapter for financial news RSS and Atom feeds.
    Parses feeds defensively, extracts article descriptions, and normalizes timestamps.
    """

    def __init__(
        self,
        feed_urls: Optional[List[str]] = None,
        timeout: Optional[float] = None,
        client: Optional[httpx.Client] = None
    ):
        self.feed_urls = feed_urls or settings.DEFAULT_FINANCIAL_RSS_FEEDS
        self.timeout = timeout or settings.INGESTION_REQUEST_TIMEOUT
        self.client = client
        self.last_status: str = "initialized"
        self.last_error: Optional[str] = None
        self.last_fetched_count: int = 0

    def fetch_articles(
        self,
        limit: int = 10,
        keywords: Optional[List[str]] = None
    ) -> List[NormalizedArticle]:
        bounded_limit = max(1, min(limit, 50))
        articles: List[NormalizedArticle] = []
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) RiskLensAI/0.1.0"
        }

        http_client = self.client or httpx.Client(timeout=self.timeout, headers=headers, follow_redirects=True)
        close_client = self.client is None

        successful_feeds = 0
        feed_errors = []

        try:
            for feed_url in self.feed_urls:
                if len(articles) >= bounded_limit:
                    break

                try:
                    logger.info(f"Fetching RSS feed: {feed_url}...")
                    resp = http_client.get(feed_url)
                    if resp.status_code != 200:
                        feed_errors.append(f"{feed_url} -> HTTP {resp.status_code}")
                        continue

                    parsed_feed = feedparser.parse(resp.text)
                    if parsed_feed.bozo and not parsed_feed.entries:
                        feed_errors.append(f"{feed_url} -> XML parse error: {parsed_feed.bozo_exception}")
                        continue

                    feed_title = parsed_feed.feed.get("title", "Financial News Feed")
                    successful_feeds += 1

                    for entry in parsed_feed.entries:
                        if len(articles) >= bounded_limit:
                            break

                        raw_link = entry.get("link", "")
                        canonical_url = canonicalize_url(raw_link)
                        if not canonical_url:
                            continue

                        raw_title = _strip_html_tags(entry.get("title", ""))
                        if not raw_title:
                            continue

                        # Extract description / summary
                        raw_desc = entry.get("summary", "") or entry.get("description", "")
                        clean_desc = _strip_html_tags(raw_desc)
                        content = f"{raw_title}. {clean_desc}".strip() if clean_desc else raw_title

                        # Parse timestamp
                        raw_date = entry.get("published_parsed") or entry.get("updated_parsed") or entry.get("published")
                        pub_date = parse_datetime_utc(raw_date)

                        publisher = entry.get("source", {}).get("title") if isinstance(entry.get("source"), dict) else None
                        if not publisher:
                            publisher = entry.get("author") or feed_title

                        dedup_key = compute_dedup_key(canonical_url, raw_title, pub_date)
                        guid = entry.get("id") or entry.get("guid") or f"rss_{dedup_key[:12]}"

                        articles.append(
                            NormalizedArticle(
                                source="financial_rss",
                                source_id=str(guid),
                                title=raw_title,
                                raw_content=content,
                                url=canonical_url,
                                publisher=str(publisher),
                                published_at=pub_date,
                                fetched_at=now_utc,
                                language="en",
                                metadata={
                                    "feed_url": feed_url,
                                    "feed_title": feed_title
                                },
                                dedup_key=dedup_key
                            )
                        )

                except httpx.TimeoutException:
                    feed_errors.append(f"{feed_url} -> Request timeout ({self.timeout}s)")
                except Exception as feed_exc:
                    feed_errors.append(f"{feed_url} -> Exception: {feed_exc}")

        finally:
            if close_client:
                http_client.close()

        if successful_feeds > 0:
            self.last_status = "healthy"
            self.last_error = "; ".join(feed_errors) if feed_errors else None
        elif feed_errors:
            self.last_status = "error"
            self.last_error = "; ".join(feed_errors)
        else:
            self.last_status = "healthy"

        self.last_fetched_count = len(articles)
        logger.info(f"Financial RSS adapter collected {len(articles)} normalized articles from {successful_feeds} feeds.")
        return articles
