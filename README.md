# Indian Market Research Lab — offline research + secure broker settings

**RESEARCH ONLY — LIVE ORDERS DISABLED**

**Start here:** [What we completed and the next development choices](docs/PROJECT_STATUS.md)
— checkpoint dated 2 November 2026.

Verified status, 1 November 2026: offline research, Zerodha authentication and a
bounded **Historical Data download-and-save workflow** work locally. The first
NIFTY 50 sample contains 375 one-minute, 75 five-minute and 25 fifteen-minute
candles for 30 October 2026. **104 tests pass.** Strategy/backtesting, scanner,
indicator, risk-simulation and AI modules remain future work.
See the [Historical Data runbook](docs/HISTORICAL_DATA.md) for current usage and
limitations. The [earlier audit](docs/CODE_AUDIT_2026-11-01.md) records the state
before this ingestion slice, including dependency risks that remain unresolved.

Local Python/Django research software with optional administrator-only Zerodha
configuration and interactive read-only API authentication. There are no order
APIs, live-trading controls, frontend CDN assets or additional paid services.
The research dashboard runs at `http://127.0.0.1:8001`. Synthetic research and
automated tests remain offline and need no broker credentials or subscription.

**Broker Settings:** http://127.0.0.1:8001/settings/broker/

Create your local administrator once using
`.\.venv\Scripts\python.exe manage.py createsuperuser`, then sign in to that page.
Enter your API key and secret there, save, and click **Login with Zerodha**.
The exact registered callback is `http://127.0.0.1:8001/kite/callback` (no trailing
slash). Full setup, key backup/rotation and recovery:
[Broker Settings runbook](docs/BROKER_CONFIGURATION.md).

**Historical Data:** http://127.0.0.1:8001/historical/. Sign in, sync the NSE master,
select NIFTY 50 and a past period, then fetch/validate/save. Existing encrypted
credentials are used automatically. No keys are entered on the data page.

## Windows PowerShell setup

Tested here with Python **3.13.7**, Django **5.2.17**, Windows 11 and SQLite.
Python and Git were already installed. Pinned dependencies install only
inside `.venv`; no PostgreSQL, Docker, WSL, Node, Redis or background service is
needed. The official Kite SDK includes its own networking dependencies; no
WebSocket service is started. Installation may require internet; research data
and mocked tests run offline afterwards. Broker actions require internet and
the owner's existing authorized Kite access. No system installation is needed.

From `C:\Automations\Trading`:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/security_keys.py init
New-Item -ItemType Directory -Path data -Force | Out-Null
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py load_demo
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001 --noreload
```

Open **http://127.0.0.1:8001/**. Port 8000 was unavailable and associated with an
existing Java process during verification; that application was preserved.
Use `127.0.0.1:8000` only when the port is free. Django's default remains 8000.
Stop the server with **Ctrl+C**. Activation is not
required, so PowerShell activation-policy changes are unnecessary. If script
execution is already permitted, `& .\scripts\setup.ps1` performs the same setup
through the demo import and system check. Otherwise use the commands above; do
not change machine execution policy. Diagnostics: `& .\scripts\check_env.ps1`.

The existing project-local database is `data/research.sqlite3`. Repeating
`migrate` and `load_demo` preserves existing datasets. Do not point this app at
another application's database. The original root instruction documents remain
untouched; the copies under `docs/` restore the expected governing-document paths.
Use `docs/DECISIONS_AND_CHANGELOG.md` for ongoing engineering progress.

## Validate the installation

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test --verbosity 2
.\.venv\Scripts\python.exe scripts/smoke_test.py
```

The unit/integration suite uses an isolated in-memory SQLite test database and
temporary raw archives. It does not mutate the demo database. The smoke test
requires the migrated database and `load_demo`; it starts its own hidden
loopback server on a free port, makes local HTTP requests, and terminates that
child. It checks HTTP 200, both required banners, coverage, SVG chart, rejected
POST, invalid Host, and absence of an orders route. Exact observed results and
commands are recorded in [docs/VERIFICATION.md](docs/VERIFICATION.md).

## Data workflow

Bundled fixture: **750 synthetic 1-minute candles**, two explicitly declared
09:15–15:30 IST sessions. Expected output: **150 five-minute** and **50
fifteen-minute** candles, **100% declared coverage**, **zero quality issues**.
The synthetic instrument is `DEMO_NSE:SYNTH-EQ`; it is not a tradable identity.

`load_demo` imports and resamples idempotently. Equivalent explicit commands:

```powershell
.\.venv\Scripts\python.exe manage.py import_candles tests/fixtures/synthetic.csv --manifest tests/fixtures/synthetic.manifest.json
# Replace 1 with the dataset ID printed by the import command.
.\.venv\Scripts\python.exe manage.py resample_bars --dataset 1 --interval 5
.\.venv\Scripts\python.exe manage.py resample_bars --dataset 1 --interval 15
```

CSV header, in this exact order:

```csv
timestamp,open,high,low,close,volume
2026-10-29T09:15:00+05:30,100.00,100.10,99.80,99.90,1000
```

Use the bundled JSON manifest as the schema example. Every import declares
source (`SYNTHETIC` or `USER_SUPPLIED`), label, provenance reference, exact
instrument snapshot and explicit session dates/hours. Prices/tick/strike are
decimal strings, with up to four decimal places. Imported data is never
automatically called broker-verified. Only import data you have rights to use;
do not include account credentials or identifiers in CSVs or manifests.

- Timestamps are **bar-open**, require an explicit offset, and normalize to UTC.
  The dashboard displays IST. `available_at` is the candle close; future
  strategies must not consume the completed bar before that time.
- OHLC must be positive, finite, tick-aligned and internally consistent. Traded
  volume must be a nonnegative integer; index volume must be blank/unknown.
- Duplicate timestamps (including equivalent UTC/IST representations), unsorted
  rows, malformed schema, invalid dates/contracts or out-of-session minutes
  reject the whole import. Valid provenance plus invalid CSV records a rejected
  job with quality issues and **no candles**. Invalid manifests/oversized files
  fail before any database write.
- Missing first/last/intermediate minutes and wholly absent declared sessions
  are warnings. Gaps remain missing; coverage includes them in the denominator.
  Undeclared dates are **not assessed**. A close jump over 20% is a review warning,
  not a universal anomaly rule or an automatic price correction.
- Aggregation starts at each declared session open, never crosses sessions,
  emits only complete buckets and records skipped buckets. For a normal demo
  session, the final 5m/15m bars open at 15:25/15:15 and close at 15:30.
- Sessions are explicit **dataset inputs**, not a verified exchange calendar.
  They support special hours without guessing weekdays/holidays. Corporate
  actions, market closures, stale live feeds, trade eligibility and complete
  historical contract validation are later work.
- Inputs are limited to 4 MiB CSV, 64 KiB manifest, 20,000 minute rows and
  31 declared dates per import. Import commands are synchronous: run one at a
  time. No parallel worker/service is installed.

Raw CSV and canonical JSON manifests are archived under `data/raw/` by SHA-256.
The fingerprint combines CSV hash, canonical manifest hash and engine version.
Identical imports are no-ops; changed inputs create separate datasets. Derived
bars belong to that dataset. Conflicting dated snapshots or changed existing
derived bars are rejected, never overwritten. Synthetic and user-supplied
instrument identities are separate. Immutability is enforced by the import
workflow, not against someone manually editing the SQLite file.

The raw archive has a 256 MiB budget and never automatically deletes files.
Filesystem archives precede the atomic database transaction: a failed transaction
can leave a content-addressed raw file for inspection, but no partial database
import. Database size is not included in this raw-file budget. Back up local data
only to an owner-approved destination; no cloud synchronization is configured.

Regenerate fixtures deterministically (overwrites only the two bundled synthetic
fixture files): `.\.venv\Scripts\python.exe scripts/generate_fixture.py`.
The generator uses a documented integer/decimal formula, no randomness or network.

## Architecture and safety

- `engine/candles.py`: framework-independent manifest/CSV checks and resampling.
- `research/models.py`: instruments, dated snapshots, import jobs, quality issues
  and candles. Database constraints protect unique bars and valid OHLC.
- `research/services.py`: bounded file reads, provenance, archives, transactional
  imports and idempotent derived bars.
- `research/views.py` and templates: source-labeled dashboard, coverage, quality
  reports, provenance and local SVG chart; no JavaScript/build system/CDN.
- `brokers/`: encrypted credentials/sessions, safe audit history, administrator
  forms, state-bound authentication and an allowlisted official-SDK adapter.
- `config/`: fixed research mode and project-local SQLite. `.env.example` is
  explanatory; broker credentials belong in the authenticated settings page.

`runserver` rejects non-loopback binds. Middleware checks the actual peer and
Host, ignores forwarded headers, and preserves the research dashboard's GET/HEAD
restriction. Only named authentication/settings routes accept CSRF-protected
POSTs. Broker settings require an active staff superuser. Callback state is
single-use and bound to that user, browser session, settings revision and a
10-minute deadline. There is no generic Django admin site or real ledger.
Fixed research safety settings cannot be enabled through environment variables.
This is a private local development server, not a public deployment.

SQLite is the permitted M1 fallback because PostgreSQL was not detected. A later
PostgreSQL move needs a **new dedicated database**, data export/import with hash
and count verification, and rerunning migrations/tests. Preserve the SQLite
source until validation; no PostgreSQL installation or database changes occur now.

## Next development step

M2 is the deterministic backtesting kernel: versioned ORB/EMA hypotheses,
completed-candle signals, later-bar entries, pessimistic same-candle ambiguity,
no/partial fills, effective-date costs and slippage, risk/cash limits, immutable
experiment manifests and chronological holdout tests. `StrategyDefinition`,
`BacktestRun`, `BacktestTrade`, `RiskPolicy` and `AuditEvent` belong there.
`SignalEvent`, scanner eligibility and `ShadowTrade` follow in their respective
later milestones. These are roadmap entries, not empty operational modules.

The owner authorized secure broker configuration and read-only service access
ahead of M2 on 1 November 2026. Scheduled downloading and historical ingestion
automation remain future work; bounded manual historical ingestion is available.
Universal scanning,
options archiving, indicators beyond baseline needs, and ML follow the governing
[master specification](docs/MASTER_SPEC_v1.3.md). No live execution is authorized.
No commits or pushes should occur until the owner approves them.

Implementation references checked on 2026-10-31: [Django 5.2 Python compatibility](https://docs.djangoproject.com/en/5.2/releases/5.2/)
and [NSE market timings](https://www.nseindia.com/static/market-data/market-timings).
The synthetic session hours model a normal cash session only; they do not certify
calendar validity or define rules for every Indian market segment.
