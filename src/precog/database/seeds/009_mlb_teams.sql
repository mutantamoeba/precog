-- Seed Data: MLB Teams with ESPN IDs
-- Date: 2025-12-25
-- Phase: 2 (Live Data Integration)
-- Purpose: Seed MLB teams with ESPN team IDs for prediction market coverage
-- Related: ADR-029 (ESPN Data Model), REQ-DATA-003 (Multi-Sport Support)
-- Source: ESPN API (https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/teams)
-- Verified: 2025-12-25

-- ============================================================================
-- MLB TEAMS - ALL 30 TEAMS (2025 SEASON)
-- ============================================================================
-- Initial Elo: Estimated based on 2024 performance (not from FiveThirtyEight)
-- ESPN IDs: VERIFIED against actual ESPN API on 2025-12-25
-- Note: Oakland Athletics now listed as "Athletics" (moving to Sacramento)

INSERT INTO teams (team_code, team_name, display_name, sport, league, sport_id, league_id, espn_team_id, current_elo_rating, conference, division) VALUES

-- AMERICAN LEAGUE EAST (5 Teams)
('NYY', 'New York Yankees', 'Yankees', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '10', 1580, 'AL', 'AL East'),
('BOS', 'Boston Red Sox', 'Red Sox', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '2', 1500, 'AL', 'AL East'),
('BAL', 'Baltimore Orioles', 'Orioles', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '1', 1560, 'AL', 'AL East'),
('TB', 'Tampa Bay Rays', 'Rays', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '30', 1520, 'AL', 'AL East'),
('TOR', 'Toronto Blue Jays', 'Blue Jays', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '14', 1480, 'AL', 'AL East'),

-- AMERICAN LEAGUE CENTRAL (5 Teams)
('CLE', 'Cleveland Guardians', 'Guardians', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '5', 1540, 'AL', 'AL Central'),
('MIN', 'Minnesota Twins', 'Twins', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '9', 1520, 'AL', 'AL Central'),
('DET', 'Detroit Tigers', 'Tigers', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '6', 1500, 'AL', 'AL Central'),
('KC', 'Kansas City Royals', 'Royals', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '7', 1500, 'AL', 'AL Central'),
('CWS', 'Chicago White Sox', 'White Sox', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '4', 1380, 'AL', 'AL Central'),

-- AMERICAN LEAGUE WEST (5 Teams)
('HOU', 'Houston Astros', 'Astros', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '18', 1560, 'AL', 'AL West'),
('TEX', 'Texas Rangers', 'Rangers', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '13', 1520, 'AL', 'AL West'),
('SEA', 'Seattle Mariners', 'Mariners', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '12', 1520, 'AL', 'AL West'),
('LAA', 'Los Angeles Angels', 'Angels', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '3', 1440, 'AL', 'AL West'),
('OAK', 'Oakland Athletics', 'Athletics', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '11', 1400, 'AL', 'AL West'),

-- NATIONAL LEAGUE EAST (5 Teams)
('ATL', 'Atlanta Braves', 'Braves', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '15', 1580, 'NL', 'NL East'),
('PHI', 'Philadelphia Phillies', 'Phillies', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '22', 1580, 'NL', 'NL East'),
('NYM', 'New York Mets', 'Mets', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '21', 1540, 'NL', 'NL East'),
('MIA', 'Miami Marlins', 'Marlins', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '28', 1420, 'NL', 'NL East'),
('WSH', 'Washington Nationals', 'Nationals', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '20', 1440, 'NL', 'NL East'),

-- NATIONAL LEAGUE CENTRAL (5 Teams)
('MIL', 'Milwaukee Brewers', 'Brewers', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '8', 1560, 'NL', 'NL Central'),
('CHC', 'Chicago Cubs', 'Cubs', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '16', 1500, 'NL', 'NL Central'),
('STL', 'St. Louis Cardinals', 'Cardinals', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '24', 1480, 'NL', 'NL Central'),
('CIN', 'Cincinnati Reds', 'Reds', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '17', 1480, 'NL', 'NL Central'),
('PIT', 'Pittsburgh Pirates', 'Pirates', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '23', 1440, 'NL', 'NL Central'),

-- NATIONAL LEAGUE WEST (5 Teams)
('LAD', 'Los Angeles Dodgers', 'Dodgers', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '19', 1620, 'NL', 'NL West'),
('SD', 'San Diego Padres', 'Padres', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '25', 1540, 'NL', 'NL West'),
('ARI', 'Arizona Diamondbacks', 'D-backs', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '29', 1540, 'NL', 'NL West'),
('SF', 'San Francisco Giants', 'Giants', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '26', 1480, 'NL', 'NL West'),
('COL', 'Colorado Rockies', 'Rockies', 'baseball', 'mlb', (SELECT id FROM sports WHERE sport_key = 'baseball'), (SELECT id FROM leagues WHERE league_key = 'mlb'), '27', 1400, 'NL', 'NL West')

ON CONFLICT (espn_team_id, league) WHERE espn_team_id IS NOT NULL DO UPDATE SET
    team_code = EXCLUDED.team_code,
    team_name = EXCLUDED.team_name,
    display_name = EXCLUDED.display_name,
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
    al_count INT;
    nl_count INT;
BEGIN
    SELECT COUNT(*) INTO team_count FROM teams WHERE league = 'mlb';

    IF team_count != 30 THEN
        RAISE EXCEPTION 'MLB seed failed: Expected 30 teams, found %', team_count;
    END IF;

    -- Check league distribution
    SELECT COUNT(*) INTO al_count FROM teams WHERE league = 'mlb' AND conference = 'AL';
    SELECT COUNT(*) INTO nl_count FROM teams WHERE league = 'mlb' AND conference = 'NL';

    IF al_count != 15 THEN
        RAISE EXCEPTION 'MLB seed failed: Expected 15 AL teams, found %', al_count;
    END IF;

    IF nl_count != 15 THEN
        RAISE EXCEPTION 'MLB seed failed: Expected 15 NL teams, found %', nl_count;
    END IF;

    -- Check all have ESPN IDs
    IF EXISTS (SELECT 1 FROM teams WHERE league = 'mlb' AND espn_team_id IS NULL) THEN
        RAISE EXCEPTION 'MLB seed failed: Some teams missing ESPN IDs';
    END IF;

    -- Check Elo ratings in valid range
    IF EXISTS (SELECT 1 FROM teams WHERE league = 'mlb' AND (current_elo_rating < 1000 OR current_elo_rating > 2000)) THEN
        RAISE EXCEPTION 'MLB seed failed: Elo ratings outside expected range (1000-2000)';
    END IF;

    RAISE NOTICE 'MLB seed successful: Loaded % teams (AL: %, NL: %)', team_count, al_count, nl_count;
    RAISE NOTICE 'Elo range: % to %',
        (SELECT MIN(current_elo_rating) FROM teams WHERE league = 'mlb'),
        (SELECT MAX(current_elo_rating) FROM teams WHERE league = 'mlb');
END $$;
