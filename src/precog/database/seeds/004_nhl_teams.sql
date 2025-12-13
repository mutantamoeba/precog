-- Seed Data: NHL Teams with ESPN IDs
-- Date: 2025-11-27
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
('BOS', 'Boston Bruins', 'Bruins', 'nhl', 'nhl', '1', 1580, 'Eastern', 'Atlantic'),
('BUF', 'Buffalo Sabres', 'Sabres', 'nhl', 'nhl', '2', 1420, 'Eastern', 'Atlantic'),
('DET', 'Detroit Red Wings', 'Red Wings', 'nhl', 'nhl', '5', 1480, 'Eastern', 'Atlantic'),
('FLA', 'Florida Panthers', 'Panthers', 'nhl', 'nhl', '26', 1640, 'Eastern', 'Atlantic'),
('MTL', 'Montreal Canadiens', 'Canadiens', 'nhl', 'nhl', '8', 1420, 'Eastern', 'Atlantic'),
('OTT', 'Ottawa Senators', 'Senators', 'nhl', 'nhl', '9', 1460, 'Eastern', 'Atlantic'),
('TBL', 'Tampa Bay Lightning', 'Lightning', 'nhl', 'nhl', '14', 1560, 'Eastern', 'Atlantic'),
('TOR', 'Toronto Maple Leafs', 'Maple Leafs', 'nhl', 'nhl', '10', 1580, 'Eastern', 'Atlantic'),

-- EASTERN CONFERENCE - Metropolitan Division
('CAR', 'Carolina Hurricanes', 'Hurricanes', 'nhl', 'nhl', '7', 1600, 'Eastern', 'Metropolitan'),
('CBJ', 'Columbus Blue Jackets', 'Blue Jackets', 'nhl', 'nhl', '29', 1400, 'Eastern', 'Metropolitan'),
('NJD', 'New Jersey Devils', 'Devils', 'nhl', 'nhl', '1', 1540, 'Eastern', 'Metropolitan'),
('NYI', 'New York Islanders', 'Islanders', 'nhl', 'nhl', '2', 1480, 'Eastern', 'Metropolitan'),
('NYR', 'New York Rangers', 'Rangers', 'nhl', 'nhl', '3', 1600, 'Eastern', 'Metropolitan'),
('PHI', 'Philadelphia Flyers', 'Flyers', 'nhl', 'nhl', '4', 1440, 'Eastern', 'Metropolitan'),
('PIT', 'Pittsburgh Penguins', 'Penguins', 'nhl', 'nhl', '5', 1500, 'Eastern', 'Metropolitan'),
('WSH', 'Washington Capitals', 'Capitals', 'nhl', 'nhl', '15', 1540, 'Eastern', 'Metropolitan'),

-- WESTERN CONFERENCE - Central Division
-- Utah Hockey Club (formerly Arizona Coyotes, relocated 2024)
-- ESPN uses team_id 129764 with code 'UTA' after relocation
('UTA', 'Utah Hockey Club', 'Utah HC', 'nhl', 'nhl', '129764', 1380, 'Western', 'Central'),
('CHI', 'Chicago Blackhawks', 'Blackhawks', 'nhl', 'nhl', '16', 1360, 'Western', 'Central'),
('COL', 'Colorado Avalanche', 'Avalanche', 'nhl', 'nhl', '17', 1580, 'Western', 'Central'),
('DAL', 'Dallas Stars', 'Stars', 'nhl', 'nhl', '25', 1600, 'Western', 'Central'),
('MIN', 'Minnesota Wild', 'Wild', 'nhl', 'nhl', '30', 1540, 'Western', 'Central'),
('NSH', 'Nashville Predators', 'Predators', 'nhl', 'nhl', '18', 1480, 'Western', 'Central'),
('STL', 'St. Louis Blues', 'Blues', 'nhl', 'nhl', '19', 1480, 'Western', 'Central'),
('WPG', 'Winnipeg Jets', 'Jets', 'nhl', 'nhl', '52', 1620, 'Western', 'Central'),

-- WESTERN CONFERENCE - Pacific Division
('ANA', 'Anaheim Ducks', 'Ducks', 'nhl', 'nhl', '24', 1380, 'Western', 'Pacific'),
('CGY', 'Calgary Flames', 'Flames', 'nhl', 'nhl', '20', 1460, 'Western', 'Pacific'),
('EDM', 'Edmonton Oilers', 'Oilers', 'nhl', 'nhl', '22', 1620, 'Western', 'Pacific'),
('LAK', 'Los Angeles Kings', 'Kings', 'nhl', 'nhl', '26', 1540, 'Western', 'Pacific'),
('SJS', 'San Jose Sharks', 'Sharks', 'nhl', 'nhl', '28', 1340, 'Western', 'Pacific'),
-- Seattle Kraken ESPN ID updated from 55 to 124292 per ESPN API
('SEA', 'Seattle Kraken', 'Kraken', 'nhl', 'nhl', '124292', 1460, 'Western', 'Pacific'),
('VAN', 'Vancouver Canucks', 'Canucks', 'nhl', 'nhl', '23', 1560, 'Western', 'Pacific'),
('VGK', 'Vegas Golden Knights', 'Golden Knights', 'nhl', 'nhl', '54', 1600, 'Western', 'Pacific');

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
