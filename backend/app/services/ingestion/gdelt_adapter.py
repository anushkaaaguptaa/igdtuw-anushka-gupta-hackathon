import time
import httpx
import datetime
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


class GDELTAdapter(BaseSourceAdapter):
    """
    Ingestion adapter for GDELT 2.0 Doc API (Global Database of Events, Language, and Tone).
    Enforces rate-limit pacing (1 request per 5.5s) and handles HTTP 429 rate limit responses gracefully.
    """

    _last_request_time: float = 0.0

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        client: Optional[httpx.Client] = None
    ):
        self.base_url = base_url or settings.GDELT_BASE_URL
        self.timeout = timeout or settings.INGESTION_REQUEST_TIMEOUT
        self.client = client
        self.last_status: str = "initialized"
        self.last_error: Optional[str] = None
        self.last_fetched_count: int = 0

    def _wait_for_rate_limit(self) -> None:
        """Enforces client-side rate limit spacing to respect GDELT's 5-second interval rule."""
        elapsed = time.time() - GDELTAdapter._last_request_time
        min_spacing = settings.GDELT_MIN_INTERVAL_SECONDS
        if elapsed < min_spacing:
            sleep_duration = min_spacing - elapsed
            logger.info(f"GDELT rate limit spacer: pausing for {sleep_duration:.2f}s...")
            time.sleep(sleep_duration)
        GDELTAdapter._last_request_time = time.time()

    def fetch_articles(
        self,
        limit: int = 10,
        keywords: Optional[List[str]] = None
    ) -> List[NormalizedArticle]:
        bounded_limit = max(1, min(limit, 50))
        kw_list = keywords or ["finance", "antitrust", "earnings", "stocks"]
        query_str = f"({' OR '.join(kw_list)}) sourcelang:english"

        params = {
            "query": query_str,
            "mode": "artlist",
            "maxrecords": str(bounded_limit),
            "format": "json"
        }

        self._wait_for_rate_limit()

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) RiskLensAI/0.1.0"
        }

        try:
            http_client = self.client or httpx.Client(timeout=self.timeout, headers=headers)
            close_client = self.client is None

            try:
                logger.info(f"Fetching up to {bounded_limit} articles from GDELT...")
                resp = http_client.get(self.base_url, params=params)
            finally:
                if close_client:
                    http_client.close()

            # Handle rate limiting (HTTP 429 or plain text warning)
            if resp.status_code == 429 or "Please limit requests" in resp.text:
                self.last_status = "rate_limited"
                self.last_error = "GDELT rate limit exceeded (HTTP 429). Retry after 5s."
                logger.warning(self.last_error)
                return []

            if resp.status_code != 200:
                self.last_status = "error"
                self.last_error = f"GDELT returned HTTP {resp.status_code}: {resp.text[:120]}"
                logger.error(self.last_error)
                return []

            try:
                data = resp.json()
            except Exception as json_err:
                self.last_status = "error"
                self.last_error = f"Malformed GDELT JSON response: {json_err}"
                logger.warning(f"{self.last_error}. Raw body: {resp.text[:150]}")
                return []

            raw_articles = data.get("articles", [])
            normalized_list: List[NormalizedArticle] = []
            now_utc = datetime.datetime.now(datetime.timezone.utc)

            for item in raw_articles:
                raw_url = item.get("url", "")
                canonical_url = canonicalize_url(raw_url)
                if not canonical_url:
                    continue

                raw_title = item.get("title", "").strip()
                if not raw_title:
                    continue

                pub_date = parse_datetime_utc(item.get("seendate"))
                dedup_key = compute_dedup_key(canonical_url, raw_title, pub_date)
                domain = item.get("domain", "Unknown GDELT Publisher")

                normalized_list.append(
                    NormalizedArticle(
                        source="gdelt",
                        source_id=f"gdelt_{dedup_key[:12]}",
                        title=raw_title,
                        raw_content=raw_title,  # GDELT artlist mode delivers headline/title context
                        url=canonical_url,
                        publisher=domain,
                        published_at=pub_date,
                        fetched_at=now_utc,
                        language=item.get("language", "en"),
                        metadata={
                            "source_country": item.get("sourcecountry"),
                            "gdelt_domain": domain
                        },
                        dedup_key=dedup_key
                    )
                )

            self.last_status = "healthy"
            self.last_error = None
            self.last_fetched_count = len(normalized_list)
            logger.info(f"Successfully normalized {len(normalized_list)} articles from GDELT.")
            return normalized_list

        except httpx.TimeoutException:
            self.last_status = "degraded"
            self.last_error = f"GDELT request timed out after {self.timeout}s."
            logger.warning(self.last_error)
            return []
        except Exception as exc:
            self.last_status = "error"
            self.last_error = f"Unexpected GDELT ingestion error: {exc}"
            logger.error(self.last_error)
            return []
