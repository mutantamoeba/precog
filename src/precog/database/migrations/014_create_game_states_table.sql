-- Migration 014: Create Game States Table with SCD Type 2 Versioning
-- Date: 2025-11-27
-- Phase: 2 (Live Data Integration)
-- Purpose: Create game_states table for tracking live game data with complete history
-- Related: ADR-029 (ESPN Data Model), REQ-DATA-001 (Game State Data Collection)

-- ============================================================================
-- BACKGROUND: SCD Type 2 for Game State History
-- ============================================================================
-- Decision: Use SCD Type 2 pattern for game_states (same pattern as markets/positions)
-- Rationale:
--   - Each game state change creates NEW row, preserving complete history
--   - row_current_ind = TRUE marks the single current state for each game
--   - Enables historical playback (what was the score at 2:30 PM?)
--   - Critical for backtesting and model validation
--   - Estimated ~1.8M rows/year across 6 sports (~9,500 games x ~190 updates/game)
--
-- JSONB Situation Field:
--   - Sport-specific data (downs for football, fouls for basketball, shots for hockey)
--   - Avoids 30+ nullable columns that vary by sport
--   - GIN index enables efficient JSON queries
--   - Schema-flexible for future sports
--
-- See: docs/utility/ESPN_DATA_MODEL_IMPLEMENTATION_PLAN_V1.0.md

-- ============================================================================
-- STEP 0: Drop legacy game_states table from migration 000
-- ============================================================================
-- Migration 000 created a simpler game_states table with home_team/away_team VARCHAR columns.
-- This migration replaces it with the Phase 2 design using proper foreign keys to teams table.
-- The || true in CI migration runner suppresses errors, so we need explicit DROP.

DROP TABLE IF EXISTS game_states CASCADE;

-- ============================================================================
-- STEP 1: Create game_states Table
-- ============================================================================

CREATE TABLE game_states (
    -- Primary Key (surrogate)
    game_state_id SERIAL PRIMARY KEY,

    -- Game Identification
    espn_event_id VARCHAR(50) NOT NULL,        -- ESPN event identifier (natural key component)

    -- Team References (foreign keys to teams table)
    home_team_id INTEGER REFERENCES teams(team_id),
    away_team_id INTEGER REFERENCES teams(team_id),

    -- Venue Reference (foreign key to venues table)
    venue_id INTEGER REFERENCES venues(venue_id),

    -- Score Data
    home_score INTEGER NOT NULL DEFAULT 0,
    away_score INTEGER NOT NULL DEFAULT 0,

    -- Game Progress
    period INTEGER NOT NULL DEFAULT 0,         -- 0=pregame, 1-4=quarters, 5+=OT
    clock_seconds DECIMAL(10,2),               -- Seconds remaining in period (NULL if stopped)
    clock_display VARCHAR(20),                 -- Display format (e.g., "5:32", "Final", "Halftime")

    -- Game Status
    game_status VARCHAR(50) NOT NULL,          -- 'pre', 'in_progress', 'halftime', 'final', 'delayed', 'postponed', 'canceled'

    -- Game Metadata (static for the game, duplicated for query convenience)
    game_date TIMESTAMP WITH TIME ZONE,        -- Scheduled game start time
    broadcast VARCHAR(100),                    -- TV broadcast info (e.g., "ESPN", "CBS")
    neutral_site BOOLEAN DEFAULT FALSE,        -- TRUE for bowl games, tournaments
    season_type VARCHAR(20),                   -- 'preseason', 'regular', 'playoff', 'bowl', 'tournament'
    week_number INTEGER,                       -- Week number (NFL weeks 1-18, college weeks 0-15)
    league VARCHAR(20),                        -- 'nfl', 'ncaaf', 'nba', etc.

    -- Sport-Specific Situation Data (JSONB for flexibility)
    -- Football: {"possession": "KC", "down": 2, "distance": 7, "yard_line": 35, ...}
    -- Basketball: {"possession": "LAL", "home_fouls": 4, "away_fouls": 3, ...}
    -- Hockey: {"home_powerplay": true, "powerplay_time": "1:45", "home_shots": 28, ...}
    situation JSONB,

    -- Period-by-Period Scores
    -- Format: [[home_q1, away_q1], [home_q2, away_q2], ...]
    linescores JSONB,

    -- Data Source Tracking
    data_source VARCHAR(50) DEFAULT 'espn',    -- Source API ('espn', 'balldontlie', etc.)

    -- SCD Type 2 Fields (Pattern 2 from DEVELOPMENT_PATTERNS)
    row_start_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    row_end_timestamp TIMESTAMP WITH TIME ZONE,         -- NULL for current row
    row_current_ind BOOLEAN DEFAULT TRUE               -- TRUE for current row only
);

-- ============================================================================
-- STEP 2: Create Partial Unique Index for Current Row
-- ============================================================================

-- Ensures only ONE current row per espn_event_id (SCD Type 2 constraint)
CREATE UNIQUE INDEX idx_game_states_current_unique
ON game_states(espn_event_id)
WHERE row_current_ind = TRUE;

-- ============================================================================
-- STEP 3: Create Performance Indexes
-- ============================================================================

-- Primary lookup: current state by event ID
CREATE INDEX idx_game_states_event ON game_states(espn_event_id);

-- Current game states only (most common access pattern)
CREATE INDEX idx_game_states_current ON game_states(espn_event_id)
WHERE row_current_ind = TRUE;

-- Date-based queries (games on a specific day)
CREATE INDEX idx_game_states_date ON game_states(game_date);

-- Status filtering (find all in-progress games)
CREATE INDEX idx_game_states_status ON game_states(game_status);

-- League filtering (all NBA games)
CREATE INDEX idx_game_states_league ON game_states(league);

-- JSONB situation queries (possession, down/distance, etc.)
CREATE INDEX idx_game_states_situation ON game_states USING GIN (situation);

-- Historical queries by timestamp
CREATE INDEX idx_game_states_timestamp ON game_states(row_start_timestamp);

-- Team lookups
CREATE INDEX idx_game_states_home_team ON game_states(home_team_id);
CREATE INDEX idx_game_states_away_team ON game_states(away_team_id);

-- Venue lookups
CREATE INDEX idx_game_states_venue ON game_states(venue_id);

-- ============================================================================
-- STEP 4: Add Comments
-- ============================================================================

COMMENT ON TABLE game_states IS 'Live game state tracking with SCD Type 2 versioning - complete history preserved (REQ-DATA-001)';

-- Core Fields
COMMENT ON COLUMN game_states.game_state_id IS 'Surrogate primary key (auto-increment)';
COMMENT ON COLUMN game_states.espn_event_id IS 'ESPN event identifier - natural key component with row_current_ind';
COMMENT ON COLUMN game_states.home_team_id IS 'Foreign key to teams.team_id for home team';
COMMENT ON COLUMN game_states.away_team_id IS 'Foreign key to teams.team_id for away team';
COMMENT ON COLUMN game_states.venue_id IS 'Foreign key to venues.venue_id';

-- Score and Progress
COMMENT ON COLUMN game_states.home_score IS 'Current home team score';
COMMENT ON COLUMN game_states.away_score IS 'Current away team score';
COMMENT ON COLUMN game_states.period IS 'Current period (0=pregame, 1-4=regulation, 5+=overtime)';
COMMENT ON COLUMN game_states.clock_seconds IS 'Seconds remaining in period (NULL when clock stopped)';
COMMENT ON COLUMN game_states.clock_display IS 'Human-readable clock display (e.g., "5:32", "Final")';
COMMENT ON COLUMN game_states.game_status IS 'Game status: pre, in_progress, halftime, final, delayed, postponed, canceled';

-- Metadata
COMMENT ON COLUMN game_states.game_date IS 'Scheduled game start time (UTC)';
COMMENT ON COLUMN game_states.broadcast IS 'TV broadcast information';
COMMENT ON COLUMN game_states.neutral_site IS 'TRUE for games at neutral venues (bowls, tournaments)';
COMMENT ON COLUMN game_states.season_type IS 'Season phase: preseason, regular, playoff, bowl, tournament';
COMMENT ON COLUMN game_states.week_number IS 'Week number within season';
COMMENT ON COLUMN game_states.league IS 'League code: nfl, ncaaf, nba, ncaab, nhl, wnba';

-- JSONB Fields
COMMENT ON COLUMN game_states.situation IS 'Sport-specific situation data (JSONB) - downs, fouls, shots, etc.';
COMMENT ON COLUMN game_states.linescores IS 'Period-by-period scores as JSONB array: [[home_p1, away_p1], ...]';

-- SCD Type 2
COMMENT ON COLUMN game_states.row_start_timestamp IS 'When this version became current (SCD Type 2)';
COMMENT ON COLUMN game_states.row_end_timestamp IS 'When this version was superseded (NULL for current row)';
COMMENT ON COLUMN game_states.row_current_ind IS 'TRUE for current row only - enforced by partial unique index';

-- ============================================================================
-- STEP 5: Add CHECK Constraints
-- ============================================================================

-- Scores must be non-negative
ALTER TABLE game_states
ADD CONSTRAINT game_states_home_score_check
CHECK (home_score >= 0);

ALTER TABLE game_states
ADD CONSTRAINT game_states_away_score_check
CHECK (away_score >= 0);

-- Period must be non-negative
ALTER TABLE game_states
ADD CONSTRAINT game_states_period_check
CHECK (period >= 0);

-- Clock seconds must be non-negative if specified
ALTER TABLE game_states
ADD CONSTRAINT game_states_clock_seconds_check
CHECK (clock_seconds IS NULL OR clock_seconds >= 0);

-- Valid game statuses
ALTER TABLE game_states
ADD CONSTRAINT game_states_status_check
CHECK (game_status IN ('pre', 'in_progress', 'halftime', 'final', 'delayed', 'postponed', 'canceled'));

-- Valid season types
ALTER TABLE game_states
ADD CONSTRAINT game_states_season_type_check
CHECK (season_type IS NULL OR season_type IN ('preseason', 'regular', 'playoff', 'bowl', 'tournament', 'allstar'));

-- Valid league values
ALTER TABLE game_states
ADD CONSTRAINT game_states_league_check
CHECK (league IS NULL OR league IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'wnba', 'mlb', 'soccer'));

-- Week number reasonable range
ALTER TABLE game_states
ADD CONSTRAINT game_states_week_check
CHECK (week_number IS NULL OR week_number BETWEEN 0 AND 25);

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    table_exists BOOLEAN;
    column_count INT;
    index_count INT;
    partial_unique_exists BOOLEAN;
BEGIN
    -- Check table exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'game_states'
    ) INTO table_exists;

    IF NOT table_exists THEN
        RAISE EXCEPTION 'Migration 014 failed: game_states table not created';
    END IF;

    -- Check column count (core columns)
    SELECT COUNT(*) INTO column_count
    FROM information_schema.columns
    WHERE table_name = 'game_states'
    AND column_name IN (
        'game_state_id', 'espn_event_id', 'home_team_id', 'away_team_id', 'venue_id',
        'home_score', 'away_score', 'period', 'clock_seconds', 'clock_display',
        'game_status', 'game_date', 'situation', 'linescores',
        'row_start_timestamp', 'row_end_timestamp', 'row_current_ind'
    );

    IF column_count < 17 THEN
        RAISE EXCEPTION 'Migration 014 failed: game_states table missing columns (found %, expected 17)', column_count;
    END IF;

    -- Check partial unique index exists (critical for SCD Type 2)
    SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'game_states'
        AND indexname = 'idx_game_states_current_unique'
    ) INTO partial_unique_exists;

    IF NOT partial_unique_exists THEN
        RAISE EXCEPTION 'Migration 014 failed: partial unique index for row_current_ind not created';
    END IF;

    -- Check index count (should have at least 10 indexes)
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE tablename = 'game_states';

    IF index_count < 10 THEN
        RAISE EXCEPTION 'Migration 014 failed: game_states table missing indexes (found %, expected 10+)', index_count;
    END IF;

    RAISE NOTICE 'Migration 014 successful: Created game_states table with SCD Type 2 support, indexes, and constraints';
END $$;

-- ============================================================================
-- USAGE NOTES
-- ============================================================================
--
-- Example: Insert initial pregame state
-- INSERT INTO game_states (
--     espn_event_id, home_team_id, away_team_id, venue_id,
--     home_score, away_score, period, game_status, game_date,
--     broadcast, league, season_type, week_number
-- )
-- VALUES (
--     '401547417', 1, 2, 1,
--     0, 0, 0, 'pre', '2024-11-28 16:30:00-05',
--     'CBS', 'nfl', 'regular', 12
-- );
--
-- Example: Update game state (SCD Type 2 - creates new row)
-- -- Step 1: Close previous row
-- UPDATE game_states
-- SET row_current_ind = FALSE,
--     row_end_timestamp = NOW()
-- WHERE espn_event_id = '401547417'
--   AND row_current_ind = TRUE;
--
-- -- Step 2: Insert new row
-- INSERT INTO game_states (
--     espn_event_id, home_team_id, away_team_id, venue_id,
--     home_score, away_score, period, clock_seconds, clock_display,
--     game_status, situation, league
-- )
-- VALUES (
--     '401547417', 1, 2, 1,
--     7, 0, 1, 892, '14:52',
--     'in_progress', '{"possession": "KC", "down": 1, "distance": 10, "yard_line": 25}'::JSONB, 'nfl'
-- );
--
-- Example: Query current game state
-- SELECT * FROM game_states
-- WHERE espn_event_id = '401547417'
--   AND row_current_ind = TRUE;
--
-- Example: Query game state history
-- SELECT game_state_id, home_score, away_score, period, clock_display, row_start_timestamp
-- FROM game_states
-- WHERE espn_event_id = '401547417'
-- ORDER BY row_start_timestamp;
--
-- Example: Query situation data (JSONB)
-- SELECT espn_event_id, situation->>'possession' AS possession,
--        (situation->>'down')::INT AS down,
--        (situation->>'distance')::INT AS distance
-- FROM game_states
-- WHERE row_current_ind = TRUE
--   AND league = 'nfl'
--   AND game_status = 'in_progress';
--
-- Example: Find all in-progress games
-- SELECT gs.espn_event_id, t_home.display_name, gs.home_score,
--        t_away.display_name, gs.away_score, gs.clock_display
-- FROM game_states gs
-- JOIN teams t_home ON gs.home_team_id = t_home.team_id
-- JOIN teams t_away ON gs.away_team_id = t_away.team_id
-- WHERE gs.row_current_ind = TRUE
--   AND gs.game_status = 'in_progress';
--
