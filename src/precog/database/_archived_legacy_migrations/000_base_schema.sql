-- Precog Database Schema (Enhanced)
-- Version: 1.1
-- Date: 2025-10-17
-- PostgreSQL 15+
--
-- ENHANCEMENTS FROM V1.0:
-- - CHECK constraints for data validation
-- - ON DELETE CASCADE for referential integrity
-- - Range validations for probabilities (0-1) and prices (0-1)
-- - Non-negative constraints for volumes, quantities, balances
--
-- CRITICAL: ALL PRICES USE DECIMAL(10,4) - NEVER FLOAT
-- See: MASTER_REQUIREMENTS_V2.3.md, KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md

-- ============================================================================
-- 1. PLATFORM & MARKET HIERARCHY
-- ============================================================================

-- Platforms (Kalshi, Polymarket, ESPN, etc.)
CREATE TABLE platforms (
    platform_id VARCHAR(50) PRIMARY KEY,
    platform_type VARCHAR(50) NOT NULL CHECK (platform_type IN ('trading', 'data_source', 'hybrid')),
    display_name VARCHAR(100) NOT NULL,
    base_url VARCHAR(255),
    websocket_url VARCHAR(255),
    api_version VARCHAR(20),
    auth_method VARCHAR(50) CHECK (auth_method IN ('rsa_pss', 'api_key', 'oauth', 'metamask', 'none')),
    fees_structure JSONB,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'maintenance')),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Series (recurring event groups)
CREATE TABLE series (
    series_id VARCHAR(100) PRIMARY KEY,
    platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
    external_id VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL CHECK (category IN ('sports', 'politics', 'entertainment', 'economics', 'weather', 'other')),
    subcategory VARCHAR(50),
    title VARCHAR(255) NOT NULL,
    frequency VARCHAR(20) CHECK (frequency IN ('daily', 'weekly', 'monthly', 'event', 'once')),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_series_platform ON series(platform_id);
CREATE INDEX idx_series_category ON series(category, subcategory);

-- Events (specific games, elections, etc.)
CREATE TABLE events (
    event_id VARCHAR(100) PRIMARY KEY,
    platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
    series_id VARCHAR(100) REFERENCES series(series_id) ON DELETE SET NULL,
    external_id VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL CHECK (category IN ('sports', 'politics', 'entertainment', 'economics', 'weather', 'other')),
    subcategory VARCHAR(50),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    status VARCHAR(20) CHECK (status IN ('scheduled', 'live', 'final', 'cancelled', 'postponed')),
    result JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT event_time_order CHECK (end_time IS NULL OR start_time IS NULL OR end_time >= start_time)
);

CREATE INDEX idx_events_platform ON events(platform_id);
CREATE INDEX idx_events_series ON events(series_id);
CREATE INDEX idx_events_status ON events(status);
CREATE INDEX idx_events_start_time ON events(start_time);

-- Markets (prediction markets on events)
-- VERSIONED TABLE: row_current_ind for SCD Type 2
CREATE TABLE markets (
    market_id VARCHAR(100) PRIMARY KEY,
    platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
    event_id VARCHAR(100) REFERENCES events(event_id) ON DELETE CASCADE,
    external_id VARCHAR(100) NOT NULL,
    ticker VARCHAR(50),
    title VARCHAR(255) NOT NULL,
    market_type VARCHAR(20) CHECK (market_type IN ('binary', 'categorical', 'scalar')),
    -- CRITICAL: ALL PRICES AS DECIMAL(10,4) with range validation
    yes_price DECIMAL(10,4) CHECK (yes_price IS NULL OR (yes_price >= 0.0000 AND yes_price <= 1.0000)),
    no_price DECIMAL(10,4) CHECK (no_price IS NULL OR (no_price >= 0.0000 AND no_price <= 1.0000)),
    volume INTEGER CHECK (volume IS NULL OR volume >= 0),
    open_interest INTEGER CHECK (open_interest IS NULL OR open_interest >= 0),
    spread DECIMAL(10,4) CHECK (spread IS NULL OR (spread >= 0.0000 AND spread <= 1.0000)),
    status VARCHAR(20) CHECK (status IN ('open', 'closed', 'settled', 'halted')),
    settlement_value DECIMAL(10,4) CHECK (settlement_value IS NULL OR (settlement_value >= 0.0000 AND settlement_value <= 1.0000)),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_markets_event ON markets(event_id);
CREATE INDEX idx_markets_platform ON markets(platform_id);
CREATE INDEX idx_markets_current ON markets(row_current_ind) WHERE row_current_ind = TRUE;
CREATE INDEX idx_markets_status ON markets(status);

-- ============================================================================
-- 2. LIVE GAME DATA
-- ============================================================================

-- Game States (live scores, period, possession)
-- VERSIONED TABLE: row_current_ind for SCD Type 2
CREATE TABLE game_states (
    game_state_id SERIAL PRIMARY KEY,
    event_id VARCHAR(100) REFERENCES events(event_id) ON DELETE CASCADE,
    external_game_id VARCHAR(100),
    sport VARCHAR(20) NOT NULL CHECK (sport IN ('nfl', 'nba', 'mlb', 'nhl', 'tennis', 'ufc', 'soccer')),
    home_team VARCHAR(100),
    away_team VARCHAR(100),
    home_score INTEGER CHECK (home_score IS NULL OR home_score >= 0),
    away_score INTEGER CHECK (away_score IS NULL OR away_score >= 0),
    period VARCHAR(20),
    time_remaining VARCHAR(20),
    possession VARCHAR(10) CHECK (possession IS NULL OR possession IN ('home', 'away')),
    status VARCHAR(20) CHECK (status IN ('scheduled', 'pregame', 'live', 'halftime', 'final', 'cancelled')),
    sport_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_game_states_event ON game_states(event_id);
CREATE INDEX idx_game_states_sport ON game_states(sport);
CREATE INDEX idx_game_states_current ON game_states(row_current_ind) WHERE row_current_ind = TRUE;

-- ============================================================================
-- 3. PROBABILITY & EDGE DETECTION
-- ============================================================================

-- Probability Matrices (historical win probabilities)
CREATE TABLE probability_matrices (
    probability_id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL CHECK (category IN ('sports', 'politics', 'entertainment', 'economics', 'weather', 'other')),
    subcategory VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    state_descriptor VARCHAR(100) NOT NULL,
    value_bucket VARCHAR(100) NOT NULL,
    situational_factors JSONB,
    -- CRITICAL: Probabilities as DECIMAL(10,4) with strict 0-1 range
    win_probability DECIMAL(10,4) NOT NULL CHECK (win_probability >= 0.0000 AND win_probability <= 1.0000),
    confidence_interval_lower DECIMAL(10,4) CHECK (confidence_interval_lower IS NULL OR (confidence_interval_lower >= 0.0000 AND confidence_interval_lower <= 1.0000)),
    confidence_interval_upper DECIMAL(10,4) CHECK (confidence_interval_upper IS NULL OR (confidence_interval_upper >= 0.0000 AND confidence_interval_upper <= 1.0000)),
    sample_size INTEGER CHECK (sample_size IS NULL OR sample_size >= 0),
    source VARCHAR(100),
    methodology TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT ci_order CHECK (confidence_interval_lower IS NULL OR confidence_interval_upper IS NULL OR confidence_interval_lower <= confidence_interval_upper)
);

CREATE INDEX idx_probability_lookup ON probability_matrices(category, subcategory, version, state_descriptor, value_bucket);

-- Edges (EV+ opportunities)
-- VERSIONED TABLE: row_current_ind for SCD Type 2
CREATE TABLE edges (
    edge_id SERIAL PRIMARY KEY,
    market_id VARCHAR(100) REFERENCES markets(market_id) ON DELETE CASCADE,
    probability_matrix_id INTEGER REFERENCES probability_matrices(probability_id) ON DELETE SET NULL,
    -- CRITICAL: ALL edge calculations as DECIMAL(10,4)
    expected_value DECIMAL(10,4) NOT NULL,
    true_win_probability DECIMAL(10,4) NOT NULL CHECK (true_win_probability >= 0.0000 AND true_win_probability <= 1.0000),
    market_implied_probability DECIMAL(10,4) NOT NULL CHECK (market_implied_probability >= 0.0000 AND market_implied_probability <= 1.0000),
    market_price DECIMAL(10,4) NOT NULL CHECK (market_price >= 0.0000 AND market_price <= 1.0000),
    confidence_level VARCHAR(20) CHECK (confidence_level IN ('high', 'medium', 'low')),
    confidence_metrics JSONB,
    recommended_action VARCHAR(50) CHECK (recommended_action IN ('auto_execute', 'alert', 'ignore')),
    created_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_edges_market ON edges(market_id);
CREATE INDEX idx_edges_probability ON edges(probability_matrix_id);
CREATE INDEX idx_edges_ev ON edges(expected_value) WHERE row_current_ind = TRUE;
CREATE INDEX idx_edges_current ON edges(row_current_ind) WHERE row_current_ind = TRUE;

-- ============================================================================
-- 4. TRADING & POSITIONS
-- ============================================================================

-- Positions (open positions)
-- VERSIONED TABLE: row_current_ind for quantity changes
CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,
    market_id VARCHAR(100) REFERENCES markets(market_id) ON DELETE CASCADE,
    platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
    side VARCHAR(10) NOT NULL CHECK (side IN ('yes', 'no', 'long', 'short')),
    -- CRITICAL: Prices as DECIMAL(10,4)
    entry_price DECIMAL(10,4) NOT NULL CHECK (entry_price >= 0.0000 AND entry_price <= 1.0000),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    fees DECIMAL(10,4) CHECK (fees IS NULL OR fees >= 0.0000),
    status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'closed', 'settled')),
    unrealized_pnl DECIMAL(10,4),
    realized_pnl DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_positions_market ON positions(market_id);
CREATE INDEX idx_positions_platform ON positions(platform_id);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_current ON positions(row_current_ind) WHERE row_current_ind = TRUE;

-- Trades (executed orders - IMMUTABLE)
-- APPEND-ONLY: No row_current_ind
CREATE TABLE trades (
    trade_id SERIAL PRIMARY KEY,
    market_id VARCHAR(100) REFERENCES markets(market_id) ON DELETE CASCADE,
    platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
    position_id INTEGER REFERENCES positions(position_id) ON DELETE SET NULL,
    edge_id INTEGER REFERENCES edges(edge_id) ON DELETE SET NULL,
    order_id VARCHAR(100),
    side VARCHAR(10) NOT NULL CHECK (side IN ('buy', 'sell')),
    -- CRITICAL: Prices as DECIMAL(10,4)
    price DECIMAL(10,4) NOT NULL CHECK (price >= 0.0000 AND price <= 1.0000),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    fees DECIMAL(10,4) CHECK (fees IS NULL OR fees >= 0.0000),
    edge_at_execution DECIMAL(10,4),
    confidence_at_execution VARCHAR(20) CHECK (confidence_at_execution IN ('high', 'medium', 'low')),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_trades_market ON trades(market_id);
CREATE INDEX idx_trades_platform ON trades(platform_id);
CREATE INDEX idx_trades_position ON trades(position_id);
CREATE INDEX idx_trades_edge ON trades(edge_id);
CREATE INDEX idx_trades_created ON trades(created_at);

-- Settlements (final market outcomes - IMMUTABLE)
-- APPEND-ONLY: No row_current_ind
CREATE TABLE settlements (
    settlement_id SERIAL PRIMARY KEY,
    market_id VARCHAR(100) REFERENCES markets(market_id) ON DELETE CASCADE,
    platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
    outcome VARCHAR(50) NOT NULL,
    -- CRITICAL: Payout as DECIMAL(10,4)
    payout DECIMAL(10,4) CHECK (payout IS NULL OR payout >= 0.0000),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_settlements_market ON settlements(market_id);
CREATE INDEX idx_settlements_platform ON settlements(platform_id);

-- Account Balance
-- VERSIONED TABLE: row_current_ind for balance changes
CREATE TABLE account_balance (
    balance_id SERIAL PRIMARY KEY,
    platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
    -- CRITICAL: Balance as DECIMAL(10,4)
    balance DECIMAL(10,4) NOT NULL CHECK (balance >= 0.0000),
    currency VARCHAR(10) DEFAULT 'USD',
    created_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_balance_platform ON account_balance(platform_id);
CREATE INDEX idx_balance_current ON account_balance(row_current_ind) WHERE row_current_ind = TRUE;

-- ============================================================================
-- 5. CONFIGURATION & STATE
-- ============================================================================

-- Config Overrides (database-level configuration overrides)
CREATE TABLE config_overrides (
    override_id SERIAL PRIMARY KEY,
    config_key VARCHAR(255) NOT NULL,
    override_value JSONB NOT NULL,
    data_type VARCHAR(20) CHECK (data_type IN ('float', 'int', 'bool', 'string', 'json')),
    reason TEXT,
    applied_by VARCHAR(100),
    applied_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    active BOOLEAN DEFAULT TRUE,
    CONSTRAINT expiry_after_applied CHECK (expires_at IS NULL OR expires_at >= applied_at)
);

CREATE INDEX idx_config_overrides_key ON config_overrides(config_key);
CREATE INDEX idx_config_overrides_active ON config_overrides(active) WHERE active = TRUE;

-- Circuit Breaker Events (system safety events)
CREATE TABLE circuit_breaker_events (
    event_id SERIAL PRIMARY KEY,
    breaker_type VARCHAR(50) NOT NULL CHECK (breaker_type IN ('daily_loss_limit', 'api_failures', 'data_stale', 'position_limit', 'manual')),
    triggered_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    trigger_value JSONB,
    resolution_action VARCHAR(100),
    notes TEXT,
    CONSTRAINT resolution_after_trigger CHECK (resolved_at IS NULL OR resolved_at >= triggered_at)
);

CREATE INDEX idx_circuit_breaker_triggered ON circuit_breaker_events(triggered_at);
CREATE INDEX idx_circuit_breaker_type ON circuit_breaker_events(breaker_type);

-- System Health (component health monitoring)
CREATE TABLE system_health (
    health_id SERIAL PRIMARY KEY,
    component VARCHAR(50) NOT NULL CHECK (component IN ('kalshi_api', 'polymarket_api', 'espn_api', 'database', 'edge_detector', 'trading_engine', 'websocket')),
    status VARCHAR(20) NOT NULL CHECK (status IN ('healthy', 'degraded', 'down')),
    last_check TIMESTAMP DEFAULT NOW(),
    details JSONB,
    alert_sent BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_health_component ON system_health(component);
CREATE INDEX idx_health_status ON system_health(status);

-- ============================================================================
-- HELPER VIEWS FOR CURRENT DATA
-- ============================================================================

-- View for current markets only (no historical versions)
CREATE VIEW current_markets AS
SELECT * FROM markets WHERE row_current_ind = TRUE;

-- View for current game states only
CREATE VIEW current_game_states AS
SELECT * FROM game_states WHERE row_current_ind = TRUE;

-- View for current edges only
CREATE VIEW current_edges AS
SELECT * FROM edges WHERE row_current_ind = TRUE;

-- View for open positions only
CREATE VIEW open_positions AS
SELECT * FROM positions WHERE row_current_ind = TRUE AND status = 'open';

-- View for current account balances
CREATE VIEW current_balances AS
SELECT * FROM account_balance WHERE row_current_ind = TRUE;

-- ============================================================================
-- INITIAL DATA (Kalshi platform)
-- ============================================================================

INSERT INTO platforms (platform_id, platform_type, display_name, base_url, websocket_url, api_version, auth_method, status)
VALUES (
    'kalshi',
    'trading',
    'Kalshi',
    'https://demo-api.kalshi.co',
    'wss://demo-api.kalshi.co/trade-api/ws/v2',
    'v2',
    'rsa_pss',
    'active'
);

-- ============================================================================
-- PARTITIONING NOTES (For Future Scalability)
-- ============================================================================
-- When tables grow large (>10M rows), consider partitioning:
--
-- trades table by created_at (monthly partitions):
-- CREATE TABLE trades_2025_10 PARTITION OF trades
--     FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
--
-- game_states by created_at (daily partitions for high-freq data):
-- CREATE TABLE game_states_2025_10_17 PARTITION OF game_states
--     FOR VALUES FROM ('2025-10-17') TO ('2025-10-18');

-- ============================================================================
-- END OF ENHANCED SCHEMA
-- ============================================================================
