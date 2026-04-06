# Era 2: Development Phases (V1.0)

**Created:** 2026-04-05 (Session 41)
**Replaces:** DEVELOPMENT_PHASES_V1.15.md (archived, Era 1 phases 0-1.5)
**Freshness:** Update at each phase gate and after scope changes.

---

## Overview

**Era 1** (Phases 0-1.5) established the data collection foundation: fetch, validate, and store market + game data from Kalshi and ESPN across 4 sports (NFL, NCAAF, NBA, NHL).

**Era 2** (Phases 2-5) builds the trading platform — from full manual trading through ML-driven autonomous execution.

### Phase Summary

| Phase | Theme | Issue Count | GitHub Label |
|-------|-------|-------------|-------------|
| **2** | Full Manual Trading Platform | 38 | `phase-2` |
| **3** | Operations, Expansion & Signal Sources | 17+ | `phase-3` |
| **4** | Probability Estimation (ML + Ensembles) | 9+ | `phase-4` |
| **5** | Strategy & Autonomous Trading | 16+ | `phase-5` |

### Phase Dependencies

```
Phase 1 (COMPLETE) ──> Phase 2 ──> Phase 3 ──────────> Phase 4 ──────────> Phase 5
  Data Collection        Trading     Operations          Probability          Strategy
                         + Web UI    + Expansion          Estimation          + Autonomous
                                     + Signal Sources     (ML + Ensembles)
```

```
                        ┌── Sportsbook odds ──────┐
Phase 3 Signal Sources ─┤                         ├──> Phase 4 Ensemble Engines
                        ├── Weather forecast APIs ─┤
                        └── Polymarket data ───────┘
```

Each phase builds on the previous. Phase gates enforce entry/exit criteria.

**Strategy Research (#602)** runs in parallel with Phases 2-3 — informing Phase 4-5 prioritization without blocking execution.

---

## Phase 2: Full Manual Trading Platform

**Goal:** A user can browse markets, place all order types (market, limit, stop loss, take profit, trailing stop), view and manage positions, and analyze trade history — all through a web UI on Kalshi's demo API.

### Entry Criteria
- Phase 1 software validation PASSED (C4 gate: GO — Session 40)
- Phase 1 environment validation PASSED (desktop deployment + 1-week soak)
- Phase 2 requirements formalized (#339)
- Trade flow architecture designed (#508)
- Kalshi demo API behavior verified (#335)

### Exit Criteria
- [ ] All 5 order types functional through web UI (market, limit, stop loss, take profit, trailing stop)
- [ ] Market browsing with search, filter, live prices
- [ ] Position management with real-time P&L
- [ ] Trade history with performance analytics (ROI, win rate, P&L curve)
- [ ] All 10 Tier 1 safety guards active and tested
- [ ] Kill switch tested on demo API
- [ ] Fills pipeline processing and reconciling with Kalshi
- [ ] Order condition monitoring service running (evaluates stop/TP/trailing)
- [ ] 1-week soak on demo with zero safety guard failures

### Scope

#### Web UI Foundation
- #568 — FastAPI backend, frontend framework, authentication, design system
- #569 — Market browsing page (search, filter, live prices)
- #570 — Trading page (all order types, confirmation flow)
- #571 — Position management page (open positions, P&L, modify/close)
- #572 — Trade history and performance reporting
- Epic: #583 (Web UI Platform)

#### Order Execution Pipeline
- #508 — Trade flow architecture (design)
- #509 — FastAPI trade placement endpoint
- #510 — Web form for trade submission
- #325 — Mandatory client_order_id for idempotency
- #326 — OrderValidator safety guards (10 Tier 1 guards)
- #328 — Three-state order result classification
- #329 — Trading kill switch
- #330 — Behavioral circuit breakers
- #332 — Pre-trade live market validation chain
- Epic: #504 (Trade Execution Pipeline)

#### Advanced Order Types
- #573 — Stop loss order type
- #574 — Take profit order type
- #575 — Trailing stop order type
- #576 — Order condition monitoring service

#### Fills & Reconciliation
- #401 — Public market trades: API client + types
- #402 — Public market trades: schema + CRUD + validation
- #403 — Public market trades: poller + config + CLI
- #404 — Portfolio fills: schema + CRUD
- #405 — Portfolio fills: poller + config + CLI + pipeline tests
- #417 — Order-fills-positions reconciliation state machine
- #327 — Order reconciliation loop (DB <-> Kalshi sync)

#### Safety & Data Quality
- #303 — Stale ESPN data phantom edge prevention
- #561 — Pre-trade data freshness guard
- #335 — Test Kalshi demo API order behavior
- #338 — Clarify price column semantics
- #339 — Formalize Phase 2 requirements
- #365 — Database schema health audit

#### Infrastructure
- #343 — Kalshi WebSocket streaming
- #394 — Validation model for WebSocket streaming
- #526 — Games coverage reporting CLI
- #527 — Matching alert escalation to circuit breaker
- #528 — Backfill resumption and progress tracking

---

## Phase 3: Operations, Expansion & Signal Sources

**Goal:** Operational maturity + signal source ingestion — web-based system management, multi-platform support (Polymarket), additional sport coverage (MLB), and ingestion of external probability signals (sportsbook odds, weather forecasts) that Phase 4 engines will consume.

### Entry Criteria
- Phase 2 complete (all exit criteria met)
- Polymarket requirements formalized
- MLB requirements formalized

### Exit Criteria
- [ ] Operations web pages functional (config, alerts, logs, scheduler)
- [ ] Automated backup system running with cloud sync
- [ ] Polymarket integration operational with shared PredictionMarketClient Protocol
- [ ] MLB data collection running
- [ ] Cross-platform event matching working
- [ ] Sportsbook odds ingestion running (3+ books)
- [ ] Weather forecast ingestion running (if Kalshi weather market liquidity verified)
- [ ] Operations guide complete

### Scope

#### Web UI — Operations
- #577 — Configuration management page
- #578 — Alerts dashboard
- #579 — Log viewer
- #580 — Scheduler management page

#### Platform Expansion — Polymarket
- #495 — Polymarket integration (Tier A3 prediction market source)
- #496 — Cross-platform event matching

#### Signal Sources — Sportsbook Odds (NEW)
- TBD — Odds API connector (aggregate odds from 5-10 books)
- TBD — Sportsbook odds schema + CRUD + poller
- TBD — Odds normalization pipeline (American/decimal/implied prob)
- Epic: #602 (Strategy Research — Track B informs requirements)

#### Signal Sources — Weather Forecasts (NEW, conditional)
- TBD — Weather API connector (Open-Meteo / NOAA GFS)
- TBD — Weather forecast schema + CRUD + poller
- TBD — Kalshi weather market monitoring (30-day liquidity assessment)
- Conditional on: Kalshi weather market liquidity verification
- Epic: #602 (Strategy Research — Track A informs requirements)

#### Data Expansion
- #487 — CFBD integration (historical game data for Elo)
- #489 — CBBD integration (NCAAB team classification)
- #505 — Data Source Expansion epic
- #511 — Widen snapshot versioning
- #514 — Kalshi enrichment audit
- #548 — Extended soak test

#### Operational Infrastructure
- #493 — MaintenanceRunner for Tier B source heartbeats
- #494 — Shared test mock harness
- #565 — Automated backup system (Filen priority)
- #566 — Operations guide
- #567 — Doc restructure

#### Schema & Data Quality
- #368 — team_id FK backfill
- #370 — execution_environment filtering for views
- #453 — Monitor for NULL game_id

---

## Phase 4: Probability Estimation (ML + Ensembles)

**Goal:** Multiple methods of producing `P(outcome)` — Elo ratings, ML models, sportsbook consensus engine, and weather ensemble engine. All methods output calibrated probabilities that Phase 5 strategies consume.

### Entry Criteria
- Phase 3 complete
- Sufficient historical data (200+ settled markets per sport)
- Sportsbook odds ingestion running (from Phase 3)
- Weather forecast ingestion running (from Phase 3, if applicable)

### Exit Criteria
- [ ] Elo engine running in production for all supported sports
- [ ] At least one ML model trained, validated, and serving predictions
- [ ] Sportsbook consensus engine producing calibrated probabilities
- [ ] Weather ensemble engine producing bracket probabilities (if Kalshi weather liquidity confirmed)
- [ ] Model performance dashboard showing calibration metrics for ALL estimation methods
- [ ] Model promotion pipeline tested (C30 gate)
- [ ] Feature engineering pipeline producing cross-source features
- [ ] Comparison report: ML vs consensus vs hybrid edge on historical data

### Scope

#### Elo Engine
- #480 — Elo Rating System epic
- #481 — Load historical game data from all sources
- #482 — Run and validate Elo computation against historical data
- #483 — Elo scheduling, monitoring, maintenance
- #484 — Audit Elo engine post-migration

#### ML Models
- #529 — Play-by-play data feasibility study
- #553 — Phase 4 data model prerequisites (win probability columns, multi-book)

#### Sportsbook Consensus Engine (NEW)
- TBD — Consensus probability calculator (aggregate odds → implied prob → de-vig → consensus)
- TBD — Consensus vs Kalshi edge calculator
- TBD — Historical backtest: consensus edge on settled Kalshi markets
- TBD — Hybrid engine: weighted blend of ML model + consensus (calibrated by source accuracy)
- Informed by: #602 Track B research, #541 (DraftKings odds as features)

#### Weather Ensemble Engine (NEW, conditional)
- TBD — Ensemble forecast → distribution fit → bracket probability calculator
- TBD — Historical backtest against Kalshi weather market prices
- TBD — City-specific bias correction from forecast error history
- Conditional on: Phase 3 liquidity verification confirms viable market depth
- Informed by: #602 Track A research (ColdMath strategy analysis)

#### Web UI — Model Analytics
- #581 — Model training interface
- #582 — Model analytics dashboard (calibration, performance, feature importance)

#### Estimation Method Comparison (NEW)
- TBD — Unified evaluation framework: all methods scored on same metrics (calibration, edge, Sharpe)
- TBD — Phase 5 recommendation: which strategies to deploy first based on edge × reliability × build cost

---

## Phase 5: Strategy & Autonomous Trading

**Goal:** Automated execution — strategies designed, backtested, paper-traded, and deployed with full safety infrastructure.

### Entry Criteria
- Phase 4 complete
- At least one validated model producing edge signals
- Risk management framework reviewed (Scorpius + Armitage council)

### Exit Criteria
- [ ] At least one strategy backtested, paper-traded, and live-traded
- [ ] Autonomous execution pipeline running with safety guards
- [ ] Strategy performance dashboard operational
- [ ] Kill switch + circuit breakers tested under autonomous operation
- [ ] Strategy retirement criteria defined and automated

### Scope

#### Strategy Development
- #540 — Strategy & Model Feature Ideas epic
- #541 — DraftKings odds as features for edge detection
- #544 — NHL slight-underdog mispricing strategy
- #545 — Sport-specific model architecture
- #546 — Pre-game entry / in-game management strategy
- #547 — NBA strong-favorite underpricing signal

#### Infrastructure
- #497 — KalshiAuth PEM content for cloud deployment

---

## Architecture Prerequisites (Cross-Phase)

These items are prerequisites for specific phases but are tracked separately:

| Item | Needed By | Description |
|------|-----------|-------------|
| PredictionMarketClient Protocol | Phase 3 | Platform-agnostic client interface |
| Common TypedDict types | Phase 3 | Platform-agnostic data structures |
| FastAPI ADR | Phase 2 | Frontend technology decisions |
| EnvironmentConfig polymarket_mode | Phase 3 | Multi-platform env configuration |
| Strategy Development Lifecycle (SDL) | Phase 5 | Formal strategy pipeline |

---

## Version History

| Version | Date | Session | Changes |
|---------|------|---------|---------|
| 1.1 | 2026-04-05 | 42c | Phase 3 expanded: signal sources (sportsbook odds, weather forecasts). Phase 4 reframed: "Probability Estimation" (ML + consensus + weather ensembles). Strategy Research epic #602 runs parallel. |
| 1.0 | 2026-04-05 | 41 | Initial Era 2 roadmap. 4 phases, 80 issues across phases. |
