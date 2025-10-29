-- Migration 010: Create Teams and Elo Rating Tables
-- Date: 2025-10-24
-- Phase: 4 (Elo Model - Preparation)
-- Purpose: Create teams table for Elo ratings and elo_rating_history for audit trail

-- ============================================================================
-- BACKGROUND: Elo Model Storage Architecture
-- ============================================================================
-- Decision: Store Elo ratings in teams table, not probability_models.config
-- Rationale:
--   - probability_models.config = IMMUTABLE MODEL PARAMETERS (k_factor, initial_rating)
--   - teams.current_elo_rating = MUTABLE TEAM RATINGS (updated after each game)
--   - Preserves immutability pattern for probability_models
--   - Simpler queries (native column vs JSONB extraction)
--   - Better performance (indexed DECIMAL vs JSONB)
--
-- See: docs/ELO_AND_SETTLEMENTS_ARCHITECTURE_ANALYSIS_V1.0.md

-- ============================================================================
-- STEP 1: Create teams Table
-- ============================================================================

CREATE TABLE teams (
    team_id SERIAL PRIMARY KEY,
    team_code VARCHAR(10) NOT NULL UNIQUE,   -- 'KC', 'BUF', 'SF'
    team_name VARCHAR NOT NULL,              -- 'Kansas City Chiefs'
    sport VARCHAR NOT NULL,                  -- 'nfl', 'nba', 'mlb'

    -- External IDs for API integration
    espn_team_id VARCHAR,
    kalshi_team_id VARCHAR,

    -- Current Elo Rating (MUTABLE - updated after each game)
    current_elo_rating DECIMAL(10,2),

    -- Team Metadata
    conference VARCHAR,                       -- 'AFC', 'NFC', 'Eastern', 'Western'
    division VARCHAR,                         -- 'West', 'East', 'North', 'South'
    metadata JSONB,                          -- Additional team-specific data

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()

    -- ❌ NO row_current_ind - teams are mutable entities, not versioned
);

-- Indexes
CREATE INDEX idx_teams_code ON teams(team_code);
CREATE INDEX idx_teams_sport ON teams(sport);
CREATE INDEX idx_teams_elo_rating ON teams(current_elo_rating);
CREATE INDEX idx_teams_espn ON teams(espn_team_id) WHERE espn_team_id IS NOT NULL;
CREATE INDEX idx_teams_kalshi ON teams(kalshi_team_id) WHERE kalshi_team_id IS NOT NULL;

-- Comments
COMMENT ON TABLE teams IS 'Team entities with current Elo ratings and metadata';
COMMENT ON COLUMN teams.team_code IS 'Short code for team (e.g., KC, BUF, SF) - used in game_states.home_team/away_team';
COMMENT ON COLUMN teams.current_elo_rating IS 'Current Elo rating (MUTABLE - updated after each game)';
COMMENT ON COLUMN teams.espn_team_id IS 'ESPN team ID for game_states feed integration';
COMMENT ON COLUMN teams.kalshi_team_id IS 'Kalshi team identifier for market matching';

-- ============================================================================
-- STEP 2: Create elo_rating_history Table
-- ============================================================================

CREATE TABLE elo_rating_history (
    history_id SERIAL PRIMARY KEY,
    team_id INT REFERENCES teams(team_id) ON DELETE CASCADE,
    event_id VARCHAR REFERENCES events(event_id),

    -- Rating Change
    rating_before DECIMAL(10,2) NOT NULL,
    rating_after DECIMAL(10,2) NOT NULL,

    -- Game Context
    opponent_team_id INT REFERENCES teams(team_id),
    game_result VARCHAR NOT NULL,            -- 'win', 'loss', 'tie'

    -- Model Parameters Used
    k_factor DECIMAL(10,2) NOT NULL,         -- K-factor used for this update

    created_at TIMESTAMP DEFAULT NOW()

    -- ❌ NO row_current_ind - history is append-only
);

-- Indexes
CREATE INDEX idx_elo_history_team ON elo_rating_history(team_id);
CREATE INDEX idx_elo_history_event ON elo_rating_history(event_id);
CREATE INDEX idx_elo_history_created ON elo_rating_history(created_at);
CREATE INDEX idx_elo_history_opponent ON elo_rating_history(opponent_team_id);

-- Comments
COMMENT ON TABLE elo_rating_history IS 'Audit trail of all Elo rating changes (append-only)';
COMMENT ON COLUMN elo_rating_history.rating_before IS 'Elo rating before this game';
COMMENT ON COLUMN elo_rating_history.rating_after IS 'Elo rating after this game';
COMMENT ON COLUMN elo_rating_history.game_result IS 'Result from this team''s perspective (win/loss/tie)';
COMMENT ON COLUMN elo_rating_history.k_factor IS 'K-factor used for this rating update (allows tracking parameter changes)';

-- ============================================================================
-- STEP 3: Add CHECK Constraints
-- ============================================================================

ALTER TABLE teams
ADD CONSTRAINT teams_sport_check
CHECK (sport IN ('nfl', 'nba', 'mlb', 'nhl', 'soccer'));

ALTER TABLE teams
ADD CONSTRAINT teams_elo_rating_check
CHECK (current_elo_rating IS NULL OR current_elo_rating BETWEEN 0 AND 3000);

ALTER TABLE elo_rating_history
ADD CONSTRAINT elo_history_game_result_check
CHECK (game_result IN ('win', 'loss', 'tie'));

ALTER TABLE elo_rating_history
ADD CONSTRAINT elo_history_rating_before_check
CHECK (rating_before BETWEEN 0 AND 3000);

ALTER TABLE elo_rating_history
ADD CONSTRAINT elo_history_rating_after_check
CHECK (rating_after BETWEEN 0 AND 3000);

ALTER TABLE elo_rating_history
ADD CONSTRAINT elo_history_k_factor_check
CHECK (k_factor > 0 AND k_factor <= 100);

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    teams_exists BOOLEAN;
    elo_history_exists BOOLEAN;
    teams_columns_count INT;
    elo_columns_count INT;
BEGIN
    -- Check teams table exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'teams'
    ) INTO teams_exists;

    IF NOT teams_exists THEN
        RAISE EXCEPTION 'Migration 010 failed: teams table not created';
    END IF;

    -- Check elo_rating_history table exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'elo_rating_history'
    ) INTO elo_history_exists;

    IF NOT elo_history_exists THEN
        RAISE EXCEPTION 'Migration 010 failed: elo_rating_history table not created';
    END IF;

    -- Check teams table has correct columns
    SELECT COUNT(*) INTO teams_columns_count
    FROM information_schema.columns
    WHERE table_name = 'teams'
    AND column_name IN ('team_id', 'team_code', 'team_name', 'sport', 'current_elo_rating',
                        'espn_team_id', 'kalshi_team_id', 'conference', 'division', 'metadata');

    IF teams_columns_count < 10 THEN
        RAISE EXCEPTION 'Migration 010 failed: teams table missing columns (found %, expected 10)', teams_columns_count;
    END IF;

    -- Check elo_rating_history table has correct columns
    SELECT COUNT(*) INTO elo_columns_count
    FROM information_schema.columns
    WHERE table_name = 'elo_rating_history'
    AND column_name IN ('history_id', 'team_id', 'event_id', 'rating_before', 'rating_after',
                        'opponent_team_id', 'game_result', 'k_factor');

    IF elo_columns_count < 8 THEN
        RAISE EXCEPTION 'Migration 010 failed: elo_rating_history table missing columns (found %, expected 8)', elo_columns_count;
    END IF;

    -- Check indexes
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'teams' AND indexname = 'idx_teams_code'
    ) THEN
        RAISE EXCEPTION 'Migration 010 failed: idx_teams_code index not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'elo_rating_history' AND indexname = 'idx_elo_history_team'
    ) THEN
        RAISE EXCEPTION 'Migration 010 failed: idx_elo_history_team index not created';
    END IF;

    RAISE NOTICE 'Migration 010 successful: Created teams and elo_rating_history tables with indexes and constraints';
END $$;

-- ============================================================================
-- USAGE NOTES
-- ============================================================================
--
-- Example: Create Elo model in probability_models (stores MODEL PARAMETERS)
-- INSERT INTO probability_models (model_name, model_version, model_type, sport, config)
-- VALUES ('elo_nfl', 'v1.0', 'elo', 'nfl', '{"k_factor": 30, "initial_rating": 1500}'::JSONB);
--
-- Example: Seed teams with initial Elo ratings (stores TEAM RATINGS)
-- INSERT INTO teams (team_code, team_name, sport, current_elo_rating, conference, division)
-- VALUES ('KC', 'Kansas City Chiefs', 'nfl', 1650, 'AFC', 'West');
--
-- Example: Update Elo after game
-- -- Record history
-- INSERT INTO elo_rating_history (team_id, event_id, rating_before, rating_after, opponent_team_id, game_result, k_factor)
-- VALUES (1, 'EVT-NFL-KC-BUF', 1650, 1665, 2, 'win', 30);
--
-- -- Update current rating
-- UPDATE teams SET current_elo_rating = 1665, updated_at = NOW() WHERE team_id = 1;
--
-- Example: Calculate edge using Elo
-- SELECT
--     m.market_id,
--     1.0 / (1 + POW(10, (t_away.current_elo_rating - t_home.current_elo_rating) / 400.0)) AS elo_win_prob,
--     m.yes_price AS market_price
-- FROM markets m
-- JOIN events e ON m.event_id = e.event_id
-- JOIN game_states gs ON e.event_id = gs.event_id AND gs.row_current_ind = TRUE
-- JOIN teams t_home ON gs.home_team = t_home.team_code
-- JOIN teams t_away ON gs.away_team = t_away.team_code;
