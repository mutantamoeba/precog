-- Seed Data: NCAAF Teams with ESPN IDs (FBS Top 80)
-- Date: 2025-11-27
-- Phase: 2 (Live Data Integration)
-- Purpose: Seed top FBS college football teams with ESPN team IDs
-- Related: ADR-029 (ESPN Data Model), REQ-DATA-003 (Multi-Sport Support)

-- ============================================================================
-- NCAAF TEAMS - POWER CONFERENCES + TOP GROUP OF 5
-- ============================================================================
-- Focus: Teams most likely to appear in Kalshi prediction markets
-- Includes: SEC, Big Ten, Big 12, ACC + Top Group of 5 programs
-- Initial Elo: 1500 = average FBS, ~1700 = CFP contender, ~1300 = rebuilding

INSERT INTO teams (team_code, team_name, display_name, sport, league, espn_team_id, current_elo_rating, conference, division) VALUES

-- SEC (16 Teams - 2024 Expansion)
('ALA', 'Alabama Crimson Tide', 'Alabama', 'ncaaf', 'ncaaf', '333', 1680, 'SEC', NULL),
('ARK', 'Arkansas Razorbacks', 'Arkansas', 'ncaaf', 'ncaaf', '8', 1480, 'SEC', NULL),
('AUB', 'Auburn Tigers', 'Auburn', 'ncaaf', 'ncaaf', '2', 1500, 'SEC', NULL),
('FLA', 'Florida Gators', 'Florida', 'ncaaf', 'ncaaf', '57', 1520, 'SEC', NULL),
('UGA', 'Georgia Bulldogs', 'Georgia', 'ncaaf', 'ncaaf', '61', 1700, 'SEC', NULL),
('UK', 'Kentucky Wildcats', 'Kentucky', 'ncaaf', 'ncaaf', '96', 1460, 'SEC', NULL),
('LSU', 'LSU Tigers', 'LSU', 'ncaaf', 'ncaaf', '99', 1600, 'SEC', NULL),
('MISS', 'Ole Miss Rebels', 'Ole Miss', 'ncaaf', 'ncaaf', '145', 1600, 'SEC', NULL),
('MSST', 'Mississippi State Bulldogs', 'Mississippi State', 'ncaaf', 'ncaaf', '344', 1440, 'SEC', NULL),
('MIZZ', 'Missouri Tigers', 'Missouri', 'ncaaf', 'ncaaf', '142', 1520, 'SEC', NULL),
('OKLA', 'Oklahoma Sooners', 'Oklahoma', 'ncaaf', 'ncaaf', '201', 1520, 'SEC', NULL),
('SCAR', 'South Carolina Gamecocks', 'South Carolina', 'ncaaf', 'ncaaf', '2579', 1480, 'SEC', NULL),
('TENN', 'Tennessee Volunteers', 'Tennessee', 'ncaaf', 'ncaaf', '2633', 1580, 'SEC', NULL),
('TAMU', 'Texas A&M Aggies', 'Texas A&M', 'ncaaf', 'ncaaf', '245', 1560, 'SEC', NULL),
('TEX', 'Texas Longhorns', 'Texas', 'ncaaf', 'ncaaf', '251', 1640, 'SEC', NULL),
('VAN', 'Vanderbilt Commodores', 'Vanderbilt', 'ncaaf', 'ncaaf', '238', 1400, 'SEC', NULL),

-- BIG TEN (18 Teams - 2024 Expansion)
('ILL', 'Illinois Fighting Illini', 'Illinois', 'ncaaf', 'ncaaf', '356', 1480, 'Big Ten', NULL),
('IND', 'Indiana Hoosiers', 'Indiana', 'ncaaf', 'ncaaf', '84', 1560, 'Big Ten', NULL),
('IOWA', 'Iowa Hawkeyes', 'Iowa', 'ncaaf', 'ncaaf', '2294', 1520, 'Big Ten', NULL),
('MD', 'Maryland Terrapins', 'Maryland', 'ncaaf', 'ncaaf', '120', 1460, 'Big Ten', NULL),
('MICH', 'Michigan Wolverines', 'Michigan', 'ncaaf', 'ncaaf', '130', 1640, 'Big Ten', NULL),
('MSU', 'Michigan State Spartans', 'Michigan State', 'ncaaf', 'ncaaf', '127', 1440, 'Big Ten', NULL),
('MINN', 'Minnesota Golden Gophers', 'Minnesota', 'ncaaf', 'ncaaf', '135', 1480, 'Big Ten', NULL),
('NEB', 'Nebraska Cornhuskers', 'Nebraska', 'ncaaf', 'ncaaf', '158', 1480, 'Big Ten', NULL),
('NW', 'Northwestern Wildcats', 'Northwestern', 'ncaaf', 'ncaaf', '77', 1420, 'Big Ten', NULL),
('OSU', 'Ohio State Buckeyes', 'Ohio State', 'ncaaf', 'ncaaf', '194', 1680, 'Big Ten', NULL),
('ORE', 'Oregon Ducks', 'Oregon', 'ncaaf', 'ncaaf', '2483', 1680, 'Big Ten', NULL),
('PSU', 'Penn State Nittany Lions', 'Penn State', 'ncaaf', 'ncaaf', '213', 1620, 'Big Ten', NULL),
('PUR', 'Purdue Boilermakers', 'Purdue', 'ncaaf', 'ncaaf', '2509', 1400, 'Big Ten', NULL),
('RUT', 'Rutgers Scarlet Knights', 'Rutgers', 'ncaaf', 'ncaaf', '164', 1440, 'Big Ten', NULL),
('UCLA', 'UCLA Bruins', 'UCLA', 'ncaaf', 'ncaaf', '26', 1440, 'Big Ten', NULL),
('USC', 'USC Trojans', 'USC', 'ncaaf', 'ncaaf', '30', 1520, 'Big Ten', NULL),
('WASH', 'Washington Huskies', 'Washington', 'ncaaf', 'ncaaf', '264', 1520, 'Big Ten', NULL),
('WISC', 'Wisconsin Badgers', 'Wisconsin', 'ncaaf', 'ncaaf', '275', 1480, 'Big Ten', NULL),

-- BIG 12 (16 Teams - 2024 Expansion)
('AZU', 'Arizona Wildcats', 'Arizona', 'ncaaf', 'ncaaf', '12', 1480, 'Big 12', NULL),
('ASU', 'Arizona State Sun Devils', 'Arizona State', 'ncaaf', 'ncaaf', '9', 1560, 'Big 12', NULL),
('BAY', 'Baylor Bears', 'Baylor', 'ncaaf', 'ncaaf', '239', 1480, 'Big 12', NULL),
('BYU', 'BYU Cougars', 'BYU', 'ncaaf', 'ncaaf', '252', 1580, 'Big 12', NULL),
('CIN', 'Cincinnati Bearcats', 'Cincinnati', 'ncaaf', 'ncaaf', '2132', 1480, 'Big 12', NULL),
('COL', 'Colorado Buffaloes', 'Colorado', 'ncaaf', 'ncaaf', '38', 1560, 'Big 12', NULL),
('HOU', 'Houston Cougars', 'Houston', 'ncaaf', 'ncaaf', '248', 1420, 'Big 12', NULL),
('ISU', 'Iowa State Cyclones', 'Iowa State', 'ncaaf', 'ncaaf', '66', 1580, 'Big 12', NULL),
('KU', 'Kansas Jayhawks', 'Kansas', 'ncaaf', 'ncaaf', '2305', 1500, 'Big 12', NULL),
('KSU', 'Kansas State Wildcats', 'Kansas State', 'ncaaf', 'ncaaf', '2306', 1560, 'Big 12', NULL),
('OKST', 'Oklahoma State Cowboys', 'Oklahoma State', 'ncaaf', 'ncaaf', '197', 1460, 'Big 12', NULL),
('TCU', 'TCU Horned Frogs', 'TCU', 'ncaaf', 'ncaaf', '2628', 1520, 'Big 12', NULL),
('TTU', 'Texas Tech Red Raiders', 'Texas Tech', 'ncaaf', 'ncaaf', '2641', 1500, 'Big 12', NULL),
('UCF', 'UCF Knights', 'UCF', 'ncaaf', 'ncaaf', '2116', 1500, 'Big 12', NULL),
('UU', 'Utah Utes', 'Utah', 'ncaaf', 'ncaaf', '254', 1500, 'Big 12', NULL),
('WVU', 'West Virginia Mountaineers', 'West Virginia', 'ncaaf', 'ncaaf', '277', 1460, 'Big 12', NULL),

-- ACC (17 Teams - 2024 Expansion)
('BC', 'Boston College Eagles', 'Boston College', 'ncaaf', 'ncaaf', '103', 1440, 'ACC', NULL),
('CAL', 'California Golden Bears', 'Cal', 'ncaaf', 'ncaaf', '25', 1460, 'ACC', NULL),
('CLEM', 'Clemson Tigers', 'Clemson', 'ncaaf', 'ncaaf', '228', 1600, 'ACC', NULL),
('DUKE', 'Duke Blue Devils', 'Duke', 'ncaaf', 'ncaaf', '150', 1500, 'ACC', NULL),
('FSU', 'Florida State Seminoles', 'Florida State', 'ncaaf', 'ncaaf', '52', 1440, 'ACC', NULL),
('GT', 'Georgia Tech Yellow Jackets', 'Georgia Tech', 'ncaaf', 'ncaaf', '59', 1500, 'ACC', NULL),
('LOU', 'Louisville Cardinals', 'Louisville', 'ncaaf', 'ncaaf', '97', 1520, 'ACC', NULL),
('MIA', 'Miami Hurricanes', 'Miami', 'ncaaf', 'ncaaf', '2390', 1600, 'ACC', NULL),
('NC', 'North Carolina Tar Heels', 'North Carolina', 'ncaaf', 'ncaaf', '153', 1480, 'ACC', NULL),
('NCST', 'NC State Wolfpack', 'NC State', 'ncaaf', 'ncaaf', '152', 1500, 'ACC', NULL),
('PITT', 'Pittsburgh Panthers', 'Pitt', 'ncaaf', 'ncaaf', '221', 1500, 'ACC', NULL),
('SMU', 'SMU Mustangs', 'SMU', 'ncaaf', 'ncaaf', '2567', 1580, 'ACC', NULL),
('STAN', 'Stanford Cardinal', 'Stanford', 'ncaaf', 'ncaaf', '24', 1380, 'ACC', NULL),
('SYR', 'Syracuse Orange', 'Syracuse', 'ncaaf', 'ncaaf', '183', 1500, 'ACC', NULL),
('UVA', 'Virginia Cavaliers', 'Virginia', 'ncaaf', 'ncaaf', '258', 1440, 'ACC', NULL),
('VT', 'Virginia Tech Hokies', 'Virginia Tech', 'ncaaf', 'ncaaf', '259', 1480, 'ACC', NULL),
('WAKE', 'Wake Forest Demon Deacons', 'Wake Forest', 'ncaaf', 'ncaaf', '154', 1440, 'ACC', NULL),

-- TOP GROUP OF 5 (12 Teams - Playoff Contenders)
('BSU', 'Boise State Broncos', 'Boise State', 'ncaaf', 'ncaaf', '68', 1580, 'Mountain West', NULL),
('APP', 'Appalachian State Mountaineers', 'App State', 'ncaaf', 'ncaaf', '2026', 1520, 'Sun Belt', NULL),
('JMU', 'James Madison Dukes', 'James Madison', 'ncaaf', 'ncaaf', '256', 1540, 'Sun Belt', NULL),
('LT', 'Louisiana Tech Bulldogs', 'Louisiana Tech', 'ncaaf', 'ncaaf', '2348', 1460, 'Conference USA', NULL),
('MEM', 'Memphis Tigers', 'Memphis', 'ncaaf', 'ncaaf', '235', 1500, 'American', NULL),
('NAVY', 'Navy Midshipmen', 'Navy', 'ncaaf', 'ncaaf', '2426', 1500, 'American', NULL),
('ARMY', 'Army Black Knights', 'Army', 'ncaaf', 'ncaaf', '349', 1560, 'American', NULL),
('SDSU', 'San Diego State Aztecs', 'San Diego State', 'ncaaf', 'ncaaf', '21', 1480, 'Mountain West', NULL),
('SJSU', 'San Jose State Spartans', 'San Jose State', 'ncaaf', 'ncaaf', '23', 1440, 'Mountain West', NULL),
('TLNE', 'Tulane Green Wave', 'Tulane', 'ncaaf', 'ncaaf', '2655', 1520, 'American', NULL),
('USF', 'South Florida Bulls', 'South Florida', 'ncaaf', 'ncaaf', '58', 1480, 'American', NULL),
('NIU', 'Northern Illinois Huskies', 'Northern Illinois', 'ncaaf', 'ncaaf', '2459', 1480, 'MAC', NULL);

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    team_count INT;
    sec_count INT;
    bigten_count INT;
    big12_count INT;
    acc_count INT;
    g5_count INT;
BEGIN
    SELECT COUNT(*) INTO team_count FROM teams WHERE league = 'ncaaf';

    IF team_count < 75 THEN
        RAISE EXCEPTION 'NCAAF seed failed: Expected at least 75 teams, found %', team_count;
    END IF;

    -- Check conference distribution
    SELECT COUNT(*) INTO sec_count FROM teams WHERE league = 'ncaaf' AND conference = 'SEC';
    SELECT COUNT(*) INTO bigten_count FROM teams WHERE league = 'ncaaf' AND conference = 'Big Ten';
    SELECT COUNT(*) INTO big12_count FROM teams WHERE league = 'ncaaf' AND conference = 'Big 12';
    SELECT COUNT(*) INTO acc_count FROM teams WHERE league = 'ncaaf' AND conference = 'ACC';

    IF sec_count != 16 THEN
        RAISE EXCEPTION 'NCAAF seed failed: Expected 16 SEC teams, found %', sec_count;
    END IF;

    IF bigten_count != 18 THEN
        RAISE EXCEPTION 'NCAAF seed failed: Expected 18 Big Ten teams, found %', bigten_count;
    END IF;

    IF big12_count != 16 THEN
        RAISE EXCEPTION 'NCAAF seed failed: Expected 16 Big 12 teams, found %', big12_count;
    END IF;

    IF acc_count != 17 THEN
        RAISE EXCEPTION 'NCAAF seed failed: Expected 17 ACC teams, found %', acc_count;
    END IF;

    -- Check all have ESPN IDs
    IF EXISTS (SELECT 1 FROM teams WHERE league = 'ncaaf' AND espn_team_id IS NULL) THEN
        RAISE EXCEPTION 'NCAAF seed failed: Some teams missing ESPN IDs';
    END IF;

    -- Check Elo ratings in valid range
    IF EXISTS (SELECT 1 FROM teams WHERE league = 'ncaaf' AND (current_elo_rating < 1000 OR current_elo_rating > 2000)) THEN
        RAISE EXCEPTION 'NCAAF seed failed: Elo ratings outside expected range (1000-2000)';
    END IF;

    RAISE NOTICE 'NCAAF seed successful: Loaded % teams', team_count;
    RAISE NOTICE 'Conference breakdown: SEC(%), Big Ten(%), Big 12(%), ACC(%)',
        sec_count, bigten_count, big12_count, acc_count;
    RAISE NOTICE 'Elo range: % to %',
        (SELECT MIN(current_elo_rating) FROM teams WHERE league = 'ncaaf'),
        (SELECT MAX(current_elo_rating) FROM teams WHERE league = 'ncaaf');
END $$;
