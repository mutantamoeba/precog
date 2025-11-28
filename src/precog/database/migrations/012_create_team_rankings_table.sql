-- Migration 012: Create Team Rankings Table
-- Date: 2025-11-27
-- Phase: 2 (Live Data Integration)
-- Purpose: Create team_rankings table for AP Poll, CFP, Coaches Poll rankings with temporal validity
-- Related: ADR-029 (ESPN Data Model), REQ-DATA-004 (Team Rankings Storage)

-- ============================================================================
-- BACKGROUND: Team Rankings Temporal Storage
-- ============================================================================
-- Decision: Store rankings with temporal validity (season + week) rather than current-only
-- Rationale:
--   - College rankings change weekly and affect market pricing
--   - Historical rankings needed for backtesting and model validation
--   - Multiple ranking types (AP Poll, CFP, Coaches, ESPN Power, ESPN FPI)
--   - Week-level granularity captures weekly poll changes
--   - Preseason/postseason rankings have week=NULL (week 0 implied)
--
-- See: docs/utility/ESPN_DATA_MODEL_IMPLEMENTATION_PLAN_V1.0.md

-- ============================================================================
-- STEP 1: Create team_rankings Table
-- ============================================================================

CREATE TABLE team_rankings (
    ranking_id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,

    -- Ranking Identification
    ranking_type VARCHAR(50) NOT NULL,    -- 'ap_poll', 'cfp', 'coaches_poll', 'espn_power', 'espn_fpi'
    rank INTEGER NOT NULL,                -- 1-25 for polls, 1-130 for FPI
    season INTEGER NOT NULL,              -- 2024, 2025, etc.
    week INTEGER,                         -- 1-18 for regular season, NULL for preseason/final

    -- Temporal Validity
    ranking_date DATE NOT NULL,           -- Date ranking was released

    -- Ranking Details (optional based on ranking type)
    points INTEGER,                       -- AP/Coaches poll points
    first_place_votes INTEGER,            -- Number of #1 votes
    previous_rank INTEGER,                -- Rank from previous week (NULL if unranked)

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure one ranking per team/type/season/week combination
    CONSTRAINT team_rankings_unique UNIQUE (team_id, ranking_type, season, week)
);

-- ============================================================================
-- STEP 2: Create Indexes
-- ============================================================================

-- Most common query: current rankings for a type
CREATE INDEX idx_rankings_type_season_week ON team_rankings(ranking_type, season, week);

-- Team history lookup
CREATE INDEX idx_rankings_team ON team_rankings(team_id);

-- Date-based queries (e.g., "what were rankings on Nov 15?")
CREATE INDEX idx_rankings_date ON team_rankings(ranking_date);

-- Top-N queries (e.g., "show top 10 teams")
CREATE INDEX idx_rankings_type_rank ON team_rankings(ranking_type, season, rank);

-- ============================================================================
-- STEP 3: Add Comments
-- ============================================================================

COMMENT ON TABLE team_rankings IS 'Historical team rankings (AP Poll, CFP, etc.) with temporal validity (REQ-DATA-004)';
COMMENT ON COLUMN team_rankings.ranking_type IS 'Type of ranking: ap_poll, cfp, coaches_poll, espn_power, espn_fpi';
COMMENT ON COLUMN team_rankings.rank IS 'Numeric rank position (1 = best)';
COMMENT ON COLUMN team_rankings.season IS 'Season year (e.g., 2024 for 2024-25 season)';
COMMENT ON COLUMN team_rankings.week IS 'Week number (1-18), NULL for preseason/final rankings';
COMMENT ON COLUMN team_rankings.ranking_date IS 'Date ranking was officially released';
COMMENT ON COLUMN team_rankings.points IS 'Poll points (AP/Coaches) - higher is better';
COMMENT ON COLUMN team_rankings.first_place_votes IS 'Number of first-place votes received';
COMMENT ON COLUMN team_rankings.previous_rank IS 'Previous week rank, NULL if team was unranked';

-- ============================================================================
-- STEP 4: Add CHECK Constraints
-- ============================================================================

-- Valid ranking types
ALTER TABLE team_rankings
ADD CONSTRAINT team_rankings_type_check
CHECK (ranking_type IN ('ap_poll', 'cfp', 'coaches_poll', 'espn_power', 'espn_fpi'));

-- Rank must be positive
ALTER TABLE team_rankings
ADD CONSTRAINT team_rankings_rank_positive
CHECK (rank > 0);

-- Season reasonable range (2020-2050)
ALTER TABLE team_rankings
ADD CONSTRAINT team_rankings_season_check
CHECK (season BETWEEN 2020 AND 2050);

-- Week valid range if specified (0-20 for bowl season)
ALTER TABLE team_rankings
ADD CONSTRAINT team_rankings_week_check
CHECK (week IS NULL OR week BETWEEN 0 AND 20);

-- Points and votes must be non-negative if specified
ALTER TABLE team_rankings
ADD CONSTRAINT team_rankings_points_check
CHECK (points IS NULL OR points >= 0);

ALTER TABLE team_rankings
ADD CONSTRAINT team_rankings_votes_check
CHECK (first_place_votes IS NULL OR first_place_votes >= 0);

-- Previous rank must be positive if specified
ALTER TABLE team_rankings
ADD CONSTRAINT team_rankings_prev_rank_check
CHECK (previous_rank IS NULL OR previous_rank > 0);

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    table_exists BOOLEAN;
    column_count INT;
    index_count INT;
BEGIN
    -- Check table exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'team_rankings'
    ) INTO table_exists;

    IF NOT table_exists THEN
        RAISE EXCEPTION 'Migration 012 failed: team_rankings table not created';
    END IF;

    -- Check column count
    SELECT COUNT(*) INTO column_count
    FROM information_schema.columns
    WHERE table_name = 'team_rankings'
    AND column_name IN ('ranking_id', 'team_id', 'ranking_type', 'rank', 'season',
                        'week', 'ranking_date', 'points', 'first_place_votes', 'previous_rank');

    IF column_count < 10 THEN
        RAISE EXCEPTION 'Migration 012 failed: team_rankings table missing columns (found %, expected 10)', column_count;
    END IF;

    -- Check indexes exist
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE tablename = 'team_rankings'
    AND indexname IN ('idx_rankings_type_season_week', 'idx_rankings_team', 'idx_rankings_date', 'idx_rankings_type_rank');

    IF index_count < 4 THEN
        RAISE EXCEPTION 'Migration 012 failed: team_rankings table missing indexes (found %, expected 4)', index_count;
    END IF;

    -- Check foreign key to teams
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'team_rankings'
        AND constraint_type = 'FOREIGN KEY'
    ) THEN
        RAISE EXCEPTION 'Migration 012 failed: team_rankings missing foreign key to teams';
    END IF;

    RAISE NOTICE 'Migration 012 successful: Created team_rankings table with indexes and constraints';
END $$;

-- ============================================================================
-- USAGE NOTES
-- ============================================================================
--
-- Example: Insert AP Poll ranking
-- INSERT INTO team_rankings (team_id, ranking_type, rank, season, week, ranking_date, points, first_place_votes)
-- VALUES (1, 'ap_poll', 3, 2024, 12, '2024-11-17', 1432, 12);
--
-- Example: Get current AP Poll top 25
-- SELECT t.team_name, tr.rank, tr.points, tr.first_place_votes
-- FROM team_rankings tr
-- JOIN teams t ON tr.team_id = t.team_id
-- WHERE tr.ranking_type = 'ap_poll'
--   AND tr.season = 2024
--   AND tr.week = (SELECT MAX(week) FROM team_rankings WHERE ranking_type = 'ap_poll' AND season = 2024)
-- ORDER BY tr.rank;
--
-- Example: Get team's ranking history
-- SELECT ranking_type, week, rank, points
-- FROM team_rankings
-- WHERE team_id = 1 AND season = 2024
-- ORDER BY ranking_type, week;
--
-- Example: Find teams that moved up in rankings
-- SELECT t.team_name, tr.rank, tr.previous_rank, (tr.previous_rank - tr.rank) AS positions_gained
-- FROM team_rankings tr
-- JOIN teams t ON tr.team_id = t.team_id
-- WHERE tr.ranking_type = 'ap_poll'
--   AND tr.season = 2024
--   AND tr.week = 12
--   AND tr.previous_rank > tr.rank
-- ORDER BY positions_gained DESC;
--
