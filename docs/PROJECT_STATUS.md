# Project status and next-path choices

**Checkpoint: 2 November 2026 (IST)**<br>
**RESEARCH ONLY — LIVE ORDERS DISABLED**

This is the current summary of completed work. The master specification describes
the longer-term plan; it does not mean every planned module has been built.

## What we have completed

| Work | Result |
|---|---|
| Repository and laptop audit | Inspected Git state/history, Windows/Python tooling, database availability and resource headroom; preserved existing work |
| Local Django application | Python 3.13 / Django 5.2, isolated virtual environment and existing local SQLite database; no Docker, WSL or extra service |
| Research dashboard | Source-labeled coverage, data-quality reports, provenance hashes, candle chart and explicit research-only banner |
| Research database | Instruments, dated snapshots, candles, import datasets, quality issues and additive migrations |
| Offline test data | Deterministic synthetic CSV, atomic/idempotent imports, strict OHLC/volume/timestamp checks and missing-bar reports |
| Candle conversion | Complete 1m → 5m/15m bars, anchored at session open, without filling gaps or crossing sessions |
| Broker configuration | Administrator-only Zerodha settings, masked inputs, safe replacement/deletion, status, profile test and safe audit events |
| Credential protection | API secrets/access tokens encrypted with Fernet; independent keyring outside Git/database, protected by Windows DPAPI |
| Key maintenance | Key rotation, retained old keys and separately encrypted portable key backup/recovery commands |
| Interactive Zerodha login | Official login/callback, one-time state bound to administrator/browser/settings revision, expiry handling and explicit disconnect |
| Login CSRF correction | Same-origin form policy, strict callback referrer protection and a safe recovery page; CSRF remains enabled and DEBUG remains false |
| Read-only API service | Profile, instrument master, historical candles, quotes and depth behind request/destination allowlists, pacing and bounded safe retries |
| Historical Data page | Administrator selects a saved NSE instrument and completed dates; downloads, validates, archives, stores and derives candles using saved credentials |
| Download management | Content-addressed master snapshots, request jobs, completed-request reuse, failed-request retries and safe error details |
| Code audit | Published/local snapshot review, tests, migrations, Git exclusions, dependency advisories and a documented implementation-gap report |
| Installation and runbooks | PowerShell setup/diagnostics, local HTTP smoke test, broker/key and historical-data instructions |

The implementation uses **Zerodha only** for broker market data. There are no
application order methods, execution worker or live activation controls. Tests
also check blocked order routes/SDK operations. The official third-party SDK
contains order features, but this application's boundaries do not permit them.

## Actual data already collected locally

The owner selected **NIFTY 50 index reference data** for the first real download.

| Item | Verified result |
|---|---|
| Saved NSE instrument master | 10,412 records |
| First historical period | 30 October 2026 |
| One-minute candles | 375 / 375 declared minutes |
| Derived candles | 75 five-minute; 25 fifteen-minute |
| Price/schema errors | None in that accepted sample |
| Explicit caveats | CURRENT_METADATA and ASSUMED_CALENDAR warnings |
| NIFTY volume, lot and tick | Unavailable/NULL; raw provider fields retained privately |
| Repeat download | Reuses the accepted dataset without another historical request |
| Existing synthetic dataset | Retained: 750 one-minute, 150 five-minute and 50 fifteen-minute candles |

This is a successful engineering check on **one real session**, not a strategy
backtest or a meaningful evidence base for profitability. Index candles cannot
establish option contract P&L, traded index volume, VWAP or order-book fills.

Raw broker responses, normalized data, the database, logs, backups and encryption
keys stay local and excluded from Git. GitHub contains source, migrations,
documentation and synthetic fixtures; cloning the repository does not copy the
owner's credentials or downloaded market data.

## What is only partially complete

- **M3 data integration:** manual historical collection works. Requests are bounded
  to seven calendar days within the last 90 days, excluding today. There is no
  scheduler or full nine-month incremental backfill yet.
- **Trading calendar:** normal NSE weekdays 09:15–15:30 IST are assumed. Missing
  declared weekdays remain gaps; holidays/special sessions are not certified and
  weekends are not assessed.
- **Historical instrument metadata:** current observation dates are preserved;
  snapshots are not backdated. Historical tick/lot validity and corporate actions
  are not independently verified.
- **Operations:** single-process pacing and local request state exist. Shared
  worker limits, richer backoff, automated housekeeping, CI and an owner-approved
  recovery drill remain future work.
- **Dependency hardening:** the official SDK pins Autobahn 19.11.2, which has two
  documented moderate advisories. Affected WebSocket/server paths are unused;
  resolve compatibility before enabling streaming. See the audit for details.

Broker credentials persist, but broker sessions are temporary. Reauthenticate
through **Login with Zerodha** when required; do not re-enter saved API credentials
unless replacing them. No automated password/OTP login is implemented.

## What we have not built yet

| Milestone | Missing implementation |
|---|---|
| M2: deterministic backtesting | ORB/EMA strategy rules, indicator engine, signals, conservative fills, versioned costs, risk/cash limits, experiment records and performance metrics |
| M4: broad opportunity scanner | Eligible/liquid universe screening, as-of features, rejection reasons and comparative holdout evaluation |
| M5: options archive | Exact active-contract pre-expiry history, licensed quote/tick capture and historical option coverage |
| M6: shadow/risk research | Paper orders/fills/trades, skipped-opportunity ledger, position sizing and adaptive/partial exits |
| M7: ML/AI research | Training pipeline, calibrated probabilities, model registry, drift analysis and baseline comparisons |
| M8: real execution | Deliberately disabled and outside current authorization |

There is no verified strategy performance or accuracy result yet. The completed
work is the application, credential/data-safety foundation and first ingestion
slice—not a finished trading-research system.

## Choose the next development path

| Choice | Concrete next deliverable | Why choose it |
|---|---|---|
| **A — Strengthen historical data (recommended first)** | Verified NSE session/holiday data, better coverage checks, controlled incremental backfill and another owner-selected cash instrument | Gives later research a larger, explainable dataset and reduces misleading gap/metadata assumptions |
| **B — Build the M2 backtesting kernel** | One versioned ORB or EMA baseline with completed-bar signals, later-state simulated fills, pessimistic stop/target ambiguity, effective-date costs and cash/risk constraints | Turns stored candles into reproducible simulation; begin with deterministic tests and make no profitability claim |
| **C — Operations and recovery** | Reproducible CI checks, dependency remediation plan, session/job housekeeping and a tested private backup/restore procedure | Improves reliability before larger downloads or longer-running research |

Suggested sequence: **A → B**, with essential recovery work from C before large
backfills. Broad scanners, options simulation and AI should follow reliable data
and baseline backtests. Starting a full scanner or ML training now would be early.

For B, keep the original chronological research/holdout discipline. Do not tune on
the holdout or describe index-based research as validated historical option P&L.
Selecting a next path does not authorize live trading or additional paid services.

## How to review the current app

With the local server running:

| Page | URL |
|---|---|
| Research dashboard | http://127.0.0.1:8001/ |
| First NIFTY dataset on this laptop | http://127.0.0.1:8001/?dataset=2 |
| Historical Data | http://127.0.0.1:8001/historical/ |
| Broker Settings | http://127.0.0.1:8001/settings/broker/ |
| Local administrator login | http://127.0.0.1:8001/accounts/login/ |

Dataset IDs are local and can differ after a fresh installation. The exact
registered Kite callback remains `http://127.0.0.1:8001/kite/callback`.

## Verification and source references

Checkpoint verification on 2 November 2026: **104 tests passed in 23.778 seconds**;
Django system, dependency-consistency and migration-drift checks passed. The HTTP
smoke test passed. Tests use synthetic/mocked broker responses and isolated
databases/archives. No new broker request was made for this checkpoint. Actual
read-only sample counts and pre-existing data preservation are documented in the
historical runbook.

Useful documents:

- [Master specification v1.5](MASTER_SPEC_v1.3.md) — governing roadmap, legacy filename retained.
- [Decisions and chronological changelog](DECISIONS_AND_CHANGELOG.md).
- [Historical Data runbook](HISTORICAL_DATA.md).
- [Broker settings, encryption keys and recovery](BROKER_CONFIGURATION.md).
- [Earlier complete code audit](CODE_AUDIT_2026-11-01.md) — a historical snapshot before the ingestion slice.

This checkpoint publishes reviewed source/documentation to the existing public
repository, as explicitly chosen by the owner. Personal data and secrets remain
private. No new broker request or strategy experiment is needed to publish it.
