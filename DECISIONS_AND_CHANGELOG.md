# Decisions and change log

**Current governing spec:** v1.3 — 31 October 2026.

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
