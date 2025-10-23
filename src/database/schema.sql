-- Precog Database Schema
-- Version: 1.0
-- Date: 2025-10-17
-- PostgreSQL 15+
--
-- CRITICAL: ALL PRICES USE DECIMAL(10,4) - NEVER FLOAT
-- See: MASTER_REQUIREMENTS_V2.3.md, KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md

-- ============================================================================
-- 1. PLATFORM & MARKET HIERARCHY
-- ============================================================================

-- Platforms (Kalshi, Polymarket, ESPN, etc.)
CREATE TABLE platforms (
    platform_id VARCHAR(50) PRIMARY KEY,
    platform_type VARCHAR(50) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    base_url VARCHAR(255),
    websocket_url VARCHAR(255),
    api_version VARCHAR(20),
    auth_method VARCHAR(50),
    fees_structure JSONB,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Series (recurring event groups)
CREATE TABLE series (
    series_id VARCHAR(100) PRIMARY KEY,
    platform_id VARCHAR(50) REFERENCES platforms(platform_id),
    external_id VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    subcategory VARCHAR(50),
    title VARCHAR(255) NOT NULL,
    frequency VARCHAR(20),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_series_platform ON series(platform_id);
CREATE INDEX idx_series_category ON series(category, subcategory);

-- Events (specific games, elections, etc.)
CREATE TABLE events (
    event_id VARCHAR(100) PRIMARY KEY,
    platform_id VARCHAR(50) REFERENCES platforms(platform_id),
    series_id VARCHAR(100) REFERENCES series(series_id),
    external_id VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    subcategory VARCHAR(50),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    status VARCHAR(20),
    result JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_events_platform ON events(platform_id);
CREATE INDEX idx_events_series ON events(series_id);
CREATE INDEX idx_events_status ON events(status);
CREATE INDEX idx_events_start_time ON events(start_time);

-- Markets (prediction markets on events)
-- VERSIONED TABLE: row_current_ind for SCD Type 2
CREATE TABLE markets (
    market_id VARCHAR(100) PRIMARY KEY,
    platform_id VARCHAR(50) REFERENCES platforms(platform_id),
    event_id VARCHAR(100) REFERENCES events(event_id),
    external_id VARCHAR(100) NOT NULL,
    ticker VARCHAR(50),
    title VARCHAR(255) NOT NULL,
    market_type VARCHAR(20),
    -- CRITICAL: ALL PRICES AS DECIMAL(10,4)
    yes_price DECIMAL(10,4),
    no_price DECIMAL(10,4),
    volume INTEGER,
    open_interest INTEGER,
    spread DECIMAL(10,4),
    status VARCHAR(20),
    settlement_value DECIMAL(10,4),
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
    event_id VARCHAR(100) REFERENCES events(event_id),
    external_game_id VARCHAR(100),
    sport VARCHAR(20) NOT NULL,
    home_team VARCHAR(100),
    away_team VARCHAR(100),
    home_score INTEGER,
    away_score INTEGER,
    period VARCHAR(20),
    time_remaining VARCHAR(20),
    possession VARCHAR(10),
    status VARCHAR(20),
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
    category VARCHAR(50) NOT NULL,
    subcategory VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    state_descriptor VARCHAR(100) NOT NULL,
    value_bucket VARCHAR(100) NOT NULL,
    situational_factors JSONB,
    -- CRITICAL: Probabilities as DECIMAL(10,4)
    win_probability DECIMAL(10,4) NOT NULL,
    confidence_interval_lower DECIMAL(10,4),
    confidence_interval_upper DECIMAL(10,4),
    sample_size INTEGER,
    source VARCHAR(100),
    methodology TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_probability_lookup ON probability_matrices(category, subcategory, version, state_descriptor, value_bucket);

-- Edges (EV+ opportunities)
-- VERSIONED TABLE: row_current_ind for SCD Type 2
CREATE TABLE edges (
    edge_id SERIAL PRIMARY KEY,
    market_id VARCHAR(100) REFERENCES markets(market_id),
    probability_matrix_id INTEGER REFERENCES probability_matrices(probability_id),
    -- CRITICAL: ALL edge calculations as DECIMAL(10,4)
    expected_value DECIMAL(10,4) NOT NULL,
    true_win_probability DECIMAL(10,4) NOT NULL,
    market_implied_probability DECIMAL(10,4) NOT NULL,
    market_price DECIMAL(10,4) NOT NULL,
    confidence_level VARCHAR(20),
    confidence_metrics JSONB,
    recommended_action VARCHAR(50),
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
    market_id VARCHAR(100) REFERENCES markets(market_id),
    platform_id VARCHAR(50) REFERENCES platforms(platform_id),
    side VARCHAR(10) NOT NULL,
    -- CRITICAL: Prices as DECIMAL(10,4)
    entry_price DECIMAL(10,4) NOT NULL,
    quantity INTEGER NOT NULL,
    fees DECIMAL(10,4),
    status VARCHAR(20) DEFAULT 'open',
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
    market_id VARCHAR(100) REFERENCES markets(market_id),
    platform_id VARCHAR(50) REFERENCES platforms(platform_id),
    position_id INTEGER REFERENCES positions(position_id),
    edge_id INTEGER REFERENCES edges(edge_id),
    order_id VARCHAR(100),
    side VARCHAR(10) NOT NULL,
    -- CRITICAL: Prices as DECIMAL(10,4)
    price DECIMAL(10,4) NOT NULL,
    quantity INTEGER NOT NULL,
    fees DECIMAL(10,4),
    edge_at_execution DECIMAL(10,4),
    confidence_at_execution VARCHAR(20),
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
    market_id VARCHAR(100) REFERENCES markets(market_id),
    platform_id VARCHAR(50) REFERENCES platforms(platform_id),
    outcome VARCHAR(50) NOT NULL,
    -- CRITICAL: Payout as DECIMAL(10,4)
    payout DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_settlements_market ON settlements(market_id);
CREATE INDEX idx_settlements_platform ON settlements(platform_id);

-- Account Balance
-- VERSIONED TABLE: row_current_ind for balance changes
CREATE TABLE account_balance (
    balance_id SERIAL PRIMARY KEY,
    platform_id VARCHAR(50) REFERENCES platforms(platform_id),
    -- CRITICAL: Balance as DECIMAL(10,4)
    balance DECIMAL(10,4) NOT NULL,
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
    data_type VARCHAR(20),
    reason TEXT,
    applied_by VARCHAR(100),
    applied_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_config_overrides_key ON config_overrides(config_key);
CREATE INDEX idx_config_overrides_active ON config_overrides(active) WHERE active = TRUE;

-- Circuit Breaker Events (system safety events)
CREATE TABLE circuit_breaker_events (
    event_id SERIAL PRIMARY KEY,
    breaker_type VARCHAR(50) NOT NULL,
    triggered_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    trigger_value JSONB,
    resolution_action VARCHAR(100),
    notes TEXT
);

CREATE INDEX idx_circuit_breaker_triggered ON circuit_breaker_events(triggered_at);

-- System Health (component health monitoring)
CREATE TABLE system_health (
    health_id SERIAL PRIMARY KEY,
    component VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    last_check TIMESTAMP DEFAULT NOW(),
    details JSONB,
    alert_sent BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_health_component ON system_health(component);
CREATE INDEX idx_health_status ON system_health(status);

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
-- END OF SCHEMA
-- ============================================================================
