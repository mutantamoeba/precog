-- Seed Data: NCAAB Teams with ESPN IDs (Top 80 D1)
-- Date: 2025-11-27
-- Phase: 2 (Live Data Integration)
-- Purpose: Seed top D1 college basketball teams with ESPN team IDs
-- Related: ADR-029 (ESPN Data Model), REQ-DATA-003 (Multi-Sport Support)

-- ============================================================================
-- NCAAB TEAMS - POWER CONFERENCES + TOP MID-MAJORS
-- ============================================================================
-- Focus: Tournament-caliber teams likely to appear in Kalshi prediction markets
-- Includes: SEC, Big Ten, Big 12, ACC, Big East + Top Mid-Majors
-- Initial Elo: 1500 = average D1, ~1700 = Final Four contender, ~1300 = rebuilding

INSERT INTO teams (team_code, team_name, display_name, sport, league, espn_team_id, current_elo_rating, conference, division) VALUES

-- SEC (16 Teams)
('ALA', 'Alabama Crimson Tide', 'Alabama', 'basketball', 'ncaab', '333', 1620, 'SEC', NULL),
('ARK', 'Arkansas Razorbacks', 'Arkansas', 'basketball', 'ncaab', '8', 1520, 'SEC', NULL),
('AUB', 'Auburn Tigers', 'Auburn', 'basketball', 'ncaab', '2', 1640, 'SEC', NULL),
('FLA', 'Florida Gators', 'Florida', 'basketball', 'ncaab', '57', 1580, 'SEC', NULL),
('UGA', 'Georgia Bulldogs', 'Georgia', 'basketball', 'ncaab', '61', 1440, 'SEC', NULL),
('UK', 'Kentucky Wildcats', 'Kentucky', 'basketball', 'ncaab', '96', 1600, 'SEC', NULL),
('LSU', 'LSU Tigers', 'LSU', 'basketball', 'ncaab', '99', 1500, 'SEC', NULL),
('MISS', 'Ole Miss Rebels', 'Ole Miss', 'basketball', 'ncaab', '145', 1500, 'SEC', NULL),
('MSST', 'Mississippi State Bulldogs', 'Mississippi State', 'basketball', 'ncaab', '344', 1480, 'SEC', NULL),
('MIZZ', 'Missouri Tigers', 'Missouri', 'basketball', 'ncaab', '142', 1480, 'SEC', NULL),
('OKLA', 'Oklahoma Sooners', 'Oklahoma', 'basketball', 'ncaab', '201', 1500, 'SEC', NULL),
('SCAR', 'South Carolina Gamecocks', 'South Carolina', 'basketball', 'ncaab', '2579', 1480, 'SEC', NULL),
('TENN', 'Tennessee Volunteers', 'Tennessee', 'basketball', 'ncaab', '2633', 1640, 'SEC', NULL),
('TAMU', 'Texas A&M Aggies', 'Texas A&M', 'basketball', 'ncaab', '245', 1540, 'SEC', NULL),
('TEX', 'Texas Longhorns', 'Texas', 'basketball', 'ncaab', '251', 1560, 'SEC', NULL),
('VAN', 'Vanderbilt Commodores', 'Vanderbilt', 'basketball', 'ncaab', '238', 1460, 'SEC', NULL),

-- BIG TEN (18 Teams)
('ILL', 'Illinois Fighting Illini', 'Illinois', 'basketball', 'ncaab', '356', 1580, 'Big Ten', NULL),
('IND', 'Indiana Hoosiers', 'Indiana', 'basketball', 'ncaab', '84', 1520, 'Big Ten', NULL),
('IOWA', 'Iowa Hawkeyes', 'Iowa', 'basketball', 'ncaab', '2294', 1520, 'Big Ten', NULL),
('MD', 'Maryland Terrapins', 'Maryland', 'basketball', 'ncaab', '120', 1500, 'Big Ten', NULL),
('MICH', 'Michigan Wolverines', 'Michigan', 'basketball', 'ncaab', '130', 1500, 'Big Ten', NULL),
('MSU', 'Michigan State Spartans', 'Michigan State', 'basketball', 'ncaab', '127', 1560, 'Big Ten', NULL),
('MINN', 'Minnesota Golden Gophers', 'Minnesota', 'basketball', 'ncaab', '135', 1460, 'Big Ten', NULL),
('NEB', 'Nebraska Cornhuskers', 'Nebraska', 'basketball', 'ncaab', '158', 1440, 'Big Ten', NULL),
('NW', 'Northwestern Wildcats', 'Northwestern', 'basketball', 'ncaab', '77', 1480, 'Big Ten', NULL),
('OSU', 'Ohio State Buckeyes', 'Ohio State', 'basketball', 'ncaab', '194', 1520, 'Big Ten', NULL),
('ORE', 'Oregon Ducks', 'Oregon', 'basketball', 'ncaab', '2483', 1500, 'Big Ten', NULL),
('PSU', 'Penn State Nittany Lions', 'Penn State', 'basketball', 'ncaab', '213', 1480, 'Big Ten', NULL),
('PUR', 'Purdue Boilermakers', 'Purdue', 'basketball', 'ncaab', '2509', 1660, 'Big Ten', NULL),
('RUT', 'Rutgers Scarlet Knights', 'Rutgers', 'basketball', 'ncaab', '164', 1460, 'Big Ten', NULL),
('UCLA', 'UCLA Bruins', 'UCLA', 'basketball', 'ncaab', '26', 1560, 'Big Ten', NULL),
('USC', 'USC Trojans', 'USC', 'basketball', 'ncaab', '30', 1500, 'Big Ten', NULL),
('WASH', 'Washington Huskies', 'Washington', 'basketball', 'ncaab', '264', 1460, 'Big Ten', NULL),
('WISC', 'Wisconsin Badgers', 'Wisconsin', 'basketball', 'ncaab', '275', 1540, 'Big Ten', NULL),

-- BIG 12 (16 Teams)
('AZU', 'Arizona Wildcats', 'Arizona', 'basketball', 'ncaab', '12', 1580, 'Big 12', NULL),
('ASU', 'Arizona State Sun Devils', 'Arizona State', 'basketball', 'ncaab', '9', 1460, 'Big 12', NULL),
('BAY', 'Baylor Bears', 'Baylor', 'basketball', 'ncaab', '239', 1560, 'Big 12', NULL),
('BYU', 'BYU Cougars', 'BYU', 'basketball', 'ncaab', '252', 1520, 'Big 12', NULL),
('CIN', 'Cincinnati Bearcats', 'Cincinnati', 'basketball', 'ncaab', '2132', 1500, 'Big 12', NULL),
('COL', 'Colorado Buffaloes', 'Colorado', 'basketball', 'ncaab', '38', 1480, 'Big 12', NULL),
('HOU', 'Houston Cougars', 'Houston', 'basketball', 'ncaab', '248', 1620, 'Big 12', NULL),
('ISU', 'Iowa State Cyclones', 'Iowa State', 'basketball', 'ncaab', '66', 1600, 'Big 12', NULL),
('KU', 'Kansas Jayhawks', 'Kansas', 'basketball', 'ncaab', '2305', 1660, 'Big 12', NULL),
('KSU', 'Kansas State Wildcats', 'Kansas State', 'basketball', 'ncaab', '2306', 1520, 'Big 12', NULL),
('OKST', 'Oklahoma State Cowboys', 'Oklahoma State', 'basketball', 'ncaab', '197', 1480, 'Big 12', NULL),
('TCU', 'TCU Horned Frogs', 'TCU', 'basketball', 'ncaab', '2628', 1500, 'Big 12', NULL),
('TTU', 'Texas Tech Red Raiders', 'Texas Tech', 'basketball', 'ncaab', '2641', 1560, 'Big 12', NULL),
('UCF', 'UCF Knights', 'UCF', 'basketball', 'ncaab', '2116', 1480, 'Big 12', NULL),
('UU', 'Utah Utes', 'Utah', 'basketball', 'ncaab', '254', 1460, 'Big 12', NULL),
('WVU', 'West Virginia Mountaineers', 'West Virginia', 'basketball', 'ncaab', '277', 1500, 'Big 12', NULL),

-- ACC (18 Teams)
('BC', 'Boston College Eagles', 'Boston College', 'basketball', 'ncaab', '103', 1440, 'ACC', NULL),
('CAL', 'California Golden Bears', 'Cal', 'basketball', 'ncaab', '25', 1420, 'ACC', NULL),
('CLEM', 'Clemson Tigers', 'Clemson', 'basketball', 'ncaab', '228', 1540, 'ACC', NULL),
('DUKE', 'Duke Blue Devils', 'Duke', 'basketball', 'ncaab', '150', 1660, 'ACC', NULL),
('FSU', 'Florida State Seminoles', 'Florida State', 'basketball', 'ncaab', '52', 1480, 'ACC', NULL),
('GT', 'Georgia Tech Yellow Jackets', 'Georgia Tech', 'basketball', 'ncaab', '59', 1460, 'ACC', NULL),
('LOU', 'Louisville Cardinals', 'Louisville', 'basketball', 'ncaab', '97', 1480, 'ACC', NULL),
('MIA', 'Miami Hurricanes', 'Miami', 'basketball', 'ncaab', '2390', 1500, 'ACC', NULL),
('NC', 'North Carolina Tar Heels', 'North Carolina', 'basketball', 'ncaab', '153', 1600, 'ACC', NULL),
('NCST', 'NC State Wolfpack', 'NC State', 'basketball', 'ncaab', '152', 1540, 'ACC', NULL),
('ND', 'Notre Dame Fighting Irish', 'Notre Dame', 'basketball', 'ncaab', '87', 1480, 'ACC', NULL),
('PITT', 'Pittsburgh Panthers', 'Pitt', 'basketball', 'ncaab', '221', 1500, 'ACC', NULL),
('SMU', 'SMU Mustangs', 'SMU', 'basketball', 'ncaab', '2567', 1480, 'ACC', NULL),
('STAN', 'Stanford Cardinal', 'Stanford', 'basketball', 'ncaab', '24', 1440, 'ACC', NULL),
('SYR', 'Syracuse Orange', 'Syracuse', 'basketball', 'ncaab', '183', 1480, 'ACC', NULL),
('UVA', 'Virginia Cavaliers', 'Virginia', 'basketball', 'ncaab', '258', 1520, 'ACC', NULL),
('VT', 'Virginia Tech Hokies', 'Virginia Tech', 'basketball', 'ncaab', '259', 1480, 'ACC', NULL),
('WAKE', 'Wake Forest Demon Deacons', 'Wake Forest', 'basketball', 'ncaab', '154', 1480, 'ACC', NULL),

-- BIG EAST (11 Teams)
('BUT', 'Butler Bulldogs', 'Butler', 'basketball', 'ncaab', '2086', 1480, 'Big East', NULL),
('CONN', 'Connecticut Huskies', 'UConn', 'basketball', 'ncaab', '41', 1700, 'Big East', NULL),
('CREIG', 'Creighton Bluejays', 'Creighton', 'basketball', 'ncaab', '156', 1560, 'Big East', NULL),
('DPU', 'DePaul Blue Demons', 'DePaul', 'basketball', 'ncaab', '305', 1420, 'Big East', NULL),
('GTWN', 'Georgetown Hoyas', 'Georgetown', 'basketball', 'ncaab', '46', 1440, 'Big East', NULL),
('MARQ', 'Marquette Golden Eagles', 'Marquette', 'basketball', 'ncaab', '269', 1600, 'Big East', NULL),
('PROV', 'Providence Friars', 'Providence', 'basketball', 'ncaab', '2507', 1500, 'Big East', NULL),
('SHU', 'Seton Hall Pirates', 'Seton Hall', 'basketball', 'ncaab', '2550', 1480, 'Big East', NULL),
('STJ', 'St. Johns Red Storm', 'St. Johns', 'basketball', 'ncaab', '2599', 1540, 'Big East', NULL),
('NOVA', 'Villanova Wildcats', 'Villanova', 'basketball', 'ncaab', '222', 1520, 'Big East', NULL),
('XAV', 'Xavier Musketeers', 'Xavier', 'basketball', 'ncaab', '2752', 1500, 'Big East', NULL),

-- TOP MID-MAJORS (Consistent Tournament Teams - 10 Teams)
('GONZ', 'Gonzaga Bulldogs', 'Gonzaga', 'basketball', 'ncaab', '2250', 1660, 'WCC', NULL),
('SDSU', 'San Diego State Aztecs', 'San Diego State', 'basketball', 'ncaab', '21', 1540, 'Mountain West', NULL),
('CREI', 'College of Charleston Cougars', 'Charleston', 'basketball', 'ncaab', '232', 1480, 'CAA', NULL),
('DAY', 'Dayton Flyers', 'Dayton', 'basketball', 'ncaab', '2168', 1520, 'A-10', NULL),
('MEM', 'Memphis Tigers', 'Memphis', 'basketball', 'ncaab', '235', 1520, 'American', NULL),
('SMC', 'Saint Marys Gaels', 'Saint Marys', 'basketball', 'ncaab', '2608', 1560, 'WCC', NULL),
('VCU', 'VCU Rams', 'VCU', 'basketball', 'ncaab', '2670', 1500, 'A-10', NULL),
('DRAKE', 'Drake Bulldogs', 'Drake', 'basketball', 'ncaab', '2181', 1500, 'MVC', NULL),
('FAU', 'FAU Owls', 'FAU', 'basketball', 'ncaab', '2226', 1480, 'American', NULL),
('NMSU', 'New Mexico State Aggies', 'New Mexico State', 'basketball', 'ncaab', '166', 1460, 'Conference USA', NULL);

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
    bigeast_count INT;
BEGIN
    SELECT COUNT(*) INTO team_count FROM teams WHERE league = 'ncaab';

    IF team_count < 80 THEN
        RAISE EXCEPTION 'NCAAB seed failed: Expected at least 80 teams, found %', team_count;
    END IF;

    -- Check major conference distribution
    SELECT COUNT(*) INTO sec_count FROM teams WHERE league = 'ncaab' AND conference = 'SEC';
    SELECT COUNT(*) INTO bigten_count FROM teams WHERE league = 'ncaab' AND conference = 'Big Ten';
    SELECT COUNT(*) INTO big12_count FROM teams WHERE league = 'ncaab' AND conference = 'Big 12';
    SELECT COUNT(*) INTO acc_count FROM teams WHERE league = 'ncaab' AND conference = 'ACC';
    SELECT COUNT(*) INTO bigeast_count FROM teams WHERE league = 'ncaab' AND conference = 'Big East';

    IF sec_count != 16 THEN
        RAISE EXCEPTION 'NCAAB seed failed: Expected 16 SEC teams, found %', sec_count;
    END IF;

    IF bigten_count != 18 THEN
        RAISE EXCEPTION 'NCAAB seed failed: Expected 18 Big Ten teams, found %', bigten_count;
    END IF;

    IF big12_count != 16 THEN
        RAISE EXCEPTION 'NCAAB seed failed: Expected 16 Big 12 teams, found %', big12_count;
    END IF;

    IF acc_count != 18 THEN
        RAISE EXCEPTION 'NCAAB seed failed: Expected 18 ACC teams, found %', acc_count;
    END IF;

    IF bigeast_count != 11 THEN
        RAISE EXCEPTION 'NCAAB seed failed: Expected 11 Big East teams, found %', bigeast_count;
    END IF;

    -- Check all have ESPN IDs
    IF EXISTS (SELECT 1 FROM teams WHERE league = 'ncaab' AND espn_team_id IS NULL) THEN
        RAISE EXCEPTION 'NCAAB seed failed: Some teams missing ESPN IDs';
    END IF;

    -- Check Elo ratings in valid range
    IF EXISTS (SELECT 1 FROM teams WHERE league = 'ncaab' AND (current_elo_rating < 1000 OR current_elo_rating > 2000)) THEN
        RAISE EXCEPTION 'NCAAB seed failed: Elo ratings outside expected range (1000-2000)';
    END IF;

    RAISE NOTICE 'NCAAB seed successful: Loaded % teams', team_count;
    RAISE NOTICE 'Major conferences: SEC(%), Big Ten(%), Big 12(%), ACC(%), Big East(%)',
        sec_count, bigten_count, big12_count, acc_count, bigeast_count;
    RAISE NOTICE 'Elo range: % to %',
        (SELECT MIN(current_elo_rating) FROM teams WHERE league = 'ncaab'),
        (SELECT MAX(current_elo_rating) FROM teams WHERE league = 'ncaab');
END $$;
