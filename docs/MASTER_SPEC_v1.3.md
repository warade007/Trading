# PERSONAL INDIA MARKET INTELLIGENCE & TRADING RESEARCH PLATFORM

**Master specification:** v1.4.1 (legacy filename retained for existing links)<br>
**As of:** 1 November 2026<br>
**Owner:** Single private Indian retail user<br>
**Git repository:** `https://github.com/warade007/Trading.git` (owner-approved public source; personal data and secrets remain private)<br>
**Implementer:** Codex in VS Code; Python/Django<br>
**Status:** Design approved for **local research, backtesting, and compliant simulation only**. No live trading authorized.<br>
**Authority:** This document supersedes earlier proposal details when they conflict, especially paid-data-provider suggestions and live execution settings. Retain previous design documents as archives, never as sources of conflicting requirements.

> **Non-negotiable economic truth:** We aim to research robust, long-run positive *net* expectancy, but cannot guarantee any profit, 90% success, safe stop fills, or reliable predictions. The owner explicitly cannot afford losses now. Real-money placement must remain technically impossible in the default system. Do not let agent confidence or profit targets override this.

---

## 0. How the coding agent should use this document

1. Read `/AGENTS.md`, this entire specification, and `/docs/DECISIONS_AND_CHANGELOG.md` before coding.
2. Treat documented requirements as design decisions, **not** proof that a strategy works. Mark unverified claims and constraints clearly.
3. Prefer a working, small, fully tested slice over scaffolding dozens of incomplete modules. Work through the implementation gates in order.
4. Inspect the existing repository, OS, Python, PostgreSQL, and environment before installing or modifying anything. User's existing laptop contains other projects and critical files; never touch unrelated folders, databases, installed software, games, and Windows configuration.
5. Preserve secrets and operational controls; never ask for the Zerodha password, TOTP seed, or trading account credentials. Use the official Kite login flow only when the user is ready.
6. For changes to market rules, exchange contract specifications, SDK compatibility, or broker restrictions, re-verify against live primary documentation before implementation. Source links below are references, not permanently valid assumptions.
7. Maintain a clear daily engineering progress record and tests. This is a **development project**, not an instruction to place trades.

## 1. Mission and success definition

Build a **personal, low-cost, universal Indian-market opportunity research system** that screens eligible instruments and compares multiple strategy families. Research whether any yields robust after-cost gains on **unseen periods**, and accurately record trade opportunities that could not be executed due to budget or risk restrictions.

The system will eventually support intraday and scalping strategy evaluation, adaptive entries/exits, capital/risk-aware sizing, probability calibration, selective shadow trade tracking, and possibly supervised broker execution; however **LIVE_TRADING_ENABLED=false** for the current project and all release gates.

Success is measured by data integrity, reproducibility, low false-confidence, realistic fill simulations, strict cost accounting, reproducible statistical tests, risk containment, and no accidental orders. We do not optimize simply for win rate, daily target, trade count, best retrospective equity curve, or highest gross return.

### Explicit owner preferences and constraints

- Single personal user, **not a commercial/public service**; private repository and local data preferred.
- **Only one paid market API:** Zerodha Kite Connect paid plan, currently advertised ₹500/month before applicable taxes. No DhanHQ, Upstox Plus, paid news provider, premium option history, cloud servers, or required additional monthly subscriptions.
- Laptop: **Dell G15 5530**, 13th Gen **Intel i7-13650HX** (14 cores / 20 threads), **16 GB RAM**, **512 GB NVMe SSD**, NVIDIA RTX GPU present (exact model unverified), Windows 11. After uninstalling unused Steam games, ~236 GB free. The 16 GB RAM was previously at 88-92% with many apps open; inspect current resource usage. Do not buy RAM/SSD or install heavyweight services without a measured need.
- Personal Zerodha account; live credentials and paid access **not yet assumed**. Provide fully working **OFFLINE/DEMO** workflows without any API key.
- The user initially described ₹50,000 account capital, but it is **an illustrative simulation default, not permission to use real money**.
- No forced daily return objective and no profit ceiling; **hard daily loss limits and per-trade exposure/risk rules**, in percentages of equity, must exist for future gated live execution.
- Instrument universe should not be limited to NIFTY/BANKNIFTY. Scan only actually eligible, liquid, affordable Indian stocks, ETFs, index products and supported options; market support must reflect actual instrument master, broker permissions, venue and contract rules.
- **Intraday is primary** (5- and 15-minute signals, optionally 1-minute execution refinement); **scalping secondary** (1-minute research / simulation first; later only with adequate order-book/tick quality).
- Capture active options regularly into private historical archives before expiry, with exact contract ID, strike, CE/PE, expiry, instrument token, lot size and timestamp. Zerodha does **not** provide accessible expired option minute candles after contracts expire. Existing index/stock historical signals must **not** be sold as tested historical option profits.
- Compare fixed targets vs partial exits vs ATR/trailing exits vs adaptive ML exits. Train models to predict specific verifiable events, not a guaranteed gain.
- Opportunity scanner records ALL eligible signals and rejection reasons. Shadow trades should be tracked with explicit synthetic/simulated fills and should not be conflated with actual trades.
- LLM, if added, is a **non-executing research/news assistant**. Do not place an LLM inside time-critical execution or let it bypass deterministic controls. Avoid paid LLM access by default.

## 2. Data available from the sole paid provider

### Zerodha Kite Connect

- Historical candles for **supported current/accessible instrument tokens**; 1-, 3-, 5-, 10-, 15-, 30-, 60-minute and day candle intervals in currently documented API. Pull in API-safe date chunks and throttled batches; do not assume unlimited historical backfill per request.
- Instrument master (download daily and retain immutable dated snapshots); each contract has exchange/tradingsymbol/token/expiry/strike/type/tick/lot fields as supplied.
- Live KiteTicker/WebSocket for subscribed instruments; 3,000 instruments per connection and 3 WebSocket connections/API key stated in current docs. Use `ltp`, `quote`, `full` modes selectively; full mode offers best five bid and ask levels for eligible tradable contracts, plus volume and F&O OI fields where available. Index packet payloads are structurally different and **do not supply an index traded volume**.
- Market depth is **displayed five levels**, not a full market-by-order feed. Queue position, hidden liquidity, aggressive trade initiator, exact cancellations, and future price pressure are **not observable**; never label model outputs as guaranteed.
- No six-month expired-option intraday history through Kite. An active option's history should be pulled before expiry; availability after expiry is unreliable.
- The account session is generated through official broker login; access tokens expire by the next trading day, and there is no promise of automated login renewal. **Never bypass login, store OTP seed, or automate CAPTCHA/TOTP.**
- Brokerage/order compliance: order placement through whitelisted static IP per Zerodha's current requirement; respect exchange algo rules and current permitted order types. **No execution adapter enabled now.**
- Historical candles have OHLC but generally **no historical bid/ask, microstructure or trade sequence**. A 1-minute bar touching target and stop cannot establish which hit first. Assume pessimistic or classify unresolvable; never infer perfect fills.
- Subscription and market-data retention/processing must comply with Zerodha, exchange and applicable vendor licensing terms, even in private use; do not redistribute raw feeds.

### Free/low-cost supporting information (verify licensing/availability)

- NSE/BSE public circulars and company announcements; market holidays and segment contract specifications; RBI calendar; exchange disclosures.
- Public news headlines as permitted by provider terms, with accurate publication and detection timestamps. No scraping behind login, automated circumvention, or invented news timestamps.
- Computed technical indicators from actual available candles; no external cost.
- Free official aggregate daily reports can supplement broad context, **never replace expired options 1-minute contracts**.
- Never silently fetch data from a second paid API or claim access to missing history.

### Explicit limitations to show in dashboard

1. Expired option minute history before our archive date: **UNAVAILABLE**, unless legitimate user-supplied data is imported with provenance.
2. Historical depth / intrabar event ordering before capture: **UNAVAILABLE**.
3. Option P&L simulated from index signal without exact historical contract data: **NOT A VALID OPTIONS BACKTEST**.
4. News timestamps/rights unclear: **NOT A QUALIFIED CAUSAL FEATURE**.
5. Simulation built from synthetic fixture data: mark **SYNTHETIC DEMO — NOT ACTUAL PERFORMANCE** conspicuously.

## 3. Markets and staged instrument universe

The universe is configurable, automatically dated, and constrained by exchange instrument master and available user/broker permissions. Default phase-one research:

- Spot/reference: NIFTY 50, BANK NIFTY, SENSEX, relevant sector indices where provided.
- Intraday research: top liquid NSE cash stocks and eligible ETFs; **calculate real traded volume and VWAP for securities, not index values**.
- Derivatives research: currently accessible, highly liquid index and selected stock CE/PE; emphasize **long-option research** initially; avoid selling/naked exposure in first release.
- Index futures/OI when genuinely available, used as market context; no assumption continuous *minute* historical futures series beyond available contracts.
- Diversification candidates: liquid equity trend following (can be less sensitive to option expiry/IV) and potentially slower trend trades, all controlled by intraday-only vs overnight policy.

Contract calendar must be **as-of-date**: lot sizes, holidays, strike grids, index weekly/monthly expiries, stock-option physical settlement, market-wide position limits and broker restrictions change. Never hardcode today's lot size or expiry weekday across prior years. No default assignment to physically settled stock options in live mode.

## 4. Strategy families to implement and compare

Each strategy is a versioned, pure function from **as-of available data** to an intent and explanation. Don't claim any family is profitable until tested.

1. **Opening Range Breakout (ORB):** configurable first 15/30 minutes range; breakout with price acceptance, sector/benchmark context and risk-adjusted entry. Pros: transparent directional signal, testable. Cons: false breakouts, gap shocks, churn, time-of-day dependence.
2. **Trend pullback / EMA continuation:** EMA regime + ATR/structure + pullback and confirmation. Pros: can capture strong moves. Cons: whipsaws, lag and overfitting in ranges.
3. **VWAP reclaim/rejection:** ONLY when true trade volume exists for the tradable instrument (stock/ETF/future); don't compute 'index VWAP' from zero synthetic volume. Pros: intraday context. Cons: noisy around news and illiquid contracts.
4. **Volatility-adjusted momentum:** momentum relative to historical intraday vol; avoid spreads/slippage regimes. Pros: regime-dependent captures. Cons: crashes, rapid decay.
5. **Range-bound mean reversion:** regime validated with volatility/trend, stops; never average down. Pros: may diversify trend family. Cons: runaway trending days and adverse selection.
6. **Scalping hypothesis lab:** 1-minute momentum / order book imbalance / pressure changes; research-only until tick/quote archive & credible execution simulator. Five-level displayed bid sizes do not equal guaranteed buy pressure.
7. **Event avoidance / news filter:** deterministic calendar blackout windows plus optional tagged headline risk. Prioritize *avoiding* sudden events over predicting them.

A strategy's signals must define instrument, side, exact contract (when option), as-of entry time, eligible slippage/fees, invalidation, desired exit policy, max holding time, model version and immutable parameters. Require config schemas and semantic strategy versioning.

## 5. Technical indicator and intelligence feature policy

**Features to begin with:** OHLC, volatility/ATR, returns, 9/21 or similar EMAs (hypotheses, not universal settings), first/previous-session high-low, prior day close, ORB boundary, realized volatility, gaps, **equity/futures** VWAP, relative volume, trend slope, momentum, drawdown/reversal patterns, opening-range width, time-of-day, exchange holiday/event indicator, sector-relative movement, days/hours to contract expiry, option premium spread/OI when present.

**As archived live data accumulates:** five-level quoted depth imbalance, changes in displayed buy/sell quantity, quote age, spread, option premium changes, option-IV/Greek *estimates with documented inputs/model uncertainties*, event/news timestamps.

**Feature cautions:** RSI/EMA/MACD are correlated transforms of same price stream; more indicators can worsen overfit. RSI is not universally overbought/oversold; a breakout is not a guaranteed continuation. OI itself does not say who is right. IV may crush option premium as index rises. News can lag. No buying-pressure score is a probability of gain unless calibrated. Indices are non-traded reference instruments and do not have ordinary index-executed volume or five-deep order books.

Every feature must have `available_at_utc` and a missing-data policy. No indicators from incomplete future candles or after-the-fact event labels. Feature matrix must carry provenance and drift statistics.

## 6. Historical data engineering

### Storage design

- Django/PostgreSQL for instrument snapshots, ingest jobs, strategy metadata, trade-level ledgers, data manifests, annotations and experiments.
- Parquet (partitioned by provider/venue/instrument/trading_day_IST) for large raw and derived time series. DuckDB/Polars for queries; keep memory usage bounded.
- Local private storage under project `/data` ignored by Git. Backup to an owner-approved drive when appropriate, not to a public service.
- Store immutable raw data, derived normalized data, and separate provenance metadata with fetch timestamp, SHA-256, source URL/endpoint, code version and quality flags.
- All timestamps UTC with explicit IST trade-session view. A candle timestamp must be explicitly defined as **bar open** or **bar close**; no silent resampling offset.
- Missing bars remain missing and flagged; zero-trade minutes and actual closures must be distinguished. Do not interpolate option premiums for executions.
- Retain and validate exact option instrument mapping: token, `exchange`, symbol, underlying, strike, expiry, CE/PE, lot, tick size, snapshot-as-of date. Option one-month chain rolling ATM is NOT same as one fixed strike contract.

### Data ingestion sequence

A. Safe offline synthetic fixture and CSV import with schema validation.<br>
B. Zerodha instrument master date snapshots; identify available index, cash, ETF, future, option instruments.<br>
C. Historical 1-minute downloads for liquid stocks/indices in rate-limited batches, initial 9 months if available.<br>
D. Build 5/15-minute derived candles from 1-minute records (session-aware).<br>
E. Active-option snapshot & end-of-day candle pre-expiry archive; daily integrity and backfill reports.<br>
F. Future live quote capture and 5-deep depth snapshots (if permitted by data terms), bounded by disk and API capacity.<br>
G. News/event ingestion only with clear source and legal reuse terms.

Handle retry/backoff/jitter, throttling, idempotent page/candle upserts, and recovery after crash. No uncontrolled parallel historical API calls. Maintain current coverage % by instrument + trading day and exact data gaps.

## 7. Realistic event-driven backtesting

### Required accuracy rules

- Research period: **older 6 months** for exploration/training, **latest 3 months untouched** as chronological holdout. Later add rolling walk-forward, purged/time-embargo validation and forward shadow evaluation. Do not tune on holdout and then still call it unseen.
- Point-in-time instrument membership, corporate actions, market sessions, exchange calendar, historical lot size, expiry mechanics; account for delisted/stopped symbols and avoid survivorship bias.
- Signals use completed candles; do not allow same-candle close-to-close fills with lookahead. Entry at a later eligible market state with conservative price assumptions.
- If target and stop touch same 1-minute candle, follow pessimistic resolution or mark ambiguous; never assume target first. 1-minute candles do not prove fill liquidity or order priority.
- Execution cost engine: brokerage/order count, GST, STT, exchange transactions, SEBI turnover, stamp duty, state-specific and security-specific where applicable, spread, slippage, partial fills, market impact. Rates and fees **versioned by effective date and product/venue**; don't hardcode timeless rupee constants.
- Limited cash and margin, no negative cash, available free funds, lot-size indivisibility; gross premium exposure cap; no borrowing/leverage to recover losses; correlated sector/index exposure grouping.
- Orders and fills separate entities; trade entry/exit can be partial or rejected; status transitions and idempotency.
- Compare exit policies using the *same entry signals*: fixed target, stepwise trailing stop, partial T1/T2/T3, adaptive risk/ML expected value. Different partial exits imply different brokerage and charge counts.
- Cost-adjusted breakeven prices from realized fills, remaining lots, fees and buffer; stop-limit orders are not guaranteed fills.
- Metrics: expectancy per trade, all-in net P&L, annual/monthly performance, drawdown, tail risk/expected shortfall, win rate, profit factor, exposure time, worst losing streak, max adverse/favorable excursion, trade frequency, cost share, slippage sensitivity, opportunity selection error and capacity constraints.
- Label **simulated** results separately from real broker statements; no fake 90%-confidence claim.

### Statistical discipline

- Establish baseline buy/hold (where meaningful), random/event-only baselines and simple strategies. Benchmark ML against non-ML on identical periods.
- Record universe, features, selection criteria and strategy rule versions **before** running holdout. Defend against selection bias and repeated strategy mining.
- Calibrate confidence for event: e.g. `P(target + spread + costs is reached before stop within H minutes for THIS contract)`; measure reliability curves, ECE/Brier score, sample counts by expiry and market regime.
- Only consider backtested EV after costs and uncertainty. A 90% win rate with outsized loss may have negative EV. Do not promote strategies on small-sample high win-rate alone.
- Use bootstrap / block bootstrap, slippage stress, fee stress, event shock, no-fill and downtime scenarios. A model failing data quality checks cannot trade.

## 8. Smart entry, adaptive exit and multi-lot management

Owner's illustrative position: long 3 lots premium 120, initial stop 115, exit one at 130, one at 140, one at 150, raising protective stop on remaining lots after targets. **These prices are examples, not strategy defaults or a promise of gain.**

Requirements:
- Support configurable partial exits by **actual filled units and valid lot quantities**; no double-selling or orphaned protective orders.
- Move stop only under defined conditions. Compute cost-adjusted breakeven including fees and an uncertainty buffer; no claim that stop ensures profit.
- Continuation model estimates `P(next_target_before_stop | available_now)` and magnitude, or expected net utility across HOLD / SELL_SOME / SELL_ALL / TRAIL; must validate out of sample. A 30% reversal probability doesn't alone imply exit.
- Protect from order-state races, duplicate submits, stale bid/ask, gaps, liquidity and tick size; atomic state + broker reconciliation in future.
- Assess end-of-session exits, holidays, settlement, market-wide limit, and unattended exposure.
- Both long CE/PE position exit and equity exit need their own applicable rules.

## 9. Risk governance (hard stops, no override)

**Live execution currently DISABLED, even when there are apparent perfect signals.** Risk policy for simulations and future approval:

- Configurable account equity reference: start-of-day equity, not static ₹50,000.
- No mandatory daily profit and no profit ceiling.
- Illustrative research-only soft session loss warning **1%**, hard shutdown **2%** of start-of-day equity, counting realistic mark-to-market, realized results, pending exposure and fees. The owner previously suggested 5%/10%: DO NOT set those as defaults; unacceptable for this financial constraint.
- Illustrative per-trade risk cap **0.25–1.0%**, subject to model calibration and minimum one-lot affordability. If one lot exceeds permitted risk, **SKIP**.
- **No override of hard loss shutdown** even if the model claims 80, 90, 99.9% confidence; move to shadow tracking. Do not allow martingale/averaging down/recovery trades.
- Total deployed premium cap, correlated exposures cap, simultaneous-position cap, order-rate cap, fee/turnover budget, late session restrictions, stale-data kill switches, disconnect handling and manual emergency stop.
- Risk-budget lot sizing: `min(floor(budget / plausible_loss_per_lot), floor(premium_exposure_cap / premium_per_lot), affordable_lots_by_cash, correlated_portfolio_limit, broker_limit)`; if minimum one lot unavailable, shadow only. Illustrative bounded confidence tiers only *after* verified calibration, never linear 100%-capital at 80% prediction.
- If in future live, use broker-allowed orders, whitelisted source IP, maintain reconciliation; no credential/script bypass. Safety constraints never depend on LLM content.

## 10. Universal scanner, daily discovery and shadow ledger

Two-stage selection:

- Broad screening with available historical/market snapshot data and liquidity, price, spread, circuit, volume, event, confidence availability, capital affordability, and contract restrictions.
- Detailed per-instrument signals on shortlisted products using exactly as-of inputs and existing instrument mapping. Rank by estimated risk-adjusted **net expectancy** and independent exposure, not by raw probability alone.
- Capture full reasoning, provenance, feature snapshot, predicted probability, confidence calibration status, correlation, rejection reason, expected fill assumptions.
- Every candidate gets a deterministic status: `QUALIFIED`, `SKIPPED_LOW_EDGE`, `SKIPPED_COST`, `SKIPPED_LIQUIDITY`, `SKIPPED_RISK`, `SKIPPED_NO_CAPITAL`, `SKIPPED_EVENT`, `SKIPPED_DATA`, `SHADOW_ONLY`, `EXECUTED_REAL` (future only).
- Shadow simulate rejected or unavailable-capital signals (when permitted by data rights) with realistic costs and simulate no-fill if appropriate. Separate `realized_real_pnl` from `simulated_shadow_pnl` at DB, API and UI levels. Never add them together as real returns.
- Prevent repeated near-identical events from inflating success count. Track independent opportunities vs continuous signal time-series.

## 11. ML and LLM architecture

Start without paid AI services:
- Baseline deterministic strategies and no ML first.
- CPU-friendly LightGBM/XGBoost/scikit-learn as experimental probability estimators with chronological and purged validation; explicit class balances, calibration, drift and explanation.
- Account for transactions, holding horizon and target-before-stop event labeling using exact contract data. No invented labels from underlying prices for option P&L.
- Model registry with training window, feature/strategy version, dataset hash, parameters, metrics, approved status and retirement rules.
- LLM as *optional research-only tool* for reading approved news, summarizing errors, proposing hypotheses, comparing experiments and documenting decisions. Never send credentials, order tokens, account statements or proprietary market data without explicit owner approval and provider rights.
- LLM may NEVER place orders, alter risk limits, enable live mode, approve a model, or change strategy without tested human review.

## 12. Django architecture and suggested repo layout

```text
trading-research/
  AGENTS.md                         # agent instructions
  README.md                         # setup, run, safety banner
  .gitignore / .env.example
  pyproject.toml                    # pinned deps and test/lint config
  manage.py
  config/                           # django settings/asgi/urls
  apps/
    core/                           # user settings, audit, feature flags
    instruments/                    # exchange master snapshots, calendars
    marketdata/                     # adapters, ingest jobs, quality reports
    research/                       # strategy registry, signals, experiments
    backtesting/                    # event engine, fills, fees, metrics
    models_lab/                     # ML experiments/calibration
    scanner/                        # screen/rank candidates
    shadow/                         # simulation-only order/trade ledger
    risk/                           # deterministic risk governor
    dashboard/                      # web views, HTMX/API visualization
    broker_zerodha/                 # read-only first; live disabled / absent
  engine/                            # framework-independent pure Python core
    indicators/ strategies/ simulation/ cost_model/
  scripts/                           # safe bootstrap and diagnostic scripts
  docs/
    MASTER_SPEC_v1.3.md
    DECISIONS_AND_CHANGELOG.md
    DATA_DICTIONARY.md (generated later)
    RUNBOOK.md (generated later)
  tests/ unit/ integration/ fixtures/
  data/                             # ignored: licensed raw data, parquet, results
  logs/                             # ignored: redacted operational logs
```

Prefer Django 5.x LTS/current supported stable version at time of implementation, but check installed Python and package compatibility first. PostgreSQL local if already installed; otherwise document a compatible setup rather than altering an unrelated DB. Redis/Celery optional until genuinely needed; phase one can use a simple synchronous worker/management command. DuckDB, Polars/Pandas, PyArrow, plotly/htmx are good no-license candidates. No Docker, WSL, virtualization, GPU package, or separate infrastructure required to start on Windows. Use `venv`, safe commands, local-only `127.0.0.1` binding and moderate batch sizes on 16 GB RAM.

**Secrets and control:** use `.env.example`, never commit real `.env`, keys, cookies, tokens or broker info. Deactivate Django DEBUG if ever exposed beyond localhost. No public web endpoint, no broker-order endpoint enabled. For signed-in future mode use session handling, CSRF, encryption at rest as applicable, audit trail and explicit two-step activation separate from model.

## 13. UI / user workflow

Initial navigation:
1. **Overview**: large banner `RESEARCH MODE — REAL ORDER PLACEMENT DISABLED`; data coverage, candidates, experiments, current data costs, machine health.
2. **Market Scanner**: venue/type, spread/liquidity, strategy, confidence calibration, reasons to reject.
3. **Historical Data**: instruments, date ranges, downloads, QA gaps, option contract chain coverage, source version and storage footprint.
4. **Strategy Lab**: compare ORB/EMA/VWAP/range versions with reproducible config; avoid enabling all strategies at once.
5. **Backtest**: time spans, cost settings, replay trades and candle-level explanations; drill-down to exact entry/exit inputs.
6. **Performance**: out-of-sample equity, after-cost net expectancy, drawdown, reliability plots and sample-size warnings.
7. **Shadow Ledger**: blocked signals, hypothetical outcomes and reason codes; labels very distinct from real.
8. **Risk Settings**: read-only defaults plus explicit simulation settings; no live toggle currently.
9. **System Health**: resource budget, memory, SSD free, data ingestion failures, credentials status without revealing secrets.

Mobile-responsive is nice, but local desktop is primary. Avoid unnecessary frontend build complexity (Django templates + HTMX + lightweight charts are sufficient).

## 14. Operating on the owner's Dell G15 laptop

- Do not modify owner files in `C:\Automations`, prior repositories, personal backups, or the Windows installation.
- Target initial RAM use under ~3 GB additional for baseline Django+DB+batch job; measure, don't promise exact footprint. Pause large parallel backtests when RAM pressure occurs; limit number of workers.
- SSD has ~236 GB free as last reported; set maximum local data-cache budget and quotas; report per-provider storage size, cleanup only generated and validated caches with explicit user approval.
- Keep separate `raw` and normalized files, backup the database and research definitions, use no surprise cloud syncing.
- Windows local timezone is IST; all internal storage UTC with tz-aware datetime.
- The laptop may sleep/disconnect; production trading on local machine therefore not reliable until explicit safety design, UPS/connectivity/static IP are validated. No active trading during this phase.

## 15. Compliance and safety research checklist

Before any real order capability is even proposed, verify **current** Zerodha retail algo rules, static IP requirements, exchange tagging/registration, instrument restrictions, NSE/BSE operating times, contract spec/settlement, accepted order types (including index-option SL-M restrictions), brokerage + tax schedules, API order/rate limits, data use licensing, session expiry, outage and reconciliation behavior. Never infer that merely having an API key authorizes unrestricted algo activity.

For our current software, use no network write actions to the broker even if an API key is present. Call the safe current market-data API only when user authorizes read-only authentication. Have a hard isolated `BrokerReadOnlyClient` with no place/modify/cancel methods in phase one. Import execution worker in a later separately approved milestone only.

## 16. Data and execution test suite — minimum

- Interval aggregation strictly within exchange session; exact timestamp semantics and holidays.
- Duplicate candles, missing bars, stale packets, wrong exchange symbol, invalid/negative OHLC, inverted highs/lows, outlier handling.
- Invalid contract on date, expiry change, strike remapping, lot size historical changes, corporate actions/physical settlement.
- No same-bar lookahead, double-triggered target/stop pessimistic or ambiguous, next-bar fill, no/partial-fill, slippage and commissions.
- Entry-side cash and margin check, lot rounding, capital no-negative, repeated signals dedupe, correlated risk and daily hard shutdown.
- Confidence calibration dataset separation, no overlapping future label leakage, slow regime shifts, minimum-sample warnings.
- Simulated vs actual trade entity separation, ledger reconciliation across restarts, no trade initiated by research-only route.
- Token missing/expired, missing subscription, API throttle/retries, static IP requirement flagged without using live order API.
- Deterministic fixtures: specify synthetic nature and input seeds. An end-to-end demo must execute without credentials or network.

## 17. Milestone plan (incremental, each with acceptance criteria)

**M0 — Audit + plan (NO CODE until brief inspection):** inventory existing project files, Python/venv, PostgreSQL, git, Windows memory free/disk. Report what exists, what is missing, proposed changes and safety tests. No destructive commands.

**M1 — Local runnable offline app:** minimal Django project, SQLite fallback only if Postgres inaccessible (document migration), `RESEARCH_MODE=true`, home dashboard/status, sample immutable instrument/candle schemas, ingestion CLI for synthetic fixture CSV, data QA, 1-minute -> 5/15-minute resampler, tests, README and `.env.example`. Must run without Zerodha subscription/key. No live order code.

**M2 — Backtesting kernel:** deterministic ORB and EMA baseline, fee/slippage config, signal/entry/exit pure core, conservative fill sequencing, time-based exits, versioned experiments, replay and result metrics with tests.

**M3 — Zerodha read-only integration:** credential input by owner only, official login flow, instrument daily snapshot, rate-limited historical downloader for index, cash, ETF; coverage QA and UI; never log sensitive auth; data ingestion remains opt-in. Confirm subscription status without attempting unauthorized endpoints.

**M4 — Broad research universe:** liquidity screens, sector/benchmark features, VWAP and ATR only where valid, market events calendar, comparative tests with holdout and leakage controls.

**M5 — Current option data archive:** exact contracts, pre-expiry historical current option retrieval, careful live tick/quote snapshot capture within licensing rights, quality/reconnect/restart handling, status `historical options before capture date NOT available`.

**M6 — Shadow engine + adaptive manager:** simulated partial exits and trailing stops, shadow ledger for unaffordable/rejected signals, capital allocation limits, score calibration and reliable reporting.

**M7 — ML lab + optional LLM research:** baseline-vs-ML comparison, calibration, drift, news risk research, no auto-order function.

**M8 — Future real execution**: BLOCKED until owner explicitly requests it in a later conversation, can afford entire potential loss, and compliance + risk + data integrity + live resilience gates are met; involves separate review. No task in current work authorizes this.

## 18. First sprint detailed delivery (what Codex should do NOW)

1. Inspect current workspace and relevant installed tools; show compact findings.
2. Initialize private git repo **only in current dedicated workspace** if not already initialized; write `.gitignore` before generating data.
3. Create local `venv` and a pinned reasonable dependency set after inspecting installed Python. Avoid implicit `pip install` outside venv.
4. Build running Django skeleton and index home page with impossible-to-miss `RESEARCH ONLY / NO LIVE ORDERS` banner.
5. Define initial DB schema/models: `Instrument`, `InstrumentSnapshot`, `Candle`, `DataIngestJob`, `DataQualityIssue`, `StrategyDefinition`, `BacktestRun`, `BacktestTrade`, `SignalEvent`, `ShadowTrade`, `RiskPolicy`, `AuditEvent` (create lean M1 subset and stub remaining with clear roadmap rather than overengineering).
6. Implement CLI `import_candles` from local CSV fixture; strict schema parsing and provenance; idempotency and gap report; atomic write.
7. Implement `resample_bars` (1m → 5m/15m exchange local) with unit tests for first-bar anchor and 15:30 session close.
8. Build demo dashboard with coverage summary and synthetic candle chart if chart dependency is light. All numbers labeled DEMO.
9. Provide safe `scripts/check_env.ps1` that inspects Python/PowerShell, RAM availability and C: free space only; no privileged changes.
10. Run tests and migration checks; report exact commands and observed pass/fail, code paths and next sprint. Do not claim unrun tests pass.

### Mandatory exit criteria for M1

- `python manage.py check` and `python manage.py test` / `pytest` pass for created tests.
- Owner can run server at `http://127.0.0.1:8000` without an API key.
- Zero function/API endpoint can submit a real trade.
- `data/`, `.env`, credential caches, large binary and local SQLite are ignored by Git.
- Data coverage/quality output distinguishes real from synthetic.
- No changes to unrelated applications, Windows settings or other workspaces.
- README explains exact Windows PowerShell steps and any prerequisite installs the owner must explicitly approve.

## 19. Open questions / verification gates (do not block M1)

- Confirm current Python executable/version and any existing pgAdmin/PostgreSQL service; never infer PostgreSQL is installed because pgAdmin is visible.
- Confirm RAM utilization after restarting and closing unused apps; avoid concurrent heavy jobs until there is headroom.
- Confirm Zerodha subscription purchased and broker account enabled only at M3.
- Confirm acceptable terms for keeping self-collected personal market data; make storage retention configurable.
- Verify venue/contract list availability for SENSEX options before assuming symbol/data support.
- Historical exact options data absent before capture date: mark as permanent coverage limitation, not a bug that future software can fix without another licensed source.
- Future real mode must pass separate financial/risk readiness and explicit approval; account capital amount may change.

## 20. Version control / change governance

- Update **this file** and `/docs/DECISIONS_AND_CHANGELOG.md` together when the user changes strategy, scope, provider, or risk rules.
- Bump spec minor number for a new major capability/design decision; patch for corrections. Preserve a copy of previous approved spec in Git history.
- Every strategy experiment must record strategy git commit, input-data hash/version, hyperparameters, calibration method, timestamp of train/validation/holdout, charges and software environment.
- Do not overwrite holdout results or retroactively change backtest dataset.
- Treat results achieved on historical data as **research evidence**, not future-profit guarantees. Include sample-size and survivorship warnings.

## 21. Official source links for implementation checks

- Kite paid API product and pricing: https://zerodha.com/products/api/
- API FAQ, market data and login behavior: https://support.zerodha.com/category/trading-and-markets/general-kite/kite-api/articles/kite-connect-api-faqs
- Historical candle specification: https://kite.trade/docs/connect/v3/historical/
- Expired options unavailable: https://support.zerodha.com/category/trading-and-markets/charts-and-orders/charts/articles/historical-data-for-expired-f-o-contract
- Live quote modes and five-level depth: https://kite.trade/docs/connect/v3/websocket/
- Instruments and quote docs: https://kite.trade/docs/connect/v3/market-quotes/
- Static IP requirement for live order placement: https://support.zerodha.com/category/trading-and-markets/general-kite/kite-api/articles/static-ip
- Official Python SDK: https://github.com/zerodha/pykiteconnect
- NSE retail algorithmic trading: https://www.nseindia.com/ (look up latest circulars/FAQs when implementing live execution)
- NSE contract spec / lots / expiries: https://www.nseindia.com/static/products-services/equity-derivatives-contract-specifications

**End of governing specification v1.3.**


## 22. Owner-provided repository and online documentation workflow

- Canonical remote: `https://github.com/warade007/Trading.git` (do not assume the current local workspace points to it).
- First inspect `git status`, `git branch --show-current` and `git remote -v`; do not overwrite existing branches, history, uncommitted changes or unrelated files.
- Keep `AGENTS.md`, this master spec, `docs/DECISIONS_AND_CHANGELOG.md`, and future `docs/EXPERIMENT_LOG.md` version-controlled.
- Keep repository **private** unless owner explicitly chooses otherwise; never commit `.env`, tokens, broker account identifiers, proprietary/downloaded raw market datasets, trading statements, huge model weights or personal information.
- Owner may locally commit/push after reviewing `git diff --cached` and ensuring no secrets. Do not attempt automated GitHub publication without authorized access.
- Once committed and pushed, GitHub provides a persistent online reference link to the master spec on the actual branch. Confirm the real branch first; never claim the link was published before push succeeded.
- No real broker order placement implementation is authorized merely because a remote repository is configured.

## 23. v1.4 — owner-authorized secure broker configuration, 1 November 2026

The owner explicitly requested this read-only M3 slice ahead of the M2 backtesting
kernel. This addendum governs the new module; M2 and remaining ingestion/scanner
milestones are not declared complete. The original root `MASTER_SPEC_v1.3.md`
is retained unchanged as the prior approved baseline.

- Add BrokerConnection, BrokerSession and safe BrokerAuditLog to the existing
  configured Django database, preserving research data with additive migrations.
- Only the owner enters API credentials through the localhost administrator page;
  never solicit secrets, passwords, OTP/TOTP or tokens in chat/source/Git.
- API secrets and access tokens use Fernet authenticated encryption. A separate
  versioned keyring lives in a Windows current-user DPAPI vault outside the repo
  and database, or a protected process environment. Django's independent random
  signing key is not used as the broker encryption key. Missing/corrupt keys fail
  closed; rotation retains old keys for separately backed-up ciphertext.
- Enable Django authentication, administrator authorization and CSRF protection
  for configuration mutations. No generic admin access to credential models.
- Official interactive Zerodha login uses the exact callback
  `http://127.0.0.1:8001/kite/callback`; single-use state binds the browser session,
  administrator, settings revision and timeout. No automated password/OTP login.
- Only authentication/token revocation and read-only profile, instrument,
  historical-candle and quote/depth endpoints are allowlisted. Orders, changes,
  cancellations, portfolio writes, payments and refresh-token automation remain
  absent/blocked. Test Connection calls profile only after interactive login.
- Credentials and tokens are masked or omitted from pages and never re-rendered
  after saving. Logs contain no callback query strings, request bodies or raw
  upstream error text. Audit events use fixed event/outcome/error codes.
- Broker usage is opt-in; defaults remain offline, research-only and disabled.
  No automatic imports or market requests on dashboard views. Existing datasets
  and research behavior remain separate from broker authentication.
- Document separate key/database backups, portable encrypted key export/restore,
  local administrator creation, session expiration and explicit disconnect.
  Tests mock broker responses; live authentication is performed only by the owner.

## 24. v1.4.1 — owner-approved public source publication, 1 November 2026

- Owner explicitly requested committing and pushing all reviewed project source.
- GitHub reported `warade007/Trading` is public. After being informed, the owner
  explicitly chose to keep it public and publish the reviewed source there.
- This is the explicit exception to the earlier private-repository preference.
  Personal databases, real/licensed datasets, secrets, keys, credentials, account
  information, logs, backups and local environments remain excluded from Git.
- Public source publication does not authorize hosted deployment, exposing the
  localhost application or enabling real orders. Research-only controls remain.
