# Database Schema Summary

---
**Version:** 1.7
**Last Updated:** 2025-10-24
**Status:** ✅ Current - Migrations 001-010 Applied
**Changes in v1.7:**
- **CRITICAL**: Completed SCD Type 2 implementation - All tables now have `row_end_ts` (migrations 005, 007)
- **CRITICAL**: Markets table PRIMARY KEY refactored - Surrogate key (id SERIAL) replaces business key (migration 009)
- Added external ID traceability columns across 5 tables for API audit trail (migration 008)
- Added exit management columns to positions table (migration 004)
- Added trade_metadata JSONB and order execution columns to trades table (migrations 005, 006)
- **NEW**: Added teams and elo_rating_history tables for Elo model (migration 010 - Phase 4 preparation)
- Updated table count: 27 tables (23 operational + 4 ML placeholders)
- Fixed markets FK relationships - All child tables use market_uuid instead of market_id
- Seeded 32 NFL teams with initial Elo ratings (1370-1660, avg 1503.1)
**Changes in v1.6:**
- **CRITICAL**: Added alerts table for centralized alert/notification logging
- Added method tables placeholders (methods, method_templates) - Phase 4-5 implementation
- **NEW**: Added ML infrastructure table placeholders (feature_definitions, features_historical, training_datasets, model_training_runs) - Phase 9 implementation
- Enhanced probability_matrices with matrix_name and description columns (planned - Phase 1 completion)
- Added method_id columns to trades and edges tables (planned - Phase 4-5)
- Updated table count: 25 tables (21 operational + 2 method placeholders + 2 alerts + 4 ML placeholders)
- Clarified Elo timeline: Phase 4 (initial), Phase 6 (sport expansion), Phase 9 (enhanced with features)
**Changes in v1.5:**
- **CRITICAL**: Added position monitoring and exit management (Phase 5)
- Added `position_exits` table - Track each exit event (including partial exits)
- Added `exit_attempts` table - Track exit order attempts for debugging (price walking)
- Enhanced `positions` table with monitoring fields: current_price, unrealized_pnl, unrealized_pnl_pct, last_update
- Added exit tracking to `positions`: exit_reason, exit_priority
- Support for 10 exit conditions with CRITICAL/HIGH/MEDIUM/LOW priorities
**Changes in v1.4:**
- Added `strategies` and `probability_models` tables (IMMUTABLE versions)
- Added `trailing_stop_state` JSONB to positions
- Added `strategy_id` and `model_id` FKs for trade attribution
- Added helper views: `active_strategies`, `active_models`, `trade_attribution`
**Changes in v1.3:**
- **CRITICAL**: Fixed all price/probability fields to use DECIMAL(10,4) instead of FLOAT
- Added CHECK constraints for data validation
- Added ON DELETE CASCADE for referential integrity
- Added helper views for current data (current_markets, etc.)
- Added partitioning notes for scalability
**Changes in v1.2:** Clarified terminology (probability vs. odds vs. market price); updated table descriptions and field documentation; added terminology note section
---

## Overview
PostgreSQL 15+ database with versioning for frequently-changing data and append-only for immutable records.

## Core Concepts

### Versioning Strategies (Two Patterns)

#### Pattern 1: Versioned Data (SCD Type 2)
**Versioned Tables** use `row_current_ind` (BOOLEAN) for frequently-changing data:
- `TRUE` = Current/active row
- `FALSE` = Historical row (superseded)
- New data = INSERT new row, UPDATE old row to set `row_current_ind = FALSE`
- **Use for:** markets, positions, game_states, edges (data changes frequently)

#### Pattern 2: Immutable Versions (Semantic Versioning)
**Immutable Version Tables** use `version` fields (e.g., v1.0, v1.1, v2.0):
- Each version is IMMUTABLE once created
- Config/parameters NEVER change after creation
- To update: Create new version (e.g., v1.0 → v1.1 for bug fix, v1.0 → v2.0 for major change)
- Status and metrics CAN update (lifecycle transitions, performance tracking)
- **Use for:** strategies, probability_models (A/B testing, trade attribution integrity)

**Why Two Patterns?**
- **Immutable Versions:** Required for A/B testing integrity and exact trade attribution
- **Versioned Data:** Efficient for rapidly-changing market/game data

#### Append-Only Tables
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
    yes_price DECIMAL(10,4),             -- Current yes price (0.0000-1.0000) - EXACT PRECISION
    no_price DECIMAL(10,4),              -- Current no price (0.0000-1.0000) - EXACT PRECISION
    volume INT,
    open_interest INT,
    spread DECIMAL(10,4),                -- DECIMAL for price precision
    status VARCHAR,                      -- 'open', 'closed', 'settled'
    settlement_value DECIMAL(10,4),      -- Final settlement (if settled) - EXACT PRECISION
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE  -- ✅ VERSIONED DATA (prices change frequently)
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
    row_current_ind BOOLEAN DEFAULT TRUE  -- ✅ VERSIONED DATA (scores update frequently)
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
    win_probability DECIMAL(10,4) NOT NULL,  -- EXACT PRECISION: 0.0000-1.0000
    confidence_interval_lower DECIMAL(10,4), -- EXACT PRECISION
    confidence_interval_upper DECIMAL(10,4), -- EXACT PRECISION
    sample_size INT,
    source VARCHAR,                      -- Data source for probabilities
    methodology TEXT,                    -- How probabilities calculated
    matrix_name VARCHAR,                 -- NEW v1.6: Human-readable matrix name (e.g., 'nfl_halftime_comeback')
    description TEXT,                    -- NEW v1.6: Detailed description of what this matrix represents
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_probability_lookup ON probability_matrices(category, subcategory, version, state_descriptor, value_bucket);
CREATE INDEX idx_probability_matrices_name ON probability_matrices(matrix_name);  -- NEW v1.6
```

**NEW in v1.6:**
- `matrix_name`: Human-readable identifier for easy lookup and reference
- `description`: Detailed documentation of matrix purpose and usage
- Index on matrix_name for fast lookups by name

**Example:**
```sql
UPDATE probability_matrices
SET
    matrix_name = 'nfl_halftime_comeback',
    description = 'Win probability for NFL teams trailing at halftime, segmented by point differential and home/away status'
WHERE category = 'sports' AND subcategory = 'nfl' AND state_descriptor = 'halftime';
```

#### probability_models (NEW in v1.4)
```sql
CREATE TABLE probability_models (
    model_id SERIAL PRIMARY KEY,
    model_name VARCHAR NOT NULL,         -- 'elo_nfl', 'regression_nba', 'ensemble_v1'
    model_version VARCHAR NOT NULL,      -- 'v1.0', 'v1.1', 'v2.0' (semantic versioning)
    model_type VARCHAR NOT NULL,         -- 'elo', 'regression', 'ensemble', 'ml'
    sport VARCHAR,                       -- 'nfl', 'nba', 'mlb' (NULL for multi-sport)
    config JSONB NOT NULL,               -- ⚠️ IMMUTABLE: Model parameters/hyperparameters
    description TEXT,
    status VARCHAR DEFAULT 'draft',      -- ✅ MUTABLE: 'draft', 'training', 'validating', 'active', 'deprecated'
    validation_accuracy DECIMAL(10,4),   -- ✅ MUTABLE: Accuracy on validation set
    validation_calibration DECIMAL(10,4),-- ✅ MUTABLE: Calibration score
    validation_sample_size INT,          -- ✅ MUTABLE: Number of validation samples
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR,
    notes TEXT,
    UNIQUE(model_name, model_version)    -- Enforce unique versions per model
    -- ❌ NO row_current_ind (versions are IMMUTABLE)
);

CREATE INDEX idx_probability_models_name ON probability_models(model_name);
CREATE INDEX idx_probability_models_status ON probability_models(status);
CREATE INDEX idx_probability_models_active ON probability_models(status) WHERE status = 'active';
```

**Immutable Version Pattern:**
- `config` field is IMMUTABLE once created (never change parameters)
- To fix bug or tune parameters: Create new version (v1.0 → v1.1)
- To make major change: Create new major version (v1.0 → v2.0)
- `status` field is MUTABLE (lifecycle: draft → training → validating → active → deprecated)
- Validation metrics are MUTABLE (updated as model is evaluated)

**Example:**
```sql
-- Original model
INSERT INTO probability_models (model_name, model_version, model_type, sport, config, status)
VALUES ('elo_nfl', 'v1.0', 'elo', 'nfl', '{"k_factor": 28, "initial_rating": 1500}', 'active');

-- Bug fix: k_factor should be 30 → Create v1.1
INSERT INTO probability_models (model_name, model_version, model_type, sport, config, status)
VALUES ('elo_nfl', 'v1.1', 'elo', 'nfl', '{"k_factor": 30, "initial_rating": 1500}', 'active');

-- Update v1.0 status (config stays unchanged)
UPDATE probability_models SET status = 'deprecated' WHERE model_name = 'elo_nfl' AND model_version = 'v1.0';
```

#### strategies (NEW in v1.4)
```sql
CREATE TABLE strategies (
    strategy_id SERIAL PRIMARY KEY,
    strategy_name VARCHAR NOT NULL,      -- 'halftime_entry', 'underdog_fade', 'momentum_scalp'
    strategy_version VARCHAR NOT NULL,   -- 'v1.0', 'v1.1', 'v2.0' (semantic versioning)
    strategy_type VARCHAR NOT NULL,      -- 'entry', 'exit', 'sizing', 'hedging'
    sport VARCHAR,                       -- 'nfl', 'nba', 'mlb' (NULL for multi-sport)
    config JSONB NOT NULL,               -- ⚠️ IMMUTABLE: Strategy parameters/rules
    description TEXT,
    status VARCHAR DEFAULT 'draft',      -- ✅ MUTABLE: 'draft', 'testing', 'active', 'inactive', 'deprecated'
    paper_roi DECIMAL(10,4),             -- ✅ MUTABLE: ROI from paper trading
    live_roi DECIMAL(10,4),              -- ✅ MUTABLE: ROI from live trading
    paper_trades_count INT DEFAULT 0,    -- ✅ MUTABLE: Number of paper trades executed
    live_trades_count INT DEFAULT 0,     -- ✅ MUTABLE: Number of live trades executed
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR,
    notes TEXT,
    UNIQUE(strategy_name, strategy_version)  -- Enforce unique versions per strategy
    -- ❌ NO row_current_ind (versions are IMMUTABLE)
);

CREATE INDEX idx_strategies_name ON strategies(strategy_name);
CREATE INDEX idx_strategies_status ON strategies(status);
CREATE INDEX idx_strategies_active ON strategies(status) WHERE status = 'active';
```

**Immutable Version Pattern:**
- `config` field is IMMUTABLE once created (never change strategy rules)
- To fix bug or tune parameters: Create new version (v1.0 → v1.1)
- To make major change: Create new major version (v1.0 → v2.0)
- `status` field is MUTABLE (lifecycle: draft → testing → active → inactive → deprecated)
- Performance metrics are MUTABLE (paper_roi, live_roi accumulate over time)

**Example:**
```sql
-- Original strategy
INSERT INTO strategies (strategy_name, strategy_version, strategy_type, sport, config, status)
VALUES ('halftime_entry', 'v1.0', 'entry', 'nfl', '{"min_lead": 7, "max_spread": 0.08}', 'testing');

-- Bug fix: min_lead should be 10 → Create v1.1
INSERT INTO strategies (strategy_name, strategy_version, strategy_type, sport, config, status)
VALUES ('halftime_entry', 'v1.1', 'entry', 'nfl', '{"min_lead": 10, "max_spread": 0.08}', 'testing');

-- Update metrics for v1.1 as trades execute (config stays unchanged)
UPDATE strategies SET paper_roi = 0.15, paper_trades_count = 42
WHERE strategy_name = 'halftime_entry' AND strategy_version = 'v1.1';
```

#### edges
```sql
CREATE TABLE edges (
    edge_id SERIAL PRIMARY KEY,
    market_id VARCHAR REFERENCES markets(market_id),            -- FK to markets
    probability_matrix_id INT REFERENCES probability_matrices(probability_id),  -- FK to probability_matrices
    strategy_id INT REFERENCES strategies(strategy_id),         -- FK to strategies (NEW in v1.4)
    model_id INT REFERENCES probability_models(model_id),       -- FK to probability_models (NEW in v1.4)
    expected_value DECIMAL(10,4) NOT NULL,        -- EXACT PRECISION for EV calculations
    true_win_probability DECIMAL(10,4) NOT NULL,  -- EXACT PRECISION: 0.0000-1.0000
    market_implied_probability DECIMAL(10,4) NOT NULL,  -- EXACT PRECISION: 0.0000-1.0000
    market_price DECIMAL(10,4) NOT NULL,          -- EXACT PRECISION: $0.0000-$1.0000
    confidence_level VARCHAR,            -- 'high', 'medium', 'low'
    confidence_metrics JSONB,            -- {sample_size, ci_width, data_recency}
    recommended_action VARCHAR,          -- 'auto_execute', 'alert', 'ignore'
    created_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE  -- ✅ VERSIONED DATA (market conditions change)
);

CREATE INDEX idx_edges_market ON edges(market_id);
CREATE INDEX idx_edges_probability ON edges(probability_matrix_id);
CREATE INDEX idx_edges_strategy ON edges(strategy_id);  -- NEW in v1.4
CREATE INDEX idx_edges_model ON edges(model_id);        -- NEW in v1.4
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
    entry_price DECIMAL(10,4) NOT NULL,  -- EXACT PRECISION: $0.0000-$1.0000
    quantity INT NOT NULL,
    fees DECIMAL(10,4),                  -- EXACT PRECISION for fee calculations
    status VARCHAR DEFAULT 'open',       -- 'open', 'closed', 'settled'

    -- P&L Tracking
    unrealized_pnl DECIMAL(10,4),        -- EXACT PRECISION for P&L
    realized_pnl DECIMAL(10,4),          -- EXACT PRECISION for P&L

    -- NEW in v1.5: Monitoring Fields (Phase 5)
    current_price DECIMAL(10,4),         -- Latest market price from monitoring loop
    unrealized_pnl_pct DECIMAL(6,4),     -- Unrealized P&L as percentage (e.g., 0.1234 = 12.34%)
    last_update TIMESTAMP,               -- Last monitoring check timestamp

    -- Trailing Stop Management (v1.4)
    trailing_stop_state JSONB,           -- {active, peak_price, current_stop_price, current_distance}

    -- NEW in v1.5: Exit Tracking (Phase 5)
    exit_reason VARCHAR(50),             -- stop_loss, trailing_stop, profit_target, etc.
    exit_priority VARCHAR(20),           -- CRITICAL, HIGH, MEDIUM, LOW

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE  -- ✅ VERSIONED DATA (quantity/price/stop changes)
);

CREATE INDEX idx_positions_market ON positions(market_id);
CREATE INDEX idx_positions_platform ON positions(platform_id);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_current ON positions(row_current_ind) WHERE row_current_ind = TRUE;
CREATE INDEX idx_positions_last_update ON positions(last_update);  -- NEW v1.5: Monitor loop queries
```

**Trailing Stop State (v1.4):**
- `trailing_stop_state` is a JSONB field that stores dynamic trailing stop loss data
- Updates as market price moves (triggers new position row with row_current_ind)
- Example: `{"active": true, "activation_price": "0.6600", "peak_price": "0.8000", "current_stop_price": "0.7840", "current_distance": "0.02"}`

**Monitoring Fields (v1.5):**
- `current_price`: Updated every 30s (normal) or 5s (urgent) by monitoring loop
- `unrealized_pnl_pct`: Calculated as (current_price - entry_price) / entry_price
- `last_update`: Monitoring loop health check - alerts if stale

**Exit Tracking (v1.5):**
- `exit_reason`: Which exit condition triggered (stop_loss, trailing_stop, profit_target, etc.)
- `exit_priority`: Priority level when exit was triggered (CRITICAL, HIGH, MEDIUM, LOW)

#### trades
```sql
CREATE TABLE trades (
    trade_id SERIAL PRIMARY KEY,
    market_id VARCHAR REFERENCES markets(market_id),            -- FK to markets
    platform_id VARCHAR REFERENCES platforms(platform_id),      -- FK to platforms
    position_id INT REFERENCES positions(position_id),          -- FK to positions
    edge_id INT REFERENCES edges(edge_id),                      -- FK to edges (what triggered trade)
    strategy_id INT REFERENCES strategies(strategy_id),         -- FK to strategies (NEW in v1.4)
    model_id INT REFERENCES probability_models(model_id),       -- FK to probability_models (NEW in v1.4)
    order_id VARCHAR,                    -- Platform's order ID
    side VARCHAR NOT NULL,               -- 'buy', 'sell'
    price DECIMAL(10,4) NOT NULL,        -- EXACT PRECISION: $0.0000-$1.0000
    quantity INT NOT NULL,
    fees DECIMAL(10,4),                  -- EXACT PRECISION for fee calculations
    edge_at_execution DECIMAL(10,4),     -- EXACT PRECISION for historical edge
    confidence_at_execution VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
    -- ❌ NO row_current_ind (trades are immutable)
);

CREATE INDEX idx_trades_market ON trades(market_id);
CREATE INDEX idx_trades_platform ON trades(platform_id);
CREATE INDEX idx_trades_position ON trades(position_id);
CREATE INDEX idx_trades_edge ON trades(edge_id);
CREATE INDEX idx_trades_strategy ON trades(strategy_id);      -- NEW in v1.4
CREATE INDEX idx_trades_model ON trades(model_id);            -- NEW in v1.4
CREATE INDEX idx_trades_created ON trades(created_at);
```

#### position_exits (NEW in v1.5)
```sql
CREATE TABLE position_exits (
    exit_id SERIAL PRIMARY KEY,
    position_id INT REFERENCES positions(position_id),          -- FK to positions
    exit_condition VARCHAR(50) NOT NULL,     -- stop_loss, trailing_stop, profit_target, etc.
    exit_priority VARCHAR(20) NOT NULL,      -- CRITICAL, HIGH, MEDIUM, LOW
    quantity_exited INT NOT NULL,            -- Contracts exited (supports partial exits)
    exit_price DECIMAL(10,4) NOT NULL,       -- EXACT PRECISION: Actual fill price
    unrealized_pnl_at_exit DECIMAL(10,4),    -- P&L at time of exit
    created_at TIMESTAMP DEFAULT NOW()
    -- ❌ NO row_current_ind (exits are immutable events)
);

CREATE INDEX idx_position_exits_position ON position_exits(position_id);
CREATE INDEX idx_position_exits_condition ON position_exits(exit_condition);
CREATE INDEX idx_position_exits_priority ON position_exits(exit_priority);
CREATE INDEX idx_position_exits_created ON position_exits(created_at);
```

**Purpose:** Track each exit event (including partial exits)
**Why append-only?** Exit events are historical records - never change after creation
**Partial Exits Example:**
- Position of 100 contracts enters at $0.60
- Exit 1: 50 contracts at $0.69 (+15% profit) → partial_exit_target, MEDIUM
- Exit 2: 25 contracts at $0.75 (+25% profit) → partial_exit_target, MEDIUM
- Exit 3: 25 contracts at $0.88 (trailing stop hit) → trailing_stop, HIGH
- Result: 3 rows in position_exits, 1 position closes

#### exit_attempts (NEW in v1.5)
```sql
CREATE TABLE exit_attempts (
    attempt_id SERIAL PRIMARY KEY,
    position_id INT REFERENCES positions(position_id),          -- FK to positions
    exit_condition VARCHAR(50) NOT NULL,     -- Which condition triggered this attempt
    priority_level VARCHAR(20) NOT NULL,     -- CRITICAL, HIGH, MEDIUM, LOW
    order_type VARCHAR(20) NOT NULL,         -- market, limit
    limit_price DECIMAL(10,4),               -- Limit price if order_type = 'limit'
    fill_price DECIMAL(10,4),                -- Actual fill price (NULL if didn't fill)
    quantity INT NOT NULL,                   -- Quantity attempted
    attempt_number INT NOT NULL,             -- 1st attempt, 2nd walk, 3rd walk, etc.
    timeout_seconds INT,                     -- Timeout before next attempt
    success BOOLEAN,                         -- Did this attempt result in fill?
    created_at TIMESTAMP DEFAULT NOW()
    -- ❌ NO row_current_ind (attempts are immutable logs)
);

CREATE INDEX idx_exit_attempts_position ON exit_attempts(position_id);
CREATE INDEX idx_exit_attempts_condition ON exit_attempts(exit_condition);
CREATE INDEX idx_exit_attempts_success ON exit_attempts(success);
CREATE INDEX idx_exit_attempts_created ON exit_attempts(created_at);
```

**Purpose:** Debug exit execution - track price walking and order attempts
**Why needed?** Answer questions like "Why didn't my exit fill?"
**Price Walking Example:**
- Stop loss triggers (CRITICAL priority)
- Attempt 1: Limit at $0.75 → No fill after 10s
- Attempt 2: Limit at $0.74 → No fill after 10s (walk price by 1¢)
- Attempt 3: Market order → Fill at $0.73 ✅
- Result: 3 rows in exit_attempts, last one success=TRUE

**Trade Attribution (NEW in v1.4):**
- Every trade now links to EXACT strategy version and model version used
- Enables precise A/B testing and performance analysis
- Example: "This trade used halftime_entry v1.1 with elo_nfl v2.0"

#### settlements
```sql
CREATE TABLE settlements (
    settlement_id SERIAL PRIMARY KEY,
    market_id VARCHAR REFERENCES markets(market_id),            -- FK to markets
    platform_id VARCHAR REFERENCES platforms(platform_id),      -- FK to platforms
    outcome VARCHAR NOT NULL,            -- 'yes', 'no', or other
    payout DECIMAL(10,4),                -- EXACT PRECISION for payout amounts
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
    balance DECIMAL(10,4) NOT NULL,      -- EXACT PRECISION for account balance
    currency VARCHAR DEFAULT 'USD',
    created_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE  -- ✅ VERSIONED DATA
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

#### alerts (NEW in v1.6)
```sql
CREATE TABLE alerts (
    alert_id SERIAL PRIMARY KEY,
    alert_uuid UUID DEFAULT gen_random_uuid() UNIQUE,

    -- Classification
    alert_type VARCHAR NOT NULL,        -- 'circuit_breaker', 'api_failure', 'loss_threshold', 'health_degraded'
    severity VARCHAR NOT NULL,          -- 'critical', 'high', 'medium', 'low'
    category VARCHAR,                   -- 'risk', 'system', 'trading', 'data'
    component VARCHAR NOT NULL,         -- 'kalshi_api', 'edge_detector', 'position_manager'

    -- Message
    message TEXT NOT NULL,              -- Human-readable alert message
    details JSONB,                      -- Additional context (stack traces, metrics, config values)

    -- Source tracking
    source_table VARCHAR,               -- 'circuit_breaker_events', 'system_health', 'trades'
    source_id INT,                      -- FK to source table record

    -- Timestamps
    triggered_at TIMESTAMP DEFAULT NOW() NOT NULL,
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP,

    -- Acknowledgement & Resolution
    acknowledged_by VARCHAR,            -- Username or system
    acknowledged_notes TEXT,
    resolved_by VARCHAR,
    resolved_notes TEXT,
    resolution_action VARCHAR,          -- 'fixed', 'false_positive', 'ignored', 'escalated'

    -- Notification tracking
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_channels JSONB,        -- {'email': true, 'sms': true, 'slack': false}
    notification_sent_at TIMESTAMP,
    notification_attempts INT DEFAULT 0,
    notification_errors JSONB,          -- Track delivery failures

    -- Deduplication
    fingerprint VARCHAR(64),            -- MD5 hash for detecting duplicates
    suppressed BOOLEAN DEFAULT FALSE,   -- Rate-limited/suppressed duplicate

    -- Metadata
    environment VARCHAR,                -- 'demo', 'prod'
    tags JSONB,                         -- Flexible tagging

    -- Constraints
    CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    CHECK (resolution_action IS NULL OR resolution_action IN ('fixed', 'false_positive', 'ignored', 'escalated'))
);

-- Indexes
CREATE INDEX idx_alerts_type ON alerts(alert_type);
CREATE INDEX idx_alerts_severity ON alerts(severity);
CREATE INDEX idx_alerts_component ON alerts(component);
CREATE INDEX idx_alerts_triggered ON alerts(triggered_at DESC);
CREATE INDEX idx_alerts_unresolved ON alerts(resolved_at) WHERE resolved_at IS NULL;
CREATE INDEX idx_alerts_fingerprint ON alerts(fingerprint) WHERE fingerprint IS NOT NULL;
CREATE INDEX idx_alerts_environment ON alerts(environment);
```

**Purpose:** Centralized alert/notification logging with full lifecycle tracking

**Key Features:**
- **Severity-based routing**: Critical → email+SMS, low → file only
- **Deduplication**: Fingerprint-based to prevent spam
- **Notification tracking**: Records which channels were used and delivery status
- **Acknowledgement flow**: Alerts require acknowledgement before resolution
- **Source linking**: Links to originating event (circuit breaker, health check, etc.)

**Integration:**
- Circuit breaker triggers → log_alert()
- System health degraded → log_alert()
- Trade execution failures → log_alert()
- Model performance degradation → log_alert()
- API failures → log_alert()

**Notification Channels (configured in system.yaml):**
- Console (always)
- File logging (always)
- Email (SMTP - critical/high)
- SMS (Twilio - critical only)
- Slack (webhook - optional)
- Custom webhook (optional)

**Example:**
```sql
-- Log critical circuit breaker alert
INSERT INTO alerts (
    alert_type, severity, category, component, message, details,
    notification_channels, fingerprint, environment
)
VALUES (
    'circuit_breaker', 'critical', 'risk', 'position_manager',
    'Daily loss limit exceeded: $525.00 / $500.00 limit',
    '{"current_loss": 525.00, "limit": 500.00, "breaker_type": "daily_loss_limit"}',
    '{"email": true, "sms": true, "console": true, "file": true}',
    md5('circuit_breaker:position_manager:daily_loss_limit'),
    'demo'
);
```

### 6. Trading Methods (Phase 4-5 - PLACEHOLDERS)

**Note:** These tables are designed and specified in Phase 0.5 (ADR-021) but implementation is deferred to Phase 4-5 when strategy and model versioning systems are fully operational.

#### methods (PLACEHOLDER - Phase 4-5)
```sql
-- Designed in Phase 0.5 (ADR-021)
-- Implementation deferred to Phase 4-5
-- See ADR_021_METHOD_ABSTRACTION.md for complete specification

CREATE TABLE methods (
    method_id SERIAL PRIMARY KEY,

    -- Naming and Versioning (immutable once created)
    method_name VARCHAR NOT NULL,       -- 'conservative_nfl', 'aggressive_nba'
    method_version VARCHAR NOT NULL,    -- 'v1.0', 'v1.1', 'v2.0' (semantic versioning)

    -- Component References (immutable once created)
    strategy_id INT NOT NULL REFERENCES strategies(strategy_id),   -- Which strategy
    model_id INT NOT NULL REFERENCES probability_models(model_id), -- Which model

    -- Configuration (immutable once created)
    position_mgmt_config JSONB NOT NULL,  -- Position management rules
    risk_config JSONB NOT NULL,           -- Risk parameters (Kelly fraction, limits)
    execution_config JSONB NOT NULL,      -- Order execution settings
    sport_config JSONB NOT NULL,          -- Sport-specific overrides
    config_hash VARCHAR(64) NOT NULL,     -- MD5 hash of all configs for comparison

    -- Lifecycle Management (mutable)
    status VARCHAR DEFAULT 'draft',       -- 'draft', 'testing', 'active', 'deprecated'
    activated_at TIMESTAMP,
    deactivated_at TIMESTAMP,

    -- Performance Metrics (mutable)
    paper_roi DECIMAL(10,4),              -- Paper trading ROI
    live_roi DECIMAL(10,4),               -- Live trading ROI
    sharpe_ratio DECIMAL(10,4),           -- Risk-adjusted return
    win_rate DECIMAL(6,4),                -- Percentage of winning trades
    total_trades INT DEFAULT 0,           -- Number of trades executed

    -- Documentation
    description TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR,

    -- Constraints
    UNIQUE(method_name, method_version)
);

-- Indexes (for Phase 4-5)
CREATE INDEX idx_methods_name ON methods(method_name);
CREATE INDEX idx_methods_status ON methods(status);
CREATE INDEX idx_methods_active ON methods(status) WHERE status = 'active';
CREATE INDEX idx_methods_strategy ON methods(strategy_id);
CREATE INDEX idx_methods_model ON methods(model_id);
CREATE INDEX idx_methods_hash ON methods(config_hash);
```

**Purpose:** Bundle complete trading approach (strategy + model + position management + risk)

**Why Deferred to Phase 4-5:**
- Requires mature strategy versioning system (Phase 2-3)
- Requires mature model versioning system (Phase 2-3)
- Requires extensive A/B testing infrastructure (Phase 4)
- Complex lifecycle management (activation criteria, validation)

**Database Changes Required (Phase 4-5):**
```sql
-- Add method_id to trades table (backward compatible)
ALTER TABLE trades ADD COLUMN method_id INT REFERENCES methods(method_id);
CREATE INDEX idx_trades_method ON trades(method_id);

-- Add method_id to edges table (backward compatible)
ALTER TABLE edges ADD COLUMN method_id INT REFERENCES methods(method_id);
CREATE INDEX idx_edges_method ON edges(method_id);
```

#### method_templates (PLACEHOLDER - Phase 4-5)
```sql
CREATE TABLE method_templates (
    template_id SERIAL PRIMARY KEY,
    template_name VARCHAR NOT NULL UNIQUE,  -- 'conservative', 'moderate', 'aggressive'
    description TEXT,
    position_mgmt_config JSONB NOT NULL,
    risk_config JSONB NOT NULL,
    execution_config JSONB NOT NULL,
    sport_config JSONB,                     -- Optional sport-specific defaults
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Purpose:** Reusable method templates as starting points

**Example Templates:**
- **conservative**: Small Kelly (0.15), tight stops (-10%), low max position ($200)
- **moderate**: Medium Kelly (0.25), normal stops (-20%), medium max position ($500)
- **aggressive**: Large Kelly (0.35), wide stops (-30%), high max position ($1000)

**Usage (Phase 4-5):**
```sql
-- Create method from template
INSERT INTO methods (method_name, method_version, strategy_id, model_id, position_mgmt_config, ...)
SELECT
    'my_nfl_method',
    'v1.0',
    1,  -- strategy_id
    2,  -- model_id
    position_mgmt_config,
    risk_config,
    execution_config,
    sport_config
FROM method_templates
WHERE template_name = 'conservative';
```

### 7. Machine Learning Infrastructure (Phase 9 - PLACEHOLDERS)

**Note:** These tables are designed and specified now but implementation is deferred to Phase 9 when XGBoost/LSTM models are introduced. Elo (Phase 4-6) does NOT require feature storage - it calculates on-the-fly based on game results.

**Why Phase 9?**
- **Phase 1-6**: Use probability_matrices (lookup tables) and simple Elo/regression
- **Phase 9**: Add XGBoost/LSTM models that require historical feature engineering
- **Elo doesn't need features**: Elo ratings are recursive (update after each game)
- **ML models need features**: XGBoost needs pre-calculated stats (DVOA, EPA, SP+, team performance metrics)

#### feature_definitions (PLACEHOLDER - Phase 9)
```sql
-- Designed for Phase 9
-- Implementation deferred until XGBoost/LSTM models are introduced

CREATE TABLE feature_definitions (
    feature_id SERIAL PRIMARY KEY,

    -- Naming and Versioning (immutable once created)
    feature_name VARCHAR NOT NULL,          -- 'team_recent_win_pct', 'home_advantage_score'
    feature_version VARCHAR NOT NULL,       -- 'v1.0', 'v1.1' (versioning for calculation changes)

    -- Classification
    category VARCHAR NOT NULL,              -- 'team_stats', 'player_stats', 'market_derived'
    sport VARCHAR,                          -- 'nfl', 'nba', 'mlb', NULL for multi-sport

    -- Calculation Details
    calculation_method TEXT,                -- Human-readable description of calculation
    data_type VARCHAR NOT NULL,             -- 'float', 'int', 'boolean', 'categorical'
    unit VARCHAR,                           -- 'percentage', 'points', 'seconds', NULL

    -- Metadata
    description TEXT,                       -- Detailed description of what feature represents
    status VARCHAR DEFAULT 'active',        -- 'active', 'deprecated'
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR,

    -- Constraints
    UNIQUE(feature_name, feature_version)   -- Enforce unique versions per feature
);

CREATE INDEX idx_feature_definitions_name ON feature_definitions(feature_name);
CREATE INDEX idx_feature_definitions_sport ON feature_definitions(sport);
CREATE INDEX idx_feature_definitions_category ON feature_definitions(category);
CREATE INDEX idx_feature_definitions_active ON feature_definitions(status) WHERE status = 'active';
```

**Purpose:** Define and version feature calculations

**Immutable Version Pattern:**
- `feature_name` + `feature_version` = unique identifier
- Example: 'team_recent_win_pct' v1.0 (5-game window) vs v1.1 (10-game window)
- Versioning enables tracking which feature version was used for which model training

**Example Features:**
```sql
-- Team performance features
INSERT INTO feature_definitions (feature_name, feature_version, category, sport, calculation_method, data_type, unit, description)
VALUES
    ('team_recent_win_pct', 'v1.0', 'team_stats', 'nfl', 'Win percentage over last 5 games', 'float', 'percentage', 'Rolling 5-game win rate'),
    ('home_advantage_score', 'v1.0', 'team_stats', NULL, 'Historical win rate at home vs away', 'float', 'percentage', 'Difference in home vs away performance'),
    ('dvoa_offense', 'v1.0', 'team_stats', 'nfl', 'Football Outsiders DVOA offensive rating', 'float', 'percentage', 'Defense-adjusted Value Over Average for offense'),
    ('epa_per_play', 'v1.0', 'team_stats', 'nfl', 'Expected Points Added per play', 'float', 'points', 'Average EPA across all offensive plays');
```

#### features_historical (PLACEHOLDER - Phase 9)
```sql
-- Designed for Phase 9
-- Implementation deferred until XGBoost/LSTM models are introduced

CREATE TABLE features_historical (
    feature_record_id SERIAL PRIMARY KEY,

    -- Feature Reference
    feature_id INT NOT NULL REFERENCES feature_definitions(feature_id),

    -- Entity Reference (what this feature describes)
    entity_type VARCHAR NOT NULL,           -- 'team', 'player', 'market', 'game'
    entity_id VARCHAR NOT NULL,             -- team_id, player_id, market_id, game_id

    -- Time-Series Data
    timestamp TIMESTAMP NOT NULL,           -- Point-in-time when feature was calculated
    feature_value DECIMAL(12,6),            -- The actual feature value (NULL if not applicable)

    -- Metadata
    metadata JSONB,                         -- Additional context (data_sources, confidence, etc.)
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX idx_features_historical_lookup ON features_historical(feature_id, entity_id, timestamp);
CREATE INDEX idx_features_historical_entity ON features_historical(entity_type, entity_id);
CREATE INDEX idx_features_historical_timestamp ON features_historical(timestamp);
CREATE INDEX idx_features_historical_feature ON features_historical(feature_id);
```

**Purpose:** Store time-series feature values for model training and backtesting

**Why Time-Series?**
- Features change over time (team performance evolves during season)
- Need historical values for backtesting: "What was team A's win % on 2024-10-15?"
- Enable training on historical snapshots

**Example Data:**
```sql
-- Store team win percentage over time
INSERT INTO features_historical (feature_id, entity_type, entity_id, timestamp, feature_value)
VALUES
    (1, 'team', 'KC', '2024-10-01', 0.8000),  -- Kansas City 80% win rate on Oct 1
    (1, 'team', 'KC', '2024-10-15', 0.7500),  -- Kansas City 75% win rate on Oct 15
    (2, 'team', 'KC', '2024-10-01', 0.6500);  -- Kansas City home advantage 65% on Oct 1
```

**Query Pattern:**
```sql
-- Get all features for a team at a specific point in time
SELECT
    fd.feature_name,
    fh.feature_value,
    fh.timestamp
FROM features_historical fh
JOIN feature_definitions fd ON fh.feature_id = fd.feature_id
WHERE fh.entity_type = 'team'
  AND fh.entity_id = 'KC'
  AND fh.timestamp <= '2024-10-15'
ORDER BY fd.feature_name, fh.timestamp DESC;
```

#### training_datasets (PLACEHOLDER - Phase 9)
```sql
-- Designed for Phase 9
-- Implementation deferred until XGBoost/LSTM models are introduced

CREATE TABLE training_datasets (
    dataset_id SERIAL PRIMARY KEY,

    -- Dataset Naming
    dataset_name VARCHAR NOT NULL,          -- 'nfl_2024_q4', 'nba_2023_season'
    sport VARCHAR NOT NULL,                 -- 'nfl', 'nba', 'mlb'

    -- Model Type
    model_type VARCHAR,                     -- 'classification', 'regression', 'ranking'
    label_type VARCHAR NOT NULL,            -- 'win_loss', 'score_differential', 'probability'

    -- Data Range
    start_date TIMESTAMP NOT NULL,          -- Data range start
    end_date TIMESTAMP NOT NULL,            -- Data range end
    feature_snapshot_date TIMESTAMP,        -- When features were extracted

    -- Dataset Details
    sample_count INT,                       -- Number of training examples
    feature_ids JSONB,                      -- Array of feature_ids used: [1, 2, 5, 7]
    feature_count INT,                      -- Number of features

    -- Train/Test Split
    train_test_split JSONB,                 -- {'train': 0.8, 'val': 0.1, 'test': 0.1}

    -- Storage
    storage_path VARCHAR,                   -- Path to parquet/csv file (if exported)
    checksum VARCHAR,                       -- MD5 for integrity verification
    file_size_mb DECIMAL(10,2),             -- File size for tracking

    -- Metadata
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR
);

CREATE INDEX idx_training_datasets_sport ON training_datasets(sport);
CREATE INDEX idx_training_datasets_dates ON training_datasets(start_date, end_date);
CREATE INDEX idx_training_datasets_model_type ON training_datasets(model_type);
```

**Purpose:** Organize and version training datasets with feature snapshots

**Why Needed?**
- Reproducibility: Recreate exact dataset used for model v1.0
- Train/Val/Test consistency: Same split across experiments
- Feature tracking: Which features were in which dataset

**Example Dataset:**
```sql
INSERT INTO training_datasets (
    dataset_name, sport, model_type, label_type,
    start_date, end_date, feature_snapshot_date,
    sample_count, feature_ids, feature_count,
    train_test_split, description
)
VALUES (
    'nfl_2024_halftime_predictor',
    'nfl',
    'classification',
    'win_loss',
    '2024-09-01',
    '2024-12-31',
    '2024-12-31',
    500,
    '[1, 2, 3, 5, 7]'::jsonb,
    5,
    '{"train": 0.8, "val": 0.1, "test": 0.1}'::jsonb,
    'NFL 2024 season - predict game winner from halftime stats'
);
```

#### model_training_runs (PLACEHOLDER - Phase 9)
```sql
-- Designed for Phase 9
-- Implementation deferred until XGBoost/LSTM models are introduced

CREATE TABLE model_training_runs (
    run_id SERIAL PRIMARY KEY,

    -- Model Reference
    model_id INT REFERENCES probability_models(model_id),  -- Which model was trained
    dataset_id INT REFERENCES training_datasets(dataset_id), -- Which dataset was used

    -- Training Details
    training_started_at TIMESTAMP,
    training_completed_at TIMESTAMP,
    training_duration_seconds INT,

    -- Hyperparameters
    hyperparameters JSONB NOT NULL,         -- Model-specific hyperparameters

    -- Metrics
    metrics JSONB,                          -- {'accuracy': 0.72, 'auc': 0.78, 'calibration': 0.85, 'brier_score': 0.15}
    train_metrics JSONB,                    -- Metrics on training set
    val_metrics JSONB,                      -- Metrics on validation set
    test_metrics JSONB,                     -- Metrics on test set

    -- Feature Analysis
    feature_importance JSONB,               -- Which features mattered most

    -- Infrastructure
    hardware_specs JSONB,                   -- {'gpu': 'NVIDIA RTX 3090', 'cpu': 'AMD Ryzen 9', 'ram_gb': 64}
    framework_version VARCHAR,              -- 'xgboost==2.0.3', 'pytorch==2.1.1'

    -- Status
    status VARCHAR DEFAULT 'running',       -- 'running', 'completed', 'failed', 'cancelled'
    error_message TEXT,                     -- If status = 'failed'

    -- Metadata
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR
);

CREATE INDEX idx_model_training_runs_model ON model_training_runs(model_id);
CREATE INDEX idx_model_training_runs_dataset ON model_training_runs(dataset_id);
CREATE INDEX idx_model_training_runs_status ON model_training_runs(status);
CREATE INDEX idx_model_training_runs_started ON model_training_runs(training_started_at DESC);
```

**Purpose:** Track ML training experiments with hyperparameters and metrics

**Why Needed?**
- Experiment tracking: Compare hyperparameter tuning runs
- Reproducibility: Recreate exact training run for model v1.0
- Performance analysis: Which hyperparameters worked best
- A/B testing: Statistical comparison of model versions

**Example Training Run:**
```sql
INSERT INTO model_training_runs (
    model_id, dataset_id,
    training_started_at, training_completed_at, training_duration_seconds,
    hyperparameters,
    metrics,
    feature_importance,
    status
)
VALUES (
    1,  -- elo_nfl v1.0
    1,  -- nfl_2024_halftime_predictor
    '2024-10-24 10:00:00',
    '2024-10-24 10:15:00',
    900,
    '{"learning_rate": 0.1, "max_depth": 6, "n_estimators": 100}'::jsonb,
    '{"accuracy": 0.72, "auc": 0.78, "calibration": 0.85}'::jsonb,
    '{"team_recent_win_pct": 0.35, "home_advantage_score": 0.25, "dvoa_offense": 0.20}'::jsonb,
    'completed'
);
```

**Query Pattern:**
```sql
-- Compare training runs for same model
SELECT
    run_id,
    training_duration_seconds,
    hyperparameters->>'learning_rate' as learning_rate,
    metrics->>'accuracy' as accuracy,
    metrics->>'auc' as auc
FROM model_training_runs
WHERE model_id = 1
ORDER BY metrics->>'accuracy' DESC;
```

**Implementation Timeline:**
- **Phase 4**: Implement Elo (no features needed)
- **Phase 6**: Extend Elo to more sports (no features needed)
- **Phase 9**: Implement XGBoost/LSTM → Create these 4 tables
- **Phase 9**: Populate features_historical with DVOA, EPA, SP+
- **Phase 9**: Train first ML model using training_datasets

## Helper Views (NEW in v1.4)

### active_strategies
```sql
CREATE VIEW active_strategies AS
SELECT * FROM strategies
WHERE status = 'active'
ORDER BY strategy_name, strategy_version DESC;
```
**Purpose:** Quick lookup of currently active strategy versions

### active_models
```sql
CREATE VIEW active_models AS
SELECT * FROM probability_models
WHERE status = 'active'
ORDER BY model_name, model_version DESC;
```
**Purpose:** Quick lookup of currently active model versions

### trade_attribution
```sql
CREATE VIEW trade_attribution AS
SELECT
    t.trade_id,
    t.created_at,
    t.side,
    t.price,
    t.quantity,
    m.ticker as market_ticker,
    s.strategy_name,
    s.strategy_version,
    s.config as strategy_config,
    pm.model_name,
    pm.model_version,
    pm.config as model_config,
    t.edge_at_execution,
    t.confidence_at_execution
FROM trades t
JOIN markets m ON t.market_id = m.market_id
LEFT JOIN strategies s ON t.strategy_id = s.strategy_id
LEFT JOIN probability_models pm ON t.model_id = pm.model_id
ORDER BY t.created_at DESC;
```
**Purpose:** Complete trade attribution showing EXACT strategy and model versions used

## Relationships Diagram (Updated for v1.4)

```
platforms (1) -----> (N) series (1) -----> (N) events (1) -----> (N) markets
    |                                           |                      |
    |                                           |                      +---> (N) edges (N) <--- (1) probability_matrices
    |                                           |                      |           |
    |                                           |                      |           +--- (1) probability_models (NEW)
    |                                           |                      |           |
    |                                           |                      |           +--- (1) strategies (NEW)
    |                                           |                      |           |
    |                                           |                      |           +---> (N) trades
    |                                           +---> (1) game_states  |
    |                                                                  |
    +-----------> (N) positions <------------------------------------ +
                       |
                       +---> (N) trades -----> (1) strategies (NEW)
                                        |
                                        +-----> (1) probability_models (NEW)

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

### Get Position P&L (with Trailing Stop State)
```sql
SELECT p.*,
       SUM(t.quantity * t.price) as total_cost,
       p.quantity * m.yes_price - total_cost as unrealized_pnl,
       p.trailing_stop_state->>'enabled' as trailing_stop_enabled,
       p.trailing_stop_state->>'current_stop' as current_stop_price
FROM positions p
JOIN trades t ON p.position_id = t.position_id
JOIN markets m ON p.market_id = m.market_id AND m.row_current_ind = TRUE
WHERE p.row_current_ind = TRUE AND p.status = 'open'
GROUP BY p.position_id;
```

### Trade Attribution - Show Exact Versions Used (NEW in v1.4)
```sql
SELECT * FROM trade_attribution
WHERE created_at >= NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;
```

### A/B Test Strategy Versions (NEW in v1.4)
```sql
SELECT
    s.strategy_name,
    s.strategy_version,
    s.config,
    COUNT(t.trade_id) as trades,
    AVG(t.price) as avg_price,
    s.paper_roi
FROM strategies s
LEFT JOIN trades t ON s.strategy_id = t.strategy_id
WHERE s.strategy_name = 'halftime_entry'
GROUP BY s.strategy_id
ORDER BY s.strategy_version DESC;
```

### Compare Model Performance (NEW in v1.4)
```sql
SELECT
    pm.model_name,
    pm.model_version,
    pm.validation_accuracy,
    pm.validation_calibration,
    COUNT(t.trade_id) as live_trades
FROM probability_models pm
LEFT JOIN trades t ON pm.model_id = t.model_id
WHERE pm.model_name = 'elo_nfl'
GROUP BY pm.model_id
ORDER BY pm.model_version DESC;
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
- **Strategies:** ~100 versions/year × 500 bytes = 50 KB (NEW in v1.4)
- **Probability Models:** ~50 versions/year × 500 bytes = 25 KB (NEW in v1.4)
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

**Versioning vs. Versions:**
- **Versioning (row_current_ind)**: Track changes to MUTABLE data (markets, positions, game_states)
- **Versions (version field)**: IMMUTABLE configs for strategies and models (v1.0, v1.1, v2.0)

---
**Document Version:** 1.4
**Last Updated:** October 19, 2025
**Purpose:** Database schema reference for development and troubleshooting

## Schema Enhancements in v1.4

### CRITICAL: Immutable Version Tables

**NEW TABLES for versioning:**
- `strategies` - Trading strategy versions with IMMUTABLE configs
- `probability_models` - ML model versions with IMMUTABLE configs

**Immutable Version Pattern:**
- Config/parameters are IMMUTABLE once version is created
- To change config: Create new version (v1.0 → v1.1 for bug fix, v1.0 → v2.0 for major change)
- Status field is MUTABLE (lifecycle transitions)
- Metrics are MUTABLE (performance tracking)
- NO `row_current_ind` (not needed - versions don't supersede each other)

**Why Immutable Versions?**
- **A/B Testing Integrity**: Can compare v1.0 vs v2.0 knowing configs never changed
- **Trade Attribution**: Know EXACTLY which strategy/model config generated each trade
- **Semantic Versioning**: v1.0 → v1.1 (bug fix), v1.0 → v2.0 (major change)

**What's Mutable:**
- `status` field (draft → testing → active → deprecated)
- Performance metrics (paper_roi, live_roi, validation_accuracy)

**What's Immutable:**
- `config` field (strategy parameters, model hyperparameters)
- `version` field (version number)

### Trade Attribution Links (NEW in v1.4)

**NEW FOREIGN KEYS:**
- `edges.strategy_id` → `strategies.strategy_id`
- `edges.model_id` → `probability_models.model_id`
- `trades.strategy_id` → `strategies.strategy_id`
- `trades.model_id` → `probability_models.model_id`

**Purpose:**
- Link every trade to EXACT strategy version and model version used
- Enable precise performance analysis and A/B testing
- Historical trade attribution never changes (versions are immutable)

### Trailing Stop Loss Support (NEW in v1.4)

**NEW COLUMN:**
- `positions.trailing_stop_state` (JSONB)

**Structure:**
```json
{
  "enabled": true,
  "activation_price": 0.7500,
  "stop_distance": 0.0500,
  "current_stop": 0.7000,
  "highest_price": 0.7500
}
```

**Updates:**
- As market price rises, highest_price and current_stop update
- Triggers new position row (row_current_ind pattern)
- Enables dynamic stop loss management

### Helper Views (NEW in v1.4)

- `active_strategies` - Currently active strategy versions
- `active_models` - Currently active model versions
- `trade_attribution` - Complete trade attribution with exact versions

### CRITICAL: DECIMAL Precision (from v1.3)
**ALL price and probability fields use DECIMAL(10,4)** for exact precision:
- Prevents floating-point rounding errors in financial calculations
- Range: 0.0000 to 1.0000 (exact to 4 decimal places)
- Examples: 0.8950, 0.0001, 1.0000

### Data Validation (CHECK Constraints from v1.3)
- Probabilities constrained to 0.0000-1.0000 range
- Prices constrained to 0.0000-1.0000 range
- Non-negative constraints on volumes, quantities, balances
- Status fields constrained to valid enums

### Referential Integrity (ON DELETE CASCADE from v1.3)
- Cascading deletes prevent orphaned records
- Example: Deleting a platform cascades to markets, trades, etc.

### Helper Views from v1.3
- `current_markets`: Only current market data (row_current_ind=TRUE)
- `current_game_states`: Only current game states
- `current_edges`: Only current edges
- `open_positions`: Only open positions
- `current_balances`: Only current account balances

---
**Document Version:** 1.4
**Last Updated:** October 19, 2025
**Purpose:** Database schema reference for development and troubleshooting
