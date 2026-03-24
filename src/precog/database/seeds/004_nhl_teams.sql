-- Seed Data: NHL Teams with ESPN IDs
-- Date: 2025-11-27 (ESPN IDs corrected 2026-03-11 via fix_espn_team_ids.py audit)
-- Phase: 2 (Live Data Integration)
-- Purpose: Seed 32 NHL teams with ESPN team IDs for live game data integration
-- Related: ADR-029 (ESPN Data Model), REQ-DATA-003 (Multi-Sport Support)

-- ============================================================================
-- NHL TEAMS (32 Teams)
-- ============================================================================
-- ESPN team IDs sourced from ESPN API
-- Initial Elo: 1500 = league average, adjusted based on 2024-25 season performance
-- Scale: ~1650 = Stanley Cup contender, ~1350 = rebuilding

INSERT INTO teams (team_code, team_name, display_name, sport, league, espn_team_id, current_elo_rating, conference, division) VALUES

-- EASTERN CONFERENCE - Atlantic Division
-- ESPN IDs verified against ESPN API 2026-03-11
('BOS', 'Boston Bruins', 'Bruins', 'hockey', 'nhl', '1', 1580, 'Eastern', 'Atlantic'),
('BUF', 'Buffalo Sabres', 'Sabres', 'hockey', 'nhl', '2', 1420, 'Eastern', 'Atlantic'),
('DET', 'Detroit Red Wings', 'Red Wings', 'hockey', 'nhl', '5', 1480, 'Eastern', 'Atlantic'),
('FLA', 'Florida Panthers', 'Panthers', 'hockey', 'nhl', '26', 1640, 'Eastern', 'Atlantic'),
('MTL', 'Montreal Canadiens', 'Canadiens', 'hockey', 'nhl', '10', 1420, 'Eastern', 'Atlantic'),
('OTT', 'Ottawa Senators', 'Senators', 'hockey', 'nhl', '14', 1460, 'Eastern', 'Atlantic'),
('TBL', 'Tampa Bay Lightning', 'Lightning', 'hockey', 'nhl', '20', 1560, 'Eastern', 'Atlantic'),
('TOR', 'Toronto Maple Leafs', 'Maple Leafs', 'hockey', 'nhl', '21', 1580, 'Eastern', 'Atlantic'),

-- EASTERN CONFERENCE - Metropolitan Division
('CAR', 'Carolina Hurricanes', 'Hurricanes', 'hockey', 'nhl', '7', 1600, 'Eastern', 'Metropolitan'),
('CBJ', 'Columbus Blue Jackets', 'Blue Jackets', 'hockey', 'nhl', '29', 1400, 'Eastern', 'Metropolitan'),
('NJD', 'New Jersey Devils', 'Devils', 'hockey', 'nhl', '11', 1540, 'Eastern', 'Metropolitan'),
('NYI', 'New York Islanders', 'Islanders', 'hockey', 'nhl', '12', 1480, 'Eastern', 'Metropolitan'),
('NYR', 'New York Rangers', 'Rangers', 'hockey', 'nhl', '13', 1600, 'Eastern', 'Metropolitan'),
('PHI', 'Philadelphia Flyers', 'Flyers', 'hockey', 'nhl', '15', 1440, 'Eastern', 'Metropolitan'),
('PIT', 'Pittsburgh Penguins', 'Penguins', 'hockey', 'nhl', '16', 1500, 'Eastern', 'Metropolitan'),
('WSH', 'Washington Capitals', 'Capitals', 'hockey', 'nhl', '23', 1540, 'Eastern', 'Metropolitan'),

-- WESTERN CONFERENCE - Central Division
-- Utah Hockey Club (formerly Arizona Coyotes, relocated 2024)
-- ESPN uses team_id 129764 with code 'UTA' after relocation
('UTA', 'Utah Hockey Club', 'Utah HC', 'hockey', 'nhl', '129764', 1380, 'Western', 'Central'),
('CHI', 'Chicago Blackhawks', 'Blackhawks', 'hockey', 'nhl', '4', 1360, 'Western', 'Central'),
('COL', 'Colorado Avalanche', 'Avalanche', 'hockey', 'nhl', '17', 1580, 'Western', 'Central'),
('DAL', 'Dallas Stars', 'Stars', 'hockey', 'nhl', '9', 1600, 'Western', 'Central'),
('MIN', 'Minnesota Wild', 'Wild', 'hockey', 'nhl', '30', 1540, 'Western', 'Central'),
('NSH', 'Nashville Predators', 'Predators', 'hockey', 'nhl', '27', 1480, 'Western', 'Central'),
('STL', 'St. Louis Blues', 'Blues', 'hockey', 'nhl', '19', 1480, 'Western', 'Central'),
('WPG', 'Winnipeg Jets', 'Jets', 'hockey', 'nhl', '28', 1620, 'Western', 'Central'),

-- WESTERN CONFERENCE - Pacific Division
('ANA', 'Anaheim Ducks', 'Ducks', 'hockey', 'nhl', '25', 1380, 'Western', 'Pacific'),
('CGY', 'Calgary Flames', 'Flames', 'hockey', 'nhl', '3', 1460, 'Western', 'Pacific'),
('EDM', 'Edmonton Oilers', 'Oilers', 'hockey', 'nhl', '6', 1620, 'Western', 'Pacific'),
('LAK', 'Los Angeles Kings', 'Kings', 'hockey', 'nhl', '8', 1540, 'Western', 'Pacific'),
('SJS', 'San Jose Sharks', 'Sharks', 'hockey', 'nhl', '18', 1340, 'Western', 'Pacific'),
('SEA', 'Seattle Kraken', 'Kraken', 'hockey', 'nhl', '124292', 1460, 'Western', 'Pacific'),
('VAN', 'Vancouver Canucks', 'Canucks', 'hockey', 'nhl', '22', 1560, 'Western', 'Pacific'),
('VGK', 'Vegas Golden Knights', 'Golden Knights', 'hockey', 'nhl', '37', 1600, 'Western', 'Pacific');

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    team_count INT;
    eastern_count INT;
    western_count INT;
BEGIN
    SELECT COUNT(*) INTO team_count FROM teams WHERE league = 'nhl';

    IF team_count != 32 THEN
        RAISE EXCEPTION 'NHL seed failed: Expected 32 teams, found %', team_count;
    END IF;

    -- Check conference distribution
    SELECT COUNT(*) INTO eastern_count FROM teams WHERE league = 'nhl' AND conference = 'Eastern';
    SELECT COUNT(*) INTO western_count FROM teams WHERE league = 'nhl' AND conference = 'Western';

    IF eastern_count != 16 THEN
        RAISE EXCEPTION 'NHL seed failed: Expected 16 Eastern teams, found %', eastern_count;
    END IF;

    IF western_count != 16 THEN
        RAISE EXCEPTION 'NHL seed failed: Expected 16 Western teams, found %', western_count;
    END IF;

    -- Check all have ESPN IDs
    IF EXISTS (SELECT 1 FROM teams WHERE league = 'nhl' AND espn_team_id IS NULL) THEN
        RAISE EXCEPTION 'NHL seed failed: Some teams missing ESPN IDs';
    END IF;

    -- Check Elo ratings in valid range
    IF EXISTS (SELECT 1 FROM teams WHERE league = 'nhl' AND (current_elo_rating < 1000 OR current_elo_rating > 2000)) THEN
        RAISE EXCEPTION 'NHL seed failed: Elo ratings outside expected range (1000-2000)';
    END IF;

    RAISE NOTICE 'NHL seed successful: Loaded 32 teams (16 Eastern, 16 Western)';
    RAISE NOTICE 'Elo range: % to %',
        (SELECT MIN(current_elo_rating) FROM teams WHERE league = 'nhl'),
        (SELECT MAX(current_elo_rating) FROM teams WHERE league = 'nhl');
END $$;
