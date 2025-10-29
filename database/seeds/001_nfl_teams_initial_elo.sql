-- Seed Data: NFL Teams with Initial Elo Ratings
-- Date: 2025-10-24
-- Phase: 4 (Elo Model - Preparation)
-- Purpose: Seed 32 NFL teams with initial Elo ratings based on 2024 season performance

-- ============================================================================
-- INITIAL ELO RATINGS (2024 Season-End Estimates)
-- ============================================================================
-- Based on 2024 regular season performance and playoff results
-- Scale: 1500 = league average, ~1650 = elite, ~1350 = rebuilding

INSERT INTO teams (team_code, team_name, sport, current_elo_rating, conference, division) VALUES

-- AFC EAST
('BUF', 'Buffalo Bills', 'nfl', 1620, 'AFC', 'East'),
('MIA', 'Miami Dolphins', 'nfl', 1540, 'AFC', 'East'),
('NYJ', 'New York Jets', 'nfl', 1460, 'AFC', 'East'),
('NE', 'New England Patriots', 'nfl', 1380, 'AFC', 'East'),

-- AFC NORTH
('BAL', 'Baltimore Ravens', 'nfl', 1610, 'AFC', 'North'),
('CIN', 'Cincinnati Bengals', 'nfl', 1550, 'AFC', 'North'),
('PIT', 'Pittsburgh Steelers', 'nfl', 1520, 'AFC', 'North'),
('CLE', 'Cleveland Browns', 'nfl', 1440, 'AFC', 'North'),

-- AFC SOUTH
('HOU', 'Houston Texans', 'nfl', 1540, 'AFC', 'South'),
('IND', 'Indianapolis Colts', 'nfl', 1480, 'AFC', 'South'),
('JAX', 'Jacksonville Jaguars', 'nfl', 1420, 'AFC', 'South'),
('TEN', 'Tennessee Titans', 'nfl', 1400, 'AFC', 'South'),

-- AFC WEST
('KC', 'Kansas City Chiefs', 'nfl', 1660, 'AFC', 'West'),
('LAC', 'Los Angeles Chargers', 'nfl', 1520, 'AFC', 'West'),
('LV', 'Las Vegas Raiders', 'nfl', 1430, 'AFC', 'West'),
('DEN', 'Denver Broncos', 'nfl', 1450, 'AFC', 'West'),

-- NFC EAST
('PHI', 'Philadelphia Eagles', 'nfl', 1580, 'NFC', 'East'),
('DAL', 'Dallas Cowboys', 'nfl', 1550, 'NFC', 'East'),
('WAS', 'Washington Commanders', 'nfl', 1490, 'NFC', 'East'),
('NYG', 'New York Giants', 'nfl', 1400, 'NFC', 'East'),

-- NFC NORTH
('DET', 'Detroit Lions', 'nfl', 1600, 'NFC', 'North'),
('GB', 'Green Bay Packers', 'nfl', 1560, 'NFC', 'North'),
('MIN', 'Minnesota Vikings', 'nfl', 1530, 'NFC', 'North'),
('CHI', 'Chicago Bears', 'nfl', 1440, 'NFC', 'North'),

-- NFC SOUTH
('TB', 'Tampa Bay Buccaneers', 'nfl', 1520, 'NFC', 'South'),
('ATL', 'Atlanta Falcons', 'nfl', 1480, 'NFC', 'South'),
('NO', 'New Orleans Saints', 'nfl', 1460, 'NFC', 'South'),
('CAR', 'Carolina Panthers', 'nfl', 1370, 'NFC', 'South'),

-- NFC WEST
('SF', 'San Francisco 49ers', 'nfl', 1630, 'NFC', 'West'),
('LAR', 'Los Angeles Rams', 'nfl', 1540, 'NFC', 'West'),
('SEA', 'Seattle Seahawks', 'nfl', 1500, 'NFC', 'West'),
('ARI', 'Arizona Cardinals', 'nfl', 1430, 'NFC', 'West');

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    team_count INT;
BEGIN
    SELECT COUNT(*) INTO team_count FROM teams WHERE sport = 'nfl';

    IF team_count != 32 THEN
        RAISE EXCEPTION 'NFL seed failed: Expected 32 teams, found %', team_count;
    END IF;

    -- Check all conferences populated
    IF NOT EXISTS (SELECT 1 FROM teams WHERE conference = 'AFC' AND sport = 'nfl') THEN
        RAISE EXCEPTION 'NFL seed failed: No AFC teams found';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM teams WHERE conference = 'NFC' AND sport = 'nfl') THEN
        RAISE EXCEPTION 'NFL seed failed: No NFC teams found';
    END IF;

    -- Check Elo ratings in valid range
    IF EXISTS (SELECT 1 FROM teams WHERE current_elo_rating < 1000 OR current_elo_rating > 2000) THEN
        RAISE EXCEPTION 'NFL seed failed: Elo ratings outside expected range (1000-2000)';
    END IF;

    RAISE NOTICE 'NFL seed successful: Loaded 32 teams with initial Elo ratings';
    RAISE NOTICE 'Elo range: % to %',
        (SELECT MIN(current_elo_rating) FROM teams WHERE sport = 'nfl'),
        (SELECT MAX(current_elo_rating) FROM teams WHERE sport = 'nfl');
END $$;
