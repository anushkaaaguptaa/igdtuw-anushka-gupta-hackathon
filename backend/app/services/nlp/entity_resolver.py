import re
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from app.core.logger import logger


@dataclass
class ResolvedEntity:
    ticker: str
    name: str
    sector: str
    asset_class: str
    relevance_score: float  # 0.0 to 1.0
    is_primary_target: bool
    matched_text: str


class EntityResolver:
    """
    Extracts and resolves corporate organizations to validated market tickers.
    Uses an explicit alias catalog and context-aware pattern matching to prevent false positives.
    """

    KNOWN_ENTITIES = {
        "NVDA": {
            "name": "NVIDIA Corporation",
            "sector": "Information Technology",
            "asset_class": "Equity",
            "aliases": ["nvidia", "nvidia corp", "nvidia corporation", "nvda"]
        },
        "AAPL": {
            "name": "Apple Inc.",
            "sector": "Information Technology",
            "asset_class": "Equity",
            "aliases": ["apple", "apple inc", "apple computer", "aapl"]
        },
        "MSFT": {
            "name": "Microsoft Corporation",
            "sector": "Information Technology",
            "asset_class": "Equity",
            "aliases": ["microsoft", "microsoft corp", "microsoft corporation", "msft"]
        },
        "GOOGL": {
            "name": "Alphabet Inc.",
            "sector": "Communication Services",
            "asset_class": "Equity",
            "aliases": ["alphabet", "alphabet inc", "google", "googl", "goog"]
        },
        "AMZN": {
            "name": "Amazon.com Inc.",
            "sector": "Consumer Discretionary",
            "asset_class": "Equity",
            "aliases": ["amazon", "amazon.com", "amazon com", "amzn"]
        },
        "META": {
            "name": "Meta Platforms Inc.",
            "sector": "Communication Services",
            "asset_class": "Equity",
            "aliases": ["meta", "meta platforms", "facebook", "fb"]
        },
        "TSLA": {
            "name": "Tesla Inc.",
            "sector": "Consumer Discretionary",
            "asset_class": "Equity",
            "aliases": ["tesla", "tesla inc", "tesla motors", "tsla"]
        },
        "CRWD": {
            "name": "CrowdStrike Holdings Inc.",
            "sector": "Information Technology",
            "asset_class": "Equity",
            "aliases": ["crowdstrike", "crowdstrike holdings", "crwd"]
        },
        "JPM": {
            "name": "JPMorgan Chase & Co.",
            "sector": "Financials",
            "asset_class": "Equity",
            "aliases": ["jpmorgan", "jpmorgan chase", "jp morgan", "chase bank", "jpm"]
        },
        "GS": {
            "name": "The Goldman Sachs Group Inc.",
            "sector": "Financials",
            "asset_class": "Equity",
            "aliases": ["goldman sachs", "goldman", "gs"]
        },
        "BAC": {
            "name": "Bank of America Corporation",
            "sector": "Financials",
            "asset_class": "Equity",
            "aliases": ["bank of america", "bofa", "bac"]
        },
        "XOM": {
            "name": "Exxon Mobil Corporation",
            "sector": "Energy",
            "asset_class": "Equity",
            "aliases": ["exxon", "exxon mobil", "exxonmobil", "xom"]
        },
        "CVX": {
            "name": "Chevron Corporation",
            "sector": "Energy",
            "asset_class": "Equity",
            "aliases": ["chevron", "chevron corp", "cvx"]
        },
        "LLY": {
            "name": "Eli Lilly and Company",
            "sector": "Healthcare",
            "asset_class": "Equity",
            "aliases": ["eli lilly", "lilly", "lly"]
        },
        "PFE": {
            "name": "Pfizer Inc.",
            "sector": "Healthcare",
            "asset_class": "Equity",
            "aliases": ["pfizer", "pfizer inc", "pfe"]
        },
        "BA": {
            "name": "The Boeing Company",
            "sector": "Industrials",
            "asset_class": "Equity",
            "aliases": ["boeing", "boeing co", "the boeing company", "ba"]
        },
        "AMD": {
            "name": "Advanced Micro Devices Inc.",
            "sector": "Information Technology",
            "asset_class": "Equity",
            "aliases": ["amd", "advanced micro devices"]
        },
        "INTC": {
            "name": "Intel Corporation",
            "sector": "Information Technology",
            "asset_class": "Equity",
            "aliases": ["intel", "intel corp", "intc"]
        },
        "ORCL": {
            "name": "Oracle Corporation",
            "sector": "Information Technology",
            "asset_class": "Equity",
            "aliases": ["oracle", "oracle corp", "orcl"]
        },
        "SIVBQ": {
            "name": "Silicon Valley Bank (SVB Financial)",
            "sector": "Financials",
            "asset_class": "Equity",
            "aliases": ["svb", "silicon valley bank", "svb financial"]
        }
    }

    # Common English words that must NOT be matched as standalone tickers without $ or exchange prefix
    AMBIGUOUS_WORDS = {"A", "CAN", "IT", "ALL", "BE", "AT", "SO", "OR", "ON", "FOR", "NOW", "DO", "GO"}

    def __init__(self):
        # Precompute inverted alias map
        self._alias_to_ticker: Dict[str, str] = {}
        for ticker, meta in self.KNOWN_ENTITIES.items():
            for alias in meta["aliases"]:
                self._alias_to_ticker[alias.lower()] = ticker

    def resolve(self, text: str, headline: Optional[str] = None) -> List[ResolvedEntity]:
        headline_text = headline or ""
        full_text = f"{headline_text} {text}"
        if not full_text.strip():
            return []

        resolved: Dict[str, ResolvedEntity] = {}

        # 1. Match explicit stock ticker syntax: $TICKER or (EXCHANGE: TICKER)
        dollar_tickers = re.findall(r"\$([A-Z]{1,5})\b", full_text)
        for t in dollar_tickers:
            if t in self.KNOWN_ENTITIES:
                meta = self.KNOWN_ENTITIES[t]
                is_headline = t in re.findall(r"\$([A-Z]{1,5})\b", headline_text)
                resolved[t] = ResolvedEntity(
                    ticker=t,
                    name=meta["name"],
                    sector=meta["sector"],
                    asset_class=meta["asset_class"],
                    relevance_score=1.0 if is_headline else 0.8,
                    is_primary_target=is_headline,
                    matched_text=f"${t}"
                )

        exchange_tickers = re.findall(r"\b(?:NASDAQ|NYSE|AMEX):\s*([A-Z]{1,5})\b", full_text)
        for t in exchange_tickers:
            if t in self.KNOWN_ENTITIES and t not in resolved:
                meta = self.KNOWN_ENTITIES[t]
                is_headline = t in headline_text
                resolved[t] = ResolvedEntity(
                    ticker=t,
                    name=meta["name"],
                    sector=meta["sector"],
                    asset_class=meta["asset_class"],
                    relevance_score=1.0 if is_headline else 0.8,
                    is_primary_target=is_headline,
                    matched_text=f"Exchange:{t}"
                )

        # 2. Match company name aliases with word boundaries
        # Sort aliases by length descending so longer phrases match first
        sorted_aliases = sorted(self._alias_to_ticker.keys(), key=len, reverse=True)

        for alias in sorted_aliases:
            ticker = self._alias_to_ticker[alias]
            if ticker in resolved:
                continue

            # Special check for words like "apple" to avoid matching fruit
            # (e.g. must be capitalized in original text or in corporate/financial context)
            alias_pattern = r"\b" + re.escape(alias) + r"\b"
            headline_matches = list(re.finditer(alias_pattern, headline_text, re.IGNORECASE))
            body_matches = list(re.finditer(alias_pattern, full_text, re.IGNORECASE))

            if headline_matches or body_matches:
                # If alias is a short ticker abbreviation without $, check that it's in uppercase in original
                if len(alias) <= 4 and alias.upper() == alias:
                    # Require that the original text actually contained uppercase letters
                    raw_matches = list(re.finditer(r"\b" + re.escape(alias.upper()) + r"\b", full_text))
                    if not raw_matches:
                        continue

                # Context check for common fruit "apple"
                if alias == "apple":
                    fruit_context = re.search(r"\b(?:cider|orchard|pie|fruit|tree|flavor)\b", full_text, re.IGNORECASE)
                    if fruit_context and not re.search(r"\b(?:inc|shares|stock|iphone|ipad|tech|tim cook|app store)\b", full_text, re.IGNORECASE):
                        continue

                meta = self.KNOWN_ENTITIES[ticker]
                is_primary = len(headline_matches) > 0
                matched_snippet = headline_matches[0].group(0) if headline_matches else body_matches[0].group(0)

                resolved[ticker] = ResolvedEntity(
                    ticker=ticker,
                    name=meta["name"],
                    sector=meta["sector"],
                    asset_class=meta["asset_class"],
                    relevance_score=1.0 if is_primary else 0.7,
                    is_primary_target=is_primary,
                    matched_text=matched_snippet
                )

        # Return list sorted by relevance_score descending
        return sorted(resolved.values(), key=lambda x: x.relevance_score, reverse=True)
