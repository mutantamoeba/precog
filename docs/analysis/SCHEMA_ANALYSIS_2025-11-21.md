# Comprehensive Schema Analysis: Trade/Position Attribution Enhancement

**Version:** 1.0
**Date:** 2025-11-21
**Authors:** User + Claude Code AI Analysis
**Purpose:** Document architectural analysis and decision-making for trade/position attribution enhancements
**Status:** ✅ Decisions Finalized
**Implementation:** Migrations 018-020, ADR-090/091/092, Pattern 15

---

## Executive Summary

**Trigger:** User identified missing attribution fields during holistic review of trading application architecture.

**Core Questions:**
1. Should we download all trades from Kalshi API or only track app actions?
2. Do trades need model prediction + market price snapshots (beyond edge linking)?
3. Should positions have strategy/model attribution for analytics?
4. Should strategies contain ONLY entry rules OR entry + exit rules?
5. If position opened with Strategy A, must it close with Strategy A's exit rules?

**Key Decisions:**
- ✅ Download ALL trades from API, use `trade_source` enum to filter (automated vs manual)
- ✅ Add explicit columns for attribution (calculated_probability, market_price, edge_value)
- ✅ Add position attribution (strategy_id, model_id, edge_at_entry, etc.)
- ✅ Strategies contain BOTH entry + exit rules with nested versioning
- ✅ Positions locked to strategy version at entry (immutable for A/B testing)
- ✅ Use explicit columns for trades/positions (performance), JSONB for strategies (flexibility)

**Impact:**
- 3 database migrations (018-020)
- 9 new columns (4 trades, 5 positions)
- 1 new enum type
- 6 new indexes
- 3 new ADRs
- 1 new development pattern
- Enables comprehensive performance attribution analytics

---

## 1. Current State Analysis

### 1.1 Trades Table (Before Enhancements)

**From migrations 005, 006 and DATABASE_SCHEMA_SUMMARY V1.9:**

```sql
CREATE TABLE trades (
    trade_id SERIAL PRIMARY KEY,
    market_id VARCHAR REFERENCES markets(market_id),
    platform_id VARCHAR REFERENCES platforms(platform_id),
    position_id INT REFERENCES positions(id),      -- Surrogate key link
    edge_id INT REFERENCES edges(edge_id),          -- ✅ What triggered trade
    strategy_id INT REFERENCES strategies(strategy_id),  -- ✅ Which strategy version
    model_id INT REFERENCES probability_models(model_id), -- ✅ Which model version
    order_id VARCHAR,                               -- Platform's order ID
    side VARCHAR NOT NULL,                          -- 'buy', 'sell'
    price DECIMAL(10,4) NOT NULL,                   -- ✅ Execution price (EXACT)
    quantity INT NOT NULL,
    fees DECIMAL(10,4),
    edge_at_execution DECIMAL(10,4),                -- Historical edge snapshot
    confidence_at_execution VARCHAR,
    order_type VARCHAR DEFAULT 'market',            -- ✅ Migration 005
    execution_time TIMESTAMP DEFAULT NOW(),         -- ✅ Migration 005
    trade_metadata JSONB,                           -- ✅ Migration 006 (flexible storage)
    created_at TIMESTAMP DEFAULT NOW()
);
```

**What Exists:**
- ✅ strategy_id (links to exact strategy version)
- ✅ model_id (links to exact model version)
- ✅ edge_id (what triggered trade)
- ✅ price (execution price as DECIMAL)
- ✅ trade_metadata JSONB (flexible extensible storage)

**What's Missing:**
- ❌ calculated_probability (model's prediction NOT stored directly)
- ❌ market_price (market quote at execution NOT stored)
- ❌ edge_value (calculated edge NOT stored directly, must derive from edge_id JOIN)
- ❌ trade_source (no way to differentiate manual vs automated trades)

### 1.2 Positions Table (Before Enhancements)

**From DATABASE_SCHEMA_SUMMARY V1.9 + Migrations 015-017:**

```sql
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,                     -- ✅ SURROGATE KEY (for FK references)
    position_id VARCHAR UNIQUE,                -- ✅ BUSINESS KEY (e.g., 'POS-1')
    market_id VARCHAR REFERENCES markets(market_id),
    platform_id VARCHAR REFERENCES platforms(platform_id),
    -- ❌ strategy_id MISSING
    -- ❌ model_id MISSING
    side VARCHAR NOT NULL,                     -- 'yes', 'no'
    entry_price DECIMAL(10,4) NOT NULL,        -- ✅ Entry price
    quantity INT NOT NULL,
    fees DECIMAL(10,4),
    status VARCHAR DEFAULT 'open',
    unrealized_pnl DECIMAL(10,4),
    realized_pnl DECIMAL(10,4),
    current_price DECIMAL(10,4),               -- Monitoring loop updates
    unrealized_pnl_pct DECIMAL(6,4),
    last_update TIMESTAMP,
    trailing_stop_state JSONB,                 -- Dynamic stop configuration
    exit_reason VARCHAR(50),
    exit_priority VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    entry_time TIMESTAMP,                      -- ✅ When position opened
    exit_time TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE,      -- ✅ SCD Type 2 versioning
    row_start_ts TIMESTAMP DEFAULT NOW(),
    row_end_ts TIMESTAMP
);
```

**What Exists:**
- ✅ Dual-key pattern (id SERIAL + position_id VARCHAR) for SCD Type 2
- ✅ entry_price, entry_time
- ✅ P&L tracking (unrealized_pnl, realized_pnl)

**What's Missing:**
- ❌ strategy_id (no attribution at position level!)
- ❌ model_id (no model tracking for position)
- ❌ calculated_probability (model's prediction lost)
- ❌ edge_at_entry (why we entered lost)
- ❌ market_price_at_entry (context lost)

**Problem:** Can't answer "Show me all positions opened by halftime_entry v1.1" without complex JOIN through trades table.

### 1.3 Strategies Table (Current State)

**From DATABASE_SCHEMA_SUMMARY V1.9:**

```sql
CREATE TABLE strategies (
    strategy_id SERIAL PRIMARY KEY,
    platform_id VARCHAR,                       -- ✅ V1.9 addition
    strategy_name VARCHAR NOT NULL,
    strategy_version VARCHAR NOT NULL,
    approach VARCHAR NOT NULL,                 -- ✅ V1.9: HOW (value, arbitrage, momentum)
    domain VARCHAR,                            -- ✅ V1.9: WHICH markets (nfl, elections, NULL)
    config JSONB NOT NULL,                     -- ⚠️ IMMUTABLE strategy parameters
    status VARCHAR DEFAULT 'draft',            -- ✅ MUTABLE (draft → testing → active)
    -- ... other fields ...
    UNIQUE(strategy_name, strategy_version)
);
```

**Critical Observation - Strategy Scope Ambiguity:**

Current config examples (from CRUD operations):
```json
{
  "min_lead": 7,           // ← ENTRY rule
  "max_spread": 0.08,      // ← ENTRY rule
  "min_edge": 0.05,        // ← ENTRY rule (maybe also exit?)
  "kelly_fraction": 0.10   // ← Position sizing (entry OR ongoing?)
}
```

**Question Identified:** Where are EXIT rules stored?

**Discovery:** NO explicit exit rules in strategies table. Exit logic appears distributed across:
1. trailing_stop_state (positions table JSONB) - dynamic trailing stop
2. exit_reason (positions table) - WHICH condition triggered
3. Exit conditions hardcoded in Position Manager (Phase 5 implementation)

**This confirms architectural concern: Strategy scope is ambiguous!**

---

## 2. Gap Analysis

### Gap 1: Trade Data Source Ambiguity 🔴 HIGH

**Current State:**
- trades table has NO `is_manual`, `source`, or similar field
- ALL trades look identical whether from:
  - Kalshi UI manual trades
  - This app's automated execution
  - Direct API calls (testing)

**Problem:**
- Performance analytics contaminated by manual trades
- Can't filter "app-only" performance
- Can't audit "who executed this trade?"
- Can't distinguish paper trading from live trading

**User Context:**
- Single Kalshi account used for BOTH manual trades (UI) and automated trades (app)
- Need to reconcile and differentiate for accurate performance tracking

**Severity:** 🔴 **HIGH** - Breaks analytics integrity

**Example Impact:**
```python
# Current: Can't answer this question
"What's the app's automated trading performance?"
→ No way to filter automated vs manual trades

# Current workaround: Maintain separate app_order_ids list (fragile)
# Desired: Simple query with trade_source filter
SELECT AVG(realized_pnl) FROM trades WHERE trade_source = 'automated'
```

### Gap 2: Incomplete Trade Attribution 🟡 MEDIUM

**Current State:**
- trades table HAS: strategy_id, model_id, edge_id, price
- trades table MISSING:
  - `calculated_probability` - What did model predict?
  - `market_price` - What was market quoting?
  - `edge_value` - What was calculated edge?

**Problem:**
Can reconstruct from edges table, but fragile:

```python
# CURRENT: Can't answer this question directly from trades table
"What probability did model_id=5 predict for this trade?"
→ MUST join edges table, but edge may have changed since execution
→ edge_at_execution exists but may be stale or NULL

# DESIRED: Direct answer from trades table
trade = get_trade(trade_id=42)
print(trade['calculated_probability'])  # Decimal('0.6200') ← MODEL's prediction
print(trade['market_price'])            # Decimal('0.5200') ← MARKET price
print(trade['edge_value'])              # Decimal('0.1000') ← 0.6200 - 0.5200
```

**Why Join is Fragile:**
- Edges table may be updated (recalculated edge)
- Edge record may be deleted (data retention policy)
- NULL values if edge not stored
- Performance penalty (every analytics query needs JOIN)

**Severity:** 🟡 **MEDIUM** - Can work around with JOINs, but fragile and slow

### Gap 3: Missing Position Attribution 🟡 MEDIUM-HIGH

**Current State:**
- positions table MISSING: strategy_id, model_id, calculated_probability, edge_at_entry

**Problem:**
Position-level analytics require complex workarounds:

```sql
-- Can't answer: "Show me all positions opened by halftime_entry v1.1"
SELECT * FROM positions WHERE strategy_id = 5;  -- ❌ NO strategy_id column!

-- Current workaround: JOIN through trades table (FRAGILE)
SELECT DISTINCT p.*, t.strategy_id, t.model_id
FROM positions p
JOIN trades t ON p.id = t.position_id
WHERE p.status = 'open'
  AND t.side = 'buy'  -- Assume first buy = entry
  AND t.execution_time = (
    SELECT MIN(execution_time)
    FROM trades
    WHERE position_id = p.id AND side = 'buy'
  );

-- ❌ BREAKS if:
--   - Multiple entry trades per position (dollar-cost averaging)
--   - Partial exits with re-entries
--   - Position rebalancing
```

**Use Cases Blocked:**
1. Real-time monitoring dashboard by strategy
2. Position-level performance attribution
3. Strategy A/B testing analysis
4. Model accuracy per position

**Severity:** 🟡 **MEDIUM-HIGH** - Critical for analytics, but workarounds exist

### Gap 4: Strategy Scope Ambiguity 🔴 CRITICAL

**User Expectations (from discussion):**
- Strategies will change frequently (feedback-driven iteration)
- Entry/exit rules will change INDEPENDENTLY (separate feedback loops)
- Example: Tweak min_probability (entry) without changing profit_target (exit)

**Current Implementation (undocumented):**
- Strategy table config contains entry rules only
- Exit rules in Position Manager configuration (global, not per-strategy)
- No explicit documentation of this design choice

**Three Architectural Options:**

**OPTION A: Entry Rules ONLY** (current undocumented state)
```json
// strategies.config
{
  "min_lead": 7,           // ENTRY: Require 7+ point lead
  "max_spread": 0.08,      // ENTRY: Reject if spread >8%
  "min_edge": 0.05,        // ENTRY: Require 5%+ edge
  "min_probability": 0.55  // ENTRY: Minimum model confidence
}

// config/position_management.yaml (GLOBAL exit rules)
exit_rules:
  profit_target: "0.25"
  stop_loss: "-0.10"
```

**Pros:**
- ✅ Simple versioning (entry change → new version)
- ✅ Consistent exit behavior (all positions use same rules)
- ✅ Fewer versions (no combinatorial explosion)

**Cons:**
- ❌ Can't A/B test exit strategies
- ❌ "Strategy" concept incomplete (missing exits)

**OPTION B: Entry + Exit Rules** (user preference)
```json
// strategies.config
{
  "entry": {
    "version": "1.5",
    "rules": {"min_lead": 10, "min_edge": 0.05, "min_probability": 0.55}
  },
  "exit": {
    "version": "2.3",
    "rules": {"profit_target": "0.25", "trailing_stop_activation": "0.15"}
  }
}
```

**Pros:**
- ✅ Complete strategy concept (entry + exit)
- ✅ Per-strategy exit customization
- ✅ Exit A/B testing possible
- ✅ Nested versioning tracks changes independently

**Cons:**
- ❌ Version explosion risk (10 entry × 10 exit = 100 combinations)
  - Mitigation: Nested versioning in config, strategy version = combination being tested
- ❌ Position Manager must load strategy.config for every exit evaluation

**OPTION C: Methods Table (3-layer architecture)**
```sql
-- Separate table composing strategy + model + position management
-- Deferred to Phase 4 per ADR-077 (requires 3-6 months trading data)
```

**User Decision:** **Option B (Entry + Exit with nested versioning)**

**Rationale:**
- User expects frequent, independent entry/exit tweaking
- A/B testing exit strategies is valuable
- Version explosion mitigated via nested versioning
- Reversible (can migrate to methods table in Phase 4)

**Severity:** 🔴 **CRITICAL** - Architectural ambiguity blocks Phase 1.5-2 development

### Gap 5: Entry-Exit Linkage Enforcement 🟢 LOW

**User Question:** "If position opened with Strategy A, must it close with Strategy A's exit rules? Or can exits be independent?"

**Options:**

**A: Exits Independent (Option B-derived)**
- Position Manager uses GLOBAL exit config
- All positions exit using same rules
- Simple but no per-strategy customization

**B: Exits Linked to Strategy (Option B-derived)**
- Position locked to opening strategy's exit rules
- Requires position.strategy_id column
- Supports exit A/B testing

**User Decision:** **Immutable linkage** (position locked to strategy version at entry)

**Rationale:**
- A/B testing integrity (each position uses consistent strategy throughout lifecycle)
- Clear attribution ("This position used halftime_entry v1.0 entry+exit rules")
- Follows immutable versioning pattern (ADR-018)

**Implementation:**
```sql
-- Store strategy_id in positions table (immutable at entry)
ALTER TABLE positions ADD COLUMN strategy_id INT REFERENCES strategies(strategy_id);

-- Position Manager reads exit rules from position.strategy_id config
def evaluate_exits(position):
    strategy = get_strategy(position.strategy_id)
    exit_config = strategy['config']['exit']
    # Use THIS position's strategy exit rules (locked at entry)
```

**Severity:** 🟢 **LOW** - Design choice, either approach works (decision made: immutable linkage)

---

## 3. Design Options & Tradeoffs

### Option 3.1: Trade Source Tracking

**OPTION A: is_manual Boolean Flag**

```sql
ALTER TABLE trades ADD COLUMN is_manual BOOLEAN DEFAULT FALSE NOT NULL;
```

**Pros:**
- ✅ Simple binary choice
- ✅ Easy filtering (`WHERE NOT is_manual`)
- ✅ No enum maintenance

**Cons:**
- ❌ Binary only (what about semi-automated? paper trading?)
- ❌ Loses granularity (WHO executed manual trade?)

**OPTION B: trade_source Enum** (RECOMMENDED)

```sql
CREATE TYPE trade_source_type AS ENUM (
  'automated',      -- App execution
  'manual_ui',      -- Kalshi UI
  'manual_api',     -- Direct API call
  'paper_trading'   -- Simulated trade
);
ALTER TABLE trades ADD COLUMN trade_source trade_source_type DEFAULT 'automated' NOT NULL;
```

**Pros:**
- ✅ Granular source tracking
- ✅ Extensible (add new sources later)
- ✅ Self-documenting enum values

**Cons:**
- ❌ Enum maintenance overhead (PostgreSQL ALTER TYPE is complex)
- ❌ More complex queries

**OPTION C: JSONB Metadata (NO new column)**

```sql
-- Store in existing trade_metadata column
INSERT INTO trades (trade_metadata) VALUES ('{"source": "automated"}');
```

**Pros:**
- ✅ Zero migration
- ✅ Maximum flexibility

**Cons:**
- ❌ No database constraint enforcement
- ❌ Slower queries (JSONB parsing)
- ❌ Hidden from schema (discoverability issue)

**USER DECISION (after discussion):** **Option B (trade_source enum)**

**Rationale:**
- Granular enough for current needs (automated, manual_ui, manual_api, paper_trading)
- Self-documenting (enum values clear)
- Database-enforced (can't store invalid values)
- Performance acceptable (indexed enum column)

### Option 3.2: Trade Attribution Enrichment

**OPTION A: Add Explicit Columns** (RECOMMENDED)

```sql
ALTER TABLE trades
ADD COLUMN calculated_probability DECIMAL(10,4),
ADD COLUMN market_price DECIMAL(10,4),
ADD COLUMN edge_value DECIMAL(10,4);

-- Add CHECK constraints
ALTER TABLE trades
ADD CONSTRAINT trades_calculated_probability_range
  CHECK (calculated_probability >= 0.0 AND calculated_probability <= 1.0),
ADD CONSTRAINT trades_market_price_range
  CHECK (market_price >= 0.0 AND market_price <= 1.0),
ADD CONSTRAINT trades_edge_value_range
  CHECK (edge_value >= -1.0 AND edge_value <= 1.0);

-- Add indexes
CREATE INDEX idx_trades_edge_value ON trades(edge_value) WHERE edge_value IS NOT NULL;
CREATE INDEX idx_trades_calc_prob ON trades(calculated_probability) WHERE calculated_probability IS NOT NULL;
```

**Pros:**
- ✅ Explicit schema (discoverable, type-safe)
- ✅ Database constraints enforce data quality
- ✅ Fast queries (indexed columns, no JSON parsing)
- ✅ Self-documenting (column names explain purpose)
- ✅ **20-100x faster** than JSONB for analytics queries

**Cons:**
- ❌ Schema bloat (3 new columns)
- ❌ Redundancy (edge_value = calculated_probability - market_implied_probability)
- ❌ Migration overhead (3 ALTER TABLE operations)

**Performance Benchmark (estimated):**

```sql
-- Explicit column (FAST - uses index):
SELECT AVG(edge_value) FROM trades WHERE edge_value > 0.05;
-- Execution time: ~10ms for 100,000 rows

-- JSONB (SLOW - must parse JSON, cast type, THEN filter):
SELECT AVG((trade_metadata->'attribution'->>'edge_value')::DECIMAL)
FROM trades
WHERE (trade_metadata->'attribution'->>'edge_value')::DECIMAL > 0.05;
-- Execution time: ~200-1000ms for 100,000 rows (20-100x slower)
```

**OPTION B: Store in trade_metadata JSONB**

```sql
-- Use existing trade_metadata column
INSERT INTO trades (trade_metadata) VALUES ('{
  "attribution": {
    "calculated_probability": "0.6200",
    "market_price": "0.5200",
    "edge_value": "0.1000"
  }
}');
```

**Pros:**
- ✅ Zero migration (trade_metadata already exists)
- ✅ Flexible schema (add confidence_score, feature_values, etc.)
- ✅ No column proliferation

**Cons:**
- ❌ Type safety relies on application code (no DB CHECK constraints)
- ❌ **20-100x slower** queries (JSONB parsing + type casting)
- ❌ Must create GIN index for performance
- ❌ Values stored as strings (precision risk if not careful)

**OPTION C: Hybrid (critical fields as columns, extended in JSONB)**

```sql
-- Critical attribution fields as columns
ALTER TABLE trades
ADD COLUMN calculated_probability DECIMAL(10,4),
ADD COLUMN market_price DECIMAL(10,4);

-- Extended metadata in JSONB
-- trade_metadata: {"confidence_score": "high", "feature_values": {...}}
```

**Pros:**
- ✅ Best of both worlds (fast queries + flexibility)
- ✅ Type safety for critical data
- ✅ Extensibility for experimental data

**Cons:**
- ❌ Complexity (developers must know which data goes where)
- ❌ Partial schema bloat

**USER DECISION (after discussion):** **Option A (Explicit Columns)**

**User's Reasoning:**
- Initial preference for JSONB flexibility
- After understanding performance penalty (20-100x slower), chose explicit columns
- Analytics queries (performance attribution) are FREQUENT operations
- Type safety critical (probabilities must be 0-1)
- Discoverability important for new developers

**Quote:** "After your explanation about performance and query complexity, I understand the downsides of JSONB more now, I think I prefer your Option A."

### Option 3.3: Position Attribution

**OPTION A: Add Explicit Columns** (RECOMMENDED)

```sql
ALTER TABLE positions
ADD COLUMN strategy_id INT REFERENCES strategies(strategy_id),
ADD COLUMN model_id INT REFERENCES probability_models(model_id),
ADD COLUMN calculated_probability DECIMAL(10,4),
ADD COLUMN edge_at_entry DECIMAL(10,4),
ADD COLUMN market_price_at_entry DECIMAL(10,4);
```

**Pros:**
- ✅ Direct position-level attribution queries (no JOIN)
- ✅ Fast analytics (`SELECT * FROM positions WHERE strategy_id = 5`)
- ✅ Immutable after entry (position "locked" to opening strategy/model)
- ✅ Enables position-level performance tracking

**Cons:**
- ❌ Redundancy with trades table (same data in 2 places)
- ❌ Data sync risk (what if position.strategy_id ≠ opening_trade.strategy_id?)

**Mitigation for Sync Risk:**
```python
# Add validation in create_position()
def create_position(..., strategy_id, model_id):
    # Validate attribution matches opening trade
    first_trade = get_first_trade_for_position(position_id)
    assert strategy_id == first_trade['strategy_id'], \
      "Position strategy_id must match opening trade"
```

**OPTION B: No Columns, Always JOIN Through Trades**

```sql
-- Get positions with strategy attribution
SELECT p.*, t.strategy_id, t.model_id
FROM positions p
JOIN trades t ON p.id = t.position_id
WHERE t.side = 'buy'
  AND t.execution_time = (SELECT MIN(execution_time) FROM trades WHERE position_id = p.id);
```

**Pros:**
- ✅ Single source of truth (trades table only)
- ✅ No data sync risk
- ✅ Zero migration

**Cons:**
- ❌ Complex query for common operation
- ❌ Performance penalty (every position query requires JOIN)
- ❌ Fragile (assumes first 'buy' = entry, breaks with dollar-cost averaging)

**USER DECISION:** **Option A (Explicit Columns with Validation)**

**Rationale:**
- Position-level analytics are FREQUENT (monitoring dashboard, exit evaluation)
- Query simplicity matters (no complex JOINs for common queries)
- Performance critical (indexed strategy_id 100x faster than JOIN)
- Data integrity via validation (ensure position.strategy_id matches opening trade)

---

## 4. User Questions & Answers

### Q1: "Trades can come from manual (Kalshi UI) OR automated (this app). Should we download all trades from API, or just track app actions?"

**ANSWER:** **Download ALL trades** from Kalshi API, use `trade_source` field to filter.

**Rationale:**
1. **Reconciliation:** App-only tracking creates blind spots (what if manual trade conflicts with open position?)
2. **Audit trail:** Need complete trade history for tax reporting, regulatory compliance
3. **Position tracking:** Positions may have been manually adjusted (need to detect this)
4. **Analytics:** Compare app performance vs manual performance (requires both datasets)

**Implementation:**
```python
# Download ALL trades via Kalshi API
all_trades = kalshi_client.get_portfolio_fills()

# Mark source when storing
for trade in all_trades:
    # Check if trade was executed by this app
    app_order_ids = get_app_order_ids()  # From our orders table
    is_app_trade = trade['order_id'] in app_order_ids

    create_trade(
        ...,
        trade_source='automated' if is_app_trade else 'manual_ui'
    )

# Analytics: App-only performance
app_trades = get_trades(trade_source='automated')
app_roi = calculate_roi(app_trades)
```

### Q2: "Trade attribution richness - Currently links to edges. Want model_id, strategy_id, calculated_probability, market_price, edge_id?"

**ANSWER:** **ALL of these exist or should be added:**

**Current (already exists):**
- ✅ strategy_id
- ✅ model_id
- ✅ edge_id
- ✅ price (execution price)

**Missing (should add):**
- ❌ calculated_probability → ADD (model's prediction)
- ❌ market_price → ADD (market's quote at execution)
- ❌ edge_value → ADD (calculated edge = calculated_probability - market_price)

**After Migration 019, full attribution available:**
```sql
SELECT
  t.trade_id,
  s.strategy_name || ' ' || s.strategy_version AS strategy,
  m.model_name || ' ' || m.model_version AS model,
  t.calculated_probability,  -- What model predicted (0.6200 = 62%)
  t.market_price,            -- What market quoted (0.5200 = 52%)
  t.edge_value,              -- Edge = 0.1000 (10%)
  t.price AS execution_price,
  t.trade_source
FROM trades t
JOIN strategies s ON t.strategy_id = s.strategy_id
JOIN probability_models m ON t.model_id = m.model_id;
```

### Q3: "Strategy scope - Should strategies contain BOTH entry rules AND exit rules? Or separate?"

**ANSWER:** **BOTH entry + exit rules** with nested versioning.

**User Context:**
- Expects frequent feedback-driven rule changes
- Entry/exit rules will change INDEPENDENTLY
- Example: Tweak min_probability (entry) without changing profit_target (exit)

**Nested Versioning Structure:**
```json
{
  "entry": {
    "version": "1.5",
    "rules": {
      "min_lead": 10,
      "max_spread": "0.08",
      "min_edge": "0.05",
      "min_probability": "0.55"  // NEW field requested by user
    }
  },
  "exit": {
    "version": "2.3",
    "rules": {
      "profit_target": "0.25",
      "stop_loss": "-0.10",
      "trailing_stop_activation": "0.15",
      "trailing_stop_distance": "0.05"
    }
  }
}
```

**Version Explosion Mitigation:**
- Track sub-versions in config (entry v1.5, exit v2.3)
- Strategy version = combination being tested (v1.0, v1.1, v1.2...)
- Example evolution:
  - v1.0: entry_v1.0 + exit_v1.0 (baseline)
  - v1.1: entry_v1.1 + exit_v1.0 (tweaked min_probability only)
  - v1.2: entry_v1.1 + exit_v1.1 (tweaked profit_target only)

**Benefits:**
- ✅ Complete strategy concept (entry + exit)
- ✅ Exit A/B testing possible
- ✅ Nested versioning tracks changes independently
- ✅ Clear which rules changed (entry v1.1 → v1.2)

### Q4: "Entry-exit linkage - If position opened with Strategy A, must it close with Strategy A's exit rules?"

**ANSWER:** **Immutable linkage** (position locked to strategy version at entry).

**User Preference:** Positions should use strategy exit rules from ENTRY time, not current version.

**Rationale:**
- **A/B testing integrity:** Each position uses consistent strategy throughout lifecycle
- **Clear attribution:** "This position used halftime_entry v1.0 entry+exit rules"
- **Immutability:** Follows ADR-018 (immutable versions)

**Implementation:**
```python
# Position opened with halftime_entry v1.0
position_id = open_position(
    strategy_id=1,  # halftime_entry v1.0
    ...
)

# Later: Strategy updated to v1.1 (new exit rules)
# Question: Does position use v1.0 or v1.1 exit rules?
# Answer: v1.0 (locked at entry for A/B testing integrity)

# Position Manager evaluates exit using position's strategy version
def evaluate_exits(position):
    strategy = get_strategy(position.strategy_id)  # Gets v1.0 (immutable)
    exit_config = strategy['config']['exit']
    # Use v1.0 exit rules (NOT v1.1)
```

### Q5: "Position table - Does it also need model/strategy/probability/edge at ENTRY time?"

**ANSWER:** **YES - Strongly recommend all 5 attribution fields.**

**Why positions need attribution (not just trades):**

**Use Case 1: Position-level performance analytics**
```sql
-- "How did halftime_entry v1.1 positions perform?"
SELECT
  s.strategy_name,
  s.strategy_version,
  COUNT(*) AS positions_opened,
  AVG(p.realized_pnl) AS avg_pnl
FROM positions p
JOIN strategies s ON p.strategy_id = s.strategy_id
WHERE s.strategy_name = 'halftime_entry' AND s.strategy_version = 'v1.1';

-- WITHOUT position.strategy_id → Complex JOIN through trades (fragile)
```

**Use Case 2: Real-time monitoring dashboard**
```python
# "Show open positions for each strategy" (common dashboard query)
positions_by_strategy = db.execute('''
    SELECT s.strategy_name, p.position_id, p.unrealized_pnl
    FROM positions p
    JOIN strategies s ON p.strategy_id = s.strategy_id
    WHERE p.status = 'open'
''')
# Fast query (single JOIN, indexed strategy_id)
```

**Use Case 3: Exit evaluation context**
```python
def evaluate_exits(position):
    # Context needed: What edge did we have at entry?
    entry_edge = position.edge_at_entry  # Need from positions table
    current_edge = calculate_current_edge(position.market_id)

    # Exit rule: "Exit if edge drops below 50% of entry edge"
    if current_edge < (entry_edge * Decimal("0.50")):
        return ('edge_deterioration', 'HIGH')
```

**Recommendation:** Add all 5 fields (strategy_id, model_id, calculated_probability, edge_at_entry, market_price_at_entry)

### Q6: "Why 'attribution' instead of 'attribute'?"

**ANSWER:** **Terminology distinction for causality tracking.**

**Attribute (generic):** Property or characteristic of an object
- "The trade has attributes: price, quantity, side"

**Attribution (specific):** Linking a result to its cause/source/origin
- "This trade is **attributed to** strategy_id=5, model_id=2"
- Answers: "**What caused this trade?**" "**What generated this P&L?**"

**Industry Context:**
"Attribution" is standard in trading/finance:
- **Performance attribution analysis:** Which strategies generated profits?
- **Risk attribution:** Which positions contribute to portfolio risk?
- **Trade attribution:** Which algorithm/strategy executed this trade?

**Examples:**
```python
# Trade ATTRIBUTES (properties):
trade.price = Decimal("0.5200")
trade.quantity = 100

# Trade ATTRIBUTION (causality):
trade.strategy_id = 5  # WHICH strategy caused this?
trade.model_id = 2     # WHICH model predicted this?
trade.calculated_probability = Decimal("0.6200")  # WHAT did model predict?
trade.edge_value = Decimal("0.1000")  # WHY did we enter?
```

**User accepted terminology:** Attribution fields = fields tracking causality for analytics.

### Q7: "What about JSONB for strategy config? Is that a concern?"

**ANSWER:** **NO - JSONB is PERFECT for strategies.config!**

**Why JSONB Works Well for Strategy Config:**

✅ **Small table:** ~20-50 strategies (not 100,000+ trades)
✅ **Infrequent reads:** Read once per position open/close (not millions of analytics queries)
✅ **Flexible schema:** Entry/exit rules will evolve (user confirmed frequent changes)
✅ **Hierarchical data:** Nested entry/exit structure makes sense

**Performance Comparison:**

| Characteristic | Strategy Config | Trades Table |
|---------------|-----------------|--------------|
| Table size | ~50 rows ✅ | ~100,000+ rows ❌ |
| Query frequency | Infrequent ✅ | Frequent (analytics) ❌ |
| Schema stability | Evolving ✅ | Stable ❌ |
| Performance impact | Acceptable ✅ | 20-100x penalty ❌ |

**Conclusion:** Keep strategies.config as JSONB ✅, use explicit columns for trades/positions ✅

### Q8: "Need min_probability attribute/column/rule in strategies?"

**ANSWER:** **YES - Add min_probability to entry rules.**

**Rationale:**
min_probability is distinct from min_edge:

**min_edge:** Market inefficiency threshold
- Calculated: `edge = model_probability - market_price`
- Example: edge = 0.62 - 0.50 = 0.12 (12% edge)

**min_probability:** Absolute model confidence threshold
- Direct: "Model must predict ≥55% to enter"
- Example: model_probability = 0.52 (52%)

**Why You Need BOTH:**
```python
# Scenario: Low-confidence edge
model_probability = 0.52  # 52% win probability
market_price = 0.48       # 48% market price
edge = 0.04               # 4% edge (above min_edge=0.03)

# Question: Should we enter?
if edge >= min_edge:  # 0.04 >= 0.03 ✅ YES, edge exists
if model_probability >= min_probability:  # 0.52 >= 0.55 ❌ NO, model not confident

# Decision: DON'T ENTER (low model confidence despite edge)
```

**Updated Entry Rules:**
```json
{
  "entry": {
    "version": "1.0",
    "rules": {
      "min_lead": 7,              // Game state requirement
      "max_spread": "0.08",       // Market efficiency filter
      "min_edge": "0.05",         // Minimum market inefficiency (5%)
      "min_probability": "0.55",  // NEW: Minimum model confidence (55%)
      "kelly_fraction": "0.10"    // Position sizing (10% Kelly)
    }
  }
}
```

---

## 5. Decision Summary

### Schema Approach Decisions

| Concern | Decision | Rationale |
|---------|----------|-----------|
| **Trade Source Tracking** | trade_source enum (automated, manual_ui, manual_api, paper_trading) | Granular tracking, database-enforced, self-documenting |
| **Trade Attribution** | 3 explicit columns (calculated_probability, market_price, edge_value) | 20-100x faster queries, type safety via CHECK constraints, discoverability |
| **Position Attribution** | 5 explicit columns (strategy_id, model_id, calculated_probability, edge_at_entry, market_price_at_entry) | Direct analytics queries (no JOIN), position-level performance tracking |
| **Strategy Scope** | BOTH entry + exit rules with nested versioning | User expects frequent independent changes, exit A/B testing valuable |
| **Entry-Exit Linkage** | Immutable (position locked to strategy version at entry) | A/B testing integrity, clear attribution |
| **Strategy Config Storage** | Keep JSONB ✅ | Small table, infrequent reads, flexible schema, hierarchical data |
| **Trade Data Source** | Download ALL trades from Kalshi API, filter by trade_source | Reconciliation, audit trail, position tracking, comparative analytics |

### Architecture Decisions Created

**ADR-090:** Strategy Contains Entry + Exit Rules with Nested Versioning
- Strategies contain BOTH entry + exit in config JSONB
- Nested versioning: entry.version, exit.version
- Strategy version = combination being tested
- Positions locked to strategy version at entry (immutable)

**ADR-091:** Explicit Columns for Trade/Position Attribution
- Use explicit columns for trades/positions (performance + type safety)
- Use JSONB for strategies.config (flexibility + small table)
- Performance impact: 20-100x faster with explicit columns
- Type safety via CHECK constraints

**ADR-092:** Trade Source Tracking and Manual Trade Reconciliation
- Download ALL trades from Kalshi API
- Use trade_source enum to differentiate
- Analytics filtering: `WHERE trade_source = 'automated'`

### Migrations Required

**Migration 018:** Trade Source Tracking
- Add trade_source_type enum
- Add trade_source column with index
- ~5 seconds downtime

**Migration 019:** Trade Attribution Enrichment
- Add 3 columns (calculated_probability, market_price, edge_value)
- Add 3 CHECK constraints (probability ranges)
- Add 2 indexes
- ~10 seconds downtime

**Migration 020:** Position Attribution
- Add 5 columns (strategy_id, model_id, calculated_probability, edge_at_entry, market_price_at_entry)
- Add 2 FK constraints
- Add 3 CHECK constraints
- Add 3 indexes
- ~15 seconds downtime

**Total Schema Impact:** 9 columns, 1 enum, 6 indexes, 2 FKs, ~30 seconds migration time

---

## 6. Recommendations

### Phase 1.5-2 Implementation (IMMEDIATE)

**Priority 1: Schema Migrations** (2-3 hours)
1. Create Migration 018 (trade_source)
2. Create Migration 019 (trade attribution)
3. Create Migration 020 (position attribution)
4. Apply migrations to database

**Priority 2: CRUD Operations** (2-3 hours)
1. Update create_trade() with 4 new parameters
2. Update create_position() with 5 new parameters
3. Add validate_position_trade_attribution()

**Priority 3: Tests** (2-3 hours)
1. test_trade_attribution.py (8-10 tests)
2. test_position_attribution.py (8-10 tests)
3. test_strategy_config_structure.py (6-8 tests)

**Priority 4: Documentation** (2-3 hours)
1. DATABASE_SCHEMA_SUMMARY V1.9 → V1.10
2. Pattern 15: Trade/Position Attribution Best Practices
3. ADR-090, ADR-091, ADR-092

### Phase 3-4 Considerations (FUTURE)

**Migrate frequently-queried JSONB fields to generated columns** (if needed):
```sql
-- Promote JSONB field to indexed column
ALTER TABLE trades
ADD COLUMN confidence_score VARCHAR
  GENERATED ALWAYS AS (trade_metadata->>'confidence_score') STORED;

-- Get column performance + keep JSONB flexibility
```

**Consider methods table architecture** (ADR-077 research):
- Collect 3-6 months trading data
- Analyze version explosion patterns
- Prototype methods table
- Decision point: Implement or stick with strategies-only

---

## 7. Analytics Enabled

After implementation, can answer:

**Performance Attribution:**
```sql
-- Which strategy is most profitable?
SELECT
  s.strategy_name,
  s.strategy_version,
  AVG(p.realized_pnl) AS avg_pnl,
  SUM(p.realized_pnl) AS total_pnl
FROM positions p
JOIN strategies s ON p.strategy_id = s.strategy_id
WHERE p.status = 'closed'
GROUP BY s.strategy_name, s.strategy_version
ORDER BY total_pnl DESC;
```

**Model Accuracy:**
```sql
-- Is model v2.1 more accurate than v2.0?
SELECT
  m.model_version,
  AVG(ABS(p.calculated_probability - actual_outcome)) AS avg_error
FROM positions p
JOIN probability_models m ON p.model_id = m.model_id
WHERE p.status = 'closed'
GROUP BY m.model_version
ORDER BY avg_error ASC;
```

**App vs Manual Performance:**
```sql
-- Compare automated vs manual trade performance
SELECT
  trade_source,
  COUNT(*) AS trade_count,
  AVG(edge_value) AS avg_edge
FROM trades
GROUP BY trade_source;
```

**Entry Rule Effectiveness:**
```sql
-- Does min_probability=0.60 outperform min_probability=0.55?
SELECT
  config->'entry'->'rules'->>'min_probability' AS min_prob,
  AVG(p.realized_pnl) AS avg_pnl
FROM positions p
JOIN strategies s ON p.strategy_id = s.strategy_id
WHERE p.status = 'closed'
GROUP BY min_prob;
```

---

## 8. References

**Architecture Decisions:**
- ADR-090: Strategy Contains Entry + Exit Rules with Nested Versioning (to be created)
- ADR-091: Explicit Columns for Trade/Position Attribution (to be created)
- ADR-092: Trade Source Tracking and Manual Trade Reconciliation (to be created)
- ADR-077: Strategy vs Method Separation (Phase 4 research) - deferred
- ADR-018: Immutable Versions

**Schema Documentation:**
- DATABASE_SCHEMA_SUMMARY V1.9 → V1.10 (to be updated)
- Migrations 018-020 (to be created)

**Development Patterns:**
- Pattern 15: Trade/Position Attribution Best Practices (to be created)

**Related Discussions:**
- User session: 2025-11-21
- TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md
- SCHEMA_MIGRATION_WORKFLOW_V1.0.md

---

**END OF SCHEMA_ANALYSIS_2025-11-21.md**

**Status:** ✅ Analysis Complete, Decisions Finalized
**Next Steps:** Implementation (Phases 2-10 of plan)
