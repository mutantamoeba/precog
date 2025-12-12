-- Seed Data: NCAAW Teams with ESPN IDs (Top 75 D1)
-- Date: 2025-12-11
-- Phase: 2 (Live Data Integration)
-- Purpose: Seed top D1 women's college basketball teams with ESPN team IDs
-- Related: ADR-029 (ESPN Data Model), REQ-DATA-003 (Multi-Sport Support), Issue #194

-- ============================================================================
-- NCAAW TEAMS - POWER CONFERENCES + TOP MID-MAJORS
-- ============================================================================
-- Focus: Tournament-caliber teams likely to appear in prediction markets
-- Includes: SEC, Big Ten, Big 12, ACC, Big East + Top Mid-Majors
-- Initial Elo: 1500 = average D1, ~1700 = Final Four contender, ~1300 = rebuilding
--
-- Note: ESPN Team IDs for women's basketball use the same IDs as men's teams
-- ESPN differentiates via sport endpoint: /womens-college-basketball/team/_/id/{id}

INSERT INTO teams (team_code, team_name, display_name, sport, league, espn_team_id, current_elo_rating, conference, division) VALUES

-- SEC (16 Teams) - Elite women's basketball conference
('SCAR-W', 'South Carolina Gamecocks', 'South Carolina', 'ncaaw', 'ncaaw', '2579', 1750, 'SEC', NULL),
('LSU-W', 'LSU Tigers', 'LSU', 'ncaaw', 'ncaaw', '99', 1680, 'SEC', NULL),
('TENN-W', 'Tennessee Lady Volunteers', 'Tennessee', 'ncaaw', 'ncaaw', '2633', 1620, 'SEC', NULL),
('TEX-W', 'Texas Longhorns', 'Texas', 'ncaaw', 'ncaaw', '251', 1600, 'SEC', NULL),
('ALA-W', 'Alabama Crimson Tide', 'Alabama', 'ncaaw', 'ncaaw', '333', 1520, 'SEC', NULL),
('ARK-W', 'Arkansas Razorbacks', 'Arkansas', 'ncaaw', 'ncaaw', '8', 1520, 'SEC', NULL),
('AUB-W', 'Auburn Tigers', 'Auburn', 'ncaaw', 'ncaaw', '2', 1500, 'SEC', NULL),
('FLA-W', 'Florida Gators', 'Florida', 'ncaaw', 'ncaaw', '57', 1520, 'SEC', NULL),
('UGA-W', 'Georgia Lady Bulldogs', 'Georgia', 'ncaaw', 'ncaaw', '61', 1500, 'SEC', NULL),
('UK-W', 'Kentucky Wildcats', 'Kentucky', 'ncaaw', 'ncaaw', '96', 1560, 'SEC', NULL),
('MISS-W', 'Ole Miss Rebels', 'Ole Miss', 'ncaaw', 'ncaaw', '145', 1520, 'SEC', NULL),
('MSST-W', 'Mississippi State Bulldogs', 'Mississippi State', 'ncaaw', 'ncaaw', '344', 1500, 'SEC', NULL),
('MIZZ-W', 'Missouri Tigers', 'Missouri', 'ncaaw', 'ncaaw', '142', 1480, 'SEC', NULL),
('OKLA-W', 'Oklahoma Sooners', 'Oklahoma', 'ncaaw', 'ncaaw', '201', 1520, 'SEC', NULL),
('TAMU-W', 'Texas A&M Aggies', 'Texas A&M', 'ncaaw', 'ncaaw', '245', 1540, 'SEC', NULL),
('VAN-W', 'Vanderbilt Commodores', 'Vanderbilt', 'ncaaw', 'ncaaw', '238', 1460, 'SEC', NULL),

-- BIG TEN (18 Teams) - Strong women's basketball conference
('IOWA-W', 'Iowa Hawkeyes', 'Iowa', 'ncaaw', 'ncaaw', '2294', 1640, 'Big Ten', NULL),
('IND-W', 'Indiana Hoosiers', 'Indiana', 'ncaaw', 'ncaaw', '84', 1600, 'Big Ten', NULL),
('OSU-W', 'Ohio State Buckeyes', 'Ohio State', 'ncaaw', 'ncaaw', '194', 1600, 'Big Ten', NULL),
('MD-W', 'Maryland Terrapins', 'Maryland', 'ncaaw', 'ncaaw', '120', 1580, 'Big Ten', NULL),
('NEB-W', 'Nebraska Cornhuskers', 'Nebraska', 'ncaaw', 'ncaaw', '158', 1560, 'Big Ten', NULL),
('UCLA-W', 'UCLA Bruins', 'UCLA', 'ncaaw', 'ncaaw', '26', 1560, 'Big Ten', NULL),
('USC-W', 'USC Trojans', 'USC', 'ncaaw', 'ncaaw', '30', 1580, 'Big Ten', NULL),
('MICH-W', 'Michigan Wolverines', 'Michigan', 'ncaaw', 'ncaaw', '130', 1540, 'Big Ten', NULL),
('MSU-W', 'Michigan State Spartans', 'Michigan State', 'ncaaw', 'ncaaw', '127', 1520, 'Big Ten', NULL),
('ILL-W', 'Illinois Fighting Illini', 'Illinois', 'ncaaw', 'ncaaw', '356', 1480, 'Big Ten', NULL),
('NW-W', 'Northwestern Wildcats', 'Northwestern', 'ncaaw', 'ncaaw', '77', 1520, 'Big Ten', NULL),
('ORE-W', 'Oregon Ducks', 'Oregon', 'ncaaw', 'ncaaw', '2483', 1520, 'Big Ten', NULL),
('PSU-W', 'Penn State Nittany Lions', 'Penn State', 'ncaaw', 'ncaaw', '213', 1480, 'Big Ten', NULL),
('PUR-W', 'Purdue Boilermakers', 'Purdue', 'ncaaw', 'ncaaw', '2509', 1500, 'Big Ten', NULL),
('RUT-W', 'Rutgers Scarlet Knights', 'Rutgers', 'ncaaw', 'ncaaw', '164', 1480, 'Big Ten', NULL),
('MINN-W', 'Minnesota Golden Gophers', 'Minnesota', 'ncaaw', 'ncaaw', '135', 1460, 'Big Ten', NULL),
('WASH-W', 'Washington Huskies', 'Washington', 'ncaaw', 'ncaaw', '264', 1480, 'Big Ten', NULL),
('WISC-W', 'Wisconsin Badgers', 'Wisconsin', 'ncaaw', 'ncaaw', '275', 1460, 'Big Ten', NULL),

-- BIG 12 (16 Teams)
('BAY-W', 'Baylor Lady Bears', 'Baylor', 'ncaaw', 'ncaaw', '239', 1620, 'Big 12', NULL),
('KU-W', 'Kansas Jayhawks', 'Kansas', 'ncaaw', 'ncaaw', '2305', 1560, 'Big 12', NULL),
('ISU-W', 'Iowa State Cyclones', 'Iowa State', 'ncaaw', 'ncaaw', '66', 1560, 'Big 12', NULL),
('TTU-W', 'Texas Tech Lady Raiders', 'Texas Tech', 'ncaaw', 'ncaaw', '2641', 1520, 'Big 12', NULL),
('WVU-W', 'West Virginia Mountaineers', 'West Virginia', 'ncaaw', 'ncaaw', '277', 1520, 'Big 12', NULL),
('KSU-W', 'Kansas State Wildcats', 'Kansas State', 'ncaaw', 'ncaaw', '2306', 1500, 'Big 12', NULL),
('TCU-W', 'TCU Horned Frogs', 'TCU', 'ncaaw', 'ncaaw', '2628', 1500, 'Big 12', NULL),
('OKST-W', 'Oklahoma State Cowgirls', 'Oklahoma State', 'ncaaw', 'ncaaw', '197', 1480, 'Big 12', NULL),
('AZU-W', 'Arizona Wildcats', 'Arizona', 'ncaaw', 'ncaaw', '12', 1540, 'Big 12', NULL),
('ASU-W', 'Arizona State Sun Devils', 'Arizona State', 'ncaaw', 'ncaaw', '9', 1480, 'Big 12', NULL),
('BYU-W', 'BYU Cougars', 'BYU', 'ncaaw', 'ncaaw', '252', 1520, 'Big 12', NULL),
('CIN-W', 'Cincinnati Bearcats', 'Cincinnati', 'ncaaw', 'ncaaw', '2132', 1480, 'Big 12', NULL),
('COL-W', 'Colorado Buffaloes', 'Colorado', 'ncaaw', 'ncaaw', '38', 1540, 'Big 12', NULL),
('HOU-W', 'Houston Cougars', 'Houston', 'ncaaw', 'ncaaw', '248', 1500, 'Big 12', NULL),
('UCF-W', 'UCF Knights', 'UCF', 'ncaaw', 'ncaaw', '2116', 1480, 'Big 12', NULL),
('UU-W', 'Utah Utes', 'Utah', 'ncaaw', 'ncaaw', '254', 1500, 'Big 12', NULL),

-- ACC (18 Teams)
('ND-W', 'Notre Dame Fighting Irish', 'Notre Dame', 'ncaaw', 'ncaaw', '87', 1640, 'ACC', NULL),
('NC-W', 'North Carolina Tar Heels', 'North Carolina', 'ncaaw', 'ncaaw', '153', 1600, 'ACC', NULL),
('NCST-W', 'NC State Wolfpack', 'NC State', 'ncaaw', 'ncaaw', '152', 1600, 'ACC', NULL),
('DUKE-W', 'Duke Blue Devils', 'Duke', 'ncaaw', 'ncaaw', '150', 1580, 'ACC', NULL),
('UVA-W', 'Virginia Cavaliers', 'Virginia', 'ncaaw', 'ncaaw', '258', 1540, 'ACC', NULL),
('LOU-W', 'Louisville Cardinals', 'Louisville', 'ncaaw', 'ncaaw', '97', 1560, 'ACC', NULL),
('SYR-W', 'Syracuse Orange', 'Syracuse', 'ncaaw', 'ncaaw', '183', 1520, 'ACC', NULL),
('FSU-W', 'Florida State Seminoles', 'Florida State', 'ncaaw', 'ncaaw', '52', 1520, 'ACC', NULL),
('MIA-W', 'Miami Hurricanes', 'Miami', 'ncaaw', 'ncaaw', '2390', 1500, 'ACC', NULL),
('VT-W', 'Virginia Tech Hokies', 'Virginia Tech', 'ncaaw', 'ncaaw', '259', 1500, 'ACC', NULL),
('CLEM-W', 'Clemson Tigers', 'Clemson', 'ncaaw', 'ncaaw', '228', 1480, 'ACC', NULL),
('GT-W', 'Georgia Tech Yellow Jackets', 'Georgia Tech', 'ncaaw', 'ncaaw', '59', 1480, 'ACC', NULL),
('PITT-W', 'Pittsburgh Panthers', 'Pittsburgh', 'ncaaw', 'ncaaw', '221', 1480, 'ACC', NULL),
('WAKE-W', 'Wake Forest Demon Deacons', 'Wake Forest', 'ncaaw', 'ncaaw', '154', 1460, 'ACC', NULL),
('BC-W', 'Boston College Eagles', 'Boston College', 'ncaaw', 'ncaaw', '103', 1440, 'ACC', NULL),
('CAL-W', 'California Golden Bears', 'Cal', 'ncaaw', 'ncaaw', '25', 1460, 'ACC', NULL),
('SMU-W', 'SMU Mustangs', 'SMU', 'ncaaw', 'ncaaw', '2567', 1480, 'ACC', NULL),
('STAN-W', 'Stanford Cardinal', 'Stanford', 'ncaaw', 'ncaaw', '24', 1560, 'ACC', NULL),

-- BIG EAST (11 Teams)
('UCONN-W', 'UConn Huskies', 'UConn', 'ncaaw', 'ncaaw', '41', 1720, 'Big East', NULL),
('CREIGH-W', 'Creighton Bluejays', 'Creighton', 'ncaaw', 'ncaaw', '156', 1560, 'Big East', NULL),
('VILL-W', 'Villanova Wildcats', 'Villanova', 'ncaaw', 'ncaaw', '222', 1520, 'Big East', NULL),
('MARQ-W', 'Marquette Golden Eagles', 'Marquette', 'ncaaw', 'ncaaw', '269', 1540, 'Big East', NULL),
('SH-W', 'Seton Hall Pirates', 'Seton Hall', 'ncaaw', 'ncaaw', '2550', 1480, 'Big East', NULL),
('SJ-W', 'St. John''s Red Storm', 'St. John''s', 'ncaaw', 'ncaaw', '2599', 1500, 'Big East', NULL),
('PROV-W', 'Providence Friars', 'Providence', 'ncaaw', 'ncaaw', '2507', 1480, 'Big East', NULL),
('GTOWN-W', 'Georgetown Hoyas', 'Georgetown', 'ncaaw', 'ncaaw', '46', 1460, 'Big East', NULL),
('BUTLER-W', 'Butler Bulldogs', 'Butler', 'ncaaw', 'ncaaw', '2086', 1460, 'Big East', NULL),
('DEPAUL-W', 'DePaul Blue Demons', 'DePaul', 'ncaaw', 'ncaaw', '305', 1480, 'Big East', NULL),
('XAVIER-W', 'Xavier Musketeers', 'Xavier', 'ncaaw', 'ncaaw', '2752', 1460, 'Big East', NULL)

ON CONFLICT (team_code, sport) DO UPDATE SET
    team_name = EXCLUDED.team_name,
    display_name = EXCLUDED.display_name,
    league = EXCLUDED.league,
    espn_team_id = EXCLUDED.espn_team_id,
    current_elo_rating = EXCLUDED.current_elo_rating,
    conference = EXCLUDED.conference,
    division = EXCLUDED.division,
    updated_at = NOW();

-- ============================================================================
-- VERIFICATION QUERY
-- ============================================================================
-- Run after seeding to verify:
-- SELECT sport, league, conference, COUNT(*) as team_count
-- FROM teams
-- WHERE sport = 'ncaaw'
-- GROUP BY sport, league, conference
-- ORDER BY conference;
--
-- Expected output:
-- sport  | league | conference | team_count
-- -------+--------+------------+------------
-- ncaaw  | ncaaw  | ACC        | 18
-- ncaaw  | ncaaw  | Big 12     | 16
-- ncaaw  | ncaaw  | Big East   | 11
-- ncaaw  | ncaaw  | Big Ten    | 18
-- ncaaw  | ncaaw  | SEC        | 16
-- Total: 79 teams
