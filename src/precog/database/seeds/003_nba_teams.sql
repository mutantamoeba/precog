-- Seed Data: NBA Teams with ESPN IDs
-- Date: 2025-11-27
-- Phase: 2 (Live Data Integration)
-- Purpose: Seed 30 NBA teams with ESPN team IDs for live game data integration
-- Related: ADR-029 (ESPN Data Model), REQ-DATA-003 (Multi-Sport Support)

-- ============================================================================
-- NBA TEAMS (30 Teams)
-- ============================================================================
-- ESPN team IDs sourced from ESPN API
-- Initial Elo: 1500 = league average, adjusted based on 2024-25 season performance
-- Scale: ~1650 = championship contender, ~1350 = rebuilding

INSERT INTO teams (team_code, team_name, display_name, sport, league, espn_team_id, current_elo_rating, conference, division) VALUES

-- EASTERN CONFERENCE - Atlantic Division
('BOS', 'Boston Celtics', 'Celtics', 'nba', 'nba', '2', 1660, 'Eastern', 'Atlantic'),
('BKN', 'Brooklyn Nets', 'Nets', 'nba', 'nba', '17', 1420, 'Eastern', 'Atlantic'),
('NYK', 'New York Knicks', 'Knicks', 'nba', 'nba', '18', 1580, 'Eastern', 'Atlantic'),
('PHI', 'Philadelphia 76ers', '76ers', 'nba', 'nba', '20', 1520, 'Eastern', 'Atlantic'),
('TOR', 'Toronto Raptors', 'Raptors', 'nba', 'nba', '28', 1400, 'Eastern', 'Atlantic'),

-- EASTERN CONFERENCE - Central Division
('CHI', 'Chicago Bulls', 'Bulls', 'nba', 'nba', '4', 1450, 'Eastern', 'Central'),
('CLE', 'Cleveland Cavaliers', 'Cavaliers', 'nba', 'nba', '5', 1620, 'Eastern', 'Central'),
('DET', 'Detroit Pistons', 'Pistons', 'nba', 'nba', '8', 1380, 'Eastern', 'Central'),
('IND', 'Indiana Pacers', 'Pacers', 'nba', 'nba', '11', 1540, 'Eastern', 'Central'),
('MIL', 'Milwaukee Bucks', 'Bucks', 'nba', 'nba', '15', 1600, 'Eastern', 'Central'),

-- EASTERN CONFERENCE - Southeast Division
('ATL', 'Atlanta Hawks', 'Hawks', 'nba', 'nba', '1', 1460, 'Eastern', 'Southeast'),
('CHA', 'Charlotte Hornets', 'Hornets', 'nba', 'nba', '30', 1380, 'Eastern', 'Southeast'),
('MIA', 'Miami Heat', 'Heat', 'nba', 'nba', '14', 1520, 'Eastern', 'Southeast'),
('ORL', 'Orlando Magic', 'Magic', 'nba', 'nba', '19', 1560, 'Eastern', 'Southeast'),
('WAS', 'Washington Wizards', 'Wizards', 'nba', 'nba', '27', 1350, 'Eastern', 'Southeast'),

-- WESTERN CONFERENCE - Northwest Division
('DEN', 'Denver Nuggets', 'Nuggets', 'nba', 'nba', '7', 1600, 'Western', 'Northwest'),
('MIN', 'Minnesota Timberwolves', 'Timberwolves', 'nba', 'nba', '16', 1580, 'Western', 'Northwest'),
('OKC', 'Oklahoma City Thunder', 'Thunder', 'nba', 'nba', '25', 1640, 'Western', 'Northwest'),
('POR', 'Portland Trail Blazers', 'Trail Blazers', 'nba', 'nba', '22', 1380, 'Western', 'Northwest'),
('UTA', 'Utah Jazz', 'Jazz', 'nba', 'nba', '26', 1400, 'Western', 'Northwest'),

-- WESTERN CONFERENCE - Pacific Division
('GSW', 'Golden State Warriors', 'Warriors', 'nba', 'nba', '9', 1540, 'Western', 'Pacific'),
('LAC', 'LA Clippers', 'Clippers', 'nba', 'nba', '12', 1500, 'Western', 'Pacific'),
('LAL', 'Los Angeles Lakers', 'Lakers', 'nba', 'nba', '13', 1540, 'Western', 'Pacific'),
('PHX', 'Phoenix Suns', 'Suns', 'nba', 'nba', '21', 1520, 'Western', 'Pacific'),
('SAC', 'Sacramento Kings', 'Kings', 'nba', 'nba', '23', 1500, 'Western', 'Pacific'),

-- WESTERN CONFERENCE - Southwest Division
('DAL', 'Dallas Mavericks', 'Mavericks', 'nba', 'nba', '6', 1560, 'Western', 'Southwest'),
('HOU', 'Houston Rockets', 'Rockets', 'nba', 'nba', '10', 1520, 'Western', 'Southwest'),
('MEM', 'Memphis Grizzlies', 'Grizzlies', 'nba', 'nba', '29', 1480, 'Western', 'Southwest'),
('NOP', 'New Orleans Pelicans', 'Pelicans', 'nba', 'nba', '3', 1460, 'Western', 'Southwest'),
('SAS', 'San Antonio Spurs', 'Spurs', 'nba', 'nba', '24', 1420, 'Western', 'Southwest');

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    team_count INT;
    eastern_count INT;
    western_count INT;
BEGIN
    SELECT COUNT(*) INTO team_count FROM teams WHERE league = 'nba';

    IF team_count != 30 THEN
        RAISE EXCEPTION 'NBA seed failed: Expected 30 teams, found %', team_count;
    END IF;

    -- Check conference distribution
    SELECT COUNT(*) INTO eastern_count FROM teams WHERE league = 'nba' AND conference = 'Eastern';
    SELECT COUNT(*) INTO western_count FROM teams WHERE league = 'nba' AND conference = 'Western';

    IF eastern_count != 15 THEN
        RAISE EXCEPTION 'NBA seed failed: Expected 15 Eastern teams, found %', eastern_count;
    END IF;

    IF western_count != 15 THEN
        RAISE EXCEPTION 'NBA seed failed: Expected 15 Western teams, found %', western_count;
    END IF;

    -- Check all have ESPN IDs
    IF EXISTS (SELECT 1 FROM teams WHERE league = 'nba' AND espn_team_id IS NULL) THEN
        RAISE EXCEPTION 'NBA seed failed: Some teams missing ESPN IDs';
    END IF;

    -- Check Elo ratings in valid range
    IF EXISTS (SELECT 1 FROM teams WHERE league = 'nba' AND (current_elo_rating < 1000 OR current_elo_rating > 2000)) THEN
        RAISE EXCEPTION 'NBA seed failed: Elo ratings outside expected range (1000-2000)';
    END IF;

    RAISE NOTICE 'NBA seed successful: Loaded 30 teams (15 Eastern, 15 Western)';
    RAISE NOTICE 'Elo range: % to %',
        (SELECT MIN(current_elo_rating) FROM teams WHERE league = 'nba'),
        (SELECT MAX(current_elo_rating) FROM teams WHERE league = 'nba');
END $$;
