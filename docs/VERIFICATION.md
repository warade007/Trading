# M0 / M1 verification — 31 October 2026

All commands below ran in `C:\Automations\Trading`. Nothing was staged, committed
or pushed. Original tracked files are unchanged. The application and test data
are local; no broker credentials, subscription or market API was used.

## Audit

- Workspace initially empty; `git status` reported no repository. Owner remote
  was reachable through `git ls-remote https://github.com/warade007/Trading.git`.
  `git clone https://github.com/warade007/Trading.git .` populated this dedicated
  workspace. No second checkout or unrelated project was altered.
- `git status --short`, `git branch -avv`, `git log -5 --oneline`, `git remote -v`:
  clean `main`, `origin/main`, baseline `4c70b44`, documentation only.
- Read AGENTS.md, complete root MASTER_SPEC_v1.3.md and
  DECISIONS_AND_CHANGELOG.md, and GIT_WORKFLOW_WINDOWS.md before implementation.
  The requested `docs/` files were absent; the root documents were the supplied
  equivalents. Copied them to `docs/` and preserved originals.
- Python 3.13.7; pip 25.2; Git 2.54.0.windows.1; Windows PowerShell 5.1.26100.9818;
  Windows 11 Home Single Language; Intel i7-13650HX, 14 cores / 20 threads.
- Usable RAM 15.69 GiB; free RAM initially 2.10 GiB, later 2.49 GiB. Free C: disk
  about 234 GiB. PostgreSQL executables/services not detected; no installation.
- Globally installed Django was inspected only. Dependencies were installed in
  a fresh project `.venv`: Django 5.2.17, asgiref 3.12.1, sqlparse 0.6.0,
  tzdata 2026.3. No global package modification.

## Executed installation and checks

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/generate_fixture.py
New-Item -ItemType Directory -Path data -Force | Out-Null
.\.venv\Scripts\python.exe manage.py makemigrations research
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test --verbosity 2
& .\scripts\check_env.ps1
& .\scripts\setup.ps1
.\.venv\Scripts\python.exe scripts/smoke_test.py
.\.venv\Scripts\python.exe manage.py load_demo
.\.venv\Scripts\python.exe manage.py showmigrations
```

Observed results:

| Check | Actual result |
|---|---|
| Dependency installation | Four pinned packages installed successfully in `.venv` |
| `pip check` | No broken requirements found |
| Django `check` | No issues, zero silenced |
| Migration drift | No changes detected |
| Initial migration | `research.0001_initial` applied; `[X]` in showmigrations |
| Final automated suite | **44 tests, 2.459 seconds, OK** |
| First suite before removing inherited duplicate cases | 60 tests, 325.548 seconds, OK; no claim about the cause of the longer runtime |
| Demo import | Dataset 1 accepted; 750/750 declared 1-minute bars |
| Resampling | 150 complete 5-minute and 50 complete 15-minute bars; zero incomplete buckets |
| Repeated demo load | Same dataset unchanged; no duplicate candles |
| HTTP smoke | 200 with safety/demo labels, coverage and SVG; POST 405; bad Host 400; orders URL 404 |
| Diagnostic/setup PowerShell scripts | Successful, no machine-policy changes |

Tests cover finite/positive/tick-aligned OHLC, volume types and index-volume
absence, timestamps/timezones, duplicates, order, schema/encoding, file bounds,
missing edges/interior/full sessions, outlier warnings, snapshot/option expiry
validation, special declared sessions, exact OHLCV aggregation, first anchor,
session close, incomplete buckets, no cross-session aggregation, availability
timestamps, raw archives and quota, atomic rollback, idempotency, source
separation, conflicts, database constraints, dashboard output/escaping and
localhost/read-only restrictions. Tests use in-memory SQLite and temporary
archives, separate from the demo database.

## Actual local server check and resource use

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
# Failed: You don't have permission to access that port.
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001 --noreload
# From another terminal:
Invoke-WebRequest -Uri 'http://127.0.0.1:8001/' -UseBasicParsing -TimeoutSec 5
```

Port 8000 was associated with an existing `java` process (PID 36344); it was
preserved. No port reservation, firewall, service or Windows setting was changed.
Port 8001 returned **HTTP 200**. The smoke test also passed on an automatically
chosen loopback port (58550). All verification servers were stopped afterwards;
the dashboard is not left running in the background.

After a dashboard HTTP request, the Python app working set was **48.14 MiB**
(same observed peak), plus the venv launcher **4.07 MiB**. These are a point-in-time
Windows `Get-Process` measurement, not a guarantee for larger datasets. SQLite
file size was **200,704 bytes**. No additional service or parallel backtest worker
was installed.

## Preservation and exclusions

```powershell
git diff --exit-code
git diff --cached --exit-code
git diff --check
git status --short --ignored
git check-ignore data/research.sqlite3 .env .venv/Scripts/python.exe tests/fixtures/synthetic.csv
Get-FileHash MASTER_SPEC_v1.3.md,docs/MASTER_SPEC_v1.3.md -Algorithm SHA256
rg -n 'place_order|modify_order|cancel_order|kiteconnect|https?://' config research engine requirements.txt
```

Tracked-file diff and index diff were empty. New code/docs/fixtures are untracked
pending owner review; no staging. `data/`, `.venv/`, caches and `.env` are ignored;
the small synthetic CSV is eligible for future version control. Master-spec
copies have matching SHA-256. Runtime source/dependencies scan returned no
broker SDK, live-order method or outbound URL matches (rg exit 1 means no match).

## Remaining scope

M1 supplies the data-engineering foundation only. Session declarations do not
certify holidays, special sessions, corporate actions, contract eligibility or
market-data rights. User-supplied data is visibly unverified. No backtest results
or profitability claims exist. Scanner, backtesting, indicator/risk research,
shadow ledgers and ML are later milestones. M2 is next; real execution remains
outside authorization.
