# Schema Design Questions - Comprehensive Analysis

**Date:** 2025-10-24
**Phase:** 1 (Foundation Completion)
**Purpose:** Answer critical schema design questions raised during migration testing
**Status:** FINDINGS DOCUMENTED - Requires user decisions

---

## Executive Summary

During Phase 1 schema migration, several critical schema design inconsistencies were discovered:

1. **row_end_ts Missing:** 9 of 11 SCD Type 2 tables lack `row_end_ts` column
2. **external_id Pattern Incomplete:** Trades/positions/exits lack API traceability
3. **Data Source Ambiguity:** Unclear if settlements/positions/exits come from API or internal logic
4. **ML Tables Unreviewed:** Feature storage tables haven't been evaluated for FK/SCD needs

**Impact:** Schema works but lacks consistency, traceability, and proper SCD Type 2 implementation

**Recommendation:** Create migration 007 to fix all issues systematically

---

## Question 1: Why Don't SCD Type 2 Tables Have row_end_ts?

### Finding

**11 tables with SCD Type 2** (have `row_current_ind`):

| Table | Has row_end_ts? | Status |
|-------|-----------------|--------|
| markets | ✅ YES | Added in migration 005 |
| positions | ✅ YES | Added in migration 005 |
| **edges** | ❌ NO | **MISSING** |
| **game_states** | ❌ NO | **MISSING** |
| **account_balance** | ❌ NO | **MISSING** |
| current_balances | ❌ NO | VIEW (doesn't need it) |
| current_edges | ❌ NO | VIEW (doesn't need it) |
| current_game_states | ❌ NO | VIEW (doesn't need it) |
| current_markets | ❌ NO | VIEW (doesn't need it) |
| open_positions | ❌ NO | VIEW (doesn't need it) |
| positions_urgent_monitoring | ❌ NO | VIEW (doesn't need it) |

**Result:** 3 base tables (edges, game_states, account_balance) are missing `row_end_ts`

### Why This Matters

**SCD Type 2 Pattern Requires:**
1. `row_current_ind BOOLEAN` - Mark current vs historical rows ✅ (all have)
2. `row_end_ts TIMESTAMP` - When did this version become invalid? ❌ (3 missing)
3. `created_at/updated_at` - When was this version created? ✅ (all have)

**Without row_end_ts:**
- Cannot query "What was the edge value at 2pm yesterday?"
- Cannot calculate "How long did each version last?"
- Incomplete historical audit trail

### Recommendation

**Migration 007: Add row_end_ts to remaining SCD Type 2 tables**

```sql
-- edges table
ALTER TABLE edges
ADD COLUMN IF NOT EXISTS row_end_ts TIMESTAMP;

COMMENT ON COLUMN edges.row_end_ts IS 'Timestamp when this edge version became invalid (SCD Type 2)';

CREATE INDEX IF NOT EXISTS idx_edges_row_end_ts
ON edges(row_end_ts)
WHERE row_end_ts IS NOT NULL;

-- game_states table
ALTER TABLE game_states
ADD COLUMN IF NOT EXISTS row_end_ts TIMESTAMP;

COMMENT ON COLUMN game_states.row_end_ts IS 'Timestamp when this game state became invalid (SCD Type 2)';

CREATE INDEX IF NOT EXISTS idx_game_states_row_end_ts
ON game_states(row_end_ts)
WHERE row_end_ts IS NOT NULL;

-- account_balance table
ALTER TABLE account_balance
ADD COLUMN IF NOT EXISTS row_end_ts TIMESTAMP;

COMMENT ON COLUMN account_balance.row_end_ts IS 'Timestamp when this balance record became invalid (SCD Type 2)';

CREATE INDEX IF NOT EXISTS idx_account_balance_row_end_ts
ON account_balance(row_end_ts)
WHERE row_end_ts IS NOT NULL;
```

**Update CRUD Operations:** Ensure `update_edge()`, `update_game_state()`, `update_balance()` functions set `row_end_ts` when marking rows historical.

---

## Question 2: Why Don't Internal Tables Have external_id?

### Finding

**Tables WITH external_id (API-sourced data):**
- ✅ `series.external_id` - Kalshi series ID
- ✅ `events.external_id` - Kalshi event ID
- ✅ `markets.external_id` - Kalshi market ID
- ✅ `game_states.external_game_id` - ESPN/external game ID

**Tables WITHOUT external_id (Internal/calculated data):**
- ❌ `trades` - Has `order_id` (Kalshi order ID) ✅ **Good!**
- ❌ `positions` - **MISSING traceability**
- ❌ `edges` - **MISSING traceability**
- ❌ `settlements` - **AMBIGUOUS** (API or calculated?)
- ❌ `position_exits` - **Internal logic**
- ❌ `exit_attempts` - **Internal logic**

### Analysis by Table

#### trades ✅ CORRECT
**Has:** `order_id VARCHAR` (Kalshi's order ID)
**Source:** Kalshi API `/portfolio/orders` endpoint
**Traceability:** ✅ Can link back to Kalshi order
**Decision:** No changes needed

#### positions ❌ NEEDS REVIEW
**Current:** No `external_id`, no `order_id`
**Source:** Created internally from edge detection
**Question:** Should positions link back to initial trade's `order_id`?

**Recommendation:**
```sql
ALTER TABLE positions
ADD COLUMN initial_order_id VARCHAR REFERENCES trades(order_id);

COMMENT ON COLUMN positions.initial_order_id IS 'Kalshi order ID of trade that opened this position';
```

**Benefit:** Can trace position back to original API order

#### edges ❌ NEEDS REVIEW
**Current:** No `external_id`, no `order_id`
**Source:** Internal calculation (our probability model vs Kalshi market price)
**Question:** Should edges link to the market snapshot that triggered them?

**Recommendation:** NO - edges are pure calculations, not API entities. Add `calculation_run_id` instead:

```sql
ALTER TABLE edges
ADD COLUMN calculation_run_id UUID;

COMMENT ON COLUMN edges.calculation_run_id IS 'Batch ID for this edge detection run (groups edges calculated together)';
```

**Benefit:** Can trace which batch of calculations produced this edge

#### settlements ⚠️ AMBIGUOUS - USER DECISION NEEDED

**Documentation says (DATABASE_SCHEMA_SUMMARY_V1.6.md line 502-514):**
```sql
CREATE TABLE settlements (
    settlement_id SERIAL PRIMARY KEY,
    market_id VARCHAR REFERENCES markets(market_id),
    platform_id VARCHAR REFERENCES platforms(platform_id),
    outcome VARCHAR NOT NULL,            -- 'yes', 'no', or other
    payout DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Two Possible Sources:**

**Option A: Kalshi API** (`/markets/{market_id}/settlements`)
- Kalshi tells us market settled and payout
- **NEEDS:** `external_settlement_id VARCHAR` to link to Kalshi settlement event

**Option B: Internal Logic**
- We calculate P&L based on `trades` and final market price
- **DOESN'T NEED:** `external_id` (pure calculation)

**Question for User:** Are settlements:
1. **Fetched from Kalshi API** (Option A) → Add `external_settlement_id`
2. **Calculated from trades** (Option B) → No changes needed

#### position_exits & exit_attempts ✅ CORRECT
**Source:** Internal exit logic (our code triggers these)
**External Reference:** Links to `trades.order_id` when exit executes
**Decision:** No `external_id` needed (internal operational data)

### Summary: external_id Pattern

**Rule of Thumb:**
- **API-sourced data** → Add `external_*_id` for traceability
- **Internal calculations** → Use surrogate keys, link to API data via FKs
- **Hybrid (API + calculations)** → Decide case-by-case

---

## Question 3: Data Sources for settlements/positions/exits

### positions Table

**Source:** Internal logic (created by our trading engine)

**Lifecycle:**
1. **Edge detected** (our probability model finds value)
2. **Trade executed** via Kalshi API → `trades` row created with `order_id`
3. **Position opened** (our code creates position from trade)
4. **Position updated** as market moves (monitoring loop)
5. **Position closed** when exit condition triggers

**API Touchpoint:** Only via `trades.order_id` (initial entry order)

**Recommendation:** Add `initial_order_id` to link position to opening trade:
```sql
ALTER TABLE positions
ADD COLUMN initial_order_id VARCHAR;

-- Backfill for existing positions
UPDATE positions p
SET initial_order_id = (
    SELECT t.order_id
    FROM trades t
    WHERE t.position_id = p.position_id
    AND t.side = 'buy'
    ORDER BY t.created_at
    LIMIT 1
);

-- Add FK constraint
ALTER TABLE positions
ADD CONSTRAINT fk_positions_initial_order
FOREIGN KEY (initial_order_id) REFERENCES trades(order_id);
```

### position_exits Table

**Source:** Internal logic (our exit management system)

**Lifecycle:**
1. **Exit condition triggers** (stop loss, trailing stop, profit target)
2. **Exit attempt logged** in `exit_attempts` table
3. **Trade executed** via Kalshi API → new `trades` row with `order_id`
4. **Exit recorded** in `position_exits` table

**API Touchpoint:** Links to `trades.order_id` for the exit trade

**Current Schema (DATABASE_SCHEMA_SUMMARY_V1.6.md line 435-449):**
```sql
CREATE TABLE position_exits (
    exit_id SERIAL PRIMARY KEY,
    position_id INT REFERENCES positions(position_id),
    exit_condition VARCHAR(50) NOT NULL,
    exit_priority VARCHAR(20) NOT NULL,
    quantity_exited INT NOT NULL,
    exit_price DECIMAL(10,4) NOT NULL,
    unrealized_pnl_at_exit DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Missing:** Link to the actual exit trade!

**Recommendation:** Add `exit_trade_id` to link to the trade that closed this position:
```sql
ALTER TABLE position_exits
ADD COLUMN exit_trade_id INT REFERENCES trades(trade_id);

COMMENT ON COLUMN position_exits.exit_trade_id IS 'Trade ID of the sell order that exited this position';
```

### exit_attempts Table

**Source:** Internal logic (exit execution debugging)

**Purpose:** Track price walking and order attempts when trying to exit

**Example:**
- Stop loss triggers (CRITICAL)
- Attempt 1: Limit @ $0.75 → No fill (10s timeout)
- Attempt 2: Limit @ $0.74 → No fill (10s timeout) - price walk
- Attempt 3: Market order → Fill @ $0.73 ✅

**API Touchpoint:** Final successful attempt links to `trades.order_id`

**Current Schema (DATABASE_SCHEMA_SUMMARY_V1.6.md line 464-483):**
```sql
CREATE TABLE exit_attempts (
    attempt_id SERIAL PRIMARY KEY,
    position_id INT REFERENCES positions(position_id),
    exit_condition VARCHAR(50) NOT NULL,
    priority_level VARCHAR(20) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    limit_price DECIMAL(10,4),
    fill_price DECIMAL(10,4),
    quantity INT NOT NULL,
    attempt_number INT NOT NULL,
    timeout_seconds INT,
    success BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Missing:** Link to the actual order when attempt succeeds!

**Recommendation:** Add `order_id` to link successful attempts to API orders:
```sql
ALTER TABLE exit_attempts
ADD COLUMN order_id VARCHAR;

COMMENT ON COLUMN exit_attempts.order_id IS 'Kalshi order ID if this attempt resulted in an order (NULL for failed attempts)';

-- Optional: Add FK to trades
-- (Wait until trades table has order_id as candidate key, or accept unverified FK)
```

### settlements Table

**REQUIRES USER DECISION** - Two possible implementations:

#### Option A: API-Sourced (Kalshi tells us settlement outcome)

**Source:** Kalshi API `/markets/{market_id}` (when status = 'finalized')

**Schema Changes:**
```sql
ALTER TABLE settlements
ADD COLUMN external_settlement_id VARCHAR,
ADD COLUMN settlement_timestamp TIMESTAMP,
ADD COLUMN api_response JSONB;

COMMENT ON COLUMN settlements.external_settlement_id IS 'Kalshi settlement event ID';
COMMENT ON COLUMN settlements.api_response IS 'Raw Kalshi settlement response for audit trail';

CREATE INDEX idx_settlements_external ON settlements(external_settlement_id);
```

**Lifecycle:**
1. Poll Kalshi API for market status
2. When market.status = 'finalized', fetch settlement data
3. Insert settlement record with Kalshi's outcome and payout
4. Update positions based on settlement

#### Option B: Internally Calculated (We calculate P&L from trades)

**Source:** Internal calculation based on `trades` and final market state

**Schema Changes:**
```sql
-- No changes needed - current schema sufficient

-- Optional: Add calculation metadata
ALTER TABLE settlements
ADD COLUMN calculation_method VARCHAR DEFAULT 'trade_based',
ADD COLUMN calculation_metadata JSONB;

COMMENT ON COLUMN settlements.calculation_method IS 'How settlement was determined: trade_based, api_sourced, manual';
```

**Lifecycle:**
1. Market closes (status = 'closed')
2. Our code calculates P&L for each position based on:
   - Entry trades (position opening)
   - Exit trades (position closing)
   - Final market price
3. Insert settlement record with calculated outcome/payout
4. Mark positions as 'settled'

**Question for User:** Which option do you prefer? (Likely Option A - trust Kalshi's settlement)

---

## Question 4: ML/Feature Tables - FK and SCD Type 2 Needs

### Tables to Review

**Phase 9 Placeholder Tables:**
1. `feature_definitions` - Feature metadata (immutable versions)
2. `features_historical` - Time-series feature values
3. `training_datasets` - Model training data organization
4. `model_training_runs` - ML experiment tracking

### Analysis

#### feature_definitions ✅ CORRECT

**Current Schema (DATABASE_SCHEMA_SUMMARY_V1.6.md line 815-844):**
```sql
CREATE TABLE feature_definitions (
    feature_id SERIAL PRIMARY KEY,
    feature_name VARCHAR NOT NULL,
    feature_version VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    sport VARCHAR,
    calculation_method TEXT,
    data_type VARCHAR NOT NULL,
    unit VARCHAR,
    description TEXT,
    status VARCHAR DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR,
    UNIQUE(feature_name, feature_version)
);
```

**SCD Type 2?** NO - Uses immutable versioning instead
**External ID?** NO - internal feature catalog
**Foreign Keys?** NONE needed (top-level reference table)

**Decision:** ✅ Schema correct as-is

#### features_historical ⚠️ NEEDS REVIEW

**Current Schema (DATABASE_SCHEMA_SUMMARY_V1.6.md line 870-893):**
```sql
CREATE TABLE features_historical (
    feature_record_id SERIAL PRIMARY KEY,
    feature_id INT NOT NULL REFERENCES feature_definitions(feature_id),
    entity_type VARCHAR NOT NULL,  -- 'team', 'player', 'market', 'game'
    entity_id VARCHAR NOT NULL,     -- team_id, player_id, market_id, game_id
    timestamp TIMESTAMP NOT NULL,
    feature_value DECIMAL(12,6),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Issue 1: entity_id is VARCHAR** - Should link to actual tables!

**Problem:**
- `entity_id` = 'KC' (Kansas City Chiefs)
- No foreign key constraint → data integrity risk
- Can't join to `teams` table (doesn't exist yet!)

**Recommendation:** Add entity-specific FK columns:
```sql
ALTER TABLE features_historical
ADD COLUMN team_id VARCHAR REFERENCES teams(team_id),
ADD COLUMN player_id VARCHAR REFERENCES players(player_id),
ADD COLUMN event_id VARCHAR REFERENCES events(event_id),
ADD COLUMN market_id VARCHAR REFERENCES markets(market_id);

-- Deprecate generic entity_id/entity_type
-- (Keep for backward compatibility but discourage use)

-- Add CHECK constraint: exactly one entity FK must be NOT NULL
ALTER TABLE features_historical
ADD CONSTRAINT features_historical_entity_check
CHECK (
    (team_id IS NOT NULL AND player_id IS NULL AND event_id IS NULL AND market_id IS NULL) OR
    (player_id IS NOT NULL AND team_id IS NULL AND event_id IS NULL AND market_id IS NULL) OR
    (event_id IS NOT NULL AND team_id IS NULL AND player_id IS NULL AND market_id IS NULL) OR
    (market_id IS NOT NULL AND team_id IS NULL AND player_id IS NULL AND event_id IS NULL)
);
```

**Issue 2: Needs external_id for data source traceability**

**Problem:** Feature values often come from external APIs:
- ESPN API (team stats, player stats)
- Football Outsiders (DVOA, EPA)
- Pro Football Reference (historical data)

**Recommendation:** Add `external_source` and `external_reference_id`:
```sql
ALTER TABLE features_historical
ADD COLUMN external_source VARCHAR,  -- 'espn_api', 'football_outsiders', 'pro_football_reference'
ADD COLUMN external_reference_id VARCHAR;  -- External API's ID for this data point

COMMENT ON COLUMN features_historical.external_source IS 'External API/system that provided this feature value';
COMMENT ON COLUMN features_historical.external_reference_id IS 'External system ID for audit trail (e.g., ESPN game ID)';
```

**Issue 3: SCD Type 2?** NO - Time-series data (timestamp IS the versioning)

**Decision:** No `row_current_ind` needed - `timestamp` column provides temporal ordering

#### training_datasets ✅ MOSTLY CORRECT

**Current Schema (DATABASE_SCHEMA_SUMMARY_V1.6.md - not shown, needs verification):**

**Expected:**
```sql
CREATE TABLE training_datasets (
    dataset_id SERIAL PRIMARY KEY,
    dataset_name VARCHAR NOT NULL,
    dataset_version VARCHAR NOT NULL,
    sport VARCHAR,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    feature_ids INT[] NOT NULL,  -- Array of feature_definition IDs
    target_variable VARCHAR NOT NULL,
    row_count INT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(dataset_name, dataset_version)
);
```

**SCD Type 2?** NO - Immutable versions (like feature_definitions)
**External ID?** NO - internal training artifact
**Foreign Keys?** ✅ Has implicit FK via `feature_ids` array

**Recommendation:** Consider adding explicit FKs to events/markets for time range:
```sql
ALTER TABLE training_datasets
ADD COLUMN start_event_id VARCHAR REFERENCES events(event_id),
ADD COLUMN end_event_id VARCHAR REFERENCES events(event_id);

COMMENT ON COLUMN training_datasets.start_event_id IS 'First event included in training data';
COMMENT ON COLUMN training_datasets.end_event_id IS 'Last event included in training data';
```

#### model_training_runs ✅ MOSTLY CORRECT

**Expected Schema:**
```sql
CREATE TABLE model_training_runs (
    run_id SERIAL PRIMARY KEY,
    model_id INT REFERENCES probability_models(model_id),
    dataset_id INT REFERENCES training_datasets(dataset_id),
    hyperparameters JSONB NOT NULL,
    metrics JSONB,  -- accuracy, precision, recall, F1, AUC, etc.
    training_duration_seconds INT,
    status VARCHAR DEFAULT 'running',  -- 'running', 'completed', 'failed'
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

**SCD Type 2?** NO - Append-only log (runs never change)
**External ID?** NO - internal experiment tracking
**Foreign Keys?** ✅ Correct - links to models and datasets

**Decision:** ✅ Schema correct as-is

### Missing Tables for ML Infrastructure

**teams table** - Not in database yet!
- Needed for `features_historical.team_id` FK
- Should have: `team_id`, `team_name`, `sport`, `external_espn_id`, etc.

**players table** - Not in database yet!
- Needed for `features_historical.player_id` FK
- Should have: `player_id`, `player_name`, `team_id`, `external_espn_id`, etc.

**Recommendation:** Add these tables in Phase 4 (when Elo models are introduced)

---

## Summary of Required Changes

### Migration 007: Complete SCD Type 2 Implementation

**Add row_end_ts to 3 tables:**
1. `edges.row_end_ts`
2. `game_states.row_end_ts`
3. `account_balance.row_end_ts`

### Migration 008: Add External ID Traceability

**Add API traceability columns:**
1. `positions.initial_order_id` → Link to opening trade
2. `position_exits.exit_trade_id` → Link to closing trade
3. `exit_attempts.order_id` → Link to API order (when successful)
4. `settlements.external_settlement_id` (IF using Kalshi API)
5. `edges.calculation_run_id` → Batch ID for edge detection runs

### Migration 009: Fix markets SCD Type 2 PRIMARY KEY

**Add surrogate PRIMARY KEY:**
1. Add `markets.id SERIAL`
2. Update FK references in edges, positions, trades
3. Drop `market_id` PRIMARY KEY
4. Add UNIQUE constraint on `(market_id, row_current_ind)` WHERE `row_current_ind = TRUE`

### Phase 9: ML Tables Enhancement (DEFERRED)

**When implementing ML infrastructure:**
1. Add `features_historical` entity-specific FKs (team_id, player_id, etc.)
2. Add `features_historical.external_source` and `external_reference_id`
3. Create `teams` and `players` tables
4. Add `training_datasets` event range FKs

---

## User Decisions Required

### Decision 1: settlements Data Source

**Question:** Are settlements:
- **Option A:** Fetched from Kalshi API (add `external_settlement_id`)
- **Option B:** Calculated internally from trades (no changes)

**Recommendation:** Option A (trust Kalshi's official settlement)

### Decision 2: Migration Priority

**Question:** Which migrations to execute now vs defer?

**Recommendation:**
- **NOW (Phase 1):**
  - Migration 007 (row_end_ts) - 15 min
  - Migration 009 (markets PRIMARY KEY) - 60 min
- **NEXT (Phase 2):**
  - Migration 008 (external_id traceability) - 30 min
- **LATER (Phase 9):**
  - ML tables enhancements

### Decision 3: Backfill Strategy

**Question:** For new columns, backfill existing data or leave NULL?

**Examples:**
- `positions.initial_order_id` - Can backfill from trades table
- `edges.row_end_ts` - Cannot backfill (historical data lost)
- `settlements.external_settlement_id` - Depends on data source

**Recommendation:** Backfill where possible, document limitations in migration SQL

---

## Next Steps

1. **User Review:** Answer Decision 1-3 above
2. **Create Migrations:** Write SQL for migrations 007-009
3. **Test Migrations:** Run on precog_dev database
4. **Update CRUD Operations:** Ensure functions use new columns correctly
5. **Update Tests:** Verify SCD Type 2 behavior with row_end_ts
6. **Document Changes:** Update DATABASE_SCHEMA_SUMMARY V1.6 → V1.7

---

**Analysis complete. Awaiting user decisions on data sources and migration priorities.**
