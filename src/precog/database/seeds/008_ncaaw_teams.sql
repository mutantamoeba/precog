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

INSERT INTO teams (team_code, team_name, display_name, sport, league, sport_id, league_id, espn_team_id, current_elo_rating, conference, division) VALUES

-- SEC (16 Teams) - Elite women's basketball conference
('SCAR-W', 'South Carolina Gamecocks', 'South Carolina', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2579', 1750, 'SEC', NULL),
('LSU-W', 'LSU Tigers', 'LSU', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '99', 1680, 'SEC', NULL),
('TENN-W', 'Tennessee Lady Volunteers', 'Tennessee', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2633', 1620, 'SEC', NULL),
('TEX-W', 'Texas Longhorns', 'Texas', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '251', 1600, 'SEC', NULL),
('ALA-W', 'Alabama Crimson Tide', 'Alabama', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '333', 1520, 'SEC', NULL),
('ARK-W', 'Arkansas Razorbacks', 'Arkansas', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '8', 1520, 'SEC', NULL),
('AUB-W', 'Auburn Tigers', 'Auburn', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2', 1500, 'SEC', NULL),
('FLA-W', 'Florida Gators', 'Florida', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '57', 1520, 'SEC', NULL),
('UGA-W', 'Georgia Lady Bulldogs', 'Georgia', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '61', 1500, 'SEC', NULL),
('UK-W', 'Kentucky Wildcats', 'Kentucky', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '96', 1560, 'SEC', NULL),
('MISS-W', 'Ole Miss Rebels', 'Ole Miss', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '145', 1520, 'SEC', NULL),
('MSST-W', 'Mississippi State Bulldogs', 'Mississippi State', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '344', 1500, 'SEC', NULL),
('MIZZ-W', 'Missouri Tigers', 'Missouri', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '142', 1480, 'SEC', NULL),
('OKLA-W', 'Oklahoma Sooners', 'Oklahoma', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '201', 1520, 'SEC', NULL),
('TAMU-W', 'Texas A&M Aggies', 'Texas A&M', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '245', 1540, 'SEC', NULL),
('VAN-W', 'Vanderbilt Commodores', 'Vanderbilt', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '238', 1460, 'SEC', NULL),

-- BIG TEN (18 Teams) - Strong women's basketball conference
('IOWA-W', 'Iowa Hawkeyes', 'Iowa', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2294', 1640, 'Big Ten', NULL),
('IND-W', 'Indiana Hoosiers', 'Indiana', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '84', 1600, 'Big Ten', NULL),
('OSU-W', 'Ohio State Buckeyes', 'Ohio State', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '194', 1600, 'Big Ten', NULL),
('MD-W', 'Maryland Terrapins', 'Maryland', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '120', 1580, 'Big Ten', NULL),
('NEB-W', 'Nebraska Cornhuskers', 'Nebraska', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '158', 1560, 'Big Ten', NULL),
('UCLA-W', 'UCLA Bruins', 'UCLA', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '26', 1560, 'Big Ten', NULL),
('USC-W', 'USC Trojans', 'USC', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '30', 1580, 'Big Ten', NULL),
('MICH-W', 'Michigan Wolverines', 'Michigan', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '130', 1540, 'Big Ten', NULL),
('MSU-W', 'Michigan State Spartans', 'Michigan State', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '127', 1520, 'Big Ten', NULL),
('ILL-W', 'Illinois Fighting Illini', 'Illinois', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '356', 1480, 'Big Ten', NULL),
('NW-W', 'Northwestern Wildcats', 'Northwestern', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '77', 1520, 'Big Ten', NULL),
('ORE-W', 'Oregon Ducks', 'Oregon', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2483', 1520, 'Big Ten', NULL),
('PSU-W', 'Penn State Nittany Lions', 'Penn State', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '213', 1480, 'Big Ten', NULL),
('PUR-W', 'Purdue Boilermakers', 'Purdue', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2509', 1500, 'Big Ten', NULL),
('RUT-W', 'Rutgers Scarlet Knights', 'Rutgers', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '164', 1480, 'Big Ten', NULL),
('MINN-W', 'Minnesota Golden Gophers', 'Minnesota', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '135', 1460, 'Big Ten', NULL),
('WASH-W', 'Washington Huskies', 'Washington', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '264', 1480, 'Big Ten', NULL),
('WISC-W', 'Wisconsin Badgers', 'Wisconsin', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '275', 1460, 'Big Ten', NULL),

-- BIG 12 (16 Teams)
('BAY-W', 'Baylor Lady Bears', 'Baylor', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '239', 1620, 'Big 12', NULL),
('KU-W', 'Kansas Jayhawks', 'Kansas', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2305', 1560, 'Big 12', NULL),
('ISU-W', 'Iowa State Cyclones', 'Iowa State', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '66', 1560, 'Big 12', NULL),
('TTU-W', 'Texas Tech Lady Raiders', 'Texas Tech', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2641', 1520, 'Big 12', NULL),
('WVU-W', 'West Virginia Mountaineers', 'West Virginia', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '277', 1520, 'Big 12', NULL),
('KSU-W', 'Kansas State Wildcats', 'Kansas State', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2306', 1500, 'Big 12', NULL),
('TCU-W', 'TCU Horned Frogs', 'TCU', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2628', 1500, 'Big 12', NULL),
('OKST-W', 'Oklahoma State Cowgirls', 'Oklahoma State', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '197', 1480, 'Big 12', NULL),
('AZU-W', 'Arizona Wildcats', 'Arizona', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '12', 1540, 'Big 12', NULL),
('ASU-W', 'Arizona State Sun Devils', 'Arizona State', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '9', 1480, 'Big 12', NULL),
('BYU-W', 'BYU Cougars', 'BYU', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '252', 1520, 'Big 12', NULL),
('CIN-W', 'Cincinnati Bearcats', 'Cincinnati', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2132', 1480, 'Big 12', NULL),
('COL-W', 'Colorado Buffaloes', 'Colorado', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '38', 1540, 'Big 12', NULL),
('HOU-W', 'Houston Cougars', 'Houston', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '248', 1500, 'Big 12', NULL),
('UCF-W', 'UCF Knights', 'UCF', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2116', 1480, 'Big 12', NULL),
('UU-W', 'Utah Utes', 'Utah', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '254', 1500, 'Big 12', NULL),

-- ACC (18 Teams)
('ND-W', 'Notre Dame Fighting Irish', 'Notre Dame', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '87', 1640, 'ACC', NULL),
('NC-W', 'North Carolina Tar Heels', 'North Carolina', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '153', 1600, 'ACC', NULL),
('NCST-W', 'NC State Wolfpack', 'NC State', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '152', 1600, 'ACC', NULL),
('DUKE-W', 'Duke Blue Devils', 'Duke', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '150', 1580, 'ACC', NULL),
('UVA-W', 'Virginia Cavaliers', 'Virginia', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '258', 1540, 'ACC', NULL),
('LOU-W', 'Louisville Cardinals', 'Louisville', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '97', 1560, 'ACC', NULL),
('SYR-W', 'Syracuse Orange', 'Syracuse', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '183', 1520, 'ACC', NULL),
('FSU-W', 'Florida State Seminoles', 'Florida State', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '52', 1520, 'ACC', NULL),
('MIA-W', 'Miami Hurricanes', 'Miami', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2390', 1500, 'ACC', NULL),
('VT-W', 'Virginia Tech Hokies', 'Virginia Tech', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '259', 1500, 'ACC', NULL),
('CLEM-W', 'Clemson Tigers', 'Clemson', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '228', 1480, 'ACC', NULL),
('GT-W', 'Georgia Tech Yellow Jackets', 'Georgia Tech', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '59', 1480, 'ACC', NULL),
('PITT-W', 'Pittsburgh Panthers', 'Pittsburgh', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '221', 1480, 'ACC', NULL),
('WAKE-W', 'Wake Forest Demon Deacons', 'Wake Forest', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '154', 1460, 'ACC', NULL),
('BC-W', 'Boston College Eagles', 'Boston College', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '103', 1440, 'ACC', NULL),
('CAL-W', 'California Golden Bears', 'Cal', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '25', 1460, 'ACC', NULL),
('SMU-W', 'SMU Mustangs', 'SMU', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2567', 1480, 'ACC', NULL),
('STAN-W', 'Stanford Cardinal', 'Stanford', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '24', 1560, 'ACC', NULL),

-- BIG EAST (11 Teams)
('UCONN-W', 'UConn Huskies', 'UConn', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '41', 1720, 'Big East', NULL),
('CREIGH-W', 'Creighton Bluejays', 'Creighton', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '156', 1560, 'Big East', NULL),
('VILL-W', 'Villanova Wildcats', 'Villanova', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '222', 1520, 'Big East', NULL),
('MARQ-W', 'Marquette Golden Eagles', 'Marquette', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '269', 1540, 'Big East', NULL),
('SH-W', 'Seton Hall Pirates', 'Seton Hall', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2550', 1480, 'Big East', NULL),
('SJ-W', 'St. John''s Red Storm', 'St. John''s', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2599', 1500, 'Big East', NULL),
('PROV-W', 'Providence Friars', 'Providence', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2507', 1480, 'Big East', NULL),
('GTOWN-W', 'Georgetown Hoyas', 'Georgetown', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '46', 1460, 'Big East', NULL),
('BUTLER-W', 'Butler Bulldogs', 'Butler', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2086', 1460, 'Big East', NULL),
('DEPAUL-W', 'DePaul Blue Demons', 'DePaul', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '305', 1480, 'Big East', NULL),
('XAVIER-W', 'Xavier Musketeers', 'Xavier', 'basketball', 'ncaaw', (SELECT id FROM sports WHERE sport_key = 'basketball'), (SELECT id FROM leagues WHERE league_key = 'ncaaw'), '2752', 1460, 'Big East', NULL)

ON CONFLICT (espn_team_id, league) WHERE espn_team_id IS NOT NULL DO UPDATE SET
    team_code = EXCLUDED.team_code,
    team_name = EXCLUDED.team_name,
    display_name = EXCLUDED.display_name,
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
-- WHERE sport = 'basketball' AND league = 'ncaaw'
-- GROUP BY sport, league, conference
-- ORDER BY conference;
--
-- Expected output:
-- sport  | league | conference | team_count
-- -------+--------+------------+------------
-- basketball | ncaaw  | ACC        | 18
-- basketball | ncaaw  | Big 12     | 16
-- basketball | ncaaw  | Big East   | 11
-- basketball | ncaaw  | Big Ten    | 18
-- basketball | ncaaw  | SEC        | 16
-- Total: 79 teams
