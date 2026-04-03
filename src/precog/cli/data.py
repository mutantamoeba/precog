"""
Data Management CLI Commands.

Provides commands for seeding, verifying, and managing data.

Commands:
    seed    - Seed data by type (teams, elo, odds, games)
    verify  - Verify seed data exists
    stats   - Show data statistics
    sources - List available data sources
    matching stats/backfill/refresh - Event-to-game matching
    teams classification/refresh-cfbd - Team classification coverage

Usage:
    precog data seed --type teams
    precog data seed --type elo --csv nfl_elo.csv
    precog data seed --type odds --dir data/historical/
    precog data verify
    precog data stats
    precog data sources

Related:
    - Issue #204: CLI Refactor
    - Issue #229: Expanded Historical Data Sources
    - docs/planning/CLI_REFACTOR_COMPREHENSIVE_PLAN_V1.0.md Section 4.2.3
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from rich.table import Table

from precog.cli._common import (
    ExitCode,
    cli_error,
    console,
    echo_success,
)

if TYPE_CHECKING:
    from precog.database.seeding.sources.base_source import BaseDataSource

app = typer.Typer(
    name="data",
    help="Data seeding and management (seed, verify, stats, sources)",
    no_args_is_help=True,
)


class SeedType(str, Enum):
    """Available seed data types."""

    TEAMS = "teams"
    ELO = "elo"
    ODDS = "odds"
    GAMES = "games"
    STATS = "stats"
    RANKINGS = "rankings"


# Expected team counts per sport
EXPECTED_TEAMS = {
    "nfl": 32,
    "nba": 30,
    "nhl": 32,
    "wnba": 12,
    "ncaaf": 134,
    "ncaab": 363,
    "ncaaw": 356,
}


@app.command()
def seed(
    seed_type: SeedType = typer.Option(
        ...,
        "--type",
        "-t",
        help="Type of data to seed (teams, elo, odds, games, stats, rankings)",
    ),
    sports: str = typer.Option(
        "nfl,nba,nhl,wnba,ncaaf,ncaab,ncaaw",
        "--sports",
        "-s",
        help="Comma-separated list of sports (for teams)",
    ),
    csv_file: str | None = typer.Option(
        None,
        "--csv",
        "-f",
        help="Path to CSV file (for elo)",
    ),
    data_dir: str | None = typer.Option(
        None,
        "--dir",
        "-d",
        help="Path to data directory (for odds)",
    ),
    seasons: str | None = typer.Option(
        None,
        "--seasons",
        help="Comma-separated seasons to load (e.g., 2022,2023,2024)",
    ),
    source: str = typer.Option(
        "fivethirtyeight",
        "--source",
        help="Data source format (fivethirtyeight, simple)",
    ),
    sport: str = typer.Option(
        "nfl",
        "--sport",
        help="Sport for historical data (nfl, ncaaf, nba, etc.)",
    ),
    link_games: bool = typer.Option(
        True,
        "--link/--no-link",
        help="Link odds to historical_games (default: True)",
    ),
    stat_type: str = typer.Option(
        "weekly",
        "--stat-type",
        help="Stats type for stats seeding: weekly, seasonal, team (default: weekly)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without making changes",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose output",
    ),
) -> None:
    """Seed data into the database by type.

    Supports seeding different types of data:
    - teams: Team reference data with ESPN IDs
    - elo: Historical Elo ratings from CSV
    - odds: Historical betting odds from CSV
    - games: Historical game results
    - stats: Player/team statistics via nfl_data_py (Issue #236)
    - rankings: Team rankings (Issue #236)

    Examples:
        precog data seed --type teams
        precog data seed --type teams --sports nfl,nba
        precog data seed --type elo --csv nfl_elo.csv
        precog data seed --type elo --csv nfl_elo.csv --seasons 2022,2023,2024
        precog data seed --type odds --dir data/historical/ --sport nfl
        precog data seed --type stats --seasons 2023,2024 --stat-type weekly
        precog data seed --type stats --seasons 2024 --stat-type team
    """
    console.print(f"\n[bold cyan]Seeding {seed_type.value} data...[/bold cyan]\n")

    try:
        if seed_type == SeedType.TEAMS:
            _seed_teams(sports, dry_run, verbose)
        elif seed_type == SeedType.ELO:
            _seed_elo(csv_file, sport, seasons, source, verbose)
        elif seed_type == SeedType.ODDS:
            _seed_odds(data_dir, sport, seasons, link_games, verbose)
        elif seed_type == SeedType.GAMES:
            _seed_games(csv_file, sport, seasons, source, verbose)
        elif seed_type == SeedType.STATS:
            _seed_stats(sport, seasons, stat_type, verbose)
        elif seed_type == SeedType.RANKINGS:
            _seed_rankings(sport, seasons, verbose)

    except typer.Exit:
        raise
    except Exception as e:
        cli_error(
            f"Seeding failed: {e}",
            ExitCode.DATABASE_ERROR,
            hint="Check database connection and data files",
        )


def _seed_teams(sports: str, dry_run: bool, verbose: bool) -> None:
    """Seed team reference data."""
    from precog.database.seeding import SeedingConfig, SeedingManager

    sport_list = [s.strip().lower() for s in sports.split(",")]
    console.print(f"[dim]Sports: {', '.join(sport_list)}[/dim]")

    config = SeedingConfig(sports=sport_list, dry_run=dry_run)
    manager = SeedingManager(config=config)

    if dry_run:
        console.print("[yellow]Dry-run mode:[/yellow] Showing what would be done\n")

    console.print("Seeding teams...")
    stats = manager.seed_teams(sports=sport_list)

    total_processed = stats["records_processed"]
    total_created = stats["records_created"]
    total_errors = stats["errors"]

    console.print(
        f"  [green]Teams: {total_created} created, "
        f"{total_processed} processed, {total_errors} errors[/green]"
    )

    # Verify
    console.print("\nVerifying seeds...")
    result = manager.verify_seeds()
    teams = result.get("categories", {}).get("teams", {})
    overall_success = result.get("success", False)

    if overall_success:
        echo_success(f"All {teams.get('expected', '?')} expected teams found")
    else:
        console.print(
            f"  [yellow]Expected {teams.get('expected', '?')}, "
            f"found {teams.get('actual', '?')}[/yellow]"
        )

    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Total processed: {total_processed}")
    console.print(f"  Total created: {total_created}")
    console.print(f"  Total errors: {total_errors}")

    if total_errors > 0:
        raise typer.Exit(code=1)

    console.print("\n[green]Team seeding completed successfully![/green]")


def _seed_elo(
    csv_file: str | None,
    sport: str,
    seasons: str | None,
    source: str,
    verbose: bool,
) -> None:
    """Seed historical Elo ratings."""
    from precog.database.seeding import load_csv_elo, load_fivethirtyeight_elo

    if not csv_file:
        cli_error(
            "CSV file required for Elo seeding",
            ExitCode.USAGE_ERROR,
            hint="Use --csv path/to/elo.csv",
        )

    csv_path = Path(csv_file)
    if not csv_path.exists():
        cli_error(
            f"CSV file not found: {csv_file}",
            ExitCode.USAGE_ERROR,
        )

    season_list = None
    if seasons:
        try:
            season_list = [int(s.strip()) for s in seasons.split(",")]
            console.print(f"[dim]Filtering to seasons: {season_list}[/dim]")
        except ValueError:
            cli_error(
                f"Invalid seasons format: {seasons}",
                ExitCode.USAGE_ERROR,
                hint="Use comma-separated years (e.g., 2022,2023,2024)",
            )

    console.print(f"[dim]Loading from: {csv_path}[/dim]")
    console.print(f"[dim]Sport: {sport}[/dim]")
    console.print(f"[dim]Source format: {source}[/dim]\n")

    if source == "fivethirtyeight":
        result = load_fivethirtyeight_elo(csv_path, sport=sport, seasons=season_list)
    elif source == "simple":
        result = load_csv_elo(csv_path, sport=sport, source="imported")
    else:
        cli_error(
            f"Unknown source format: {source}",
            ExitCode.USAGE_ERROR,
            hint="Supported formats: fivethirtyeight, simple",
        )

    console.print("[bold]Load Results:[/bold]")
    console.print(f"  Records processed: {result.records_processed:,}")
    console.print(f"  Records inserted: {result.records_inserted:,}")
    console.print(f"  Records skipped: {result.records_skipped:,}")
    console.print(f"  Errors: {result.errors}")

    if result.records_skipped > 0:
        console.print("\n[yellow]Note: Skipped records may be due to missing teams.[/yellow]")
        console.print("[dim]Ensure teams are seeded first: precog data seed --type teams[/dim]")

    if result.errors > 0:
        if verbose and result.error_messages:
            for msg in result.error_messages[:10]:
                console.print(f"  [dim]{msg}[/dim]")
        raise typer.Exit(code=1)

    console.print("\n[green]Elo seeding completed successfully![/green]")


def _seed_odds(
    data_dir: str | None,
    sport: str,
    seasons: str | None,
    link_games: bool,
    verbose: bool,
) -> None:
    """Seed historical betting odds."""
    from precog.database.seeding import load_odds_from_source
    from precog.database.seeding.sources import BettingCSVSource

    if not data_dir:
        cli_error(
            "Data directory required for odds seeding",
            ExitCode.USAGE_ERROR,
            hint="Use --dir path/to/odds_data/",
        )

    data_path = Path(data_dir)
    if not data_path.exists():
        cli_error(
            f"Directory not found: {data_dir}",
            ExitCode.USAGE_ERROR,
        )

    season_list = None
    if seasons:
        try:
            season_list = [int(s.strip()) for s in seasons.split(",")]
            console.print(f"[dim]Filtering to seasons: {season_list}[/dim]")
        except ValueError:
            cli_error(
                f"Invalid seasons format: {seasons}",
                ExitCode.USAGE_ERROR,
                hint="Use comma-separated years (e.g., 2020,2021,2022)",
            )

    console.print(f"[dim]Loading from: {data_path}[/dim]")
    console.print(f"[dim]Sport: {sport}[/dim]")
    console.print(f"[dim]Link to games: {link_games}[/dim]\n")

    source_adapter = BettingCSVSource(data_dir=data_path)
    result = load_odds_from_source(
        source_adapter,
        sport=sport,
        seasons=season_list,
        link_games=link_games,
    )

    console.print("[bold]Load Results:[/bold]")
    console.print(f"  Records processed: {result.records_processed:,}")
    console.print(f"  Records inserted: {result.records_inserted:,}")
    console.print(f"  Records skipped: {result.records_skipped:,}")
    console.print(f"  Errors: {result.errors}")

    if result.errors > 0:
        if verbose and result.error_messages:
            for msg in result.error_messages[:10]:
                console.print(f"  [dim]{msg}[/dim]")
        raise typer.Exit(code=1)

    console.print("\n[green]Odds seeding completed successfully![/green]")


def _seed_games(
    csv_file: str | None,
    sport: str,
    seasons: str | None,
    source: str,
    verbose: bool,
) -> None:
    """Seed historical game results from CSV file.

    Loads game results from FiveThirtyEight Elo CSV files or simple CSV format.
    Game results are stored in the historical_games table for use in:
    - Model validation (predicted vs actual outcomes)
    - Elo rating computation
    - Backtesting

    Args:
        csv_file: Path to CSV file with game data
        sport: Sport code (nfl, nba, nhl, mlb, ncaaf, ncaab)
        seasons: Comma-separated seasons to load (optional filter)
        source: Data source format (fivethirtyeight, simple)
        verbose: Enable verbose output

    Usage:
        precog data seed --type games --csv nfl_elo.csv --sport nfl
        precog data seed --type games --csv nfl_elo.csv --seasons 2022,2023,2024
        precog data seed --type games --csv games.csv --source simple --sport nba

    Educational Note:
        FiveThirtyEight Elo CSVs include game results alongside ratings.
        We extract: date, team1/team2, score1/score2, neutral, playoff.
        Team codes are normalized to match our teams table.

    Related:
        - Issue #229: Expanded Historical Data Sources
        - Migration 0006: Create historical_games table
        - historical_games_loader.py: Data loading implementation
    """
    from precog.database.seeding.batch_result import ErrorHandlingMode
    from precog.database.seeding.historical_games_loader import (
        load_csv_games,
        load_fivethirtyeight_games,
        load_fivethirtyeight_nba_games,
    )

    # Require CSV file for game seeding
    if not csv_file:
        cli_error(
            "CSV file required for game seeding",
            ExitCode.USAGE_ERROR,
            hint="Use --csv to specify the path to game data CSV file\n"
            "  Example: precog data seed --type games --csv nfl_elo.csv",
        )

    csv_path = Path(csv_file)
    if not csv_path.exists():
        cli_error(
            f"CSV file not found: {csv_file}",
            ExitCode.USAGE_ERROR,
            hint="Check the file path and ensure the file exists",
        )

    # Parse seasons filter
    season_list: list[int] | None = None
    if seasons:
        season_list = [int(s.strip()) for s in seasons.split(",")]
        console.print(f"[dim]Filtering to seasons: {season_list}[/dim]")

    console.print(f"[dim]Sport: {sport}[/dim]")
    console.print(f"[dim]Source format: {source}[/dim]")
    console.print(f"[dim]CSV file: {csv_path}[/dim]")

    # Use COLLECT mode for error reporting (don't fail on first unknown team)
    error_mode = ErrorHandlingMode.COLLECT

    if source.lower() == "fivethirtyeight":
        console.print("\n[bold]Loading FiveThirtyEight game data...[/bold]")

        # NBA uses a different format (each game appears twice, with _iscopy flag)
        if sport.lower() == "nba":
            console.print("[dim]Using NBA-specific format parser...[/dim]")
            result = load_fivethirtyeight_nba_games(
                csv_path,
                seasons=season_list,
                error_mode=error_mode,
                show_progress=True,
            )
        else:
            # NFL and other sports use standard FiveThirtyEight format
            result = load_fivethirtyeight_games(
                csv_path,
                sport=sport,
                seasons=season_list,
                error_mode=error_mode,
                show_progress=True,
            )
    else:
        # Simple CSV format
        console.print(f"\n[bold]Loading game data ({source} format)...[/bold]")
        result = load_csv_games(
            csv_path,
            sport=sport,
            source=source,
            error_mode=error_mode,
            show_progress=True,
        )

    # Report results
    if result.has_failures:
        console.print(f"\n[yellow]Warning: {result.errors} records had errors[/yellow]")
        if verbose:
            console.print(result.get_failure_summary())

    if result.records_skipped > 0:
        console.print(f"[dim]Skipped {result.records_skipped} records (unknown teams)[/dim]")

    console.print(
        f"\n[green]Game seeding completed: {result.records_inserted} games loaded[/green]"
    )


def _seed_stats(
    sport: str,
    seasons: str | None,
    stat_type: str,
    verbose: bool,
) -> None:
    """Seed player/team statistics from nfl_data_py.

    Loads statistics using the NFLDataPySource adapter and inserts
    them into the historical_stats table.

    Args:
        sport: Sport to load (currently only 'nfl' supported)
        seasons: Comma-separated list of seasons
        stat_type: Type of stats (weekly, seasonal, team)
        verbose: Enable verbose output

    Related:
        - Issue #236: StatsRecord/RankingRecord Infrastructure
        - Migration 0009: historical_stats table
        - NFLDataPySource: Data source adapter
    """
    from precog.database.seeding.sources import NFLDataPySource

    if sport.lower() != "nfl":
        cli_error(
            f"Stats seeding only supports NFL currently (got: {sport})",
            ExitCode.USAGE_ERROR,
            hint="Future: nba_api for NBA stats",
        )

    season_list = None
    if seasons:
        try:
            season_list = [int(s.strip()) for s in seasons.split(",")]
            console.print(f"[dim]Filtering to seasons: {season_list}[/dim]")
        except ValueError:
            cli_error(
                f"Invalid seasons format: {seasons}",
                ExitCode.USAGE_ERROR,
                hint="Use comma-separated years (e.g., 2022,2023,2024)",
            )

    console.print(f"[dim]Sport: {sport}[/dim]")
    console.print(f"[dim]Stat type: {stat_type}[/dim]\n")

    try:
        source = NFLDataPySource()
    except Exception as e:
        cli_error(
            f"Failed to initialize NFLDataPySource: {e}",
            ExitCode.ERROR,
            hint="Ensure nfl_data_py is installed: pip install nfl_data_py",
        )

    # Load stats from source
    console.print("Loading stats from nfl_data_py...")
    records_processed = 0
    records_inserted = 0
    errors = 0

    try:
        for stat_record in source.load_stats(
            sport=sport,
            seasons=season_list,
            stat_type=stat_type,
        ):
            records_processed += 1
            # TODO: Insert into historical_stats table when CRUD is implemented
            # For now, just count records
            records_inserted += 1  # Placeholder

            if verbose and records_processed % 1000 == 0:
                console.print(f"  [dim]Processed {records_processed:,} records...[/dim]")

    except Exception as e:
        errors += 1
        console.print(f"[red]Error loading stats: {e}[/red]")

    console.print("\n[bold]Load Results:[/bold]")
    console.print(f"  Records processed: {records_processed:,}")
    console.print(f"  Records inserted: {records_inserted:,}")
    console.print(f"  Errors: {errors}")

    if records_processed == 0:
        console.print(
            "\n[yellow]No stats found. Check if nfl_data_py has data for these seasons.[/yellow]"
        )
    else:
        console.print("\n[green]Stats loading completed![/green]")
        console.print(
            "[dim]Note: Database insertion requires Migration 0009 and CRUD implementation.[/dim]"
        )


def _seed_rankings(
    sport: str,
    seasons: str | None,
    verbose: bool,
) -> None:
    """Seed team rankings (placeholder for future implementation).

    Will load rankings from various sources (ESPN, FiveThirtyEight power rankings).

    Related:
        - Issue #236: StatsRecord/RankingRecord Infrastructure
        - Migration 0009: historical_rankings table
    """
    cli_error(
        "Rankings seeding not yet fully implemented",
        ExitCode.ERROR,
        hint="Target: Use ESPN API or FiveThirtyEight power rankings. "
        "The team_rankings table (Migration 012) stores live rankings.",
    )


@app.command()
def verify(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Show detailed per-sport breakdown",
    ),
) -> None:
    """Verify that required seed data exists in the database.

    Checks that all expected reference data (teams, venues, etc.) is present.
    Use this to diagnose "team not found" errors during polling.

    Examples:
        precog data verify
        precog data verify --verbose
    """
    console.print("\n[bold cyan]Verifying Seed Data[/bold cyan]\n")

    try:
        from precog.database.seeding import SeedingManager

        manager = SeedingManager()
        result = manager.verify_seeds()

        teams = result.get("categories", {}).get("teams", {})
        overall_success = result.get("success", False)

        if overall_success:
            echo_success("All required seeds present")
            console.print(f"  Total teams: {teams.get('actual', '?')}/{teams.get('expected', '?')}")
            console.print(f"  Teams with ESPN IDs: {teams.get('has_espn_ids', '?')}")
        else:
            console.print("[yellow]Some seeds missing[/yellow]")
            console.print(f"  Total teams: {teams.get('actual', '?')}/{teams.get('expected', '?')}")
            missing = teams.get("missing_sports", [])
            if missing:
                console.print(f"  Missing sports: {', '.join(missing)}")

        if verbose:
            by_sport = teams.get("by_sport", {})
            if by_sport:
                console.print("\n[bold]Per-Sport Breakdown:[/bold]")

                table = Table(show_header=True, header_style="bold")
                table.add_column("Sport")
                table.add_column("Expected", justify="right")
                table.add_column("Actual", justify="right")
                table.add_column("ESPN IDs", justify="right")
                table.add_column("Status")

                for sport_code, data in sorted(by_sport.items()):
                    status = "[green]OK[/green]" if data.get("ok") else "[red]MISSING[/red]"
                    table.add_row(
                        sport_code.upper(),
                        str(data.get("expected", "?")),
                        str(data.get("actual", "?")),
                        str(data.get("has_espn_ids", "?")),
                        status,
                    )

                console.print(table)

        if not overall_success:
            console.print(
                "\n[yellow]Hint: Run 'precog data seed --type teams' to populate[/yellow]"
            )
            raise typer.Exit(code=1)

        console.print()

    except ImportError as e:
        cli_error(
            f"Failed to import seeding module: {e}",
            ExitCode.ERROR,
            hint="Ensure precog.database.seeding package exists",
        )
    except typer.Exit:
        raise
    except Exception as e:
        cli_error(
            f"Verification failed: {e}",
            ExitCode.DATABASE_ERROR,
        )


@app.command()
def stats(
    data_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Specific data type (elo, odds, teams) or all",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Show detailed statistics",
    ),
) -> None:
    """Show data statistics for seeded data.

    Displays counts and breakdowns of historical data in the database.

    Examples:
        precog data stats
        precog data stats --type elo
        precog data stats --type odds --verbose
    """
    console.print("\n[bold cyan]Data Statistics[/bold cyan]\n")

    show_all = data_type is None
    errors = []

    # Elo statistics
    if show_all or data_type == "elo":
        try:
            from precog.database.seeding import get_historical_elo_stats

            stats = get_historical_elo_stats()

            console.print("[bold]Historical Elo:[/bold]")
            console.print(f"  Total records: {stats['total']:,}")

            if verbose and stats.get("by_sport"):
                console.print("  By Sport:")
                for sport_name, count in stats["by_sport"].items():
                    console.print(f"    {sport_name.upper()}: {count:,}")

            if verbose and stats.get("by_season"):
                console.print("  By Season (recent):")
                for season, count in stats["by_season"].items():
                    console.print(f"    {season}: {count:,}")

            console.print()

        except Exception as e:
            errors.append(f"Elo stats: {e}")
            if verbose:
                console.print(f"[dim]Elo stats unavailable: {e}[/dim]\n")

    # Odds statistics
    if show_all or data_type == "odds":
        try:
            from precog.database.seeding import get_game_odds_stats

            stats = get_game_odds_stats()

            console.print("[bold]Historical Odds:[/bold]")
            console.print(f"  Total records: {stats['total']:,}")

            if verbose and stats.get("by_sport"):
                console.print("  By Sport:")
                for sport_name, count in stats["by_sport"].items():
                    console.print(f"    {sport_name.upper()}: {count:,}")

            linked = stats.get("linked_to_games", 0)
            unlinked = stats.get("unlinked", 0)
            if linked or unlinked:
                console.print(f"  Linked to games: {linked:,}")
                console.print(f"  Unlinked: {unlinked:,}")

            console.print()

        except Exception as e:
            errors.append(f"Odds stats: {e}")
            if verbose:
                console.print(f"[dim]Odds stats unavailable: {e}[/dim]\n")

    # Team statistics
    if show_all or data_type == "teams":
        try:
            from precog.database.seeding import SeedingManager

            manager = SeedingManager()
            result = manager.verify_seeds()
            teams = result.get("categories", {}).get("teams", {})

            console.print("[bold]Teams:[/bold]")
            console.print(f"  Total teams: {teams.get('actual', '?')}")
            console.print(f"  With ESPN IDs: {teams.get('has_espn_ids', '?')}")

            if verbose:
                by_sport = teams.get("by_sport", {})
                if by_sport:
                    console.print("  By Sport:")
                    for sport_code, data in sorted(by_sport.items()):
                        console.print(f"    {sport_code.upper()}: {data.get('actual', '?')}")

            console.print()

        except Exception as e:
            errors.append(f"Team stats: {e}")
            if verbose:
                console.print(f"[dim]Team stats unavailable: {e}[/dim]\n")

    if errors and not verbose:
        console.print("[dim]Some stats unavailable. Use --verbose for details.[/dim]")


@app.command()
def sources() -> None:
    """List available data sources and their capabilities.

    Shows all registered data source adapters and what record types
    they can provide (games, odds, elo, stats, rankings).

    Examples:
        precog data sources
    """
    console.print("\n[bold cyan]Available Data Sources[/bold cyan]\n")

    # Static list of known sources with their capabilities
    sources_info = [
        {
            "name": "FiveThirtyEight",
            "module": "fivethirtyeight",
            "types": ["elo", "games"],
            "sports": ["nfl", "nba", "mlb"],
            "description": "Historical Elo ratings and game results",
            "status": "active",
        },
        {
            "name": "Betting CSV",
            "module": "betting_csv",
            "types": ["odds"],
            "sports": ["nfl", "ncaaf", "nba"],
            "description": "Historical betting lines from CSV files",
            "status": "active",
        },
        {
            "name": "nfl_data_py",
            "module": "nfl_data_py_source",
            "types": ["games", "stats"],
            "sports": ["nfl"],
            "description": "NFL schedules, game data, and player/team stats",
            "status": "active",
        },
        {
            "name": "ESPN API",
            "module": "espn_client",
            "types": ["games", "teams", "rankings"],
            "sports": ["nfl", "ncaaf", "nba", "ncaab", "nhl", "wnba"],
            "description": "Live game states, team data, and rankings",
            "status": "active",
        },
        {
            "name": "ESPN Historical",
            "module": "historical_games_loader",
            "types": ["games"],
            "sports": ["nfl", "ncaaf", "nba", "ncaab", "nhl", "mlb", "wnba"],
            "description": "Historical games with local caching (seed-espn command)",
            "status": "active",
        },
        {
            "name": "nba_api",
            "module": "nba_api_adapter",
            "types": ["games", "stats"],
            "sports": ["nba"],
            "description": "NBA game logs and statistics from stats.nba.com",
            "status": "active",
        },
        {
            "name": "pybaseball",
            "module": "pybaseball_adapter",
            "types": ["games", "stats"],
            "sports": ["mlb"],
            "description": "MLB games and statistics (Baseball Reference, Retrosheet)",
            "status": "active",
        },
    ]

    table = Table(title="Data Sources")
    table.add_column("Source", style="cyan", no_wrap=True)
    table.add_column("Data Types", style="white")
    table.add_column("Sports", style="green")
    table.add_column("Status", justify="center")

    for source in sources_info:
        source_status = str(source["status"])
        source_name = str(source["name"])
        source_types = source["types"]
        source_sports = source["sports"]
        status_str = {
            "active": "[green]Active[/green]",
            "partial": "[yellow]Partial[/yellow]",
            "planned": "[dim]Planned[/dim]",
        }.get(source_status, source_status)

        # Type narrowing for list fields
        types_list = source_types if isinstance(source_types, list) else []
        sports_list = source_sports if isinstance(source_sports, list) else []

        table.add_row(
            source_name,
            ", ".join(str(t) for t in types_list),
            ", ".join(str(s) for s in sports_list),
            status_str,
        )

    console.print(table)

    # Data types legend
    console.print("\n[bold]Data Types:[/bold]")
    types_legend = [
        ("games", "Game results with scores, dates, teams"),
        ("odds", "Betting lines (spreads, totals, moneylines)"),
        ("elo", "Team rating history"),
        ("teams", "Team reference data with IDs"),
        ("stats", "Player/team statistics (Issue #236)"),
        ("rankings", "AP/Coaches polls, power rankings (Issue #236)"),
    ]

    for type_name, desc in types_legend:
        console.print(f"  [cyan]{type_name}[/cyan]: {desc}")

    console.print()


@app.command("seed-espn")
def seed_espn(
    sport: str = typer.Option(
        "nfl",
        "--sport",
        "-s",
        help="Sport to seed (nfl, nba, nhl, mlb, ncaaf, ncaab, wnba)",
    ),
    start_date: str = typer.Option(
        ...,
        "--start",
        help="Start date (YYYY-MM-DD)",
    ),
    end_date: str = typer.Option(
        ...,
        "--end",
        help="End date (YYYY-MM-DD)",
    ),
    fetch: bool = typer.Option(
        True,
        "--fetch/--cache-only",
        help="Fetch from ESPN API (default) or use cache only",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose output",
    ),
) -> None:
    """Seed historical games from ESPN API with local caching.

    Fetches game data from ESPN's scoreboard API and caches locally.
    Subsequent runs with --cache-only skip API calls.

    Caching:
        Data cached to data/historical/espn/{sport}/{YYYY-MM-DD}.json
        Use --cache-only to load from cache without API calls.
        Useful for reproducibility and offline development.

    Rate Limiting:
        ESPN allows ~500 requests/hour. With 7.5s between requests,
        a full season (~180 days) takes ~22 minutes.

    Examples:
        # Seed NFL 2023 regular season (fetch from API + cache)
        precog data seed-espn --sport nfl --start 2023-09-07 --end 2024-01-07

        # Seed from cache only (no API calls)
        precog data seed-espn --sport nfl --start 2023-09-07 --end 2024-01-07 --cache-only

        # Seed NBA 2023-24 season
        precog data seed-espn --sport nba --start 2023-10-24 --end 2024-04-14

    Related:
        - Issue #229: Expanded Historical Data Sources
        - ESPNClient: API client with rate limiting
        - data/historical/espn/: Cache directory
    """
    from datetime import datetime as dt

    from precog.database.seeding.batch_result import ErrorHandlingMode
    from precog.database.seeding.historical_games_loader import (
        get_cache_stats,
        load_espn_historical_games,
    )

    # Parse dates
    try:
        start = dt.strptime(start_date, "%Y-%m-%d").date()
        end = dt.strptime(end_date, "%Y-%m-%d").date()
    except ValueError as e:
        cli_error(
            f"Invalid date format: {e}",
            ExitCode.USAGE_ERROR,
            hint="Use YYYY-MM-DD format (e.g., 2023-09-07)",
        )

    if end < start:
        cli_error(
            f"End date ({end}) must be after start date ({start})",
            ExitCode.USAGE_ERROR,
        )

    # Calculate days
    days = (end - start).days + 1
    console.print("\n[bold cyan]ESPN Historical Games Seeder[/bold cyan]\n")
    console.print(f"[dim]Sport: {sport.upper()}[/dim]")
    console.print(f"[dim]Date range: {start} to {end} ({days} days)[/dim]")
    console.print(f"[dim]Mode: {'Fetch + Cache' if fetch else 'Cache Only'}[/dim]\n")

    # Estimate time if fetching
    if fetch:
        estimated_time = days * 7.5 / 60  # 7.5s per request
        console.print(f"[dim]Estimated time: ~{estimated_time:.1f} minutes[/dim]\n")

    # Load games
    console.print("[bold]Loading ESPN games...[/bold]\n")

    try:
        result = load_espn_historical_games(
            sport=sport,
            start_date=start,
            end_date=end,
            use_cache=True,  # Always try cache first
            fetch_missing=fetch,  # Only fetch if --fetch
            error_mode=ErrorHandlingMode.COLLECT,
            show_progress=True,
        )
    except Exception as e:
        cli_error(
            f"ESPN seeding failed: {e}",
            ExitCode.ERROR,
            hint="Check ESPN API availability and rate limits",
        )

    # Report results
    console.print("\n[bold]Results:[/bold]")
    console.print(f"  Records processed: {result.records_processed:,}")
    console.print(f"  Records inserted: {result.records_inserted:,}")
    console.print(f"  Records skipped: {result.records_skipped:,}")
    console.print(f"  Errors: {result.errors}")

    if result.has_failures and verbose:
        console.print("\n[yellow]Errors:[/yellow]")
        console.print(result.get_failure_summary())

    # Cache stats
    try:
        cache_info = get_cache_stats(sport)
        console.print(f"\n[bold]Cache Status ({sport.upper()}):[/bold]")
        console.print(f"  Cached dates: {cache_info.get('cached_dates', 0):,}")
        console.print(f"  Cached games: {cache_info.get('total_games', 0):,}")
        console.print(f"  Cache size: {cache_info.get('total_size_mb', 0):.2f} MB")
    except Exception:
        pass  # Cache stats are optional

    if result.records_inserted > 0:
        console.print(
            f"\n[green]ESPN seeding completed: {result.records_inserted} games loaded[/green]"
        )
    else:
        console.print("\n[yellow]No new games inserted (may already exist in DB)[/yellow]")


@app.command("cache-stats")
def cache_stats(
    sport: str | None = typer.Option(
        None,
        "--sport",
        "-s",
        help="Specific sport or all sports if not provided",
    ),
) -> None:
    """Show cache statistics for ESPN historical data.

    Displays information about locally cached ESPN data including
    date ranges, game counts, and cache sizes.

    Examples:
        precog data cache-stats
        precog data cache-stats --sport nfl
    """
    from precog.database.seeding.historical_games_loader import get_cache_stats

    console.print("\n[bold cyan]ESPN Cache Statistics[/bold cyan]\n")

    try:
        stats = get_cache_stats(sport)
    except Exception as e:
        cli_error(
            f"Failed to get cache stats: {e}",
            ExitCode.ERROR,
        )

    if sport:
        # Single sport stats
        console.print(f"[bold]{sport.upper()}:[/bold]")
        console.print(f"  Cached dates: {stats.get('cached_dates', 0):,}")
        console.print(f"  Total games: {stats.get('total_games', 0):,}")
        console.print(f"  Cache size: {stats.get('total_size_mb', 0):.2f} MB")

        date_range = stats.get("date_range")
        if date_range:
            console.print(f"  Date range: {date_range[0]} to {date_range[1]}")
    else:
        # All sports stats
        by_sport = stats.get("by_sport", {})
        if not by_sport:
            console.print("[dim]No cached data found[/dim]")
            console.print("[dim]Run 'precog data seed-espn' to cache data[/dim]")
            return

        table = Table(title="ESPN Cache by Sport")
        table.add_column("Sport", style="cyan")
        table.add_column("Dates", justify="right")
        table.add_column("Games", justify="right")
        table.add_column("Size (MB)", justify="right")

        total_dates = 0
        total_games = 0
        total_size = 0.0

        for sport_name, sport_stats in sorted(by_sport.items()):
            dates = sport_stats.get("cached_dates", 0)
            games = sport_stats.get("total_games", 0)
            size = sport_stats.get("total_size_mb", 0)

            total_dates += dates
            total_games += games
            total_size += size

            table.add_row(
                sport_name.upper(),
                f"{dates:,}",
                f"{games:,}",
                f"{size:.2f}",
            )

        table.add_row(
            "[bold]TOTAL[/bold]",
            f"[bold]{total_dates:,}[/bold]",
            f"[bold]{total_games:,}[/bold]",
            f"[bold]{total_size:.2f}[/bold]",
        )

        console.print(table)

    console.print()


@app.command("cache-kalshi")
def cache_kalshi(
    data_type: str = typer.Option(
        "all",
        "--type",
        "-t",
        help="Type to cache: markets, series, positions, or all",
    ),
    category: str | None = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter by category (e.g., sports)",
    ),
    series_ticker: str | None = typer.Option(
        None,
        "--series",
        "-s",
        help="Filter markets by series ticker (e.g., KXNFLGAME)",
    ),
    force_refresh: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force refresh even if cache exists",
    ),
) -> None:
    """Cache Kalshi API data locally for reproducibility.

    Fetches data from Kalshi API and saves to local cache files.
    Useful for backtesting, development, and production migration.

    Cache Location:
        data/historical/kalshi/{type}/{YYYY-MM-DD}.json

    Examples:
        # Cache all data types for today
        precog data cache-kalshi

        # Cache only sports series
        precog data cache-kalshi --type series --category sports

        # Cache NFL game markets
        precog data cache-kalshi --type markets --series KXNFLGAME

        # Force refresh existing cache
        precog data cache-kalshi --type markets --force

    Related:
        - precog data kalshi-cache-stats: View cache statistics
        - data/historical/kalshi/: Cache directory
    """
    from datetime import UTC, datetime

    from precog.api_connectors import KalshiClient
    from precog.database.seeding.kalshi_historical_cache import (
        fetch_and_cache_markets,
        fetch_and_cache_positions,
        fetch_and_cache_series,
    )

    console.print("\n[bold cyan]Kalshi Data Caching[/bold cyan]\n")

    today = datetime.now(UTC).date()
    console.print(f"[dim]Date: {today}[/dim]")
    console.print(f"[dim]Type: {data_type}[/dim]")

    if category:
        console.print(f"[dim]Category: {category}[/dim]")
    if series_ticker:
        console.print(f"[dim]Series: {series_ticker}[/dim]")
    console.print()

    # Initialize Kalshi client
    try:
        client = KalshiClient()
    except Exception as e:
        cli_error(
            f"Failed to initialize Kalshi client: {e}",
            ExitCode.ERROR,
            hint="Check KALSHI_API_KEY and KALSHI_API_SECRET in .env",
        )

    types_to_cache = ["series", "markets", "positions"] if data_type == "all" else [data_type]

    results = {}

    for cache_type in types_to_cache:
        console.print(f"[bold]Caching {cache_type}...[/bold]")

        try:
            if cache_type == "markets":
                data = fetch_and_cache_markets(
                    client,
                    today,
                    series_ticker=series_ticker,
                    category=category,
                    force_refresh=force_refresh,
                )
            elif cache_type == "series":
                data = fetch_and_cache_series(
                    client,
                    today,
                    category=category,
                    force_refresh=force_refresh,
                )
            elif cache_type == "positions":
                data = fetch_and_cache_positions(
                    client,
                    today,
                    force_refresh=force_refresh,
                )
            else:
                console.print(f"  [yellow]Unknown type: {cache_type}[/yellow]")
                continue

            results[cache_type] = len(data)
            console.print(f"  [green]Cached {len(data)} {cache_type}[/green]")

        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")
            results[cache_type] = -1

    # Summary
    console.print("\n[bold]Summary:[/bold]")
    for cache_type, count in results.items():
        if count >= 0:
            console.print(f"  {cache_type}: {count} records")
        else:
            console.print(f"  {cache_type}: [red]failed[/red]")

    console.print("\n[dim]Cache location: data/historical/kalshi/[/dim]")


@app.command("kalshi-cache-stats")
def kalshi_cache_stats(
    data_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Specific type (markets, series, positions) or all if not provided",
    ),
) -> None:
    """Show cache statistics for Kalshi historical data.

    Displays information about locally cached Kalshi data including
    date ranges, record counts, and cache sizes.

    Examples:
        precog data kalshi-cache-stats
        precog data kalshi-cache-stats --type markets
    """
    from precog.database.seeding.kalshi_historical_cache import get_kalshi_cache_stats

    console.print("\n[bold cyan]Kalshi Cache Statistics[/bold cyan]\n")

    try:
        stats = get_kalshi_cache_stats(data_type)
    except Exception as e:
        cli_error(
            f"Failed to get cache stats: {e}",
            ExitCode.ERROR,
        )

    if data_type:
        # Single type stats
        type_stats = stats.get("by_type", {}).get(data_type, {})
        console.print(f"[bold]{data_type.upper()}:[/bold]")
        console.print(f"  Cached dates: {type_stats.get('cached_dates', 0):,}")
        console.print(f"  Total records: {type_stats.get('total_records', 0):,}")

        size_bytes = type_stats.get("total_size_bytes", 0)
        console.print(f"  Cache size: {size_bytes / (1024 * 1024):.2f} MB")

        date_range = type_stats.get("date_range")
        if date_range:
            console.print(f"  Date range: {date_range[0]} to {date_range[1]}")
    else:
        # All types
        by_type = stats.get("by_type", {})
        if not any(t.get("cached_dates", 0) > 0 for t in by_type.values()):
            console.print("[dim]No cached data found[/dim]")
            console.print("[dim]Run 'precog data cache-kalshi' to cache data[/dim]")
            return

        table = Table(title="Kalshi Cache by Type")
        table.add_column("Type", style="cyan")
        table.add_column("Dates", justify="right")
        table.add_column("Records", justify="right")
        table.add_column("Size (MB)", justify="right")

        for type_name, type_stats in sorted(by_type.items()):
            dates = type_stats.get("cached_dates", 0)
            records = type_stats.get("total_records", 0)
            size = type_stats.get("total_size_bytes", 0) / (1024 * 1024)

            table.add_row(
                type_name.upper(),
                f"{dates:,}",
                f"{records:,}",
                f"{size:.2f}",
            )

        table.add_row(
            "[bold]TOTAL[/bold]",
            f"[bold]{stats.get('cached_dates', 0):,}[/bold]",
            f"[bold]{stats.get('total_records', 0):,}[/bold]",
            f"[bold]{stats.get('total_size_mb', 0):.2f}[/bold]",
        )

        console.print(table)

        date_range = stats.get("date_range")
        if date_range:
            console.print(f"\n[dim]Date range: {date_range[0]} to {date_range[1]}[/dim]")

    console.print()


class LibrarySource(str, Enum):
    """Available Python library sources."""

    NFL_DATA_PY = "nfl_data_py"
    NFLREADPY = "nflreadpy"
    NBA_API = "nba_api"
    PYBASEBALL = "pybaseball"


@app.command("seed-lib")
def seed_lib(
    source: LibrarySource = typer.Option(
        ...,
        "--source",
        "-s",
        help="Python library source (nfl_data_py, nflreadpy, nba_api, pybaseball)",
    ),
    seasons: str = typer.Option(
        ...,
        "--seasons",
        help="Comma-separated seasons to load (e.g., 2022,2023,2024)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose output",
    ),
) -> None:
    """Seed historical games from Python sports data libraries.

    Loads game data from various sports data Python libraries and inserts
    into the historical_games table for Elo computation.

    Supported Libraries:
        nfl_data_py: NFL schedules and results (2000-present)
        nflreadpy: NFL data with EPA metrics (1999-present)
        nba_api: NBA game logs from stats.nba.com (1996-present)
        pybaseball: MLB games from Baseball Reference (1901-present)

    Examples:
        # Seed NFL 2022-2024 from nfl_data_py
        precog data seed-lib --source nfl_data_py --seasons 2022,2023,2024

        # Seed NBA 2020-2024 from nba_api
        precog data seed-lib --source nba_api --seasons 2020,2021,2022,2023,2024

        # Seed MLB 2023-2024 from pybaseball
        precog data seed-lib --source pybaseball --seasons 2023,2024

    Prerequisites:
        - Teams must be seeded first: precog data seed --type teams
        - Library must be installed (pip install nfl_data_py / nba_api / pybaseball)

    Related:
        - Issue #229: Expanded Historical Data Sources
        - docs/guides/: Data source adapter documentation
    """

    # Parse seasons
    try:
        season_list = [int(s.strip()) for s in seasons.split(",")]
    except ValueError:
        cli_error(
            f"Invalid seasons format: {seasons}",
            ExitCode.USAGE_ERROR,
            hint="Use comma-separated years (e.g., 2022,2023,2024)",
        )

    console.print("\n[bold cyan]Python Library Seeder[/bold cyan]\n")
    console.print(f"[dim]Source: {source.value}[/dim]")
    console.print(f"[dim]Seasons: {season_list}[/dim]\n")

    # Load appropriate adapter
    adapter: BaseDataSource | None = None
    sport: str = ""

    if source == LibrarySource.NFL_DATA_PY:
        sport = "nfl"
        try:
            from precog.database.seeding.sources.sports.nfl_data_py_adapter import (
                NFLDataPySource,
            )

            adapter = NFLDataPySource()
        except ImportError as e:
            cli_error(
                f"nfl_data_py not installed: {e}",
                ExitCode.ERROR,
                hint="Install with: pip install nfl_data_py",
            )

    elif source == LibrarySource.NFLREADPY:
        sport = "nfl"
        try:
            from precog.database.seeding.sources.sports.nflreadpy_adapter import (
                NFLReadPySource,
            )

            adapter = NFLReadPySource()
        except ImportError as e:
            cli_error(
                f"nflreadpy not installed: {e}",
                ExitCode.ERROR,
                hint="Install with: pip install nflreadpy",
            )

    elif source == LibrarySource.NBA_API:
        sport = "nba"
        try:
            from precog.database.seeding.sources.sports.nba_api_adapter import (
                NBAApiSource,
            )

            adapter = NBAApiSource()
        except ImportError as e:
            cli_error(
                f"nba_api not installed: {e}",
                ExitCode.ERROR,
                hint="Install with: pip install nba_api",
            )

    elif source == LibrarySource.PYBASEBALL:
        sport = "mlb"
        try:
            from precog.database.seeding.sources.sports.pybaseball_adapter import (
                PybaseballSource,
            )

            adapter = PybaseballSource()
        except ImportError as e:
            cli_error(
                f"pybaseball not installed: {e}",
                ExitCode.ERROR,
                hint="Install with: pip install pybaseball",
            )

    else:
        cli_error(
            f"Unknown source: {source}",
            ExitCode.USAGE_ERROR,
        )

    # Safety assertion - all branches either set adapter or call cli_error (NoReturn)
    assert adapter is not None, "Adapter should be set by source selection"

    console.print(f"[bold]Loading {sport.upper()} games from {source.value}...[/bold]\n")

    # Collect games from adapter
    games_loaded = 0
    games_skipped = 0
    errors = 0

    try:
        for game_record in adapter.load_games(sport=sport, seasons=season_list):
            games_loaded += 1

            if verbose and games_loaded % 100 == 0:
                console.print(f"  [dim]Loaded {games_loaded} games...[/dim]")

            # TODO: Insert into historical_games table
            # For now, just count the games

    except Exception as e:
        errors += 1
        console.print(f"[red]Error loading games: {e}[/red]")

    # Report results
    console.print("\n[bold]Results:[/bold]")
    console.print(f"  Games loaded: {games_loaded:,}")
    console.print(f"  Games skipped: {games_skipped:,}")
    console.print(f"  Errors: {errors}")

    if games_loaded > 0:
        console.print(f"\n[green]Library seeding complete: {games_loaded} games loaded[/green]")
        console.print(
            "[dim]Note: Database insertion requires connecting to historical_games CRUD[/dim]"
        )
    else:
        console.print(f"\n[yellow]No games found for seasons {season_list}[/yellow]")
        console.print(f"[dim]Check if {source.value} has data for these seasons[/dim]")


# =============================================================================
# Elo Rating Computation Commands
# =============================================================================


class EloLeague(str, Enum):
    """Leagues supported for Elo computation.

    Renamed from EloSport to EloLeague in #460 Phase B -- values are league codes.
    """

    NFL = "nfl"
    NBA = "nba"
    NHL = "nhl"
    MLB = "mlb"
    NCAAF = "ncaaf"
    NCAAB = "ncaab"
    WNBA = "wnba"
    MLS = "mls"


@app.command("compute-elo")
def compute_elo(
    league: EloLeague = typer.Argument(
        ...,
        help="League to compute Elo ratings for",
    ),
    seasons: str = typer.Option(
        "",
        "--seasons",
        "-s",
        help="Comma-separated seasons (e.g., '2019,2020'). Default: all available.",
    ),
    skip_computed: bool = typer.Option(
        True,
        "--skip-computed/--recompute",
        help="Skip games already in elo_calculation_log (default: skip)",
    ),
    show_ratings: bool = typer.Option(
        False,
        "--show-ratings",
        "-r",
        help="Show team ratings after computation",
    ),
    top_n: int = typer.Option(
        10,
        "--top",
        "-n",
        help="Number of top teams to show (requires --show-ratings)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed progress",
    ),
    sync_to_teams: bool = typer.Option(
        False,
        "--sync",
        help="Update teams.current_elo_rating after computation",
    ),
) -> None:
    """Compute Elo ratings from historical games.

    This command processes games chronologically and computes Elo ratings
    using the FiveThirtyEight-style algorithm. Results are stored in
    elo_calculation_log for audit trail.

    Pipeline (with --sync):
        historical_games -> elo_calculation_log (audit)
            -> teams.current_elo_rating (LIVE)

    Example:
        precog data compute-elo nfl
        precog data compute-elo nba --seasons 2019,2020 --show-ratings
        precog data compute-elo nfl --recompute  # Force recomputation
        precog data compute-elo nfl --sync       # Also update teams table
    """
    from precog.analytics.elo_computation_service import (
        EloComputationService,
        get_elo_computation_stats,
    )
    from precog.database.connection import get_connection, release_connection

    # Parse seasons
    season_list: list[int] | None = None
    if seasons:
        try:
            season_list = [int(s.strip()) for s in seasons.split(",")]
        except ValueError:
            cli_error(
                f"Invalid seasons format: {seasons}",
                ExitCode.USAGE_ERROR,
                hint="Use comma-separated years: --seasons 2019,2020",
            )

    console.print(f"\n[bold]Computing Elo Ratings for {league.value.upper()}[/bold]")
    console.print(f"  Seasons: {season_list if season_list else 'all available'}")
    console.print(f"  Skip computed: {skip_computed}")
    console.print(f"  Sync to teams: {sync_to_teams}")
    console.print()

    conn = None
    try:
        conn = get_connection()
        # Create service (use 'backfill' since we're computing historical data)
        service = EloComputationService(
            conn,
            calculation_source="backfill",
            calculation_version="1.0",
        )

        # Compute ratings (use simple print for Windows cp1252 compatibility)
        console.print(f"Processing {league.value.upper()} games...")

        result = service.compute_ratings(
            league=league.value,
            seasons=season_list,
            skip_computed=skip_computed,
            sync_to_teams=sync_to_teams,
        )

        console.print("Done!")

        # Display results
        console.print("\n[bold]Computation Results:[/bold]")

        results_table = Table(show_header=False, box=None, padding=(0, 2))
        results_table.add_column("Metric", style="dim")
        results_table.add_column("Value", style="bold")

        results_table.add_row("League", result.league.upper())
        results_table.add_row("Seasons", str(result.seasons))
        results_table.add_row("Games Processed", f"{result.games_processed:,}")
        results_table.add_row("Games Skipped", f"{result.games_skipped:,}")
        results_table.add_row("Teams Updated", str(result.teams_updated))
        results_table.add_row("Logs Inserted", f"{result.logs_inserted:,}")
        if sync_to_teams:
            results_table.add_row(
                "Teams Synced", f"{result.teams_updated} -> teams.current_elo_rating"
            )
        results_table.add_row("Duration", f"{result.duration_seconds:.2f}s")

        console.print(results_table)

        if result.errors:
            console.print("\n[red]Errors:[/red]")
            for error in result.errors:
                console.print(f"  - {error}")

        # Show ratings if requested
        if show_ratings and result.games_processed > 0:
            ratings = service.get_team_rating_details(league.value)

            if ratings:
                # Sort by rating descending
                sorted_teams = sorted(
                    ratings.items(),
                    key=lambda x: x[1]["rating"],
                    reverse=True,
                )[:top_n]

                console.print(f"\n[bold]Top {top_n} Teams by Elo Rating:[/bold]")

                ratings_table = Table(box=None)
                ratings_table.add_column("Rank", style="dim", width=4)
                ratings_table.add_column("Team", style="bold", width=8)
                ratings_table.add_column("Rating", justify="right", width=8)
                ratings_table.add_column("Games", justify="right", width=6)
                ratings_table.add_column("Change", justify="right", width=8)
                ratings_table.add_column("Peak", justify="right", width=8)

                for i, (team, data) in enumerate(sorted_teams, 1):
                    change = data["rating_change"]
                    change_str = f"{change:+.1f}"
                    change_style = "green" if change > 0 else "red" if change < 0 else "dim"

                    ratings_table.add_row(
                        str(i),
                        team,
                        f"{data['rating']:.0f}",
                        str(data["games_played"]),
                        f"[{change_style}]{change_str}[/{change_style}]",
                        f"{data['peak_rating']:.0f}",
                    )

                console.print(ratings_table)

        # Show overall stats
        if verbose:
            stats = get_elo_computation_stats(conn)
            console.print("\n[bold]Overall Elo Computation Stats:[/bold]")
            console.print(f"  Total calculations: {stats['total_calculations']:,}")
            for league_name, league_stats in stats["by_league"].items():
                console.print(
                    f"  {league_name.upper()}: {league_stats['count']:,} "
                    f"({league_stats['first_date']} to {league_stats['last_date']})"
                )

        if result.games_processed > 0:
            echo_success(
                f"Computed {result.games_processed:,} Elo ratings for {league.value.upper()}"
            )
        elif result.games_skipped > 0:
            console.print(
                f"\n[yellow]All {result.games_skipped:,} games already computed. "
                f"Use --recompute to recalculate.[/yellow]"
            )
        else:
            console.print(
                f"\n[yellow]No games found for {league.value.upper()} "
                f"seasons {season_list}[/yellow]"
            )

    except Exception as e:
        cli_error(
            f"Elo computation failed: {e}",
            ExitCode.ERROR,
            hint="Check database connection and historical_games data",
        )
    finally:
        if conn is not None:
            release_connection(conn)


@app.command("elo-stats")
def elo_stats(
    league: EloLeague | None = typer.Argument(
        None,
        help="League to show stats for (optional)",
    ),
) -> None:
    """Show Elo computation statistics from elo_calculation_log.

    Example:
        precog data elo-stats        # Show all leagues
        precog data elo-stats nfl    # Show NFL only
    """
    from precog.analytics.elo_computation_service import get_elo_computation_stats
    from precog.database.connection import get_connection, release_connection

    console.print("\n[bold]Elo Computation Statistics[/bold]\n")

    conn = None
    try:
        conn = get_connection()
        stats = get_elo_computation_stats(conn)

        if stats["total_calculations"] == 0:
            console.print("[yellow]No Elo computations found in database.[/yellow]")
            console.print("[dim]Run 'precog data compute-elo <league>' to compute ratings.[/dim]")
            return

        # Filter by league if specified
        if league:
            if league.value in stats["by_league"]:
                stats["by_league"] = {league.value: stats["by_league"][league.value]}
            else:
                console.print(f"[yellow]No computations found for {league.value.upper()}[/yellow]")
                return

        # Create table
        table = Table(title="Elo Calculations by League")
        table.add_column("League", style="bold")
        table.add_column("Games", justify="right")
        table.add_column("First Date")
        table.add_column("Last Date")

        for league_name, league_stats in sorted(stats["by_league"].items()):
            table.add_row(
                league_name.upper(),
                f"{league_stats['count']:,}",
                league_stats["first_date"] or "-",
                league_stats["last_date"] or "-",
            )

        console.print(table)
        console.print(f"\n[bold]Total:[/bold] {stats['total_calculations']:,} calculations")

    except Exception as e:
        cli_error(
            f"Failed to get Elo stats: {e}",
            ExitCode.ERROR,
        )
    finally:
        if conn is not None:
            release_connection(conn)


# =============================================================================
# Matching Subcommand Group
# =============================================================================

matching_app = typer.Typer(
    name="matching",
    help="Event-to-game matching operations (stats, backfill, refresh)",
    no_args_is_help=True,
)
app.add_typer(matching_app, name="matching")


@matching_app.command(
    "stats",
    help="Show event-to-game matching statistics.",
    epilog="Example: precog data matching stats --league nfl",
)
def matching_stats(
    league: str | None = typer.Option(
        None,
        "--league",
        "-l",
        help="Filter by league (nfl, nba, nhl, ncaaf, ncaab)",
    ),
) -> None:
    """Show event-to-game matching statistics.

    Displays how many events have been matched to games, broken down
    by match result category (matched, parse_fail, no_code, no_game).

    Examples:
        precog data matching stats
        precog data matching stats --league nfl
    """
    console.print("\n[bold cyan]Event-to-Game Matching Statistics[/bold cyan]\n")

    try:
        from precog.database.connection import get_cursor
        from precog.database.crud_operations import find_unlinked_sports_events

        with get_cursor() as cursor:
            # Count linked vs unlinked events
            if league:
                cursor.execute(
                    "SELECT COUNT(*) FROM events WHERE game_id IS NOT NULL AND subcategory = %s",
                    (league,),
                )
            else:
                cursor.execute(
                    "SELECT COUNT(*) FROM events WHERE game_id IS NOT NULL "
                    "AND subcategory IS NOT NULL"
                )
            linked_count = cursor.fetchone()[0]

            # Get unlinked count
            unlinked = find_unlinked_sports_events(league=league)
            unlinked_count = len(unlinked)

            total = linked_count + unlinked_count
            # NOTE: float is intentional here -- this is a ratio of integer
            # counts, not a price or probability.
            match_rate = (linked_count / total * 100) if total > 0 else 0.0

            console.print("[bold]Overall:[/bold]")
            console.print(f"  Total sports events: {total:,}")
            console.print(f"  Linked to games:     {linked_count:,}")
            console.print(f"  Unlinked:            {unlinked_count:,}")
            console.print(f"  Match rate:          {match_rate:.1f}%")

            # Per-league breakdown
            if not league:
                cursor.execute(
                    "SELECT subcategory, "
                    "  COUNT(*) FILTER (WHERE game_id IS NOT NULL) AS linked, "
                    "  COUNT(*) FILTER (WHERE game_id IS NULL) AS unlinked "
                    "FROM events "
                    "WHERE subcategory IS NOT NULL "
                    "GROUP BY subcategory ORDER BY subcategory"
                )
                rows = cursor.fetchall()
                if rows:
                    console.print("\n[bold]Per League:[/bold]")
                    league_table = Table(show_header=True, header_style="bold")
                    league_table.add_column("League")
                    league_table.add_column("Linked", justify="right")
                    league_table.add_column("Unlinked", justify="right")
                    league_table.add_column("Rate", justify="right")

                    for row in rows:
                        row_league, row_linked, row_unlinked = row
                        row_total = row_linked + row_unlinked
                        row_rate = (row_linked / row_total * 100) if row_total > 0 else 0.0
                        league_table.add_row(
                            row_league.upper(),
                            f"{row_linked:,}",
                            f"{row_unlinked:,}",
                            f"{row_rate:.1f}%",
                        )
                    console.print(league_table)

    except Exception as e:
        cli_error(
            f"Failed to get matching stats: {e}",
            ExitCode.DATABASE_ERROR,
            hint="Check database connection",
        )

    console.print()


@matching_app.command(
    "backfill",
    help="Manually trigger backfill of unlinked events.",
    epilog="Example: precog data matching backfill --league nfl",
)
def matching_backfill(
    league: str | None = typer.Option(
        None,
        "--league",
        "-l",
        help="Filter by league (nfl, nba, nhl, ncaaf, ncaab)",
    ),
) -> None:
    """Manually trigger backfill of events with game_id=NULL.

    Attempts to match unlinked events to games using ticker parsing
    and the team code registry. Safe to run multiple times.

    Examples:
        precog data matching backfill
        precog data matching backfill --league nfl
    """
    console.print("\n[bold cyan]Matching Backfill[/bold cyan]\n")

    try:
        from precog.matching import EventGameMatcher

        console.print("[dim]Loading team code registry...[/dim]")
        matcher = EventGameMatcher()
        matcher.registry.load()

        registry_codes = sum(
            len(matcher.registry.get_kalshi_codes(lg))
            for lg in ("nfl", "ncaaf", "nba", "ncaab", "nhl", "wnba")
        )
        console.print(f"[dim]Registry loaded: {registry_codes} codes[/dim]\n")

        console.print("Running backfill...")
        linked = matcher.backfill_unlinked_events(league=league)

        if linked > 0:
            echo_success(f"Linked {linked} events to games")
        else:
            console.print("[dim]No new matches found[/dim]")

    except Exception as e:
        cli_error(
            f"Backfill failed: {e}",
            ExitCode.DATABASE_ERROR,
            hint="Check database connection and that teams are seeded",
        )

    console.print()


@matching_app.command(
    "refresh",
    help="Manually reload the team code registry from the database.",
    epilog="Example: precog data matching refresh",
)
def matching_refresh(
    league: str | None = typer.Option(
        None,
        "--league",
        "-l",
        help="Refresh only a specific league (default: all)",
    ),
) -> None:
    """Manually reload the team code registry from the database.

    Use this after adding new teams or updating kalshi_team_code mappings
    to ensure the matching module picks up the changes.

    Examples:
        precog data matching refresh
        precog data matching refresh --league nfl
    """
    console.print("\n[bold cyan]Registry Refresh[/bold cyan]\n")

    try:
        from precog.matching import TeamCodeRegistry

        registry = TeamCodeRegistry()
        console.print("[dim]Loading team codes from database...[/dim]")
        registry.load(league=league)

        # Show what was loaded
        leagues = ("nfl", "ncaaf", "nba", "ncaab", "nhl", "wnba")
        loaded_table = Table(show_header=True, header_style="bold")
        loaded_table.add_column("League")
        loaded_table.add_column("Codes", justify="right")

        total = 0
        for lg in leagues:
            codes = registry.get_kalshi_codes(lg)
            if codes:
                loaded_table.add_row(lg.upper(), str(len(codes)))
                total += len(codes)

        if total > 0:
            console.print(loaded_table)
            echo_success(f"Registry loaded: {total} codes across {len(leagues)} leagues")
        else:
            console.print("[yellow]No team codes found in database[/yellow]")
            console.print("[dim]Run 'precog data seed --type teams' first[/dim]")

        if registry.last_loaded_at:
            console.print(f"\n[dim]Loaded at: {registry.last_loaded_at.isoformat()}[/dim]")

    except Exception as e:
        cli_error(
            f"Registry refresh failed: {e}",
            ExitCode.DATABASE_ERROR,
            hint="Check database connection",
        )

    console.print()


# =============================================================================
# Teams Subcommand Group
# =============================================================================

teams_app = typer.Typer(
    name="teams",
    help="Team data operations (classification, CFBD refresh)",
    no_args_is_help=True,
)
app.add_typer(teams_app, name="teams")


@teams_app.command(
    "classification",
    help="Show team classification coverage by league.",
    epilog="Example: precog data teams classification",
)
def teams_classification(
    league: str | None = typer.Option(
        None,
        "--league",
        "-l",
        help="Filter by league (nfl, nba, ncaaf, etc.)",
    ),
) -> None:
    """Show team classification coverage by league.

    Displays how many teams have classification data (FBS/FCS/D2/D3/
    professional) vs NULL, broken down by league. Useful for monitoring
    data quality after CFBD backfills.

    Examples:
        precog data teams classification
        precog data teams classification --league ncaaf
    """
    console.print("\n[bold cyan]Team Classification Coverage[/bold cyan]\n")

    try:
        from precog.database.crud_operations import fetch_all as db_fetch_all

        if league:
            rows = db_fetch_all(
                "SELECT league, classification, COUNT(*) AS cnt "
                "FROM teams WHERE league = %s "
                "GROUP BY league, classification "
                "ORDER BY league, classification",
                (league,),
            )
        else:
            rows = db_fetch_all(
                "SELECT league, classification, COUNT(*) AS cnt "
                "FROM teams "
                "GROUP BY league, classification "
                "ORDER BY league, classification",
            )

        if not rows:
            console.print("[dim]No teams found[/dim]")
            return

        cls_table = Table(show_header=True, header_style="bold")
        cls_table.add_column("League")
        cls_table.add_column("Classification")
        cls_table.add_column("Count", justify="right")

        total_classified = 0
        total_null = 0
        for row in rows:
            row_league = row["league"]
            row_cls = row["classification"]
            cnt = int(row["cnt"])
            display_cls = row_cls or "[dim]NULL[/dim]"
            cls_table.add_row(row_league.upper(), display_cls, f"{cnt:,}")
            if row_cls:
                total_classified += cnt
            else:
                total_null += cnt

        console.print(cls_table)

        total = total_classified + total_null
        # NOTE: float is intentional — ratio of counts, not a price
        pct = (total_classified / total * 100) if total > 0 else 0.0
        console.print(
            f"\n[bold]Total:[/bold] {total_classified:,}/{total:,} classified ({pct:.1f}%)"
        )
        if total_null > 0:
            console.print(
                "[dim]Hint: Run 'precog data teams refresh-cfbd' to classify "
                "NCAAF teams via CFBD API[/dim]"
            )

    except Exception as e:
        cli_error(
            f"Failed to get classification stats: {e}",
            ExitCode.DATABASE_ERROR,
            hint="Check database connection",
        )

    console.print()


@teams_app.command(
    "refresh-cfbd",
    help="Populate team classifications from CFBD API.",
    epilog="Example: precog data teams refresh-cfbd",
)
def teams_refresh_cfbd(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be updated without making changes",
    ),
) -> None:
    """Fetch team classifications from CFBD API and update the teams table.

    Matches CFBD teams to our teams by abbreviation and updates the
    classification and conference columns. Only updates teams with NULL
    classification (won't overwrite existing values).

    Requires CFBD_API_KEY environment variable to be set.
    Get a free key at: https://collegefootballdata.com

    Examples:
        precog data teams refresh-cfbd
        precog data teams refresh-cfbd --dry-run
    """
    console.print("\n[bold cyan]CFBD Classification Refresh[/bold cyan]\n")

    try:
        from precog.database.crud_operations import fetch_all, update_team_classification
        from precog.database.seeding.sources.sports.cfbd_adapter import CFBDSource

        # Step 1: Fetch from CFBD
        console.print("[dim]Connecting to CFBD API...[/dim]")
        source = CFBDSource()
        cfbd_teams = source.get_team_classifications()
        console.print(f"[dim]CFBD returned {len(cfbd_teams)} classified teams[/dim]\n")

        # Build lookup by abbreviation
        cfbd_by_code: dict[str, dict[str, Any]] = {}
        for t in cfbd_teams:
            abbr = t.get("abbreviation")
            if abbr:
                cfbd_by_code[abbr.upper()] = dict(t)

        # Step 2: Find NCAAF teams with NULL classification
        our_teams = fetch_all(
            "SELECT team_id, team_code, team_name, classification "
            "FROM teams WHERE league = 'ncaaf' AND classification IS NULL "
            "ORDER BY team_code",
        )
        console.print(f"NCAAF teams with NULL classification: {len(our_teams)}")

        # Step 3: Match and update
        matched = 0
        updated = 0
        for team in our_teams:
            code = team["team_code"].upper()
            cfbd_match = cfbd_by_code.get(code)
            if cfbd_match:
                matched += 1
                if dry_run:
                    console.print(
                        f"  [dim]Would update {code}: "
                        f"{cfbd_match['classification']} ({cfbd_match.get('conference', '?')})[/dim]"
                    )
                else:
                    success = update_team_classification(
                        team["team_id"],
                        classification=cfbd_match["classification"],
                        conference=cfbd_match.get("conference"),
                    )
                    if success:
                        updated += 1

        source.close()

        # Report
        if dry_run:
            console.print(f"\n[bold]Dry run:[/bold] Would update {matched} teams")
        elif updated > 0:
            echo_success(f"Updated {updated} teams with CFBD classifications")
        else:
            console.print("[dim]No teams needed updating[/dim]")

        unmatched = len(our_teams) - matched
        if unmatched > 0:
            console.print(
                f"[dim]{unmatched} teams not found in CFBD (likely NAIA/club programs)[/dim]"
            )

    except Exception as e:
        error_msg = str(e)
        if "CFBD_API_KEY" in error_msg:
            cli_error(
                "CFBD API key not configured",
                ExitCode.CONFIG_ERROR,
                hint="Set CFBD_API_KEY in .env (free key from collegefootballdata.com)",
            )
        else:
            cli_error(
                f"CFBD refresh failed: {e}",
                ExitCode.NETWORK_ERROR,
                hint="Check CFBD_API_KEY and network connectivity",
            )

    console.print()
