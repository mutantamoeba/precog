"""
Data Management CLI Commands.

Provides commands for seeding, verifying, and managing data.

Commands:
    seed    - Seed data by type (teams, elo, odds, games)
    verify  - Verify seed data exists
    stats   - Show data statistics
    sources - List available data sources

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

import typer
from rich.table import Table

from precog.cli._common import (
    ExitCode,
    cli_error,
    console,
    echo_success,
)

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
        help="Type of data to seed (teams, elo, odds, games)",
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

    Examples:
        precog data seed --type teams
        precog data seed --type teams --sports nfl,nba
        precog data seed --type elo --csv nfl_elo.csv
        precog data seed --type elo --csv nfl_elo.csv --seasons 2022,2023,2024
        precog data seed --type odds --dir data/historical/ --sport nfl
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
            _seed_games(sport, seasons, verbose)

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


def _seed_games(sport: str, seasons: str | None, verbose: bool) -> None:
    """Seed historical game results (placeholder for future implementation)."""
    cli_error(
        "Game seeding not yet implemented",
        ExitCode.ERROR,
        hint="Target: Phase 2.5 - Use Elo seeding which includes game results",
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
            from precog.database.seeding import get_historical_odds_stats

            stats = get_historical_odds_stats()

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
            "module": "nfl_data_py_adapter",
            "types": ["games"],
            "sports": ["nfl"],
            "description": "NFL schedules and game data (stats planned)",
            "status": "partial",
        },
        {
            "name": "ESPN API",
            "module": "espn_client",
            "types": ["games", "teams"],
            "sports": ["nfl", "ncaaf", "nba", "ncaab", "nhl", "wnba"],
            "description": "Live game states and team data",
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
        ("stats", "Player/team statistics (planned)"),
        ("rankings", "AP/Coaches polls (planned)"),
    ]

    for type_name, desc in types_legend:
        console.print(f"  [cyan]{type_name}[/cyan]: {desc}")

    console.print()
