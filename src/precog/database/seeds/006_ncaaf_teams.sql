-- Seed Data: NCAAF Teams with ESPN IDs (FBS + FCS, 154 teams)
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

INSERT INTO teams (team_code, team_name, display_name, sport, league, sport_id, league_id, espn_team_id, current_elo_rating, conference, division) VALUES

-- SEC (16 Teams - 2024 Expansion)
('ALA', 'Alabama Crimson Tide', 'Alabama', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '333', 1680, 'SEC', NULL),
('ARK', 'Arkansas Razorbacks', 'Arkansas', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '8', 1480, 'SEC', NULL),
('AUB', 'Auburn Tigers', 'Auburn', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2', 1500, 'SEC', NULL),
('FLA', 'Florida Gators', 'Florida', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '57', 1520, 'SEC', NULL),
('UGA', 'Georgia Bulldogs', 'Georgia', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '61', 1700, 'SEC', NULL),
('UK', 'Kentucky Wildcats', 'Kentucky', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '96', 1460, 'SEC', NULL),
('LSU', 'LSU Tigers', 'LSU', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '99', 1600, 'SEC', NULL),
('MISS', 'Ole Miss Rebels', 'Ole Miss', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '145', 1600, 'SEC', NULL),
('MSST', 'Mississippi State Bulldogs', 'Mississippi State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '344', 1440, 'SEC', NULL),
('MIZZ', 'Missouri Tigers', 'Missouri', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '142', 1520, 'SEC', NULL),
('OKLA', 'Oklahoma Sooners', 'Oklahoma', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '201', 1520, 'SEC', NULL),
('SCAR', 'South Carolina Gamecocks', 'South Carolina', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2579', 1480, 'SEC', NULL),
('TENN', 'Tennessee Volunteers', 'Tennessee', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2633', 1580, 'SEC', NULL),
('TAMU', 'Texas A&M Aggies', 'Texas A&M', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '245', 1560, 'SEC', NULL),
('TEX', 'Texas Longhorns', 'Texas', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '251', 1640, 'SEC', NULL),
('VAN', 'Vanderbilt Commodores', 'Vanderbilt', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '238', 1400, 'SEC', NULL),

-- BIG TEN (18 Teams - 2024 Expansion)
('ILL', 'Illinois Fighting Illini', 'Illinois', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '356', 1480, 'Big Ten', NULL),
('IND', 'Indiana Hoosiers', 'Indiana', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '84', 1560, 'Big Ten', NULL),
('IOWA', 'Iowa Hawkeyes', 'Iowa', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2294', 1520, 'Big Ten', NULL),
('MD', 'Maryland Terrapins', 'Maryland', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '120', 1460, 'Big Ten', NULL),
('MICH', 'Michigan Wolverines', 'Michigan', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '130', 1640, 'Big Ten', NULL),
('MSU', 'Michigan State Spartans', 'Michigan State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '127', 1440, 'Big Ten', NULL),
('MINN', 'Minnesota Golden Gophers', 'Minnesota', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '135', 1480, 'Big Ten', NULL),
('NEB', 'Nebraska Cornhuskers', 'Nebraska', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '158', 1480, 'Big Ten', NULL),
('NU', 'Northwestern Wildcats', 'Northwestern', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '77', 1420, 'Big Ten', NULL),
('OSU', 'Ohio State Buckeyes', 'Ohio State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '194', 1680, 'Big Ten', NULL),
('ORE', 'Oregon Ducks', 'Oregon', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2483', 1680, 'Big Ten', NULL),
('PSU', 'Penn State Nittany Lions', 'Penn State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '213', 1620, 'Big Ten', NULL),
('PUR', 'Purdue Boilermakers', 'Purdue', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2509', 1400, 'Big Ten', NULL),
('RUT', 'Rutgers Scarlet Knights', 'Rutgers', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '164', 1440, 'Big Ten', NULL),
('UCLA', 'UCLA Bruins', 'UCLA', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '26', 1440, 'Big Ten', NULL),
('USC', 'USC Trojans', 'USC', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '30', 1520, 'Big Ten', NULL),
('WASH', 'Washington Huskies', 'Washington', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '264', 1520, 'Big Ten', NULL),
('WISC', 'Wisconsin Badgers', 'Wisconsin', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '275', 1480, 'Big Ten', NULL),

-- BIG 12 (16 Teams - 2024 Expansion)
('AZU', 'Arizona Wildcats', 'Arizona', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '12', 1480, 'Big 12', NULL),
('ASU', 'Arizona State Sun Devils', 'Arizona State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '9', 1560, 'Big 12', NULL),
('BAY', 'Baylor Bears', 'Baylor', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '239', 1480, 'Big 12', NULL),
('BYU', 'BYU Cougars', 'BYU', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '252', 1580, 'Big 12', NULL),
('CIN', 'Cincinnati Bearcats', 'Cincinnati', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2132', 1480, 'Big 12', NULL),
('COL', 'Colorado Buffaloes', 'Colorado', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '38', 1560, 'Big 12', NULL),
('HOU', 'Houston Cougars', 'Houston', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '248', 1420, 'Big 12', NULL),
('ISU', 'Iowa State Cyclones', 'Iowa State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '66', 1580, 'Big 12', NULL),
('KU', 'Kansas Jayhawks', 'Kansas', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2305', 1500, 'Big 12', NULL),
('KSU', 'Kansas State Wildcats', 'Kansas State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2306', 1560, 'Big 12', NULL),
('OKST', 'Oklahoma State Cowboys', 'Oklahoma State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '197', 1460, 'Big 12', NULL),
('TCU', 'TCU Horned Frogs', 'TCU', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2628', 1520, 'Big 12', NULL),
('TTU', 'Texas Tech Red Raiders', 'Texas Tech', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2641', 1500, 'Big 12', NULL),
('UCF', 'UCF Knights', 'UCF', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2116', 1500, 'Big 12', NULL),
('UU', 'Utah Utes', 'Utah', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '254', 1500, 'Big 12', NULL),
('WVU', 'West Virginia Mountaineers', 'West Virginia', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '277', 1460, 'Big 12', NULL),

-- ACC (17 Teams - 2024 Expansion)
('BC', 'Boston College Eagles', 'Boston College', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '103', 1440, 'ACC', NULL),
('CAL', 'California Golden Bears', 'Cal', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '25', 1460, 'ACC', NULL),
('CLEM', 'Clemson Tigers', 'Clemson', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '228', 1600, 'ACC', NULL),
('DUKE', 'Duke Blue Devils', 'Duke', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '150', 1500, 'ACC', NULL),
('FSU', 'Florida State Seminoles', 'Florida State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '52', 1440, 'ACC', NULL),
('GT', 'Georgia Tech Yellow Jackets', 'Georgia Tech', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '59', 1500, 'ACC', NULL),
('LOU', 'Louisville Cardinals', 'Louisville', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '97', 1520, 'ACC', NULL),
('MIA', 'Miami Hurricanes', 'Miami', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2390', 1600, 'ACC', NULL),
('NC', 'North Carolina Tar Heels', 'North Carolina', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '153', 1480, 'ACC', NULL),
('NCSU', 'NC State Wolfpack', 'NC State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '152', 1500, 'ACC', NULL),
('PITT', 'Pittsburgh Panthers', 'Pitt', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '221', 1500, 'ACC', NULL),
('SMU', 'SMU Mustangs', 'SMU', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2567', 1580, 'ACC', NULL),
('STAN', 'Stanford Cardinal', 'Stanford', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '24', 1380, 'ACC', NULL),
('SYR', 'Syracuse Orange', 'Syracuse', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '183', 1500, 'ACC', NULL),
('UVA', 'Virginia Cavaliers', 'Virginia', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '258', 1440, 'ACC', NULL),
('VT', 'Virginia Tech Hokies', 'Virginia Tech', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '259', 1480, 'ACC', NULL),
('WAKE', 'Wake Forest Demon Deacons', 'Wake Forest', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '154', 1440, 'ACC', NULL),

-- TOP GROUP OF 5 (12 Teams - Playoff Contenders)
('BOIS', 'Boise State Broncos', 'Boise State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '68', 1580, 'Mountain West', NULL),
('APP', 'Appalachian State Mountaineers', 'App State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2026', 1520, 'Sun Belt', NULL),
('JMU', 'James Madison Dukes', 'James Madison', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '256', 1540, 'Sun Belt', NULL),
('LT', 'Louisiana Tech Bulldogs', 'Louisiana Tech', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2348', 1460, 'Conference USA', NULL),
('MEM', 'Memphis Tigers', 'Memphis', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '235', 1500, 'American', NULL),
('NAVY', 'Navy Midshipmen', 'Navy', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2426', 1500, 'American', NULL),
('ARMY', 'Army Black Knights', 'Army', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '349', 1560, 'American', NULL),
('SDSU', 'San Diego State Aztecs', 'San Diego State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '21', 1480, 'Mountain West', NULL),
('SJSU', 'San Jose State Spartans', 'San Jose State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '23', 1440, 'Mountain West', NULL),
('TULN', 'Tulane Green Wave', 'Tulane', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2655', 1520, 'American', NULL),
('USF', 'South Florida Bulls', 'South Florida', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '58', 1480, 'American', NULL),
('NIU', 'Northern Illinois Huskies', 'Northern Illinois', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2459', 1480, 'MAC', NULL),

-- ADDITIONAL FBS + FCS TEAMS (2026-03-08)
-- Teams discovered via ESPN scoreboard polling that were missing from seed data.
-- Includes remaining FBS independents, FCS teams, and smaller programs.
-- All default to 1500 Elo (unrated).
('ACU', 'Abilene Christian Wildcats', 'Abilene Christian', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2000', 1500, 'WAC', NULL),
('AKR', 'Akron Zips', 'Akron', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2006', 1500, 'MAC', NULL),
('APSU', 'Austin Peay Governors', 'Austin Peay', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2046', 1500, 'ASUN', NULL),
('ARST', 'Arkansas State Red Wolves', 'Arkansas State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2032', 1500, 'Sun Belt', NULL),
('BALL', 'Ball State Cardinals', 'Ball State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2050', 1500, 'MAC', NULL),
('BCU', 'Bethune-Cookman Wildcats', 'Bethune-Cookman', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2065', 1500, 'SWAC', NULL),
('BRY', 'Bryant Bulldogs', 'Bryant', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2803', 1500, 'FCS Independent', NULL),
('CCU', 'Coastal Carolina Chanticleers', 'Coastal Carolina', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '324', 1500, 'Sun Belt', NULL),
('CIT', 'The Citadel Bulldogs', 'The Citadel', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2643', 1500, 'Southern', NULL),
('CLT', 'Charlotte 49ers', 'Charlotte', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2429', 1500, 'American', NULL),
('CONN', 'UConn Huskies', 'UConn', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '41', 1500, 'FBS Independent', NULL),
('CSU', 'Colorado State Rams', 'Colorado State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '36', 1500, 'Mountain West', NULL),
('ECU', 'East Carolina Pirates', 'East Carolina', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '151', 1500, 'American', NULL),
('EIU', 'Eastern Illinois Panthers', 'Eastern Illinois', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2197', 1500, 'OVC', NULL),
('FAU', 'Florida Atlantic Owls', 'Florida Atlantic', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2226', 1500, 'American', NULL),
('FIU', 'Florida International Panthers', 'Florida International', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2229', 1500, 'Conference USA', NULL),
('FRES', 'Fresno State Bulldogs', 'Fresno State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '278', 1500, 'Mountain West', NULL),
('FUR', 'Furman Paladins', 'Furman', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '231', 1500, 'Southern', NULL),
('HAW', 'Hawaii Rainbow Warriors', 'Hawaii', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '62', 1500, 'Mountain West', NULL),
('HCU', 'Houston Christian Huskies', 'Houston Christian', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2277', 1500, 'Southland', NULL),
('HOW', 'Howard Bison', 'Howard', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '47', 1500, 'MEAC', NULL),
('IDHO', 'Idaho Vandals', 'Idaho', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '70', 1500, 'Big Sky', NULL),
('IDST', 'Idaho State Bengals', 'Idaho State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '304', 1500, 'Big Sky', NULL),
('INST', 'Indiana State Sycamores', 'Indiana State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '282', 1500, 'MVC', NULL),
('KENT', 'Kent State Golden Flashes', 'Kent State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2309', 1500, 'MAC', NULL),
('LAF', 'Lafayette Leopards', 'Lafayette', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '322', 1500, 'Patriot', NULL),
('LIU', 'Long Island University Sharks', 'LIU', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2341', 1500, 'NEC', NULL),
('M-OH', 'Miami (OH) RedHawks', 'Miami OH', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '193', 1500, 'MAC', NULL),
('MASS', 'Massachusetts Minutemen', 'UMass', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '113', 1500, 'FBS Independent', NULL),
('MORG', 'Morgan State Bears', 'Morgan State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2415', 1500, 'MEAC', NULL),
('MOST', 'Missouri State Bears', 'Missouri State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2623', 1500, 'MVC', NULL),
('MRSH', 'Marshall Thundering Herd', 'Marshall', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '276', 1500, 'Sun Belt', NULL),
('NAU', 'Northern Arizona Lumberjacks', 'Northern Arizona', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2464', 1500, 'Big Sky', NULL),
('ND', 'Notre Dame Fighting Irish', 'Notre Dame', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '87', 1500, 'FBS Independent', NULL),
('NICH', 'Nicholls Colonels', 'Nicholls', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2447', 1500, 'Southland', NULL),
('NMSU', 'New Mexico State Aggies', 'New Mexico State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '166', 1500, 'Conference USA', NULL),
('OHIO', 'Ohio Bobcats', 'Ohio', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '195', 1500, 'MAC', NULL),
('ORST', 'Oregon State Beavers', 'Oregon State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '204', 1500, 'FBS Independent', NULL),
('PRST', 'Portland State Vikings', 'Portland State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2502', 1500, 'Big Sky', NULL),
('RGV', 'UT Rio Grande Valley Vaqueros', 'UTRGV', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '292', 1500, 'WAC', NULL),
('RICE', 'Rice Owls', 'Rice', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '242', 1500, 'American', NULL),
('SDST', 'South Dakota State Jackrabbits', 'South Dakota State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2571', 1500, 'MVC', NULL),
('SEMO', 'Southeast Missouri State Redhawks', 'SE Missouri', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2546', 1500, 'OVC', NULL),
('TEM', 'Temple Owls', 'Temple', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '218', 1500, 'American', NULL),
('TLSA', 'Tulsa Golden Hurricane', 'Tulsa', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '202', 1500, 'American', NULL),
('TNST', 'Tennessee State Tigers', 'Tennessee State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2634', 1500, 'OVC', NULL),
('TOL', 'Toledo Rockets', 'Toledo', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2649', 1500, 'MAC', NULL),
('TOW', 'Towson Tigers', 'Towson', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '119', 1500, 'CAA', NULL),
('TXST', 'Texas State Bobcats', 'Texas State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '326', 1500, 'Sun Belt', NULL),
('UAB', 'UAB Blazers', 'UAB', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '5', 1500, 'American', NULL),
('UAPB', 'Arkansas-Pine Bluff Golden Lions', 'AR-Pine Bluff', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2029', 1500, 'SWAC', NULL),
('ULM', 'UL Monroe Warhawks', 'UL Monroe', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2433', 1500, 'Sun Belt', NULL),
('UNA', 'North Alabama Lions', 'North Alabama', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2453', 1500, 'Conference USA', NULL),
('UNH', 'New Hampshire Wildcats', 'New Hampshire', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '160', 1500, 'CAA', NULL),
('UNLV', 'UNLV Rebels', 'UNLV', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2439', 1500, 'Mountain West', NULL),
('UNT', 'North Texas Mean Green', 'North Texas', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '249', 1500, 'American', NULL),
('URI', 'Rhode Island Rams', 'Rhode Island', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '227', 1500, 'CAA', NULL),
('USU', 'Utah State Aggies', 'Utah State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '328', 1500, 'Mountain West', NULL),
('UTEP', 'UTEP Miners', 'UTEP', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2638', 1500, 'Conference USA', NULL),
('UTSA', 'UTSA Roadrunners', 'UTSA', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2636', 1500, 'American', NULL),
('UTU', 'Utah Tech Trailblazers', 'Utah Tech', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '3101', 1500, 'WAC', NULL),
('VMI', 'VMI Keydets', 'VMI', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2678', 1500, 'Southern', NULL),
('WMU', 'Western Michigan Broncos', 'Western Michigan', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2711', 1500, 'MAC', NULL),
('WSU', 'Washington State Cougars', 'Washington State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '265', 1500, 'FBS Independent', NULL),
('WYO', 'Wyoming Cowboys', 'Wyoming', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2751', 1500, 'Mountain West', NULL),
('YSU', 'Youngstown State Penguins', 'Youngstown State', 'football', 'ncaaf', (SELECT id FROM sports WHERE sport_key = 'football'), (SELECT id FROM leagues WHERE league_key = 'ncaaf'), '2754', 1500, 'MVC', NULL);

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
