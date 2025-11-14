# Performance Tracking Implementation Guide

---
**Version:** 1.0
**Created:** 2025-11-10
**Last Updated:** 2025-11-10
**Status:** ✅ Current
**Phase:** Phases 1.5-2 (Foundation), Phase 6 (Full Implementation)
**Related ADRs:** ADR-079 (Performance Tracking Architecture)
**Related Requirements:** REQ-ANALYTICS-003 (8-Level Time-Series Aggregation)
**Related Docs:** ANALYTICS_ARCHITECTURE_GUIDE_V1.0.md, DATABASE_SCHEMA_SUMMARY_V1.8.md
**Target Audience:** Backend developers implementing performance analytics
**Changes in v1.0:**
- Initial creation with 8-level aggregation architecture
- Database schema for performance_tracking table
- SQL implementation for all aggregation levels
- Incremental update strategy
- Dashboard integration patterns
---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Principles](#architecture-principles)
3. [Database Schema](#database-schema)
4. [8-Level Aggregation Strategy](#8-level-aggregation-strategy)
5. [Implementation: Trade-Level Tracking](#implementation-trade-level-tracking)
6. [Implementation: Hourly Aggregation](#implementation-hourly-aggregation)
7. [Implementation: Daily Aggregation](#implementation-daily-aggregation)
8. [Implementation: Weekly/Monthly/Quarterly/Yearly](#implementation-weeklymonthlyquarterlyyearly)
9. [Implementation: All-Time Aggregation](#implementation-all-time-aggregation)
10. [Incremental Update Strategy](#incremental-update-strategy)
11. [Querying Performance Data](#querying-performance-data)
12. [Dashboard Integration](#dashboard-integration)
13. [Maintenance and Monitoring](#maintenance-and-monitoring)
14. [Common Patterns and Examples](#common-patterns-and-examples)
15. [Troubleshooting](#troubleshooting)

---

## Overview

### What is Performance Tracking?

Performance tracking captures **comprehensive P&L metrics** at multiple time granularities to enable:
- **Real-time dashboards**: Display current performance without expensive aggregations
- **Historical analysis**: Compare performance across different time periods
- **Model evaluation**: Track model accuracy and edge capture over time
- **Strategy comparison**: A/B test different trading strategies

### Why 8 Levels?

**Problem:** On-demand aggregation of 100,000+ trades is too slow for dashboards (5-10 seconds per query).

**Solution:** Pre-compute aggregations at 8 time granularities:
1. **trade** - Individual trade P&L (base level)
2. **hourly** - Hourly aggregated metrics
3. **daily** - Daily rollup
4. **weekly** - Weekly rollup
5. **monthly** - Monthly rollup
6. **quarterly** - Quarterly rollup
7. **yearly** - Yearly rollup
8. **all_time** - Lifetime totals

**Performance:** 158x-683x speedup on dashboard queries (ADR-083).

### Key Concepts

- **Incremental Aggregation**: Trade-level inserts trigger cascading updates (hourly → daily → ... → all_time)
- **Partition Keys**: `{strategy_id, model_id, league, market_type}` for granular analysis
- **DECIMAL Precision**: All P&L values use `DECIMAL(12,4)` (never float!)
- **Idempotency**: Aggregation functions are idempotent (safe to re-run)

---

## Architecture Principles

### Design Decisions (from ADR-079)

1. **8-Level Hierarchy**: Trade → Hourly → Daily → Weekly → Monthly → Quarterly → Yearly → All-Time
2. **Partition by Strategy + Model**: Enables A/B testing and model comparison
3. **Pre-Computed Aggregations**: Trade storage (9x) for query speed (158x-683x)
4. **Incremental Updates**: Avoid full table scans with targeted incremental logic
5. **PostgreSQL Native**: Use window functions, CTEs, and UPSERT for efficiency

### Storage Trade-offs

| Level | Rows (100k trades) | Storage Overhead | Query Speedup |
|-------|-------------------|------------------|---------------|
| trade | 100,000 | Baseline (1x) | Baseline (1x) |
| hourly | ~4,000 | +4% | 25x faster |
| daily | ~180 | +0.2% | 555x faster |
| weekly | ~26 | +0.03% | 3,846x faster |
| monthly | ~6 | +0.006% | 16,667x faster |
| quarterly | ~2 | +0.002% | 50,000x faster |
| yearly | ~1 | +0.001% | 100,000x faster |
| all_time | ~1 | +0.001% | 100,000x faster |
| **TOTAL** | ~104,216 | **+4.2%** | **158x-683x** |

**Conclusion:** 4.2% storage overhead for 158x-683x query speedup is excellent trade-off.

---

## Database Schema

### performance_tracking Table

```sql
CREATE TABLE performance_tracking (
    tracking_id SERIAL PRIMARY KEY,

    -- Partition keys (enable granular analysis)
    strategy_id INTEGER NOT NULL,
    model_id INTEGER NOT NULL,
    league VARCHAR(50) NOT NULL,        -- 'nfl', 'ncaaf', 'nba', etc.
    market_type VARCHAR(50) NOT NULL,   -- 'game_winner', 'spread', 'total', etc.

    -- Time dimensions
    aggregation_level VARCHAR(20) NOT NULL,  -- 'trade', 'hourly', 'daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'all_time'
    period_start TIMESTAMP NOT NULL,         -- Start of aggregation period
    period_end TIMESTAMP NOT NULL,           -- End of aggregation period (inclusive)

    -- Trade counts
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,

    -- P&L metrics (DECIMAL precision!)
    gross_pnl DECIMAL(12,4) NOT NULL DEFAULT 0,        -- Before fees
    net_pnl DECIMAL(12,4) NOT NULL DEFAULT 0,          -- After fees
    total_fees DECIMAL(12,4) NOT NULL DEFAULT 0,
    average_pnl_per_trade DECIMAL(12,4),               -- net_pnl / total_trades

    -- Win rate metrics
    win_rate DECIMAL(5,4),                             -- winning_trades / total_trades
    avg_win DECIMAL(12,4),                             -- Average P&L of winning trades
    avg_loss DECIMAL(12,4),                            -- Average P&L of losing trades (negative)
    profit_factor DECIMAL(8,4),                        -- abs(total_wins / total_losses)

    -- Edge and model accuracy
    total_edge DECIMAL(12,4),                          -- Sum of edge% across all trades
    average_edge DECIMAL(6,4),                         -- total_edge / total_trades
    model_accuracy DECIMAL(5,4),                       -- Percent of predictions correct
    calibration_error DECIMAL(5,4),                    -- Brier score or ECE (from model_evaluation)

    -- Risk metrics
    max_drawdown DECIMAL(12,4),                        -- Largest peak-to-trough decline
    sharpe_ratio DECIMAL(8,4),                         -- (avg_return - risk_free_rate) / std_dev

    -- Metadata
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id),
    FOREIGN KEY (model_id) REFERENCES probability_models(model_id),
    CHECK (aggregation_level IN ('trade', 'hourly', 'daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'all_time')),
    CHECK (period_end >= period_start),
    CHECK (total_trades >= 0),
    CHECK (winning_trades + losing_trades <= total_trades),

    -- Unique constraint for idempotent updates
    UNIQUE (strategy_id, model_id, league, market_type, aggregation_level, period_start)
);

-- Indexes for fast queries
CREATE INDEX idx_perf_tracking_lookup ON performance_tracking(
    strategy_id, model_id, league, market_type, aggregation_level, period_start
);

CREATE INDEX idx_perf_tracking_time ON performance_tracking(aggregation_level, period_start);
CREATE INDEX idx_perf_tracking_strategy ON performance_tracking(strategy_id, aggregation_level);
CREATE INDEX idx_perf_tracking_model ON performance_tracking(model_id, aggregation_level);
```

### Why This Schema?

**Partition Keys (`strategy_id`, `model_id`, `league`, `market_type`):**
- Enable A/B testing (compare strategy v1.0 vs v1.1)
- Enable model comparison (Model A vs Model B accuracy)
- Enable market-specific analysis (NFL vs NCAAF performance)

**Aggregation Levels:**
- Single table for all 8 levels (simpler than 8 separate tables)
- `aggregation_level` field discriminates trade vs hourly vs daily, etc.

**DECIMAL Precision:**
- All P&L fields use `DECIMAL(12,4)` for exact sub-penny arithmetic
- **NEVER use float** - causes rounding errors (see Pattern 1 in CLAUDE.md)

**Idempotency:**
- `UNIQUE (strategy_id, model_id, league, market_type, aggregation_level, period_start)` ensures UPSERT safety
- Safe to re-run aggregation logic without duplicates

---

## 8-Level Aggregation Strategy

### Level 1: Trade (Base Level)

**Purpose:** Capture individual trade P&L as they occur.

**Trigger:** INSERT on `trades` table (after trade executed and settled).

**Data Source:** Join `trades` + `positions` + `markets` for complete context.

**Implementation:** See [Implementation: Trade-Level Tracking](#implementation-trade-level-tracking)

### Level 2: Hourly Aggregation

**Purpose:** Aggregate all trades within same hour.

**Trigger:** Hourly cron job OR real-time on trade insert (if low volume).

**Partition:** `{strategy_id, model_id, league, market_type, hour}`

**Implementation:** See [Implementation: Hourly Aggregation](#implementation-hourly-aggregation)

### Level 3: Daily Aggregation

**Purpose:** Daily rollup of hourly data.

**Trigger:** Daily cron job (runs at end of day, e.g., 11:59 PM).

**Partition:** `{strategy_id, model_id, league, market_type, day}`

**Implementation:** See [Implementation: Daily Aggregation](#implementation-daily-aggregation)

### Levels 4-7: Weekly, Monthly, Quarterly, Yearly

**Purpose:** Higher-level rollups for long-term trend analysis.

**Trigger:** Weekly (Sunday 11:59 PM), Monthly (end of month), Quarterly (end of quarter), Yearly (Dec 31).

**Implementation:** Similar to daily aggregation, but with different date truncation.

**See:** [Implementation: Weekly/Monthly/Quarterly/Yearly](#implementation-weeklymonthlyquarterlyyearly)

### Level 8: All-Time Aggregation

**Purpose:** Lifetime totals across all time periods.

**Trigger:** Updated on every trade insert OR hourly cron job.

**Partition:** `{strategy_id, model_id, league, market_type}` (no time dimension)

**Implementation:** See [Implementation: All-Time Aggregation](#implementation-all-time-aggregation)

---

## Implementation: Trade-Level Tracking

### When to Insert Trade-Level Records

Trade-level records are inserted **when a position is closed** (exit executed and settlement confirmed).

**Trigger:** After `positions.status` changes to `'exited'` and settlement P&L is calculated.

### SQL: Insert Trade-Level Performance Record

```sql
-- Insert trade-level performance record
-- Called by application after position exit and settlement

INSERT INTO performance_tracking (
    strategy_id,
    model_id,
    league,
    market_type,
    aggregation_level,
    period_start,
    period_end,
    total_trades,
    winning_trades,
    losing_trades,
    gross_pnl,
    net_pnl,
    total_fees,
    average_pnl_per_trade,
    win_rate,
    avg_win,
    avg_loss,
    total_edge,
    average_edge,
    last_updated
)
SELECT
    t.strategy_id,
    t.model_id,
    m.league,
    m.market_type,
    'trade' AS aggregation_level,
    t.exit_timestamp AS period_start,      -- Trade timestamp
    t.exit_timestamp AS period_end,        -- Same as start for individual trades
    1 AS total_trades,
    CASE WHEN p.realized_pnl > 0 THEN 1 ELSE 0 END AS winning_trades,
    CASE WHEN p.realized_pnl <= 0 THEN 1 ELSE 0 END AS losing_trades,
    p.realized_pnl AS gross_pnl,           -- Before fees
    (p.realized_pnl - p.total_fees) AS net_pnl,  -- After fees
    p.total_fees,
    (p.realized_pnl - p.total_fees) AS average_pnl_per_trade,  -- Same as net_pnl for single trade
    CASE WHEN p.realized_pnl > 0 THEN 1.0 ELSE 0.0 END AS win_rate,
    CASE WHEN p.realized_pnl > 0 THEN p.realized_pnl ELSE NULL END AS avg_win,
    CASE WHEN p.realized_pnl <= 0 THEN p.realized_pnl ELSE NULL END AS avg_loss,
    e.edge AS total_edge,                  -- Edge for this trade
    e.edge AS average_edge,                -- Same as total_edge for single trade
    CURRENT_TIMESTAMP AS last_updated
FROM
    trades t
    INNER JOIN positions p ON t.position_id = p.position_id
    INNER JOIN markets m ON p.market_id = m.market_id
    INNER JOIN edges e ON p.market_id = e.market_id AND e.row_current_ind = TRUE
WHERE
    t.trade_id = :trade_id  -- Parameterized (application passes trade_id after exit)
ON CONFLICT (strategy_id, model_id, league, market_type, aggregation_level, period_start)
DO UPDATE SET
    -- Should not happen for trade-level (each trade is unique timestamp), but handle idempotently
    total_trades = performance_tracking.total_trades + EXCLUDED.total_trades,
    winning_trades = performance_tracking.winning_trades + EXCLUDED.winning_trades,
    losing_trades = performance_tracking.losing_trades + EXCLUDED.losing_trades,
    gross_pnl = performance_tracking.gross_pnl + EXCLUDED.gross_pnl,
    net_pnl = performance_tracking.net_pnl + EXCLUDED.net_pnl,
    total_fees = performance_tracking.total_fees + EXCLUDED.total_fees,
    total_edge = performance_tracking.total_edge + EXCLUDED.total_edge,
    last_updated = CURRENT_TIMESTAMP;
```

### Python Application Code

```python
from decimal import Decimal
from sqlalchemy import text

def record_trade_performance(session, trade_id: int) -> None:
    """
    Record trade-level performance metrics after position exit.

    Args:
        session: SQLAlchemy session
        trade_id: ID of completed trade

    Educational Note:
        This function inserts a trade-level performance record immediately
        after a position is closed. This serves as the base layer for all
        higher-level aggregations (hourly, daily, etc.).

        Why immediate insertion:
        - Enables real-time dashboard updates
        - Provides audit trail for every trade
        - Base data for cascading aggregations

    Example:
        >>> # After exiting a position
        >>> trade = session.query(Trade).filter_by(trade_id=42).first()
        >>> record_trade_performance(session, trade.trade_id)
        >>> session.commit()

    Related:
        - ADR-079: Performance Tracking Architecture
        - REQ-ANALYTICS-003: 8-Level Time-Series Aggregation
    """
    sql = text("""
        -- [SQL from above]
    """)

    session.execute(sql, {"trade_id": trade_id})
    # Commit handled by caller
```

---

## Implementation: Hourly Aggregation

### Purpose

Aggregate all trade-level performance records within the same hour, grouped by `{strategy_id, model_id, league, market_type}`.

### Trigger

**Option A (Real-time):** Trigger on INSERT to `performance_tracking` at trade level (low volume systems).
**Option B (Batch):** Hourly cron job at HH:00 (recommended for high volume).

### SQL: Hourly Aggregation

```sql
-- Aggregate trade-level data into hourly records
-- Run hourly via cron OR trigger on trade insert

INSERT INTO performance_tracking (
    strategy_id,
    model_id,
    league,
    market_type,
    aggregation_level,
    period_start,
    period_end,
    total_trades,
    winning_trades,
    losing_trades,
    gross_pnl,
    net_pnl,
    total_fees,
    average_pnl_per_trade,
    win_rate,
    avg_win,
    avg_loss,
    profit_factor,
    total_edge,
    average_edge,
    last_updated
)
SELECT
    strategy_id,
    model_id,
    league,
    market_type,
    'hourly' AS aggregation_level,
    DATE_TRUNC('hour', period_start) AS period_start,  -- Truncate to hour boundary
    DATE_TRUNC('hour', period_start) + INTERVAL '1 hour' - INTERVAL '1 second' AS period_end,  -- End of hour
    SUM(total_trades) AS total_trades,
    SUM(winning_trades) AS winning_trades,
    SUM(losing_trades) AS losing_trades,
    SUM(gross_pnl) AS gross_pnl,
    SUM(net_pnl) AS net_pnl,
    SUM(total_fees) AS total_fees,
    CASE WHEN SUM(total_trades) > 0 THEN SUM(net_pnl) / SUM(total_trades) ELSE NULL END AS average_pnl_per_trade,
    CASE WHEN SUM(total_trades) > 0 THEN SUM(winning_trades)::DECIMAL / SUM(total_trades) ELSE NULL END AS win_rate,
    CASE WHEN SUM(winning_trades) > 0 THEN SUM(CASE WHEN winning_trades > 0 THEN gross_pnl ELSE 0 END) / SUM(winning_trades) ELSE NULL END AS avg_win,
    CASE WHEN SUM(losing_trades) > 0 THEN SUM(CASE WHEN losing_trades > 0 THEN gross_pnl ELSE 0 END) / SUM(losing_trades) ELSE NULL END AS avg_loss,
    CASE
        WHEN SUM(CASE WHEN gross_pnl < 0 THEN gross_pnl ELSE 0 END) <> 0
        THEN ABS(SUM(CASE WHEN gross_pnl > 0 THEN gross_pnl ELSE 0 END) / SUM(CASE WHEN gross_pnl < 0 THEN gross_pnl ELSE 0 END))
        ELSE NULL
    END AS profit_factor,
    SUM(total_edge) AS total_edge,
    CASE WHEN SUM(total_trades) > 0 THEN SUM(total_edge) / SUM(total_trades) ELSE NULL END AS average_edge,
    CURRENT_TIMESTAMP AS last_updated
FROM
    performance_tracking
WHERE
    aggregation_level = 'trade'
    AND period_start >= :start_hour  -- Parameterized (e.g., '2025-11-10 14:00:00')
    AND period_start < :end_hour     -- Parameterized (e.g., '2025-11-10 15:00:00')
GROUP BY
    strategy_id, model_id, league, market_type, DATE_TRUNC('hour', period_start)
ON CONFLICT (strategy_id, model_id, league, market_type, aggregation_level, period_start)
DO UPDATE SET
    total_trades = EXCLUDED.total_trades,
    winning_trades = EXCLUDED.winning_trades,
    losing_trades = EXCLUDED.losing_trades,
    gross_pnl = EXCLUDED.gross_pnl,
    net_pnl = EXCLUDED.net_pnl,
    total_fees = EXCLUDED.total_fees,
    average_pnl_per_trade = EXCLUDED.average_pnl_per_trade,
    win_rate = EXCLUDED.win_rate,
    avg_win = EXCLUDED.avg_win,
    avg_loss = EXCLUDED.avg_loss,
    profit_factor = EXCLUDED.profit_factor,
    total_edge = EXCLUDED.total_edge,
    average_edge = EXCLUDED.average_edge,
    last_updated = CURRENT_TIMESTAMP;
```

### Python Cron Job (Hourly)

```python
from datetime import datetime, timedelta
from sqlalchemy import text

def aggregate_hourly_performance(session) -> None:
    """
    Aggregate trade-level performance into hourly records.

    Run via cron every hour at HH:00.

    Educational Note:
        This function is the FIRST level of aggregation above trade-level.
        It groups all trades within the same hour and computes aggregate metrics
        (total P&L, win rate, average edge, etc.).

        Why hourly granularity:
        - Fine enough for intraday analysis
        - Coarse enough to reduce storage (25x fewer records than trade-level)
        - Matches typical trading session granularity

        Idempotency:
        - ON CONFLICT DO UPDATE ensures safe re-runs
        - If cron fails, can safely backfill by re-running for past hours

    Example:
        >>> # Cron job runs at 15:00
        >>> aggregate_hourly_performance(session)
        >>> # Aggregates all trades from 14:00:00 to 14:59:59
        >>> session.commit()

    Related:
        - ADR-079: 8-Level Aggregation Strategy
        - PERFORMANCE_TRACKING_GUIDE: Incremental Update Strategy
    """
    # Aggregate for the previous hour
    now = datetime.now()
    start_hour = (now - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    end_hour = start_hour + timedelta(hours=1)

    sql = text("""
        -- [SQL from above]
    """)

    session.execute(sql, {
        "start_hour": start_hour,
        "end_hour": end_hour
    })

    print(f"[INFO] Aggregated hourly performance for {start_hour.strftime('%Y-%m-%d %H:00')}")
```

---

## Implementation: Daily Aggregation

### Purpose

Aggregate hourly performance into daily records (one record per day per partition).

### Trigger

Daily cron job at 11:59 PM (or 00:01 AM for previous day).

### SQL: Daily Aggregation

```sql
-- Aggregate hourly data into daily records
-- Run daily via cron at end of day

INSERT INTO performance_tracking (
    strategy_id,
    model_id,
    league,
    market_type,
    aggregation_level,
    period_start,
    period_end,
    total_trades,
    winning_trades,
    losing_trades,
    gross_pnl,
    net_pnl,
    total_fees,
    average_pnl_per_trade,
    win_rate,
    avg_win,
    avg_loss,
    profit_factor,
    total_edge,
    average_edge,
    max_drawdown,
    sharpe_ratio,
    last_updated
)
SELECT
    strategy_id,
    model_id,
    league,
    market_type,
    'daily' AS aggregation_level,
    DATE_TRUNC('day', period_start) AS period_start,  -- Start of day
    DATE_TRUNC('day', period_start) + INTERVAL '1 day' - INTERVAL '1 second' AS period_end,  -- End of day
    SUM(total_trades) AS total_trades,
    SUM(winning_trades) AS winning_trades,
    SUM(losing_trades) AS losing_trades,
    SUM(gross_pnl) AS gross_pnl,
    SUM(net_pnl) AS net_pnl,
    SUM(total_fees) AS total_fees,
    CASE WHEN SUM(total_trades) > 0 THEN SUM(net_pnl) / SUM(total_trades) ELSE NULL END AS average_pnl_per_trade,
    CASE WHEN SUM(total_trades) > 0 THEN SUM(winning_trades)::DECIMAL / SUM(total_trades) ELSE NULL END AS win_rate,
    CASE WHEN SUM(winning_trades) > 0 THEN SUM(CASE WHEN winning_trades > 0 THEN gross_pnl ELSE 0 END) / SUM(winning_trades) ELSE NULL END AS avg_win,
    CASE WHEN SUM(losing_trades) > 0 THEN SUM(CASE WHEN losing_trades > 0 THEN gross_pnl ELSE 0 END) / SUM(losing_trades) ELSE NULL END AS avg_loss,
    CASE
        WHEN SUM(CASE WHEN gross_pnl < 0 THEN gross_pnl ELSE 0 END) <> 0
        THEN ABS(SUM(CASE WHEN gross_pnl > 0 THEN gross_pnl ELSE 0 END) / SUM(CASE WHEN gross_pnl < 0 THEN gross_pnl ELSE 0 END))
        ELSE NULL
    END AS profit_factor,
    SUM(total_edge) AS total_edge,
    CASE WHEN SUM(total_trades) > 0 THEN SUM(total_edge) / SUM(total_trades) ELSE NULL END AS average_edge,

    -- Max drawdown calculation (requires window function over cumulative P&L)
    NULL AS max_drawdown,  -- Computed separately (see Max Drawdown section below)

    -- Sharpe ratio (requires std dev calculation)
    NULL AS sharpe_ratio,  -- Computed separately (see Sharpe Ratio section below)

    CURRENT_TIMESTAMP AS last_updated
FROM
    performance_tracking
WHERE
    aggregation_level = 'hourly'
    AND period_start >= :start_day  -- Parameterized (e.g., '2025-11-10 00:00:00')
    AND period_start < :end_day     -- Parameterized (e.g., '2025-11-11 00:00:00')
GROUP BY
    strategy_id, model_id, league, market_type, DATE_TRUNC('day', period_start)
ON CONFLICT (strategy_id, model_id, league, market_type, aggregation_level, period_start)
DO UPDATE SET
    total_trades = EXCLUDED.total_trades,
    winning_trades = EXCLUDED.winning_trades,
    losing_trades = EXCLUDED.losing_trades,
    gross_pnl = EXCLUDED.gross_pnl,
    net_pnl = EXCLUDED.net_pnl,
    total_fees = EXCLUDED.total_fees,
    average_pnl_per_trade = EXCLUDED.average_pnl_per_trade,
    win_rate = EXCLUDED.win_rate,
    avg_win = EXCLUDED.avg_win,
    avg_loss = EXCLUDED.avg_loss,
    profit_factor = EXCLUDED.profit_factor,
    total_edge = EXCLUDED.total_edge,
    average_edge = EXCLUDED.average_edge,
    last_updated = CURRENT_TIMESTAMP;
```

### Max Drawdown Calculation

Max drawdown requires computing **cumulative P&L** over time and finding the largest peak-to-trough decline.

```sql
-- Compute max drawdown for a given day
-- This is a separate UPDATE query (expensive, run once daily)

WITH cumulative_pnl AS (
    SELECT
        strategy_id,
        model_id,
        league,
        market_type,
        period_start,
        SUM(net_pnl) OVER (
            PARTITION BY strategy_id, model_id, league, market_type
            ORDER BY period_start
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cumulative_net_pnl
    FROM performance_tracking
    WHERE aggregation_level = 'hourly'
        AND period_start >= :start_day
        AND period_start < :end_day
),
peak_pnl AS (
    SELECT
        strategy_id,
        model_id,
        league,
        market_type,
        period_start,
        cumulative_net_pnl,
        MAX(cumulative_net_pnl) OVER (
            PARTITION BY strategy_id, model_id, league, market_type
            ORDER BY period_start
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS peak_so_far
    FROM cumulative_pnl
),
drawdowns AS (
    SELECT
        strategy_id,
        model_id,
        league,
        market_type,
        MAX(peak_so_far - cumulative_net_pnl) AS max_drawdown
    FROM peak_pnl
    GROUP BY strategy_id, model_id, league, market_type
)
UPDATE performance_tracking
SET max_drawdown = d.max_drawdown
FROM drawdowns d
WHERE performance_tracking.strategy_id = d.strategy_id
    AND performance_tracking.model_id = d.model_id
    AND performance_tracking.league = d.league
    AND performance_tracking.market_type = d.market_type
    AND performance_tracking.aggregation_level = 'daily'
    AND performance_tracking.period_start = :start_day;
```

### Sharpe Ratio Calculation

Sharpe ratio requires **standard deviation** of returns.

```sql
-- Compute Sharpe ratio for a given day
-- Assumes risk-free rate = 0 for simplicity (can parameterize)

WITH returns AS (
    SELECT
        strategy_id,
        model_id,
        league,
        market_type,
        average_pnl_per_trade AS return
    FROM performance_tracking
    WHERE aggregation_level = 'hourly'
        AND period_start >= :start_day
        AND period_start < :end_day
),
stats AS (
    SELECT
        strategy_id,
        model_id,
        league,
        market_type,
        AVG(return) AS avg_return,
        STDDEV(return) AS std_dev
    FROM returns
    GROUP BY strategy_id, model_id, league, market_type
)
UPDATE performance_tracking
SET sharpe_ratio = CASE
    WHEN s.std_dev > 0 THEN s.avg_return / s.std_dev
    ELSE NULL
END
FROM stats s
WHERE performance_tracking.strategy_id = s.strategy_id
    AND performance_tracking.model_id = s.model_id
    AND performance_tracking.league = s.league
    AND performance_tracking.market_type = s.market_type
    AND performance_tracking.aggregation_level = 'daily'
    AND performance_tracking.period_start = :start_day;
```

---

## Implementation: Weekly/Monthly/Quarterly/Yearly

### Pattern

All higher-level aggregations follow the same pattern as daily aggregation:
1. Aggregate from previous level (daily → weekly, weekly → monthly, etc.)
2. Use `DATE_TRUNC('week', ...)`, `DATE_TRUNC('month', ...)`, etc.
3. Insert with ON CONFLICT DO UPDATE for idempotency

### SQL Template (Weekly Example)

```sql
-- Weekly aggregation (aggregate daily records)
INSERT INTO performance_tracking (
    strategy_id,
    model_id,
    league,
    market_type,
    aggregation_level,
    period_start,
    period_end,
    -- [same fields as daily]
)
SELECT
    strategy_id,
    model_id,
    league,
    market_type,
    'weekly' AS aggregation_level,
    DATE_TRUNC('week', period_start) AS period_start,  -- Week starts Monday
    DATE_TRUNC('week', period_start) + INTERVAL '1 week' - INTERVAL '1 second' AS period_end,
    SUM(total_trades) AS total_trades,
    -- [same aggregations as daily]
FROM
    performance_tracking
WHERE
    aggregation_level = 'daily'
    AND period_start >= :start_week
    AND period_start < :end_week
GROUP BY
    strategy_id, model_id, league, market_type, DATE_TRUNC('week', period_start)
ON CONFLICT (strategy_id, model_id, league, market_type, aggregation_level, period_start)
DO UPDATE SET
    -- [same updates as daily]
```

### Cron Schedule

| Level | Cron Schedule | Example |
|-------|--------------|---------|
| Hourly | `0 * * * *` | Every hour at HH:00 |
| Daily | `59 23 * * *` | 11:59 PM every day |
| Weekly | `59 23 * * 0` | 11:59 PM every Sunday |
| Monthly | `59 23 L * *` | 11:59 PM last day of month |
| Quarterly | Manual or script | End of Mar/Jun/Sep/Dec |
| Yearly | `59 23 31 12 *` | Dec 31 11:59 PM |
| All-time | `0 * * * *` | Every hour (incremental update) |

---

## Implementation: All-Time Aggregation

### Purpose

Lifetime totals across ALL time periods for a given `{strategy_id, model_id, league, market_type}`.

### Trigger

**Option A (Real-time):** Update on every trade insert.
**Option B (Batch):** Hourly cron job (recommended for simplicity).

### SQL: All-Time Aggregation

```sql
-- Aggregate ALL data into all-time record
-- Run hourly OR on trade insert

INSERT INTO performance_tracking (
    strategy_id,
    model_id,
    league,
    market_type,
    aggregation_level,
    period_start,
    period_end,
    total_trades,
    winning_trades,
    losing_trades,
    gross_pnl,
    net_pnl,
    total_fees,
    average_pnl_per_trade,
    win_rate,
    avg_win,
    avg_loss,
    profit_factor,
    total_edge,
    average_edge,
    last_updated
)
SELECT
    strategy_id,
    model_id,
    league,
    market_type,
    'all_time' AS aggregation_level,
    MIN(period_start) AS period_start,  -- Earliest trade
    MAX(period_end) AS period_end,      -- Latest trade
    SUM(total_trades) AS total_trades,
    SUM(winning_trades) AS winning_trades,
    SUM(losing_trades) AS losing_trades,
    SUM(gross_pnl) AS gross_pnl,
    SUM(net_pnl) AS net_pnl,
    SUM(total_fees) AS total_fees,
    CASE WHEN SUM(total_trades) > 0 THEN SUM(net_pnl) / SUM(total_trades) ELSE NULL END AS average_pnl_per_trade,
    CASE WHEN SUM(total_trades) > 0 THEN SUM(winning_trades)::DECIMAL / SUM(total_trades) ELSE NULL END AS win_rate,
    CASE WHEN SUM(winning_trades) > 0 THEN SUM(CASE WHEN winning_trades > 0 THEN gross_pnl ELSE 0 END) / SUM(winning_trades) ELSE NULL END AS avg_win,
    CASE WHEN SUM(losing_trades) > 0 THEN SUM(CASE WHEN losing_trades > 0 THEN gross_pnl ELSE 0 END) / SUM(losing_trades) ELSE NULL END AS avg_loss,
    CASE
        WHEN SUM(CASE WHEN gross_pnl < 0 THEN gross_pnl ELSE 0 END) <> 0
        THEN ABS(SUM(CASE WHEN gross_pnl > 0 THEN gross_pnl ELSE 0 END) / SUM(CASE WHEN gross_pnl < 0 THEN gross_pnl ELSE 0 END))
        ELSE NULL
    END AS profit_factor,
    SUM(total_edge) AS total_edge,
    CASE WHEN SUM(total_trades) > 0 THEN SUM(total_edge) / SUM(total_trades) ELSE NULL END AS average_edge,
    CURRENT_TIMESTAMP AS last_updated
FROM
    performance_tracking
WHERE
    aggregation_level = 'trade'  -- Aggregate from base level (most accurate)
GROUP BY
    strategy_id, model_id, league, market_type
ON CONFLICT (strategy_id, model_id, league, market_type, aggregation_level, period_start)
DO UPDATE SET
    period_end = EXCLUDED.period_end,
    total_trades = EXCLUDED.total_trades,
    winning_trades = EXCLUDED.winning_trades,
    losing_trades = EXCLUDED.losing_trades,
    gross_pnl = EXCLUDED.gross_pnl,
    net_pnl = EXCLUDED.net_pnl,
    total_fees = EXCLUDED.total_fees,
    average_pnl_per_trade = EXCLUDED.average_pnl_per_trade,
    win_rate = EXCLUDED.win_rate,
    avg_win = EXCLUDED.avg_win,
    avg_loss = EXCLUDED.avg_loss,
    profit_factor = EXCLUDED.profit_factor,
    total_edge = EXCLUDED.total_edge,
    average_edge = EXCLUDED.average_edge,
    last_updated = CURRENT_TIMESTAMP;
```

### Why Aggregate from Trade-Level?

**Option 1:** Aggregate from trade-level (chosen).
**Option 2:** Aggregate from daily/weekly/monthly.

**Rationale:** Trade-level aggregation is more accurate (no rounding errors from intermediate aggregations). Storage overhead is minimal (1 all-time record per partition vs ~180 daily records).

---

## Incremental Update Strategy

### Cascading Updates

When a new trade is inserted:

```
Trade INSERT
    ↓
Trade-level record INSERT
    ↓
Hourly aggregation UPDATE (for current hour)
    ↓
Daily aggregation UPDATE (for current day) — triggered at end of day
    ↓
Weekly/Monthly/... UPDATE — triggered at end of week/month
    ↓
All-time aggregation UPDATE
```

### Real-Time vs Batch Updates

| Level | Real-Time? | Batch? | Recommended |
|-------|------------|--------|-------------|
| Trade | Yes (on insert) | N/A | Real-time |
| Hourly | Possible | Yes (every hour) | Batch (hourly cron) |
| Daily | No (expensive) | Yes (daily cron) | Batch (daily cron) |
| Weekly/Monthly/... | No | Yes (weekly/monthly cron) | Batch (scheduled cron) |
| All-time | Possible | Yes (hourly cron) | Batch (hourly cron) |

**Recommendation:** Use batch cron jobs for all levels except trade-level (which is real-time on insert).

### Backfilling Historical Data

If aggregations fail or need to be recomputed:

```sql
-- Backfill hourly aggregations for a specific date range
-- Safe to re-run (idempotent)

DO $$
DECLARE
    current_hour TIMESTAMP;
    end_hour TIMESTAMP;
BEGIN
    current_hour := '2025-11-01 00:00:00';
    end_hour := '2025-11-10 23:00:00';

    WHILE current_hour <= end_hour LOOP
        -- Insert/update hourly aggregation for current_hour
        -- [Use hourly aggregation SQL from above]

        current_hour := current_hour + INTERVAL '1 hour';
    END LOOP;
END $$;
```

---

## Querying Performance Data

### Example Queries

**Get current month performance by strategy:**
```sql
SELECT
    s.strategy_name,
    s.strategy_version,
    pt.league,
    pt.market_type,
    pt.total_trades,
    pt.net_pnl,
    pt.win_rate,
    pt.average_edge,
    pt.profit_factor
FROM performance_tracking pt
    INNER JOIN strategies s ON pt.strategy_id = s.strategy_id
WHERE
    pt.aggregation_level = 'monthly'
    AND pt.period_start = DATE_TRUNC('month', CURRENT_DATE)
ORDER BY pt.net_pnl DESC;
```

**Compare two strategies (A/B testing):**
```sql
SELECT
    s.strategy_version,
    SUM(pt.total_trades) AS total_trades,
    SUM(pt.net_pnl) AS total_pnl,
    AVG(pt.win_rate) AS avg_win_rate,
    AVG(pt.average_edge) AS avg_edge
FROM performance_tracking pt
    INNER JOIN strategies s ON pt.strategy_id = s.strategy_id
WHERE
    pt.aggregation_level = 'daily'
    AND pt.period_start >= CURRENT_DATE - INTERVAL '30 days'
    AND s.strategy_name = 'halftime_entry'
    AND s.strategy_version IN ('v1.0', 'v1.1')
GROUP BY s.strategy_version
ORDER BY total_pnl DESC;
```

**Daily P&L chart (last 30 days):**
```sql
SELECT
    period_start::DATE AS date,
    SUM(net_pnl) AS daily_pnl
FROM performance_tracking
WHERE
    aggregation_level = 'daily'
    AND period_start >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY period_start::DATE
ORDER BY date;
```

---

## Dashboard Integration

### React Component Example

```typescript
// components/PerformanceChart.tsx
import { useEffect, useState } from 'react';
import Plotly from 'plotly.js-dist';

interface DailyPerformance {
    date: string;
    net_pnl: number;
}

export function PerformanceChart() {
    const [data, setData] = useState<DailyPerformance[]>([]);

    useEffect(() => {
        // Fetch daily performance data
        fetch('/api/performance/daily?days=30')
            .then(res => res.json())
            .then(setData);
    }, []);

    useEffect(() => {
        if (data.length === 0) return;

        // Render Plotly chart
        Plotly.newPlot('performance-chart', [{
            x: data.map(d => d.date),
            y: data.map(d => d.net_pnl),
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Net P&L'
        }], {
            title: 'Daily Performance (Last 30 Days)',
            xaxis: { title: 'Date' },
            yaxis: { title: 'Net P&L ($)' }
        });
    }, [data]);

    return <div id="performance-chart" />;
}
```

### API Endpoint Example

```python
# api/performance.py
from fastapi import APIRouter, Query
from sqlalchemy import text
from datetime import date, timedelta

router = APIRouter()

@router.get("/performance/daily")
def get_daily_performance(days: int = Query(30, ge=1, le=365)):
    """
    Get daily performance data for the last N days.

    Used by dashboard to render performance charts.
    """
    start_date = date.today() - timedelta(days=days)

    sql = text("""
        SELECT
            period_start::DATE AS date,
            SUM(net_pnl) AS net_pnl
        FROM performance_tracking
        WHERE
            aggregation_level = 'daily'
            AND period_start >= :start_date
        GROUP BY period_start::DATE
        ORDER BY date
    """)

    results = session.execute(sql, {"start_date": start_date}).fetchall()

    return [{"date": str(row.date), "net_pnl": float(row.net_pnl)} for row in results]
```

---

## Maintenance and Monitoring

### Monitoring Queries

**Check aggregation freshness:**
```sql
-- Verify aggregations are up-to-date
SELECT
    aggregation_level,
    MAX(last_updated) AS last_updated,
    COUNT(*) AS record_count
FROM performance_tracking
GROUP BY aggregation_level
ORDER BY aggregation_level;
```

**Detect missing aggregations:**
```sql
-- Find hours with trade-level data but no hourly aggregation
SELECT DISTINCT
    DATE_TRUNC('hour', period_start) AS missing_hour
FROM performance_tracking
WHERE aggregation_level = 'trade'
    AND DATE_TRUNC('hour', period_start) NOT IN (
        SELECT period_start
        FROM performance_tracking
        WHERE aggregation_level = 'hourly'
    )
ORDER BY missing_hour DESC
LIMIT 10;
```

### Alerting Thresholds

- **Hourly aggregation delay > 2 hours:** Alert
- **Daily aggregation not run by 1:00 AM:** Alert
- **All-time aggregation stale > 3 hours:** Alert
- **Max drawdown > 20%:** Warning
- **Win rate < 50%:** Investigation needed

---

## Common Patterns and Examples

### Pattern 1: Partition-Specific Analysis

Query performance for a specific strategy + model + league + market:

```sql
SELECT *
FROM performance_tracking
WHERE
    strategy_id = 42
    AND model_id = 7
    AND league = 'nfl'
    AND market_type = 'game_winner'
    AND aggregation_level = 'monthly'
ORDER BY period_start DESC;
```

### Pattern 2: Compare Leagues

Which league is most profitable?

```sql
SELECT
    league,
    SUM(net_pnl) AS total_pnl,
    AVG(win_rate) AS avg_win_rate,
    SUM(total_trades) AS total_trades
FROM performance_tracking
WHERE
    aggregation_level = 'all_time'
GROUP BY league
ORDER BY total_pnl DESC;
```

### Pattern 3: Model Performance Comparison

Compare two models:

```sql
SELECT
    pm.model_name,
    pm.model_version,
    SUM(pt.total_trades) AS trades,
    SUM(pt.net_pnl) AS pnl,
    AVG(pt.win_rate) AS win_rate,
    AVG(pt.model_accuracy) AS accuracy
FROM performance_tracking pt
    INNER JOIN probability_models pm ON pt.model_id = pm.model_id
WHERE
    pt.aggregation_level = 'monthly'
    AND pt.period_start >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '6 months'
    AND pm.model_name IN ('model_a', 'model_b')
GROUP BY pm.model_name, pm.model_version
ORDER BY pnl DESC;
```

---

## Troubleshooting

### Issue: Hourly Aggregation Missing Records

**Symptom:** Query shows gaps in hourly aggregation.

**Diagnosis:**
```sql
SELECT
    DATE_TRUNC('hour', period_start) AS hour,
    COUNT(*) AS trade_count
FROM performance_tracking
WHERE aggregation_level = 'trade'
GROUP BY DATE_TRUNC('hour', period_start)
ORDER BY hour DESC
LIMIT 24;

-- Compare with:
SELECT period_start
FROM performance_tracking
WHERE aggregation_level = 'hourly'
ORDER BY period_start DESC
LIMIT 24;
```

**Fix:** Backfill missing hours (see [Incremental Update Strategy](#incremental-update-strategy)).

### Issue: Decimal Precision Errors

**Symptom:** P&L values don't match trade-level sums.

**Diagnosis:**
```sql
-- Check if any float values sneaked in (should be DECIMAL)
SELECT
    aggregation_level,
    AVG(net_pnl),
    SUM(net_pnl)
FROM performance_tracking
GROUP BY aggregation_level;
```

**Fix:** Ensure all P&L fields are `DECIMAL(12,4)` in schema. Never use float arithmetic.

### Issue: Performance Degradation

**Symptom:** Dashboard queries slow (>1 second).

**Diagnosis:**
```sql
EXPLAIN ANALYZE
SELECT *
FROM performance_tracking
WHERE
    strategy_id = 42
    AND aggregation_level = 'daily'
    AND period_start >= '2025-01-01';
```

**Fix:** Verify indexes exist (see [Database Schema](#database-schema)). Consider adding covering index if specific query patterns dominate.

---

## Summary

### What You've Learned

1. **8-Level Aggregation Architecture**: Trade → Hourly → Daily → Weekly → Monthly → Quarterly → Yearly → All-Time
2. **Database Schema**: Single `performance_tracking` table with partition keys and aggregation levels
3. **Incremental Updates**: Cascading aggregations triggered by cron jobs
4. **Query Performance**: 158x-683x speedup with 4.2% storage overhead
5. **Dashboard Integration**: Real-time charts via API endpoints

### Next Steps

1. **Implement Schema**: Create `performance_tracking` table and indexes
2. **Deploy Cron Jobs**: Set up hourly/daily/weekly/monthly/yearly/all-time aggregation jobs
3. **Test Backfilling**: Verify idempotency by re-running aggregations
4. **Build Dashboard**: Integrate with React + Next.js dashboard (see DASHBOARD_DEVELOPMENT_GUIDE_V1.0.md)
5. **Monitor Metrics**: Set up alerts for aggregation delays and performance anomalies

### Related Documentation

- **ANALYTICS_ARCHITECTURE_GUIDE_V1.0.md**: End-to-end analytics pipeline
- **DASHBOARD_DEVELOPMENT_GUIDE_V1.0.md**: React + Next.js implementation
- **MODEL_EVALUATION_GUIDE_V1.0.md**: Model accuracy tracking and calibration
- **ADR-079**: Performance Tracking Architecture (design decisions)
- **ADR-083**: Analytics Data Model (materialized views strategy)

---

**END OF PERFORMANCE_TRACKING_GUIDE_V1.0.md**
