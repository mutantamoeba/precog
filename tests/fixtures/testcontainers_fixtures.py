"""
Testcontainers PostgreSQL Fixtures for Property Tests.

Provides ephemeral PostgreSQL containers for database isolation in property tests.
This implements ADR-057: Testcontainers for Database Test Isolation.

Why Testcontainers?
    Property-based tests with Hypothesis generate 100+ test cases per test.
    Hypothesis caches examples in `.hypothesis/examples/` and replays them.
    When schema constraints change (e.g., season range 2020-2050), cached
    examples with old values (e.g., season=2099) cause test failures.

    Testcontainers provides TRUE isolation:
    - Fresh PostgreSQL container per test class
    - All migrations applied from scratch
    - No state leakage between tests
    - Reproducible CI/CD runs

Usage:
    @pytest.mark.usefixtures("postgres_container")
    class TestPropertyBasedCRUD:
        def test_some_property(self, db_connection):
            # Uses the containerized database
            ...

References:
    - ADR-057: Testcontainers for Database Test Isolation
    - TEST_ISOLATION_PATTERNS_V1.0.md
    - DATABASE_ENVIRONMENT_STRATEGY_V1.0.md
"""

import os
import sys
from collections.abc import Generator
from pathlib import Path

import psycopg2
import pytest
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


def _apply_migration_sql(connection: psycopg2.extensions.connection) -> None:
    """
    Apply the initial baseline schema migration directly via SQL.

    This runs the same SQL as Alembic migration 0001_initial_baseline_schema.py
    but without requiring the Alembic CLI infrastructure.

    Args:
        connection: Active PostgreSQL connection with autocommit enabled

    Educational Note:
        We apply migrations directly rather than using `alembic upgrade head`
        because testcontainers creates a fresh database on each run and we
        want to avoid the overhead of setting up Alembic config files and
        environment variables for each container.
    """
    # Read the migration file and extract SQL
    migration_path = (
        Path(__file__).parent.parent.parent
        / "src"
        / "precog"
        / "database"
        / "alembic"
        / "versions"
        / "0001_initial_baseline_schema.py"
    )

    if not migration_path.exists():
        raise FileNotFoundError(f"Migration file not found: {migration_path}")

    # Execute the migration upgrade function directly
    # Import and run the upgrade function from the migration module
    import importlib.util

    spec = importlib.util.spec_from_file_location("migration_0001", migration_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load migration module: {migration_path}")

    migration_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration_module)

    # The upgrade() function in the migration file uses op.execute()
    # We need to run it differently - extract SQL statements directly
    # For now, we'll execute the SQL directly

    cursor = connection.cursor()

    # Create alembic_version table to track migrations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alembic_version (
            version_num VARCHAR(32) NOT NULL,
            CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
        )
    """)

    # The full schema creation SQL (extracted from migration)
    schema_sql = """
    -- 1. PLATFORM & MARKET HIERARCHY
    CREATE TABLE IF NOT EXISTS platforms (
        platform_id VARCHAR(50) PRIMARY KEY,
        platform_type VARCHAR(50) NOT NULL CHECK (platform_type IN ('trading', 'data_source', 'hybrid')),
        display_name VARCHAR(100) NOT NULL,
        base_url VARCHAR(255),
        websocket_url VARCHAR(255),
        api_version VARCHAR(20),
        auth_method VARCHAR(50) CHECK (auth_method IN ('rsa_pss', 'api_key', 'oauth', 'metamask', 'none')),
        fees_structure JSONB,
        status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'maintenance')),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS series (
        series_id VARCHAR(100) PRIMARY KEY,
        platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
        external_id VARCHAR(100) NOT NULL,
        category VARCHAR(50) NOT NULL CHECK (category IN ('sports', 'politics', 'entertainment', 'economics', 'weather', 'other')),
        subcategory VARCHAR(50),
        title VARCHAR(255) NOT NULL,
        frequency VARCHAR(20) CHECK (frequency IN ('single', 'recurring', 'continuous')),
        metadata JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_series_platform ON series(platform_id);
    CREATE INDEX IF NOT EXISTS idx_series_category ON series(category, subcategory);

    CREATE TABLE IF NOT EXISTS events (
        event_id VARCHAR(100) PRIMARY KEY,
        platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
        series_id VARCHAR(100) REFERENCES series(series_id) ON DELETE SET NULL,
        external_id VARCHAR(100) NOT NULL,
        category VARCHAR(50) NOT NULL CHECK (category IN ('sports', 'politics', 'entertainment', 'economics', 'weather', 'other')),
        subcategory VARCHAR(50),
        title VARCHAR(255) NOT NULL,
        description TEXT,
        start_time TIMESTAMP WITH TIME ZONE,
        end_time TIMESTAMP WITH TIME ZONE,
        status VARCHAR(20) CHECK (status IN ('scheduled', 'live', 'final', 'cancelled', 'postponed')),
        result JSONB,
        metadata JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        CONSTRAINT event_time_order CHECK (end_time IS NULL OR start_time IS NULL OR end_time >= start_time)
    );
    CREATE INDEX IF NOT EXISTS idx_events_platform ON events(platform_id);
    CREATE INDEX IF NOT EXISTS idx_events_series ON events(series_id);
    CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
    CREATE INDEX IF NOT EXISTS idx_events_start_time ON events(start_time);

    -- markets table (SCD Type 2 with row_current_ind)
    CREATE TABLE IF NOT EXISTS markets (
        id SERIAL,
        market_id VARCHAR(100) NOT NULL,
        market_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
        platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
        event_id VARCHAR(100) REFERENCES events(event_id) ON DELETE CASCADE,
        external_id VARCHAR(100) NOT NULL,
        ticker VARCHAR(50),
        title VARCHAR(255) NOT NULL,
        market_type VARCHAR(20) CHECK (market_type IN ('binary', 'categorical', 'scalar')),
        yes_price DECIMAL(10,4) CHECK (yes_price IS NULL OR (yes_price >= 0.0000 AND yes_price <= 1.0000)),
        no_price DECIMAL(10,4) CHECK (no_price IS NULL OR (no_price >= 0.0000 AND no_price <= 1.0000)),
        volume INTEGER CHECK (volume IS NULL OR volume >= 0),
        open_interest INTEGER CHECK (open_interest IS NULL OR open_interest >= 0),
        spread DECIMAL(10,4) CHECK (spread IS NULL OR (spread >= 0.0000 AND spread <= 1.0000)),
        status VARCHAR(20) CHECK (status IN ('open', 'closed', 'settled', 'halted')),
        settlement_value DECIMAL(10,4) CHECK (settlement_value IS NULL OR (settlement_value >= 0.0000 AND settlement_value <= 1.0000)),
        metadata JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        row_start_ts TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        row_end_ts TIMESTAMP WITH TIME ZONE,
        row_current_ind BOOLEAN DEFAULT TRUE,
        PRIMARY KEY (id)
    );
    CREATE INDEX IF NOT EXISTS idx_markets_event ON markets(event_id);
    CREATE INDEX IF NOT EXISTS idx_markets_platform ON markets(platform_id);
    CREATE INDEX IF NOT EXISTS idx_markets_current ON markets(row_current_ind) WHERE row_current_ind = TRUE;
    CREATE INDEX IF NOT EXISTS idx_markets_status ON markets(status);
    CREATE INDEX IF NOT EXISTS idx_markets_market_id ON markets(market_id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_markets_unique_current ON markets(market_id) WHERE row_current_ind = TRUE;
    CREATE UNIQUE INDEX IF NOT EXISTS idx_markets_unique_ticker_current ON markets(ticker) WHERE row_current_ind = TRUE;
    -- Historical query index (migration 024)
    CREATE INDEX IF NOT EXISTS idx_markets_history ON markets(row_current_ind, created_at DESC);

    -- 2. TEAMS & SPORTS DATA
    CREATE TABLE IF NOT EXISTS teams (
        team_id SERIAL PRIMARY KEY,
        team_code VARCHAR(10) NOT NULL UNIQUE,
        team_name VARCHAR(100) NOT NULL,
        display_name VARCHAR(100),
        abbreviation VARCHAR(10),
        sport VARCHAR(20) NOT NULL CHECK (sport IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'wnba', 'mlb', 'soccer')),
        league VARCHAR(20) CHECK (league IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'wnba', 'mlb', 'soccer')),
        conference VARCHAR(50),
        division VARCHAR(50),
        espn_team_id VARCHAR(50),
        current_elo_rating DECIMAL(10,2) CHECK (current_elo_rating IS NULL OR current_elo_rating BETWEEN 0 AND 3000),
        external_ids JSONB,
        metadata JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_teams_code ON teams(team_code);
    CREATE INDEX IF NOT EXISTS idx_teams_sport ON teams(sport);
    CREATE INDEX IF NOT EXISTS idx_teams_league ON teams(league);
    CREATE INDEX IF NOT EXISTS idx_teams_espn_id ON teams(espn_team_id);
    CREATE INDEX IF NOT EXISTS idx_teams_elo_rating ON teams(current_elo_rating);

    CREATE TABLE IF NOT EXISTS elo_rating_history (
        rating_id SERIAL PRIMARY KEY,
        team_id INTEGER REFERENCES teams(team_id) ON DELETE CASCADE,
        rating DECIMAL(10,4) NOT NULL,
        rating_date DATE NOT NULL,
        season INTEGER,
        week INTEGER,
        opponent_id INTEGER REFERENCES teams(team_id),
        game_result VARCHAR(10) CHECK (game_result IN ('win', 'loss', 'tie')),
        rating_change DECIMAL(10,4),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_elo_team ON elo_rating_history(team_id);
    CREATE INDEX IF NOT EXISTS idx_elo_date ON elo_rating_history(rating_date);

    CREATE TABLE IF NOT EXISTS venues (
        venue_id SERIAL PRIMARY KEY,
        espn_venue_id VARCHAR(50) UNIQUE,
        venue_name VARCHAR(200) NOT NULL,
        city VARCHAR(100),
        state VARCHAR(50),
        country VARCHAR(50) DEFAULT 'USA',
        capacity INTEGER CHECK (capacity IS NULL OR capacity > 0),
        indoor BOOLEAN DEFAULT FALSE,
        surface VARCHAR(50),
        metadata JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_venues_espn_id ON venues(espn_venue_id);
    CREATE INDEX IF NOT EXISTS idx_venues_name ON venues(venue_name);

    CREATE TABLE IF NOT EXISTS team_rankings (
        ranking_id SERIAL PRIMARY KEY,
        team_id INTEGER REFERENCES teams(team_id) ON DELETE CASCADE,
        ranking_type VARCHAR(50) NOT NULL CHECK (ranking_type IN ('ap_poll', 'coaches_poll', 'cfp', 'committee', 'power_ranking')),
        rank INTEGER NOT NULL CHECK (rank > 0),
        season INTEGER NOT NULL CHECK (season >= 2020 AND season <= 2050),
        week INTEGER CHECK (week IS NULL OR (week >= 0 AND week <= 20)),
        ranking_date DATE,
        points INTEGER,
        first_place_votes INTEGER,
        previous_rank INTEGER,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        CONSTRAINT unique_team_ranking UNIQUE (team_id, ranking_type, season, week)
    );
    CREATE INDEX IF NOT EXISTS idx_rankings_type_season_week ON team_rankings(ranking_type, season, week);
    CREATE INDEX IF NOT EXISTS idx_rankings_team ON team_rankings(team_id);

    -- 3. GAME STATES (SCD Type 2)
    CREATE TABLE IF NOT EXISTS game_states (
        id SERIAL PRIMARY KEY,
        game_state_id VARCHAR(50) NOT NULL,
        espn_event_id VARCHAR(50) NOT NULL,
        home_team_id INTEGER REFERENCES teams(team_id),
        away_team_id INTEGER REFERENCES teams(team_id),
        venue_id INTEGER REFERENCES venues(venue_id),
        home_score INTEGER NOT NULL DEFAULT 0 CHECK (home_score >= 0),
        away_score INTEGER NOT NULL DEFAULT 0 CHECK (away_score >= 0),
        period INTEGER NOT NULL DEFAULT 0 CHECK (period >= 0),
        clock_seconds DECIMAL(10,2) CHECK (clock_seconds IS NULL OR clock_seconds >= 0),
        clock_display VARCHAR(20),
        game_status VARCHAR(50) NOT NULL CHECK (game_status IN (
            'pre', 'in_progress', 'halftime', 'end_of_period',
            'final', 'final_ot', 'delayed', 'postponed', 'cancelled', 'suspended'
        )),
        game_date TIMESTAMP WITH TIME ZONE,
        broadcast VARCHAR(100),
        neutral_site BOOLEAN DEFAULT FALSE NOT NULL,
        season_type VARCHAR(20) CHECK (season_type IS NULL OR season_type IN (
            'preseason', 'regular', 'playoff', 'bowl', 'allstar', 'exhibition'
        )),
        week_number INTEGER CHECK (week_number IS NULL OR (week_number >= 0 AND week_number <= 25)),
        league VARCHAR(20) NOT NULL CHECK (league IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'wnba')),
        situation JSONB,
        linescores JSONB,
        data_source VARCHAR(50) DEFAULT 'espn' NOT NULL,
        row_start_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
        row_end_timestamp TIMESTAMP WITH TIME ZONE,
        row_current_ind BOOLEAN DEFAULT TRUE NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_game_states_event ON game_states(espn_event_id);
    CREATE INDEX IF NOT EXISTS idx_game_states_current ON game_states(espn_event_id) WHERE row_current_ind = TRUE;
    CREATE UNIQUE INDEX IF NOT EXISTS idx_game_states_current_unique ON game_states(espn_event_id) WHERE row_current_ind = TRUE;
    CREATE INDEX IF NOT EXISTS idx_game_states_date ON game_states(game_date);
    CREATE INDEX IF NOT EXISTS idx_game_states_status ON game_states(game_status) WHERE row_current_ind = TRUE;
    CREATE INDEX IF NOT EXISTS idx_game_states_league ON game_states(league) WHERE row_current_ind = TRUE;
    CREATE INDEX IF NOT EXISTS idx_game_states_situation ON game_states USING GIN (situation);
    CREATE INDEX IF NOT EXISTS idx_game_states_teams ON game_states(home_team_id, away_team_id) WHERE row_current_ind = TRUE;
    CREATE INDEX IF NOT EXISTS idx_game_states_business_key ON game_states(game_state_id);

    -- 4. PROBABILITY & EDGE DETECTION
    CREATE TABLE IF NOT EXISTS probability_matrices (
        probability_id SERIAL PRIMARY KEY,
        category VARCHAR(50) NOT NULL CHECK (category IN ('sports', 'politics', 'entertainment', 'economics', 'weather', 'other')),
        subcategory VARCHAR(50) NOT NULL,
        version VARCHAR(20) NOT NULL,
        state_descriptor VARCHAR(100) NOT NULL,
        value_bucket VARCHAR(100) NOT NULL,
        situational_factors JSONB,
        win_probability DECIMAL(10,4) NOT NULL CHECK (win_probability >= 0.0000 AND win_probability <= 1.0000),
        confidence_interval_lower DECIMAL(10,4) CHECK (confidence_interval_lower IS NULL OR (confidence_interval_lower >= 0.0000 AND confidence_interval_lower <= 1.0000)),
        confidence_interval_upper DECIMAL(10,4) CHECK (confidence_interval_upper IS NULL OR (confidence_interval_upper >= 0.0000 AND confidence_interval_upper <= 1.0000)),
        sample_size INTEGER CHECK (sample_size IS NULL OR sample_size >= 0),
        source VARCHAR(100),
        methodology TEXT,
        matrix_name VARCHAR(100),
        description TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        CONSTRAINT ci_order CHECK (confidence_interval_lower IS NULL OR confidence_interval_upper IS NULL OR confidence_interval_lower <= confidence_interval_upper)
    );
    CREATE INDEX IF NOT EXISTS idx_probability_lookup ON probability_matrices(category, subcategory, version, state_descriptor, value_bucket);

    -- 5. LOOKUP TABLES
    CREATE TABLE IF NOT EXISTS strategy_types (
        strategy_type_code VARCHAR(50) PRIMARY KEY,
        display_name VARCHAR(100) NOT NULL,
        description TEXT,
        category VARCHAR(50) CHECK (category IN ('directional', 'arbitrage', 'risk_management', 'event_driven')),
        is_active BOOLEAN DEFAULT TRUE,
        display_order INTEGER DEFAULT 0,
        icon_name VARCHAR(50),
        help_text TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_strategy_types_active ON strategy_types(is_active) WHERE is_active = TRUE;
    CREATE INDEX IF NOT EXISTS idx_strategy_types_category ON strategy_types(category);
    -- Unique display_order constraint (migration 025)
    CREATE UNIQUE INDEX IF NOT EXISTS unique_strategy_types_display_order ON strategy_types(category, display_order) WHERE display_order IS NOT NULL;

    INSERT INTO strategy_types (strategy_type_code, display_name, description, category, display_order)
    VALUES
        ('value', 'Value', 'Exploit mispriced markets based on calculated true probability', 'directional', 1),
        ('arbitrage', 'Arbitrage', 'Risk-free profit from price discrepancies across markets', 'arbitrage', 2),
        ('momentum', 'Momentum', 'Follow price trends and market momentum', 'directional', 3),
        ('mean_reversion', 'Mean Reversion', 'Bet on prices returning to historical averages', 'directional', 4)
    ON CONFLICT (strategy_type_code) DO NOTHING;

    CREATE TABLE IF NOT EXISTS model_classes (
        model_class_code VARCHAR(50) PRIMARY KEY,
        display_name VARCHAR(100) NOT NULL,
        description TEXT,
        category VARCHAR(50) CHECK (category IN ('statistical', 'machine_learning', 'hybrid', 'baseline')),
        complexity_level VARCHAR(20) CHECK (complexity_level IN ('simple', 'moderate', 'advanced')),
        is_active BOOLEAN DEFAULT TRUE,
        display_order INTEGER DEFAULT 0,
        icon_name VARCHAR(50),
        help_text TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_model_classes_active ON model_classes(is_active) WHERE is_active = TRUE;
    CREATE INDEX IF NOT EXISTS idx_model_classes_category ON model_classes(category);
    -- Unique display_order constraint (migration 025)
    CREATE UNIQUE INDEX IF NOT EXISTS unique_model_classes_display_order ON model_classes(category, display_order) WHERE display_order IS NOT NULL;

    INSERT INTO model_classes (model_class_code, display_name, description, category, complexity_level, display_order)
    VALUES
        ('elo', 'Elo Rating', 'Classic Elo rating system for head-to-head predictions', 'statistical', 'simple', 1),
        ('ensemble', 'Ensemble', 'Combine multiple models for robust predictions', 'hybrid', 'moderate', 2),
        ('ml', 'Machine Learning', 'General ML models (XGBoost, Random Forest, etc.)', 'machine_learning', 'moderate', 3),
        ('hybrid', 'Hybrid', 'Combine statistical and ML approaches', 'hybrid', 'moderate', 4),
        ('regression', 'Regression', 'Linear and logistic regression models', 'statistical', 'simple', 5),
        ('neural_net', 'Neural Network', 'Deep learning models', 'machine_learning', 'advanced', 6),
        ('baseline', 'Baseline', 'Simple baseline models for comparison', 'baseline', 'simple', 7)
    ON CONFLICT (model_class_code) DO NOTHING;

    -- 6. STRATEGIES & PROBABILITY MODELS
    CREATE TABLE IF NOT EXISTS strategies (
        strategy_id SERIAL PRIMARY KEY,
        platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
        strategy_name VARCHAR(100) NOT NULL,
        strategy_version VARCHAR(20) NOT NULL DEFAULT '1.0',
        strategy_type VARCHAR(50) NOT NULL REFERENCES strategy_types(strategy_type_code),
        domain VARCHAR(50),
        config JSONB NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'draft'
            CHECK (status IN ('draft', 'testing', 'active', 'inactive', 'deprecated')),
        activated_at TIMESTAMP WITH TIME ZONE,
        deactivated_at TIMESTAMP WITH TIME ZONE,
        notes TEXT,
        paper_trades_count INTEGER DEFAULT 0 CHECK (paper_trades_count >= 0),
        paper_roi DECIMAL(10,4),
        live_trades_count INTEGER DEFAULT 0 CHECK (live_trades_count >= 0),
        live_roi DECIMAL(10,4),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        description TEXT,
        created_by VARCHAR(100),
        CONSTRAINT unique_strategy_name_version UNIQUE (strategy_name, strategy_version),
        CONSTRAINT strategy_activation_order
            CHECK (deactivated_at IS NULL OR activated_at IS NULL OR deactivated_at >= activated_at)
    );
    CREATE INDEX IF NOT EXISTS idx_strategies_platform ON strategies(platform_id);
    CREATE INDEX IF NOT EXISTS idx_strategies_status ON strategies(status);
    CREATE INDEX IF NOT EXISTS idx_strategies_strategy_type ON strategies(strategy_type);
    -- Historical query index (migration 024)
    CREATE INDEX IF NOT EXISTS idx_strategies_version_history ON strategies(strategy_name, strategy_version, created_at DESC);

    CREATE TABLE IF NOT EXISTS probability_models (
        model_id SERIAL PRIMARY KEY,
        model_name VARCHAR(100) NOT NULL,
        model_version VARCHAR(20) NOT NULL DEFAULT '1.0',
        model_class VARCHAR(50) NOT NULL REFERENCES model_classes(model_class_code),
        domain VARCHAR(50),
        config JSONB NOT NULL,
        training_start_date DATE,
        training_end_date DATE,
        training_sample_size INTEGER CHECK (training_sample_size IS NULL OR training_sample_size >= 0),
        status VARCHAR(20) NOT NULL DEFAULT 'draft'
            CHECK (status IN ('draft', 'testing', 'active', 'deprecated')),
        activated_at TIMESTAMP WITH TIME ZONE,
        deactivated_at TIMESTAMP WITH TIME ZONE,
        notes TEXT,
        validation_accuracy DECIMAL(6,4) CHECK (validation_accuracy IS NULL OR (validation_accuracy >= 0.0000 AND validation_accuracy <= 1.0000)),
        validation_calibration DECIMAL(6,4) CHECK (validation_calibration IS NULL OR validation_calibration >= 0.0000),
        validation_sample_size INTEGER CHECK (validation_sample_size IS NULL OR validation_sample_size >= 0),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        description TEXT,
        created_by VARCHAR(100),
        CONSTRAINT unique_model_name_version UNIQUE (model_name, model_version),
        CONSTRAINT model_activation_order
            CHECK (deactivated_at IS NULL OR activated_at IS NULL OR deactivated_at >= activated_at)
    );
    CREATE INDEX IF NOT EXISTS idx_probability_models_model_class ON probability_models(model_class);
    CREATE INDEX IF NOT EXISTS idx_probability_models_status ON probability_models(status);
    CREATE INDEX IF NOT EXISTS idx_probability_models_category ON probability_models(model_class, domain);

    -- edges table (SCD Type 2 with dual-key structure per migration 017)
    -- id: Surrogate primary key (unique across all versions)
    -- edge_id: Business key (can repeat for SCD Type 2 versions)
    CREATE TABLE IF NOT EXISTS edges (
        id SERIAL PRIMARY KEY,
        edge_id VARCHAR NOT NULL,
        market_id VARCHAR(100),
        probability_matrix_id INTEGER REFERENCES probability_matrices(probability_id) ON DELETE SET NULL,
        model_id INTEGER REFERENCES probability_models(model_id) ON DELETE SET NULL,
        expected_value DECIMAL(10,4) NOT NULL,
        true_win_probability DECIMAL(10,4) NOT NULL CHECK (true_win_probability >= 0.0000 AND true_win_probability <= 1.0000),
        market_implied_probability DECIMAL(10,4) NOT NULL CHECK (market_implied_probability >= 0.0000 AND market_implied_probability <= 1.0000),
        market_price DECIMAL(10,4) NOT NULL CHECK (market_price >= 0.0000 AND market_price <= 1.0000),
        confidence_level VARCHAR(20) CHECK (confidence_level IN ('high', 'medium', 'low')),
        confidence_metrics JSONB,
        recommended_action VARCHAR(50) CHECK (recommended_action IN ('auto_execute', 'alert', 'ignore')),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        row_current_ind BOOLEAN DEFAULT TRUE
    );
    CREATE INDEX IF NOT EXISTS idx_edges_market ON edges(market_id);
    CREATE INDEX IF NOT EXISTS idx_edges_ev ON edges(expected_value) WHERE row_current_ind = TRUE;
    CREATE INDEX IF NOT EXISTS idx_edges_current ON edges(row_current_ind) WHERE row_current_ind = TRUE;
    CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_unique_current ON edges(edge_id) WHERE row_current_ind = TRUE;
    CREATE INDEX IF NOT EXISTS idx_edges_business_key ON edges(edge_id);

    -- 7. TRADING & POSITIONS
    -- positions table (SCD Type 2 with dual-key structure per migration 015)
    -- id: Surrogate primary key (unique across all versions)
    -- position_id: Business key (can repeat for SCD Type 2 versions)
    CREATE TABLE IF NOT EXISTS positions (
        id SERIAL PRIMARY KEY,
        position_id VARCHAR NOT NULL,
        market_id VARCHAR(100),
        platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
        strategy_id INTEGER REFERENCES strategies(strategy_id),
        model_id INTEGER REFERENCES probability_models(model_id),
        side VARCHAR(10) NOT NULL CHECK (side IN ('yes', 'no', 'long', 'short')),
        entry_price DECIMAL(10,4) NOT NULL CHECK (entry_price >= 0.0000 AND entry_price <= 1.0000),
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        current_price DECIMAL(10,4),
        fees DECIMAL(10,4) CHECK (fees IS NULL OR fees >= 0.0000),
        status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'closed', 'settled')),
        unrealized_pnl DECIMAL(10,4),
        unrealized_pnl_pct DECIMAL(10,4),
        realized_pnl DECIMAL(10,4),
        trailing_stop_state JSONB,
        target_price DECIMAL(10,4) CHECK (target_price IS NULL OR (target_price >= 0.0000 AND target_price <= 1.0000)),
        stop_loss_price DECIMAL(10,4) CHECK (stop_loss_price IS NULL OR (stop_loss_price >= 0.0000 AND stop_loss_price <= 1.0000)),
        entry_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        exit_time TIMESTAMP WITH TIME ZONE,
        last_check_time TIMESTAMP WITH TIME ZONE,
        exit_price DECIMAL(10,4) CHECK (exit_price IS NULL OR (exit_price >= 0.0000 AND exit_price <= 1.0000)),
        position_metadata JSONB,
        exit_reason VARCHAR(100),
        exit_priority VARCHAR(20) CHECK (exit_priority IS NULL OR exit_priority IN ('critical', 'high', 'medium', 'low')),
        calculated_probability DECIMAL(10,4) CHECK (calculated_probability IS NULL OR (calculated_probability >= 0.0000 AND calculated_probability <= 1.0000)),
        edge_at_entry DECIMAL(10,4),
        market_price_at_entry DECIMAL(10,4) CHECK (market_price_at_entry IS NULL OR (market_price_at_entry >= 0.0000 AND market_price_at_entry <= 1.0000)),
        last_update TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        row_start_ts TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        row_end_ts TIMESTAMP WITH TIME ZONE,
        row_current_ind BOOLEAN DEFAULT TRUE
    );
    CREATE INDEX IF NOT EXISTS idx_positions_market ON positions(market_id);
    CREATE INDEX IF NOT EXISTS idx_positions_platform ON positions(platform_id);
    CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
    CREATE INDEX IF NOT EXISTS idx_positions_current ON positions(row_current_ind) WHERE row_current_ind = TRUE;
    CREATE UNIQUE INDEX IF NOT EXISTS idx_positions_unique_current ON positions(position_id) WHERE row_current_ind = TRUE;
    CREATE INDEX IF NOT EXISTS idx_positions_business_key ON positions(position_id);
    -- Historical query index (migration 024)
    CREATE INDEX IF NOT EXISTS idx_positions_history ON positions(row_current_ind, created_at DESC);

    -- Create ENUM type for trade source
    DO $$ BEGIN
        CREATE TYPE trade_source_type AS ENUM ('automated', 'manual');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;

    -- trades table (per migration 015/017: References surrogate IDs, not business keys)
    CREATE TABLE IF NOT EXISTS trades (
        trade_id SERIAL PRIMARY KEY,
        market_id VARCHAR(100),
        platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
        position_internal_id INTEGER REFERENCES positions(id) ON DELETE SET NULL,
        edge_internal_id INTEGER REFERENCES edges(id) ON DELETE SET NULL,
        strategy_id INTEGER REFERENCES strategies(strategy_id),
        model_id INTEGER REFERENCES probability_models(model_id),
        order_id VARCHAR(100),
        external_order_id VARCHAR(100),
        side VARCHAR(10) NOT NULL CHECK (side IN ('buy', 'sell')),
        price DECIMAL(10,4) NOT NULL CHECK (price >= 0.0000 AND price <= 1.0000),
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        fees DECIMAL(10,4) CHECK (fees IS NULL OR fees >= 0.0000),
        trade_source trade_source_type DEFAULT 'automated',
        calculated_probability DECIMAL(10,4) CHECK (calculated_probability IS NULL OR (calculated_probability >= 0.0000 AND calculated_probability <= 1.0000)),
        market_price DECIMAL(10,4) CHECK (market_price IS NULL OR (market_price >= 0.0000 AND market_price <= 1.0000)),
        edge_value DECIMAL(10,4),
        edge_at_execution DECIMAL(10,4),
        confidence_at_execution VARCHAR(20) CHECK (confidence_at_execution IN ('high', 'medium', 'low')),
        trade_metadata JSONB,
        fill_time_ms INTEGER,
        slippage DECIMAL(10,4),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_trades_market ON trades(market_id);
    CREATE INDEX IF NOT EXISTS idx_trades_platform ON trades(platform_id);
    CREATE INDEX IF NOT EXISTS idx_trades_position ON trades(position_internal_id);
    CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at);
    CREATE INDEX IF NOT EXISTS idx_trades_source ON trades(trade_source);

    CREATE TABLE IF NOT EXISTS settlements (
        settlement_id SERIAL PRIMARY KEY,
        market_id VARCHAR(100),
        platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
        outcome VARCHAR(50) NOT NULL,
        payout DECIMAL(10,4) CHECK (payout IS NULL OR payout >= 0.0000),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_settlements_market ON settlements(market_id);

    -- position_exits table (per migration 015: References surrogate ID, not business key)
    CREATE TABLE IF NOT EXISTS position_exits (
        exit_id SERIAL PRIMARY KEY,
        position_internal_id INTEGER REFERENCES positions(id) ON DELETE CASCADE,
        exit_reason VARCHAR(100) NOT NULL,
        exit_priority VARCHAR(20) CHECK (exit_priority IN ('critical', 'high', 'medium', 'low')),
        exit_price DECIMAL(10,4) CHECK (exit_price >= 0.0000 AND exit_price <= 1.0000),
        quantity_exited INTEGER CHECK (quantity_exited > 0),
        realized_pnl DECIMAL(10,4),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_position_exits_position ON position_exits(position_internal_id);

    -- exit_attempts table (per migration 015: References surrogate ID, not business key)
    CREATE TABLE IF NOT EXISTS exit_attempts (
        attempt_id SERIAL PRIMARY KEY,
        position_internal_id INTEGER REFERENCES positions(id) ON DELETE CASCADE,
        exit_reason VARCHAR(100) NOT NULL,
        attempted_price DECIMAL(10,4),
        actual_price DECIMAL(10,4),
        quantity INTEGER,
        success BOOLEAN,
        failure_reason TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_exit_attempts_position ON exit_attempts(position_internal_id);

    CREATE TABLE IF NOT EXISTS account_balance (
        balance_id SERIAL PRIMARY KEY,
        platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
        balance DECIMAL(10,4) NOT NULL CHECK (balance >= 0.0000),
        currency VARCHAR(10) DEFAULT 'USD',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        row_current_ind BOOLEAN DEFAULT TRUE
    );
    CREATE INDEX IF NOT EXISTS idx_balance_platform ON account_balance(platform_id);
    CREATE INDEX IF NOT EXISTS idx_balance_current ON account_balance(row_current_ind) WHERE row_current_ind = TRUE;

    -- 8. CONFIGURATION & SYSTEM STATE
    CREATE TABLE IF NOT EXISTS config_overrides (
        override_id SERIAL PRIMARY KEY,
        config_key VARCHAR(255) NOT NULL,
        override_value JSONB NOT NULL,
        data_type VARCHAR(20) CHECK (data_type IN ('float', 'int', 'bool', 'string', 'json')),
        reason TEXT,
        applied_by VARCHAR(100),
        applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        expires_at TIMESTAMP WITH TIME ZONE,
        active BOOLEAN DEFAULT TRUE,
        CONSTRAINT expiry_after_applied CHECK (expires_at IS NULL OR expires_at >= applied_at)
    );
    CREATE INDEX IF NOT EXISTS idx_config_overrides_key ON config_overrides(config_key);
    CREATE INDEX IF NOT EXISTS idx_config_overrides_active ON config_overrides(active) WHERE active = TRUE;

    CREATE TABLE IF NOT EXISTS circuit_breaker_events (
        event_id SERIAL PRIMARY KEY,
        breaker_type VARCHAR(50) NOT NULL CHECK (breaker_type IN ('daily_loss_limit', 'api_failures', 'data_stale', 'position_limit', 'manual')),
        triggered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        resolved_at TIMESTAMP WITH TIME ZONE,
        trigger_value JSONB,
        resolution_action VARCHAR(100),
        notes TEXT,
        CONSTRAINT resolution_after_trigger CHECK (resolved_at IS NULL OR resolved_at >= triggered_at)
    );
    CREATE INDEX IF NOT EXISTS idx_circuit_breaker_triggered ON circuit_breaker_events(triggered_at);
    CREATE INDEX IF NOT EXISTS idx_circuit_breaker_type ON circuit_breaker_events(breaker_type);

    CREATE TABLE IF NOT EXISTS system_health (
        health_id SERIAL PRIMARY KEY,
        component VARCHAR(50) NOT NULL CHECK (component IN ('kalshi_api', 'polymarket_api', 'espn_api', 'database', 'edge_detector', 'trading_engine', 'websocket')),
        status VARCHAR(20) NOT NULL CHECK (status IN ('healthy', 'degraded', 'down')),
        last_check TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        details JSONB,
        alert_sent BOOLEAN DEFAULT FALSE
    );
    CREATE INDEX IF NOT EXISTS idx_health_component ON system_health(component);
    CREATE INDEX IF NOT EXISTS idx_health_status ON system_health(status);

    CREATE TABLE IF NOT EXISTS alerts (
        alert_id SERIAL PRIMARY KEY,
        alert_type VARCHAR(50) NOT NULL,
        severity VARCHAR(20) CHECK (severity IN ('info', 'warning', 'error', 'critical')),
        message TEXT NOT NULL,
        source VARCHAR(100),
        acknowledged BOOLEAN DEFAULT FALSE,
        acknowledged_by VARCHAR(100),
        acknowledged_at TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);
    CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
    CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON alerts(acknowledged);

    -- 9. VIEWS
    CREATE OR REPLACE VIEW current_markets AS SELECT * FROM markets WHERE row_current_ind = TRUE;
    CREATE OR REPLACE VIEW current_game_states AS SELECT * FROM game_states WHERE row_current_ind = TRUE;
    CREATE OR REPLACE VIEW current_edges AS SELECT * FROM edges WHERE row_current_ind = TRUE;
    CREATE OR REPLACE VIEW open_positions AS SELECT * FROM positions WHERE row_current_ind = TRUE AND status = 'open';
    CREATE OR REPLACE VIEW current_balances AS SELECT * FROM account_balance WHERE row_current_ind = TRUE;
    CREATE OR REPLACE VIEW active_strategies AS SELECT * FROM strategies WHERE status = 'active';
    CREATE OR REPLACE VIEW active_models AS SELECT * FROM probability_models WHERE status = 'active';

    -- 10. SEED DATA - Kalshi Platform
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
    )
    ON CONFLICT (platform_id) DO NOTHING;

    -- Track migration version
    INSERT INTO alembic_version (version_num) VALUES ('0001')
    ON CONFLICT (version_num) DO NOTHING;
    """

    cursor.execute(schema_sql)
    connection.commit()
    cursor.close()


# Try to import testcontainers - gracefully handle if not available
try:
    from testcontainers.postgres import PostgresContainer

    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False
    PostgresContainer = None  # type: ignore[misc, assignment]


@pytest.fixture(scope="session")
def postgres_container() -> Generator[dict[str, str], None, None]:
    """
    Create an ephemeral PostgreSQL container for ALL database tests.

    Scope: session - One container for entire test run (optimal for pre-push hooks).

    Yields:
        Dictionary with connection parameters:
        - host: Container hostname
        - port: Exposed PostgreSQL port
        - database: Database name
        - user: Database user
        - password: Database password
        - connection_url: Full connection URL

    Educational Note:
        Using session scope means:
        1. Container starts once when first database test runs
        2. ALL tests share the same container (fast startup)
        3. Container stops after all tests complete
        4. Tests should use transactions/cleanup for isolation

        This provides BEST PERFORMANCE for pre-push hooks (~10s startup once
        vs ~10s per test class with class scope).

    Why Session Scope for Pre-Push:
        Pre-push runs ALL 8 test types (1196 tests). With class scope,
        we'd spin up ~50+ containers (one per test class). Session scope
        spins up ONE container, making pre-push run in ~3-5 min vs ~30 min.

    Isolation Strategy:
        - Each test should use clean_test_data fixture for data isolation
        - Tests should NOT rely on auto-increment IDs (use UUIDs)
        - Use unique identifiers per test to avoid collisions
    """
    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("testcontainers not installed - run: pip install testcontainers[postgres]")

    # Start PostgreSQL container
    container = PostgresContainer(
        image="postgres:15",
        user="test_user",
        password="test_password",
        dbname="precog_test",
    )

    with container:
        # Get connection parameters
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)

        connection_params = {
            "host": host,
            "port": port,
            "database": "precog_test",
            "user": "test_user",
            "password": "test_password",
            "connection_url": container.get_connection_url(),
        }

        # Apply schema migrations
        conn = psycopg2.connect(
            host=host,
            port=port,
            database="precog_test",
            user="test_user",
            password="test_password",
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        _apply_migration_sql(conn)
        conn.close()

        # Set environment variables for precog.database.connection
        original_env = {
            "DB_HOST": os.environ.get("DB_HOST"),
            "DB_PORT": os.environ.get("DB_PORT"),
            "DB_NAME": os.environ.get("DB_NAME"),
            "DB_USER": os.environ.get("DB_USER"),
            "DB_PASSWORD": os.environ.get("DB_PASSWORD"),
        }

        os.environ["DB_HOST"] = host
        os.environ["DB_PORT"] = str(port)
        os.environ["DB_NAME"] = "precog_test"
        os.environ["DB_USER"] = "test_user"
        os.environ["DB_PASSWORD"] = "test_password"

        yield connection_params

        # Restore original environment
        for key, value in original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]


@pytest.fixture
def container_db_connection(
    postgres_container: dict[str, str],
) -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Provide a database connection to the testcontainer.

    Args:
        postgres_container: The running PostgreSQL container fixture

    Yields:
        Active psycopg2 connection to the containerized database

    Usage:
        def test_something(self, container_db_connection):
            with container_db_connection.cursor() as cur:
                cur.execute("SELECT 1")
    """
    conn = psycopg2.connect(
        host=postgres_container["host"],
        port=postgres_container["port"],
        database=postgres_container["database"],
        user=postgres_container["user"],
        password=postgres_container["password"],
    )

    yield conn

    conn.close()


@pytest.fixture
def container_cursor(
    container_db_connection: psycopg2.extensions.connection,
) -> Generator[psycopg2.extensions.cursor, None, None]:
    """
    Provide a cursor with automatic rollback for test isolation.

    Args:
        container_db_connection: Active connection to containerized database

    Yields:
        Cursor for executing queries. Changes are rolled back after test.
    """
    cursor = container_db_connection.cursor()

    yield cursor

    # Rollback any uncommitted changes
    container_db_connection.rollback()
    cursor.close()
