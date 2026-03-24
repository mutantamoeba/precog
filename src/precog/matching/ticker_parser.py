"""
Parse Kalshi event tickers into structured game data.

Kalshi event tickers encode league, date, and team matchup information:
    Format: {SERIES}-{YY}{MON}{DD}{AWAY}{HOME}
    Example: KXNFLGAME-26JAN18HOUNE
             series=KXNFLGAME, date=2026-01-18, away=HOU, home=NE

The parser extracts:
    - League from series prefix (NFL, NBA, NCAAF, NHL, MLB)
    - Game date from the encoded date segment
    - Away and home team codes (variable length: 2-4 chars)

Team code splitting requires a set of valid codes for the league, since
codes are concatenated without a delimiter. The split algorithm tries all
possible positions and returns the one where both halves are valid codes.

Educational Note:
    Why not use a regex for team splitting? Because team codes are variable
    length (NE=2, HOU=3, WAKE=4) and concatenated: "HOUNE" could be
    HOU+NE or HO+UNE. Only by checking against known valid codes can we
    determine the correct split point.

Related:
    - Issue #462: Event-to-game matching
    - team_code_registry.py: Provides valid code sets for splitting
"""

import logging
import re
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)

# Month abbreviations used in Kalshi tickers (uppercase)
_MONTH_MAP: dict[str, int] = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

# Pattern to extract league from series prefix.
# Matches the FIRST sport keyword found in the series string.
# Order matters: NCAAF before NFL (longer match first), NCAAB before NBA.
_LEAGUE_PATTERNS: list[tuple[str, str]] = [
    ("NCAAF", "ncaaf"),
    ("NCAAB", "ncaab"),
    ("NFL", "nfl"),
    ("NBA", "nba"),
    ("NHL", "nhl"),
    ("MLB", "mlb"),
]

# Regex for the date portion: 2-digit year, 3-letter month, 2-digit day
_DATE_PATTERN = re.compile(r"^(\d{2})([A-Z]{3})(\d{2})")


@dataclass(frozen=True)
class ParsedTicker:
    """Result of parsing a Kalshi event ticker.

    Attributes:
        series: Full series prefix (e.g., "KXNFLGAME")
        league: Lowercase league code extracted from series (e.g., "nfl")
        game_date: Parsed game date
        away_team_code: Kalshi team code for away team (e.g., "HOU")
        home_team_code: Kalshi team code for home team (e.g., "NE")

    Educational Note:
        frozen=True makes ParsedTicker immutable and hashable, which is
        appropriate since parsed data should not be modified after creation.
    """

    series: str
    league: str
    game_date: date
    away_team_code: str
    home_team_code: str


def _extract_league(series: str) -> str | None:
    """Extract league code from series prefix.

    Args:
        series: Series prefix string (e.g., "KXNFLGAME", "KXNCAAFGAME")

    Returns:
        Lowercase league code (e.g., "nfl") or None if no league found.

    Example:
        >>> _extract_league("KXNFLGAME")
        'nfl'
        >>> _extract_league("KXNCAAFD3GAME")
        'ncaaf'
        >>> _extract_league("KXNBA2HWINNER")
        'nba'
    """
    upper = series.upper()
    for pattern, league in _LEAGUE_PATTERNS:
        if pattern in upper:
            return league
    return None


def _parse_date_segment(segment: str) -> tuple[date, str] | None:
    """Parse date from the beginning of a ticker segment.

    The date format is YYMONDD where:
        YY = 2-digit year (20xx)
        MON = 3-letter month abbreviation
        DD = 2-digit day

    Args:
        segment: The portion after the hyphen (e.g., "26JAN18HOUNE")

    Returns:
        Tuple of (parsed_date, remaining_string) or None if parsing fails.

    Example:
        >>> _parse_date_segment("26JAN18HOUNE")
        (date(2026, 1, 18), 'HOUNE')
        >>> _parse_date_segment("25DEC31DALNYG")
        (date(2025, 12, 31), 'DALNYG')
    """
    match = _DATE_PATTERN.match(segment.upper())
    if not match:
        return None

    year_str, month_str, day_str = match.groups()
    month = _MONTH_MAP.get(month_str)
    if month is None:
        return None

    try:
        year = 2000 + int(year_str)
        day = int(day_str)
        parsed_date = date(year, month, day)
    except ValueError:
        # Invalid date (e.g., Feb 30)
        return None

    remaining = segment[match.end() :]
    return parsed_date, remaining


def split_team_codes(combined: str, valid_codes: set[str]) -> tuple[str, str] | None:
    """Split concatenated team codes using a set of valid codes.

    Tries all split points from position 2 to len-2 and returns the split
    where BOTH halves are recognized as valid team codes for the league.

    Args:
        combined: Concatenated team codes (e.g., "HOUNE", "OKCBOS", "WAKEMSST")
        valid_codes: Set of valid Kalshi team codes for the league (uppercase)

    Returns:
        Tuple of (away_code, home_code) or None if no valid split found.
        Returns None if multiple valid splits are found (ambiguous).

    Example:
        >>> codes = {"HOU", "NE", "KC", "BUF"}
        >>> split_team_codes("HOUNE", codes)
        ('HOU', 'NE')
        >>> split_team_codes("KCBUF", codes)
        ('KC', 'BUF')
    """
    if len(combined) < 4:
        # Minimum: 2-char code + 2-char code
        return None

    upper = combined.upper()
    valid_upper = {c.upper() for c in valid_codes}
    matches: list[tuple[str, str]] = []

    # Try split points from position 2 to len(combined)-2
    for i in range(2, len(upper) - 1):
        left = upper[:i]
        right = upper[i:]
        if left in valid_upper and right in valid_upper:
            matches.append((left, right))

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        # Ambiguous split — can't determine which is correct
        logger.warning(
            "Ambiguous team code split for '%s': %d valid splits found: %s",
            combined,
            len(matches),
            matches,
        )
        return None

    # No valid split found
    return None


def parse_event_ticker(ticker: str, valid_codes: set[str] | None = None) -> ParsedTicker | None:
    """Parse a Kalshi event ticker into structured game data.

    Extracts league, game date, and team codes from the ticker string.
    Team code splitting requires valid_codes to disambiguate variable-length
    codes. If valid_codes is not provided, team splitting is skipped.

    Args:
        ticker: Full Kalshi event ticker (e.g., "KXNFLGAME-26JAN18HOUNE")
        valid_codes: Set of valid Kalshi team codes for the league.
                     Required for team code extraction. Get from
                     TeamCodeRegistry.get_kalshi_codes().

    Returns:
        ParsedTicker with all fields populated, or None if parsing fails.

    Example:
        >>> nfl_codes = {"ARI", "ATL", "BAL", "BUF", "HOU", "NE", ...}
        >>> result = parse_event_ticker("KXNFLGAME-26JAN18HOUNE", nfl_codes)
        >>> result.league
        'nfl'
        >>> result.game_date
        datetime.date(2026, 1, 18)
        >>> result.away_team_code
        'HOU'
        >>> result.home_team_code
        'NE'

    Related:
        - TeamCodeRegistry.get_kalshi_codes(): Provides valid code sets
        - EventGameMatcher.match_event(): Primary caller
    """
    if not ticker or not isinstance(ticker, str):
        return None

    # Split on first hyphen: series prefix and the rest
    parts = ticker.split("-", 1)
    if len(parts) != 2:
        return None

    series, remainder = parts
    if not series or not remainder:
        return None

    # Extract league from series
    league = _extract_league(series)
    if league is None:
        return None

    # Parse date from remainder
    date_result = _parse_date_segment(remainder)
    if date_result is None:
        return None

    game_date, team_segment = date_result

    # If no valid codes provided or no team segment, return partial result
    if not team_segment:
        return None

    if valid_codes is None:
        # Can't split team codes without valid code set
        return None

    # Split concatenated team codes
    split = split_team_codes(team_segment, valid_codes)
    if split is None:
        return None

    away_code, home_code = split

    return ParsedTicker(
        series=series,
        league=league,
        game_date=game_date,
        away_team_code=away_code,
        home_team_code=home_code,
    )
