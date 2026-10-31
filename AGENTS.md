# Codex agent operating instructions — private India trading research project

Owner-provided Git remote: `https://github.com/warade007/Trading.git`. Inspect and preserve local repo state before committing; this instruction is not permission to publish or alter remote history.

**READ FIRST:** [`docs/MASTER_SPEC_v1.3.md`](docs/MASTER_SPEC_v1.3.md), then [`docs/DECISIONS_AND_CHANGELOG.md`](docs/DECISIONS_AND_CHANGELOG.md).

## High-priority constraints

- PRIVATE personal software, Zerodha Kite Connect is the **only allowed paid market-data API**. No paid extra services, servers, packages or subscriptions without express owner permission.
- **RESEARCH-ONLY. NO REAL ORDERS.** Owner cannot afford financial losses. Never code live placement/cancel/modify endpoints in the initial application, never call them, never add a hidden bypass. Default config is offline and read-only. Simulated and real ledger data must never be mixed.
- Do not make profitability or 90%-accuracy guarantees. Index-only backtests are not option-P&L backtests. Expired option 1-minute histories cannot be retrieved from Zerodha after expiry.
- Use Python + Django; Windows 11 laptop Dell G15 5530, i7-13650HX, 16GB RAM, 512GB NVMe with ~236GB free; avoid Docker, WSL installation, heavy ML downloads or memory-hungry parallel jobs unless justified.
- Inspect existing files before editing. Do not touch unrelated projects, existing databases, Windows config, credentials, or backup folders.
- Never solicit/record OTP/TOTP, passwords, broker secrets; only official user-interactive Zerodha login if explicitly authorized later. Never store credentials in source or Git.
- Tests before declaring each milestone complete. Preserve research provenance, effective-date trading rules and accurate citations. Respect Zerodha/exchange market-data terms.
- Implement ONLY milestone M0 + M1 now, unless user explicitly requests a later milestone. State what was done, what remains and exact commands run.

## Engineering protocol

1. Audit workspace and installed Python, Postgres, git, resource headroom; report findings before destructive changes.
2. Make a runnable local offline Django app with sample/SYNTHETIC data; small increments and automated tests.
3. Keep business logic in pure Python `engine/`, not coupled to database or HTTP.
4. Use migrations, explicit UTC/IST timestamps, versioned strategy/data manifests, clear realistic cost models.
5. Disallow look-ahead; model nonfilled/partially-filled orders; treat ambiguous same-candle stops and targets pessimistically.
6. Every completed step should include tests and a short changelog update.
7. Do not ask for broker subscription or key during offline milestone. Ask only for genuinely blocking local prerequisites.

## First deliverable acceptance

- Django page available only on `127.0.0.1`, visibly stating **RESEARCH ONLY — LIVE ORDERS DISABLED**.
- Local CSV fixture -> validated 1-minute data -> deterministic 5/15-minute bars and data quality output.
- Unit tests, README, `.env.example`, `.gitignore`, Windows PowerShell setup and diagnostic script.
- No payment needed to run the project; no broker order API reachable.
