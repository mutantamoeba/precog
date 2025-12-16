# ADR-201: Position History Tracking Without SCD Type 2

**Status:** ✅ Accepted
**Date:** 2025-11-18
**Context:** Phase 1.5 - Manager Architecture
**Related ADRs:** ADR-018 (Strategy Versioning), ADR-019 (Model Versioning), ADR-002 (Decimal Precision)
**Related REQs:** REQ-POSITION-001 through REQ-POSITION-006

---

## Problem Statement

During Position Manager implementation, we discovered a **fundamental architectural mismatch**:

**Documentation Claims (MANAGER_ARCHITECTURE_GUIDE_V1.0.md):**
- Positions should use SCD Type 2 (Slowly Changing Dimension Type 2) for history tracking
- Rationale: "Positions change every second → need history without version explosion"

**Database Schema Reality:**
- `positions` table has `position_id` as PRIMARY KEY (must be unique)
- **Missing dual-key structure** required for SCD Type 2 (separate PK + business key)
- Attempting SCD Type 2 causes: `duplicate key value violates unique constraint "positions_pkey"`

**Critical User Requirement:**
- Need historical analysis: "Position was up +20% at peak but exited at -5% due to trailing stop"
- Required to refine strategies: "Should we use different trailing stop parameters?"
- Performance reporting: Track position P&L evolution over time

**Decision Required:** How to track position history without SCD Type 2?

---

## Schema Analysis: SCD Type 2 Support Across Tables

### Tables with `row_current_ind` Column (11 total)

**CAN use SCD Type 2 (1 table):**
```
markets:
├─ id (integer) ──────────── PRIMARY KEY (auto-increment, surrogate)
├─ market_id (varchar) ───── BUSINESS KEY (can repeat across versions)
├─ row_current_ind (boolean)  SCD TYPE 2 FLAG
└─ row_end_ts (timestamp) ─── SCD TYPE 2 END TIME

Example SCD Type 2 in markets:
id | market_id     | yes_price | row_current_ind
---|---------------|-----------|----------------
1  | MKT-NFL-123   | 0.5000    | FALSE (old)
2  | MKT-NFL-123   | 0.5200    | FALSE (old)
3  | MKT-NFL-123   | 0.5500    | TRUE  (current) ✅ Works!
```

**CANNOT use SCD Type 2 (10 tables):**
```
positions:
├─ position_id (integer) ──── PRIMARY KEY (auto-increment, business key + PK)
├─ (no separate business key) ⚠️ MISSING DUAL-KEY STRUCTURE
├─ row_current_ind (boolean)  SCD TYPE 2 FLAG (but can't use!)
└─ row_end_ts (timestamp) ─── SCD TYPE 2 END TIME

Attempted SCD Type 2 in positions:
position_id | current_price | row_current_ind
------------|---------------|----------------
123         | 0.5000        | FALSE (old)
123         | 0.5200        | TRUE  (current) ❌ DUPLICATE KEY ERROR!

Error: duplicate key value violates unique constraint "positions_pkey"
```

**Other blocked tables:** `account_balance`, `edges`, `game_states`, `current_balances`, `current_edges`, `current_game_states`, `current_markets`, `open_positions`, `positions_urgent_monitoring`

**Architectural Finding:** Only 1 out of 11 tables with `row_current_ind` can actually use SCD Type 2!

---

## Considered Alternatives

### Alternative 1: Composite Primary Key ❌ REJECTED

**Approach:**
```sql
ALTER TABLE positions DROP CONSTRAINT positions_pkey;
ALTER TABLE positions ADD PRIMARY KEY (position_id, row_current_ind);
```

**Allows:**
```
position_id | row_current_ind | current_price
------------|-----------------|---------------
123         | FALSE           | 0.5000 ✅ OK
123         | FALSE           | 0.5100 ✅ OK (multiple FALSE rows)
123         | FALSE           | 0.5200 ✅ OK
123         | TRUE            | 0.5500 ✅ OK (only one TRUE row)
```

**Rejected Because:**
1. **Awkward invariant**: Unlimited `(position_id, FALSE)` rows, but only ONE `(position_id, TRUE)` row
2. **Foreign key complexity**: Other tables reference `position_id` → would need to also track `row_current_ind`
3. **Query complexity**: Every query needs `WHERE position_id = X AND row_current_ind = TRUE`
4. **Migration risk**: Changing PK on production table with existing data
5. **Over-engineering**: Simpler solutions exist (see Alternative 3)

### Alternative 2: Add Surrogate Primary Key ⏸️ DEFERRED

**Approach:**
```sql
-- Add new id column as PK (like markets table)
ALTER TABLE positions ADD COLUMN id SERIAL;
ALTER TABLE positions DROP CONSTRAINT positions_pkey;
ALTER TABLE positions ADD PRIMARY KEY (id);

-- position_id becomes business key (non-unique)
CREATE INDEX idx_positions_position_id ON positions(position_id);
```

**This WOULD enable SCD Type 2:**
```
id | position_id | current_price | row_current_ind
---|-------------|---------------|----------------
1  | 123         | 0.5000        | FALSE (old)
2  | 123         | 0.5200        | FALSE (old)
3  | 123         | 0.5500        | TRUE  (current) ✅ Works!
```

**Deferred to Phase 2+ Because:**
1. **Trades table already provides audit trail** (simpler solution exists)
2. **Schema migration on production** (risky, requires careful planning)
3. **Version explosion still a concern**: 100 positions × 1000 updates/day = 100,000 rows/day
4. **Intermediate price updates not needed**: Only entry/exit prices matter for P&L analysis

**When to reconsider:**
- Phase 5: If real-time monitoring reveals need for granular price history
- Performance analysis: If trades table proves insufficient for strategy refinement
- Regulatory compliance: If audit requirements demand sub-second position history

### Alternative 3: Trades Table + Position State Snapshots ✅ ACCEPTED

**Approach:** Three-tier history tracking system

**Tier 1: Trades Table (Entry/Exit Prices)**
```sql
SELECT
    t.trade_id,
    t.position_id,
    t.action,        -- 'entry' or 'exit'
    t.price,
    t.quantity,
    t.fees,
    t.timestamp,
    t.metadata       -- JSON: {"exit_reason": "trailing_stop", "peak_price": "0.75", ...}
FROM trades t
WHERE t.position_id = 123
ORDER BY t.timestamp;

-- Example result:
-- trade_id | position_id | action | price  | timestamp           | metadata
-- ---------|-------------|--------|--------|---------------------|----------
-- 1001     | 123         | entry  | 0.5500 | 2024-01-15 10:00:00 | {...}
-- 1002     | 123         | exit   | 0.5800 | 2024-01-15 14:30:00 | {"exit_reason": "trailing_stop", ...}
```

**Tier 2: Position State Snapshots (Periodic Sampling)**
```sql
-- New table: position_snapshots
CREATE TABLE position_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    position_id INTEGER NOT NULL REFERENCES positions(position_id),
    snapshot_time TIMESTAMP NOT NULL,
    current_price DECIMAL(10,4) NOT NULL,
    unrealized_pnl DECIMAL(10,4) NOT NULL,
    unrealized_pnl_pct DECIMAL(6,4) NOT NULL,
    trailing_stop_state JSONB,
    -- Snapshot reason
    trigger_reason VARCHAR(50), -- 'periodic', 'peak', 'significant_change', 'exit_evaluation'

    CONSTRAINT unique_position_snapshot UNIQUE(position_id, snapshot_time)
);

-- Create index for fast position lookups
CREATE INDEX idx_position_snapshots_position_id ON position_snapshots(position_id, snapshot_time DESC);

-- Example: Track position evolution every 5 minutes OR on significant events
INSERT INTO position_snapshots (
    position_id, snapshot_time, current_price,
    unrealized_pnl, unrealized_pnl_pct, trailing_stop_state, trigger_reason
)
VALUES
    (123, '2024-01-15 10:00:00', 0.5500, 0, 0, '{"active": false}', 'entry'),
    (123, '2024-01-15 10:05:00', 0.6200, 7.00, 0.1273, '{"active": true, "peak_price": "0.6200"}', 'periodic'),
    (123, '2024-01-15 10:15:00', 0.7500, 20.00, 0.3636, '{"active": true, "peak_price": "0.7500"}', 'peak'), -- New peak!
    (123, '2024-01-15 10:20:00', 0.6800, 13.00, 0.2364, '{"active": true, "peak_price": "0.7500"}', 'periodic'),
    (123, '2024-01-15 10:30:00', 0.5800, 3.00, 0.0545, '{"active": true, "peak_price": "0.7500"}', 'exit_evaluation'); -- Trailing stop triggered
```

**Tier 3: Positions Table (Current State Only)**
```sql
-- Simple UPDATE pattern (no SCD Type 2)
UPDATE positions
SET
    current_price = 0.5800,
    unrealized_pnl = 3.00,
    unrealized_pnl_pct = 0.0545,
    last_update = '2024-01-15 10:30:00'
WHERE position_id = 123 AND row_current_ind = TRUE;
```

**Snapshot Triggering Logic (Phase 5 Implementation):**
```python
def should_create_snapshot(position: Position, new_price: Decimal) -> bool:
    """Determine if we should create a snapshot."""
    # Always snapshot on entry/exit
    if position.status in ('new', 'closing'):
        return True

    # Snapshot on new peak (for trailing stop analysis)
    if new_price > position.trailing_stop_state.get('peak_price', Decimal('0')):
        return True

    # Snapshot on significant price change (>5%)
    if abs(new_price - position.current_price) / position.current_price > Decimal('0.05'):
        return True

    # Periodic snapshot (every 5 minutes)
    time_since_last = datetime.utcnow() - position.last_snapshot_time
    if time_since_last > timedelta(minutes=5):
        return True

    return False
```

---

## Decision: Three-Tier History System

**Accepted:** Alternative 3 (Trades + Snapshots + Current State)

### Tier 1: Trades Table (Complete Audit Trail)
- **Purpose:** Regulatory compliance, audit trail, P&L calculation
- **Granularity:** Entry and exit only
- **Retention:** Permanent (never delete)
- **Storage Cost:** Low (2 rows per position lifecycle)

### Tier 2: Position Snapshots (Performance Analysis)
- **Purpose:** Strategy refinement, trailing stop analysis, performance debugging
- **Granularity:** Configurable (periodic + event-driven)
- **Retention:** Configurable (default: 90 days, then aggregate)
- **Storage Cost:** Medium (5-20 rows per position depending on duration)

### Tier 3: Positions Table (Current State)
- **Purpose:** Real-time monitoring, exit decision making
- **Granularity:** Live (updated every second in Phase 5)
- **Retention:** Until position closes
- **Storage Cost:** Low (1 row per open position)

---

## Rationale

### Why This Solution Addresses All Requirements

**1. Historical Analysis (User Requirement):**
```sql
-- "Position was up +20% at peak but exited at -5% - why?"
SELECT
    ps.snapshot_time,
    ps.current_price,
    ps.unrealized_pnl_pct,
    ps.trailing_stop_state->>'peak_price' as peak_price,
    ps.trigger_reason
FROM position_snapshots ps
WHERE ps.position_id = 123
ORDER BY ps.snapshot_time;

-- Result:
-- snapshot_time       | current_price | unrealized_pnl_pct | peak_price | trigger_reason
-- --------------------|---------------|--------------------|-----------|-----------------
-- 2024-01-15 10:00:00 | 0.5500        | 0.0000             | null      | entry
-- 2024-01-15 10:15:00 | 0.7500        | 0.3636             | 0.7500    | peak (📈 +36% gain!)
-- 2024-01-15 10:30:00 | 0.5800        | 0.0545             | 0.7500    | exit_evaluation
-- 2024-01-15 10:30:00 | 0.5800        | 0.0545             | 0.7500    | exit

-- Analysis: Position peaked at +36%, then trailing stop triggered at +5.45%
-- Action: Consider tighter trailing stop to lock in more gains
```

**2. Strategy Refinement:**
```sql
-- Compare trailing stop configurations across positions
SELECT
    p.strategy_id,
    AVG(ps_peak.unrealized_pnl_pct) as avg_peak_gain,
    AVG(t_exit.price - t_entry.price) / AVG(t_entry.price) as avg_realized_gain,
    AVG(ps_peak.unrealized_pnl_pct) - AVG(t_exit.price - t_entry.price) / AVG(t_entry.price) as avg_slippage
FROM positions p
JOIN position_snapshots ps_peak ON ps_peak.position_id = p.position_id AND ps_peak.trigger_reason = 'peak'
JOIN trades t_entry ON t_entry.position_id = p.position_id AND t_entry.action = 'entry'
JOIN trades t_exit ON t_exit.position_id = p.position_id AND t_exit.action = 'exit'
WHERE p.status = 'closed'
GROUP BY p.strategy_id;

-- Result shows: Strategy A has 15% slippage (peak - realized) → trailing stop too loose!
```

**3. Performance vs. Storage:**
```
SCD Type 2 (Alternative 2):
- 100 positions × 1000 updates/day × 90 days = 9,000,000 rows
- Storage: ~900 MB (assuming 100 bytes/row)

Snapshot System (Alternative 3):
- 100 positions × 20 snapshots/position × 90 days = 180,000 rows
- Storage: ~18 MB (assuming 100 bytes/row)
- 50x less storage than SCD Type 2! 📉
```

**4. Query Performance:**
```sql
-- SCD Type 2: Get position state at specific time
SELECT *
FROM positions
WHERE position_id = 123
  AND row_current_ind = TRUE
  AND created_at <= '2024-01-15 10:15:00'
  AND (row_end_ts IS NULL OR row_end_ts > '2024-01-15 10:15:00')
ORDER BY created_at DESC LIMIT 1;

-- Snapshot System: Get position state at specific time
SELECT *
FROM position_snapshots
WHERE position_id = 123
  AND snapshot_time <= '2024-01-15 10:15:00'
ORDER BY snapshot_time DESC LIMIT 1;

-- Both O(log n) with index, but snapshot table 50x smaller → faster!
```

---

## Implementation Plan

### Phase 1.5 (Current): Defer Position Manager
- ✅ Document architectural decision (this ADR)
- ✅ Push and merge Strategy Manager PR
- ⏸️ Defer Position Manager to next session

### Phase 2: Implement Position Manager with Simple UPDATE
- Create `PositionManager` class
- Use simple UPDATE pattern (no SCD Type 2)
- Integrate with trades table for entry/exit tracking

### Phase 5: Add Snapshot System
- Create `position_snapshots` table
- Implement snapshot triggering logic
- Add snapshot creation to position monitoring loop
- Create performance analysis queries

### Phase 5+: Snapshot Retention Policy
- Keep raw snapshots for 90 days
- Aggregate to hourly averages after 90 days
- Keep aggregated data for 1 year
- Archive to cold storage after 1 year

---

## Consequences

### Positive
✅ **No schema migration**: Works with current positions table structure
✅ **Trades table provides audit trail**: Entry/exit prices preserved
✅ **Snapshot system enables analysis**: Track position evolution for strategy refinement
✅ **50x less storage**: Compared to SCD Type 2 with every price update
✅ **Configurable granularity**: Adjust snapshot frequency based on needs
✅ **Simple queries**: No complex SCD Type 2 temporal queries
✅ **Better performance**: Smaller snapshot table → faster queries

### Negative
⚠️ **Two tables to maintain**: `trades` + `position_snapshots` (vs. one SCD Type 2 table)
⚠️ **Snapshot logic complexity**: Need to determine when to create snapshots
⚠️ **Not real-time history**: Snapshots are periodic (5-minute intervals)
⚠️ **Snapshot storage overhead**: Additional 18 MB per 90 days

### Neutral
🔵 **Deferred implementation**: Snapshot system in Phase 5 (not blocking Phase 1.5)
🔵 **Can add SCD Type 2 later**: If schema refactored with surrogate PK (Alternative 2)

---

## Validation

### Test Coverage Requirements

**1. Position Manager (Phase 2):**
- ✅ Create position (inserts into `positions` table)
- ✅ Update position price (simple UPDATE, no SCD Type 2)
- ✅ Close position (UPDATE status to 'closed')
- ✅ Verify trades table updated on entry/exit

**2. Snapshot System (Phase 5):**
- ✅ Create snapshot on entry
- ✅ Create snapshot on peak price
- ✅ Create snapshot on significant price change (>5%)
- ✅ Create snapshot on periodic interval (5 minutes)
- ✅ Query position history from snapshots
- ✅ Calculate average slippage (peak - realized)

**3. Historical Analysis Queries (Phase 5):**
- ✅ Get position state at specific timestamp
- ✅ Track P&L evolution over time
- ✅ Compare peak gains vs. realized gains
- ✅ Identify best/worst performing positions

---

## References

- **Schema**: `docs/database/DATABASE_SCHEMA_SUMMARY_V1.13.md` (positions table)
- **Manager Architecture**: `docs/guides/MANAGER_ARCHITECTURE_GUIDE_V1.0.md` (Section 3)
- **Trades Table**: `docs/database/DATABASE_SCHEMA_SUMMARY_V1.13.md` (lines 800-900)
- **SCD Type 2 Pattern**: Kimball Group, "The Data Warehouse Toolkit" (Chapter 5)
- **Related ADRs**:
  - ADR-018 (Strategy Versioning - immutable configs)
  - ADR-019 (Model Versioning - immutable versions)
  - ADR-002 (Decimal Precision - all prices use Decimal)

---

**Approved By:** Claude Code AI Assistant
**Implementation Priority:** Phase 2 (Position Manager), Phase 5 (Snapshot System)
**Review Date:** 2025-12-01 (reassess after Phase 2 completion)
