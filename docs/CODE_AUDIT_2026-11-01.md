# Verified implementation audit — 1 November 2026

Historical record: this audit predates the subsequent historical-ingestion slice.
For current capability and its verified NIFTY 50 download, see
[Historical Data](HISTORICAL_DATA.md). The dependency/security findings below
remain relevant; missing-feature findings are as of the audited snapshot.

## Scope and conclusion

Reviewed the governing AGENTS.md, current master specification v1.4.1, changelog,
Git workflow, all application/engine/security code, templates, commands,
migrations, tests, dependencies and installation/recovery documentation.

The application is a working **local offline data-research foundation plus a
partial Zerodha read-only integration**. It is not yet an operational historical
collection platform or strategy/backtesting system. Real order operations remain
blocked. No new critical credential disclosure or reachable order operation was
verified, and the baseline tests did not fail. No production credentials were
decrypted, printed, transmitted to an audit service or used for new broker calls.

The requested critical-security/failing-test fix gate found no new issue requiring
an additional functional patch. The existing local CSRF correction was preserved
and verified. Moderate dependency issues and other limitations remain explicitly
documented below; passing tests are not a security certification.

### Published versus local code

- `origin/main` and local HEAD both point to
  `534c7facaa1ba6f853aad2dc80978f24aca30053` after `git fetch origin`.
- That published commit has 79 passing tests but predates the reported login CSRF
  compatibility fix. Its blanket no-referrer policy can break browser form POSTs.
- The working directory additionally contains the previously implemented local
  fix: same-origin form referrers, no-referrer on the token callback, a safe CSRF
  recovery page, four regression tests, and related documentation. Local tests: 83.
- Both snapshots were tested separately. The published snapshot was extracted to
  a temporary ignored directory and tested with generated temporary environment
  keys; neither the production database nor the real key vault was used there.
- No changes were committed or pushed by this audit. Existing local work remains
  intact. The public repository is owner-approved; private runtime data is not.

## Completed and working

| Area | Verified implementation | Important boundary |
|---|---|---|
| Local application | Django 5.2.17 / Python 3.13.7, localhost dashboard, source labels, provenance, coverage, quality reports and SVG chart | Development server; desktop/local use |
| Broker Settings | API key/secret inputs, exact callback, enable state, update, profile-only test, interactive login, status, expiry, disconnect, confirmed deletion and audit history | Active staff superuser required |
| Database integration | BrokerConnection, BrokerSession and BrokerAuditLog use the existing configured SQLite database; Django users/sessions reused | PostgreSQL is not configured/installed by this project |
| Credential storage | API secret and access token use authenticated Fernet encryption with version/purpose envelopes | Public API key stored in plaintext as requested and masked in the UI |
| Key management | Independent random Django signing key and broker keyring; Windows current-user DPAPI vault outside repository/database; protected process-environment alternative | Current Windows user can access its vault; not protection from malware running as that user |
| Replacement/deletion | Blank inputs preserve saved credentials; replacement clears local sessions; disconnect tries token revocation then clears local tokens; deletion clears saved credential fields | Old backups retain encrypted material; replacing credentials alone does not revoke an old remote token |
| Rotation/recovery | Retained old keys, primary-key re-encryption command with atomic rollback, passphrase-encrypted portable key export/import | Real-machine recovery drill has not been performed |
| Access controls | Administrator checks, authenticated server-side sessions, CSRF middleware, HTTP-only/Lax cookies, Host/peer checks, no-cache pages and restrictive CSP | Plain HTTP on IPv4 loopback only |
| Login/callback | Official SDK login and token exchange, one-time hashed state, browser/user/revision binding, 10-minute deadline, replay rejection and clean redirect | No automated broker password/OTP login |
| Session handling | Next 06:00 IST local expiry estimate, token-error handling, reauthentication and explicit disconnect | Broker may invalidate earlier; expiry cleanup is lazy on settings/data access |
| Market-data service | Profile, instruments, historical candles, quotes and snapshot depth through a centralized read-only client | Service methods exist; scheduled downloads and ingestion UI do not |
| Request safety | SDK route/method allowlist plus HTTPS destination/path allowlist; TLS validation, redirects blocked, explicit timeouts, no implicit proxy/netrc | No order/GTT/funds-transfer routes permitted |
| Retry/limits | Process-local pacing at one request per 1.05 seconds; at most one retry for transient read failures/429; no automatic authentication/revocation retries | Single worker; not a shared per-API-key limiter |
| Local candle research | Instrument/snapshot/candle/import/issue models, strict CSV/manifest checks, raw SHA-256 archives, atomic imports, idempotency, full declared-session gap reports | Accepts SYNTHETIC and USER_SUPPLIED only |
| Aggregation | Deterministic complete 5m/15m candles from 1m, session-open anchoring, no crossing sessions or filling gaps, explicit available-at timestamps | Sessions supplied by manifest, not an exchange-verified calendar |
| Trade safety | Fixed research mode; no application order interface or execution worker; SDK and transport deny nonallowlisted requests | Official third-party SDK contains order functionality, but this app does not expose/use it |

Local metadata inspection showed one enabled CONNECTED Zerodha connection and an
ACTIVE session not past its local expiry at inspection. This is stored state,
not a new remote health check or proof of historical-data permissions. Existing
owner-initiated connection evidence is separate from this audit's mocked tests.

Research storage contains **one accepted SYNTHETIC dataset**: 750 one-minute,
150 five-minute and 50 fifteen-minute candles, zero quality issues. No broker
historical-candle dataset is present. Row counts and SHA-256 content hashes of
all five research tables were unchanged before/after audit tests.

## Findings and recommended fixes

### A01 — High functional priority: real historical ingestion is absent

Evidence: `brokers/services.py:192` provides read-only historical requests, while
`engine/candles.py:103` accepts only SYNTHETIC/USER_SUPPLIED provenance and
`config/urls.py` has no historical-data page. Instrument downloads are not stored
as dated broker snapshots; candles returned by the SDK are not automatically
normalized, archived, validated, persisted or resampled.

Recommended next slice: an administrator-only instrument sync and bounded
historical-download workflow, explicit ZERODHA provenance, raw-response and
instrument-master hashes, resumable jobs, declared/verified sessions, completion
cutoffs, QA and idempotent persistence. Start with one cash instrument and a short
completed period. A successful profile test does not establish historical API
entitlement; handle that response explicitly without buying services.

### A02 — Moderate dependency risk: upstream-pinned vulnerable Autobahn

The installed 29-package runtime set was checked against OSV. Four advisory IDs
reduce to **two distinct issues**, both in `autobahn==19.11.2`:

| Advisory | Issue | Patched upstream version |
|---|---|---|
| GHSA-gwp7-vqr5-h33h / PYSEC-2020-25 / CVE-2020-35678 | Redirect header injection | 20.12.3 |
| GHSA-hxp9-w8x3-p566 / PYSEC-2026-4027 / CVE-2026-77528 | WebSocket compressed-message size limit bypass/resource exhaustion | 26.7.1 |

Both are rated moderate by the advisory publishers. The official installed
`kiteconnect==5.2.2` metadata requires `autobahn[twisted]==19.11.2` exactly.
Forcing a newer Autobahn would violate that dependency constraint and make
`pip check` fail; the audit did not silently create an incompatible environment.

The affected server/WebSocket operations are not instantiated or reachable in the
current REST-only app. That is a scoped reachability assessment, not removal of
the vulnerable package. Keep WebSockets disabled. Resolve the SDK dependency
through a compatible upstream release or a separately reviewed packaging/source
patch before implementing quote streaming. Add repeatable advisory scanning to CI.

Primary references: [maintainer redirect fix](https://github.com/crossbario/autobahn-python/pull/1439),
[redirect advisory](https://github.com/advisories/GHSA-gwp7-vqr5-h33h),
[maintainer compressed-message advisory](https://github.com/crossbario/autobahn-python/security/advisories/GHSA-hxp9-w8x3-p566).

### A03 — Published-login defect: verified local fix is not on GitHub

Evidence: published `research/middleware.py` overwrites Referrer-Policy with
no-referrer for all pages. Local code now keeps same-origin for forms and
no-referrer for `/kite/callback`; the safe CSRF recovery page and four tests are
present locally. Origin checks and DEBUG=false remain intact.

Recommended action: publish the reviewed local correction when authorized.
A fresh clone of the current published commit still has the old behavior.
No CSRF exemption, trusted-null-origin setting or DEBUG workaround was added.

### A04 — High data-engineering priority: snapshot-date semantics block backfill

Evidence: `engine/candles.py:152` rejects a session before `snapshot_date`.
This is intentional for the M1 fixture's validity assumptions, but a newly fetched
instrument master cannot be used as historical metadata by simply changing that
date or pretending it existed in the past.

Before live-data ingestion, distinguish snapshot observation/fetch timestamps
from instrument validity/effective dates. Keep point-in-time contract identities
and historical tick/lot metadata where available, and mark unverified historical
attributes. Never fabricate earlier snapshot dates to bypass the validator.
This audit preserves existing data/validation rather than loosening it blindly.

### A05 — Low hardening gap: model guard checks format, not authenticated content

Evidence: `brokers/crypto.py:46` checks only the ciphertext prefix on model saves.
The dashboard/service paths correctly call Fernet encryption and decryption checks
authenticated purpose. However, a trusted developer can assign a prefix-shaped
string directly, and bulk ORM updates bypass model save guards entirely.

Recommended: enforce credential writes through a dedicated encrypted field or
repository boundary, with dirty-value authentication tests, while retaining the
ability to clear tokens when keys are unavailable. No attacker-controlled web
path writing plaintext was found. This is a defense-in-depth recommendation, not
a verified browser exploit or evidence of stored plaintext credentials.

### A06 — Operational hardening needed before broader deployment

- Login throttling is process-local/global to the local app and resets on restart.
  Use persistent/shared bounded counters if moving beyond one private worker.
- The request limiter is process-local. Multi-worker download tasks need a shared
  per-API-key limiter, coordinated retry/backoff, Retry-After handling and jitter.
- Session cleanup is lazy; add a housekeeping command before continuous operation.
  Local credentials changes clear tokens, but remote revocation is only attempted
  by disconnect/delete. Disconnect first when replacing/revoking an existing key.
- Rotation/export/import exist, but an owner-approved restore drill is still
  needed. After restoring backups, discard stale browser/broker sessions and
  reauthenticate; a database/key backup is sensitive even if encrypted.
- Database size is not covered by the 256 MiB raw-archive budget. Broad history
  collection needs measured SQLite limits, storage quotas, retention and later
  partitioned Parquet/query storage as specified.
- The research overview is accessible to local users without administrator login;
  broker settings are protected. This matches the present personal localhost
  workflow, but should be reconsidered before multiple users or proxying.

### A07 — Deployment warnings are real, scoped to localhost HTTP

`manage.py check --deploy` reports W004 (HSTS), W008 (SSL redirect), W012 (secure
session cookie) and W016 (secure CSRF cookie). The app intentionally uses HTTP
on loopback, so switching those flags without HTTPS would break local access.
They were not silenced or reported as passing. This is **not a public deployment
configuration**; any future deployment needs HTTPS, appropriate cookie/HSTS
settings, a production server, access controls and a separate security review.

## Partial and missing capabilities against the specification

| Milestone/area | Current state | Remaining work |
|---|---|---|
| M0 audit | Complete for this snapshot | Repeat for materially changed dependencies/data architecture |
| M1 offline foundation | Working | Exchange-calendar/corporate-action validation beyond fixture assumptions |
| M2 strategy/backtest kernel | Missing | ORB/EMA rules, indicators, signals, later-state fills, pessimistic ambiguity, partial/nonfills, fees/slippage, cash/risk rules, experiments and metrics |
| M3 Zerodha integration | Partial | Daily instrument snapshots, historical downloader, provenance/schema extension, persistence/QA UI, retries/recovery jobs, coverage/backfill |
| M4 universal scanner | Missing | Liquid/eligible universe, as-of features, sector/benchmark context, signal explanations/rejections and untouched holdout comparisons |
| M5 options archive | Missing | Exact-contract pre-expiry archives, OI/quotes/ticks when licensed, reconnection and coverage history |
| M6 shadow/risk ledger | Missing | Simulated orders/fills/trades, risk sizing/limits, skipped-opportunity ledger and adaptive/partial exits |
| M7 ML/AI | Missing | Feature/version registry, chronological training/holdout, calibration, drift and baseline comparisons; optional non-executing research assistant |
| M8 real execution | Deliberately blocked | No live execution implementation or authorization |
| Storage infrastructure | SQLite plus bounded CSV/raw archive | No PostgreSQL/Parquet/DuckDB/Polars pipeline; no Redis/Celery/service needed yet |
| Other spec entities | Roadmap only | No StrategyDefinition, BacktestRun/Trade, SignalEvent, ShadowTrade or RiskPolicy models; broker audit is implemented |
| Market/rules data | Partial manifest checks | Effective-date exchange rules, verified holidays/special sessions, corporate actions, survivorship and historical universe eligibility |
| Automated operations | Missing | Scheduler, restart recovery, incremental checkpoints, CI workflow and full disaster-recovery drill |

No strategy performance, simulated profitability, model accuracy or real-money
readiness can be inferred from the current synthetic candles or passing tests.

## Exact verification and observed results

Commands ran through the existing `.venv\Scripts\python.exe`, without installing
packages, resetting data or invoking broker APIs:

```powershell
git fetch origin
git rev-list --left-right --count HEAD...origin/main
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py showmigrations
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe manage.py test --verbosity 1
.\.venv\Scripts\python.exe manage.py check --deploy
.\.venv\Scripts\python.exe scripts/smoke_test.py
```

| Check | Actual result |
|---|---|
| Current local tests | **83 passed in 17.069 seconds** |
| Clean published snapshot tests | **79 passed in 15.801 seconds** |
| Django check | No issues; zero silenced |
| Migration drift | No changes detected |
| Migrations | All auth, contenttypes, broker, research and session migrations applied |
| Dependency consistency | No broken requirements found |
| Dependency advisory query | 29 package versions; two distinct moderate Autobahn issues, four alias IDs |
| Deployment check | Four warnings W004/W008/W012/W016, documented above |
| HTTP research smoke | Passed: dashboard 200, safety/demo labels, coverage/chart, root POST 405, invalid Host 400, missing orders URL 404 |
| Research preservation | Five table row counts and content hashes unchanged |
| Git history review | Two commits, 55 unique blobs: no private-file paths, private-key/GitHub-token pattern matches or configured public API-key literal found |
| Current-source pattern review | 65 eligible files; no private-key/GitHub-token matches |
| Git exclusions | DB, raw data, backups, environment, credential folders and key files ignored; none tracked |
| Key placement | Current vault outside workspace; populated credential fields have ciphertext envelopes; actual production credentials were not decrypted |

Secret scans were bounded static/history checks, not proof that all possible
secret formats are absent. The OSV query transmitted public package names and
versions only. Its alias count must not be misreported as four distinct flaws.
Audit metadata/logs are in ignored `data/`; they contain no decrypted credentials.

## Readiness and next priorities

**Ready:** personal localhost synthetic-data research, administrator credential
configuration and manually initiated read-only broker authentication/service use.

**Not ready:** complete historical collection, backtesting claims, universal
scanning, ML, unattended streaming, public hosting or real trading.

1. Publish the reviewed CSRF correction after owner approval; retain the local
   regression tests and safe recovery page.
2. Implement a small M3 historical ingestion slice: explicit broker provenance,
   observed-versus-valid instrument metadata, one cash instrument, a few completed
   sessions, 1m validation/archive/storage, then derived 5m/15m QA.
3. Add incremental jobs/checkpoints, verified calendars and staged backfill; verify
   historical entitlement with a small owner-authorized request.
4. Implement M2 deterministic baselines and conservative fills/cost/risk tests
   before broad scanning or AI work. Declare the chronological holdout in advance.
5. Resolve the SDK's Autobahn dependency before introducing WebSockets; add CI
   security/dependency checks and an approved backup/restore drill.

Credential entry URL: **http://127.0.0.1:8001/settings/broker/**.
Local administrator sign-in: **http://127.0.0.1:8001/accounts/login/**.
Exact registered callback: **http://127.0.0.1:8001/kite/callback**.

## Primary references

- [Kite official authentication and expiry](https://kite.trade/docs/connect/v3/user/)
- [Kite error types and rate limits](https://kite.trade/docs/connect/v3/exceptions/)
- [Kite historical candles](https://kite.trade/docs/connect/v3/historical/)
- [Fernet authenticated encryption and rotation](https://cryptography.io/en/latest/fernet/)
- [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- Autobahn maintainer/advisory links in finding A02.
