# Historical Data — bounded manual NSE ingestion

**RESEARCH ONLY — LIVE ORDERS DISABLED**

Open **http://127.0.0.1:8001/historical/** using your local administrator account.
The page uses the encrypted broker credentials/session already saved in Broker
Settings. There is no key/password field on this page.

1. Click **Sync NSE instrument list** to save a content-addressed, timestamped
   snapshot. A repeat identical response reuses its original observation record.
2. Select **NIFTY 50** (the default) or another eligible current NSE cash/reference
   instrument from that saved master. Futures/options and other venues are outside
   this first slice. Cash EQ types are not independently classified as stock/ETF.
3. Select a completed period of up to seven calendar days within the last 90 days.
   Today is excluded, even after the normal close. The default is the previous
   weekday, which may still be an exchange holiday; it is not claimed as verified.
4. Click **Fetch, validate and save candles** and wait for the synchronous request.
   The downloader requests 1-minute data and derives complete 5m/15m bars locally.
5. Open the resulting dataset link for source labels, coverage, chart, timestamps,
   hashes and quality issues. Repeating a completed request with the same master,
   symbol and dates reuses the accepted dataset without another historical call.

If the session expired, use **Login with Zerodha** in Broker Settings and retry.
Historical-data permission errors are sanitized and recorded; the app never buys
a subscription or asks for credentials in chat. Test Connection checks profile
access only, so the first successful historical request is a separate verification.

## First real download verified

| Item | Observed result |
|---|---|
| Instrument | NSE:NIFTY 50, current master token resolved server-side |
| Period | 30 October 2026, normal declared session |
| Dataset / download job | 2 / 1 in the owner's current local database |
| One-minute bars | 375 / 375 declared minutes, 100% coverage |
| Derived bars | 75 × 5-minute, 25 × 15-minute |
| Index volume/lot/tick | Unavailable/NULL; broker originals preserved in decoded archive |
| Quality | No price/schema errors; CURRENT_METADATA and ASSUMED_CALENDAR warnings |
| Repeated request | Reused the same dataset; no new historical request |
| Master | 10,412 records in content-addressed NSE snapshot 1 |

Dataset URL on this laptop: **http://127.0.0.1:8001/?dataset=2**.
IDs are generated locally and may differ in another installation.

## Provenance and correctness boundaries

- Existing CSV manifest v1 and original datasets are preserved. Broker manifests
  use v2, ZERODHA source and the `kite-ingest.1` ingestion version. Arbitrary local
  CSV import cannot mark itself ZERODHA; only the broker download workflow can.
- Master observation date means when that archived content was first observed.
  It is not rewritten as an earlier historical validity date. Each dataset records
  the exact master and response SHA-256 plus its actual download observation time.
- Archived broker JSON is **SDK-decoded canonical JSON**, not an exact copy of HTTP
  wire bytes. No authorization headers, access tokens or account credentials are
  included. Normalized CSV/manifests and raw decoded payloads stay in ignored
  `data/raw/`; the existing 256 MiB archive budget remains in force.
- Broker history before the observed master date carries a deliberate historical
  metadata caveat. Current tick/lot values are not certified for that historical
  date; current tick alignment is not imposed on those historical candles.
- Session policy is explicitly **NSE_NORMAL_WEEKDAYS_ASSUMED_V1**: weekdays,
  09:15–15:30 IST. Holidays are not silently treated as valid closures; their
  missing minutes remain quality gaps. Weekends/special sessions are not assessed.
  This is not a complete exchange-calendar or corporate-action validation system.
- Timestamps are bar-open, stored in UTC and displayed in IST. Requests end at
  15:29 for the final 1m bar closing at 15:30. Only past dates are downloadable.
- Index volume is not traded volume. Index lot/tick fields are inapplicable and
  normalize to NULL even if the master reports zeros. No index VWAP, depth or
  option-profit claim is calculated. Raw values are retained for provenance.
- Validation rejects malformed, duplicate, out-of-session or inconsistent OHLC
  responses atomically. Missing bars remain missing; incomplete 5/15m buckets are
  skipped with warnings. Accepted datasets may have gaps; inspect coverage first.
- The broker service retains TLS, destination/method allowlists, pacing and bounded
  safe GET retries. There are no new order endpoints or live-trading settings.

## Jobs and recovery

`HistoricalDownloadJob` records request state; `DataIngestJob` remains the accepted
or rejected dataset/QA record. Completed/rejected results are immutable for the
same master/symbol/period/version; use another range/master when appropriate.
Failed network/authentication requests can retry the same job. An interrupted
RUNNING request may resume after ten minutes. Only one local download runs at a
time; this is not a multi-worker scheduler. Raw archives may remain after a failed
database transaction for inspection, but partial candle imports roll back.

The full daily scheduler, forced-refresh versioning, large incremental backfills,
verified exchange calendar, historical contract metadata and broader data-cache
retention are still future work. The SDK's existing Autobahn advisories are not
resolved by this REST-only feature; no WebSocket worker is activated.

## CLI equivalents

Use the already configured broker session; do not put credentials in arguments:

```powershell
.\.venv\Scripts\python.exe manage.py sync_instruments
.\.venv\Scripts\python.exe manage.py fetch_candles --symbol 'NIFTY 50' --start 2026-10-30 --end 2026-10-30
```

Fresh checkout: initialize local keys and apply migrations using the normal setup
instructions. Existing installation: apply the additive migrations after a
private database backup. On this laptop 0002 and 0003 have already been applied.
The backup contains encrypted credentials, not the separate DPAPI encryption keys.
No existing dataset/database was overwritten or reset.

## Verification

Executed:

```powershell
.\.venv\Scripts\python.exe manage.py test --verbosity 1
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts/smoke_test.py
```

Results: **104 tests passed in 62.228 seconds**, system/dependency checks passed,
no migration drift, synthetic smoke passed, and the real NIFTY dataset returned
HTTP 200 with its chart, source label, coverage and caveats. Anonymous Historical
Data access redirects to administrator sign-in. New tests mock broker responses
and cover master integrity, bounded dates, provenance, index fields, OHLC/volume,
gaps/duplicates/empty responses, atomic rollback, retry/idempotency and CSRF.
Every pre-existing research row/original column value was verified unchanged.

Primary references: [Kite historical API](https://kite.trade/docs/connect/v3/historical/),
[instrument master](https://kite.trade/docs/connect/v3/market-quotes/),
[NSE normal market timings](https://www.nseindia.com/static/market-data/market-timings).
