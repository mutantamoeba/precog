# Database Schema Summary

---
**Version:** 1.2
**Last Updated:** 2025-10-16
**Status:** ✅ Current
**Changes in v1.2:** Clarified terminology (probability vs. odds vs. market price); updated table descriptions and field documentation; added terminology note section
---

## Overview
PostgreSQL 15+ database with versioning for frequently-changing data and append-only for immutable records.

## Core Concepts

### Versioning Strategy
**Versioned Tables** use `row_current_ind` (BOOLEAN):
- `TRUE` = Current/active row
- `FALSE` = Historical row (superseded)
- New data = INSERT new row, UPDATE old row to set `row_current_ind = FALSE`

**Append-Only Tables** have no `row_current_ind`:
- Data is immutable (trades, settlements)
- Never UPDATE, only INSERT

### Foreign Key Relationships
All major tables properly linked for efficient joins and referential integrity.

## Table Categories

### 1. Platform & Market Hierarchy

#### platforms
```sql
CREATE TABLE platforms (
    platform_id VARCHAR PRIMARY KEY,     -- 'kalshi', 'polymarket'
    platform_type VARCHAR NOT NULL,      -- 'trading', 'data_source'
    display_name VARCHAR NOT NULL,
    base_url VARCHAR,
    websocket_url VARCHAR,
    api_version VARCHAR,
    auth_method VARCHAR,                 -- 'rsa_pss', 'api_key', 'metamask'
    fees_structure JSONB,
    status VARCHAR DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### series
```sql
CREATE TABLE series (
    series_id VARCHAR PRIMARY KEY,
    platform_id VARCHAR REFERENCES platforms(platform_id),  -- FK to platforms
    external_id VARCHAR NOT NULL,
    category VARCHAR NOT NULL,           -- 'sports', 'politics', 'entertainment'
    subcategory VARCHAR,                 -- 'nfl', 'presidential', 'boxoffice'
    title VARCHAR NOT NULL,
    frequency VARCHAR,                   -- 'single', 'recurring'
    metadata JSONB,                      -- Platform/category-specific data
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### events
```sql
CREATE TABLE events (
    event_id VARCHAR PRIMARY KEY,
    platform_id VARCHAR REFERENCES platforms(platform_id),  -- FK to platforms
    series_id VARCHAR REFERENCES series(series_id),         -- FK to series
    external_id VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    subcategory VARCHAR,
    title VARCHAR NOT NULL,
    description TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    status VARCHAR,                      -- 'scheduled', 'live', 'final', 'cancelled'
    result JSONB,                        -- Final outcome data
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### markets
```sql
CREATE TABLE markets (
    market_id VARCHAR PRIMARY KEY,
    platform_id VARCHAR REFERENCES platforms(platform_id),  -- FK to platforms
    event_id VARCHAR REFERENCES events(event_id),           -- FK to events
    external_id VARCHAR NOT NULL,
    ticker VARCHAR,
    title VARCHAR NOT NULL,
    market_type VARCHAR,                 -- 'binary', 'categorical', 'scalar'
    yes_price FLOAT,                     -- Current yes price (0.0-1.0)
    no_price FLOAT,                      -- Current no price (0.0-1.0)
    volume INT,
    open_interest INT,
    spread FLOAT,
    status VARCHAR,                      -- 'open', 'closed', 'settled'
    settlement_value FLOAT,              -- Final settlement (if settled)
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE  -- ✅ VERSIONED
);

CREATE INDEX idx_markets_event ON markets(event_id);
CREATE INDEX idx_markets_platform ON markets(platform_id);
CREATE INDEX idx_markets_current ON markets(row_current_ind) WHERE row_current_ind = TRUE;
```

### 2. Live Game Data

#### game_states
```sql
CREATE TABLE game_states (
    game_state_id SERIAL PRIMARY KEY,
    event_id VARCHAR REFERENCES events(event_id),           -- FK to events
    external_game_id VARCHAR,
    sport VARCHAR NOT NULL,              -- 'nfl', 'nba', 'tennis', 'mlb'
    home_team VARCHAR,
    away_team VARCHAR,
    home_score INT,
    away_score INT,
    period VARCHAR,                      -- 'Q1', 'Q2', 'Halftime', 'Q3', 'Q4', 'OT', 'Final'
    time_remaining VARCHAR,              -- '12:45', '00:00'
    possession VARCHAR,                  -- 'home', 'away', null
    status VARCHAR,                      -- 'scheduled', 'pregame', 'live', 'halftime', 'final'
    sport_metadata JSONB,                -- Sport-specific data (down, distance, fouls, etc.)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE  -- ✅ VERSIONED
);

CREATE INDEX idx_game_states_event ON game_states(event_id);
CREATE INDEX idx_game_states_sport ON game_states(sport);
CREATE INDEX idx_game_states_current ON game_states(row_current_ind) WHERE row_current_ind = TRUE;
```

### 3. Probability & Edge Detection

#### probability_matrices
```sql
CREATE TABLE probability_matrices (
    probability_id SERIAL PRIMARY KEY,
    category VARCHAR NOT NULL,           -- 'sports', 'politics', 'entertainment'
    subcategory VARCHAR NOT NULL,        -- 'nfl', 'nba', 'presidential', 'boxoffice'
    version VARCHAR NOT NULL,            -- 'v1.0', 'v2.0'
    state_descriptor VARCHAR NOT NULL,   -- 'halftime', '30_days_before', 'opening_weekend'
    value_bucket VARCHAR NOT NULL,       -- '10+_points', 'polling_3to5_ahead', 'budget_50to100M'
    situational_factors JSONB,           -- Flexible metadata (home/away, fav/underdog, etc.)
    win_probability FLOAT NOT NULL,
    confidence_interval_lower FLOAT,
    confidence_interval_upper FLOAT,
    sample_size INT,
    source VARCHAR,                      -- Data source for probabilities
    methodology TEXT,                    -- How probabilities calculated
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_probability_lookup ON probability_matrices(category, subcategory, version, state_descriptor, value_bucket);
```

#### edges
```sql
CREATE TABLE edges (
    edge_id SERIAL PRIMARY KEY,
    market_id VARCHAR REFERENCES markets(market_id),            -- FK to markets
    probability_matrix_id INT REFERENCES probability_matrices(probability_id),  -- FK to probability_matrices
    expected_value FLOAT NOT NULL,
    true_win_probability FLOAT NOT NULL,
    market_implied_probability FLOAT NOT NULL,
    market_price FLOAT NOT NULL,
    confidence_level VARCHAR,            -- 'high', 'medium', 'low'
    confidence_metrics JSONB,            -- {sample_size, ci_width, data_recency}
    recommended_action VARCHAR,          -- 'auto_execute', 'alert', 'ignore'
    created_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE  -- ✅ VERSIONED
);

CREATE INDEX idx_edges_market ON edges(market_id);
CREATE INDEX idx_edges_probability ON edges(probability_matrix_id);
CREATE INDEX idx_edges_ev ON edges(expected_value) WHERE row_current_ind = TRUE;
CREATE INDEX idx_edges_current ON edges(row_current_ind) WHERE row_current_ind = TRUE;
```

### 4. Trading & Positions

#### positions
```sql
CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,
    market_id VARCHAR REFERENCES markets(market_id),            -- FK to markets
    platform_id VARCHAR REFERENCES platforms(platform_id),      -- FK to platforms
    side VARCHAR NOT NULL,               -- 'yes', 'no'
    entry_price FLOAT NOT NULL,
    quantity INT NOT NULL,
    fees FLOAT,
    status VARCHAR DEFAULT 'open',       -- 'open', 'closed', 'settled'
    unrealized_pnl FLOAT,
    realized_pnl FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE  -- ✅ VERSIONED (quantity changes)
);

CREATE INDEX idx_positions_market ON positions(market_id);
CREATE INDEX idx_positions_platform ON positions(platform_id);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_current ON positions(row_current_ind) WHERE row_current_ind = TRUE;
```

#### trades
```sql
CREATE TABLE trades (
    trade_id SERIAL PRIMARY KEY,
    market_id VARCHAR REFERENCES markets(market_id),            -- FK to markets
    platform_id VARCHAR REFERENCES platforms(platform_id),      -- FK to platforms
    position_id INT REFERENCES positions(position_id),          -- FK to positions
    edge_id INT REFERENCES edges(edge_id),                      -- FK to edges (what triggered trade)
    order_id VARCHAR,                    -- Platform's order ID
    side VARCHAR NOT NULL,               -- 'buy', 'sell'
    price FLOAT NOT NULL,
    quantity INT NOT NULL,
    fees FLOAT,
    edge_at_execution FLOAT,
    confidence_at_execution VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
    -- ❌ NO row_current_ind (trades are immutable)
);

CREATE INDEX idx_trades_market ON trades(market_id);
CREATE INDEX idx_trades_platform ON trades(platform_id);
CREATE INDEX idx_trades_position ON trades(position_id);
CREATE INDEX idx_trades_edge ON trades(edge_id);
CREATE INDEX idx_trades_created ON trades(created_at);
```

#### settlements
```sql
CREATE TABLE settlements (
    settlement_id SERIAL PRIMARY KEY,
    market_id VARCHAR REFERENCES markets(market_id),            -- FK to markets
    platform_id VARCHAR REFERENCES platforms(platform_id),      -- FK to platforms
    outcome VARCHAR NOT NULL,            -- 'yes', 'no', or other
    payout FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
    -- ❌ NO row_current_ind (settlements are final)
);

CREATE INDEX idx_settlements_market ON settlements(market_id);
CREATE INDEX idx_settlements_platform ON settlements(platform_id);
```

#### account_balance
```sql
CREATE TABLE account_balance (
    balance_id SERIAL PRIMARY KEY,
    platform_id VARCHAR REFERENCES platforms(platform_id),      -- FK to platforms
    balance FLOAT NOT NULL,
    currency VARCHAR DEFAULT 'USD',
    created_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE  -- ✅ VERSIONED
);

CREATE INDEX idx_balance_platform ON account_balance(platform_id);
CREATE INDEX idx_balance_current ON account_balance(row_current_ind) WHERE row_current_ind = TRUE;
```

### 5. Configuration & State

#### config_overrides
```sql
CREATE TABLE config_overrides (
    override_id SERIAL PRIMARY KEY,
    config_key VARCHAR NOT NULL,         -- 'trading.sports_live.execution.max_spread'
    override_value JSONB NOT NULL,       -- {value: 0.08}
    data_type VARCHAR,                   -- 'float', 'int', 'bool', 'string'
    reason TEXT,                         -- Why override was applied
    applied_by VARCHAR,                  -- Who/what applied it
    applied_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,                -- Optional expiration
    active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_config_overrides_key ON config_overrides(config_key);
CREATE INDEX idx_config_overrides_active ON config_overrides(active) WHERE active = TRUE;
```

#### circuit_breaker_events
```sql
CREATE TABLE circuit_breaker_events (
    event_id SERIAL PRIMARY KEY,
    breaker_type VARCHAR NOT NULL,       -- 'daily_loss_limit', 'api_failures', 'data_stale'
    triggered_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    trigger_value JSONB,                 -- What caused trigger
    resolution_action VARCHAR,           -- How it was resolved
    notes TEXT
);

CREATE INDEX idx_circuit_breaker_triggered ON circuit_breaker_events(triggered_at);
```

#### system_health
```sql
CREATE TABLE system_health (
    health_id SERIAL PRIMARY KEY,
    component VARCHAR NOT NULL,          -- 'kalshi_api', 'database', 'edge_detector'
    status VARCHAR NOT NULL,             -- 'healthy', 'degraded', 'down'
    last_check TIMESTAMP DEFAULT NOW(),
    details JSONB,                       -- Metrics, error messages
    alert_sent BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_health_component ON system_health(component);
CREATE INDEX idx_health_status ON system_health(status);
```

## Relationships Diagram (Simplified)

```
platforms (1) -----> (N) series (1) -----> (N) events (1) -----> (N) markets
    |                                           |                      |
    |                                           |                      +---> (N) edges (N) <--- (1) probability_matrices
    |                                           |                      |           |
    |                                           |                      |           +---> (N) trades
    |                                           +---> (1) game_states  |
    |                                                                  |
    +-----------> (N) positions <------------------------------------ +
                       |
                       +---> (N) trades
                       
    +-----------> (N) account_balance
    +-----------> (N) settlements
```

## Query Patterns

### Get Current Market Price
```sql
SELECT yes_price, no_price, volume
FROM markets
WHERE market_id = $1 AND row_current_ind = TRUE;
```

### Get All Active Edges Above Threshold
```sql
SELECT e.*, m.ticker, m.title
FROM edges e
JOIN markets m ON e.market_id = m.market_id AND m.row_current_ind = TRUE
WHERE e.row_current_ind = TRUE 
  AND e.expected_value >= 0.08
  AND e.confidence_level IN ('high', 'medium')
ORDER BY e.expected_value DESC;
```

### Get Position P&L
```sql
SELECT p.*, 
       SUM(t.quantity * t.price) as total_cost,
       p.quantity * m.yes_price - total_cost as unrealized_pnl
FROM positions p
JOIN trades t ON p.position_id = t.position_id
JOIN markets m ON p.market_id = m.market_id AND m.row_current_ind = TRUE
WHERE p.row_current_ind = TRUE AND p.status = 'open'
GROUP BY p.position_id;
```

### Trade History for Analysis
```sql
SELECT t.*, e.expected_value, e.confidence_level, s.outcome
FROM trades t
LEFT JOIN edges e ON t.edge_id = e.edge_id
LEFT JOIN settlements s ON t.market_id = s.market_id
WHERE t.created_at >= NOW() - INTERVAL '30 days'
ORDER BY t.created_at DESC;
```

## Storage Estimates

### Annual Data Volume
- **Markets:** ~500K updates/year × 200 bytes = 100 MB
- **Game States:** ~200K updates/year × 300 bytes = 60 MB
- **Edges:** ~2M calculations/year × 150 bytes = 300 MB
- **Trades:** ~10K trades/year × 200 bytes = 2 MB
- **Positions:** ~30K updates/year × 200 bytes = 6 MB
- **Total:** ~470 MB/year core tables
- **With indexes, logs, overhead:** ~18 GB/year total

### Archival Strategy
- **Hot Storage (PostgreSQL):** Last 18 months
- **Warm Storage (Compressed PostgreSQL):** 18-42 months
- **Cold Storage (S3/Parquet):** 42+ months
- **Total Retention:** 10 years

## Backup Strategy
- **Daily:** Full database backup to S3 (automated, 2 AM)
- **Hourly:** Incremental WAL backups during trading hours
- **Retention:** 30 days online, 1 year in cold storage
- **Test Restores:** Monthly verification

## Terminology Note

**Probability vs. Odds vs. Market Price:**
- **Probability**: 0.0000 to 1.0000 (what we store in `win_probability` fields in `probability_matrices`)
- **Market Price**: $0.0000 to $1.0000 (what Kalshi shows; stored in `market_price` field in `markets` table)
- **Odds**: Ratio format (e.g., 3:2); rarely used in Precog
- **Edge**: Difference between probability and price (stored in `edge` fields)

This database uses "probability" for all likelihood calculations stored in the `probability_matrices` table. The term "odds" is only used in user-facing displays when specifically formatted as a ratio.

**Example:**
- We calculate: `win_probability = 0.7000` (70% chance from probability_matrices table)
- Kalshi shows: `market_price = 0.6000` ($0.60 for YES contract)
- Our edge: `edge = 0.7000 - 0.6000 = 0.1000` (10% edge)

---
**Document Version:** 1.2
**Last Updated:** October 16, 2025
**Purpose:** Database schema reference for development and troubleshooting
