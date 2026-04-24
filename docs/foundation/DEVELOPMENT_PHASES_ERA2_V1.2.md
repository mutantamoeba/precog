# Era 2: Development Phases (V1.2)

**Created:** 2026-04-05 (Session 41)
**Last Updated:** 2026-04-23 (Session 71 — Phase 5 LLM/MCP Integration section added via Task 9)
**Replaces:** DEVELOPMENT_PHASES_ERA2_V1.1.md (superseded-and-deleted per R098 convention)
**Also replaces:** DEVELOPMENT_PHASES_V1.15.md (archived, Era 1 phases 0-1.5)
**Freshness:** Update at each phase gate and after scope changes.

---

## Overview

**Era 1** (Phases 0-1.5) established the data collection foundation: fetch, validate, and store market + game data from Kalshi and ESPN across 4 sports (NFL, NCAAF, NBA, NHL).

**Era 2** (Phases 2-5) builds the trading platform — from full manual trading through ML-driven autonomous execution, with LLM/MCP integration in Phase 5 via a shared service layer.

### Phase Summary

| Phase | Theme | Issue Count | GitHub Label |
|-------|-------|-------------|-------------|
| **2** | Full Manual Trading Platform | 38 | `phase-2` |
| **3** | Operations, Expansion & Signal Sources | 20 + 6 TBD | `phase-3` |
| **4** | Probability Estimation (ML + Ensembles) | 7 + 9 TBD | `phase-4` |
| **5** | Strategy, Autonomous Trading, & LLM/MCP Integration | 16 + 8 (Epic #990) | `phase-5` |

> **TBD items** are signal source / engine work items not yet ticketed — they'll be filed during Phase 3 entry once Strategy Research Epic #602 produces requirements. Defined counts reflect issues already filed in GitHub.

### Phase Dependencies

```
Phase 1 (COMPLETE) ──> Phase 2 ──> Phase 3 ──────────> Phase 4 ──────────> Phase 5
  Data Collection        Trading     Operations          Probability          Strategy
                         + Web UI    + Expansion         Estimation           + Autonomous
                                     + Signal Sources    (ML + Ensembles)     + LLM/MCP
```

```
                        ┌── Sportsbook odds ──────┐
Phase 3 Signal Sources ─┤                         ├──> Phase 4 Ensemble Engines
                        ├── Weather forecast APIs ─┤
                        └── Polymarket data ───────┘
```

```
Phase 2 Service Foundation ──> Phase 5 Service Layer ──> Read-Only MCP
                                       │                       │
                                       ├──> Analytics MCP ─────┤
                                       │                       │
                                       └──> Trade-Placement ───┴──> MCP Deployment
                                                                         │
                                                          (conditional)  │
                                                           OpenAI-Compat Adapter
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
- Informed by: #602 Track B (Strategy Research — sportsbook consensus)

#### Signal Sources — Weather Forecasts (NEW, conditional)
- TBD — Weather API connector (Open-Meteo / NOAA GFS)
- TBD — Weather forecast schema + CRUD + poller
- TBD — Kalshi weather market monitoring (30-day liquidity assessment)
- Conditional on: Kalshi weather market liquidity verification
- Informed by: #602 Track A (Strategy Research — weather strategy)

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
- Historical game data loaded for all sports — enables Elo computation, ML training, and consensus backtesting (#481)
- Sportsbook odds ingestion running (from Phase 3)
- Weather forecast ingestion running (from Phase 3, if applicable)

> **Note on Elo:** V1.0 listed "Elo ratings computed and validated" as a Phase 4 entry criterion, but Elo computation (#482-#484) is itself in Phase 4 scope — that was a circular gate. V1.1 reframes the gate as "historical data loaded" (the *prerequisite* for Elo), with Elo execution and validation tracked in scope and exit criteria.

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

## Phase 5: Strategy, Autonomous Trading, & LLM/MCP Integration

**Goal:** Automated execution plus LLM-assisted operation — strategies designed, backtested, paper-traded, and deployed with full safety infrastructure, and a shared service layer that exposes market data, analytics, and (eventually) trade placement to LLM clients via MCP.

### Entry Criteria
- Phase 4 complete
- At least one validated model producing edge signals
- Risk management framework reviewed (Scorpius + Armitage council)
- FastAPI service foundation from Phase 2 available (web UI backend) — service layer extension piggybacks on this

### Exit Criteria
- [ ] At least one strategy backtested, paper-traded, and live-traded
- [ ] Autonomous execution pipeline running with safety guards
- [ ] Strategy performance dashboard operational
- [ ] Kill switch + circuit breakers tested under autonomous operation
- [ ] Strategy retirement criteria defined and automated
- [ ] Service layer (FastAPI + shared Pydantic contracts) extracted; MCP + web UI both consume it
- [ ] At least one MCP server (read-only) deployed and discoverable
- [ ] Analytics MCP operational (backtesting, EV, calibration queries)
- [ ] Trade-placement MCP operational on demo with full audit trail and rate-limit enforcement
- [ ] MCP deployment pattern codified (stdio + SSE; process isolation; credential handoff)
- [ ] Anthropic-MCP vs self-hosted-LLM decision ADR merged

### Scope

#### Strategy Development
- #540 — Strategy & Model Feature Ideas epic
- #541 — DraftKings odds as features for edge detection
- #544 — NHL slight-underdog mispricing strategy
- #545 — Sport-specific model architecture
- #546 — Pre-game entry / in-game management strategy
- #547 — NBA strong-favorite underpricing signal

#### Infrastructure (Strategy side)
- #497 — KalshiAuth PEM content for cloud deployment

#### LLM / MCP Integration (NEW — Path B via shared service layer)

**Path B commitment (session 69):** A shared FastAPI service layer with Pydantic contracts is consumed by MCP tools and web UI via the same backend routes. LLM actions ride on the same primitives as user actions — single audit trail, single validation layer, single rate-limit enforcement. Anthropic-MCP-vs-self-hosted-LLM decision is **deferred** until the service layer ships.

- **Epic #990** — MCP/LLM Integration via Shared Service Layer (Path B)
- **#982** — ADR-tracker: Service Layer Architecture (FastAPI + Pydantic contracts)
- **#983** — ADR-tracker: Anthropic MCP vs Self-Hosted LLM (deferred; unblocked when service layer ships)
- **#984** — Capability surface: Service Layer (**backbone — ships first**)
- **#985** — Capability surface: Read-Only MCP (first MCP; reference pattern for the MCP-over-service-layer shape)
- **#986** — Capability surface: Analytics MCP (backtesting, EV, calibration; read-heavy + computational)
- **#987** — Capability surface: Trade-Placement MCP (state-mutating; blocked until Phase 2 trade execution stabilizes on demo; full audit trail + confirmation-token + rate-limit)
- **#988** — Capability surface: MCP Deployment (stdio + SSE; process isolation; credential handoff)
- **#989** — Capability surface: OpenAI-Compat Adapter (conditional on #983 decision)
- **#991** — Capability surface: Observability & Tracing Infrastructure (**P1 — ships before #987 enters demo soak**; per REQ-LLM-011)
- **#992** — Capability surface: Review Dashboard for LLM-Initiated Actions (surfaces REQ-LLM-009 audit trail to operators)
- **#993** — Capability surface: Adversarial / Red-Team Test Harness for MCPs (**pre-live-trading gate**; proves safety guards engage under attack)

Sequence within Phase 5:
1. Service Layer (#984) extracts from Phase 2 FastAPI foundation.
2. Read-Only MCP (#985) ships as reference implementation.
3. MCP Deployment (#988) codifies the pattern.
4. Analytics MCP (#986) extends computationally.
5. ADR-tracker #982 authored before or alongside the first service-layer PRs.
6. Observability & Tracing Infrastructure (#991) — **P1, must be in place before Trade-Placement MCP enters demo soak** so safety-guard regressions are visible in production (per REQ-LLM-011).
7. After Phase 2 trade-execution demo soak: Trade-Placement MCP (#987).
8. Review Dashboard for LLM Actions (#992) — alongside or immediately after #987 (audit trail operational UI).
9. ADR-tracker #983 decision after service layer is stable in production.
10. OpenAI-Compat Adapter (#989) conditional on #983 decision.
11. Red-Team Test Harness (#993) — **pre-live-trading gate** — proves safety guards engage under adversarial prompts before any live-trading MCP ships.

Status: **Planning** (until Epic #990 gains traction in a session cohort).

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
| Shared Pydantic Contracts module | Phase 5 | SSOT contract types consumed by service, MCP, web UI |

---

## Version History

| Version | Date | Session | Changes |
|---------|------|---------|---------|
| 1.2 | 2026-04-23 | 71 | Phase 5 LLM/MCP Integration section added (Task 9). References Epic #990 + 8 child issues (#982-#989). Path B service-layer architecture recorded. Anthropic-vs-self-hosted decision explicitly deferred. Shared Pydantic Contracts added to cross-phase architecture prerequisites. |
| 1.1 | 2026-04-06 | 42c | Phase 3 expanded: signal sources (sportsbook odds, weather forecasts). Phase 4 reframed: "Probability Estimation" (ML + consensus + weather ensembles). Strategy Research epic #602 runs parallel. Claude Review fixes: issue counts, Elo gate visibility, ASCII alignment, "Informed by" convention, V1.0→V1.1 filename. |
| 1.0 | 2026-04-05 | 41 | Initial Era 2 roadmap. 4 phases, 80 issues across phases. |
