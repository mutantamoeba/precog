# ADR-107: Single-Database Architecture with Execution Environments

---
**Version:** 1.0
**Date:** December 20, 2025
**Status:** Accepted
**Phase:** Phase 2 (Database Architecture Enhancement)
**Drivers:** Simplicity, data integrity, model training with production context, unified analytics
**GitHub Issue:** #241
---

## Context

User asked key architectural questions about database separation:
1. "Where do we write live ESPN game state data - train or prod database?"
2. "What about strategy testing with Kalshi demo trades and trained models?"
3. "Did we thoroughly think through this architecture?"

**The Problem:**
Originally considered separate databases (precog_prod, precog_train, precog_dev), but this creates challenges:
- **Data duplication:** Game states needed in both train and prod
- **Cross-environment analysis:** Hard to compare paper vs live performance
- **Complex migrations:** Schema changes require syncing multiple databases
- **Training gaps:** Models trained without production trade context

## Decision

Implement a **single-database architecture** with **execution_environment column** to distinguish data origin:

```sql
-- New ENUM type for execution environment
CREATE TYPE execution_environment AS ENUM ('live', 'paper', 'backtest');

-- Add to trades table (new column)
ALTER TABLE trades ADD COLUMN execution_environment execution_environment NOT NULL DEFAULT 'live';

-- Add to positions table (new column)
ALTER TABLE positions ADD COLUMN execution_environment execution_environment NOT NULL DEFAULT 'live';
```

## Three Environments Explained

| Environment | API Used | Data | Purpose | Real Money? |
|-------------|----------|------|---------|-------------|
| **live** | Kalshi Production API | Real-time markets | Production trading | Yes |
| **paper** | Kalshi Demo/Sandbox API | Real-time markets | Integration testing, latency testing | No |
| **backtest** | None (simulated) | Historical data | Strategy validation, model evaluation | No |

### Key Differences: Paper Trading vs Backtesting

| Aspect | Paper Trading | Backtesting |
|--------|---------------|-------------|
| **Timing** | Real-time execution | As-fast-as-possible simulation |
| **API calls** | Real calls to demo endpoint | No API calls |
| **Slippage** | Real market slippage | Idealized fills |
| **Latency** | Real network latency | Zero latency |
| **Market impact** | Real (on demo) | None |
| **Use case** | Test integration, validate latency | Test strategy on historical data |

## Design

### Two Orthogonal Dimensions

1. **trade_source** (WHO created): `automated`, `manual` (already exists)
2. **execution_environment** (WHERE executed): `live`, `paper`, `backtest` (new)

This allows all combinations:
- Automated + Live = Production bot trading
- Automated + Paper = Testing bot on demo
- Automated + Backtest = Backtesting strategy
- Manual + Live = User placed trade manually
- Manual + Paper = User testing on demo

### Shared Tables

```sql
-- Game states - ALL live ESPN data goes here
-- Used for: Production trading AND model training
game_states (
    -- No environment column needed - game states are game states
    ...
)

-- Market prices - Kalshi live prices
markets (
    -- No environment needed - prices are prices
    ...
)

-- Trades and positions - tagged by environment
trades (
    trade_source trade_source_type DEFAULT 'automated',
    execution_environment execution_environment NOT NULL DEFAULT 'live',
    ...
)

positions (
    execution_environment execution_environment NOT NULL DEFAULT 'live',
    ...
)
```

### Convenience Views

```sql
-- Live trading only
CREATE VIEW live_trades AS
SELECT * FROM trades WHERE execution_environment = 'live';

CREATE VIEW live_positions AS
SELECT * FROM positions WHERE execution_environment = 'live';

-- Paper trading only
CREATE VIEW paper_trades AS
SELECT * FROM trades WHERE execution_environment = 'paper';

-- Backtesting only
CREATE VIEW backtest_trades AS
SELECT * FROM trades WHERE execution_environment = 'backtest';

-- Non-production (for model training)
CREATE VIEW training_data_trades AS
SELECT * FROM trades WHERE execution_environment IN ('paper', 'backtest');
```

## Data Flow

```
Production Trading     Paper Trading        Backtesting
      |                     |                    |
      | env='live'          | env='paper'        | env='backtest'
      v                     v                    v
+------------------------------------------------------------------+
|                    SINGLE DATABASE (precog)                       |
+------------------------------------------------------------------+
|  game_states    - ALL live ESPN data (shared for all uses)       |
|  markets        - ALL Kalshi prices (shared)                     |
|  trades         - Tagged by execution_environment                |
|  positions      - Tagged by execution_environment                |
|  historical_*   - Historical data for backtesting                |
+------------------------------------------------------------------+
      |                     |                    |
      v                     v                    v
  live_trades         paper_trades        backtest_trades
    (view)              (view)               (view)
```

## Model Training Strategy

**Question:** "Does the app write game state data to train database only?"

**Answer:** No. Game states go to a SINGLE database, used by ALL:

1. **Production trading:** Uses live game_states for real-time decisions
2. **Paper trading:** Uses same live game_states (real data, fake trades)
3. **Model training:** Queries historical game_states + historical_* tables
4. **Backtesting:** Uses historical_* tables (historical_games, historical_odds, historical_elo)

**Training Data Sources:**
- `game_states` table - Live in-game data (collected during production)
- `historical_games` table - Years of past game results
- `historical_elo` table - Historical team strength ratings
- `historical_odds` table - Historical betting lines for CLV analysis
- `trades` WHERE execution_environment IN ('paper', 'backtest') - Trade outcomes for feature engineering

## Why Not is_paper Boolean?

Considered `is_paper BOOLEAN` but rejected because:
1. **Three states, not two:** Live, Paper, Backtest are distinct
2. **Semantic clarity:** `execution_environment = 'paper'` is clearer than `is_paper = TRUE`
3. **Extensibility:** Could add 'simulation', 'contest', etc. later
4. **Consistency:** Matches existing ENUM patterns (trade_source, etc.)

## Relationship to trade_source

Keep both columns - they answer different questions:

| Column | Question Answered | Values |
|--------|-------------------|--------|
| `trade_source` | Who/what created this trade? | automated, manual |
| `execution_environment` | Where was it executed? | live, paper, backtest |

## Migration Path

**Migration 0008: Add Execution Environment**
```sql
-- 1. Create ENUM type
CREATE TYPE execution_environment AS ENUM ('live', 'paper', 'backtest');

-- 2. Add column to trades (default to 'live' for existing data)
ALTER TABLE trades
ADD COLUMN execution_environment execution_environment NOT NULL DEFAULT 'live';

-- 3. Add column to positions
ALTER TABLE positions
ADD COLUMN execution_environment execution_environment NOT NULL DEFAULT 'live';

-- 4. Create convenience views
CREATE VIEW live_trades AS SELECT * FROM trades WHERE execution_environment = 'live';
CREATE VIEW paper_trades AS SELECT * FROM trades WHERE execution_environment = 'paper';
CREATE VIEW backtest_trades AS SELECT * FROM trades WHERE execution_environment = 'backtest';

-- 5. Add indexes for common queries
CREATE INDEX idx_trades_environment ON trades(execution_environment);
CREATE INDEX idx_positions_environment ON positions(execution_environment);
```

## Safety Guardrails

1. **Default to live:** Existing code works unchanged
2. **Explicit environment:** New code must specify environment for paper/backtest
3. **Views for isolation:** Use views instead of raw tables for queries
4. **API mode separation:** Kalshi API mode (live/demo) must match execution_environment

## Benefits

1. **Simplicity:** One database to manage, one schema to migrate
2. **Data integrity:** No duplication, single source of truth
3. **Cross-environment analysis:** Compare paper vs live performance easily
4. **Model training:** Access all data (live, paper, backtest) for training
5. **Unified analytics:** Dashboard shows all environments in one place

## Alternatives Rejected

**Alternative 1: Separate Databases (Rejected)**
- **Pro:** Complete isolation
- **Con:** Data duplication, complex migrations, no cross-analysis
- **Why Rejected:** Game states needed in both; migrations nightmare

**Alternative 2: is_paper Boolean (Rejected)**
- **Pro:** Simple
- **Con:** Only two states; what about backtest?
- **Why Rejected:** Three distinct environments exist

**Alternative 3: Environment Tables (Rejected)**
- **Pro:** Complete schema separation
- **Con:** Extreme duplication (live_trades, paper_trades, backtest_trades tables)
- **Why Rejected:** Maintenance nightmare, no polymorphic queries

## Related Artifacts

- **Migration 0008:** Add execution_environment column (planned)
- **ADR-092:** Trade Source Tracking (trade_source column)
- **ADR-105:** Two-Axis Environment Configuration (PRECOG_ENV + API modes)
- **Issue #241:** Cloud Deployment Strategy
- **REQ-DB-017:** Execution Environment Tracking (planned)

---

**END OF ADR-107**
