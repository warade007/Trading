# Decisions and change log

**Current governing spec:** v1.4.1 — 1 November 2026; legacy master-spec filename retained.

## Locked decisions

| Area | Decision | Reason |
|---|---|---|
| Purpose | Personal Indian-market **research and simulation** | Not a public trading product |
| Capital | Example ₹50,000; cannot afford real losses now | Real trading currently forbidden |
| Paid API | **Zerodha Kite Connect only** | Low cost; no Dhan/Upstox subscription |
| Scope | Universal eligible market scanner, not only NIFTY/BANKNIFTY | More options, but strict liquidity/risk selection |
| Market focus | Intraday research primary, scalping secondary | Lower sensitivity to fills and costs |
| Historical options | Capture current contracts from Zerodha before expiry; do not assume old expired minute data | Historical coverage limitation |
| ML | Train calibrated target-before-stop predictions after simple baselines | Confidence is not a guarantee |
| LLM | Optional offline/research assistant, not execution controller | Latency, hallucination and risk controls |
| Risk | No mandatory daily return; hard loss limits never overridden | Protect capital |
| Missed trades | Shadow ledger for skipped/unaffordable opportunities | Measure opportunity cost, not actual P&L |
| Hardware | Dell G15 5530 i7-13650HX, 16GB RAM, 512GB SSD | No hardware purchases now |
| Implementation | Python/Django local Windows; avoid unneeded Docker/WSL | Low resource cost |
| First milestone | M0 audit + M1 offline safe Django application | Build proof of data/engineering first |

## Changes relative to master blueprint v1.0

- Removed recommendation to subscribe to DhanHQ/Upstox or any additional paid historical option source.
- Expanded instrument universe from NIFTY/BANKNIFTY to eligible stocks, ETFs, indices and available options.
- Intraday became initial primary trading style; scalping remains secondary research.
- Added market intelligence, bid/ask depth constraints, news/event filters, probability calibration and opportunity scanner.
- Added strict separation of real vs synthetic/shadow, and unconditional live order prohibition for current financial readiness.
- Documented hardware resource state, storage recovered and local-only preference.

## Revision protocol

- Update this table and master spec whenever the owner changes requirements; record *date, version, requirement, reason, implementation impact*.
- Track open issues and experiment outcomes separately from facts and binding requirements.
- Never overwrite previous reports, metrics or dataset manifests when revising strategy parameters.

## 31 October 2026 — v1.3 repository decision

- Owner confirmed existing Git and provided canonical remote `https://github.com/warade007/Trading.git`.
- No authenticated write access to the remote has been established in this chat; instructions are staged in a downloadable pack.
- Codex must inspect repository history first, preserve existing work, and keep all real-order code disabled.

## 31 October 2026 — M0 audit completed

- The dedicated `C:\Automations\Trading` workspace was empty. Cloned the owner-provided remote there; clean `main` at `4c70b44`, no prior local changes or databases.
- Remote contains an instruction pack only. Restored expected `docs/` paths by copying the root spec and changelog; retained all original tracked files unchanged. The master-spec copy is byte-identical to the original. This `docs/` changelog is the ongoing engineering record.
- Inspected Python 3.13.7, Git 2.54.0.windows.1, Windows 11, i7-13650HX (14 cores/20 threads), 15.69 GiB usable RAM. Initially about 2.10 GiB RAM and 234 GiB disk free. No PostgreSQL executable or service detected; GitHub CLI/Node/uv were not on PATH.
- Used the already-authorized SQLite fallback and an isolated `.venv`; installed only four pinned free dependencies. No system configuration, unrelated project/database, Docker, WSL or service changes.
- Validation: repository status/history/remote inspected, complete governing documents read, `scripts/check_env.ps1` executed successfully. No scope/provider/risk-rule changes; governing spec remains v1.3.

## 31 October 2026 — M1 offline application completed

- Added the local read-only Django research dashboard with required safety banner, synthetic-data label, data coverage, quality report, provenance, UTC/IST semantics and dependency-free SVG candles.
- Added instruments, source-separated identities, immutable dated-snapshot import rules, import jobs, quality issues, candles, database constraints and initial migration. No empty future subsystem scaffolding.
- Added bounded, strict CSV/manifest validation; atomic rejected/accepted imports; SHA-256 raw archives; idempotency; full declared-session coverage; index-volume handling; exact contract checks; complete session-anchored 5/15-minute aggregation. Raw archive limit: 256 MiB; no automatic deletion.
- Added reproducible synthetic fixture, import/resampling/demo commands, PowerShell setup/diagnostics, README, environment example, ignore rules, tests and an actual HTTP smoke test.
- Verification: final **44 tests passed in 2.459s**, dependency check passed, Django check passed, migration drift absent. New local migration applied; demo contains **750 / 150 / 50** candles at **1 / 5 / 15 minutes**, 100% declared coverage and zero quality issues. Repeated import/resampling unchanged. HTTP smoke test passed.
- Port 8000 could not bind and was associated with an existing Java process. Preserved it; verified HTTP 200 on `127.0.0.1:8001`. Documented this local port adjustment without changing Windows settings. Measured app working set 48.14 MiB plus launcher 4.07 MiB, SQLite 200,704 bytes. Test servers stopped after checks.
- No broker integration, credentials, order APIs, subscriptions, commits, staging or pushes. All existing tracked files and remote history remain unchanged. New work remains local for owner review.
- Limitations: declared sessions are not a verified historical exchange calendar; no corporate-action certification, signals, trading simulation, scanner or ML yet. See README and VERIFICATION.md for exact operational limits and commands.
- Next: M2 deterministic ORB/EMA backtesting core with conservative fills, versioned costs, risk/cash constraints and chronological holdout validation. Read-only Zerodha integration remains M3; live execution remains unauthorized.

## 1 November 2026 — v1.4 secure broker configuration (owner-requested M3 slice)

- Owner explicitly authorized encrypted API settings, administrator-only dashboard,
  official interactive Kite authentication and a centralized read-only service,
  ahead of M2. No live execution, extra paid service, Git publication or credential
  sharing in chat is authorized. Updated the governing spec with this scope.
- Added BrokerConnection, BrokerSession (also holds hashed single-use login state)
  and BrokerAuditLog; reused Django users/sessions and the existing SQLite database.
  No duplicated market-data tables or automatic broker ingestion.
- Added independent Fernet keyring and Django signing key in a current-user Windows
  DPAPI vault outside the repo/DB; encrypted backup/restore and rotation commands.
  Blank secret updates preserve ciphertext; deletion clears credentials/tokens.
- Added administrator login, CSRF-protected settings/actions, strict callback
  `http://127.0.0.1:8001/kite/callback`, session/user/revision-bound state, expiry,
  reauthentication, explicit revocation/disconnect and sanitized status/audit data.
- Official SDK calls pass route/method and HTTPS-URL allowlists. Profile is the only
  connectivity test. Safe GET retries are bounded and paced; invalid sessions clear
  local token ciphertext. No order operation is permitted by either boundary.
- Existing M1 tests continue passing. New security tests use synthetic credentials
  and mocked network responses. Exact final results and database preservation checks
  are recorded in BROKER_CONFIGURATION.md. No real API test/login was performed.
- Additive auth/broker/session migrations applied after a project-local SQLite
  backup. Research dataset rows and hashes are checked before/after migration.
  No unrelated database, service or Windows setting changed.
- Final validation: **79 tests passed in 15.324 seconds**; Django and dependency
  checks passed; migration drift absent. All five research tables have identical
  content hashes and row counts after migration. Actual HTTP login/CSRF and prior
  research smoke checks passed. Server restarted on 127.0.0.1:8001 for owner use;
  owner must create the local administrator and enter broker credentials.

## 1 November 2026 — v1.4.1 source publication authorized

- Owner requested committing and pushing the completed project source. GitHub
  visibility was checked: repository is public. Owner explicitly confirmed keeping
  it public and pushing reviewed source; this overrides the earlier repository
  privacy preference, while all personal data and secrets remain private.
- Pre-publication verification: 79 tests passed in 22.504 seconds; system,
  dependency and migration-drift checks passed. Reviewed eligible files for
  embedded credentials, private keys, database files and oversized artifacts.
- Databases, the external DPAPI key vault, key backups, raw archives, logs, caches
  and virtual environments are excluded. Existing Git history is preserved;
  publication uses a normal push to main, without force or history replacement.
