#!/usr/bin/env python3
"""
Backfill historical games from ESPN scoreboard API.

Iterates a date range for each league, fetches scoreboard data per date,
and upserts games via get_or_create_game().  Idempotent -- safe to run
multiple times on the same date range.

The same code path as the live ESPN poller is used (get_or_create_game +
update_game_result), ensuring backfilled games are indistinguishable from
poller-created games except for the data_source tag.

Usage:
    # Single league, explicit date range:
    python scripts/backfill_espn_games.py --league nba --start 2025-10-01 --end 2026-03-30

    # Multiple leagues:
    python scripts/backfill_espn_games.py --league nba --league nhl --start 2025-10-01 --end 2026-03-30

    # All supported leagues, full current season:
    python scripts/backfill_espn_games.py --all-leagues --season 2025

    # Dry run (no writes, shows what would happen):
    python scripts/backfill_espn_games.py --league nfl --start 2025-09-01 --end 2026-02-10 --dry-run

    # Resume from last backfilled date (DB-derived):
    python scripts/backfill_espn_games.py --league nba --start 2025-10-01 --end 2026-03-30 --resume

Prerequisites:
    - Database credentials in .env (DB_HOST, DB_USER, etc.)
    - No ESPN API key needed (public API)

Rate limiting:
    ESPN public API community limit ~250 req/hour.
    Default delay: 250ms between requests (~240 req/hour, safe margin).

Reference:
    - Issue #524: ESPN historical game backfill
    - ADR-106: Historical Data Collection Architecture
    - ADR-114: External Data Source Architecture (ESPN = Tier A2/C)
    - games table uses natural key UNIQUE(sport, game_date, home_team_code, away_team_code)
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from precog.api_connectors.espn_client import ESPNClient, ESPNGameFull, ESPNVenueInfo
from precog.database.connection import fetch_one, initialize_pool
from precog.database.crud_operations import (
    LEAGUE_SPORT_CATEGORY,
    create_venue,
    get_or_create_game,
    get_team_by_espn_id,
    update_game_result,
)
from precog.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_LEAGUES = ["nfl", "ncaaf", "nba", "ncaab", "nhl"]

# Season start dates (approximate — ESPN returns empty for off-season dates)
SEASON_START_DATES: dict[str, tuple[int, int]] = {
    "nfl": (9, 1),  # September
    "ncaaf": (8, 24),  # Late August
    "nba": (10, 15),  # Mid-October
    "ncaab": (11, 1),  # November
    "nhl": (10, 1),  # October
}

# Season end dates (approximate)
SEASON_END_DATES: dict[str, tuple[int, int]] = {
    "nfl": (2, 15),  # Mid-February (Super Bowl)
    "ncaaf": (1, 15),  # Mid-January (CFP)
    "nba": (6, 25),  # Late June (Finals)
    "ncaab": (4, 10),  # Early April (Final Four)
    "nhl": (6, 25),  # Late June (Stanley Cup)
}

DEFAULT_DELAY_MS = 250  # 250ms between API calls


# ---------------------------------------------------------------------------
# Team ID lookup (mirrors espn_game_poller._get_db_team_id)
# ---------------------------------------------------------------------------


def _get_db_team_id(espn_team_id: str | None, league: str, team_code: str | None) -> int | None:
    """Look up database team_id from ESPN team_id."""
    if not espn_team_id:
        return None

    team = get_team_by_espn_id(espn_team_id, league)
    if team:
        return int(team["team_id"])

    logger.debug(
        "Team not found: espn_id=%s, league=%s, code=%s",
        espn_team_id,
        league,
        team_code,
    )
    return None


# ---------------------------------------------------------------------------
# Venue lookup (mirrors espn_game_poller._ensure_venue_normalized)
# ---------------------------------------------------------------------------


def _ensure_venue(venue_info: ESPNVenueInfo) -> int | None:
    """Ensure venue exists in database, return venue_id or None."""
    venue_name = venue_info.get("venue_name")
    if not venue_name:
        return None
    try:
        venue_id: int = create_venue(
            espn_venue_id=venue_info.get("espn_venue_id", venue_name),
            venue_name=venue_name,
            city=venue_info.get("city"),
            state=venue_info.get("state"),
            capacity=venue_info.get("capacity"),
            indoor=venue_info.get("indoor", False),
        )
        return venue_id
    except Exception:
        logger.debug("Could not create venue: %s", venue_name)
        return None


# ---------------------------------------------------------------------------
# Status normalization (mirrors espn_game_poller._normalize_game_status)
# ---------------------------------------------------------------------------


def _normalize_game_status(status: str) -> str:
    """Normalize ESPN game status to standard values."""
    status_lower = status.lower() if status else "pre"
    if status_lower in ("pre", "scheduled"):
        return "pre"
    if status_lower in ("in", "in_progress"):
        return "in_progress"
    if status_lower == "halftime":
        return "halftime"
    if status_lower in ("post", "final", "final/ot", "final/2ot"):
        return "final"
    return "pre"


# ---------------------------------------------------------------------------
# Core: process one game (mirrors espn_game_poller._sync_game_to_db)
# ---------------------------------------------------------------------------


def _process_game(game: ESPNGameFull, league: str, *, dry_run: bool = False) -> str:
    """
    Process a single ESPN game into the games dimension table.

    Uses the same field mapping as espn_game_poller._sync_game_to_db()
    to ensure consistency between live-polled and backfilled games.

    Returns:
        "new", "updated", "skipped", or "error"
    """
    metadata = game.get("metadata", {})
    state = game.get("state", {})

    espn_event_id = metadata.get("espn_event_id")
    if not espn_event_id:
        return "skipped"

    home_team_info = metadata.get("home_team", {})
    away_team_info = metadata.get("away_team", {})

    home_code = home_team_info.get("team_code", "")
    away_code = away_team_info.get("team_code", "")
    if not home_code or not away_code:
        return "skipped"

    # Parse game date
    game_date_str = metadata.get("game_date")
    if not game_date_str:
        return "skipped"
    try:
        game_dt = datetime.fromisoformat(game_date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return "skipped"

    if dry_run:
        return "new"  # Optimistic — can't tell new vs updated without DB check

    # Team ID lookups
    home_team_id = _get_db_team_id(
        home_team_info.get("espn_team_id"),
        league,
        home_code,
    )
    away_team_id = _get_db_team_id(
        away_team_info.get("espn_team_id"),
        league,
        away_code,
    )

    # Venue
    venue_info = metadata.get("venue", {})
    venue_id = _ensure_venue(venue_info)

    # Derived fields
    game_season = game_dt.year
    game_season_type = str(metadata.get("season_type")) if metadata.get("season_type") else None
    game_week_number = metadata.get("week_number")
    normalized_status = _normalize_game_status(state.get("game_status", "pre"))

    try:
        game_id = get_or_create_game(
            sport=LEAGUE_SPORT_CATEGORY.get(league, league),
            game_date=game_dt.date(),
            home_team_code=home_code,
            away_team_code=away_code,
            season=game_season,
            league=league,
            season_type=game_season_type,
            week_number=game_week_number,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            venue_id=venue_id,
            venue_name=venue_info.get("venue_name"),
            neutral_site=metadata.get("neutral_site", False),
            espn_event_id=espn_event_id,
            game_status=normalized_status,
            game_time=game_dt,
            home_score=state.get("home_score"),
            away_score=state.get("away_score"),
            data_source="espn",
        )
    except Exception:
        logger.warning(
            "Failed to upsert game: %s vs %s on %s",
            away_code,
            home_code,
            game_dt.date(),
            exc_info=True,
        )
        return "error"

    # Update result for completed games
    if game_id and normalized_status in ("final", "final_ot"):
        home_score = state.get("home_score")
        away_score = state.get("away_score")
        if home_score is not None and away_score is not None:
            try:
                update_game_result(
                    game_id=game_id,
                    home_score=home_score,
                    away_score=away_score,
                )
            except Exception:
                logger.debug("Failed to update result for game_id=%s", game_id)

    return "new"


# ---------------------------------------------------------------------------
# Date range helpers
# ---------------------------------------------------------------------------


def _season_date_range(season_year: int, league: str) -> tuple[date, date]:
    """
    Compute start and end dates for a league's season.

    For fall-start leagues (NFL, NCAAF, NBA, NCAAB, NHL), the season
    starts in year N and ends in year N+1.

    Args:
        season_year: The starting year of the season (e.g., 2025 for 2025-26)
        league: League code

    Returns:
        (start_date, end_date) tuple
    """
    start_month, start_day = SEASON_START_DATES.get(league, (9, 1))
    end_month, end_day = SEASON_END_DATES.get(league, (6, 30))

    start = date(season_year, start_month, start_day)
    end = date(season_year + 1, end_month, end_day)
    return start, end


def _get_resume_date(league: str, start_date: date, end_date: date) -> date | None:
    """
    Find the last game date within the requested range for this league.

    Scoped to the requested date range to avoid being confused by games
    outside the range (e.g., live poller games beyond the backfill window).

    Args:
        league: League code
        start_date: Start of requested backfill range
        end_date: End of requested backfill range

    Returns:
        Last game_date within [start_date, end_date] for this league,
        or None if no games exist in that range.
    """
    sport = LEAGUE_SPORT_CATEGORY.get(league, league)
    row = fetch_one(
        """
        SELECT MAX(game_date) AS last_date
        FROM games
        WHERE sport = %s AND league = %s
          AND game_date BETWEEN %s AND %s
        """,
        (sport, league, start_date, end_date),
    )
    if row and row["last_date"]:
        last: date = row["last_date"]
        return last
    return None


# ---------------------------------------------------------------------------
# Main backfill loop
# ---------------------------------------------------------------------------


def backfill_league(
    client: ESPNClient,
    league: str,
    start_date: date,
    end_date: date,
    *,
    dry_run: bool = False,
    delay_ms: int = DEFAULT_DELAY_MS,
    resume: bool = False,
) -> dict[str, int]:
    """
    Backfill games for a single league over a date range.

    Iterates each date, calls ESPN scoreboard API, upserts games.

    Args:
        client: Initialized ESPN client
        league: League code (nfl, nba, etc.)
        start_date: First date to backfill (inclusive)
        end_date: Last date to backfill (inclusive)
        dry_run: If True, don't write to database
        delay_ms: Milliseconds between API calls
        resume: If True, skip dates already backfilled

    Returns:
        Dict with counts: dates_processed, games_found, new, updated, skipped, errors
    """
    # Clamp end_date to today (can't backfill the future)
    today = datetime.now(tz=UTC).date()
    if end_date > today:
        end_date = today

    # Handle resume
    effective_start = start_date
    if resume:
        last_date = _get_resume_date(league, start_date, end_date)
        if last_date:
            # Start from the day after the last backfilled date
            resume_from = last_date + timedelta(days=1)
            if resume_from > effective_start:
                print(f"  Resuming from {resume_from} (last backfilled: {last_date})")
                effective_start = resume_from

    if effective_start > end_date:
        print(f"  Nothing to backfill ({effective_start} > {end_date})")
        return {
            "dates_processed": 0,
            "games_found": 0,
            "new": 0,
            "skipped": 0,
            "errors": 0,
        }

    total_days = (end_date - effective_start).days + 1
    stats = {
        "dates_processed": 0,
        "games_found": 0,
        "new": 0,
        "skipped": 0,
        "errors": 0,
        "api_errors": 0,
    }

    current = effective_start
    while current <= end_date:
        stats["dates_processed"] += 1

        # Fetch scoreboard for this date
        try:
            dt = datetime(current.year, current.month, current.day)
            games = client.get_scoreboard(league, date=dt)
        except Exception as e:
            logger.warning("API error for %s %s: %s", league.upper(), current, e)
            stats["api_errors"] += 1
            current += timedelta(days=1)
            time.sleep(delay_ms / 1000.0)
            continue

        # Process each game
        date_new = 0
        date_errors = 0
        for game in games:
            result = _process_game(game, league, dry_run=dry_run)
            stats[result] = stats.get(result, 0) + 1
            if result == "new":
                date_new += 1
            elif result == "error":
                date_errors += 1
        stats["games_found"] += len(games)

        # Progress line
        if len(games) > 0 or stats["dates_processed"] % 10 == 0:
            mode = "[DRY RUN] " if dry_run else ""
            print(
                f"  {mode}{league.upper()} {current}: "
                f"{len(games)} games, {date_new} new"
                f"{f', {date_errors} errors' if date_errors else ''}"
                f"  [{stats['dates_processed']}/{total_days}]"
            )

        current += timedelta(days=1)

        # Rate limiting
        if not dry_run:
            time.sleep(delay_ms / 1000.0)

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Run ESPN historical game backfill."""
    parser = argparse.ArgumentParser(
        description="Backfill historical games from ESPN scoreboard API.",
        epilog=(
            "Examples:\n"
            "  python scripts/backfill_espn_games.py --league nba --start 2025-10-01 --end 2026-03-30\n"
            "  python scripts/backfill_espn_games.py --all-leagues --season 2025\n"
            "  python scripts/backfill_espn_games.py --league nfl --start 2025-09-01 --end 2026-02-10 --dry-run\n"
            "  python scripts/backfill_espn_games.py --league nba --start 2025-10-01 --end 2026-03-30 --resume\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--league",
        action="append",
        choices=SUPPORTED_LEAGUES,
        help="League(s) to backfill. Can be specified multiple times.",
    )
    parser.add_argument(
        "--all-leagues",
        action="store_true",
        help="Backfill all supported leagues.",
    )
    parser.add_argument(
        "--start",
        type=lambda s: date.fromisoformat(s),
        help="Start date (YYYY-MM-DD). Required unless --season is used.",
    )
    parser.add_argument(
        "--end",
        type=lambda s: date.fromisoformat(s),
        help="End date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--season",
        type=int,
        help="Season starting year (e.g., 2025 for 2025-26). Auto-computes date range per league.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fetched without writing to database.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last backfilled date (DB-derived, per league).",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=DEFAULT_DELAY_MS,
        help=f"Delay between API calls in milliseconds (default: {DEFAULT_DELAY_MS}).",
    )
    args = parser.parse_args()

    # Validate arguments
    if not args.league and not args.all_leagues:
        parser.error("Specify --league or --all-leagues")

    if not args.start and not args.season:
        parser.error("Specify --start or --season")

    leagues = SUPPORTED_LEAGUES if args.all_leagues else args.league

    mode_label = "[DRY RUN] " if args.dry_run else ""
    print(f"{mode_label}ESPN Historical Game Backfill")
    print(f"Leagues: {', '.join(lg.upper() for lg in leagues)}")
    if args.season:
        print(f"Season: {args.season}-{args.season + 1}")
    else:
        end = args.end or datetime.now(tz=UTC).date()
        print(f"Date range: {args.start} to {end}")
    print(f"Delay: {args.delay}ms between API calls")
    print("=" * 60)

    # Initialize
    initialize_pool()
    client = ESPNClient()

    grand_totals = {
        "dates_processed": 0,
        "games_found": 0,
        "new": 0,
        "errors": 0,
        "api_errors": 0,
    }

    try:
        for league in leagues:
            # Determine date range
            if args.season:
                start, end = _season_date_range(args.season, league)
            else:
                start = args.start
                end = args.end or datetime.now(tz=UTC).date()

            print(f"\n--- {league.upper()} ({start} to {end}) ---")

            stats = backfill_league(
                client,
                league,
                start,
                end,
                dry_run=args.dry_run,
                delay_ms=args.delay,
                resume=args.resume,
            )

            # League summary
            print(
                f"  {league.upper()} complete: {stats['dates_processed']} dates, "
                f"{stats['games_found']} games found, {stats['new']} upserted, "
                f"{stats['errors']} errors, {stats.get('api_errors', 0)} API failures"
            )

            for key in grand_totals:
                grand_totals[key] += stats.get(key, 0)

    finally:
        client.close()

    # Grand summary
    print("\n" + "=" * 60)
    print(f"{mode_label}Backfill complete.")
    print(
        f"  Total: {grand_totals['dates_processed']} dates, "
        f"{grand_totals['games_found']} games found, "
        f"{grand_totals['new']} upserted, "
        f"{grand_totals['errors']} errors, "
        f"{grand_totals['api_errors']} API failures"
    )

    if not args.dry_run and grand_totals["new"] > 0:
        print("\nNext step: run matching backfill to link events to new games:")
        print("  python main.py data matching backfill")


if __name__ == "__main__":
    main()
