# Database Schema Summary

<!-- FRESHNESS: alembic_head=0070, verified=2026-04-26, tables=51, migrations=69, last_changelog_migration=0070 -->
<!--
Changelog from prior FRESHNESS marker (V2.0: alembic_head=0051, verified=2026-04-07, tables=42):
- Migrations 0052-0055: execution_environment cascade — account_ledger / settlements /
  position_exits / exit_attempts gain the same per-environment NOT NULL discriminator
  account_balance gained in 0051.  Closes the cross-environment contamination surface
  for every money-touching table (#691 Phase A, PR #714).
- Migration 0056: DB-level write-protection triggers on immutable tables — applies
  to 7 tables: `strategies`, `probability_models`, `trades`, `settlements`,
  `account_ledger`, `position_exits`, `exit_attempts` — append-only / version-immutable
  rows rejected at the DB layer rather than only at the CRUD layer.  #371 + #723.
- Migration 0057: 59 FK columns converted to ON DELETE RESTRICT + SCD Type 2 added to
  teams / venues / series.  Closes cascade-delete surface that could silently orphan
  trade attribution (#724, PR #758).
- Migration 0058: business-key column renames (e.g. position_id -> position_key
  on positions; game_state_id -> game_state_key on game_states) — establishes
  the "_key" suffix convention for SCD-2 version-stable surrogates.  Pattern 80
  later (V1.35) codified the rule that justifies this rename: row_current_ind
  presence is the load-bearing test (#788 / C2b, PR #797).  Note: temporal_alignment
  retains the older `market_snapshot_id` / `game_state_id` column names (FKs to the
  surrogate IDs of those tables, not business keys — the rename did not apply).
- Migration 0059: missing FK backfill from the C2b audit + SCD copy-forward helper
  (#725 phase 1, PR #839).
- Migration 0060 (A1): sports + leagues lookup tables created; nullable FK columns
  backfilled across teams / games / game_states (#738 A1, PR #840).
- Migration 0061 (A2): 12 FK columns flipped to NOT NULL after backfill verification +
  9 redundant CHECK constraints dropped (replaced by the lookup-FK guarantee) —
  the first concrete instance of the pattern Pattern 81 later (V1.36) codified
  (#738 A2, PR #855).  Hotfix in PR #857: idempotent CHECK drops + count fix.
- Migration 0062: business key columns added to orders / position_exits / exit_attempts
  using two-step INSERT pattern (separate UPDATE within the same transaction) (#791 C2c,
  PR #861).
- Migration 0063: orderbook_snapshot_id FK on orders + edges — completes the snapshot
  attribution chain so a trade row can prove which orderbook depth it acted against
  (#725 item 11, PR #863).
- Migration 0064: SCD Type 2 added to strategies + probability_models — model + strategy
  versions are now temporally addressable, not just immutable-by-(name, version) (#791 C2c,
  PR #883).  Pattern 80 (V1.35) later cites this as the "row_current_ind presence
  test passes" precedent.
- Migration 0065: edge_lifecycle realized_pnl sign inversion fix (#909, PR #918) —
  YES-side position semantics; pure VIEW change, no schema delta on edges itself.
- Migration 0066: idx_games_espn_event demoted from UNIQUE -> non-unique (#933 +
  Epic #935 Phase 1, PR #938).  External keys are NOT unique by design — the
  demotion is the canonical instance of the three-tier identity model
  (Pattern 79 / ADR-117 / V1.34) applied retroactively.

Cohort 1 + Cohort 2 — Phase B.5 ADR-118 canonical identity layer:

- Migration 0067 (Cohort 1A): canonical_event_domains + canonical_event_types +
  canonical_events.  First three concrete tables of the "Level B" canonical-events
  tier from ADR-118 V2.38.  Two open-canonical-enum lookup tables (Pattern 81),
  one main fact table with composite natural-key hash + FK back to the lookup
  tables.  ADR-118 V2.38 amendment captured #996; PR #1005.
- Migration 0068 (Cohort 1B): canonical_entity_kinds + canonical_entity +
  canonical_participant_roles + canonical_event_participants — plus the
  enforce_canonical_entity_team_backref CONSTRAINT TRIGGER (Pattern 82
  canonical instance: PG CHECK cannot subquery the lookup table to resolve
  entity_kind_id -> text, so the polymorphic typed back-ref integrity rule
  is encoded as a deferrable CONSTRAINT TRIGGER).  PR #1008.
- Migration 0069 (Cohort 2): canonical_markets standalone — links the canonical
  event tier to the platform-markets fact tier via canonical_event_id BIGINT
  NOT NULL with ON DELETE RESTRICT (markets carry settlement; CASCADE would
  silently delete settlement-bearing rows).  ADR-118 V2.39 amendment captured
  the Cohort 2 design council; PR #1022.
- Migration 0070 (Cohort 1 carry-forward, #1011): two additive integrity fences —
  partial UNIQUE INDEX on canonical_participant_roles cross-domain rows +
  CHECK constraint canonical_events_lifecycle_phase_check on the 8 canonical
  state-machine phases.  Single-phase ADD CONSTRAINT CHECK justified by 0-row
  state at deploy time (the canonical "When NOT to Apply" carve-out documented
  in Pattern 84, V1.38).  ADR-118 V2.40 amendment ratified the carry-forward
  council adjudications; PR #1031.

Migration 0029 was eliminated (portfolio_fills design abandoned pre-baseline);
the slot is intentionally skipped — 69 migration files cover slots 0001-0070.
-->


---
**Version:** 2.1
**Last Updated:** 2026-04-26
**Status:** Current — Alembic head: migration 0070
**Replaces:** V2.0 (retained in same directory for changelog history; V1.16 also retained)

> **V2.1 Rewrite:** Brings the schema reference back in sync with `alembic_version` after
> the 19-migration drift V2.0 acquired between V2.0's authoring and Cohort 1 + 2 ship.
> Adds the eight canonical_* tables landed in Migrations 0067 + 0068 + 0069, refreshes
> the Cohort-arc migration catalog (0049-0070), corrects the Quick Reference counts,
> demonstrates Pattern 86 (Living-Doc Freshness Markers) as the freshness-marker shape,
> and restores the missing temporal_alignment column-list detail. Same structural shape
> as V2.0 — V2.1 is a faithful revision, not a re-architecture.

---

## Quick Reference

| Metric | Count |
|--------|-------|
| Core Tables | 51 |
| Views | 19 |
| Migrations | 69 (0001-0070, 0029 skipped) |
| SCD Type 2 Tables | 11 |
| JSONB Columns | 52 |
| Decimal Precision | DECIMAL(10,4) everywhere except Elo (10,2), temporal_alignment (numeric, no scale) |
| Canonical Identity Tier (Cohorts 1A + 1B + 2) | 8 tables (Migrations 0067-0069) |

### Key Design Patterns

- **SCD Type 2:** `row_current_ind`, `row_start_ts`, `row_end_ts` on volatile data
  (prices, game states, positions, balances, edges, strategies, models) — 11 tables.
- **Immutable Versioning:** strategies + probability_models use `(name, version)` UNIQUE,
  never overwritten. Migration 0064 layered SCD-2 on top so version rows are also
  temporally addressable (Pattern 80 / V1.35 codifies the rule).
- **Fact / Dimension Split:** markets (dimension) + market_snapshots (fact) since
  Migration 0021. Same shape applied to game_odds (Migration 0048).
- **DECIMAL(10,4):** ALL financial / probability values. Never float. (ADR-002.)
- **Platform FK Hierarchy:** `platforms.platform_id` is root FK for multi-platform support.
- **Three-Tier Identity Model (Pattern 79 / ADR-117):** Tier 1 surrogate PK,
  Tier 2 SCD-2 version-stable business keys (`*_key` columns), Tier 3 external IDs
  (NOT unique by design — Migration 0066 demoted `idx_games_espn_event` accordingly).
- **Canonical Identity Layer (ADR-118):** Cohorts 1+2 land the eight canonical_* tables
  that abstract events, entities, and markets across platforms. Cohorts 3-9 will land
  matching infrastructure, dim/fact split, event-state machine, views/CRUD, seeders,
  business-key cleanup, and weather Phase 1 per ADR-119.
- **Open-Canonical-Enum -> Lookup Table (Pattern 81 / V1.36):** Open enums likely to
  grow are encoded as lookup tables with FK, not CHECK constraints. The four lookup
  tables in Cohorts 1A + 1B (canonical_event_domains, canonical_event_types,
  canonical_entity_kinds, canonical_participant_roles) are the canonical instances.
- **CONSTRAINT TRIGGER for Polymorphic Typed Back-Reference (Pattern 82 / V1.36):**
  When a typed back-ref column's nullability depends on a discriminator that lives in
  a lookup table, the integrity rule cannot be encoded as a CHECK constraint
  (PG CHECK cannot subquery). The canonical_entity_kinds + canonical_entity pair
  in Migration 0068 is the canonical instance — see `enforce_canonical_entity_team_backref`.

---

## Table Groups

### A. Platform & Market Hierarchy

#### platforms (Dimension)

Static platform reference. Root of FK hierarchy. Seeded with `'kalshi'`.

| Column | Type | Notes |
|--------|------|-------|
| platform_id (PK) | VARCHAR(50) | |
| platform_type | VARCHAR(50) | |
| display_name | VARCHAR(100) | |
| base_url | VARCHAR(255) | |
| websocket_url | VARCHAR(255) | |
| auth_method | VARCHAR(20) | CHECK: rsa_pss, api_key, oauth2, metamask |
| status | VARCHAR(20) | CHECK: active, inactive, maintenance |
| fees_structure | JSONB | |

#### series (Dimension - SCD Type 2)

Grouping for related events / markets (e.g. "NFL Week 12"). SCD-2 since Migration 0057.

| Column | Type | Notes |
|--------|------|-------|
| series_id (PK / business key) | VARCHAR(100) | Natural key |
| id | SERIAL | Surrogate (Migration 0019) |
| platform_id (FK) | VARCHAR(50) | |
| category, subcategory | VARCHAR | |
| title | VARCHAR(200) | |
| tags | JSONB | Added Migration 0010 |
| row_current_ind | BOOLEAN | SCD-2 (added Migration 0057) |
| row_start_ts, row_end_ts | TIMESTAMPTZ | SCD-2 (added Migration 0057) |

#### events (Dimension)

Specific outcome events within a series.

| Column | Type | Notes |
|--------|------|-------|
| event_id (PK / business key) | VARCHAR(100) | Natural key |
| id | SERIAL | Surrogate (Migration 0020) |
| platform_id (FK) | VARCHAR(50) | |
| series_id (FK) | VARCHAR(100) | |
| game_id (FK) | INTEGER | Links to games dimension (Migration 0038) |
| status | VARCHAR(20) | |
| result | JSONB | |

#### markets (Dimension)

Market identity and metadata. Prices live in market_snapshots (the fact).

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| platform_id (FK) | VARCHAR(50) | |
| event_internal_id (FK) | INTEGER | Added Migration 0021 |
| ticker | VARCHAR(100) | UNIQUE |
| title | VARCHAR(500) | |
| market_type | VARCHAR(20) | binary, categorical, scalar |
| status | VARCHAR(20) | open, closed, settled, halted |
| subcategory | VARCHAR(100) | Renamed from `league` (Migration 0037) |
| subtitle | VARCHAR(500) | Added Migration 0033 |
| open_time, close_time, expiration_time | TIMESTAMPTZ | Added Migration 0033 |
| settlement_value | DECIMAL(10,4) | |
| expiration_value | VARCHAR(100) | Added Migration 0046 |

UNIQUE(platform_id, external_id), UNIQUE(ticker).

#### market_snapshots (Fact - SCD Type 2)

Versioned price / depth snapshots. ~100 versions / market / day during live trading.

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
| volume_24h | INTEGER | Added Migration 0046 |
| previous_yes_bid, previous_yes_ask, previous_price | DECIMAL(10,4) | Added Migration 0046 |
| yes_bid_size, yes_ask_size | INTEGER | Added Migration 0046 |
| row_current_ind | BOOLEAN | SCD-2 |
| row_start_ts, row_end_ts | TIMESTAMPTZ | SCD-2 |

Partial unique index: 1 current row per `market_id`.

---

### B. Teams & Sports Data

#### teams (Dimension - SCD Type 2)

Core sports team reference. Supports 9 sports. SCD-2 since Migration 0057.

| Column | Type | Notes |
|--------|------|-------|
| team_id (PK) | SERIAL | |
| team_code | VARCHAR(20) | |
| team_name, display_name | VARCHAR | |
| sport | VARCHAR(20) | nfl, ncaaf, nba, ncaab, nhl, wnba, mlb, soccer, ncaaw |
| league | VARCHAR(20) | |
| espn_team_id | VARCHAR(20) | |
| kalshi_team_code | VARCHAR(50) | Added Migration 0041 |
| classification | VARCHAR(20) | Added Migration 0042 (d1, fbs, fcs, etc.) |
| current_elo_rating | DECIMAL(10,2) | |
| row_current_ind | BOOLEAN | SCD-2 (added Migration 0057) |
| row_start_ts, row_end_ts | TIMESTAMPTZ | SCD-2 (added Migration 0057) |

UNIQUE(team_code, sport) via partial index for pro leagues.

#### venues (Dimension - SCD Type 2)

Venue reference for games. SCD-2 since Migration 0057.

| Column | Type | Notes |
|--------|------|-------|
| venue_id (PK) | SERIAL | |
| venue_name, city, state, country | VARCHAR | |
| timezone | VARCHAR(50) | |
| capacity | INTEGER | |
| surface, indoor | VARCHAR / BOOLEAN | |
| row_current_ind | BOOLEAN | SCD-2 (added Migration 0057) |
| row_start_ts, row_end_ts | TIMESTAMPTZ | SCD-2 (added Migration 0057) |

#### external_team_codes (Dimension)

Cross-platform team identity mapping. Created Migration 0045.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| team_id (FK) | INTEGER | ON DELETE RESTRICT (since Migration 0057) |
| source | VARCHAR(50) | kalshi, espn, polymarket, etc. |
| source_team_code | VARCHAR(100) | |
| league | VARCHAR(20) | |
| confidence | VARCHAR(20) | exact, manual, heuristic |

UNIQUE(source, source_team_code, league).

#### games (Dimension)

Canonical game identity. Created Migration 0035. Replaces fragmented game references.

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
| espn_event_id | VARCHAR(100) | Non-unique partial index since Migration 0066 (was UNIQUE pre-#933) |
| data_source | VARCHAR(50) | espn, espn_poller, historical_import, etc. |

UNIQUE(sport, game_date, home_team_code, away_team_code).

> **Note:** `espn_event_id` was demoted from UNIQUE to non-unique in Migration 0066
> per Epic #935 Phase 1 (#933). External keys are NOT unique by the three-tier
> identity model (Pattern 79 / ADR-117). The non-unique partial index preserves
> query performance while the UNIQUE behaviour shifts to Tier 2 (`game_key` business
> key) and Tier 1 (`id` surrogate PK).

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
| row_current_ind | BOOLEAN | SCD-2 |
| row_start_ts, row_end_ts | TIMESTAMPTZ | SCD-2 |

Partial unique index: 1 current row per `espn_event_id`. GIN index on `situation` JSONB.

#### game_odds (Fact - SCD Type 2)

Historical CSV odds + live ESPN poller odds. Renamed from historical_odds in Migration 0048.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| game_id (FK) | INTEGER | |
| sport, league | VARCHAR(20) | |
| spread_home_odds_open / close | DECIMAL(10,4) | |
| spread_away_odds_open / close | DECIMAL(10,4) | Added Migration 0048 |
| moneyline_home / away_open / close | DECIMAL(10,4) | |
| over / under_odds_open / close | DECIMAL(10,4) | `under` added Migration 0048 |
| home_favorite, away_favorite | BOOLEAN | Added Migration 0048 |
| data_source | VARCHAR(20) | csv, espn_poller |
| row_current_ind | BOOLEAN | SCD-2 (added Migration 0048) |
| row_start_ts, row_end_ts | TIMESTAMPTZ | SCD-2 (added Migration 0048) |

---

### C. Orders, Trades & Execution

#### orders (Fact)

Trading DECISION — what was requested. Created Migration 0025.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| platform_id (FK) | VARCHAR(50) | |
| external_order_id | VARCHAR(100) | |
| market_internal_id (FK) | INTEGER | |
| strategy_id, model_id, edge_id, position_id (FK) | INTEGER | Full attribution |
| orderbook_snapshot_id (FK) | INTEGER | Added Migration 0063 |
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

UNIQUE(platform_id, external_order_id).

#### trades (Fact)

Trading EXECUTION — what actually happened at the exchange.

| Column | Type | Notes |
|--------|------|-------|
| trade_id (PK) | SERIAL | |
| market_id | VARCHAR(100) | Transitional (pre-Migration 0021) |
| platform_id (FK) | VARCHAR(50) | |
| position_internal_id (FK) | INTEGER | |
| side | VARCHAR(5) | buy, sell |
| price | DECIMAL(10,4) | |
| quantity | INTEGER | |
| fees | DECIMAL(10,4) | |
| trade_source | VARCHAR(20) | automated, manual |
| execution_time | TIMESTAMPTZ | |

Write-protected at the DB layer since Migration 0056 (append-only).

#### positions (Fact - SCD Type 2)

Position state over time. Versioned via SCD.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| position_id | VARCHAR | Business key for SCD (renamed conceptually to `position_key` in Migration 0058 family) |
| market_id | VARCHAR(100) | |
| platform_id (FK) | VARCHAR(50) | |
| strategy_id, model_id (FK) | INTEGER | |
| side | VARCHAR(10) | YES, NO, LONG, SHORT |
| entry_price, current_price | DECIMAL(10,4) | |
| quantity | INTEGER | |
| status | VARCHAR(20) | open, closed, settled |
| unrealized_pnl, realized_pnl | DECIMAL(10,4) | |
| row_current_ind | BOOLEAN | SCD-2 |
| row_start_ts, row_end_ts | TIMESTAMPTZ | SCD-2 |

Partial unique index: 1 current row per business key.

#### account_balance (Fact - SCD Type 2)

Balance snapshots per platform, partitioned by `execution_environment`.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | renamed from `balance_id` in Migration 0036 |
| platform_id (FK) | VARCHAR(50) | |
| balance | DECIMAL(10,4) | >= 0 |
| currency | VARCHAR(3) | DEFAULT 'USD' |
| execution_environment | VARCHAR(20) | NOT NULL DEFAULT 'live'. CHECK IN ('live', 'paper', 'backtest', 'unknown'). Added Migration 0051. REQUIRED parameter on all CRUD writes — no Python default. See ADR-107 and findings_622_686_synthesis.md. The 'unknown' value is reserved for future forensic backfills of historical rows; no rows in the current schema use it. |
| row_current_ind | BOOLEAN | SCD-2 |
| row_start_ts | TIMESTAMPTZ | SCD-2 (added Migration 0049) |
| row_end_ts | TIMESTAMPTZ | SCD-2 (added Migration 0049) |

**Partial unique index `idx_balance_unique_current`:** composite on `(platform_id,
execution_environment) WHERE row_current_ind = TRUE`. The index name is preserved
across Migrations 0049 and 0051 so the SCD retry helper
(`crud_shared.retry_on_scd_unique_conflict`) continues to discriminate by constraint
name. One current row per `(platform_id, execution_environment)` tuple.

**Cross-environment isolation:** post-Migration 0051, `account_balance` can hold
parallel current rows for the same `platform_id` in different environments (e.g.
one live and one paper). Queries that need a single environment MUST filter on both
`row_current_ind = TRUE` AND `execution_environment = %s`. Mode-blind queries are a
money-contamination risk — see issues #622, #662, #686.

#### account_ledger (Fact - Append Only)

Explains WHY the balance changed. Created Migration 0026.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| platform_id (FK) | VARCHAR(50) | |
| transaction_type | VARCHAR(20) | deposit, withdrawal, trade_pnl, fee, rebate, adjustment |
| amount | DECIMAL(10,4) | Can be negative |
| running_balance | DECIMAL(10,4) | >= 0 |
| reference_type | VARCHAR(20) | order, settlement, trade, manual, system |
| order_id (FK) | INTEGER | Direct FK for trade entries |
| execution_environment | VARCHAR(20) | NOT NULL. Added Migration 0052. |

#### settlements / position_exits / exit_attempts (Fact)

Settlement outcomes, exit lifecycle records, and per-attempt exit logs. All three
gained `execution_environment` NOT NULL columns in Migrations 0053 / 0054 / 0055,
extending the cross-environment isolation rule beyond `account_balance`.

---

### D. Market Data & Trading Signals

#### market_trades (Fact)

Public trade tape. All fills on a market (not just ours). Created Migration 0028.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| market_internal_id (FK) | INTEGER | |
| yes_price, no_price | DECIMAL(10,4) | |
| count | INTEGER | |
| taker_side | VARCHAR(5) | yes, no |
| trade_time | TIMESTAMPTZ | |

UNIQUE(platform_id, external_trade_id).

#### orderbook_snapshots (Fact)

Full order-book depth. Created Migration 0034.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| market_internal_id (FK) | INTEGER | |
| best_bid, best_ask, spread | DECIMAL(10,4) | |
| bid_prices, ask_prices | DECIMAL(10,4)[] | PostgreSQL arrays |
| bid_quantities, ask_quantities | INTEGER[] | PostgreSQL arrays |
| depth_imbalance | DECIMAL(10,4) | -1.0 to 1.0 |

#### temporal_alignment (Fact)

Links Kalshi snapshots (15s) to ESPN game states (30s). Created Migration 0027;
`game_id` FK added Migration 0035; FKs converted to RESTRICT in Migration 0057.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| market_id (FK) | INTEGER | |
| market_snapshot_id (FK) | INTEGER | -> market_snapshots(id). Surrogate FK, not a business key (so the Migration 0058 `_key` rename did not apply). |
| game_state_id (FK) | INTEGER | -> game_states(id). Same — surrogate FK. |
| game_id (FK) | INTEGER | NULLABLE. Added Migration 0035. |
| snapshot_time | TIMESTAMPTZ | |
| game_state_time | TIMESTAMPTZ | |
| time_delta_seconds | NUMERIC | Untyped scale (no DECIMAL precision). |
| alignment_quality | VARCHAR(10) | exact, good, fair, poor, stale. DEFAULT 'good'. |
| yes_ask_price, no_ask_price, spread | NUMERIC | NULLABLE — denormalized snapshot of price at alignment time. |
| volume | INTEGER | NULLABLE — denormalized. |
| game_status | VARCHAR | NULLABLE — denormalized. |
| home_score, away_score | INTEGER | NULLABLE — denormalized. |
| period, clock | VARCHAR | NULLABLE — denormalized. |
| created_at | TIMESTAMPTZ | NULLABLE, DEFAULT now() (default applies on INSERT; column accepts explicit NULL). |

UNIQUE(market_snapshot_id, game_state_id).

> **Why NUMERIC and not DECIMAL(10,4):** the denormalized columns predate the
> DECIMAL-precision rule consolidation; they store snapshot copies of values that
> are already DECIMAL(10,4) on the source table, so the precision constraint is
> already enforced upstream. Future migrations may tighten the type — out of
> scope here.

---

### E. Analytics & Evaluation

#### edges (Fact - SCD Type 2)

Edge-detection results.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| edge_id | VARCHAR | Business key |
| model_id (FK) | INTEGER | |
| orderbook_snapshot_id (FK) | INTEGER | Added Migration 0063 |
| expected_value | DECIMAL(10,4) | |
| true_win_probability | DECIMAL(10,4) | |
| market_implied_probability | DECIMAL(10,4) | |
| confidence_level | VARCHAR(10) | high, medium, low |
| row_current_ind | BOOLEAN | SCD-2 |

#### evaluation_runs, backtesting_runs, predictions, performance_metrics

Created Migration 0031. Phase 4-5 ML pipeline tables.

#### elo_calculation_log

Append-only Elo calculation audit trail. Renamed `sport` -> `league` in Migration 0040.

#### settlements

Settlement outcome records. Gained `execution_environment` NOT NULL in Migration 0053.

---

### F. Strategy & Model Definitions

#### strategies (Dimension - Immutable Versions + SCD Type 2)

UNIQUE(strategy_name, strategy_version). New versions don't overwrite. SCD-2 layered
on top in Migration 0064 — version rows are temporally addressable in addition to
immutable-by-name+version. Pattern 80 (V1.35) cites this as a load-bearing
business-key example (the `strategy_key` is decoration; version-immutability is the
identity rule, with row_current_ind providing the temporal axis).

#### probability_models (Dimension - Immutable Versions + SCD Type 2)

UNIQUE(model_name, model_version). Linked to trades via orders. SCD-2 layered on
top in Migration 0064 (same shape as `strategies`).

#### strategy_types, model_classes (Lookup)

Seeded reference tables. Updated with audit columns in Migration 0002.

---

### G. Canonical Identity Layer (Cohorts 1A + 1B + 2 — ADR-118)

The eight canonical_* tables shipped in Migrations 0067 + 0068 + 0069 establish
the "Level B" canonical identity layer per ADR-118 V2.38 (Cohort 1) + V2.39
(Cohort 2) + V2.40 (Cohort 1 carry-forward).  This tier abstracts events,
entities, and markets across platforms; the platform-specific markets / events /
games / teams tables remain in place as Level A platform-tier dimensions, with
canonical-tier rows linking back to Level A via FK columns where appropriate.

#### canonical_event_domains (Lookup) — Migration 0067

Open-canonical-enum lookup table for event domains. Pattern 81 canonical instance.
7 seed rows: `sports`, `politics`, `weather`, `econ`, `news`, `entertainment`,
`fighting`.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| domain | TEXT | NOT NULL. UNIQUE. |
| description | TEXT | NULLABLE. |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now(). |

#### canonical_event_types (Lookup) — Migration 0067

Open-canonical-enum lookup table for event types within a domain. Pattern 81.
~13 seeded composite rows (e.g. `(sports, game)`, `(politics, election)`).
The `fighting` domain has no event_types seeded — landed with the first fighting
market (INSERT-not-ALTER discipline).

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| domain_id (FK) | INTEGER | -> canonical_event_domains(id). NOT NULL. |
| event_type | TEXT | NOT NULL. |
| description | TEXT | NULLABLE. |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now(). |

UNIQUE(domain_id, event_type).

#### canonical_events (Main) — Migration 0067

The canonical event row. Lifecycle phase tracked via the 8-value state machine
codified by `CANONICAL_EVENT_LIFECYCLE_PHASES` (Pattern 73 SSOT pointer; see
`src/precog/database/constants.py`).

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | BIGINT | |
| domain_id (FK) | INTEGER | -> canonical_event_domains(id). NOT NULL. |
| event_type_id (FK) | INTEGER | -> canonical_event_types(id). NOT NULL. |
| entities_sorted | INTEGER[] | NOT NULL. Array of canonical_entity ids — order canonical for natural-key hash determinism. |
| resolution_window | TSTZRANGE | NOT NULL. Time window in which the event resolves. |
| resolution_rule_fp | BYTEA | NULLABLE. Fingerprint hash of the resolution rule text — drift detector across rule updates. |
| natural_key_hash | BYTEA | NOT NULL. UNIQUE. Application-layer derivation; DDL is agnostic. |
| title | VARCHAR | NOT NULL. |
| description | TEXT | NULLABLE. |
| game_id (FK) | INTEGER | NULLABLE. -> games(id). Single-game event link (sports domain only). |
| series_id (FK) | INTEGER | NULLABLE. -> series.id (surrogate). Series-level event link. |
| lifecycle_phase | VARCHAR(32) | NOT NULL DEFAULT `'proposed'`. CHECK IN ('proposed', 'listed', 'pre_event', 'live', 'suspended', 'settling', 'resolved', 'voided') — single-phase ADD CONSTRAINT CHECK justified by 0-row state at 0070 deploy time (Pattern 84 carve-out, ADR-118 V2.40 item 3). |
| metadata | JSONB | NULLABLE. |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now(). |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now(). |
| retired_at | TIMESTAMPTZ | NULLABLE. Soft-delete timestamp — set when an event is permanently retired. |

> **Forward-pointer (load-bearing per ADR-118 V2.40):** when Migration 0077 lands
> `canonical_event_phase_log`, that migration MUST add an identical CHECK on the
> `phase` column with the same 8 values. Vocabulary drift between
> `canonical_events.lifecycle_phase` (the dim) and
> `canonical_event_phase_log.phase` (the audit log) would corrupt both surfaces
> simultaneously via a single typo. Two-fence enforcement is the design intent.

#### canonical_event_participants (Relation) — Migration 0068

Many-to-many bridge between canonical events and canonical entities, role-typed.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | BIGINT | |
| canonical_event_id (FK) | BIGINT | -> canonical_events(id). NOT NULL. ON DELETE CASCADE — participants are denormalization, not load-bearing. |
| entity_id (FK) | BIGINT | -> canonical_entity(id). NOT NULL. |
| role_id (FK) | INTEGER | -> canonical_participant_roles(id). NOT NULL. |
| sequence_number | INTEGER | NOT NULL. Disambiguates same-role participants (e.g. multi-fighter brawl). |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now(). |

UNIQUE(canonical_event_id, entity_id, role_id, sequence_number).

#### canonical_participant_roles (Lookup) — Migration 0068

Open-canonical-enum lookup table for participant roles. Pattern 81. Seed rows
include domain-scoped roles (e.g. `(sports, home_team)`, `(politics, incumbent)`)
and cross-domain roles where `domain_id IS NULL` (e.g. `(NULL, yes_side)`).

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| domain_id (FK) | INTEGER | NULLABLE. -> canonical_event_domains(id). NULL = cross-domain role. |
| role | TEXT | NOT NULL. |
| description | TEXT | NULLABLE. |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now(). |

Composite UNIQUE(domain_id, role) handles domain-scoped uniqueness.

> **Cross-domain partial unique index added Migration 0070:**
> `uq_canonical_participant_roles_role_when_cross_domain` on
> `(role) WHERE domain_id IS NULL` — closes the silent-duplication path for
> cross-domain roles. PostgreSQL treats NULL as distinct in unique constraints, so
> without this partial index two `(NULL, 'yes_side')` rows could land cleanly.
> Pattern 81 § "Nullable Parent Scope" gap closure.

#### canonical_entity_kinds (Lookup) — Migration 0068

Open-canonical-enum lookup table for entity kinds. Pattern 81. 12 seed rows:
`team`, `fighter`, `candidate`, `storm`, `company`, `location`, `person`,
`product`, `country`, `organization`, `commodity`, `media`.

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | SERIAL | |
| entity_kind | TEXT | NOT NULL. UNIQUE. |
| description | TEXT | NULLABLE. |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now(). |

#### canonical_entity (Main, Polymorphic) — Migration 0068

Canonical entity row, polymorphic over `entity_kind_id`. Carries an optional
typed back-ref to `teams` (the only kind with a back-ref column today; future
kinds will land typed back-refs in their own migrations).

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | BIGINT | |
| entity_kind_id (FK) | INTEGER | -> canonical_entity_kinds(id). NOT NULL. |
| entity_key | TEXT | NOT NULL. Application-layer natural key (e.g. ESPN team id, candidate ballot name). |
| display_name | TEXT | NOT NULL. |
| ref_team_id (FK) | INTEGER | NULLABLE. -> teams(team_id). Populated when `entity_kind_id` resolves to `'team'`, NULL otherwise. |
| metadata | JSONB | NULLABLE. |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now(). |

UNIQUE(entity_kind_id, entity_key).

> **CONSTRAINT TRIGGER `enforce_canonical_entity_team_backref`** (Pattern 82
> canonical instance, Migration 0068):
> `DEFERRABLE INITIALLY IMMEDIATE`. Enforces that `ref_team_id` is NOT NULL when
> `entity_kind_id` resolves to `'team'`. Encoded as a trigger because PG CHECK
> constraints cannot subquery the lookup table to resolve the discriminator id
> back to text. Pattern 82 V2 (V1.37) makes the rule forward-only: the trigger
> requires `ref_team_id NOT NULL` when the discriminator matches; the reverse
> direction (forbid `ref_team_id` when the discriminator does NOT match) is
> deliberately NOT enforced, preserving polymorphic-overloading future
> extensibility per ADR-118 V2.38 decision #5.

#### canonical_markets (Main) — Migration 0069

Canonical market row, FK-linked to `canonical_events`. `market_type_general` uses
an inline CHECK constraint (closed enum tied to the pmxt #964 NormalizedMarket
contract — explicitly NOT a Pattern 81 lookup table; new market shapes require
a code deploy regardless).

| Column | Type | Notes |
|--------|------|-------|
| id (PK) | BIGINT | |
| canonical_event_id (FK) | BIGINT | -> canonical_events(id). NOT NULL. ON DELETE RESTRICT — markets carry settlement; CASCADE would silently delete settlement-bearing rows; NOT NULL precludes SET NULL. |
| market_type_general | VARCHAR | NOT NULL. CHECK IN ('binary', 'categorical', 'scalar'). |
| outcome_label | VARCHAR | NULLABLE — used for categorical markets only. |
| natural_key_hash | BYTEA | NOT NULL. UNIQUE. Application-layer derivation. |
| metadata | JSONB | NULLABLE. |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now(). |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now(). BEFORE UPDATE trigger. |
| retired_at | TIMESTAMPTZ | NULLABLE. Soft-delete timestamp. |

> **Asymmetry vs `canonical_event_participants.CASCADE`:** participants are
> denormalization (regenerable from authoritative platform data); markets carry
> settlement value + observation history that cannot be regenerated. The CASCADE
> vs RESTRICT split is intentional. ADR-118 V2.39 Cohort 2 decision #5b.

---

### H. System & Operations

#### system_health
Component health snapshots. CHECK constraint dropped in Migration 0043 (validation
moved to app layer).

#### scheduler_status
Composite PK (host_id, service_name). Cross-process IPC for service coordination.

#### circuit_breaker_events
Append-only audit trail. Types: daily_loss_limit, api_failures, data_stale,
position_limit, manual.

#### alerts
Append-only alert log with severity levels and acknowledgment tracking.

#### config_overrides
Runtime configuration overrides with expiration support.

---

### I. Lookup & Reference Tables

#### sports (Lookup) — Migration 0060

Sport-level lookup table. Replaces the pre-Migration 0060 `sport` VARCHAR + CHECK
constraint pattern with an FK to a seeded lookup table (Pattern 81 instance).

#### leagues (Lookup) — Migration 0060

League-level lookup table, FK-linked to `sports`. Same Pattern 81 shape.

#### strategy_types, model_classes (Lookup)

Seeded reference tables for strategy + model classification. Updated with audit
columns in Migration 0002.

#### historical_epa, historical_rankings, historical_stats, team_rankings

Historical sports-data reference tables. `historical_epa` gained audit columns in
Migration 0013.

---

## Views

| View | Purpose | Key Join |
|------|---------|----------|
| current_markets | Markets + latest prices | markets LEFT JOIN market_snapshots WHERE row_current_ind |
| current_game_states | Latest game states | game_states WHERE row_current_ind |
| current_edges | Active edges | edges WHERE row_current_ind |
| current_series | Current series rows | series WHERE row_current_ind |
| current_teams | Current team rows | teams WHERE row_current_ind |
| current_venues | Current venue rows | venues WHERE row_current_ind |
| current_season_standings | Season W/L/D rollup | derived from games + game_states |
| open_positions | Active positions | positions WHERE row_current_ind AND status = 'open' |
| live_positions | Live-environment current positions | positions WHERE row_current_ind AND execution_environment = 'live' |
| paper_positions | Paper-environment current positions | positions WHERE row_current_ind AND execution_environment = 'paper' |
| backtest_positions | Backtest-environment current positions | positions WHERE row_current_ind AND execution_environment = 'backtest' |
| live_trades | Live-environment trades | trades JOIN orders WHERE execution_environment = 'live' |
| paper_trades | Paper-environment trades | trades JOIN orders WHERE execution_environment = 'paper' |
| backtest_trades | Backtest-environment trades | trades JOIN orders WHERE execution_environment = 'backtest' |
| training_data_trades | Trades flagged for ML training | trades JOIN orders WHERE trade_source filters |
| edge_lifecycle | Edge state-machine view | edges + downstream resolution events |
| active_strategies | Deployed strategies | strategies WHERE status = 'active' AND row_current_ind |
| active_models | Models in use | probability_models WHERE status = 'active' AND row_current_ind |
| team_season_records | W/L/D aggregation | UNION ALL from games + game_states with dedup |

> **V2.0 vs V2.1 view-count reconciliation:** V2.0 listed 8 views and described
> the per-mode position views as DROPPED in Migration 0051. The MCP view count is
> 19. Reconciliation: V2.0's "DROPPED" claim referred to the per-mode trade views
> (`live_trades`, `paper_trades`, etc.) being recreated as view-on-view selectors
> after `account_balance` got `execution_environment`; the per-mode position
> views were similarly recreated. The drop + recreation gives the appearance of
> "fewer views" if the recreations are not counted; the live state has them.
> Future cleanup tracked under #897.

---

## Migration Catalog

69 migration files cover slots 0001-0070 (slot 0029 intentionally skipped —
`portfolio_fills` design abandoned pre-baseline). Key structural changes:

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
| 0037 | Rename `markets.league` -> `subcategory` | Naming cleanup |
| 0039-0040 | Sport value renames + Elo column rename | Naming cleanup |
| 0041-0042 | Kalshi team code + team classification | New columns |
| 0045 | External team codes (cross-platform mapping) | New table |
| 0046 | Market depth + daily movement columns | New columns |
| **0048** | **Game odds rename + SCD Type 2** | Major restructure |
| 0049 | account_balance SCD-2 temporal columns + idx_balance_unique_current | SCD-2 retrofit |
| 0050 | Phase 2 indexes for trade execution queries | Performance |
| **0051** | **account_balance.execution_environment** + drop dead per-mode views | Cross-environment isolation kickoff |
| 0052-0055 | execution_environment cascade across account_ledger / settlements / position_exits / exit_attempts | Cross-environment isolation completion |
| 0056 | DB-level write-protection triggers on immutable tables | Append-only enforcement |
| 0057 | 59 FKs converted to ON DELETE RESTRICT + SCD-2 on teams / venues / series | Cascade-safety + dimension SCD-2 |
| 0058 | Business-key column renames (`_key` suffix convention) | Naming convention (Pattern 80 precedent) |
| 0059 | Missing FKs from C2b audit + SCD copy-forward helper | FK completeness |
| **0060** | **sports + leagues lookup tables** (#738 A1) | Pattern 81 instance kickoff |
| 0061 | SET NOT NULL on 12 FK columns + drop 9 redundant CHECKs (#738 A2) | Constraint hardening |
| 0062 | Business key columns on orders / position_exits / exit_attempts (two-step INSERT) | Pattern 80 instance |
| 0063 | orderbook_snapshot_id FK on orders + edges | Attribution chain |
| **0064** | **SCD-2 on strategies + probability_models** | Version-immutable + SCD-2 |
| 0065 | edge_lifecycle realized_pnl sign-inversion fix | View bugfix (#909) |
| 0066 | idx_games_espn_event UNIQUE -> non-unique (Epic #935 Phase 1) | Three-tier identity model retrofit |
| **0067** | **Cohort 1A — canonical_event_domains + canonical_event_types + canonical_events** | Canonical layer kickoff (ADR-118 V2.38) |
| **0068** | **Cohort 1B — canonical_entity_kinds + canonical_entity + canonical_participant_roles + canonical_event_participants + CONSTRAINT TRIGGER** | Canonical entity tier (Pattern 82 instance) |
| **0069** | **Cohort 2 — canonical_markets** | Canonical market tier (ADR-118 V2.39) |
| 0070 | Cohort 1 carry-forward — partial unique index + lifecycle_phase CHECK | Integrity fence (ADR-118 V2.40, Pattern 84 carve-out) |

All migrations have `downgrade()` functions. Migration 0029 intentionally skipped
(`portfolio_fills` eliminated). Migration sequence is just a number; what matters
is the dependency graph.

---

## Cohort Roadmap (Forward-Pointer)

The canonical-layer arc is in progress. Cohorts 1+2 shipped in Migrations
0067-0070; Cohorts 3-9 are planned per ADR-118 + ADR-119
(in `docs/foundation/ARCHITECTURE_DECISIONS.md`), which is the canonical
SSOT for cohort definitions.

| Cohort | Slots (planned) | Focus |
|--------|-----------------|-------|
| 1A + 1B | 0067-0068 (SHIPPED) | canonical_event_* + canonical_entity_* + canonical_participant_roles |
| 2 | 0069 (SHIPPED) | canonical_markets |
| 1 carry-forward | 0070 (SHIPPED) | additive integrity fences |
| 3 | 0071-0075 | matching infrastructure (`match_algorithm`, `canonical_market_links`, `canonical_event_links`, `canonical_match_log`, `canonical_match_reviews`, `canonical_match_overrides`) — 5-slot lock per session 78 council adjudication (Holden's FK-ordering argument: lookup ships first standalone) |
| 4 | 0076-0079 | dim/fact split refinement |
| 5 | 0080-0083 | event-state machine + canonical_event_phase_log |
| 6 | 0084-0085 | views / CRUD / resolver |
| 7 | 0086-0091 | seeding (canonical_events 1:1 from games) + #937 |
| 8 | 0092-0095 | business-key cleanup (per ADR-119) |
| 9 | 0096-0098 | weather Phase 1 (per ADR-119) |

This roadmap is forward-looking — slot numbers are planning estimates, not
commitments. Slots cascade with each cohort's actual scope; ADR-118 / ADR-119
update on amendment. Cohort 3's 5-slot lock displaces all downstream cohorts
by +1 nominally vs ADR-118 V2.39's original numbering (Migration 0070 was
consumed by the Cohort 1 carry-forward in session 75; Cohort 3's
expansion to 5 slots in session 78 cascades the rest).

---

## Freshness Marker Discipline (Pattern 86)

This document and other living canonical docs (ARCHITECTURE_DECISIONS.md,
MASTER_REQUIREMENTS_V2.26.md) carry a freshness marker as an HTML comment near
the top of the file. The marker names the source-of-truth state at last
verification:

```markdown
<!-- FRESHNESS: alembic_head=0070, verified=2026-04-26, tables=51, migrations=69, last_changelog_migration=0070 -->
```

For schema docs the fields are: `alembic_head`, `verified`, `tables`,
`migrations`, `last_changelog_migration`. Other living-doc types use different
field sets (ADR docs use `adr_count` + `last_adr`; requirements use `req_count`
+ `last_review_session`).

The discipline is codified in **Pattern 86: Living-Doc Freshness Markers**
(see `docs/guides/DEVELOPMENT_PATTERNS.md` V1.39). Pattern 86 is Pattern 73
(Single Source of Truth) applied to time: the canonical source-of-truth for a
doc's freshness is the doc itself, and the marker is how the doc declares what
version of truth it claims to represent. V2.0 is the cautionary tale —
V2.0's marker decayed 19 migrations behind its own body without surfacing,
because no concrete marker means "is this doc fresh?" has no answer.

V2.1 is the canonical-form demonstration of the pattern. Future revisions
(V2.2, V2.3, ...) update the marker fields in lockstep with the body.

---

## Version History

| Version | Date | Summary |
|---------|------|---------|
| 2.1 | 2026-04-26 | Re-sync with alembic_head=0070. +8 canonical_* tables (Cohorts 1A+1B+2). Migrations 0049-0070 catalogued. Pattern 86 freshness-marker demonstration. View count corrected (8 -> 19). SCD-2 count corrected (6 -> 11). JSONB column count refresh (25+ -> 52). |
| 2.0 | 2026-04-05 | Complete rewrite. All 42 tables, 8 views, 47 migrations documented. (Marker drifted 19 migrations behind during the gap to V2.1.) |
| 1.16 | 2026-04-03 | Migrations 0044-0048 documented. Gaps for 0014-0043. |
| 1.0 | 2025-10-28 | Initial schema summary. |
