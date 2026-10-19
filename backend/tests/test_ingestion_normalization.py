import datetime
import pytest
from app.services.ingestion.base import (
    canonicalize_url,
    compute_dedup_key,
    parse_datetime_utc
)


def test_canonicalize_url_strips_tracking_params():
    raw_url = "https://www.bloomberg.com/news/articles/2024-07-19/crowdstrike-update?utm_source=twitter&utm_medium=social&utm_campaign=breaking#main-content"
    clean_url = canonicalize_url(raw_url)
    assert clean_url == "https://www.bloomberg.com/news/articles/2024-07-19/crowdstrike-update"
    assert "utm_source" not in clean_url
    assert "#main-content" not in clean_url


def test_canonicalize_url_normalizes_trailing_slashes_and_casing():
    url_with_slash = "HTTPS://WWW.Reuters.COM/business/finance/deal-news//"
    clean = canonicalize_url(url_with_slash)
    assert clean == "https://www.reuters.com/business/finance/deal-news"


def test_compute_dedup_key_stability():
    pub_date = datetime.datetime(2024, 7, 19, 8, 15, 0, tzinfo=datetime.timezone.utc)
    url_a = "https://example.com/news/article1?utm_source=newsletter"
    url_b = "https://example.com/news/article1?ref=home"

    key_a = compute_dedup_key(canonicalize_url(url_a), "Sample Title", pub_date)
    key_b = compute_dedup_key(canonicalize_url(url_b), "Sample Title", pub_date)

    # Identical canonical URL must yield identical dedup keys
    assert key_a == key_b
    assert len(key_a) == 24


def test_compute_dedup_key_fallback_on_missing_url():
    pub_date = datetime.datetime(2024, 3, 10, 16, 30, 0, tzinfo=datetime.timezone.utc)
    key_1 = compute_dedup_key("", "SVB Liquidity Outflow Alert", pub_date)
    key_2 = compute_dedup_key("", "  svb liquidity outflow alert  ", pub_date)
    assert key_1 == key_2


def test_parse_datetime_utc_various_formats():
    # 1. GDELT format
    gdelt_date = parse_datetime_utc("20240719T081500Z")
    assert gdelt_date.year == 2024
    assert gdelt_date.month == 7
    assert gdelt_date.day == 19
    assert gdelt_date.hour == 8
    assert gdelt_date.tzinfo == datetime.timezone.utc

    # 2. RFC 822 / RSS format
    rfc_date = parse_datetime_utc("Wed, 21 Feb 2024 21:05:00 GMT")
    assert rfc_date.year == 2024
    assert rfc_date.month == 2
    assert rfc_date.day == 21
    assert rfc_date.hour == 21
    assert rfc_date.tzinfo == datetime.timezone.utc

    # 3. ISO 8601 with offset
    iso_date = parse_datetime_utc("2024-03-10T12:30:00-04:00")
    assert iso_date.tzinfo == datetime.timezone.utc
    # 12:30 EDT (-04:00) is 16:30 UTC
    assert iso_date.hour == 16

    # 4. Fallback on empty or malformed
    now = datetime.datetime.now(datetime.timezone.utc)
    fallback = parse_datetime_utc("not-a-real-date")
    assert abs((fallback - now).total_seconds()) < 5
