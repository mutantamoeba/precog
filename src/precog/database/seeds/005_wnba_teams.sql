-- Seed Data: WNBA Teams with ESPN IDs
-- Date: 2025-11-27
-- Phase: 2 (Live Data Integration)
-- Purpose: Seed 12 WNBA teams with ESPN team IDs for live game data integration
-- Related: ADR-029 (ESPN Data Model), REQ-DATA-003 (Multi-Sport Support)

-- ============================================================================
-- WNBA TEAMS (12 Teams)
-- ============================================================================
-- ESPN team IDs sourced from ESPN API
-- Initial Elo: 1500 = league average, adjusted based on 2024 season performance
-- Scale: ~1650 = championship contender, ~1350 = rebuilding

INSERT INTO teams (team_code, team_name, display_name, sport, league, espn_team_id, current_elo_rating, conference, division) VALUES

-- EASTERN CONFERENCE
('ATL', 'Atlanta Dream', 'Dream', 'wnba', 'wnba', '3', 1480, 'Eastern', NULL),
('CHI', 'Chicago Sky', 'Sky', 'wnba', 'wnba', '4', 1500, 'Eastern', NULL),
('CON', 'Connecticut Sun', 'Sun', 'wnba', 'wnba', '5', 1580, 'Eastern', NULL),
('IND', 'Indiana Fever', 'Fever', 'wnba', 'wnba', '7', 1460, 'Eastern', NULL),
('NYL', 'New York Liberty', 'Liberty', 'wnba', 'wnba', '9', 1660, 'Eastern', NULL),
('WAS', 'Washington Mystics', 'Mystics', 'wnba', 'wnba', '14', 1420, 'Eastern', NULL),

-- WESTERN CONFERENCE
('DAL', 'Dallas Wings', 'Wings', 'wnba', 'wnba', '6', 1400, 'Western', NULL),
('LVA', 'Las Vegas Aces', 'Aces', 'wnba', 'wnba', '18', 1640, 'Western', NULL),
('LAX', 'Los Angeles Sparks', 'Sparks', 'wnba', 'wnba', '8', 1380, 'Western', NULL),
('MIN', 'Minnesota Lynx', 'Lynx', 'wnba', 'wnba', '16', 1620, 'Western', NULL),
('PHO', 'Phoenix Mercury', 'Mercury', 'wnba', 'wnba', '11', 1460, 'Western', NULL),
('SEA', 'Seattle Storm', 'Storm', 'wnba', 'wnba', '17', 1520, 'Western', NULL);

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    team_count INT;
    eastern_count INT;
    western_count INT;
BEGIN
    SELECT COUNT(*) INTO team_count FROM teams WHERE league = 'wnba';

    IF team_count != 12 THEN
        RAISE EXCEPTION 'WNBA seed failed: Expected 12 teams, found %', team_count;
    END IF;

    -- Check conference distribution
    SELECT COUNT(*) INTO eastern_count FROM teams WHERE league = 'wnba' AND conference = 'Eastern';
    SELECT COUNT(*) INTO western_count FROM teams WHERE league = 'wnba' AND conference = 'Western';

    IF eastern_count != 6 THEN
        RAISE EXCEPTION 'WNBA seed failed: Expected 6 Eastern teams, found %', eastern_count;
    END IF;

    IF western_count != 6 THEN
        RAISE EXCEPTION 'WNBA seed failed: Expected 6 Western teams, found %', western_count;
    END IF;

    -- Check all have ESPN IDs
    IF EXISTS (SELECT 1 FROM teams WHERE league = 'wnba' AND espn_team_id IS NULL) THEN
        RAISE EXCEPTION 'WNBA seed failed: Some teams missing ESPN IDs';
    END IF;

    -- Check Elo ratings in valid range
    IF EXISTS (SELECT 1 FROM teams WHERE league = 'wnba' AND (current_elo_rating < 1000 OR current_elo_rating > 2000)) THEN
        RAISE EXCEPTION 'WNBA seed failed: Elo ratings outside expected range (1000-2000)';
    END IF;

    RAISE NOTICE 'WNBA seed successful: Loaded 12 teams (6 Eastern, 6 Western)';
    RAISE NOTICE 'Elo range: % to %',
        (SELECT MIN(current_elo_rating) FROM teams WHERE league = 'wnba'),
        (SELECT MAX(current_elo_rating) FROM teams WHERE league = 'wnba');
END $$;
