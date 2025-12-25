-- Seed Data: MLB Teams with ESPN IDs
-- Date: 2025-12-24
-- Phase: 2 (Live Data Integration)
-- Purpose: Seed MLB teams with ESPN team IDs for prediction market coverage
-- Related: ADR-029 (ESPN Data Model), REQ-DATA-003 (Multi-Sport Support)

-- ============================================================================
-- MLB TEAMS - ALL 30 TEAMS (2024 SEASON)
-- ============================================================================
-- Initial Elo: 1500 = average, ~1600 = playoff contender, ~1400 = rebuilding
-- ESPN IDs verified against ESPN API

INSERT INTO teams (team_code, team_name, display_name, sport, league, espn_team_id, current_elo_rating, conference, division) VALUES

-- AMERICAN LEAGUE EAST (5 Teams)
('NYY', 'New York Yankees', 'Yankees', 'mlb', 'mlb', '10', 1580, 'AL', 'AL East'),
('BOS', 'Boston Red Sox', 'Red Sox', 'mlb', 'mlb', '2', 1500, 'AL', 'AL East'),
('BAL', 'Baltimore Orioles', 'Orioles', 'mlb', 'mlb', '1', 1560, 'AL', 'AL East'),
('TB', 'Tampa Bay Rays', 'Rays', 'mlb', 'mlb', '30', 1520, 'AL', 'AL East'),
('TOR', 'Toronto Blue Jays', 'Blue Jays', 'mlb', 'mlb', '14', 1480, 'AL', 'AL East'),

-- AMERICAN LEAGUE CENTRAL (5 Teams)
('CLE', 'Cleveland Guardians', 'Guardians', 'mlb', 'mlb', '5', 1540, 'AL', 'AL Central'),
('MIN', 'Minnesota Twins', 'Twins', 'mlb', 'mlb', '9', 1520, 'AL', 'AL Central'),
('DET', 'Detroit Tigers', 'Tigers', 'mlb', 'mlb', '6', 1500, 'AL', 'AL Central'),
('KC', 'Kansas City Royals', 'Royals', 'mlb', 'mlb', '7', 1500, 'AL', 'AL Central'),
('CWS', 'Chicago White Sox', 'White Sox', 'mlb', 'mlb', '4', 1380, 'AL', 'AL Central'),

-- AMERICAN LEAGUE WEST (5 Teams)
('HOU', 'Houston Astros', 'Astros', 'mlb', 'mlb', '18', 1560, 'AL', 'AL West'),
('TEX', 'Texas Rangers', 'Rangers', 'mlb', 'mlb', '13', 1520, 'AL', 'AL West'),
('SEA', 'Seattle Mariners', 'Mariners', 'mlb', 'mlb', '12', 1520, 'AL', 'AL West'),
('LAA', 'Los Angeles Angels', 'Angels', 'mlb', 'mlb', '3', 1440, 'AL', 'AL West'),
('OAK', 'Oakland Athletics', 'Athletics', 'mlb', 'mlb', '11', 1400, 'AL', 'AL West'),

-- NATIONAL LEAGUE EAST (5 Teams)
('ATL', 'Atlanta Braves', 'Braves', 'mlb', 'mlb', '15', 1580, 'NL', 'NL East'),
('PHI', 'Philadelphia Phillies', 'Phillies', 'mlb', 'mlb', '22', 1580, 'NL', 'NL East'),
('NYM', 'New York Mets', 'Mets', 'mlb', 'mlb', '21', 1540, 'NL', 'NL East'),
('MIA', 'Miami Marlins', 'Marlins', 'mlb', 'mlb', '28', 1420, 'NL', 'NL East'),
('WSH', 'Washington Nationals', 'Nationals', 'mlb', 'mlb', '20', 1440, 'NL', 'NL East'),

-- NATIONAL LEAGUE CENTRAL (5 Teams)
('MIL', 'Milwaukee Brewers', 'Brewers', 'mlb', 'mlb', '8', 1560, 'NL', 'NL Central'),
('CHC', 'Chicago Cubs', 'Cubs', 'mlb', 'mlb', '16', 1500, 'NL', 'NL Central'),
('STL', 'St. Louis Cardinals', 'Cardinals', 'mlb', 'mlb', '24', 1480, 'NL', 'NL Central'),
('CIN', 'Cincinnati Reds', 'Reds', 'mlb', 'mlb', '17', 1480, 'NL', 'NL Central'),
('PIT', 'Pittsburgh Pirates', 'Pirates', 'mlb', 'mlb', '23', 1440, 'NL', 'NL Central'),

-- NATIONAL LEAGUE WEST (5 Teams)
('LAD', 'Los Angeles Dodgers', 'Dodgers', 'mlb', 'mlb', '19', 1620, 'NL', 'NL West'),
('SD', 'San Diego Padres', 'Padres', 'mlb', 'mlb', '25', 1540, 'NL', 'NL West'),
('ARI', 'Arizona Diamondbacks', 'D-backs', 'mlb', 'mlb', '29', 1540, 'NL', 'NL West'),
('SF', 'San Francisco Giants', 'Giants', 'mlb', 'mlb', '26', 1480, 'NL', 'NL West'),
('COL', 'Colorado Rockies', 'Rockies', 'mlb', 'mlb', '27', 1400, 'NL', 'NL West')

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
