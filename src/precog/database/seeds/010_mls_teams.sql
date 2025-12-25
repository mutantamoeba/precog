-- Seed Data: MLS Teams with ESPN IDs
-- Date: 2025-12-24
-- Phase: 2 (Live Data Integration)
-- Purpose: Seed MLS teams with ESPN team IDs for prediction market coverage
-- Related: ADR-029 (ESPN Data Model), REQ-DATA-003 (Multi-Sport Support)

-- ============================================================================
-- MLS TEAMS - ALL 29 TEAMS (2024 SEASON)
-- ============================================================================
-- Initial Elo: 1500 = average, ~1600 = MLS Cup contender, ~1400 = rebuilding
-- ESPN IDs verified against ESPN API

INSERT INTO teams (team_code, team_name, display_name, sport, league, espn_team_id, current_elo_rating, conference, division) VALUES

-- EASTERN CONFERENCE (15 Teams)
('ATL', 'Atlanta United FC', 'Atlanta United', 'soccer', 'mls', '18144', 1480, 'Eastern', NULL),
('CLT', 'Charlotte FC', 'Charlotte FC', 'soccer', 'mls', '18170', 1440, 'Eastern', NULL),
('CHI', 'Chicago Fire FC', 'Chicago Fire', 'soccer', 'mls', '167', 1440, 'Eastern', NULL),
('CIN', 'FC Cincinnati', 'FC Cincinnati', 'soccer', 'mls', '18154', 1560, 'Eastern', NULL),
('CLB', 'Columbus Crew', 'Columbus', 'soccer', 'mls', '169', 1600, 'Eastern', NULL),
('DC', 'D.C. United', 'D.C. United', 'soccer', 'mls', '170', 1420, 'Eastern', NULL),
('MIA', 'Inter Miami CF', 'Inter Miami', 'soccer', 'mls', '18159', 1540, 'Eastern', NULL),
('MTL', 'CF Montreal', 'CF Montreal', 'soccer', 'mls', '168', 1480, 'Eastern', NULL),
('NE', 'New England Revolution', 'New England', 'soccer', 'mls', '175', 1460, 'Eastern', NULL),
('RBNY', 'New York Red Bulls', 'NY Red Bulls', 'soccer', 'mls', '176', 1500, 'Eastern', NULL),
('NYC', 'New York City FC', 'NYCFC', 'soccer', 'mls', '17551', 1520, 'Eastern', NULL),
('ORL', 'Orlando City SC', 'Orlando City', 'soccer', 'mls', '12698', 1500, 'Eastern', NULL),
('PHI', 'Philadelphia Union', 'Philadelphia', 'soccer', 'mls', '178', 1520, 'Eastern', NULL),
('TOR', 'Toronto FC', 'Toronto FC', 'soccer', 'mls', '181', 1420, 'Eastern', NULL),
('NSH', 'Nashville SC', 'Nashville', 'soccer', 'mls', '18157', 1480, 'Eastern', NULL),

-- WESTERN CONFERENCE (14 Teams)
('AUS', 'Austin FC', 'Austin FC', 'soccer', 'mls', '18165', 1480, 'Western', NULL),
('COL', 'Colorado Rapids', 'Colorado', 'soccer', 'mls', '174', 1460, 'Western', NULL),
('DAL', 'FC Dallas', 'FC Dallas', 'soccer', 'mls', '171', 1460, 'Western', NULL),
('HOU', 'Houston Dynamo FC', 'Houston', 'soccer', 'mls', '183', 1520, 'Western', NULL),
('LA', 'LA Galaxy', 'LA Galaxy', 'soccer', 'mls', '172', 1540, 'Western', NULL),
('LAFC', 'Los Angeles FC', 'LAFC', 'soccer', 'mls', '17853', 1580, 'Western', NULL),
('MIN', 'Minnesota United FC', 'Minnesota', 'soccer', 'mls', '17372', 1480, 'Western', NULL),
('POR', 'Portland Timbers', 'Portland', 'soccer', 'mls', '179', 1480, 'Western', NULL),
('RSL', 'Real Salt Lake', 'Real Salt Lake', 'soccer', 'mls', '180', 1520, 'Western', NULL),
('SJ', 'San Jose Earthquakes', 'San Jose', 'soccer', 'mls', '182', 1380, 'Western', NULL),
('SEA', 'Seattle Sounders FC', 'Seattle', 'soccer', 'mls', '184', 1520, 'Western', NULL),
('SKC', 'Sporting Kansas City', 'Sporting KC', 'soccer', 'mls', '177', 1440, 'Western', NULL),
('STL', 'St. Louis CITY SC', 'St. Louis', 'soccer', 'mls', '18169', 1480, 'Western', NULL),
('VAN', 'Vancouver Whitecaps FC', 'Vancouver', 'soccer', 'mls', '186', 1480, 'Western', NULL)

ON CONFLICT (team_code) DO UPDATE SET
    espn_team_id = EXCLUDED.espn_team_id,
    current_elo_rating = EXCLUDED.current_elo_rating,
    conference = EXCLUDED.conference,
    division = EXCLUDED.division,
    updated_at = CURRENT_TIMESTAMP;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    team_count INT;
    east_count INT;
    west_count INT;
BEGIN
    SELECT COUNT(*) INTO team_count FROM teams WHERE league = 'mls';

    IF team_count != 29 THEN
        RAISE EXCEPTION 'MLS seed failed: Expected 29 teams, found %', team_count;
    END IF;

    -- Check conference distribution
    SELECT COUNT(*) INTO east_count FROM teams WHERE league = 'mls' AND conference = 'Eastern';
    SELECT COUNT(*) INTO west_count FROM teams WHERE league = 'mls' AND conference = 'Western';

    IF east_count != 15 THEN
        RAISE EXCEPTION 'MLS seed failed: Expected 15 Eastern teams, found %', east_count;
    END IF;

    IF west_count != 14 THEN
        RAISE EXCEPTION 'MLS seed failed: Expected 14 Western teams, found %', west_count;
    END IF;

    -- Check all have ESPN IDs
    IF EXISTS (SELECT 1 FROM teams WHERE league = 'mls' AND espn_team_id IS NULL) THEN
        RAISE EXCEPTION 'MLS seed failed: Some teams missing ESPN IDs';
    END IF;

    -- Check Elo ratings in valid range
    IF EXISTS (SELECT 1 FROM teams WHERE league = 'mls' AND (current_elo_rating < 1000 OR current_elo_rating > 2000)) THEN
        RAISE EXCEPTION 'MLS seed failed: Elo ratings outside expected range (1000-2000)';
    END IF;

    RAISE NOTICE 'MLS seed successful: Loaded % teams (Eastern: %, Western: %)', team_count, east_count, west_count;
    RAISE NOTICE 'Elo range: % to %',
        (SELECT MIN(current_elo_rating) FROM teams WHERE league = 'mls'),
        (SELECT MAX(current_elo_rating) FROM teams WHERE league = 'mls');
END $$;
