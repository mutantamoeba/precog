-- Migration 013: Enhance Teams Table for Multi-Sport Support
-- Date: 2025-11-27
-- Phase: 2 (Live Data Integration)
-- Purpose: Add display_name, league columns and update sport CHECK constraint for 6 leagues
-- Related: ADR-029 (ESPN Data Model), REQ-DATA-003 (Multi-Sport Support)

-- ============================================================================
-- BACKGROUND: Multi-Sport Team Enhancement
-- ============================================================================
-- Decision: Enhance teams table to support 6 leagues (NFL, NCAAF, NBA, NCAAB, NHL, WNBA)
-- Rationale:
--   - display_name provides short team name ('Chiefs' vs 'Kansas City Chiefs')
--   - league differentiates within same sport (NCAAF vs NFL are both 'football')
--   - sport field updated to include all supported sports
--   - Maintains backward compatibility with existing NFL/NBA teams
--
-- Changes:
--   - ADD COLUMN display_name VARCHAR(100)
--   - ADD COLUMN league VARCHAR(20)
--   - UPDATE sport CHECK to include: nfl, ncaaf, nba, ncaab, nhl, wnba, mlb, soccer
--
-- See: docs/utility/ESPN_DATA_MODEL_IMPLEMENTATION_PLAN_V1.0.md

-- ============================================================================
-- STEP 1: Add New Columns
-- ============================================================================

-- Add display_name (short team name for UI/display)
ALTER TABLE teams
ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);

-- Add league (to differentiate NFL vs NCAAF, NBA vs NCAAB)
ALTER TABLE teams
ADD COLUMN IF NOT EXISTS league VARCHAR(20);

-- ============================================================================
-- STEP 2: Update Sport CHECK Constraint
-- ============================================================================

-- Drop old CHECK constraint (from migration 010)
ALTER TABLE teams
DROP CONSTRAINT IF EXISTS teams_sport_check;

-- Add new CHECK constraint with all 6 primary leagues + future expansion
ALTER TABLE teams
ADD CONSTRAINT teams_sport_check
CHECK (sport IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'wnba', 'mlb', 'soccer'));

-- ============================================================================
-- STEP 3: Add League CHECK Constraint
-- ============================================================================

-- League values should match sport values for consistency
ALTER TABLE teams
ADD CONSTRAINT teams_league_check
CHECK (league IS NULL OR league IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'wnba', 'mlb', 'soccer'));

-- ============================================================================
-- STEP 4: Backfill league Column from sport
-- ============================================================================

-- For existing teams, set league = sport (maintains backward compatibility)
UPDATE teams
SET league = sport
WHERE league IS NULL;

-- ============================================================================
-- STEP 5: Add Index on League
-- ============================================================================

-- Index for league-specific queries
CREATE INDEX IF NOT EXISTS idx_teams_league ON teams(league) WHERE league IS NOT NULL;

-- ============================================================================
-- STEP 6: Update Comments
-- ============================================================================

COMMENT ON COLUMN teams.display_name IS 'Short team name for display (e.g., "Chiefs" vs "Kansas City Chiefs")';
COMMENT ON COLUMN teams.league IS 'League code (nfl, ncaaf, nba, ncaab, nhl, wnba) - may differ from sport for clarity';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    display_name_exists BOOLEAN;
    league_exists BOOLEAN;
    sport_check_valid BOOLEAN;
    league_check_valid BOOLEAN;
BEGIN
    -- Check display_name column exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'teams' AND column_name = 'display_name'
    ) INTO display_name_exists;

    IF NOT display_name_exists THEN
        RAISE EXCEPTION 'Migration 013 failed: display_name column not created';
    END IF;

    -- Check league column exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'teams' AND column_name = 'league'
    ) INTO league_exists;

    IF NOT league_exists THEN
        RAISE EXCEPTION 'Migration 013 failed: league column not created';
    END IF;

    -- Check sport CHECK constraint includes new values
    SELECT EXISTS (
        SELECT 1 FROM information_schema.check_constraints
        WHERE constraint_name = 'teams_sport_check'
        AND check_clause LIKE '%ncaaf%'
        AND check_clause LIKE '%ncaab%'
        AND check_clause LIKE '%nhl%'
        AND check_clause LIKE '%wnba%'
    ) INTO sport_check_valid;

    IF NOT sport_check_valid THEN
        RAISE EXCEPTION 'Migration 013 failed: sport CHECK constraint not updated with new leagues';
    END IF;

    -- Check league CHECK constraint exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.check_constraints
        WHERE constraint_name = 'teams_league_check'
    ) INTO league_check_valid;

    IF NOT league_check_valid THEN
        RAISE EXCEPTION 'Migration 013 failed: league CHECK constraint not created';
    END IF;

    -- Check league backfill worked
    IF EXISTS (
        SELECT 1 FROM teams
        WHERE sport IS NOT NULL AND league IS NULL
    ) THEN
        RAISE EXCEPTION 'Migration 013 failed: league column not backfilled from sport';
    END IF;

    RAISE NOTICE 'Migration 013 successful: Enhanced teams table with display_name, league, and updated constraints';
END $$;

-- ============================================================================
-- USAGE NOTES
-- ============================================================================
--
-- Example: Insert NBA team with new columns
-- INSERT INTO teams (team_code, team_name, display_name, sport, league, espn_team_id, conference, division)
-- VALUES ('LAL', 'Los Angeles Lakers', 'Lakers', 'nba', 'nba', '13', 'Western', 'Pacific');
--
-- Example: Insert NCAAF team (distinguished from NFL)
-- INSERT INTO teams (team_code, team_name, display_name, sport, league, espn_team_id, conference, division)
-- VALUES ('ALA', 'Alabama Crimson Tide', 'Alabama', 'ncaaf', 'ncaaf', '333', 'SEC', 'West');
--
-- Example: Query by league
-- SELECT team_code, team_name, display_name, conference
-- FROM teams
-- WHERE league = 'nba'
-- ORDER BY conference, division;
--
-- Example: Get display names for game display
-- SELECT t1.display_name AS home_team, t2.display_name AS away_team
-- FROM game_states gs
-- JOIN teams t1 ON gs.home_team_id = t1.team_id
-- JOIN teams t2 ON gs.away_team_id = t2.team_id
-- WHERE gs.row_current_ind = TRUE;
--
