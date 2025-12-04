"""Initial baseline schema for Precog database.

This migration creates all database tables with the CORRECT schemas,
consolidating the previous SQL and Python migrations (000-029) into
a single authoritative source.

Key Features:
- SCD Type 2 versioning for frequently-changing data (markets, positions, game_states)
- Immutable versioning for strategies and probability models
- Decimal precision (10,4) for all prices/probabilities
- CHECK constraints for data validation
- Proper foreign key relationships with CASCADE

Revision ID: 0001
Revises: None (initial migration)
Create Date: 2025-12-03

References:
- ADR-030: Alembic Migration Framework
- DATABASE_SCHEMA_SUMMARY_V1.12.md
- DEVELOPMENT_PATTERNS_V1.5.md (Pattern 1: Decimal Precision)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all database tables with correct schemas."""

    # =========================================================================
    # 1. PLATFORM & MARKET HIERARCHY
    # =========================================================================

    # platforms table
    op.execute("""
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
        )
    """)

    # series table
    op.execute("""
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
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_series_platform ON series(platform_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_series_category ON series(category, subcategory)")

    # events table
    op.execute("""
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
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_platform ON events(platform_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_series ON events(series_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_status ON events(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_start_time ON events(start_time)")

    # markets table (SCD Type 2 with row_current_ind)
    op.execute("""
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
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_markets_event ON markets(event_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_markets_platform ON markets(platform_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_markets_current ON markets(row_current_ind) WHERE row_current_ind = TRUE"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_markets_status ON markets(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_markets_market_id ON markets(market_id)")

    # =========================================================================
    # 2. TEAMS & SPORTS DATA
    # =========================================================================

    # teams table
    op.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            team_id SERIAL PRIMARY KEY,
            team_name VARCHAR(100) NOT NULL,
            display_name VARCHAR(100),
            abbreviation VARCHAR(10),
            sport VARCHAR(20) NOT NULL CHECK (sport IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'wnba', 'mlb', 'soccer')),
            league VARCHAR(20) CHECK (league IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'wnba', 'mlb', 'soccer')),
            conference VARCHAR(50),
            division VARCHAR(50),
            espn_team_id VARCHAR(50),
            external_ids JSONB,
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_teams_sport ON teams(sport)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_teams_league ON teams(league)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_teams_espn_id ON teams(espn_team_id)")

    # elo_rating_history table
    op.execute("""
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
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_elo_team ON elo_rating_history(team_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_elo_date ON elo_rating_history(rating_date)")

    # venues table
    op.execute("""
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
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_venues_espn_id ON venues(espn_venue_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_venues_name ON venues(venue_name)")

    # team_rankings table
    op.execute("""
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
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rankings_type_season_week ON team_rankings(ranking_type, season, week)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_rankings_team ON team_rankings(team_id)")

    # =========================================================================
    # 3. GAME STATES (SCD Type 2) - CORRECT SCHEMA FROM MIGRATION 029
    # =========================================================================

    op.execute("""
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
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_game_states_event ON game_states(espn_event_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_game_states_current ON game_states(espn_event_id) WHERE row_current_ind = TRUE"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_game_states_current_unique ON game_states(espn_event_id) WHERE row_current_ind = TRUE"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_game_states_date ON game_states(game_date)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_game_states_status ON game_states(game_status) WHERE row_current_ind = TRUE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_game_states_league ON game_states(league) WHERE row_current_ind = TRUE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_game_states_situation ON game_states USING GIN (situation)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_game_states_teams ON game_states(home_team_id, away_team_id) WHERE row_current_ind = TRUE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_game_states_business_key ON game_states(game_state_id)"
    )

    # =========================================================================
    # 4. PROBABILITY & EDGE DETECTION
    # =========================================================================

    # probability_matrices table
    op.execute("""
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
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_probability_lookup ON probability_matrices(category, subcategory, version, state_descriptor, value_bucket)"
    )

    # =========================================================================
    # 5. LOOKUP TABLES (Strategy Types & Model Classes)
    # =========================================================================

    # strategy_types lookup table
    op.execute("""
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
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_strategy_types_active ON strategy_types(is_active) WHERE is_active = TRUE"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_strategy_types_category ON strategy_types(category)")

    # Seed initial strategy types
    op.execute("""
        INSERT INTO strategy_types (strategy_type_code, display_name, description, category, display_order)
        VALUES
            ('value', 'Value', 'Exploit mispriced markets based on calculated true probability', 'directional', 1),
            ('arbitrage', 'Arbitrage', 'Risk-free profit from price discrepancies across markets', 'arbitrage', 2),
            ('momentum', 'Momentum', 'Follow price trends and market momentum', 'directional', 3),
            ('mean_reversion', 'Mean Reversion', 'Bet on prices returning to historical averages', 'directional', 4)
        ON CONFLICT (strategy_type_code) DO NOTHING
    """)

    # model_classes lookup table
    op.execute("""
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
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_model_classes_active ON model_classes(is_active) WHERE is_active = TRUE"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_model_classes_category ON model_classes(category)")

    # Seed initial model classes
    op.execute("""
        INSERT INTO model_classes (model_class_code, display_name, description, category, complexity_level, display_order)
        VALUES
            ('elo', 'Elo Rating', 'Classic Elo rating system for head-to-head predictions', 'statistical', 'simple', 1),
            ('ensemble', 'Ensemble', 'Combine multiple models for robust predictions', 'hybrid', 'advanced', 2),
            ('ml', 'Machine Learning', 'General ML models (XGBoost, Random Forest, etc.)', 'machine_learning', 'moderate', 3),
            ('hybrid', 'Hybrid', 'Combine statistical and ML approaches', 'hybrid', 'advanced', 4),
            ('regression', 'Regression', 'Linear and logistic regression models', 'statistical', 'simple', 5),
            ('neural_net', 'Neural Network', 'Deep learning models', 'machine_learning', 'advanced', 6),
            ('baseline', 'Baseline', 'Simple baseline models for comparison', 'baseline', 'simple', 7)
        ON CONFLICT (model_class_code) DO NOTHING
    """)

    # =========================================================================
    # 6. STRATEGIES & PROBABILITY MODELS (Immutable Versions)
    # =========================================================================

    # strategies table (Immutable versions)
    op.execute("""
        CREATE TABLE IF NOT EXISTS strategies (
            strategy_id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            version VARCHAR(20) NOT NULL,
            approach VARCHAR(50) REFERENCES strategy_types(strategy_type_code),
            domain VARCHAR(50),
            platform_id VARCHAR(50) REFERENCES platforms(platform_id),
            config JSONB NOT NULL,
            entry_criteria JSONB,
            exit_criteria JSONB,
            risk_params JSONB,
            status VARCHAR(20) DEFAULT 'development' CHECK (status IN ('development', 'testing', 'active', 'paused', 'retired')),
            description TEXT,
            created_by VARCHAR(100),
            activated_at TIMESTAMP WITH TIME ZONE,
            deactivated_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT unique_strategy_version UNIQUE (name, version)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_strategies_name ON strategies(name)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_strategies_approach_domain ON strategies(approach, domain)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_strategies_status ON strategies(status)")

    # probability_models table (Immutable versions)
    op.execute("""
        CREATE TABLE IF NOT EXISTS probability_models (
            model_id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            version VARCHAR(20) NOT NULL,
            approach VARCHAR(50) REFERENCES model_classes(model_class_code),
            domain VARCHAR(50),
            config JSONB NOT NULL,
            weights JSONB,
            feature_columns JSONB,
            training_start_date DATE,
            training_end_date DATE,
            training_sample_size INTEGER,
            status VARCHAR(20) DEFAULT 'development' CHECK (status IN ('development', 'testing', 'active', 'paused', 'retired')),
            description TEXT,
            created_by VARCHAR(100),
            activated_at TIMESTAMP WITH TIME ZONE,
            deactivated_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT unique_model_version UNIQUE (name, version)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_models_name ON probability_models(name)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_models_approach_domain ON probability_models(approach, domain)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_models_status ON probability_models(status)")

    # edges table (SCD Type 2)
    op.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            edge_id SERIAL PRIMARY KEY,
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
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_edges_market ON edges(market_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edges_ev ON edges(expected_value) WHERE row_current_ind = TRUE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edges_current ON edges(row_current_ind) WHERE row_current_ind = TRUE"
    )

    # =========================================================================
    # 7. TRADING & POSITIONS
    # =========================================================================

    # positions table (SCD Type 2)
    op.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            position_id SERIAL PRIMARY KEY,
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
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_positions_market ON positions(market_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_positions_platform ON positions(platform_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_positions_current ON positions(row_current_ind) WHERE row_current_ind = TRUE"
    )

    # Create ENUM type for trade source
    op.execute("CREATE TYPE trade_source_type AS ENUM ('automated', 'manual')")

    # trades table (Append-only)
    op.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            trade_id SERIAL PRIMARY KEY,
            market_id VARCHAR(100),
            platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
            position_id INTEGER REFERENCES positions(position_id) ON DELETE SET NULL,
            edge_id INTEGER REFERENCES edges(edge_id) ON DELETE SET NULL,
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
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_trades_market ON trades(market_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_trades_platform ON trades(platform_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_trades_position ON trades(position_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_trades_source ON trades(trade_source)")

    # settlements table (Append-only)
    op.execute("""
        CREATE TABLE IF NOT EXISTS settlements (
            settlement_id SERIAL PRIMARY KEY,
            market_id VARCHAR(100),
            platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
            outcome VARCHAR(50) NOT NULL,
            payout DECIMAL(10,4) CHECK (payout IS NULL OR payout >= 0.0000),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_settlements_market ON settlements(market_id)")

    # position_exits table
    op.execute("""
        CREATE TABLE IF NOT EXISTS position_exits (
            exit_id SERIAL PRIMARY KEY,
            position_id INTEGER REFERENCES positions(position_id) ON DELETE CASCADE,
            exit_reason VARCHAR(100) NOT NULL,
            exit_priority VARCHAR(20) CHECK (exit_priority IN ('critical', 'high', 'medium', 'low')),
            exit_price DECIMAL(10,4) CHECK (exit_price >= 0.0000 AND exit_price <= 1.0000),
            quantity_exited INTEGER CHECK (quantity_exited > 0),
            realized_pnl DECIMAL(10,4),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_position_exits_position ON position_exits(position_id)"
    )

    # exit_attempts table
    op.execute("""
        CREATE TABLE IF NOT EXISTS exit_attempts (
            attempt_id SERIAL PRIMARY KEY,
            position_id INTEGER REFERENCES positions(position_id) ON DELETE CASCADE,
            exit_reason VARCHAR(100) NOT NULL,
            attempted_price DECIMAL(10,4),
            actual_price DECIMAL(10,4),
            quantity INTEGER,
            success BOOLEAN,
            failure_reason TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_exit_attempts_position ON exit_attempts(position_id)"
    )

    # account_balance table (SCD Type 2)
    op.execute("""
        CREATE TABLE IF NOT EXISTS account_balance (
            balance_id SERIAL PRIMARY KEY,
            platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
            balance DECIMAL(10,4) NOT NULL CHECK (balance >= 0.0000),
            currency VARCHAR(10) DEFAULT 'USD',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            row_current_ind BOOLEAN DEFAULT TRUE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_balance_platform ON account_balance(platform_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_balance_current ON account_balance(row_current_ind) WHERE row_current_ind = TRUE"
    )

    # =========================================================================
    # 8. CONFIGURATION & SYSTEM STATE
    # =========================================================================

    # config_overrides table
    op.execute("""
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
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_config_overrides_key ON config_overrides(config_key)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_config_overrides_active ON config_overrides(active) WHERE active = TRUE"
    )

    # circuit_breaker_events table
    op.execute("""
        CREATE TABLE IF NOT EXISTS circuit_breaker_events (
            event_id SERIAL PRIMARY KEY,
            breaker_type VARCHAR(50) NOT NULL CHECK (breaker_type IN ('daily_loss_limit', 'api_failures', 'data_stale', 'position_limit', 'manual')),
            triggered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            resolved_at TIMESTAMP WITH TIME ZONE,
            trigger_value JSONB,
            resolution_action VARCHAR(100),
            notes TEXT,
            CONSTRAINT resolution_after_trigger CHECK (resolved_at IS NULL OR resolved_at >= triggered_at)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_circuit_breaker_triggered ON circuit_breaker_events(triggered_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_circuit_breaker_type ON circuit_breaker_events(breaker_type)"
    )

    # system_health table
    op.execute("""
        CREATE TABLE IF NOT EXISTS system_health (
            health_id SERIAL PRIMARY KEY,
            component VARCHAR(50) NOT NULL CHECK (component IN ('kalshi_api', 'polymarket_api', 'espn_api', 'database', 'edge_detector', 'trading_engine', 'websocket')),
            status VARCHAR(20) NOT NULL CHECK (status IN ('healthy', 'degraded', 'down')),
            last_check TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            details JSONB,
            alert_sent BOOLEAN DEFAULT FALSE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_health_component ON system_health(component)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_health_status ON system_health(status)")

    # alerts table
    op.execute("""
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
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON alerts(acknowledged)")

    # =========================================================================
    # 9. HELPER VIEWS
    # =========================================================================

    op.execute("""
        CREATE OR REPLACE VIEW current_markets AS
        SELECT * FROM markets WHERE row_current_ind = TRUE
    """)

    op.execute("""
        CREATE OR REPLACE VIEW current_game_states AS
        SELECT * FROM game_states WHERE row_current_ind = TRUE
    """)

    op.execute("""
        CREATE OR REPLACE VIEW current_edges AS
        SELECT * FROM edges WHERE row_current_ind = TRUE
    """)

    op.execute("""
        CREATE OR REPLACE VIEW open_positions AS
        SELECT * FROM positions WHERE row_current_ind = TRUE AND status = 'open'
    """)

    op.execute("""
        CREATE OR REPLACE VIEW current_balances AS
        SELECT * FROM account_balance WHERE row_current_ind = TRUE
    """)

    op.execute("""
        CREATE OR REPLACE VIEW active_strategies AS
        SELECT * FROM strategies WHERE status = 'active'
    """)

    op.execute("""
        CREATE OR REPLACE VIEW active_models AS
        SELECT * FROM probability_models WHERE status = 'active'
    """)

    # =========================================================================
    # 10. SEED DATA - Kalshi Platform
    # =========================================================================

    op.execute("""
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
        ON CONFLICT (platform_id) DO NOTHING
    """)


def downgrade() -> None:
    """Drop all database tables in reverse dependency order."""

    # Drop views first
    op.execute("DROP VIEW IF EXISTS active_models CASCADE")
    op.execute("DROP VIEW IF EXISTS active_strategies CASCADE")
    op.execute("DROP VIEW IF EXISTS current_balances CASCADE")
    op.execute("DROP VIEW IF EXISTS open_positions CASCADE")
    op.execute("DROP VIEW IF EXISTS current_edges CASCADE")
    op.execute("DROP VIEW IF EXISTS current_game_states CASCADE")
    op.execute("DROP VIEW IF EXISTS current_markets CASCADE")

    # Drop tables in reverse dependency order
    op.execute("DROP TABLE IF EXISTS alerts CASCADE")
    op.execute("DROP TABLE IF EXISTS system_health CASCADE")
    op.execute("DROP TABLE IF EXISTS circuit_breaker_events CASCADE")
    op.execute("DROP TABLE IF EXISTS config_overrides CASCADE")
    op.execute("DROP TABLE IF EXISTS account_balance CASCADE")
    op.execute("DROP TABLE IF EXISTS exit_attempts CASCADE")
    op.execute("DROP TABLE IF EXISTS position_exits CASCADE")
    op.execute("DROP TABLE IF EXISTS settlements CASCADE")
    op.execute("DROP TABLE IF EXISTS trades CASCADE")
    op.execute("DROP TABLE IF EXISTS positions CASCADE")
    op.execute("DROP TABLE IF EXISTS edges CASCADE")
    op.execute("DROP TABLE IF EXISTS probability_models CASCADE")
    op.execute("DROP TABLE IF EXISTS strategies CASCADE")
    op.execute("DROP TABLE IF EXISTS model_classes CASCADE")
    op.execute("DROP TABLE IF EXISTS strategy_types CASCADE")
    op.execute("DROP TABLE IF EXISTS probability_matrices CASCADE")
    op.execute("DROP TABLE IF EXISTS game_states CASCADE")
    op.execute("DROP TABLE IF EXISTS team_rankings CASCADE")
    op.execute("DROP TABLE IF EXISTS venues CASCADE")
    op.execute("DROP TABLE IF EXISTS elo_rating_history CASCADE")
    op.execute("DROP TABLE IF EXISTS teams CASCADE")
    op.execute("DROP TABLE IF EXISTS markets CASCADE")
    op.execute("DROP TABLE IF EXISTS events CASCADE")
    op.execute("DROP TABLE IF EXISTS series CASCADE")
    op.execute("DROP TABLE IF EXISTS platforms CASCADE")

    # Drop ENUM type
    op.execute("DROP TYPE IF EXISTS trade_source_type CASCADE")
