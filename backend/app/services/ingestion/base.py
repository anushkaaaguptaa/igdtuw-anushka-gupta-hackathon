import re
import hashlib
import datetime
from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import email.utils

from app.models.schemas import NormalizedArticle
from app.core.logger import logger


def canonicalize_url(url: str) -> str:
    """
    Cleans and canonicalizes a URL by stripping analytics query tracking parameters
    (utm_*, ref, fbclid, etc.), removing URL fragments, and normalizing casing.
    """
    if not url or not url.strip():
        return ""

    try:
        parsed = urlparse(url.strip())
        # Lowercase scheme and domain
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Filter out tracking query parameters
        tracking_prefixes = {"utm_", "fbclid", "gclid", "ref", "mc_cid", "mc_eid", "_ga"}
        clean_query = []
        if parsed.query:
            for k, v in parse_qsl(parsed.query, keep_blank_values=False):
                k_lower = k.lower()
                if not any(k_lower.startswith(p) for p in tracking_prefixes):
                    clean_query.append((k, v))

        query_str = urlencode(clean_query)
        # Strip trailing slash from path (unless it's just '/')
        path = parsed.path.rstrip("/") if len(parsed.path) > 1 else parsed.path

        # Reconstruct canonical URL without fragment
        canonical = urlunparse((scheme, netloc, path, parsed.params, query_str, ""))
        return canonical
    except Exception as exc:
        logger.warning(f"Failed to canonicalize URL '{url}': {exc}")
        return url.strip()


def compute_dedup_key(canonical_url: str, title: str, published_at: datetime.datetime) -> str:
    """
    Generates a deterministic SHA-256 deduplication key.
    Uses canonical URL if present, otherwise falls back to normalized title + publication timestamp.
    """
    if canonical_url and len(canonical_url) > 8:
        raw_key = f"url:{canonical_url}"
    else:
        norm_title = re.sub(r"\s+", " ", (title or "").lower().strip())
        pub_str = published_at.strftime("%Y-%m-%d") if published_at else "nodate"
        raw_key = f"content:{norm_title}:{pub_str}"

    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:24]


def parse_datetime_utc(val: Any) -> datetime.datetime:
    """
    Robust datetime parser normalizing any supported timestamp format into an aware UTC datetime.
    Supports ISO 8601, RFC 822 / 2822, GDELT compact format, struct_time, and unix epoch.
    """
    if isinstance(val, datetime.datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=datetime.timezone.utc)
        return val.astimezone(datetime.timezone.utc)

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if not val:
        return now_utc

    # 1. Handle struct_time from feedparser
    if hasattr(val, "tm_year"):
        try:
            return datetime.datetime(
                val.tm_year, val.tm_mon, val.tm_mday,
                val.tm_hour, val.tm_min, val.tm_sec,
                tzinfo=datetime.timezone.utc
            )
        except Exception:
            pass

    # 2. String parsing
    if isinstance(val, str):
        s = val.strip()

        # GDELT compact format: YYYYMMDDTHHMMSSZ or YYYYMMDDHHMMSS
        gdelt_match = re.match(r"^(\d{4})(\d{2})(\d{2})T?(\d{2})(\d{2})(\d{2})Z?$", s)
        if gdelt_match:
            try:
                y, m, d, H, M, S = map(int, gdelt_match.groups())
                return datetime.datetime(y, m, d, H, M, S, tzinfo=datetime.timezone.utc)
            except Exception:
                pass

        # RFC 822 / RFC 2822 (e.g. "Wed, 21 Feb 2024 21:05:00 GMT")
        try:
            parsed_rfc = email.utils.parsedate_to_datetime(s)
            if parsed_rfc:
                if parsed_rfc.tzinfo is None:
                    return parsed_rfc.replace(tzinfo=datetime.timezone.utc)
                return parsed_rfc.astimezone(datetime.timezone.utc)
        except Exception:
            pass

        # ISO 8601 parsing
        try:
            iso_str = s.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(iso_str)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=datetime.timezone.utc)
            return dt.astimezone(datetime.timezone.utc)
        except Exception:
            pass

    # 3. Numeric epoch
    if isinstance(val, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc)
        except Exception:
            pass

    logger.warning(f"Unrecognized datetime format: '{val}'. Defaulting to current UTC.")
    return now_utc


class BaseSourceAdapter(ABC):
    """Abstract base class for all RiskLens news ingestion adapters."""

    @abstractmethod
    def fetch_articles(
        self,
        limit: int = 10,
        keywords: Optional[List[str]] = None
    ) -> List[NormalizedArticle]:
        """Fetch and normalize articles from the source provider."""
        pass
