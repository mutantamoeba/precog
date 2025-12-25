-- Seed Data: MLS Teams with ESPN IDs
-- Date: 2025-12-25
-- Phase: 2 (Live Data Integration)
-- Purpose: Seed MLS teams with ESPN team IDs for prediction market coverage
-- Related: ADR-029 (ESPN Data Model), REQ-DATA-003 (Multi-Sport Support)
-- Source: ESPN API (https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/teams)
-- Verified: 2025-12-25

-- ============================================================================
-- MLS TEAMS - ALL 30 TEAMS (2025 SEASON)
-- ============================================================================
-- Initial Elo: 1500 = average (placeholder - real Elo requires game history)
-- ESPN IDs: VERIFIED against actual ESPN API on 2025-12-25
-- Note: San Diego FC added as expansion team for 2025

INSERT INTO teams (team_code, team_name, display_name, sport, league, espn_team_id, current_elo_rating, conference, division) VALUES

-- EASTERN CONFERENCE (15 Teams)
('ATL', 'Atlanta United FC', 'Atlanta United', 'soccer', 'mls', '18418', 1500, 'Eastern', NULL),
('CLT', 'Charlotte FC', 'Charlotte FC', 'soccer', 'mls', '21300', 1500, 'Eastern', NULL),
('CHI', 'Chicago Fire FC', 'Chicago Fire', 'soccer', 'mls', '182', 1500, 'Eastern', NULL),
('CIN', 'FC Cincinnati', 'FC Cincinnati', 'soccer', 'mls', '18267', 1500, 'Eastern', NULL),
('CLB', 'Columbus Crew', 'Columbus Crew', 'soccer', 'mls', '183', 1500, 'Eastern', NULL),
('DC', 'D.C. United', 'D.C. United', 'soccer', 'mls', '193', 1500, 'Eastern', NULL),
('MIA', 'Inter Miami CF', 'Inter Miami', 'soccer', 'mls', '20232', 1500, 'Eastern', NULL),
('MTL', 'CF Montréal', 'CF Montréal', 'soccer', 'mls', '9720', 1500, 'Eastern', NULL),
('NE', 'New England Revolution', 'New England', 'soccer', 'mls', '189', 1500, 'Eastern', NULL),
('NY', 'New York Red Bulls', 'NY Red Bulls', 'soccer', 'mls', '190', 1500, 'Eastern', NULL),
('NYC', 'New York City FC', 'NYCFC', 'soccer', 'mls', '17606', 1500, 'Eastern', NULL),
('ORL', 'Orlando City SC', 'Orlando City', 'soccer', 'mls', '12011', 1500, 'Eastern', NULL),
('PHI', 'Philadelphia Union', 'Philadelphia', 'soccer', 'mls', '10739', 1500, 'Eastern', NULL),
('TOR', 'Toronto FC', 'Toronto FC', 'soccer', 'mls', '7318', 1500, 'Eastern', NULL),
('NSH', 'Nashville SC', 'Nashville', 'soccer', 'mls', '18986', 1500, 'Eastern', NULL),

-- WESTERN CONFERENCE (15 Teams - includes San Diego FC for 2025)
('ATX', 'Austin FC', 'Austin FC', 'soccer', 'mls', '20906', 1500, 'Western', NULL),
('COL', 'Colorado Rapids', 'Colorado', 'soccer', 'mls', '184', 1500, 'Western', NULL),
('DAL', 'FC Dallas', 'FC Dallas', 'soccer', 'mls', '185', 1500, 'Western', NULL),
('HOU', 'Houston Dynamo FC', 'Houston', 'soccer', 'mls', '6077', 1500, 'Western', NULL),
('LA', 'LA Galaxy', 'LA Galaxy', 'soccer', 'mls', '187', 1500, 'Western', NULL),
('LAFC', 'Los Angeles FC', 'LAFC', 'soccer', 'mls', '18966', 1500, 'Western', NULL),
('MIN', 'Minnesota United FC', 'Minnesota', 'soccer', 'mls', '17362', 1500, 'Western', NULL),
('POR', 'Portland Timbers', 'Portland', 'soccer', 'mls', '9723', 1500, 'Western', NULL),
('RSL', 'Real Salt Lake', 'Real Salt Lake', 'soccer', 'mls', '4771', 1500, 'Western', NULL),
('SD', 'San Diego FC', 'San Diego FC', 'soccer', 'mls', '22529', 1500, 'Western', NULL),
('SJ', 'San Jose Earthquakes', 'San Jose', 'soccer', 'mls', '191', 1500, 'Western', NULL),
('SEA', 'Seattle Sounders FC', 'Seattle', 'soccer', 'mls', '9726', 1500, 'Western', NULL),
('SKC', 'Sporting Kansas City', 'Sporting KC', 'soccer', 'mls', '186', 1500, 'Western', NULL),
('STL', 'St. Louis CITY SC', 'St. Louis', 'soccer', 'mls', '21812', 1500, 'Western', NULL),
('VAN', 'Vancouver Whitecaps FC', 'Vancouver', 'soccer', 'mls', '9727', 1500, 'Western', NULL)

ON CONFLICT (team_code, sport) DO UPDATE SET
    espn_team_id = EXCLUDED.espn_team_id,
    team_name = EXCLUDED.team_name,
    display_name = EXCLUDED.display_name,
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

    IF team_count != 30 THEN
        RAISE EXCEPTION 'MLS seed failed: Expected 30 teams, found %', team_count;
    END IF;

    -- Check conference distribution
    SELECT COUNT(*) INTO east_count FROM teams WHERE league = 'mls' AND conference = 'Eastern';
    SELECT COUNT(*) INTO west_count FROM teams WHERE league = 'mls' AND conference = 'Western';

    IF east_count != 15 THEN
        RAISE EXCEPTION 'MLS seed failed: Expected 15 Eastern teams, found %', east_count;
    END IF;

    IF west_count != 15 THEN
        RAISE EXCEPTION 'MLS seed failed: Expected 15 Western teams, found %', west_count;
    END IF;

    -- Check all have ESPN IDs
    IF EXISTS (SELECT 1 FROM teams WHERE league = 'mls' AND espn_team_id IS NULL) THEN
        RAISE EXCEPTION 'MLS seed failed: Some teams missing ESPN IDs';
    END IF;

    RAISE NOTICE 'MLS seed successful: Loaded % teams (Eastern: %, Western: %)', team_count, east_count, west_count;
END $$;
