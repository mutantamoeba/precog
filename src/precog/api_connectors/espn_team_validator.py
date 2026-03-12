"""
ESPN team ID startup validation module.

This module validates that ESPN team IDs stored in the database match the
authoritative team data from ESPN's public teams API. It can be called at
poller startup to detect and optionally correct mismatches before polling
begins.

Key Features:
- Fetches team lists from ESPN API for NFL, NBA, NHL, NCAAF leagues
- Compares ESPN IDs against the database using existing CRUD functions
- Reports mismatches with structured logging
- Optionally auto-corrects mismatched IDs in the database
- Graceful error handling: validation failure never prevents poller startup

Educational Notes:
------------------
ESPN Teams Endpoint:
    ESPN provides a public teams endpoint at:
        https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/teams
    This returns ALL teams for a league with their ESPN IDs, abbreviations,
    display names, conference, and division info. This is separate from
    the scoreboard endpoint used for live game data.

Code Aliases:
    ESPN abbreviations sometimes differ from our database codes. For example,
    ESPN uses 'WSH' for the Washington Commanders while our DB uses 'WAS'.
    The CODE_ALIASES mapping handles these known discrepancies so validation
    doesn't produce false-positive mismatches.

Reference: docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md
Related:
    - scripts/fix_espn_team_ids.py (standalone audit script this builds upon)
    - src/precog/database/crud_operations.py (get_team_by_espn_id)
    - src/precog/schedulers/espn_game_poller.py (integration point)
"""

import logging
import time
from typing import Any

import requests

from precog.database.connection import fetch_one, get_cursor
from precog.database.crud_operations import create_team, get_team_by_espn_id

logger = logging.getLogger(__name__)

# =============================================================================
# ESPN Teams API Configuration
# =============================================================================

ESPN_TEAMS_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"

# Sport/league mapping for ESPN teams endpoint
# Keys are our internal league codes, values define ESPN URL parameters
LEAGUE_CONFIGS: dict[str, dict[str, Any]] = {
    "nfl": {
        "sport": "football",
        "league": "nfl",
        "url": f"{ESPN_TEAMS_BASE_URL}/football/nfl/teams",
        "expected_teams": 32,
    },
    "nba": {
        "sport": "basketball",
        "league": "nba",
        "url": f"{ESPN_TEAMS_BASE_URL}/basketball/nba/teams",
        "expected_teams": 30,
    },
    "nhl": {
        "sport": "hockey",
        "league": "nhl",
        "url": f"{ESPN_TEAMS_BASE_URL}/hockey/nhl/teams",
        "expected_teams": 32,
    },
    "ncaaf": {
        "sport": "football",
        "league": "college-football",
        "url": f"{ESPN_TEAMS_BASE_URL}/football/college-football/teams",
        "expected_teams": 134,  # FBS teams; ESPN returns many more
    },
}

# =============================================================================
# Code Aliases: ESPN abbreviation -> our DB team_code
# =============================================================================
# ESPN API sometimes uses different abbreviations than our database codes.
# These mappings translate ESPN codes to our codes for accurate matching.

CODE_ALIASES: dict[str, dict[str, str]] = {
    "nfl": {
        "WSH": "WAS",  # ESPN uses 'WSH' for Commanders, we use 'WAS'
        "JAX": "JAX",  # Same, but included for documentation
    },
    "nba": {
        "GS": "GSW",  # ESPN uses 'GS' for Warriors, we use 'GSW'
        "NO": "NOP",  # ESPN uses 'NO' for Pelicans, we use 'NOP'
        "NY": "NYK",  # ESPN uses 'NY' for Knicks, we use 'NYK'
        "SA": "SAS",  # ESPN uses 'SA' for Spurs, we use 'SAS'
        "UTAH": "UTA",  # ESPN uses 'UTAH' for Jazz, we use 'UTA'
        "WSH": "WAS",  # ESPN uses 'WSH' for Wizards, we use 'WAS'
    },
    "nhl": {
        "LA": "LAK",  # ESPN uses 'LA' for Kings, we use 'LAK'
        "TB": "TBL",  # ESPN uses 'TB' for Lightning, we use 'TBL'
        "SJ": "SJS",  # ESPN uses 'SJ' for Sharks, we use 'SJS'
        "NJ": "NJD",  # ESPN uses 'NJ' for Devils, we use 'NJD'
        "UTAH": "UTA",  # ESPN uses 'UTAH' for Utah Hockey Club, we use 'UTA'
    },
    "ncaaf": {
        "ARIZ": "AZU",  # ESPN uses 'ARIZ' for Arizona, we use 'AZU'
        "COLO": "COL",  # ESPN uses 'COLO' for Colorado, we use 'COL'
        "DEP": "DPU",  # ESPN uses 'DEP' for DePaul, we use 'DPU'
        "DRKE": "DRAKE",  # ESPN uses 'DRKE' for Drake, we use 'DRAKE'
        "IU": "IND",  # ESPN uses 'IU' for Indiana, we use 'IND'
        "MIZ": "MIZZ",  # ESPN uses 'MIZ' for Missouri, we use 'MIZZ'
        "UNC": "NC",  # ESPN uses 'UNC' for North Carolina, we use 'NC'
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


# =============================================================================
# ESPN API Fetch Functions
# =============================================================================


def fetch_espn_teams(league: str, limit: int = 100) -> list[dict[str, Any]]:
    """Fetch all teams from ESPN API for a given league.

    Uses pagination to retrieve all teams, handling large college football
    rosters that exceed a single page.

    Args:
        league: League key from LEAGUE_CONFIGS (nfl, nba, nhl, ncaaf)
        limit: Page size for ESPN API pagination (default 100)

    Returns:
        List of team dicts with id, abbreviation, displayName, etc.

    Raises:
        requests.RequestException: If API returns error status after request

    Educational Note:
        The ESPN teams endpoint supports pagination via ?limit=N&page=P.
        For professional leagues (NFL=32, NBA=30, NHL=32) one page suffices.
        For college (134+ FBS teams), we paginate to be safe.

    Related:
        - scripts/fix_espn_team_ids.py (fetch_espn_teams function)
    """
    config = LEAGUE_CONFIGS[league]
    url = str(config["url"])
    all_teams: list[dict[str, Any]] = []
    page = 1

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Precog/1.0 (Sports Analytics - Team ID Validation)",
            "Accept": "application/json",
        }
    )

    try:
        while True:
            params = {"limit": limit, "page": page}
            logger.debug(
                "Fetching %s teams page %d from ESPN API...",
                league.upper(),
                page,
            )

            response = session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            # ESPN returns teams under "sports" -> [0] -> "leagues" -> [0] -> "teams"
            sports = data.get("sports", [])
            if not sports:
                break

            leagues_data = sports[0].get("leagues", [])
            if not leagues_data:
                break

            teams_wrapper = leagues_data[0].get("teams", [])
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
    finally:
        session.close()

    logger.debug(
        "Fetched %d %s teams from ESPN API",
        len(all_teams),
        league.upper(),
    )
    return all_teams


def _resolve_db_code(espn_code: str, league: str) -> str:
    """Resolve an ESPN abbreviation to the database team_code.

    Applies CODE_ALIASES to translate known differences between ESPN
    abbreviations and our database codes.

    Args:
        espn_code: Team abbreviation from ESPN API (e.g., 'WSH')
        league: League key (nfl, nba, nhl, ncaaf)

    Returns:
        The corresponding database team_code (e.g., 'WAS')

    Educational Note:
        This is a simple lookup: if the ESPN code is in our alias map
        for this league, return the mapped code. Otherwise, return the
        ESPN code unchanged (it matches our DB code already).

    Related:
        - CODE_ALIASES dict in this module
    """
    aliases = CODE_ALIASES.get(league, {})
    return aliases.get(espn_code, espn_code)


def _get_team_by_espn_id_or_code(
    espn_id: str,
    team_code: str,
    league: str,
) -> dict[str, Any] | None:
    """Look up a team by ESPN ID first, falling back to team_code + league.

    ESPN-ID-first lookup is critical for NCAAF where multiple teams share
    the same abbreviation code (e.g., 5 teams with code 'WES'). Looking up
    by code alone causes ping-ponging between wrong team records on every
    validator restart.

    Lookup order:
        1. Try ESPN ID + league (unique, authoritative match)
        2. Fall back to team_code + league (backward compat for teams
           that don't have an ESPN ID yet)

    Args:
        espn_id: ESPN's unique team identifier (e.g., '12' for Chiefs)
        team_code: Our database team code (e.g., 'KC', 'WAS')
        league: League identifier (nfl, nba, nhl, ncaaf)

    Returns:
        Dictionary with team data, or None if not found by either method.

    Educational Note:
        After migration 0018, the teams table uses espn_team_id + league
        as the preferred lookup path. The code+league fallback handles
        legacy teams that were created before ESPN IDs were populated.

    Related:
        - src/precog/database/crud_operations.py (get_team_by_espn_id)
    """
    # Primary lookup: ESPN ID + league (authoritative)
    if espn_id:
        db_team = get_team_by_espn_id(espn_id, league=league)
        if db_team is not None:
            # If found by ESPN ID but code differs, warn for visibility
            db_code = db_team.get("team_code", "")
            if db_code != team_code:
                logger.warning(
                    "Team found by ESPN ID %s in %s: DB code '%s' differs "
                    "from resolved code '%s' (alias or code change)",
                    espn_id,
                    league.upper(),
                    db_code,
                    team_code,
                )
            return db_team

    # Fallback: code + league (for teams without ESPN IDs)
    return fetch_one(
        "SELECT * FROM teams WHERE team_code = %s AND (sport = %s OR league = %s)",
        (team_code, league, league),
    )


# =============================================================================
# Team Auto-Creation (Pro Leagues Only)
# =============================================================================

# All leagues configured in LEAGUE_CONFIGS are eligible for auto-creation.
# If we poll a league, we should keep its teams synced.

# Sport mapping for the teams table 'sport' column.
# For pro leagues, sport == league. Kept explicit for clarity.
LEAGUE_SPORT_MAP: dict[str, str] = {
    "nfl": "nfl",
    "nba": "nba",
    "nhl": "nhl",
    "ncaaf": "ncaaf",
}


def _create_missing_team(
    espn_team: dict[str, Any],
    db_code: str,
    league: str,
) -> int | None:
    """Create a missing team record from ESPN API data.

    Called when a team exists in ESPN's API but not in our database.
    Creates the team with NULL Elo rating (real Elo must be computed
    by the EloEngine from game results, never defaulted to 1500).

    Args:
        espn_team: Raw team dict from ESPN API response. Expected keys:
            id, abbreviation, displayName, shortDisplayName.
        db_code: Resolved database team code (after alias mapping).
        league: League key (nfl, nba, nhl, ncaaf).

    Returns:
        team_id of the created team, or None if creation failed.

    Educational Note:
        Conference/division info is not reliably available in the ESPN
        teams list response at the team level. The 'groups' field may
        contain conference info but the structure varies by sport.
        We create the team without conference/division and let future
        updates fill that in if needed.

    Related:
        - validate_league_teams() (calls this when auto_correct=True)
        - create_team() in crud_operations.py
    """
    espn_id = str(espn_team.get("id", ""))
    team_name = espn_team.get("displayName", "")
    display_name = espn_team.get("shortDisplayName", "") or team_name
    sport = LEAGUE_SPORT_MAP.get(league, league)

    if not espn_id or not team_name:
        logger.warning(
            "Cannot create team: missing ESPN ID or name for %s %s",
            league.upper(),
            db_code,
        )
        return None

    try:
        team_id = create_team(
            team_code=db_code,
            team_name=team_name,
            display_name=display_name,
            sport=sport,
            league=league,
            espn_team_id=espn_id,
            current_elo_rating=None,  # Real Elo must come from EloEngine
            conference=None,
            division=None,
        )
        logger.info(
            "Auto-created missing team: %s %s (%s, espn_id=%s, team_id=%d)",
            league.upper(),
            db_code,
            team_name,
            espn_id,
            team_id,
        )
        return team_id
    except Exception as e:
        logger.error(
            "Failed to auto-create team %s %s (%s): %s",
            league.upper(),
            db_code,
            team_name,
            e,
        )
        return None


# =============================================================================
# Core Validation Logic
# =============================================================================


def validate_league_teams(
    league: str,
    auto_correct: bool = False,
) -> dict[str, Any]:
    """Validate ESPN team IDs for a single league against the database.

    Fetches the authoritative team list from ESPN's teams API, then
    compares each team's ESPN ID against what is stored in the database.
    Reports mismatches and optionally corrects them.

    Args:
        league: League to validate (nfl, nba, nhl, ncaaf)
        auto_correct: If True, update mismatched ESPN IDs in the database.
            Default False (report only).

    Returns:
        Dict with validation results:
            - league: League code
            - teams_checked: Number of teams compared
            - mismatches: List of mismatch details
            - errors: List of error messages (if any)

    Educational Note:
        The validation process matches teams in two ways:
        1. By team_code (with alias resolution): ESPN 'WSH' -> our 'WAS'
        2. By ESPN ID: If codes don't match, try finding by ESPN ID

        This dual-lookup approach catches both code alias mismatches and
        genuine ESPN ID discrepancies in the database.

    Related:
        - validate_espn_teams() (multi-league orchestrator)
        - scripts/fix_espn_team_ids.py (standalone audit script)
    """
    result: dict[str, Any] = {
        "league": league,
        "teams_checked": 0,
        "teams_created": 0,
        "mismatches": [],
        "errors": [],
    }

    if league not in LEAGUE_CONFIGS:
        result["errors"].append(f"Unsupported league: {league}")
        return result

    # Step 1: Fetch teams from ESPN API
    try:
        espn_teams = fetch_espn_teams(league)
    except requests.RequestException as e:
        error_msg = f"Failed to fetch {league.upper()} teams from ESPN API: {e}"
        logger.warning(error_msg)
        result["errors"].append(error_msg)
        return result

    if not espn_teams:
        logger.info("No teams returned from ESPN API for %s", league.upper())
        return result

    # Step 2: Compare each ESPN team against the database
    teams_checked = 0
    teams_created = 0
    mismatches: list[dict[str, str]] = []

    for espn_team_raw in espn_teams:
        espn_id = str(espn_team_raw.get("id", ""))
        espn_code = espn_team_raw.get("abbreviation", "")
        espn_name = espn_team_raw.get("displayName", "")

        if not espn_id or not espn_code:
            continue

        # Resolve the ESPN code to our DB code (applying aliases)
        db_code = _resolve_db_code(espn_code, league)

        # Look up the team: ESPN ID first, then fall back to code + league
        db_team = _get_team_by_espn_id_or_code(espn_id, db_code, league)

        if db_team is None:
            # Auto-create missing teams for any polled league when
            # auto_correct is enabled. If we poll it, we sync it.
            if auto_correct:
                created_id = _create_missing_team(
                    espn_team=espn_team_raw,
                    db_code=db_code,
                    league=league,
                )
                if created_id is not None:
                    teams_created += 1
                    teams_checked += 1
                    # Team just created with correct ESPN ID, no mismatch
                    continue
            else:
                logger.warning(
                    "Team missing from DB: %s %s (%s, espn_id=%s). "
                    "Run with auto_correct=True to create automatically.",
                    league.upper(),
                    espn_code,
                    espn_name,
                    espn_id,
                )
            continue

        teams_checked += 1

        # Compare ESPN IDs
        raw_espn_id = db_team.get("espn_team_id")
        if raw_espn_id is None:
            continue

        db_espn_id = str(raw_espn_id)

        if db_espn_id != espn_id:
            mismatch = {
                "team_code": db_code,
                "espn_code": espn_code,
                "team_name": espn_name,
                "db_espn_id": db_espn_id,
                "api_espn_id": espn_id,
            }
            mismatches.append(mismatch)
            logger.warning(
                "ESPN ID mismatch for %s %s (%s): DB has '%s', ESPN API has '%s'",
                league.upper(),
                db_code,
                espn_name,
                db_espn_id,
                espn_id,
            )

            # Auto-correct if configured
            if auto_correct:
                _correct_espn_id(
                    team_id=db_team["team_id"],
                    team_code=db_code,
                    league=league,
                    old_espn_id=db_espn_id,
                    new_espn_id=espn_id,
                )

    result["teams_checked"] = teams_checked
    result["teams_created"] = teams_created
    result["mismatches"] = mismatches

    logger.info(
        "Validated %d teams for %s, found %d mismatches, created %d new teams",
        teams_checked,
        league.upper(),
        len(mismatches),
        teams_created,
    )

    return result


def _correct_espn_id(
    team_id: int,
    team_code: str,
    league: str,
    old_espn_id: str,
    new_espn_id: str,
) -> None:
    """Update a team's ESPN ID in the database.

    Args:
        team_id: Primary key of the team row
        team_code: Team code for logging
        league: League for logging
        old_espn_id: Previous (incorrect) ESPN ID
        new_espn_id: Correct ESPN ID from the API

    Educational Note:
        This uses get_cursor(commit=True) to immediately commit the
        correction. Each correction is logged at WARNING level to
        ensure visibility in production logs.

    Related:
        - validate_league_teams() (calls this when auto_correct=True)
    """
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE teams SET espn_team_id = %s, updated_at = NOW() WHERE team_id = %s",
                (new_espn_id, team_id),
            )
            rows_updated = cur.rowcount or 0

        if rows_updated > 0:
            logger.warning(
                "Auto-corrected ESPN ID for %s %s: '%s' -> '%s'",
                league.upper(),
                team_code,
                old_espn_id,
                new_espn_id,
            )
        else:
            logger.warning(
                "Failed to auto-correct ESPN ID for %s %s (team_id=%d): no rows updated",
                league.upper(),
                team_code,
                team_id,
            )
    except Exception as e:
        logger.error(
            "Error auto-correcting ESPN ID for %s %s: %s",
            league.upper(),
            team_code,
            e,
        )


# =============================================================================
# Public API - Integration Point
# =============================================================================


def validate_espn_teams(
    leagues: list[str] | None = None,
    auto_correct: bool = False,
) -> dict[str, Any]:
    """Validate ESPN team IDs for multiple leagues against the database.

    This is the main entry point for the ESPN game poller to call at
    startup. It validates team IDs for each configured league and
    reports any mismatches found.

    Args:
        leagues: List of league codes to validate. Defaults to all
            supported leagues (nfl, nba, nhl, ncaaf).
        auto_correct: If True, update mismatched ESPN IDs in the database.
            Default False (report only).

    Returns:
        Dict with overall results:
            - total_checked: Total teams validated across all leagues
            - total_mismatches: Total mismatches found
            - leagues: Dict of per-league results from validate_league_teams()

    Educational Note:
        This function includes a 0.5s delay between league fetches to be
        a good ESPN API citizen. ESPN's public API has no official rate
        limits, but community reports suggest ~2,500 requests/day before
        IP blocking. The delay prevents burst requests at startup.

    Example:
        >>> results = validate_espn_teams(leagues=["nfl", "nba"])
        >>> print(f"Checked {results['total_checked']} teams")
        >>> print(f"Found {results['total_mismatches']} mismatches")

    Related:
        - ESPNGamePoller._on_start() (calls this at poller startup)
        - scripts/fix_espn_team_ids.py (standalone audit script)
    """
    if leagues is None:
        leagues = list(LEAGUE_CONFIGS.keys())

    overall: dict[str, Any] = {
        "total_checked": 0,
        "total_mismatches": 0,
        "total_created": 0,
        "leagues": {},
    }

    for idx, league in enumerate(leagues):
        if league not in LEAGUE_CONFIGS:
            logger.warning("Skipping unsupported league for validation: %s", league)
            continue

        # Rate limiting: 0.5s delay between league fetches
        if idx > 0:
            time.sleep(0.5)

        league_result = validate_league_teams(
            league=league,
            auto_correct=auto_correct,
        )

        overall["leagues"][league] = league_result
        overall["total_checked"] += league_result["teams_checked"]
        overall["total_mismatches"] += len(league_result["mismatches"])
        overall["total_created"] += league_result.get("teams_created", 0)

    logger.info(
        "ESPN team validation complete: checked %d teams across %d leagues, "
        "found %d total mismatches, created %d new teams",
        overall["total_checked"],
        len(overall["leagues"]),
        overall["total_mismatches"],
        overall["total_created"],
    )

    return overall
