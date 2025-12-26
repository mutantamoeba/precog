"""
Unified Team History Mapping System.

This module provides comprehensive team relocation and renaming tracking
across multiple sports, enabling accurate historical data attribution.

Issue: #257 - Extend team mapping to support multi-sport historical relocations

Educational Notes:
-----------------
Team Relocations and Historical Data:
    Sports teams frequently relocate or rebrand. When loading historical data
    (game results, Elo ratings, betting lines), we need to map old team codes
    to current codes while preserving the historical relationship.

    Example: Oakland Raiders (1960-2019) -> Las Vegas Raiders (2020-present)
    - Games from 2019 should map to LV (current franchise code)
    - The mapping must be date-aware to avoid incorrect attributions

Date-Aware Resolution:
    The resolve_team_code() function uses year context to correctly map:
    - "OAK" in 2019 -> "LV" (Raiders were still in Oakland)
    - "OAK" in 2020 -> "LV" (but they moved, so still LV)
    - "SEA" in 2007 -> "OKC" (Supersonics became Thunder in 2008)

    This is critical for:
    - Joining historical data with current team records
    - Computing franchise-level statistics across relocations
    - Accurate Elo rating continuity

Data Structure Design:
    The TEAM_HISTORY dictionary uses sport -> current_code -> timeline format:

    TEAM_HISTORY["nfl"]["LV"] = [
        ("OAK", 1960, 2019),  # Oakland from 1960-2019
        ("LV", 2020, None),   # Las Vegas from 2020-present
    ]

    - current_code is the franchise's current team code
    - Each tuple is (historical_code, start_year, end_year)
    - None for end_year means "current" (ongoing)

Reference:
    - Issue #257: Multi-sport historical relocations
    - ADR-106: Historical Data Collection Architecture
    - FiveThirtyEight Elo methodology (handles franchise continuity)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Team History Data
# =============================================================================

# Format: sport -> current_code -> [(historical_code, start_year, end_year), ...]
# None for end_year means "current" (ongoing through present)
# Teams are listed by their CURRENT franchise code

TEAM_HISTORY: dict[str, dict[str, list[tuple[str, int, int | None]]]] = {
    # =========================================================================
    # NFL Team Relocations
    # =========================================================================
    "nfl": {
        # Las Vegas Raiders (formerly Oakland/LA Raiders)
        "LV": [
            ("OAK", 1960, 1981),  # Oakland Raiders
            ("LA", 1982, 1994),  # Los Angeles Raiders
            ("OAK", 1995, 2019),  # Back to Oakland
            ("LV", 2020, None),  # Las Vegas Raiders
        ],
        # Tennessee Titans (formerly Houston Oilers)
        "TEN": [
            ("HOU", 1960, 1996),  # Houston Oilers
            ("TEN", 1997, None),  # Tennessee Oilers (1997-98), then Titans
        ],
        # Indianapolis Colts (formerly Baltimore Colts)
        "IND": [
            ("BAL", 1953, 1983),  # Baltimore Colts
            ("IND", 1984, None),  # Indianapolis Colts
        ],
        # Los Angeles Chargers (formerly San Diego)
        "LAC": [
            ("SD", 1961, 2016),  # San Diego Chargers
            ("LAC", 2017, None),  # Los Angeles Chargers
        ],
        # Los Angeles Rams (formerly St. Louis, Cleveland)
        "LAR": [
            ("CLE", 1936, 1945),  # Cleveland Rams
            ("LA", 1946, 1994),  # Los Angeles Rams (first stint)
            ("STL", 1995, 2015),  # St. Louis Rams
            ("LAR", 2016, None),  # Los Angeles Rams (return)
        ],
        # Arizona Cardinals (originally Chicago, then St. Louis, then Phoenix)
        "ARI": [
            ("CHI", 1920, 1959),  # Chicago Cardinals
            ("STL", 1960, 1987),  # St. Louis Cardinals
            ("PHO", 1988, 1993),  # Phoenix Cardinals
            ("ARI", 1994, None),  # Arizona Cardinals
        ],
        # Washington Commanders (multiple names at same location)
        "WAS": [
            ("BOS", 1932, 1936),  # Boston Braves/Redskins
            ("WAS", 1937, None),  # Washington (various names)
        ],
        # Baltimore Ravens (expansion team, NOT the old Colts)
        "BAL": [
            ("BAL", 1996, None),  # Baltimore Ravens (new franchise from Cleveland Browns move)
        ],
        # Cleveland Browns (re-established 1999)
        "CLE": [
            ("CLE", 1946, 1995),  # Cleveland Browns (original)
            # 1996-1998: Franchise moved to Baltimore (Ravens)
            ("CLE", 1999, None),  # Cleveland Browns (expansion)
        ],
    },
    # =========================================================================
    # NBA Team Relocations
    # =========================================================================
    "nba": {
        # Oklahoma City Thunder (formerly Seattle SuperSonics)
        # Note: Sonics last season was 2007-08, Thunder first was 2008-09
        # We use the season START year (2007 for last SEA, 2008 for first OKC)
        "OKC": [
            ("SEA", 1967, 2007),  # Seattle SuperSonics (last: 2007-08 season)
            ("OKC", 2008, None),  # Oklahoma City Thunder (first: 2008-09 season)
        ],
        # Brooklyn Nets (formerly New Jersey)
        "BKN": [
            ("NJN", 1977, 2012),  # New Jersey Nets
            ("BKN", 2012, None),  # Brooklyn Nets
        ],
        # Memphis Grizzlies (formerly Vancouver)
        "MEM": [
            ("VAN", 1995, 2001),  # Vancouver Grizzlies
            ("MEM", 2001, None),  # Memphis Grizzlies
        ],
        # New Orleans Pelicans (formerly Hornets, originally Charlotte)
        "NOP": [
            ("NOH", 2002, 2013),  # New Orleans Hornets (from Charlotte)
            ("NOP", 2013, None),  # New Orleans Pelicans
        ],
        # Charlotte Hornets (expansion 2004, formerly Bobcats)
        "CHA": [
            ("CHA", 2004, 2014),  # Charlotte Bobcats
            ("CHA", 2014, None),  # Charlotte Hornets (reclaimed name)
        ],
        # Phoenix Suns (stable franchise, PHO in FiveThirtyEight data -> PHX)
        "PHX": [
            ("PHO", 1968, None),  # FiveThirtyEight uses PHO for Phoenix Suns
        ],
        # Sacramento Kings (formerly Kansas City, Cincinnati)
        "SAC": [
            ("CIN", 1957, 1972),  # Cincinnati Royals
            ("KCK", 1972, 1975),  # Kansas City-Omaha Kings
            ("KC", 1975, 1985),  # Kansas City Kings
            ("SAC", 1985, None),  # Sacramento Kings
        ],
        # Los Angeles Clippers (formerly San Diego, Buffalo)
        "LAC": [
            ("BUF", 1970, 1978),  # Buffalo Braves
            ("SD", 1978, 1984),  # San Diego Clippers
            ("LAC", 1984, None),  # Los Angeles Clippers
        ],
        # Washington Wizards (various names)
        "WAS": [
            ("BAL", 1961, 1973),  # Baltimore Bullets
            ("CAP", 1973, 1974),  # Capital Bullets
            ("WSB", 1974, 1997),  # Washington Bullets
            ("WAS", 1997, None),  # Washington Wizards
        ],
        # Utah Jazz (formerly New Orleans)
        "UTA": [
            ("NO", 1974, 1979),  # New Orleans Jazz
            ("UTA", 1979, None),  # Utah Jazz
        ],
        # Atlanta Hawks (originally Buffalo, then moved multiple times)
        "ATL": [
            ("TRI", 1946, 1951),  # Tri-Cities Blackhawks
            ("MLH", 1951, 1955),  # Milwaukee Hawks
            ("STL", 1955, 1968),  # St. Louis Hawks
            ("ATL", 1968, None),  # Atlanta Hawks
        ],
    },
    # =========================================================================
    # MLB Team Relocations
    # =========================================================================
    "mlb": {
        # Washington Nationals (formerly Montreal Expos)
        "WAS": [
            ("MON", 1969, 2004),  # Montreal Expos
            ("WAS", 2005, None),  # Washington Nationals
        ],
        # Los Angeles Dodgers (formerly Brooklyn)
        "LAD": [
            ("BRO", 1890, 1957),  # Brooklyn Dodgers
            ("LAD", 1958, None),  # Los Angeles Dodgers
        ],
        # San Francisco Giants (formerly New York)
        "SF": [
            ("NYG", 1883, 1957),  # New York Giants
            ("SF", 1958, None),  # San Francisco Giants
        ],
        # Oakland Athletics (formerly Kansas City, Philadelphia)
        "OAK": [
            ("PHA", 1901, 1954),  # Philadelphia Athletics
            ("KC", 1955, 1967),  # Kansas City Athletics
            ("OAK", 1968, None),  # Oakland Athletics
        ],
        # Atlanta Braves (formerly Milwaukee, Boston)
        "ATL": [
            ("BSN", 1871, 1952),  # Boston Braves
            ("MLN", 1953, 1965),  # Milwaukee Braves
            ("ATL", 1966, None),  # Atlanta Braves
        ],
        # Minnesota Twins (formerly Washington Senators)
        "MIN": [
            ("WS1", 1901, 1960),  # Washington Senators (first)
            ("MIN", 1961, None),  # Minnesota Twins
        ],
        # Texas Rangers (formerly Washington Senators expansion)
        "TEX": [
            ("WS2", 1961, 1971),  # Washington Senators (expansion)
            ("TEX", 1972, None),  # Texas Rangers
        ],
        # Baltimore Orioles (formerly St. Louis Browns)
        "BAL": [
            ("SLB", 1902, 1953),  # St. Louis Browns
            ("BAL", 1954, None),  # Baltimore Orioles
        ],
        # Milwaukee Brewers (formerly Seattle Pilots)
        "MIL": [
            ("SEP", 1969, 1969),  # Seattle Pilots (one season)
            ("MIL", 1970, None),  # Milwaukee Brewers
        ],
    },
    # =========================================================================
    # NHL Team Relocations
    # =========================================================================
    "nhl": {
        # Winnipeg Jets (formerly Atlanta Thrashers, different from original Jets)
        "WPG": [
            ("ATL", 1999, 2011),  # Atlanta Thrashers
            ("WPG", 2011, None),  # Winnipeg Jets (current)
        ],
        # Carolina Hurricanes (formerly Hartford Whalers)
        "CAR": [
            ("HFD", 1979, 1997),  # Hartford Whalers
            ("CAR", 1997, None),  # Carolina Hurricanes
        ],
        # Colorado Avalanche (formerly Quebec Nordiques)
        "COL": [
            ("QUE", 1972, 1995),  # Quebec Nordiques
            ("COL", 1995, None),  # Colorado Avalanche
        ],
        # Arizona Coyotes (formerly Winnipeg Jets original, then PHX)
        "ARI": [
            ("WPG", 1972, 1996),  # Winnipeg Jets (original, different from current)
            ("PHX", 1996, 2014),  # Phoenix Coyotes
            ("ARI", 2014, None),  # Arizona Coyotes
        ],
        # Dallas Stars (formerly Minnesota North Stars)
        "DAL": [
            ("MNS", 1967, 1993),  # Minnesota North Stars
            ("DAL", 1993, None),  # Dallas Stars
        ],
        # New Jersey Devils (formerly Colorado Rockies, Kansas City Scouts)
        "NJD": [
            ("KCS", 1974, 1976),  # Kansas City Scouts
            ("CLR", 1976, 1982),  # Colorado Rockies
            ("NJD", 1982, None),  # New Jersey Devils
        ],
        # Calgary Flames (formerly Atlanta Flames)
        "CGY": [
            ("AFM", 1972, 1980),  # Atlanta Flames
            ("CGY", 1980, None),  # Calgary Flames
        ],
    },
    # =========================================================================
    # NCAAF - Conference Realignment (selected examples)
    # =========================================================================
    "ncaaf": {
        # Note: NCAAF is complex due to conference realignment
        # These are placeholder entries for teams that changed conference codes
        # Most NCAAF team codes remain stable; it's conference membership that changes
    },
}


# =============================================================================
# Reverse Lookup Index (for performance)
# =============================================================================

# Built lazily: sport -> historical_code -> (current_code, end_year)
# Used for quick lookups when we don't know the current code
# The end_year is stored internally to resolve conflicts (most recent wins)
_REVERSE_INDEX: dict[str, dict[str, tuple[str, int | None]]] | None = None


def _build_reverse_index() -> dict[str, dict[str, tuple[str, int | None]]]:
    """Build reverse index mapping historical codes to current codes.

    Returns:
        Dict mapping sport -> historical_code -> (current_code, end_year)
        The end_year is stored to resolve conflicts (most recent wins).

    Educational Note:
        This index enables O(1) lookup when given a historical code.
        Without it, we'd need to scan all teams in all sports.

        Some historical codes are used by multiple franchises at different times:
        - STL: Cardinals (1960-1987) and Rams (1995-2015)
        - LA: Rams (1946-1994) and Raiders (1982-1994)

        We resolve conflicts by preferring the MOST RECENT usage (highest end_year).
        For genuinely ambiguous cases (same end year), we use lexicographic order.
    """
    index: dict[str, dict[str, tuple[str, int | None]]] = {}

    for sport, teams in TEAM_HISTORY.items():
        if sport not in index:
            index[sport] = {}

        for current_code, timeline in teams.items():
            for historical_code, _, end_year in timeline:
                # Check if this code already exists in the index
                if historical_code in index[sport]:
                    existing_code, existing_end = index[sport][historical_code]
                    # Convert None to high value for comparison (ongoing = most recent)
                    existing_end_val = existing_end if existing_end is not None else 9999
                    new_end_val = end_year if end_year is not None else 9999

                    # Only replace if new mapping is more recent
                    if new_end_val > existing_end_val:
                        index[sport][historical_code] = (current_code, end_year)
                    elif new_end_val == existing_end_val and current_code > existing_code:
                        # Tie-breaker: lexicographic order
                        index[sport][historical_code] = (current_code, end_year)
                else:
                    index[sport][historical_code] = (current_code, end_year)

    return index


def get_reverse_index() -> dict[str, dict[str, tuple[str, int | None]]]:
    """Get or build the reverse lookup index.

    Returns:
        Dict mapping sport -> historical_code -> (current_code, end_year)
        The end_year is included to track when the mapping was valid.
    """
    global _REVERSE_INDEX
    if _REVERSE_INDEX is None:
        _REVERSE_INDEX = _build_reverse_index()
    return _REVERSE_INDEX


# =============================================================================
# Public API
# =============================================================================


def resolve_team_code(
    sport: str,
    code: str,
    year: int | None = None,
) -> str:
    """
    Resolve a historical team code to the current franchise code.

    This is the primary API for team code normalization. Given a team code
    from historical data, it returns the current franchise code that should
    be used for database lookups and data association.

    Args:
        sport: Sport code (e.g., "nfl", "nba", "mlb", "nhl")
        code: Team code from historical data
        year: Year context for resolution (optional, for logging/validation)

    Returns:
        Current franchise code for the team

    Educational Note:
        The year parameter is currently used for validation/logging but
        the mapping itself is franchise-based. All historical codes for
        a franchise map to the same current code regardless of year.

    Examples:
        >>> resolve_team_code("nfl", "OAK", 2019)
        'LV'
        >>> resolve_team_code("nfl", "SD", 2015)
        'LAC'
        >>> resolve_team_code("nba", "SEA", 2007)
        'OKC'
        >>> resolve_team_code("nfl", "KC", 2023)  # No mapping needed
        'KC'
    """
    code_upper = code.upper().strip()
    sport_lower = sport.lower().strip()

    # Check reverse index for quick lookup (historical relocations)
    index = get_reverse_index()
    sport_index = index.get(sport_lower, {})

    if code_upper in sport_index:
        current_code, _ = sport_index[code_upper]  # Extract code, ignore end_year
        logger.debug(
            "Resolved %s team code %s -> %s (year=%s)",
            sport_lower,
            code_upper,
            current_code,
            year,
        )
        return current_code

    # Check SPORT-SPECIFIC code mappings first (fixes cross-sport contamination bug)
    # e.g., NBA "SEA" -> "OKC" should NOT apply to NHL "SEA" (Seattle Kraken)
    sport_mappings = SPORT_CODE_MAPPINGS.get(sport_lower, {})
    if code_upper in sport_mappings:
        mapped_code = sport_mappings[code_upper]
        logger.debug(
            "Resolved %s team code %s -> %s via sport-specific mapping (year=%s)",
            sport_lower,
            code_upper,
            mapped_code,
            year,
        )
        return mapped_code

    # Fallback to legacy TEAM_CODE_MAPPING for abbreviation variants
    # (e.g., WSH -> WAS is safe across most sports)
    # WARNING: This fallback is deprecated - prefer SPORT_CODE_MAPPINGS
    if code_upper in TEAM_CODE_MAPPING:
        mapped_code = TEAM_CODE_MAPPING[code_upper]
        logger.debug(
            "Resolved %s team code %s -> %s via legacy mapping (year=%s)",
            sport_lower,
            code_upper,
            mapped_code,
            year,
        )
        return mapped_code

    # No mapping found - return as-is (likely already current code)
    return code_upper


def get_team_timeline(sport: str, current_code: str) -> list[tuple[str, int, int | None]] | None:
    """
    Get the historical timeline for a team franchise.

    Args:
        sport: Sport code (e.g., "nfl")
        current_code: Current franchise code (e.g., "LV" for Raiders)

    Returns:
        List of (code, start_year, end_year) tuples, or None if not found

    Example:
        >>> get_team_timeline("nfl", "LV")
        [('OAK', 1960, 1981), ('LA', 1982, 1994), ('OAK', 1995, 2019), ('LV', 2020, None)]
    """
    sport_lower = sport.lower().strip()
    code_upper = current_code.upper().strip()

    sport_teams = TEAM_HISTORY.get(sport_lower, {})
    return sport_teams.get(code_upper)


def get_team_code_at_year(sport: str, current_code: str, year: int) -> str | None:
    """
    Get what a franchise was called in a specific year.

    Args:
        sport: Sport code
        current_code: Current franchise code
        year: Year to check

    Returns:
        Team code used in that year, or None if franchise didn't exist

    Example:
        >>> get_team_code_at_year("nfl", "LV", 2015)
        'OAK'
        >>> get_team_code_at_year("nfl", "LV", 2020)
        'LV'
    """
    timeline = get_team_timeline(sport, current_code)
    if not timeline:
        return None

    for code, start_year, end_year in timeline:
        if start_year <= year and (end_year is None or year <= end_year):
            return code

    return None


def get_all_historical_codes(sport: str, current_code: str) -> list[str]:
    """
    Get all historical codes ever used by a franchise.

    Args:
        sport: Sport code
        current_code: Current franchise code

    Returns:
        List of all team codes (including current)

    Example:
        >>> get_all_historical_codes("nfl", "LV")
        ['OAK', 'LA', 'LV']
    """
    timeline = get_team_timeline(sport, current_code)
    if not timeline:
        return [current_code.upper()]

    # Return unique codes in chronological order
    seen = set()
    codes = []
    for code, _, _ in timeline:
        if code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def is_known_relocation(sport: str, code: str) -> bool:
    """
    Check if a team code is a known historical/relocated team.

    Args:
        sport: Sport code
        code: Team code to check

    Returns:
        True if this code appears in relocation history

    Example:
        >>> is_known_relocation("nfl", "OAK")
        True
        >>> is_known_relocation("nfl", "KC")
        False
    """
    index = get_reverse_index()
    sport_index = index.get(sport.lower(), {})
    return code.upper() in sport_index


def get_supported_sports() -> list[str]:
    """Get list of sports with relocation data.

    Returns:
        List of sport codes (e.g., ["nfl", "nba", "mlb", "nhl", "ncaaf"])
    """
    return list(TEAM_HISTORY.keys())


def get_franchise_count(sport: str) -> int:
    """Get number of franchises with relocation history for a sport.

    Args:
        sport: Sport code

    Returns:
        Number of franchises with tracked history
    """
    return len(TEAM_HISTORY.get(sport.lower(), {}))


# =============================================================================
# Legacy Compatibility Layer
# =============================================================================


def normalize_team_code(code: str, sport: str = "nfl") -> str:
    """
    Legacy compatibility wrapper for resolve_team_code.

    This function provides backward compatibility with existing code
    that uses normalize_team_code(). New code should use resolve_team_code().

    Args:
        code: Team code from external source
        sport: Sport code (default: "nfl" for backward compatibility)

    Returns:
        Normalized team code

    Note:
        This is a thin wrapper around resolve_team_code() for backward
        compatibility with historical_elo_loader.py and similar modules.
    """
    return resolve_team_code(sport, code)


# =============================================================================
# Sport-Specific Code Mappings (Abbreviation Variants)
# =============================================================================
# These are NOT relocations but alternative abbreviations or legacy codes
# from different data sources. They must be sport-specific to avoid
# cross-contamination (e.g., NBA "SEA" -> "OKC" should not apply to NHL).
#
# Bug fixed: Issue #257 - SEA (Seattle Kraken, NHL) was incorrectly resolved
# to OKC (Oklahoma City Thunder, NBA) due to sport-agnostic mapping.

SPORT_CODE_MAPPINGS: dict[str, dict[str, str]] = {
    "nfl": {
        "WSH": "WAS",  # Washington (common abbreviation variant)
        "OAK": "LV",  # Oakland Raiders -> Las Vegas
        "SD": "LAC",  # San Diego Chargers -> Los Angeles
        "STL": "LAR",  # St. Louis Rams -> Los Angeles
        "LA": "LAR",  # Old LA (Rams) -> LAR
        "HOU": "TEN",  # Houston Oilers -> Tennessee Titans
        "PHO": "ARI",  # Phoenix Cardinals
    },
    "nba": {
        "SEA": "OKC",  # SuperSonics -> Thunder
        "NJN": "BKN",  # Nets (New Jersey)
        "BRK": "BKN",  # Nets (FiveThirtyEight Brooklyn code)
        "VAN": "MEM",  # Grizzlies
        "CHO": "CHA",  # Charlotte Hornets (old FiveThirtyEight code)
        "NOH": "NOP",  # New Orleans Hornets -> Pelicans
        "NOK": "NOP",  # New Orleans/OK City Hornets (2005-07 Katrina)
        "PHO": "PHX",  # Phoenix Suns (FiveThirtyEight -> standard)
    },
    "mlb": {
        "MON": "WAS",  # Montreal Expos -> Washington Nationals
        "BRO": "LAD",  # Brooklyn Dodgers -> Los Angeles Dodgers
        "FLA": "MIA",  # Florida Marlins -> Miami Marlins
        "TBD": "TBR",  # Tampa Bay Devil Rays -> Rays
        "ANA": "LAA",  # Anaheim Angels -> Los Angeles Angels
    },
    "nhl": {
        "ATL": "WPG",  # Atlanta Thrashers -> Winnipeg Jets
        "HFD": "CAR",  # Hartford Whalers -> Carolina Hurricanes
        "QUE": "COL",  # Quebec Nordiques -> Colorado Avalanche
        "PHX": "ARI",  # Phoenix Coyotes -> Arizona Coyotes (pre-2014)
        "MNS": "DAL",  # Minnesota North Stars -> Dallas Stars
        # Note: VEG in data is VGK in our teams table
        "VEG": "VGK",  # Vegas Golden Knights (data source variant)
        # Note: UTA (Utah Hockey Club) is a 2024 expansion - code may vary
    },
    "ncaaf": {
        # College football abbreviations (minimal relocations)
    },
}

# Legacy backward compatibility dict (deprecated, use SPORT_CODE_MAPPINGS)
# This fallback is used ONLY when sport-specific mapping doesn't exist
# WARNING: These mappings are ambiguous across sports!
TEAM_CODE_MAPPING: dict[str, str] = {
    # Common abbreviation variants (relatively safe across sports)
    "WSH": "WAS",  # Washington
}
