# Database Schema Summary

<!-- FRESHNESS: alembic_head=0051, verified=2026-04-07, tables=42, views=1 -->
<!--
Changelog from prior FRESHNESS marker (alembic_head=0048):
- Migration 0049: account_balance SCD temporal columns (row_start_ts, row_end_ts) + idx_balance_unique_current
- Migration 0050: Phase 2 indexes for trade execution queries
- Migration 0051: account_balance.execution_environment column + drop dead per-mode views
  - account_balance gets execution_environment VARCHAR(20) NOT NULL DEFAULT 'live'
  - CHECK constraint allows ('live', 'paper', 'backtest', 'unknown')
  - 'unknown' is reserved for future forensic backfills (no rows use it today)
  - idx_balance_unique_current is now composite (platform_id, execution_environment) WHERE row_current_ind = TRUE
  - DROPPED views: current_balances, live_trades, paper_trades, backtest_trades, training_data_trades, live_positions, paper_positions, backtest_positions
    All had ZERO production consumers verified by grep on src/.
  - See findings_622_686_synthesis.md for the design rationale
-->


---
**Version:** 2.0
**Last Updated:** 2026-04-05
**Status:** Current - Alembic head: migration 0048
**Replaces:** V1.16 (retained in same directory for changelog history)

> **V2.0 Rewrite:** Complete schema reference covering all 42 tables, 8 views, and 47 migrations.
> V1.16 was changelog-focused with gaps for migrations 0014-0043. This version is a clean reference.

---

## Quick Reference

| Metric | Count |
|--------|-------|
| Core Tables | 42 |
| Views | 8 |
| Migrations | 47 (0001-0048, 0029 skipped) |
| SCD Type 2 Tables | 6 |
| JSONB Columns | 25+ |
| Decimal Precision | DECIMAL(10,4) everywhere except Elo (10,2) |

### Key Design Patterns

- **SCD Type 2**: `row_current_ind`, `row_start_ts`, `row_end_ts` on volatile data (prices, game states, positions)
- **Immutable Versioning**: strategies + models use `(name, version)` UNIQUE, never overwritten
- **Fact/Dimension Split**: markets (dimension) + market_snapshots (fact) since migration 0021
- **DECIMAL(10,4)**: ALL financial/probability values. Never float. (ADR-002)
- **Platform FK Hierarchy**: `platforms.platform_id` is root FK for multi-platform support

---

## Table Groups

### A. Platform & Market Hierarchy

#### platforms (Dimension)
Static platform reference. Root of FK hierarchy.

| Column | Type | Notes |
|--------|------|-------|
| platform_id (PK) | VARCHAR(50) | 'kalshi' seeded |
| platform_type | VARCHAR(50) | |
| display_name | VARCHAR(100) | |
| base_url | VARCHAR(255) | |
| websocket_url | VARCHAR(255) | |
| auth_method | VARCHAR(20) | CHECK: rsa_pss, api_key, oauth2, metamask |
| status | VARCHAR(20) | CHECK: active, inactive, maintenance |
| fees_structure | JSONB | |

#### series (Dimension)
Grouping for related events/markets (e.g., "NFL Week 12").

| Column | Type | Notes |
|--------|------|-------|
| series_id (PK) | VARCHAR(100) | Natural key |
| id | SERIAL | Surrogate (0019) |
| platform_id (FK) | VARCHAR(50) | |
| category, subcategory | VARCHAR | |
| title | VARCHAR(200) | |
| tags | JSONB | Added 0010 |

#### events (Dimension)
Specific outcome events within a series.

| Column | Type | Notes |
|--------|------|-------|
| event_id (PK) | VARCHAR(100) | Natural key |
| id | SERIAL | Surrogate (0020) |
| platform_id (FK) | VARCHAR(50) | |
| series_id (FK) | VARCHAR(100) | |
| game_id (FK) | INTEGER | Links to games dimension (0038) |
| status | VARCHAR(20) | |
| result | JSONB | |

#### markets (Dimension)
Market identity and metadata. Prices are in market_snapshots.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| platform_id (FK) | VARCHAR(50) | |
| event_internal_id (FK) | INTEGER | Added 0021 |
| ticker | VARCHAR(100) | UNIQUE |
| title | VARCHAR(500) | |
| market_type | VARCHAR(20) | binary, categorical, scalar |
| status | VARCHAR(20) | open, closed, settled, halted |
| subcategory | VARCHAR(100) | Renamed from league (0037) |
| subtitle | VARCHAR(500) | Added 0033 |
| open_time, close_time, expiration_time | TIMESTAMPTZ | Added 0033 |
| settlement_value | DECIMAL(10,4) | |
| expiration_value | VARCHAR(100) | Added 0046 |

UNIQUE(platform_id, external_id), UNIQUE(ticker)

#### market_snapshots (Fact - SCD Type 2)
Versioned price/depth snapshots. ~100 versions/market/day during live trading.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| market_id (FK) | INTEGER | -> markets(id) |
| yes_ask_price | DECIMAL(10,4) | |
| no_ask_price | DECIMAL(10,4) | |
| yes_bid_price | DECIMAL(10,4) | |
| no_bid_price | DECIMAL(10,4) | |
| last_price, spread | DECIMAL(10,4) | |
| volume, open_interest | INTEGER | |
| volume_24h | INTEGER | Added 0046 |
| previous_yes_bid, previous_yes_ask, previous_price | DECIMAL(10,4) | Added 0046 |
| yes_bid_size, yes_ask_size | INTEGER | Added 0046 |
| row_current_ind | BOOLEAN | SCD Type 2 |
| row_start_ts, row_end_ts | TIMESTAMPTZ | SCD Type 2 |

Partial unique index: 1 current row per market_id.

---

### B. Teams & Sports Data

#### teams (Dimension)
Core sports team reference. Supports 9 sports.

| Column | Type | Notes |
|--------|------|-------|
| team_id (PK) | SERIAL | |
| team_code | VARCHAR(20) | |
| team_name, display_name | VARCHAR | |
| sport | VARCHAR(20) | nfl, ncaaf, nba, ncaab, nhl, wnba, mlb, soccer, ncaaw |
| league | VARCHAR(20) | |
| espn_team_id | VARCHAR(20) | |
| kalshi_team_code | VARCHAR(50) | Added 0041 |
| classification | VARCHAR(20) | Added 0042 (d1, fbs, fcs, etc.) |
| current_elo_rating | DECIMAL(10,2) | |

UNIQUE(team_code, sport) via partial index for pro leagues.

#### external_team_codes (Dimension)
Cross-platform team identity mapping. Created 0045.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| team_id (FK) | INTEGER | ON DELETE RESTRICT |
| source | VARCHAR(50) | kalshi, espn, polymarket, etc. |
| source_team_code | VARCHAR(100) | |
| league | VARCHAR(20) | |
| confidence | VARCHAR(20) | exact, manual, heuristic |

UNIQUE(source, source_team_code, league)

#### games (Dimension)
Canonical game identity. Created 0035. Replaces fragmented game references.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| sport | VARCHAR(20) | CHECK constraint |
| game_date | DATE | |
| home_team_code, away_team_code | VARCHAR(20) | |
| home_team_id, away_team_id (FK) | INTEGER | |
| venue_id (FK) | INTEGER | |
| season | INTEGER | 1900-2100 |
| season_type | VARCHAR(20) | regular, playoff, bowl, etc. |
| game_status | VARCHAR(20) | scheduled through cancelled |
| home_score, away_score | INTEGER | |
| espn_event_id | VARCHAR(100) | UNIQUE partial index |
| data_source | VARCHAR(50) | espn, espn_poller, historical_import, etc. |

UNIQUE(sport, game_date, home_team_code, away_team_code)

#### game_states (Fact - SCD Type 2)
Live game state updates from ESPN. ~30s poll frequency.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| espn_event_id | VARCHAR(100) | Business key for SCD |
| home_team_id, away_team_id (FK) | INTEGER | |
| home_score, away_score | INTEGER | |
| period | INTEGER | |
| clock_seconds | DECIMAL(10,4) | |
| game_status | VARCHAR(20) | |
| situation | JSONB | Sport-specific (possession, down, etc.) |
| linescores | JSONB | |
| row_current_ind | BOOLEAN | SCD Type 2 |
| row_start_ts, row_end_ts | TIMESTAMPTZ | SCD Type 2 |

Partial unique index: 1 current row per espn_event_id. GIN index on situation JSONB.

#### game_odds (Fact - SCD Type 2)
Historical CSV odds + live ESPN poller odds. Renamed from historical_odds in 0048.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| game_id (FK) | INTEGER | |
| sport, league | VARCHAR(20) | |
| spread_home_odds_open/close | DECIMAL(10,4) | |
| spread_away_odds_open/close | DECIMAL(10,4) | Added 0048 |
| moneyline_home/away_open/close | DECIMAL(10,4) | |
| over/under_odds_open/close | DECIMAL(10,4) | under added 0048 |
| home_favorite, away_favorite | BOOLEAN | Added 0048 |
| data_source | VARCHAR(20) | csv, espn_poller |
| row_current_ind | BOOLEAN | SCD Type 2 (added 0048) |
| row_start_ts, row_end_ts | TIMESTAMPTZ | SCD Type 2 (added 0048) |

---

### C. Orders, Trades & Execution

#### orders (Fact)
Trading DECISION — what was requested. Created 0025.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| platform_id (FK) | VARCHAR(50) | |
| external_order_id | VARCHAR(100) | |
| market_internal_id (FK) | INTEGER | |
| strategy_id, model_id, edge_id, position_id (FK) | INTEGER | Full attribution |
| side | VARCHAR(5) | yes, no |
| action | VARCHAR(10) | buy, sell |
| order_type | VARCHAR(20) | market, limit |
| requested_price | DECIMAL(10,4) | |
| requested_quantity | INTEGER | |
| filled_quantity | INTEGER | DEFAULT 0 |
| average_fill_price | DECIMAL(10,4) | |
| status | VARCHAR(20) | submitted through expired |
| execution_environment | VARCHAR(20) | live, paper, backtest |
| trade_source | VARCHAR(20) | automated, manual |

UNIQUE(platform_id, external_order_id)

#### trades (Fact)
Trading EXECUTION — what actually happened at exchange.

| Column | Type | Notes |
|--------|------|-------|
| trade_id (PK) | SERIAL | |
| market_id | VARCHAR(100) | Transitional (pre-0021) |
| platform_id (FK) | VARCHAR(50) | |
| position_internal_id (FK) | INTEGER | |
| side | VARCHAR(5) | buy, sell |
| price | DECIMAL(10,4) | |
| quantity | INTEGER | |
| fees | DECIMAL(10,4) | |
| trade_source | VARCHAR(20) | automated, manual |
| execution_time | TIMESTAMPTZ | |

#### positions (Fact - SCD Type 2)
Position state over time. Versioned via SCD.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| position_id | VARCHAR | Business key for SCD |
| market_id | VARCHAR(100) | |
| platform_id (FK) | VARCHAR(50) | |
| strategy_id, model_id (FK) | INTEGER | |
| side | VARCHAR(10) | YES, NO, LONG, SHORT |
| entry_price, current_price | DECIMAL(10,4) | |
| quantity | INTEGER | |
| status | VARCHAR(20) | open, closed, settled |
| unrealized_pnl, realized_pnl | DECIMAL(10,4) | |
| row_current_ind | BOOLEAN | SCD Type 2 |
| row_start_ts, row_end_ts | TIMESTAMPTZ | SCD Type 2 |

Partial unique index: 1 current row per position_id.

#### account_balance (Fact - SCD Type 2)
Balance snapshots per platform, partitioned by execution_environment.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | renamed from `balance_id` in migration 0036 |
| platform_id (FK) | VARCHAR(50) | |
| balance | DECIMAL(10,4) | >= 0 |
| currency | VARCHAR(3) | DEFAULT 'USD' |
| execution_environment | VARCHAR(20) | NOT NULL DEFAULT 'live'. CHECK IN ('live', 'paper', 'backtest', 'unknown'). Added in migration 0051. REQUIRED parameter on all CRUD writes — no Python default. See ADR-107 and findings_622_686_synthesis.md. The 'unknown' value is reserved for future forensic backfills of historical rows; no rows in the current schema use it. |
| row_current_ind | BOOLEAN | SCD Type 2 |
| row_start_ts | TIMESTAMPTZ | SCD Type 2 (added migration 0049) |
| row_end_ts | TIMESTAMPTZ | SCD Type 2 (added migration 0049) |

**Partial unique index** `idx_balance_unique_current`: composite on `(platform_id, execution_environment) WHERE row_current_ind = TRUE`. The index name is preserved across migrations 0049 and 0051 so the SCD retry helper (`crud_shared.retry_on_scd_unique_conflict`) continues to discriminate by constraint name. One current row per `(platform_id, execution_environment)` tuple.

**Cross-environment isolation:** post-migration 0051, `account_balance` can hold parallel current rows for the same `platform_id` in different environments (e.g., one live and one paper). Queries that need a single environment MUST filter on both `row_current_ind = TRUE` AND `execution_environment = %s`. Mode-blind queries are a money-contamination risk — see #622, #662, #686 in the issue tracker.

#### account_ledger (Fact - Append Only)
Explains WHY balance changed. Created 0026.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| platform_id (FK) | VARCHAR(50) | |
| transaction_type | VARCHAR(20) | deposit, withdrawal, trade_pnl, fee, rebate, adjustment |
| amount | DECIMAL(10,4) | Can be negative |
| running_balance | DECIMAL(10,4) | >= 0 |
| reference_type | VARCHAR(20) | order, settlement, trade, manual, system |
| order_id (FK) | INTEGER | Direct FK for trade entries |

---

### D. Market Data & Trading Signals

#### market_trades (Fact)
Public trade tape. All fills on a market (not just ours). Created 0028.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| market_internal_id (FK) | INTEGER | |
| yes_price, no_price | DECIMAL(10,4) | |
| count | INTEGER | |
| taker_side | VARCHAR(5) | yes, no |
| trade_time | TIMESTAMPTZ | |

UNIQUE(platform_id, external_trade_id)

#### orderbook_snapshots (Fact)
Full order book depth. Created 0034.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| market_internal_id (FK) | INTEGER | |
| best_bid, best_ask, spread | DECIMAL(10,4) | |
| bid_prices, ask_prices | DECIMAL(10,4)[] | PostgreSQL arrays |
| bid_quantities, ask_quantities | INTEGER[] | PostgreSQL arrays |
| depth_imbalance | DECIMAL(10,4) | -1.0 to 1.0 |

#### temporal_alignment (Fact)
Links Kalshi snapshots (15s) to ESPN game states (30s). Created 0027.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| market_id (FK) | INTEGER | |
| market_snapshot_id, game_state_id (FK) | INTEGER | |
| time_delta_seconds | DECIMAL(10,2) | |
| alignment_quality | VARCHAR(10) | exact, good, fair, poor, stale |

UNIQUE(market_snapshot_id, game_state_id)

---

### E. Analytics & Evaluation

#### edges (Fact - SCD Type 2)
Edge detection results.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| edge_id | VARCHAR | Business key |
| model_id (FK) | INTEGER | |
| expected_value | DECIMAL(10,4) | |
| true_win_probability | DECIMAL(10,4) | |
| market_implied_probability | DECIMAL(10,4) | |
| confidence_level | VARCHAR(10) | high, medium, low |
| row_current_ind | BOOLEAN | SCD Type 2 |

#### evaluation_runs, backtesting_runs, predictions, performance_metrics
Created 0031. Phase 4-5 ML pipeline tables. See V1.16 for full column details.

---

### F. Strategy & Model Definitions

#### strategies (Dimension - Immutable Versions)
UNIQUE(strategy_name, strategy_version). New versions don't overwrite.

#### probability_models (Dimension - Immutable Versions)
UNIQUE(model_name, model_version). Linked to trades via orders.

#### strategy_types, model_classes (Lookup)
Seeded reference tables. Updated with audit columns in 0002.

---

### G. System & Operations

#### system_health
Component health snapshots. CHECK constraint dropped in 0043 (validation moved to app layer).

#### scheduler_status
Composite PK (host_id, service_name). Cross-process IPC for service coordination.

#### circuit_breaker_events
Append-only audit trail. Types: daily_loss_limit, api_failures, data_stale, position_limit, manual.

#### alerts
Append-only alert log with severity levels and acknowledgment tracking.

#### config_overrides
Runtime configuration overrides with expiration support.

---

## Views

| View | Purpose | Key Join |
|------|---------|----------|
| current_markets | Market + latest prices | markets LEFT JOIN market_snapshots WHERE row_current_ind |
| current_game_states | Latest game states | game_states WHERE row_current_ind |
| current_edges | Active edges | edges WHERE row_current_ind |
| open_positions | Active positions | positions WHERE row_current_ind AND status = 'open' |
| ~~current_balances~~ | DROPPED in migration 0051 | use `WHERE row_current_ind=TRUE AND execution_environment=%s` |
| active_strategies | Deployed strategies | strategies WHERE status = 'active' |
| active_models | Models in use | probability_models WHERE status = 'active' |
| team_season_records | W/L/D aggregation | UNION ALL from games + game_states with dedup |

---

## Migration Catalog

47 migrations (0001-0048, 0029 skipped). Key structural changes:

| Migration | Description | Impact |
|-----------|-------------|--------|
| 0001 | Initial baseline (all core tables) | Foundation |
| 0019-0020 | Surrogate PKs for series, events | Performance |
| **0021** | **Markets split** (dimension + snapshots fact) | Major restructure |
| **0025** | **Create orders** (attribution moved from trades) | Major restructure |
| 0026 | Account ledger (append-only transaction log) | New table |
| 0027 | Temporal alignment (Kalshi-ESPN linking) | New table |
| 0028 | Market trades (public trade tape) | New table |
| 0031 | Analytics tables (eval, backtest, predictions, metrics) | 4 new tables |
| 0033-0034 | Market enrichment + orderbook snapshots | New columns + table |
| **0035** | **Games dimension** (canonical game identity) | Major restructure |
| 0037 | Rename markets.league -> subcategory | Naming cleanup |
| 0039-0040 | Sport value renames + Elo column rename | Naming cleanup |
| 0041-0042 | Kalshi team code + team classification | New columns |
| 0045 | External team codes (cross-platform mapping) | New table |
| 0046 | Market depth + daily movement columns | New columns |
| **0048** | **Game odds rename + SCD Type 2** | Major restructure |

All migrations have `downgrade()` functions. 0029 intentionally skipped (portfolio_fills eliminated).

---

## Version History

| Version | Date | Summary |
|---------|------|---------|
| 2.0 | 2026-04-05 | Complete rewrite. All 42 tables, 8 views, 47 migrations documented. |
| 1.16 | 2026-04-03 | Migrations 0044-0048 documented. Gaps for 0014-0043. |
| 1.0 | 2025-10-28 | Initial schema summary. |
