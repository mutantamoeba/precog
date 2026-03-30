#!/usr/bin/env python3
"""
Seed the external_team_codes table from existing teams data.

Populates the external_team_codes table with mappings derived from the
teams table. Creates three categories of mappings:

1. source='kalshi', confidence='manual': Teams that have an explicit
   kalshi_team_code set (e.g., JAX -> JAC). These were human-verified.
2. source='kalshi', confidence='heuristic': Teams without kalshi_team_code
   where we assume the Kalshi code matches the ESPN team_code (~95% of teams).
3. source='espn', confidence='exact': Every team gets an ESPN mapping using
   team_code, since team_code IS the ESPN code.

Uses upsert for idempotency — safe to run multiple times without duplicates.

Usage:
    # Seed from existing teams data
    python scripts/seed_external_team_codes.py

    # Dry run (show counts, don't write)
    python scripts/seed_external_team_codes.py --dry-run

    # Filter to specific league
    python scripts/seed_external_team_codes.py --league nfl

Environment:
    Uses PRECOG_ENV to determine database connection (dev/test/staging/prod).
    Defaults to 'dev' if not set.

Related:
    - Issue #516: External team codes table
    - Migration 0045: CREATE TABLE external_team_codes
    - crud_operations.upsert_external_team_code(): Write function
    - crud_operations.get_teams_with_kalshi_codes(): Data source
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure src/ is on the path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from precog.database.crud_operations import (
    get_teams_with_kalshi_codes,
    upsert_external_team_code,
)
from precog.utils.logger import get_logger

logger = get_logger(__name__)


def seed_external_team_codes(
    league: str | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Seed external_team_codes from teams table data.

    Args:
        league: Optional league filter. If None, seeds all leagues.
        dry_run: If True, compute and print counts without writing.

    Returns:
        Dict with counts: {
            'kalshi_manual': N,
            'kalshi_heuristic': N,
            'espn_exact': N,
            'total': N,
        }
    """
    teams = get_teams_with_kalshi_codes(league=league)

    if not teams:
        logger.warning("No teams found%s", f" for league={league}" if league else "")
        return {"kalshi_manual": 0, "kalshi_heuristic": 0, "espn_exact": 0, "total": 0}

    kalshi_manual = 0
    kalshi_heuristic = 0
    espn_exact = 0
    skipped = 0

    for team in teams:
        team_id = team["team_id"]
        team_code = team["team_code"]
        team_league = team["league"]
        kalshi_code = team.get("kalshi_team_code")

        if not team_code or not team_league:
            logger.warning(
                "Skipping team_id=%d: missing team_code or league",
                team["team_id"],
            )
            skipped += 1
            continue

        # --- Kalshi mapping ---
        if kalshi_code:
            # Explicit kalshi_team_code: human-verified mapping
            if not dry_run:
                upsert_external_team_code(
                    team_id=team_id,
                    source="kalshi",
                    source_team_code=kalshi_code,
                    league=team_league,
                    confidence="manual",
                    notes=f"From teams.kalshi_team_code (ESPN code: {team_code})",
                )
            kalshi_manual += 1
        else:
            # No explicit Kalshi code: assume Kalshi code = ESPN code
            if not dry_run:
                upsert_external_team_code(
                    team_id=team_id,
                    source="kalshi",
                    source_team_code=team_code,
                    league=team_league,
                    confidence="heuristic",
                    notes="Assumed Kalshi code matches ESPN team_code",
                )
            kalshi_heuristic += 1

        # --- ESPN mapping ---
        # team_code IS the ESPN code, so this is always exact
        if not dry_run:
            upsert_external_team_code(
                team_id=team_id,
                source="espn",
                source_team_code=team_code,
                league=team_league,
                confidence="exact",
                notes="ESPN team_code from teams table",
            )
        espn_exact += 1

    total = kalshi_manual + kalshi_heuristic + espn_exact
    return {
        "kalshi_manual": kalshi_manual,
        "kalshi_heuristic": kalshi_heuristic,
        "espn_exact": espn_exact,
        "skipped": skipped,
        "total": total,
    }


def main() -> None:
    """CLI entry point for seeding external team codes."""
    parser = argparse.ArgumentParser(
        description="Seed external_team_codes table from existing teams data.",
        epilog=(
            "Examples:\n"
            "  python scripts/seed_external_team_codes.py\n"
            "  python scripts/seed_external_team_codes.py --dry-run\n"
            "  python scripts/seed_external_team_codes.py --league nfl\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be seeded without writing to the database.",
    )
    parser.add_argument(
        "--league",
        type=str,
        default=None,
        help="Seed only a specific league (e.g., nfl, ncaaf). Default: all leagues.",
    )
    args = parser.parse_args()

    env = os.getenv("PRECOG_ENV", "dev")
    mode = "DRY RUN" if args.dry_run else "LIVE"
    league_label = args.league or "all"

    print(f"Seeding external_team_codes [{mode}] (env={env}, league={league_label})")
    print("-" * 60)

    counts = seed_external_team_codes(league=args.league, dry_run=args.dry_run)

    print(f"  Kalshi codes: {counts['kalshi_manual'] + counts['kalshi_heuristic']}")
    print(f"    - manual (explicit kalshi_team_code):  {counts['kalshi_manual']}")
    print(f"    - heuristic (assumed = ESPN code):     {counts['kalshi_heuristic']}")
    print(f"  ESPN codes:   {counts['espn_exact']}")
    print(f"  Total:        {counts['total']}")
    print("-" * 60)

    if args.dry_run:
        print("DRY RUN complete. No rows were written.")
    else:
        print("Seeding complete.")


if __name__ == "__main__":
    main()
