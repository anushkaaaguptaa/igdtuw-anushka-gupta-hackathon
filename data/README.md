# RiskLens AI — Datasets & Replay Fixtures

This directory documents and stores the datasets, replay fixtures, and portfolio calibrations used across the RiskLens AI platform.

## 1. Data Classification & Provenance

RiskLens AI strictly distinguishes between three distinct data tiers to ensure complete auditability, academic integrity, and compliance with institutional standards:

| Tier | Source / Format | Storage Location | Audit Provenance Label | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Live External Feeds** | GDELT 2.0 Doc API & Financial RSS Feeds | Ephemeral / Database (`risklens.db`) | `source: "gdelt"` / `source: "rss"` | Real-time global financial news and macroeconomic headlines ingested via REST and XML RSS feeds. |
| **Historical Replay Fixtures** | Curated JSON Fixture | `data/fixtures/historical_news.json` | `source: "replay_fixture"`, `is_replay_fixture: true` | Verified historical news articles representing canonical financial events used for deterministic offline evaluation. |
| **Synthetic Portfolios** | Calibrated Financial JSON | `data/portfolios/synthetic_wholesale_portfolio.json` | `calibration_basis: "Synthetic Wholesale Banking"` | Realistic wholesale banking multi-asset portfolio with explicit instrument risk parameters ($16.99M baseline carrying value). |

---

## 2. Historical Replay Fixtures (`data/fixtures/historical_news.json`)

Contains 6 verified historical market events formatted according to the `NormalizedArticle` schema:

1. **Silicon Valley Bank Deposit Run (March 2023)** — Credit event and regional banking liquidity contagion shock.
2. **CrowdStrike Falcon Sensor Outage (July 2024)** — Product and operational failure triggering enterprise IT disruptions.
3. **FTC Big Tech Generative AI Inquiry (January 2024)** — Regulatory and antitrust action targeting cloud hyperscalers.
4. **NVIDIA Q4 Earnings Surge (February 2024)** — Financial results driven by data center AI demand.
5. **Federal Reserve 22-Year High Rate Hike (July 2023)** — Central bank monetary policy tightening and yield curve shift.
6. **DOJ Smartphone Antitrust Lawsuit Against Apple (March 2024)** — Regulatory enforcement on enterprise platform ecosystems.

All replay articles are stamped with `source: "replay_fixture"` and preserved with canonical source URLs, publishers, and publication timestamps.

---

## 3. Synthetic Wholesale Banking Portfolio (`data/portfolios/synthetic_wholesale_portfolio.json`)

Calibrated for wholesale banking stress testing benchmarks:
- **Total Baseline Carrying Value:** $16,993,750.00 USD
- **Holdings:**
  1. `ACME_CORP_LOAN`: Corporate credit loan modeled under amortized cost (IFRS 9 / Basel II Expected Credit Loss). EAD = $5.0M, PD = 2.5%, LGD = 45%, baseline carrying value = $4,943,750.00.
  2. `US_TREASURY_10Y`: 10-year US Treasury Note ($4.0M notional). Repriced via duration-convexity expansion ($D_{\text{mod}} = 7.8$, Convexity = $65.0$).
  3. `MS_CORP_BOND_5Y`: 5-year investment grade corporate bond ($3.0M notional). Repriced via yield duration ($D_{\text{mod}} = 4.2$) and credit spread widening (+120 bps).
  4. `NVDA`: Public mega-cap equity ($2.6M market value, $\beta = 1.45$).
  5. `AAPL`: Public mega-cap equity ($2.2M market value, $\beta = 1.05$).
  6. `SPX_PUT_HEDGE`: Protective put option contract ($250,000 premium carrying value) hedging $10.0M underlying equity notional with $\Delta = -0.35$.
