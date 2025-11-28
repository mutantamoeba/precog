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
('ALA', 'Alabama Crimson Tide', 'Alabama', 'ncaab', 'ncaab', '333', 1620, 'SEC', NULL),
('ARK', 'Arkansas Razorbacks', 'Arkansas', 'ncaab', 'ncaab', '8', 1520, 'SEC', NULL),
('AUB', 'Auburn Tigers', 'Auburn', 'ncaab', 'ncaab', '2', 1640, 'SEC', NULL),
('FLA', 'Florida Gators', 'Florida', 'ncaab', 'ncaab', '57', 1580, 'SEC', NULL),
('UGA', 'Georgia Bulldogs', 'Georgia', 'ncaab', 'ncaab', '61', 1440, 'SEC', NULL),
('UK', 'Kentucky Wildcats', 'Kentucky', 'ncaab', 'ncaab', '96', 1600, 'SEC', NULL),
('LSU', 'LSU Tigers', 'LSU', 'ncaab', 'ncaab', '99', 1500, 'SEC', NULL),
('MISS', 'Ole Miss Rebels', 'Ole Miss', 'ncaab', 'ncaab', '145', 1500, 'SEC', NULL),
('MSST', 'Mississippi State Bulldogs', 'Mississippi State', 'ncaab', 'ncaab', '344', 1480, 'SEC', NULL),
('MIZZ', 'Missouri Tigers', 'Missouri', 'ncaab', 'ncaab', '142', 1480, 'SEC', NULL),
('OKLA', 'Oklahoma Sooners', 'Oklahoma', 'ncaab', 'ncaab', '201', 1500, 'SEC', NULL),
('SCAR', 'South Carolina Gamecocks', 'South Carolina', 'ncaab', 'ncaab', '2579', 1480, 'SEC', NULL),
('TENN', 'Tennessee Volunteers', 'Tennessee', 'ncaab', 'ncaab', '2633', 1640, 'SEC', NULL),
('TAMU', 'Texas A&M Aggies', 'Texas A&M', 'ncaab', 'ncaab', '245', 1540, 'SEC', NULL),
('TEX', 'Texas Longhorns', 'Texas', 'ncaab', 'ncaab', '251', 1560, 'SEC', NULL),
('VAN', 'Vanderbilt Commodores', 'Vanderbilt', 'ncaab', 'ncaab', '238', 1460, 'SEC', NULL),

-- BIG TEN (18 Teams)
('ILL', 'Illinois Fighting Illini', 'Illinois', 'ncaab', 'ncaab', '356', 1580, 'Big Ten', NULL),
('IND', 'Indiana Hoosiers', 'Indiana', 'ncaab', 'ncaab', '84', 1520, 'Big Ten', NULL),
('IOWA', 'Iowa Hawkeyes', 'Iowa', 'ncaab', 'ncaab', '2294', 1520, 'Big Ten', NULL),
('MD', 'Maryland Terrapins', 'Maryland', 'ncaab', 'ncaab', '120', 1500, 'Big Ten', NULL),
('MICH', 'Michigan Wolverines', 'Michigan', 'ncaab', 'ncaab', '130', 1500, 'Big Ten', NULL),
('MSU', 'Michigan State Spartans', 'Michigan State', 'ncaab', 'ncaab', '127', 1560, 'Big Ten', NULL),
('MINN', 'Minnesota Golden Gophers', 'Minnesota', 'ncaab', 'ncaab', '135', 1460, 'Big Ten', NULL),
('NEB', 'Nebraska Cornhuskers', 'Nebraska', 'ncaab', 'ncaab', '158', 1440, 'Big Ten', NULL),
('NW', 'Northwestern Wildcats', 'Northwestern', 'ncaab', 'ncaab', '77', 1480, 'Big Ten', NULL),
('OSU', 'Ohio State Buckeyes', 'Ohio State', 'ncaab', 'ncaab', '194', 1520, 'Big Ten', NULL),
('ORE', 'Oregon Ducks', 'Oregon', 'ncaab', 'ncaab', '2483', 1500, 'Big Ten', NULL),
('PSU', 'Penn State Nittany Lions', 'Penn State', 'ncaab', 'ncaab', '213', 1480, 'Big Ten', NULL),
('PUR', 'Purdue Boilermakers', 'Purdue', 'ncaab', 'ncaab', '2509', 1660, 'Big Ten', NULL),
('RUT', 'Rutgers Scarlet Knights', 'Rutgers', 'ncaab', 'ncaab', '164', 1460, 'Big Ten', NULL),
('UCLA', 'UCLA Bruins', 'UCLA', 'ncaab', 'ncaab', '26', 1560, 'Big Ten', NULL),
('USC', 'USC Trojans', 'USC', 'ncaab', 'ncaab', '30', 1500, 'Big Ten', NULL),
('WASH', 'Washington Huskies', 'Washington', 'ncaab', 'ncaab', '264', 1460, 'Big Ten', NULL),
('WISC', 'Wisconsin Badgers', 'Wisconsin', 'ncaab', 'ncaab', '275', 1540, 'Big Ten', NULL),

-- BIG 12 (16 Teams)
('AZU', 'Arizona Wildcats', 'Arizona', 'ncaab', 'ncaab', '12', 1580, 'Big 12', NULL),
('ASU', 'Arizona State Sun Devils', 'Arizona State', 'ncaab', 'ncaab', '9', 1460, 'Big 12', NULL),
('BAY', 'Baylor Bears', 'Baylor', 'ncaab', 'ncaab', '239', 1560, 'Big 12', NULL),
('BYU', 'BYU Cougars', 'BYU', 'ncaab', 'ncaab', '252', 1520, 'Big 12', NULL),
('CIN', 'Cincinnati Bearcats', 'Cincinnati', 'ncaab', 'ncaab', '2132', 1500, 'Big 12', NULL),
('COL', 'Colorado Buffaloes', 'Colorado', 'ncaab', 'ncaab', '38', 1480, 'Big 12', NULL),
('HOU', 'Houston Cougars', 'Houston', 'ncaab', 'ncaab', '248', 1620, 'Big 12', NULL),
('ISU', 'Iowa State Cyclones', 'Iowa State', 'ncaab', 'ncaab', '66', 1600, 'Big 12', NULL),
('KU', 'Kansas Jayhawks', 'Kansas', 'ncaab', 'ncaab', '2305', 1660, 'Big 12', NULL),
('KSU', 'Kansas State Wildcats', 'Kansas State', 'ncaab', 'ncaab', '2306', 1520, 'Big 12', NULL),
('OKST', 'Oklahoma State Cowboys', 'Oklahoma State', 'ncaab', 'ncaab', '197', 1480, 'Big 12', NULL),
('TCU', 'TCU Horned Frogs', 'TCU', 'ncaab', 'ncaab', '2628', 1500, 'Big 12', NULL),
('TTU', 'Texas Tech Red Raiders', 'Texas Tech', 'ncaab', 'ncaab', '2641', 1560, 'Big 12', NULL),
('UCF', 'UCF Knights', 'UCF', 'ncaab', 'ncaab', '2116', 1480, 'Big 12', NULL),
('UU', 'Utah Utes', 'Utah', 'ncaab', 'ncaab', '254', 1460, 'Big 12', NULL),
('WVU', 'West Virginia Mountaineers', 'West Virginia', 'ncaab', 'ncaab', '277', 1500, 'Big 12', NULL),

-- ACC (18 Teams)
('BC', 'Boston College Eagles', 'Boston College', 'ncaab', 'ncaab', '103', 1440, 'ACC', NULL),
('CAL', 'California Golden Bears', 'Cal', 'ncaab', 'ncaab', '25', 1420, 'ACC', NULL),
('CLEM', 'Clemson Tigers', 'Clemson', 'ncaab', 'ncaab', '228', 1540, 'ACC', NULL),
('DUKE', 'Duke Blue Devils', 'Duke', 'ncaab', 'ncaab', '150', 1660, 'ACC', NULL),
('FSU', 'Florida State Seminoles', 'Florida State', 'ncaab', 'ncaab', '52', 1480, 'ACC', NULL),
('GT', 'Georgia Tech Yellow Jackets', 'Georgia Tech', 'ncaab', 'ncaab', '59', 1460, 'ACC', NULL),
('LOU', 'Louisville Cardinals', 'Louisville', 'ncaab', 'ncaab', '97', 1480, 'ACC', NULL),
('MIA', 'Miami Hurricanes', 'Miami', 'ncaab', 'ncaab', '2390', 1500, 'ACC', NULL),
('NC', 'North Carolina Tar Heels', 'North Carolina', 'ncaab', 'ncaab', '153', 1600, 'ACC', NULL),
('NCST', 'NC State Wolfpack', 'NC State', 'ncaab', 'ncaab', '152', 1540, 'ACC', NULL),
('ND', 'Notre Dame Fighting Irish', 'Notre Dame', 'ncaab', 'ncaab', '87', 1480, 'ACC', NULL),
('PITT', 'Pittsburgh Panthers', 'Pitt', 'ncaab', 'ncaab', '221', 1500, 'ACC', NULL),
('SMU', 'SMU Mustangs', 'SMU', 'ncaab', 'ncaab', '2567', 1480, 'ACC', NULL),
('STAN', 'Stanford Cardinal', 'Stanford', 'ncaab', 'ncaab', '24', 1440, 'ACC', NULL),
('SYR', 'Syracuse Orange', 'Syracuse', 'ncaab', 'ncaab', '183', 1480, 'ACC', NULL),
('UVA', 'Virginia Cavaliers', 'Virginia', 'ncaab', 'ncaab', '258', 1520, 'ACC', NULL),
('VT', 'Virginia Tech Hokies', 'Virginia Tech', 'ncaab', 'ncaab', '259', 1480, 'ACC', NULL),
('WAKE', 'Wake Forest Demon Deacons', 'Wake Forest', 'ncaab', 'ncaab', '154', 1480, 'ACC', NULL),

-- BIG EAST (11 Teams)
('BUT', 'Butler Bulldogs', 'Butler', 'ncaab', 'ncaab', '2086', 1480, 'Big East', NULL),
('CONN', 'Connecticut Huskies', 'UConn', 'ncaab', 'ncaab', '41', 1700, 'Big East', NULL),
('CREIG', 'Creighton Bluejays', 'Creighton', 'ncaab', 'ncaab', '156', 1560, 'Big East', NULL),
('DPU', 'DePaul Blue Demons', 'DePaul', 'ncaab', 'ncaab', '305', 1420, 'Big East', NULL),
('GTWN', 'Georgetown Hoyas', 'Georgetown', 'ncaab', 'ncaab', '46', 1440, 'Big East', NULL),
('MARQ', 'Marquette Golden Eagles', 'Marquette', 'ncaab', 'ncaab', '269', 1600, 'Big East', NULL),
('PROV', 'Providence Friars', 'Providence', 'ncaab', 'ncaab', '2507', 1500, 'Big East', NULL),
('SHU', 'Seton Hall Pirates', 'Seton Hall', 'ncaab', 'ncaab', '2550', 1480, 'Big East', NULL),
('STJ', 'St. Johns Red Storm', 'St. Johns', 'ncaab', 'ncaab', '2599', 1540, 'Big East', NULL),
('NOVA', 'Villanova Wildcats', 'Villanova', 'ncaab', 'ncaab', '222', 1520, 'Big East', NULL),
('XAV', 'Xavier Musketeers', 'Xavier', 'ncaab', 'ncaab', '2752', 1500, 'Big East', NULL),

-- TOP MID-MAJORS (Consistent Tournament Teams - 10 Teams)
('GONZ', 'Gonzaga Bulldogs', 'Gonzaga', 'ncaab', 'ncaab', '2250', 1660, 'WCC', NULL),
('SDSU', 'San Diego State Aztecs', 'San Diego State', 'ncaab', 'ncaab', '21', 1540, 'Mountain West', NULL),
('CREI', 'College of Charleston Cougars', 'Charleston', 'ncaab', 'ncaab', '232', 1480, 'CAA', NULL),
('DAY', 'Dayton Flyers', 'Dayton', 'ncaab', 'ncaab', '2168', 1520, 'A-10', NULL),
('MEM', 'Memphis Tigers', 'Memphis', 'ncaab', 'ncaab', '235', 1520, 'American', NULL),
('SMC', 'Saint Marys Gaels', 'Saint Marys', 'ncaab', 'ncaab', '2608', 1560, 'WCC', NULL),
('VCU', 'VCU Rams', 'VCU', 'ncaab', 'ncaab', '2670', 1500, 'A-10', NULL),
('DRAKE', 'Drake Bulldogs', 'Drake', 'ncaab', 'ncaab', '2181', 1500, 'MVC', NULL),
('FAU', 'FAU Owls', 'FAU', 'ncaab', 'ncaab', '2226', 1480, 'American', NULL),
('NMSU', 'New Mexico State Aggies', 'New Mexico State', 'ncaab', 'ncaab', '166', 1460, 'Conference USA', NULL);

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
