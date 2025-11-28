-- Seed Data: NFL Teams ESPN ID and Display Name Update
-- Date: 2025-11-27
-- Phase: 2 (Live Data Integration)
-- Purpose: Update existing NFL teams with ESPN team IDs and display names
-- Related: ADR-029 (ESPN Data Model), REQ-DATA-003 (Multi-Sport Support)

-- ============================================================================
-- BACKGROUND: ESPN Team ID Integration
-- ============================================================================
-- ESPN team IDs are required for matching live game data from ESPN API
-- Display names provide short team names for UI display
-- This update maintains backward compatibility with existing NFL seed (001)

-- ============================================================================
-- UPDATE NFL TEAMS WITH ESPN IDS AND DISPLAY NAMES
-- ============================================================================
-- ESPN team IDs sourced from ESPN API responses
-- Display names are commonly used short names

-- AFC EAST
UPDATE teams SET espn_team_id = '2', display_name = 'Bills', league = 'nfl' WHERE team_code = 'BUF' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '15', display_name = 'Dolphins', league = 'nfl' WHERE team_code = 'MIA' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '20', display_name = 'Jets', league = 'nfl' WHERE team_code = 'NYJ' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '17', display_name = 'Patriots', league = 'nfl' WHERE team_code = 'NE' AND sport = 'nfl';

-- AFC NORTH
UPDATE teams SET espn_team_id = '33', display_name = 'Ravens', league = 'nfl' WHERE team_code = 'BAL' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '4', display_name = 'Bengals', league = 'nfl' WHERE team_code = 'CIN' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '23', display_name = 'Steelers', league = 'nfl' WHERE team_code = 'PIT' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '5', display_name = 'Browns', league = 'nfl' WHERE team_code = 'CLE' AND sport = 'nfl';

-- AFC SOUTH
UPDATE teams SET espn_team_id = '34', display_name = 'Texans', league = 'nfl' WHERE team_code = 'HOU' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '11', display_name = 'Colts', league = 'nfl' WHERE team_code = 'IND' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '30', display_name = 'Jaguars', league = 'nfl' WHERE team_code = 'JAX' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '10', display_name = 'Titans', league = 'nfl' WHERE team_code = 'TEN' AND sport = 'nfl';

-- AFC WEST
UPDATE teams SET espn_team_id = '12', display_name = 'Chiefs', league = 'nfl' WHERE team_code = 'KC' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '24', display_name = 'Chargers', league = 'nfl' WHERE team_code = 'LAC' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '13', display_name = 'Raiders', league = 'nfl' WHERE team_code = 'LV' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '7', display_name = 'Broncos', league = 'nfl' WHERE team_code = 'DEN' AND sport = 'nfl';

-- NFC EAST
UPDATE teams SET espn_team_id = '21', display_name = 'Eagles', league = 'nfl' WHERE team_code = 'PHI' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '6', display_name = 'Cowboys', league = 'nfl' WHERE team_code = 'DAL' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '28', display_name = 'Commanders', league = 'nfl' WHERE team_code = 'WAS' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '19', display_name = 'Giants', league = 'nfl' WHERE team_code = 'NYG' AND sport = 'nfl';

-- NFC NORTH
UPDATE teams SET espn_team_id = '8', display_name = 'Lions', league = 'nfl' WHERE team_code = 'DET' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '9', display_name = 'Packers', league = 'nfl' WHERE team_code = 'GB' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '16', display_name = 'Vikings', league = 'nfl' WHERE team_code = 'MIN' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '3', display_name = 'Bears', league = 'nfl' WHERE team_code = 'CHI' AND sport = 'nfl';

-- NFC SOUTH
UPDATE teams SET espn_team_id = '27', display_name = 'Buccaneers', league = 'nfl' WHERE team_code = 'TB' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '1', display_name = 'Falcons', league = 'nfl' WHERE team_code = 'ATL' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '18', display_name = 'Saints', league = 'nfl' WHERE team_code = 'NO' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '29', display_name = 'Panthers', league = 'nfl' WHERE team_code = 'CAR' AND sport = 'nfl';

-- NFC WEST
UPDATE teams SET espn_team_id = '25', display_name = '49ers', league = 'nfl' WHERE team_code = 'SF' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '14', display_name = 'Rams', league = 'nfl' WHERE team_code = 'LAR' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '26', display_name = 'Seahawks', league = 'nfl' WHERE team_code = 'SEA' AND sport = 'nfl';
UPDATE teams SET espn_team_id = '22', display_name = 'Cardinals', league = 'nfl' WHERE team_code = 'ARI' AND sport = 'nfl';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    updated_count INT;
    missing_espn_ids INT;
    missing_display_names INT;
BEGIN
    -- Count teams with ESPN IDs
    SELECT COUNT(*) INTO updated_count
    FROM teams
    WHERE sport = 'nfl' AND espn_team_id IS NOT NULL;

    IF updated_count != 32 THEN
        RAISE EXCEPTION 'NFL ESPN update failed: Expected 32 teams with ESPN IDs, found %', updated_count;
    END IF;

    -- Check for missing ESPN IDs
    SELECT COUNT(*) INTO missing_espn_ids
    FROM teams
    WHERE sport = 'nfl' AND espn_team_id IS NULL;

    IF missing_espn_ids > 0 THEN
        RAISE EXCEPTION 'NFL ESPN update failed: % teams missing ESPN IDs', missing_espn_ids;
    END IF;

    -- Check for missing display names
    SELECT COUNT(*) INTO missing_display_names
    FROM teams
    WHERE sport = 'nfl' AND display_name IS NULL;

    IF missing_display_names > 0 THEN
        RAISE EXCEPTION 'NFL ESPN update failed: % teams missing display names', missing_display_names;
    END IF;

    RAISE NOTICE 'NFL ESPN update successful: Updated 32 teams with ESPN IDs and display names';
END $$;
