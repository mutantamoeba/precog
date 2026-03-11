"""Fix ESPN team IDs in the precog_dev database.

This script fetches all teams from the ESPN API for NHL, NBA, and NCAAB,
compares them against the seed files and (optionally) the live database,
and generates SQL UPDATE/INSERT statements for any mismatches.

Usage:
    python scripts/fix_espn_team_ids.py

    # Also check against live database (requires DB connection)
    python scripts/fix_espn_team_ids.py --check-db

Educational Note:
    ESPN provides a public teams endpoint at:
        https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/teams
    This returns ALL teams for a league with their ESPN IDs, abbreviations,
    display names, conference, and division info.

    The scoreboard endpoint only returns teams playing on a given day,
    so the teams endpoint is the authoritative source for team metadata.

Args:
    --check-db: Also query the precog_dev database for comparison

Returns:
    Prints comparison tables and SQL statements to stdout.

Related:
    - src/precog/database/seeds/004_nhl_teams.sql
    - src/precog/database/seeds/003_nba_teams.sql
    - src/precog/database/seeds/007_ncaab_teams.sql
    - src/precog/api_connectors/espn_client.py
"""

import argparse
import logging
import time
from typing import Any

import requests

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ESPN Teams API endpoints
# These are separate from the scoreboard endpoints and return ALL teams
ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"
LEAGUE_CONFIGS = {
    "nhl": {
        "sport": "hockey",
        "league": "nhl",
        "url": f"{ESPN_BASE_URL}/hockey/nhl/teams",
        "expected_teams": 32,
    },
    "nba": {
        "sport": "basketball",
        "league": "nba",
        "url": f"{ESPN_BASE_URL}/basketball/nba/teams",
        "expected_teams": 30,
    },
    "ncaab": {
        "sport": "basketball",
        "league": "mens-college-basketball",
        "url": f"{ESPN_BASE_URL}/basketball/mens-college-basketball/teams",
        "expected_teams": 362,  # ESPN returns all D1 teams
    },
}

# Known team code mappings where ESPN abbreviation differs from our DB code
# ESPN API -> our DB code
CODE_ALIASES: dict[str, dict[str, str]] = {
    "nhl": {
        "LA": "LAK",  # ESPN uses 'LA' for Kings, we use 'LAK'
        "TB": "TBL",  # ESPN uses 'TB' for Lightning, we use 'TBL'
        "SJ": "SJS",  # ESPN uses 'SJ' for Sharks, we use 'SJS'
        "NJ": "NJD",  # ESPN uses 'NJ' for Devils, we use 'NJD'
        "UTAH": "UTA",  # ESPN uses 'UTAH' for Utah Hockey Club/Mammoth, we use 'UTA'
    },
    "nba": {
        "GS": "GSW",  # ESPN uses 'GS' for Warriors, we use 'GSW'
        "NO": "NOP",  # ESPN uses 'NO' for Pelicans, we use 'NOP'
        "NY": "NYK",  # ESPN uses 'NY' for Knicks, we use 'NYK'
        "SA": "SAS",  # ESPN uses 'SA' for Spurs, we use 'SAS'
        "UTAH": "UTA",  # ESPN uses 'UTAH' for Jazz, we use 'UTA'
        "WSH": "WAS",  # ESPN uses 'WSH' for Wizards, we use 'WAS'
    },
    "ncaab": {
        # ESPN abbreviations that differ from our seed file codes
        "ARIZ": "AZU",  # ESPN uses 'ARIZ' for Arizona, we use 'AZU'
        "COLO": "COL",  # ESPN uses 'COLO' for Colorado, we use 'COL'
        "CREIG": "CREIG",  # Already matching (Creighton)
        "DEP": "DPU",  # ESPN uses 'DEP' for DePaul, we use 'DPU'
        "DRKE": "DRAKE",  # ESPN uses 'DRKE' for Drake, we use 'DRAKE'
        "IU": "IND",  # ESPN uses 'IU' for Indiana, we use 'IND'
        "MIZ": "MIZZ",  # ESPN uses 'MIZ' for Missouri, we use 'MIZZ'
        "UNC": "NC",  # ESPN uses 'UNC' for North Carolina, we use 'NC'
        "NCST": "NCST",  # Already matching (NC State)
        "NOVA": "NOVA",  # Already matching (Villanova)
        "NW": "NW",  # Already matching (Northwestern)
        "OU": "OKLA",  # ESPN uses 'OU' for Oklahoma, we use 'OKLA'
        "RUTG": "RUT",  # ESPN uses 'RUTG' for Rutgers, we use 'RUT'
        "SC": "SCAR",  # ESPN uses 'SC' for South Carolina, we use 'SCAR'
        "SJU": "STJ",  # ESPN uses 'SJU' for St. John's, we use 'STJ'
        "TA&M": "TAMU",  # ESPN uses 'TA&M' for Texas A&M, we use 'TAMU'
        "UTAH": "UU",  # ESPN uses 'UTAH' for Utah, we use 'UU'
        "WIS": "WISC",  # ESPN uses 'WIS' for Wisconsin, we use 'WISC'
        "VILL": "NOVA",  # Alternate ESPN code for Villanova
    },
}


def fetch_espn_teams(league: str, limit: int = 100) -> list[dict[str, Any]]:
    """Fetch all teams from ESPN API for a given league.

    Args:
        league: League key from LEAGUE_CONFIGS (nhl, nba, ncaab)
        limit: Page size for ESPN API pagination (default 100)

    Returns:
        List of team dicts with espn_id, abbreviation, displayName, etc.

    Educational Note:
        The ESPN teams endpoint supports pagination via ?limit=N&page=P.
        For professional leagues (NHL=32, NBA=30) one page suffices.
        For college (362+ teams), we paginate.

    Raises:
        requests.HTTPError: If API returns error status
    """
    config = LEAGUE_CONFIGS[league]
    url = str(config["url"])
    all_teams: list[dict[str, Any]] = []
    page = 1

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Precog/1.0 (Sports Analytics - Team ID Audit)",
            "Accept": "application/json",
        }
    )

    while True:
        params = {"limit": limit, "page": page}
        logger.info(f"Fetching {league.upper()} teams page {page} from ESPN API...")

        response = session.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        # ESPN returns teams under "sports" -> [0] -> "leagues" -> [0] -> "teams"
        sports = data.get("sports", [])
        if not sports:
            break

        leagues = sports[0].get("leagues", [])
        if not leagues:
            break

        teams_wrapper = leagues[0].get("teams", [])
        if not teams_wrapper:
            break

        for wrapper in teams_wrapper:
            team = wrapper.get("team", {})
            if team:
                all_teams.append(team)

        # Check if we got fewer than limit (last page)
        if len(teams_wrapper) < limit:
            break

        page += 1
        time.sleep(0.5)  # Be a good API citizen

    session.close()
    logger.info(f"Fetched {len(all_teams)} {league.upper()} teams from ESPN API")
    return all_teams


def parse_espn_team(team: dict[str, Any]) -> dict[str, str]:
    """Parse ESPN team response into a normalized dict.

    Args:
        team: Raw ESPN team dict

    Returns:
        Dict with keys: espn_id, code, name, display_name, conference, division

    Educational Note:
        ESPN team structure:
        {
            "id": "1",
            "abbreviation": "BOS",
            "displayName": "Boston Bruins",
            "shortDisplayName": "Bruins",
            "groups": {"id": "...", "isConference": true}
        }
    """
    return {
        "espn_id": str(team.get("id", "")),
        "code": team.get("abbreviation", ""),
        "name": team.get("displayName", ""),
        "display_name": team.get("shortDisplayName", ""),
        "location": team.get("location", ""),
    }


def load_seed_teams(league: str) -> dict[str, dict[str, str]]:
    """Load team data from seed SQL files for comparison.

    Args:
        league: League key (nhl, nba, ncaab)

    Returns:
        Dict keyed by team_code with espn_team_id and other fields

    Educational Note:
        We parse the INSERT VALUES from the SQL seed files to get the
        current expected state. This is more reliable than querying the
        database which may have drifted from the seeds.
    """
    import re
    from pathlib import Path

    seed_files = {
        "nhl": Path("src/precog/database/seeds/004_nhl_teams.sql"),
        "nba": Path("src/precog/database/seeds/003_nba_teams.sql"),
        "ncaab": Path("src/precog/database/seeds/007_ncaab_teams.sql"),
    }

    seed_path = seed_files.get(league)
    if not seed_path or not seed_path.exists():
        logger.warning(f"Seed file not found for {league}")
        return {}

    teams: dict[str, dict[str, str]] = {}

    # Parse INSERT VALUES lines
    # Format: ('CODE', 'Name', 'Display', 'sport', 'league', 'espn_id', elo, 'conf', 'div')
    pattern = re.compile(
        r"\('([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'[^']+',\s*'[^']+',\s*'([^']+)',\s*(\d+),\s*'([^']*)',\s*(?:'([^']*)'|NULL)\)"
    )

    content = seed_path.read_text(encoding="utf-8")
    for match in pattern.finditer(content):
        code = match.group(1)
        name = match.group(2)
        display = match.group(3)
        espn_id = match.group(4)
        conf = match.group(6)
        div = match.group(7) if match.group(7) else ""

        teams[code] = {
            "team_code": code,
            "team_name": name,
            "display_name": display,
            "espn_team_id": espn_id,
            "conference": conf,
            "division": div,
        }

    logger.info(f"Loaded {len(teams)} {league.upper()} teams from seed file")
    return teams


def compare_teams(
    league: str,
    espn_teams: list[dict[str, Any]],
    seed_teams: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Compare ESPN API teams with seed file teams.

    Args:
        league: League key (nhl, nba, ncaab)
        espn_teams: Teams from ESPN API
        seed_teams: Teams from seed SQL files

    Returns:
        Tuple of (mismatches, missing_from_db, extra_in_db):
        - mismatches: Teams where ESPN ID differs between API and seed
        - missing_from_db: Teams in ESPN API but not in seed file
        - extra_in_db: Teams in seed file but not found in ESPN API

    Educational Note:
        We match teams by abbreviation code, accounting for known aliases
        (e.g., ESPN 'LA' = our 'LAK' for LA Kings). Mismatches in ESPN ID
        indicate the seed file has wrong data that needs correcting.
    """
    aliases = CODE_ALIASES.get(league, {})
    # Build reverse alias map: our_code -> espn_code
    reverse_aliases = {v: k for k, v in aliases.items()}

    # Build ESPN lookup by abbreviation
    espn_by_code: dict[str, dict[str, str]] = {}
    for team in espn_teams:
        parsed = parse_espn_team(team)
        code = parsed["code"]
        espn_by_code[code] = parsed

    mismatches: list[dict[str, str]] = []
    missing_from_db: list[dict[str, str]] = []
    matched_espn_codes: set[str] = set()

    for db_code, db_team in sorted(seed_teams.items()):
        # Try direct match first
        espn_code = db_code
        espn_team = espn_by_code.get(espn_code)

        # Try reverse alias (our LAK -> ESPN LA)
        if not espn_team and db_code in reverse_aliases:
            espn_code = reverse_aliases[db_code]
            espn_team = espn_by_code.get(espn_code)

        if not espn_team:
            # Try matching by ESPN ID
            for ecode, eteam in espn_by_code.items():
                if eteam["espn_id"] == db_team["espn_team_id"]:
                    espn_team = eteam
                    espn_code = ecode
                    break

        if not espn_team:
            # Could not find this DB team in ESPN at all
            # This is unusual - may indicate a renamed/relocated team
            continue

        matched_espn_codes.add(espn_code)

        # Compare ESPN IDs
        if espn_team["espn_id"] != db_team["espn_team_id"]:
            mismatches.append(
                {
                    "db_code": db_code,
                    "espn_code": espn_code,
                    "db_espn_id": db_team["espn_team_id"],
                    "api_espn_id": espn_team["espn_id"],
                    "db_name": db_team["team_name"],
                    "api_name": espn_team["name"],
                    "code_alias": "Y" if espn_code != db_code else "",
                }
            )

    # Find ESPN teams not in our DB
    for espn_code, espn_team in sorted(espn_by_code.items()):
        if espn_code not in matched_espn_codes:
            # Check if aliased version is in DB
            aliased = aliases.get(espn_code, espn_code)
            if aliased not in seed_teams and espn_code not in seed_teams:
                missing_from_db.append(
                    {
                        "espn_code": espn_code,
                        "espn_id": espn_team["espn_id"],
                        "name": espn_team["name"],
                        "display_name": espn_team["display_name"],
                    }
                )

    # Find DB teams not matched to any ESPN team
    extra_in_db: list[dict[str, str]] = []
    for db_code in sorted(seed_teams.keys()):
        espn_code = reverse_aliases.get(db_code, db_code)
        if espn_code not in matched_espn_codes and db_code not in matched_espn_codes:
            extra_in_db.append(
                {
                    "db_code": db_code,
                    "db_espn_id": seed_teams[db_code]["espn_team_id"],
                    "db_name": seed_teams[db_code]["team_name"],
                }
            )

    return mismatches, missing_from_db, extra_in_db


def print_comparison_table(
    league: str,
    mismatches: list[dict[str, str]],
    missing_from_db: list[dict[str, str]],
    extra_in_db: list[dict[str, str]],
) -> None:
    """Print formatted comparison table.

    Args:
        league: League name
        mismatches: Teams with differing ESPN IDs
        missing_from_db: Teams in ESPN but not in DB
        extra_in_db: Teams in DB but not in ESPN
    """
    separator = "=" * 90
    print(f"\n{separator}")
    print(f"  {league.upper()} TEAM COMPARISON: ESPN API vs Seed File")
    print(separator)

    if mismatches:
        print(f"\n  ESPN ID MISMATCHES ({len(mismatches)} found):")
        print(
            f"  {'DB Code':<8} {'ESPN Code':<10} {'DB ESPN ID':<12} {'API ESPN ID':<12} {'Team Name':<30} {'Alias?'}"
        )
        print(f"  {'-' * 8} {'-' * 10} {'-' * 12} {'-' * 12} {'-' * 30} {'-' * 6}")
        for m in mismatches:
            print(
                f"  {m['db_code']:<8} {m['espn_code']:<10} {m['db_espn_id']:<12} "
                f"{m['api_espn_id']:<12} {m['db_name']:<30} {m['code_alias']}"
            )
    else:
        print("\n  No ESPN ID mismatches found - all IDs match!")

    if missing_from_db:
        print(f"\n  TEAMS IN ESPN API BUT NOT IN SEED FILE ({len(missing_from_db)}):")
        if league == "ncaab" and len(missing_from_db) > 20:
            print(
                f"  (Showing first 20 of {len(missing_from_db)} - college has 350+ teams, we only seed ~90)"
            )
            show = missing_from_db[:20]
        else:
            show = missing_from_db
        print(f"  {'ESPN Code':<10} {'ESPN ID':<12} {'Team Name':<40}")
        print(f"  {'-' * 10} {'-' * 12} {'-' * 40}")
        for m in show:
            print(f"  {m['espn_code']:<10} {m['espn_id']:<12} {m['name']:<40}")

    if extra_in_db:
        print(f"\n  TEAMS IN SEED FILE BUT NOT MATCHED IN ESPN API ({len(extra_in_db)}):")
        print(f"  {'DB Code':<10} {'DB ESPN ID':<12} {'Team Name':<40}")
        print(f"  {'-' * 10} {'-' * 12} {'-' * 40}")
        for m in extra_in_db:
            print(f"  {m['db_code']:<10} {m['db_espn_id']:<12} {m['db_name']:<40}")

    print()


def generate_sql_updates(
    league: str,
    mismatches: list[dict[str, str]],
    missing_from_db: list[dict[str, str]],
    espn_teams: list[dict[str, Any]],
) -> str:
    """Generate SQL UPDATE and INSERT statements.

    Args:
        league: League key (nhl, nba, ncaab)
        mismatches: Teams with differing ESPN IDs
        missing_from_db: Teams in ESPN but not in DB
        espn_teams: Full ESPN team data for INSERT defaults

    Returns:
        SQL string with UPDATE and INSERT statements

    Educational Note:
        We use the (team_code, sport) composite unique constraint for WHERE
        clauses since team_code alone can collide across sports (e.g., PHI
        in both NFL and NBA).
    """
    sport_map = {"nhl": "nhl", "nba": "nba", "ncaab": "ncaab"}
    sport = sport_map[league]

    lines: list[str] = []
    lines.append("-- ============================================================================")
    lines.append(f"-- {league.upper()} ESPN ID Fixes - Auto-generated by fix_espn_team_ids.py")
    lines.append("-- ============================================================================")
    lines.append("-- Run against precog_dev database")
    lines.append("")

    if mismatches:
        lines.append(f"-- UPDATE {len(mismatches)} teams with corrected ESPN IDs")
        lines.append("BEGIN;")
        lines.append("")

        for m in mismatches:
            lines.append(f"-- {m['db_name']}: {m['db_espn_id']} -> {m['api_espn_id']}")
            lines.append(
                f"UPDATE teams SET espn_team_id = '{m['api_espn_id']}' "  # noqa: S608
                f"WHERE team_code = '{m['db_code']}' AND sport = '{sport}';"
            )
            lines.append("")

        lines.append("-- Verify updates")
        lines.append(
            f"SELECT team_code, team_name, espn_team_id FROM teams "  # noqa: S608
            f"WHERE sport = '{sport}' ORDER BY team_code;"
        )
        lines.append("")
        lines.append("COMMIT;")
    else:
        lines.append(f"-- No ESPN ID updates needed for {league.upper()}")

    if missing_from_db and league != "ncaab":
        # For NHL/NBA, missing teams are notable. For NCAAB, we only seed top ~90.
        lines.append("")
        lines.append(
            "-- ============================================================================"
        )
        lines.append(f"-- INSERT missing {league.upper()} teams")
        lines.append(
            "-- ============================================================================"
        )

        # Build lookup by code from ESPN data
        espn_by_code: dict[str, dict[str, Any]] = {}
        for team in espn_teams:
            espn_by_code[team.get("abbreviation", "")] = team

        for m in missing_from_db:
            display = m.get("display_name", m["name"])
            lines.append(
                f"INSERT INTO teams (team_code, team_name, display_name, sport, league, "  # noqa: S608
                f"espn_team_id, current_elo_rating, conference, division) VALUES "
                f"('{m['espn_code']}', '{m['name']}', '{display}', '{sport}', '{sport}', "
                f"'{m['espn_id']}', 1500, NULL, NULL);"
            )

    lines.append("")
    return "\n".join(lines)


def check_duplicate_espn_ids(seed_teams: dict[str, dict[str, str]], league: str) -> None:
    """Check for duplicate ESPN IDs within a league's seed data.

    Args:
        seed_teams: Teams from seed file
        league: League name for display

    Educational Note:
        ESPN IDs should be unique per league. Duplicates indicate data entry
        errors in the seed files (e.g., copy-paste mistakes).
    """
    id_to_teams: dict[str, list[str]] = {}
    for code, team in seed_teams.items():
        espn_id = team["espn_team_id"]
        if espn_id not in id_to_teams:
            id_to_teams[espn_id] = []
        id_to_teams[espn_id].append(code)

    duplicates = {eid: codes for eid, codes in id_to_teams.items() if len(codes) > 1}
    if duplicates:
        print(f"\n  WARNING: Duplicate ESPN IDs in {league.upper()} seed file:")
        for eid, codes in sorted(duplicates.items()):
            print(f"    ESPN ID '{eid}' is used by: {', '.join(codes)}")
    else:
        print(f"\n  No duplicate ESPN IDs in {league.upper()} seed file")


def check_database(league: str) -> dict[str, dict[str, str]] | None:
    """Query the precog_dev database for current team data.

    Args:
        league: League key (nhl, nba, ncaab)

    Returns:
        Dict keyed by team_code with team data, or None if DB unavailable

    Educational Note:
        Uses psycopg2 directly to avoid ORM overhead for this utility script.
        Connection details come from environment variables following the
        credential pattern: {PRECOG_ENV}_* prefix.
    """
    import os

    try:
        import psycopg2
    except ImportError:
        logger.warning("psycopg2 not available - skipping database check")
        return None

    # Try to connect using environment variables
    db_host = os.getenv("DEV_DB_HOST", "localhost")
    db_port = os.getenv("DEV_DB_PORT", "5432")
    db_name = os.getenv("DEV_DB_NAME", "precog_dev")
    db_user = os.getenv("DEV_DB_USER", "precog")
    db_password = os.getenv("DEV_DB_PASSWORD", "")

    if not db_password:
        logger.info("No DEV_DB_PASSWORD set - skipping database check")
        return None

    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password,
        )
        cursor = conn.cursor()
        cursor.execute(
            "SELECT team_code, team_name, display_name, espn_team_id, conference, division "
            "FROM teams WHERE league = %s ORDER BY team_code",
            (league,),
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        teams: dict[str, dict[str, str]] = {}
        for row in rows:
            teams[row[0]] = {
                "team_code": row[0],
                "team_name": row[1],
                "display_name": row[2] or "",
                "espn_team_id": row[3] or "",
                "conference": row[4] or "",
                "division": row[5] or "",
            }

        logger.info(f"Loaded {len(teams)} {league.upper()} teams from database")
        return teams

    except Exception as e:
        logger.warning(f"Could not connect to database: {e}")
        return None


def print_full_espn_team_list(league: str, espn_teams: list[dict[str, Any]]) -> None:
    """Print all teams from ESPN API for reference.

    Args:
        league: League name
        espn_teams: Raw ESPN team data
    """
    print(f"\n  ALL {league.upper()} TEAMS FROM ESPN API ({len(espn_teams)} teams):")
    print(f"  {'ESPN ID':<10} {'Code':<8} {'Team Name':<40} {'Location':<25}")
    print(f"  {'-' * 10} {'-' * 8} {'-' * 40} {'-' * 25}")

    sorted_teams = sorted(espn_teams, key=lambda t: t.get("abbreviation", ""))
    for team in sorted_teams:
        parsed = parse_espn_team(team)
        print(
            f"  {parsed['espn_id']:<10} {parsed['code']:<8} "
            f"{parsed['name']:<40} {parsed['display_name']:<25}"
        )


def main() -> None:
    """Main entry point for ESPN team ID comparison and fix generation.

    Educational Note:
        This script follows a three-step process:
        1. Fetch authoritative data from ESPN API
        2. Compare against our seed files (and optionally live DB)
        3. Generate SQL to fix any discrepancies

        This approach ensures we use ESPN as the single source of truth
        for team IDs rather than manual lookup.
    """
    parser = argparse.ArgumentParser(description="Compare and fix ESPN team IDs in precog database")
    parser.add_argument(
        "--check-db",
        action="store_true",
        help="Also check against live precog_dev database",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Show full ESPN team lists for reference",
    )
    parser.add_argument(
        "--leagues",
        nargs="+",
        default=["nhl", "nba", "ncaab"],
        choices=["nhl", "nba", "ncaab"],
        help="Which leagues to check (default: all three)",
    )
    parser.add_argument(
        "--output-sql",
        type=str,
        default=None,
        help="Write SQL fix statements to this file",
    )
    args = parser.parse_args()

    print("\n" + "=" * 90)
    print("  ESPN TEAM ID AUDIT - Comparing ESPN API vs Seed Files")
    print("=" * 90)

    all_sql: list[str] = []

    for league in args.leagues:
        print(f"\n{'~' * 90}")
        print(f"  Processing {league.upper()}...")
        print(f"{'~' * 90}")

        # Step 1: Fetch from ESPN API
        try:
            espn_teams = fetch_espn_teams(league)
        except Exception as e:
            logger.error(f"Failed to fetch {league.upper()} teams from ESPN: {e}")
            continue

        if args.show_all:
            print_full_espn_team_list(league, espn_teams)

        # Step 2: Load seed file data
        seed_teams = load_seed_teams(league)
        if not seed_teams:
            logger.warning(f"No seed data loaded for {league.upper()}")
            continue

        # Step 2b: Check for duplicate ESPN IDs in seed file
        check_duplicate_espn_ids(seed_teams, league)

        # Step 3: Compare
        mismatches, missing_from_db, extra_in_db = compare_teams(league, espn_teams, seed_teams)

        # Step 4: Print results
        print_comparison_table(league, mismatches, missing_from_db, extra_in_db)

        # Step 5: Generate SQL
        sql = generate_sql_updates(league, mismatches, missing_from_db, espn_teams)
        all_sql.append(sql)
        print(sql)

        # Step 6: Optionally check live database
        if args.check_db:
            db_teams = check_database(league)
            if db_teams:
                print("\n  DATABASE vs ESPN API comparison:")
                db_mismatches, db_missing, db_extra = compare_teams(league, espn_teams, db_teams)
                print_comparison_table(f"{league} (DATABASE)", db_mismatches, db_missing, db_extra)

    # Write SQL to file if requested
    if args.output_sql:
        combined_sql = "\n\n".join(all_sql)
        with open(args.output_sql, "w", encoding="utf-8") as f:
            f.write(combined_sql)
        print(f"\nSQL statements written to: {args.output_sql}")

    print("\n" + "=" * 90)
    print("  AUDIT COMPLETE")
    print("=" * 90)
    print()


if __name__ == "__main__":
    main()
