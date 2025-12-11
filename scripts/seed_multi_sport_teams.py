#!/usr/bin/env python3
"""
Multi-sport team seeding script for Precog database.

Seeds team data for all supported sports/leagues into the enhanced teams table.
Each seed function is idempotent (safe to re-run) with built-in verification.

Supported Leagues:
    - NFL: 32 teams with ESPN IDs
    - NBA: 30 teams with ESPN IDs
    - NHL: 32 teams with ESPN IDs
    - WNBA: 12 teams with ESPN IDs
    - NCAAF: 79 teams (Power 5 + Group of 5) with ESPN IDs
    - NCAAB: 89 teams (Power conferences + mid-majors) with ESPN IDs

Usage:
    # Seed all sports
    python scripts/seed_multi_sport_teams.py

    # Seed specific sports
    python scripts/seed_multi_sport_teams.py --sports nfl nba

    # Dry run (show what would be seeded)
    python scripts/seed_multi_sport_teams.py --dry-run

    # Use specific database
    python scripts/seed_multi_sport_teams.py --database precog_dev

Educational Note:
    The seed files use PostgreSQL's DO $$ ... END $$ blocks for verification.
    These blocks run assertions after INSERT statements to ensure data integrity:
    - Correct team counts per league/conference
    - No NULL ESPN IDs
    - Elo ratings within expected range (1000-2000)

    The "ON CONFLICT" approach isn't used because:
    1. SQL files are designed for fresh seeding
    2. Verification blocks catch any duplicate issues
    3. Idempotency is achieved at the application level (check before running)

Reference:
    - Issue #187: Multi-sport Team Seeding
    - docs/database/seeds/ - SQL seed files
    - src/precog/database/initialization.py - Migration patterns

Related:
    - ADR-029: ESPN Data Model
    - REQ-DATA-003: Multi-Sport Support
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from precog.utils.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)

# Seed file configuration
SEEDS_DIR = Path(__file__).parent.parent / "src" / "precog" / "database" / "seeds"


@dataclass
class SeedConfig:
    """Configuration for a seed operation.

    Attributes:
        name: Human-readable name for logging
        file: SQL seed file name
        team_count: Expected number of teams (for verification)
        prerequisite: Optional seed that must run first (e.g., NFL base before ESPN update)
    """

    name: str
    file: str
    team_count: int
    prerequisite: str | None = None


# Seed configurations for each league
SEED_CONFIGS: dict[str, SeedConfig] = {
    "nfl_base": SeedConfig(
        name="NFL Teams (Initial)",
        file="001_nfl_teams_initial_elo.sql",
        team_count=32,
    ),
    "nfl_espn": SeedConfig(
        name="NFL ESPN IDs",
        file="002_nfl_teams_espn_update.sql",
        team_count=32,
        prerequisite="nfl_base",
    ),
    "nba": SeedConfig(
        name="NBA Teams",
        file="003_nba_teams.sql",
        team_count=30,
    ),
    "nhl": SeedConfig(
        name="NHL Teams",
        file="004_nhl_teams.sql",
        team_count=32,
    ),
    "wnba": SeedConfig(
        name="WNBA Teams",
        file="005_wnba_teams.sql",
        team_count=12,
    ),
    "ncaaf": SeedConfig(
        name="NCAAF Teams",
        file="006_ncaaf_teams.sql",
        team_count=79,  # 67 Power 5 + 12 Group of 5
    ),
    "ncaab": SeedConfig(
        name="NCAAB Teams",
        file="007_ncaab_teams.sql",
        team_count=89,  # 79 Power + 10 mid-majors
    ),
}

# Logical grouping of seeds for --sports flag
SPORT_SEEDS: dict[str, list[str]] = {
    "nfl": ["nfl_base", "nfl_espn"],
    "nba": ["nba"],
    "nhl": ["nhl"],
    "wnba": ["wnba"],
    "ncaaf": ["ncaaf"],
    "ncaab": ["ncaab"],
}


def get_database_url(database: str | None = None) -> str:
    """Get database connection URL.

    Args:
        database: Optional database name override. If provided, replaces the
                 database name in DATABASE_URL.

    Returns:
        PostgreSQL connection URL

    Raises:
        ValueError: If DATABASE_URL is not set or invalid
    """
    base_url = os.getenv("DATABASE_URL")
    if not base_url:
        raise ValueError("DATABASE_URL environment variable not set")

    if database:
        # Replace database name in URL (last segment after final /)
        parts = base_url.rsplit("/", 1)
        if len(parts) == 2:
            return f"{parts[0]}/{database}"
        raise ValueError(f"Invalid DATABASE_URL format: {base_url}")

    return base_url


VALID_LEAGUES = frozenset(["nfl", "nba", "nhl", "wnba", "ncaaf", "ncaab"])


def check_teams_exist(db_url: str, league: str) -> int:
    """Check how many teams exist for a league.

    Args:
        db_url: PostgreSQL connection URL
        league: League code (nfl, nba, etc.)

    Returns:
        Number of teams found for the league

    Educational Note:
        We use psql with -t (tuple-only) and -A (unaligned) flags to get
        a clean numeric output that's easy to parse. This avoids importing
        database connection code and keeps the script self-contained.

        Security: League value is validated against VALID_LEAGUES whitelist
        to prevent SQL injection. This is defense-in-depth - even though
        callers should only pass valid league codes.
    """
    # Security: Validate league against whitelist to prevent SQL injection
    if league not in VALID_LEAGUES:
        logger.warning(f"Invalid league code: {league}")
        return 0

    try:
        # League is now guaranteed to be from VALID_LEAGUES whitelist
        result = subprocess.run(
            [
                "psql",
                db_url,
                "-t",
                "-A",
                "-c",
                f"SELECT COUNT(*) FROM teams WHERE league = '{league}'",  # noqa: S608
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            # Table might not exist
            return 0

        return int(result.stdout.strip() or 0)

    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return 0


def apply_seed_file(db_url: str, seed_file: Path, timeout: int = 60) -> tuple[bool, str]:
    """Apply a SQL seed file to the database.

    Args:
        db_url: PostgreSQL connection URL
        seed_file: Path to SQL seed file
        timeout: Maximum seconds to wait for psql command

    Returns:
        Tuple of (success: bool, error_message: str)

    Educational Note:
        The SQL seed files include verification DO blocks that will raise
        exceptions if the seed fails validation. These exceptions cause
        psql to return a non-zero exit code, which we interpret as failure.

        We treat "already exists" and "duplicate key" as success because
        the seed is idempotent - running it again should not be an error.
    """
    if not seed_file.exists():
        return False, f"Seed file not found: {seed_file}"

    try:
        result = subprocess.run(
            ["psql", db_url, "-f", str(seed_file)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Check for errors (but ignore "already exists" and "duplicate key")
        if result.returncode != 0:
            stderr_lower = result.stderr.lower()
            if "already exists" in stderr_lower or "duplicate key" in stderr_lower:
                # Idempotent - data already seeded
                return True, ""
            return False, result.stderr

        return True, ""

    except FileNotFoundError:
        return False, "psql command not found - please install PostgreSQL client tools"

    except subprocess.TimeoutExpired:
        return False, f"Seed application timed out after {timeout} seconds"


def seed_nfl_teams(db_url: str, dry_run: bool = False) -> tuple[bool, int]:
    """Seed NFL teams with initial Elo ratings and ESPN IDs.

    Args:
        db_url: PostgreSQL connection URL
        dry_run: If True, only report what would be done

    Returns:
        Tuple of (success: bool, teams_seeded: int)

    Educational Note:
        NFL seeding is two-phase:
        1. Initial seed (001): Creates 32 teams with Elo ratings
        2. ESPN update (002): Adds ESPN IDs and display names

        This two-phase approach maintains backward compatibility with
        existing code that might only need basic team data.
    """
    existing = check_teams_exist(db_url, "nfl")
    config_base = SEED_CONFIGS["nfl_base"]
    config_espn = SEED_CONFIGS["nfl_espn"]

    if existing >= config_base.team_count:
        logger.info(f"NFL: {existing} teams already exist (expected {config_base.team_count})")
        if dry_run:
            return True, 0
        # Still apply ESPN update in case IDs are missing
        logger.info("Applying NFL ESPN ID update...")
        seed_file = SEEDS_DIR / config_espn.file
        success, error = apply_seed_file(db_url, seed_file)
        if not success:
            logger.error(f"NFL ESPN update failed: {error}")
            return False, 0
        return True, 0

    if dry_run:
        logger.info(f"Would seed {config_base.team_count} NFL teams")
        return True, config_base.team_count

    # Apply base seed
    logger.info(f"Seeding {config_base.team_count} NFL teams...")
    seed_file = SEEDS_DIR / config_base.file
    success, error = apply_seed_file(db_url, seed_file)
    if not success:
        logger.error(f"NFL base seed failed: {error}")
        return False, 0

    # Apply ESPN update
    logger.info("Applying NFL ESPN ID update...")
    seed_file = SEEDS_DIR / config_espn.file
    success, error = apply_seed_file(db_url, seed_file)
    if not success:
        logger.error(f"NFL ESPN update failed: {error}")
        return False, 0

    logger.info(f"NFL seed complete: {config_base.team_count} teams with ESPN IDs")
    return True, config_base.team_count


def seed_nba_teams(db_url: str, dry_run: bool = False) -> tuple[bool, int]:
    """Seed NBA teams with ESPN IDs.

    Args:
        db_url: PostgreSQL connection URL
        dry_run: If True, only report what would be done

    Returns:
        Tuple of (success: bool, teams_seeded: int)
    """
    return _seed_league(db_url, "nba", dry_run)


def seed_nhl_teams(db_url: str, dry_run: bool = False) -> tuple[bool, int]:
    """Seed NHL teams with ESPN IDs.

    Args:
        db_url: PostgreSQL connection URL
        dry_run: If True, only report what would be done

    Returns:
        Tuple of (success: bool, teams_seeded: int)
    """
    return _seed_league(db_url, "nhl", dry_run)


def seed_wnba_teams(db_url: str, dry_run: bool = False) -> tuple[bool, int]:
    """Seed WNBA teams with ESPN IDs.

    Args:
        db_url: PostgreSQL connection URL
        dry_run: If True, only report what would be done

    Returns:
        Tuple of (success: bool, teams_seeded: int)
    """
    return _seed_league(db_url, "wnba", dry_run)


def seed_ncaaf_teams(db_url: str, dry_run: bool = False) -> tuple[bool, int]:
    """Seed NCAAF teams with ESPN IDs.

    Seeds Power 5 conferences (SEC, Big Ten, Big 12, ACC) plus top Group of 5
    programs that are likely to appear in Kalshi prediction markets.

    Args:
        db_url: PostgreSQL connection URL
        dry_run: If True, only report what would be done

    Returns:
        Tuple of (success: bool, teams_seeded: int)
    """
    return _seed_league(db_url, "ncaaf", dry_run)


def seed_ncaab_teams(db_url: str, dry_run: bool = False) -> tuple[bool, int]:
    """Seed NCAAB teams with ESPN IDs.

    Seeds Power 5 conferences plus Big East and top mid-major programs
    that consistently make the NCAA tournament.

    Args:
        db_url: PostgreSQL connection URL
        dry_run: If True, only report what would be done

    Returns:
        Tuple of (success: bool, teams_seeded: int)
    """
    return _seed_league(db_url, "ncaab", dry_run)


def _seed_league(db_url: str, league: str, dry_run: bool = False) -> tuple[bool, int]:
    """Generic league seeding function.

    Args:
        db_url: PostgreSQL connection URL
        league: League code (nba, nhl, wnba, ncaaf, ncaab)
        dry_run: If True, only report what would be done

    Returns:
        Tuple of (success: bool, teams_seeded: int)
    """
    config = SEED_CONFIGS[league]
    existing = check_teams_exist(db_url, league)

    if existing >= config.team_count:
        logger.info(
            f"{league.upper()}: {existing} teams already exist (expected {config.team_count})"
        )
        return True, 0

    if dry_run:
        logger.info(f"Would seed {config.team_count} {league.upper()} teams")
        return True, config.team_count

    logger.info(f"Seeding {config.team_count} {league.upper()} teams...")
    seed_file = SEEDS_DIR / config.file
    success, error = apply_seed_file(db_url, seed_file)

    if not success:
        logger.error(f"{league.upper()} seed failed: {error}")
        return False, 0

    logger.info(f"{league.upper()} seed complete: {config.team_count} teams")
    return True, config.team_count


def seed_all_teams(db_url: str, dry_run: bool = False) -> tuple[bool, dict[str, int]]:
    """Seed all supported sports/leagues.

    Args:
        db_url: PostgreSQL connection URL
        dry_run: If True, only report what would be done

    Returns:
        Tuple of (all_success: bool, teams_by_league: dict[str, int])

    Educational Note:
        Seeding order matters! NFL base must come before NFL ESPN update.
        All other leagues are independent and can be seeded in any order.
    """
    results: dict[str, int] = {}
    all_success = True

    # Seed functions in order
    seed_functions: list[tuple[str, Callable[[str, bool], tuple[bool, int]]]] = [
        ("nfl", seed_nfl_teams),
        ("nba", seed_nba_teams),
        ("nhl", seed_nhl_teams),
        ("wnba", seed_wnba_teams),
        ("ncaaf", seed_ncaaf_teams),
        ("ncaab", seed_ncaab_teams),
    ]

    for league, seed_func in seed_functions:
        success, count = seed_func(db_url, dry_run)
        results[league] = count
        if not success:
            all_success = False

    return all_success, results


def seed_sports(
    db_url: str, sports: list[str], dry_run: bool = False
) -> tuple[bool, dict[str, int]]:
    """Seed specific sports.

    Args:
        db_url: PostgreSQL connection URL
        sports: List of sport codes (nfl, nba, etc.)
        dry_run: If True, only report what would be done

    Returns:
        Tuple of (all_success: bool, teams_by_league: dict[str, int])
    """
    results: dict[str, int] = {}
    all_success = True

    seed_map: dict[str, Callable[[str, bool], tuple[bool, int]]] = {
        "nfl": seed_nfl_teams,
        "nba": seed_nba_teams,
        "nhl": seed_nhl_teams,
        "wnba": seed_wnba_teams,
        "ncaaf": seed_ncaaf_teams,
        "ncaab": seed_ncaab_teams,
    }

    for sport in sports:
        if sport not in seed_map:
            logger.warning(f"Unknown sport: {sport} (valid: {list(seed_map.keys())})")
            continue

        success, count = seed_map[sport](db_url, dry_run)
        results[sport] = count
        if not success:
            all_success = False

    return all_success, results


def get_summary(db_url: str) -> dict[str, int]:
    """Get summary of teams by league.

    Args:
        db_url: PostgreSQL connection URL

    Returns:
        Dictionary mapping league code to team count
    """
    leagues = ["nfl", "nba", "nhl", "wnba", "ncaaf", "ncaab"]
    return {league: check_teams_exist(db_url, league) for league in leagues}


def main() -> int:
    """Main entry point for seed script.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Seed multi-sport team data into Precog database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Seed all sports
    python scripts/seed_multi_sport_teams.py

    # Seed specific sports
    python scripts/seed_multi_sport_teams.py --sports nfl nba

    # Show current state
    python scripts/seed_multi_sport_teams.py --summary

    # Dry run
    python scripts/seed_multi_sport_teams.py --dry-run
        """,
    )

    parser.add_argument(
        "--sports",
        nargs="+",
        choices=["nfl", "nba", "nhl", "wnba", "ncaaf", "ncaab"],
        help="Specific sports to seed (default: all)",
    )

    parser.add_argument(
        "--database",
        help="Database name override (default: from DATABASE_URL)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be seeded without making changes",
    )

    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show current team counts by league and exit",
    )

    args = parser.parse_args()

    try:
        db_url = get_database_url(args.database)
    except ValueError as e:
        logger.error(str(e))
        return 1

    # Summary mode
    if args.summary:
        logger.info("Current team counts by league:")
        summary = get_summary(db_url)
        total = 0
        for league, count in summary.items():
            expected = SEED_CONFIGS.get(league, SEED_CONFIGS.get(f"{league}_base"))
            expected_count = expected.team_count if expected else "?"
            status = "OK" if count >= (expected.team_count if expected else 0) else "MISSING"
            logger.info(f"  {league.upper():6} {count:3} / {expected_count:3} teams [{status}]")
            total += count
        logger.info(f"  {'TOTAL':6} {total:3} teams")
        return 0

    # Seed mode
    if args.dry_run:
        logger.info("DRY RUN - no changes will be made")

    if args.sports:
        success, results = seed_sports(db_url, args.sports, args.dry_run)
    else:
        success, results = seed_all_teams(db_url, args.dry_run)

    # Print summary
    total_seeded = sum(results.values())
    if args.dry_run:
        logger.info(f"Would seed {total_seeded} teams total")
    else:
        logger.info(f"Seeded {total_seeded} new teams")

    # Show final state
    logger.info("Final team counts:")
    summary = get_summary(db_url)
    for league, count in summary.items():
        logger.info(f"  {league.upper():6} {count:3} teams")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
