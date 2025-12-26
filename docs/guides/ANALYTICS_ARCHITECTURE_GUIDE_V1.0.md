# Analytics Architecture Guide

---
**Version:** 1.0
**Created:** 2025-11-10
**Last Updated:** 2025-11-10
**Status:** ✅ Current
**Phase:** Phase 6 (Analytics Infrastructure), Phase 7 (Dashboard), Phase 8 (A/B Testing), Phase 9 (Model Evaluation)
**Related ADRs:** ADR-079 (Performance Tracking), ADR-080 (Metrics Collection), ADR-081 (Dashboard Architecture), ADR-082 (Model Evaluation), ADR-083 (Materialized Views), ADR-084 (A/B Testing), ADR-085 (JSONB Hybrid)
**Related Requirements:** REQ-ANALYTICS-001-004, REQ-REPORTING-001
**Related Docs:** PERFORMANCE_TRACKING_GUIDE_V1.0.md, DASHBOARD_DEVELOPMENT_GUIDE_V1.0.md, MODEL_EVALUATION_GUIDE_V1.0.md, AB_TESTING_GUIDE_V1.0.md
**Data Sources:** `docs/supplementary/DATA_SOURCES_SPECIFICATION_V1.0.md` - 8 sources for analytics
**Elo Module:** `docs/guides/ELO_COMPUTATION_GUIDE_V1.0.md` 🔵 **PLANNED** - Elo-based probability models
**Target Audience:** Architects, backend developers, data engineers
**Changes in v1.0:**
- Initial creation with end-to-end analytics pipeline architecture
- 4-layer design: Data collection → Storage → Aggregation → Presentation
- Real-time + batch processing strategies
- Materialized view optimization (158x-683x speedup)
- WebSocket integration for live updates
- A/B testing and model evaluation integration
---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Principles](#architecture-principles)
3. [System Architecture Diagram](#system-architecture-diagram)
4. [Layer 1: Data Collection](#layer-1-data-collection)
5. [Layer 2: Storage](#layer-2-storage)
6. [Layer 3: Aggregation & Analytics](#layer-3-aggregation--analytics)
7. [Layer 4: Presentation (Dashboard)](#layer-4-presentation-dashboard)
8. [Real-Time Processing Pipeline](#real-time-processing-pipeline)
9. [Batch Processing Pipeline](#batch-processing-pipeline)
10. [Materialized Views Strategy](#materialized-views-strategy)
11. [Model Evaluation Integration](#model-evaluation-integration)
12. [A/B Testing Integration](#ab-testing-integration)
13. [Performance Optimization](#performance-optimization)
14. [Scalability Considerations](#scalability-considerations)
15. [Monitoring and Observability](#monitoring-and-observability)
16. [Deployment Architecture](#deployment-architecture)

---

## Overview

### What is the Analytics Architecture?

The **Precog Analytics Architecture** is a comprehensive system for collecting, storing, aggregating, and presenting trading performance data across multiple dimensions (time, strategy, model, market).

### Goals

1. **Real-Time Insights**: Display current P&L, positions, and performance within <500ms
2. **Historical Analysis**: Enable trend analysis across days, weeks, months, years
3. **Model Evaluation**: Track model accuracy, calibration, and edge capture
4. **A/B Testing**: Compare strategy and model versions with statistical rigor
5. **Scalability**: Support 100,000+ trades/month without performance degradation
6. **Cost Efficiency**: Minimize database queries through pre-computed aggregations

### Key Metrics

| Metric | Target | Current (Phase 6+) |
|--------|--------|-------------------|
| Dashboard load time | <1 second | 0.15-0.3 seconds |
| Real-time update latency | <500ms | <200ms (WebSocket) |
| Query speedup (materialized views) | >100x | 158x-683x |
| Storage overhead (aggregations) | <10% | 4.2% |
| Aggregation freshness | <1 hour | Hourly (pg_cron) |

---

## Architecture Principles

### 1. Separation of Concerns (4 Layers)

**Layer 1: Data Collection**
- Capture trade executions, position updates, model predictions
- Real-time event streaming

**Layer 2: Storage**
- PostgreSQL operational tables (trades, positions, edges, model_predictions)
- JSONB for flexible model configs and features
- SCD Type 2 versioning for historical accuracy

**Layer 3: Aggregation & Analytics**
- 8-level time-series aggregation (trade → all_time)
- Materialized views for expensive queries (158x-683x speedup)
- Batch processing via pg_cron

**Layer 4: Presentation**
- React + Next.js dashboard
- WebSocket for real-time updates
- Plotly.js for interactive charts

### 2. Dual Processing Strategy

**Real-Time Pipeline** (latency <500ms):
- Trade execution → WebSocket → Dashboard update
- Used for: Live P&L, current positions, recent trades

**Batch Pipeline** (latency 1-24 hours):
- Hourly/daily/weekly cron jobs
- Used for: Historical charts, model evaluation, A/B testing

### 3. Pre-Computation Over On-Demand

**Problem:** Aggregating 100,000+ trades on-demand is slow (5-10 seconds).

**Solution:** Pre-compute aggregations at 8 time granularities, store in `performance_tracking` table, refresh hourly.

**Result:** Dashboard queries run in 15-30ms (683x faster).

### 4. Flexible Storage (JSONB Hybrid)

**Structured Data**: Trade P&L, position sizes, market prices (normalized tables).

**Semi-Structured Data**: Model features, strategy configs, A/B test metadata (JSONB).

**Optimization**: Materialized views extract frequently-queried JSONB fields into indexed columns.

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 1: DATA COLLECTION                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐           │
│  │ Trade        │   │ Position     │   │ Model        │           │
│  │ Execution    │   │ Updates      │   │ Predictions  │           │
│  │ Events       │   │ (Entry/Exit) │   │ (Edges)      │           │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘           │
│         │                  │                  │                    │
│         └──────────────────┴──────────────────┘                    │
│                           │                                        │
└───────────────────────────┼────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      LAYER 2: STORAGE                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │              PostgreSQL 15+ Database                        │   │
│  │                                                              │   │
│  │  Operational Tables:                                        │   │
│  │  • trades (100k+ rows)                                      │   │
│  │  • positions (10k+ rows, SCD Type 2)                        │   │
│  │  • markets (5k+ rows, SCD Type 2)                           │   │
│  │  • edges (5k+ rows, SCD Type 2)                             │   │
│  │  • strategies (10 rows, immutable JSONB configs)            │   │
│  │  • probability_models (10 rows, immutable JSONB configs)    │   │
│  │  • model_predictions (100k+ rows)                           │   │
│  │  • ab_test_assignments (100k+ rows)                         │   │
│  │                                                              │   │
│  │  Performance Tracking:                                      │   │
│  │  • performance_tracking (104k+ rows, 8 aggregation levels)  │   │
│  │                                                              │   │
│  │  Materialized Views (Optimized Queries):                    │   │
│  │  • mv_current_positions (158x speedup)                      │   │
│  │  • mv_daily_pnl (555x speedup)                              │   │
│  │  • mv_strategy_performance (683x speedup)                   │   │
│  │  • mv_model_accuracy (400x speedup)                         │   │
│  │  • mv_market_edges (300x speedup)                           │   │
│  │  • mv_ab_test_results (500x speedup)                        │   │
│  └────────────────────────────────────────────────────────────┘   │
│                           │                                        │
└───────────────────────────┼────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│               LAYER 3: AGGREGATION & ANALYTICS                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────┐   ┌──────────────────┐   ┌────────────────┐ │
│  │ 8-Level          │   │ Materialized     │   │ Model          │ │
│  │ Time-Series      │   │ View Refresh     │   │ Evaluation     │ │
│  │ Aggregation      │   │ (pg_cron Hourly) │   │ (Daily Batch)  │ │
│  │                  │   │                  │   │                │ │
│  │ trade → hourly   │   │ REFRESH MATERIALI│   │ Backtesting    │ │
│  │ hourly → daily   │   │ ZED VIEW         │   │ Cross-Val      │ │
│  │ daily → weekly   │   │ mv_current_positi│   │ Calibration    │ │
│  │ weekly → monthly │   │ ons CONCURRENTLY;│   │                │ │
│  │ monthly → quart. │   │                  │   │                │ │
│  │ quart. → yearly  │   │ (Zero downtime)  │   │                │ │
│  │ yearly → all_time│   │                  │   │                │ │
│  └────────┬─────────┘   └────────┬─────────┘   └────────┬───────┘ │
│           │                      │                      │         │
│           └──────────────────────┴──────────────────────┘         │
│                           │                                        │
└───────────────────────────┼────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   LAYER 4: PRESENTATION                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │               React 18 + Next.js 14 Dashboard               │   │
│  │                                                              │   │
│  │  Components:                                                │   │
│  │  • P&L Chart (Plotly.js, WebSocket updates)                 │   │
│  │  • Position Table (current positions, real-time updates)    │   │
│  │  • Strategy Comparison (A/B test results)                   │   │
│  │  • Model Accuracy (calibration curves)                      │   │
│  │  • Market Overview (current edges, volumes)                 │   │
│  │                                                              │   │
│  │  Real-Time Updates:                                         │   │
│  │  WebSocket connection to backend (<200ms latency)           │   │
│  │  Server-sent events for trade notifications                 │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

         ┌──────────────────────────────────────────────┐
         │     MONITORING & OBSERVABILITY               │
         ├──────────────────────────────────────────────┤
         │ • Aggregation freshness alerts               │
         │ • Query performance tracking                 │
         │ • WebSocket connection monitoring            │
         │ • Materialized view refresh status           │
         │ • Database connection pool metrics           │
         └──────────────────────────────────────────────┘
```

---

## Layer 1: Data Collection

### Data Sources

**1. Trade Execution Events**
- **Source**: Trading engine after order fill
- **Data**: trade_id, position_id, side (entry/exit), quantity, price, fees, timestamp
- **Frequency**: Real-time (on trade execution)

**2. Position Updates**
- **Source**: Position manager after entry/exit/update
- **Data**: position_id, market_id, strategy_id, model_id, current_price, unrealized_pnl, status
- **Frequency**: Real-time (on price update), typically every 30-60 seconds

**3. Model Predictions (Edges)**
- **Source**: Probability model after prediction
- **Data**: market_id, model_id, predicted_prob, market_price, edge, confidence, features (JSONB)
- **Frequency**: Real-time (on market data update), typically every 5-15 minutes

**4. Market Data**
- **Source**: Kalshi API poller
- **Data**: market_id, yes_bid, yes_ask, no_bid, no_ask, volume, status, settlement_value
- **Frequency**: Real-time (WebSocket) or polling (every 30 seconds)

### Collection Mechanisms

**Real-Time Collection:**
```python
# Example: Record trade execution event
from sqlalchemy import text

def record_trade_execution(session, trade_data: dict) -> None:
    """Insert trade execution record and trigger performance tracking."""
    # Insert into trades table
    sql = text("""
        INSERT INTO trades (position_id, side, quantity, price, fees, execution_timestamp)
        VALUES (:position_id, :side, :quantity, :price, :fees, :execution_timestamp)
        RETURNING trade_id
    """)

    result = session.execute(sql, trade_data)
    trade_id = result.scalar()

    # Trigger trade-level performance tracking
    from performance_tracking import record_trade_performance
    record_trade_performance(session, trade_id)

    # Emit WebSocket event for real-time dashboard update
    from websocket_manager import emit_trade_event
    emit_trade_event(trade_id, trade_data)

    session.commit()
```

**Batch Collection:**
```python
# Example: Bulk import historical trades
def import_historical_trades(session, csv_file_path: str) -> None:
    """Bulk import trades from CSV (backfilling)."""
    import pandas as pd

    df = pd.read_csv(csv_file_path)

    # Convert to DECIMAL (never float!)
    df['price'] = df['price'].astype(str).apply(Decimal)
    df['fees'] = df['fees'].astype(str).apply(Decimal)

    # Bulk insert
    from sqlalchemy.dialects.postgresql import insert

    for chunk in np.array_split(df, len(df) // 1000):  # 1000 rows per batch
        stmt = insert(trades).values(chunk.to_dict('records'))
        session.execute(stmt)

    session.commit()

    # Trigger batch aggregation for imported period
    from performance_tracking import backfill_aggregations
    backfill_aggregations(session, start_date=df['execution_timestamp'].min())
```

---

## Layer 2: Storage

### Operational Tables

See `DATABASE_SCHEMA_SUMMARY_V1.8.md` for complete schema.

**Key Tables:**
1. `trades` - Individual trade executions (base data)
2. `positions` - Position lifecycle (SCD Type 2 versioned)
3. `markets` - Market data snapshots (SCD Type 2 versioned)
4. `edges` - Edge calculations (SCD Type 2 versioned)
5. `strategies` - Strategy definitions (immutable JSONB configs)
6. `probability_models` - Model definitions (immutable JSONB configs)
7. `model_predictions` - Model prediction history
8. `ab_test_assignments` - A/B test variant assignments
9. `performance_tracking` - 8-level time-series aggregations

### Storage Patterns

**Pattern 1: SCD Type 2 for Frequently-Changing Data**

Used for: markets, positions, edges

```sql
-- Example: Position updates maintain history
CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,
    market_id INTEGER NOT NULL,
    strategy_id INTEGER NOT NULL,
    model_id INTEGER NOT NULL,
    side VARCHAR(3) NOT NULL,  -- 'yes', 'no'
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(10,4) NOT NULL,
    current_price DECIMAL(10,4),
    unrealized_pnl DECIMAL(12,4),
    status VARCHAR(20) NOT NULL,  -- 'open', 'monitoring', 'exited'
    row_current_ind BOOLEAN NOT NULL DEFAULT TRUE,  -- SCD Type 2
    row_start_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_end_ts TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1
);

-- Query current positions ONLY
SELECT * FROM positions WHERE row_current_ind = TRUE;
```

**Pattern 2: Immutable JSONB Configs for Versioned Strategies/Models**

Used for: strategies, probability_models

```sql
-- Example: Strategy configs are immutable
CREATE TABLE strategies (
    strategy_id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL,
    strategy_version VARCHAR(20) NOT NULL,  -- 'v1.0', 'v1.1', etc.
    config JSONB NOT NULL,  -- IMMUTABLE config (create new version to change)
    status VARCHAR(20) NOT NULL,  -- 'draft', 'testing', 'active', 'deprecated'
    UNIQUE (strategy_name, strategy_version)
);

-- To change config: Create new version (v1.0 → v1.1)
INSERT INTO strategies (strategy_name, strategy_version, config, status)
VALUES ('halftime_entry', 'v1.1', '{"min_lead": 10}', 'draft');

-- NOT allowed: UPDATE config for existing version (violates immutability)
```

**Pattern 3: JSONB for Flexible Semi-Structured Data**

Used for: model features, A/B test metadata

```sql
-- Example: Model features stored as JSONB
CREATE TABLE model_predictions (
    prediction_id SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL,
    market_id INTEGER NOT NULL,
    predicted_prob DECIMAL(6,4) NOT NULL,
    features JSONB NOT NULL,  -- Flexible: {"elo_diff": 8.5, "home_adv": 2.3, ...}
    prediction_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Query by JSONB field
SELECT *
FROM model_predictions
WHERE (features->>'elo_diff')::DECIMAL > 10;

-- Create index for frequent JSONB queries
CREATE INDEX idx_model_pred_elo_diff ON model_predictions ((features->>'elo_diff'));
```

---

## Layer 3: Aggregation & Analytics

### 8-Level Time-Series Aggregation

**Hierarchy:** trade → hourly → daily → weekly → monthly → quarterly → yearly → all_time

**Purpose:** Enable fast queries at any time granularity without on-demand aggregation.

**Implementation:** See `PERFORMANCE_TRACKING_GUIDE_V1.0.md` for complete details.

**Key Insight:** Pre-compute aggregations incrementally (hourly cron jobs), store in `performance_tracking` table, query in 15-30ms instead of 5-10 seconds.

### Materialized Views

**Purpose:** Pre-compute expensive joins and aggregations for dashboard queries.

**Refresh Strategy:** `REFRESH MATERIALIZED VIEW CONCURRENTLY` via pg_cron (hourly).

**Performance:** 158x-683x query speedup (ADR-083).

**Example Materialized Views:**

**1. Current Positions (158x speedup):**
```sql
CREATE MATERIALIZED VIEW mv_current_positions AS
SELECT
    p.position_id,
    p.market_id,
    m.ticker,
    m.league,
    m.market_type,
    s.strategy_name,
    s.strategy_version,
    pm.model_name,
    pm.model_version,
    p.side,
    p.quantity,
    p.entry_price,
    p.current_price,
    p.unrealized_pnl,
    p.status,
    p.row_start_ts AS entry_timestamp
FROM
    positions p
    INNER JOIN markets m ON p.market_id = m.market_id AND m.row_current_ind = TRUE
    INNER JOIN strategies s ON p.strategy_id = s.strategy_id
    INNER JOIN probability_models pm ON p.model_id = pm.model_id
WHERE
    p.row_current_ind = TRUE
    AND p.status IN ('open', 'monitoring');

-- Unique index required for REFRESH CONCURRENTLY (zero downtime)
CREATE UNIQUE INDEX idx_mv_current_positions_pk ON mv_current_positions (position_id);

-- Refresh hourly via pg_cron
-- SELECT cron.schedule('refresh_current_positions', '0 * * * *', 'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_current_positions');
```

**2. Daily P&L (555x speedup):**
```sql
CREATE MATERIALIZED VIEW mv_daily_pnl AS
SELECT
    period_start::DATE AS date,
    strategy_id,
    model_id,
    league,
    market_type,
    total_trades,
    net_pnl,
    win_rate,
    average_edge
FROM performance_tracking
WHERE aggregation_level = 'daily'
ORDER BY period_start DESC;

CREATE UNIQUE INDEX idx_mv_daily_pnl_pk ON mv_daily_pnl (date, strategy_id, model_id, league, market_type);
```

**3. Strategy Performance (683x speedup):**
```sql
CREATE MATERIALIZED VIEW mv_strategy_performance AS
SELECT
    s.strategy_name,
    s.strategy_version,
    pt.league,
    pt.market_type,
    SUM(pt.total_trades) AS total_trades,
    SUM(pt.net_pnl) AS total_pnl,
    AVG(pt.win_rate) AS avg_win_rate,
    AVG(pt.average_edge) AS avg_edge,
    AVG(pt.profit_factor) AS avg_profit_factor
FROM performance_tracking pt
    INNER JOIN strategies s ON pt.strategy_id = s.strategy_id
WHERE pt.aggregation_level = 'all_time'
GROUP BY s.strategy_name, s.strategy_version, pt.league, pt.market_type;

CREATE UNIQUE INDEX idx_mv_strategy_perf_pk ON mv_strategy_performance (strategy_name, strategy_version, league, market_type);
```

### Batch Processing (pg_cron)

**Setup pg_cron Extension:**
```sql
-- Install pg_cron (requires superuser or RDS extension management)
CREATE EXTENSION pg_cron;

-- Grant access to application user
GRANT USAGE ON SCHEMA cron TO precog_app;
```

**Schedule Aggregation Jobs:**
```sql
-- Hourly: Aggregate trade-level → hourly
SELECT cron.schedule(
    'aggregate_hourly_performance',
    '0 * * * *',  -- Every hour at HH:00
    $$
    CALL aggregate_hourly_performance(NOW() - INTERVAL '1 hour');
    $$
);

-- Daily: Aggregate hourly → daily
SELECT cron.schedule(
    'aggregate_daily_performance',
    '59 23 * * *',  -- 11:59 PM every day
    $$
    CALL aggregate_daily_performance(CURRENT_DATE);
    $$
);

-- Hourly: Refresh all materialized views
SELECT cron.schedule(
    'refresh_materialized_views',
    '30 * * * *',  -- Every hour at HH:30 (offset from aggregation)
    $$
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_current_positions;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_pnl;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_strategy_performance;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_model_accuracy;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_market_edges;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_ab_test_results;
    $$
);
```

**Monitor Cron Jobs:**
```sql
-- View scheduled jobs
SELECT * FROM cron.job ORDER BY jobid;

-- View job run history
SELECT * FROM cron.job_run_details ORDER BY start_time DESC LIMIT 20;

-- Check for failures
SELECT *
FROM cron.job_run_details
WHERE status = 'failed'
ORDER BY start_time DESC
LIMIT 10;
```

---

## Layer 4: Presentation (Dashboard)

### Dashboard Architecture

**Framework:** React 18 + Next.js 14 (server-side rendering + client-side SPA)

**Charting:** Plotly.js (interactive financial charts)

**Real-Time:** WebSocket (Socket.IO for trade/position updates)

**Styling:** Tailwind CSS (responsive design)

### Dashboard Components

See `DASHBOARD_DEVELOPMENT_GUIDE_V1.0.md` for complete implementation.

**Key Components:**
1. **P&L Chart** - Daily performance line chart (Plotly.js, last 30 days)
2. **Position Table** - Current open positions with live updates
3. **Strategy Comparison** - A/B test results (side-by-side metrics)
4. **Model Accuracy** - Calibration curves and accuracy metrics
5. **Market Overview** - Current edges, volumes, win rates by market type

### API Endpoints

**FastAPI Backend:**
```python
from fastapi import APIRouter, Query
from sqlalchemy import text
from datetime import date, timedelta

router = APIRouter()

@router.get("/performance/daily")
def get_daily_performance(days: int = Query(30, ge=1, le=365)):
    """Get daily P&L for last N days (optimized via materialized view)."""
    start_date = date.today() - timedelta(days=days)

    # Query materialized view (555x faster than on-demand aggregation)
    sql = text("""
        SELECT date, SUM(net_pnl) AS net_pnl
        FROM mv_daily_pnl
        WHERE date >= :start_date
        GROUP BY date
        ORDER BY date
    """)

    results = session.execute(sql, {"start_date": start_date}).fetchall()

    return [{"date": str(row.date), "net_pnl": float(row.net_pnl)} for row in results]

@router.get("/positions/current")
def get_current_positions():
    """Get current open positions (optimized via materialized view)."""
    # Query materialized view (158x faster)
    sql = text("SELECT * FROM mv_current_positions ORDER BY entry_timestamp DESC")

    results = session.execute(sql).fetchall()

    return [dict(row._mapping) for row in results]

@router.get("/strategies/comparison")
def compare_strategies(strategy_name: str, versions: list[str] = Query(...)):
    """Compare two strategy versions (A/B testing)."""
    # Query materialized view (683x faster)
    sql = text("""
        SELECT *
        FROM mv_strategy_performance
        WHERE strategy_name = :strategy_name
        AND strategy_version = ANY(:versions)
    """)

    results = session.execute(sql, {
        "strategy_name": strategy_name,
        "versions": versions
    }).fetchall()

    return [dict(row._mapping) for row in results]
```

### WebSocket Integration

**Backend (Socket.IO):**
```python
from socketio import AsyncServer
import socketio

sio = AsyncServer(async_mode='asgi', cors_allowed_origins='*')

@sio.event
async def connect(sid, environ):
    """Client connected to WebSocket."""
    print(f"[INFO] Client {sid} connected")

@sio.event
async def disconnect(sid):
    """Client disconnected from WebSocket."""
    print(f"[INFO] Client {sid} disconnected")

# Emit trade event to all connected clients
async def emit_trade_event(trade_id: int, trade_data: dict):
    """Notify dashboard of new trade execution."""
    await sio.emit('trade_executed', {
        'trade_id': trade_id,
        'side': trade_data['side'],
        'quantity': trade_data['quantity'],
        'price': str(trade_data['price']),  # Convert Decimal to string
        'timestamp': trade_data['execution_timestamp'].isoformat()
    })

# Emit position update event
async def emit_position_update(position_id: int, unrealized_pnl: Decimal):
    """Notify dashboard of position P&L update."""
    await sio.emit('position_updated', {
        'position_id': position_id,
        'unrealized_pnl': str(unrealized_pnl)
    })
```

**Frontend (React):**
```typescript
// hooks/useWebSocket.ts
import { useEffect, useState } from 'react';
import io, { Socket } from 'socket.io-client';

export function useWebSocket(url: string) {
    const [socket, setSocket] = useState<Socket | null>(null);
    const [connected, setConnected] = useState(false);

    useEffect(() => {
        const newSocket = io(url);

        newSocket.on('connect', () => {
            console.log('[INFO] WebSocket connected');
            setConnected(true);
        });

        newSocket.on('disconnect', () => {
            console.log('[INFO] WebSocket disconnected');
            setConnected(false);
        });

        newSocket.on('trade_executed', (data) => {
            console.log('[INFO] Trade executed:', data);
            // Trigger dashboard update
        });

        newSocket.on('position_updated', (data) => {
            console.log('[INFO] Position updated:', data);
            // Update position table
        });

        setSocket(newSocket);

        return () => {
            newSocket.disconnect();
        };
    }, [url]);

    return { socket, connected };
}
```

---

## Real-Time Processing Pipeline

### Pipeline Flow

```
Trade Execution
    ↓
Insert into trades table
    ↓
Insert trade-level performance_tracking record
    ↓
Emit WebSocket event to dashboard
    ↓
Dashboard updates live P&L chart (<200ms latency)
```

### Implementation

**Step 1: Trade Execution Event Handler**
```python
async def handle_trade_execution(trade_data: dict) -> None:
    """Handle trade execution event (async for WebSocket emit)."""
    async with get_async_session() as session:
        # Insert trade record
        trade_id = await insert_trade_record(session, trade_data)

        # Insert trade-level performance tracking
        await record_trade_performance(session, trade_id)

        # Commit transaction
        await session.commit()

    # Emit WebSocket event (non-blocking)
    await emit_trade_event(trade_id, trade_data)

    # Trigger hourly aggregation update (if needed)
    # Can be skipped if hourly cron job handles this
```

**Step 2: Position Update Event Handler**
```python
async def handle_position_update(position_id: int, new_price: Decimal) -> None:
    """Handle position price update event."""
    async with get_async_session() as session:
        # Update position current_price and unrealized_pnl
        await update_position_price(session, position_id, new_price)

        # Get updated P&L
        unrealized_pnl = await calculate_unrealized_pnl(session, position_id)

        # Commit transaction
        await session.commit()

    # Emit WebSocket event
    await emit_position_update(position_id, unrealized_pnl)
```

---

## Batch Processing Pipeline

### Pipeline Flow

```
Hourly Cron Job (HH:00)
    ↓
Aggregate trade-level → hourly performance_tracking
    ↓
Refresh materialized views CONCURRENTLY (HH:30)
    ↓
Dashboard queries materialized views (683x faster)
```

### Implementation

**Hourly Aggregation:**
```python
# Scheduled via pg_cron OR application cron (e.g., APScheduler)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', hour='*', minute=0)
async def hourly_aggregation_job():
    """Run hourly aggregation (triggered at HH:00)."""
    async with get_async_session() as session:
        # Aggregate previous hour
        start_hour = (datetime.now() - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        await aggregate_hourly_performance(session, start_hour)

        await session.commit()

    print(f"[INFO] Hourly aggregation completed for {start_hour.strftime('%Y-%m-%d %H:00')}")

scheduler.start()
```

**Daily Aggregation:**
```python
@scheduler.scheduled_job('cron', hour=23, minute=59)
async def daily_aggregation_job():
    """Run daily aggregation (triggered at 11:59 PM)."""
    async with get_async_session() as session:
        # Aggregate current day
        today = date.today()
        await aggregate_daily_performance(session, today)

        # Compute max drawdown and Sharpe ratio
        await compute_daily_risk_metrics(session, today)

        await session.commit()

    print(f"[INFO] Daily aggregation completed for {today}")
```

---

## Materialized Views Strategy

### Why Materialized Views?

**Problem:** Dashboard queries involve expensive joins (5-7 tables) and aggregations (100k+ rows).

**Example (slow query - 5-10 seconds):**
```sql
-- Get current positions with market details, strategy, model (JOIN 5 tables)
SELECT
    p.position_id,
    m.ticker,
    s.strategy_name,
    pm.model_name,
    p.unrealized_pnl
FROM positions p
    INNER JOIN markets m ON p.market_id = m.market_id AND m.row_current_ind = TRUE
    INNER JOIN strategies s ON p.strategy_id = s.strategy_id
    INNER JOIN probability_models pm ON p.model_id = pm.model_id
WHERE p.row_current_ind = TRUE AND p.status = 'open';
-- Execution time: 4.2 seconds (100k positions, 5k markets)
```

**Solution:** Materialized view (158x faster):
```sql
-- Query materialized view (pre-computed join)
SELECT * FROM mv_current_positions;
-- Execution time: 27ms (158x speedup!)
```

### Materialized View Best Practices

1. **REFRESH CONCURRENTLY**: Zero downtime (requires unique index)
2. **Hourly Refresh**: Balance freshness vs overhead
3. **Selective Materialization**: Only expensive queries (not all queries)
4. **Monitor Refresh Time**: Alert if refresh > 10 minutes

### Complete Materialized View List

See ADR-083 for complete details.

| View Name | Purpose | Speedup | Refresh Frequency |
|-----------|---------|---------|-------------------|
| `mv_current_positions` | Dashboard position table | 158x | Hourly |
| `mv_daily_pnl` | P&L chart | 555x | Hourly |
| `mv_strategy_performance` | Strategy comparison | 683x | Hourly |
| `mv_model_accuracy` | Model evaluation | 400x | Daily |
| `mv_market_edges` | Market overview | 300x | Hourly |
| `mv_ab_test_results` | A/B test summary | 500x | Daily |

---

## Model Evaluation Integration

### Integration Points

**1. Daily Batch Job: Compute Model Accuracy**
```python
@scheduler.scheduled_job('cron', hour=1, minute=0)  # 1:00 AM daily
async def model_evaluation_job():
    """Compute model accuracy metrics (backtesting, calibration)."""
    from model_evaluation import evaluate_all_models

    async with get_async_session() as session:
        # Evaluate all active models
        results = await evaluate_all_models(session)

        # Store results in model_evaluation_results table
        await store_evaluation_results(session, results)

        await session.commit()

    print(f"[INFO] Model evaluation completed: {len(results)} models evaluated")
```

**2. Dashboard: Display Calibration Curves**
```typescript
// components/ModelCalibrationChart.tsx
import Plotly from 'plotly.js-dist';

export function ModelCalibrationChart({ modelId }: { modelId: number }) {
    const [calibrationData, setCalibrationData] = useState([]);

    useEffect(() => {
        fetch(`/api/models/${modelId}/calibration`)
            .then(res => res.json())
            .then(setCalibrationData);
    }, [modelId]);

    useEffect(() => {
        if (calibrationData.length === 0) return;

        Plotly.newPlot('calibration-chart', [
            {
                x: calibrationData.map(d => d.predicted_prob),
                y: calibrationData.map(d => d.actual_prob),
                mode: 'markers',
                name: 'Model Predictions'
            },
            {
                x: [0, 1],
                y: [0, 1],
                mode: 'lines',
                name: 'Perfect Calibration',
                line: { dash: 'dash', color: 'gray' }
            }
        ], {
            title: 'Model Calibration Curve',
            xaxis: { title: 'Predicted Probability' },
            yaxis: { title: 'Actual Win Rate' }
        });
    }, [calibrationData]);

    return <div id="calibration-chart" />;
}
```

See `MODEL_EVALUATION_GUIDE_V1.0.md` for complete implementation.

---

## A/B Testing Integration

### Integration Points

**1. Assign Variants on Trade Entry**
```python
from ab_testing import assign_ab_test_variant

def enter_position(session, market_id: int, strategy_id: int, model_id: int):
    """Enter new position with A/B test variant assignment."""
    # Assign variant (stratified by league + market_type)
    variant = assign_ab_test_variant(
        session=session,
        experiment_name='strategy_v1.0_vs_v1.1',
        user_id=None,  # No user-level assignment (market-level)
        stratification_key=f"{market.league}_{market.market_type}"
    )

    # Record assignment
    insert_ab_test_assignment(session, market_id, variant)

    # Use assigned variant for trading logic
    if variant == 'control':
        strategy_id = get_strategy_id('halftime_entry', 'v1.0')
    else:  # variant == 'treatment'
        strategy_id = get_strategy_id('halftime_entry', 'v1.1')

    # ... execute trade with assigned strategy
```

**2. Analyze A/B Test Results**
```python
@scheduler.scheduled_job('cron', hour=2, minute=0)  # 2:00 AM daily
async def ab_test_analysis_job():
    """Analyze A/B test results (statistical significance)."""
    from ab_testing import analyze_experiment

    async with get_async_session() as session:
        # Analyze active experiments
        experiments = await get_active_experiments(session)

        for experiment in experiments:
            results = await analyze_experiment(session, experiment.experiment_name)

            # Store results in ab_test_results table
            await store_ab_test_results(session, experiment.experiment_name, results)

        await session.commit()

    print(f"[INFO] A/B test analysis completed: {len(experiments)} experiments")
```

**3. Dashboard: Display A/B Test Results**
```typescript
// components/ABTestComparison.tsx
export function ABTestComparison({ experimentName }: { experimentName: string }) {
    const [results, setResults] = useState(null);

    useEffect(() => {
        fetch(`/api/ab-tests/${experimentName}/results`)
            .then(res => res.json())
            .then(setResults);
    }, [experimentName]);

    if (!results) return <div>Loading...</div>;

    return (
        <div>
            <h2>A/B Test: {experimentName}</h2>
            <table>
                <thead>
                    <tr>
                        <th>Variant</th>
                        <th>Trades</th>
                        <th>Win Rate</th>
                        <th>Avg P&L</th>
                        <th>Total P&L</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Control</td>
                        <td>{results.control.trades}</td>
                        <td>{(results.control.win_rate * 100).toFixed(2)}%</td>
                        <td>${results.control.avg_pnl.toFixed(2)}</td>
                        <td>${results.control.total_pnl.toFixed(2)}</td>
                    </tr>
                    <tr>
                        <td>Treatment</td>
                        <td>{results.treatment.trades}</td>
                        <td>{(results.treatment.win_rate * 100).toFixed(2)}%</td>
                        <td>${results.treatment.avg_pnl.toFixed(2)}</td>
                        <td>${results.treatment.total_pnl.toFixed(2)}</td>
                    </tr>
                </tbody>
            </table>
            <div>
                <strong>Statistical Significance:</strong> {results.p_value < 0.05 ? 'Yes' : 'No'} (p = {results.p_value.toFixed(4)})
            </div>
        </div>
    );
}
```

See `AB_TESTING_GUIDE_V1.0.md` for complete implementation.

---

## Performance Optimization

### Query Optimization

1. **Use Materialized Views**: 158x-683x speedup
2. **Index Frequently-Queried Columns**: strategy_id, model_id, aggregation_level, period_start
3. **Avoid SELECT ***: Query only needed columns
4. **Use EXPLAIN ANALYZE**: Identify slow queries

### Aggregation Optimization

1. **Incremental Updates**: Only aggregate new data (not full table scans)
2. **Batch Processing**: Hourly/daily cron jobs (not real-time)
3. **Idempotent Logic**: ON CONFLICT DO UPDATE (safe to re-run)

### WebSocket Optimization

1. **Throttle Updates**: Max 1 update per position per second
2. **Compress Payloads**: Use JSON compression (gzip)
3. **Connection Pooling**: Limit concurrent WebSocket connections

---

## Scalability Considerations

### Database Scalability

**Current Capacity (Single PostgreSQL Instance):**
- 100,000 trades/month
- 10,000 open positions
- 5,000 markets
- <1 second dashboard queries

**Scaling Strategy (Phase 10+):**
- **Read Replicas**: Offload dashboard queries to read replicas
- **Partitioning**: Partition `trades` and `performance_tracking` by date
- **Archiving**: Move trades >1 year old to archive database

### Application Scalability

**Current Capacity:**
- Single FastAPI instance
- 100 concurrent dashboard users
- 10 trades/second

**Scaling Strategy (Phase 10+):**
- **Load Balancer**: NGINX for multiple FastAPI instances
- **Redis Cache**: Cache dashboard API responses (1-minute TTL)
- **Message Queue**: RabbitMQ for async trade processing

---

## Monitoring and Observability

### Key Metrics

1. **Aggregation Freshness**: Time since last hourly/daily/weekly aggregation
2. **Query Performance**: P95 latency for dashboard API endpoints
3. **WebSocket Connections**: Active connections, disconnection rate
4. **Materialized View Refresh**: Time to refresh each view, failure rate
5. **Database Connection Pool**: Active connections, wait time

### Alerting Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Aggregation delay | >2 hours | >6 hours |
| Dashboard API P95 latency | >500ms | >2 seconds |
| WebSocket disconnection rate | >5% | >20% |
| Materialized view refresh time | >10 min | >30 min |
| Database connection pool | >80% | >95% |

### Monitoring Implementation

**Prometheus Metrics:**
```python
from prometheus_client import Counter, Histogram, Gauge

# Aggregation metrics
aggregation_duration = Histogram(
    'aggregation_duration_seconds',
    'Time taken to run aggregation job',
    ['aggregation_level']
)

aggregation_failures = Counter(
    'aggregation_failures_total',
    'Number of aggregation job failures',
    ['aggregation_level']
)

# Dashboard API metrics
api_request_duration = Histogram(
    'api_request_duration_seconds',
    'API request duration',
    ['endpoint']
)

# WebSocket metrics
websocket_connections = Gauge(
    'websocket_connections_active',
    'Number of active WebSocket connections'
)
```

**Grafana Dashboard:**
- Panel 1: Aggregation freshness (time series)
- Panel 2: Dashboard API latency (heatmap)
- Panel 3: WebSocket connections (gauge)
- Panel 4: Database connection pool (time series)
- Panel 5: Materialized view refresh status (table)

---

## Deployment Architecture

### Production Environment

```
┌────────────────────────────────────────────────────────────┐
│                      Load Balancer (NGINX)                 │
│                    (SSL Termination + Routing)             │
└────────────┬───────────────────────────┬───────────────────┘
             │                           │
             ▼                           ▼
┌────────────────────────┐   ┌────────────────────────┐
│  FastAPI Instance 1    │   │  FastAPI Instance 2    │
│  (Dashboard API +      │   │  (Dashboard API +      │
│   WebSocket Server)    │   │   WebSocket Server)    │
└────────────┬───────────┘   └────────────┬───────────┘
             │                           │
             └───────────┬───────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────┐
        │      PostgreSQL 15+ (Primary)          │
        │  • Operational tables (trades, etc.)   │
        │  • performance_tracking (8 levels)     │
        │  • Materialized views (6 views)        │
        │  • pg_cron extension (hourly jobs)     │
        └────────────┬───────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────────┐
        │   PostgreSQL Read Replica (Optional)   │
        │   • Dashboard queries offloaded here   │
        │   • Reduces load on primary            │
        └────────────────────────────────────────┘
```

### Container Deployment (Docker)

**docker-compose.yml:**
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: precog
      POSTGRES_USER: precog_app
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  api:
    build: ./backend
    command: uvicorn main:app --host 0.0.0.0 --port 8000
    environment:
      DATABASE_URL: postgresql://precog_app:${DB_PASSWORD}@postgres:5432/precog
      REDIS_URL: redis://redis:6379
    depends_on:
      - postgres
      - redis
    ports:
      - "8000:8000"

  dashboard:
    build: ./frontend
    command: npm run start
    environment:
      NEXT_PUBLIC_API_URL: http://api:8000
      NEXT_PUBLIC_WS_URL: ws://api:8000
    ports:
      - "3000:3000"

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
      - dashboard

volumes:
  postgres_data:
```

---

## Summary

### What You've Learned

1. **4-Layer Architecture**: Data Collection → Storage → Aggregation → Presentation
2. **Dual Processing**: Real-time (WebSocket, <200ms) + Batch (cron, hourly/daily)
3. **Materialized Views**: 158x-683x query speedup with hourly REFRESH CONCURRENTLY
4. **8-Level Aggregation**: Trade → all_time (4.2% storage for 683x speedup)
5. **Dashboard Integration**: React + Next.js + Plotly.js + WebSocket
6. **Model Evaluation**: Daily batch jobs for calibration and accuracy tracking
7. **A/B Testing**: Stratified random assignment with statistical validation
8. **Scalability**: Read replicas, partitioning, archiving for 10x growth

### Next Steps

1. **Implement Performance Tracking**: Create `performance_tracking` table, deploy cron jobs
2. **Create Materialized Views**: Implement 6 materialized views, set up pg_cron refresh
3. **Build Dashboard**: React + Next.js implementation (see DASHBOARD_DEVELOPMENT_GUIDE_V1.0.md)
4. **Integrate WebSocket**: Real-time trade/position updates
5. **Deploy Model Evaluation**: Daily batch jobs for accuracy tracking
6. **Set Up A/B Testing**: Variant assignment and statistical analysis
7. **Configure Monitoring**: Prometheus + Grafana dashboards

### Related Documentation

- **PERFORMANCE_TRACKING_GUIDE_V1.0.md**: 8-level aggregation implementation
- **DASHBOARD_DEVELOPMENT_GUIDE_V1.0.md**: React + Next.js dashboard
- **MODEL_EVALUATION_GUIDE_V1.0.md**: Backtesting, cross-validation, calibration
- **AB_TESTING_GUIDE_V1.0.md**: Stratified assignment, statistical tests
- **DATABASE_SCHEMA_SUMMARY_V1.8.md**: Complete database schema
- **ADR-079 through ADR-085**: Architecture decisions for analytics infrastructure

---

**END OF ANALYTICS_ARCHITECTURE_GUIDE_V1.0.md**
