"""
ESPN Data Operations CLI Commands.

Provides commands for fetching and displaying ESPN game data.

Commands:
    scores    - Show current game scores for a league
    schedule  - Show games for a specific date
    live      - Show only games currently in progress
    status    - Show ESPN client status and rate limits

Usage:
    precog espn scores nfl
    precog espn scores ncaaf --date 2025-01-01
    precog espn schedule nfl --date 2025-01-05
    precog espn live nfl
    precog espn status

Related:
    - Issue #204: CLI Refactor
    - docs/guides/ESPN_DATA_MODEL_V1.0.md
    - docs/planning/CLI_REFACTOR_COMPREHENSIVE_PLAN_V1.0.md Section 4.2.2
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import typer
from rich.table import Table

from precog.cli._common import (
    ExitCode,
    cli_error,
    console,
    get_espn_client,
)

app = typer.Typer(
    name="espn",
    help="ESPN data operations (scores, schedule, live games)",
    no_args_is_help=True,
)

# Supported leagues mapping
SUPPORTED_LEAGUES = {
    "nfl": "NFL Football",
    "ncaaf": "College Football",
    "nba": "NBA Basketball",
    "ncaab": "College Basketball",
    "nhl": "NHL Hockey",
    "wnba": "WNBA Basketball",
}


def _parse_date(date_str: str | None) -> datetime | None:
    """Parse date string into datetime.

    Args:
        date_str: Date in YYYY-MM-DD format or None for today

    Returns:
        Parsed datetime or None for today

    Raises:
        typer.Exit: If date format is invalid
    """
    if not date_str:
        return None

    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as err:
        cli_error(
            f"Invalid date format: {date_str}",
            ExitCode.USAGE_ERROR,
            hint="Use YYYY-MM-DD format (e.g., 2025-01-15)",
        )
        raise typer.Exit(code=1) from err  # pragma: no cover


def _format_game_status(status: str) -> str:
    """Format game status with color coding.

    Args:
        status: Game status string

    Returns:
        Rich-formatted status string
    """
    status_colors = {
        "pre": "[dim]Scheduled[/dim]",
        "in_progress": "[green]LIVE[/green]",
        "halftime": "[yellow]Halftime[/yellow]",
        "final": "[blue]Final[/blue]",
        "unknown": "[dim]Unknown[/dim]",
    }
    return status_colors.get(status, f"[dim]{status}[/dim]")


def _format_score(game: dict[str, Any]) -> str:
    """Format score display for a game.

    Args:
        game: ESPNGameFull dict

    Returns:
        Formatted score string
    """
    state = game.get("state", {})
    home_score = state.get("home_score", 0)
    away_score = state.get("away_score", 0)
    status = state.get("game_status", "pre")

    if status == "pre":
        return "[dim]--[/dim]"
    return f"{away_score} - {home_score}"


def _format_clock(game: dict[str, Any]) -> str:
    """Format clock/period display for a game.

    Args:
        game: ESPNGameFull dict

    Returns:
        Formatted clock string
    """
    state = game.get("state", {})
    status = state.get("game_status", "pre")
    period = state.get("period", 0)
    clock = state.get("clock_display", "")

    if status == "pre":
        # Show game time
        metadata = game.get("metadata", {})
        game_date = metadata.get("game_date", "")
        if game_date:
            try:
                dt = datetime.fromisoformat(game_date.replace("Z", "+00:00"))
                return dt.strftime("%I:%M %p")
            except Exception:
                return "[dim]TBD[/dim]"
        return "[dim]TBD[/dim]"

    if status == "halftime":
        return "Half"

    if status == "final":
        if period > 4:
            return "Final/OT"
        return "Final"

    # In progress
    period_name = f"Q{period}" if period <= 4 else f"OT{period - 4}"
    return f"{period_name} {clock}"


@app.command()
def scores(
    league: str = typer.Argument(
        ...,
        help="League to fetch scores for (nfl, ncaaf, nba, ncaab, nhl, wnba)",
    ),
    date: str | None = typer.Option(
        None,
        "--date",
        "-d",
        help="Date in YYYY-MM-DD format (default: today)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose output",
    ),
) -> None:
    """Show current game scores for a league.

    Fetches and displays all games for the specified league and date,
    showing teams, scores, and game status.

    Examples:
        precog espn scores nfl
        precog espn scores ncaaf --date 2025-01-01
        precog espn scores nba --verbose
    """
    # Validate league
    league_lower = league.lower()
    if league_lower not in SUPPORTED_LEAGUES:
        cli_error(
            f"Unsupported league: {league}",
            ExitCode.USAGE_ERROR,
            hint=f"Supported leagues: {', '.join(SUPPORTED_LEAGUES.keys())}",
        )

    # Parse date
    target_date = _parse_date(date)
    date_display = target_date.strftime("%Y-%m-%d") if target_date else "Today"

    console.print(
        f"\n[bold cyan]Fetching {SUPPORTED_LEAGUES[league_lower]} scores for {date_display}...[/bold cyan]"
    )

    try:
        client = get_espn_client()
        games = client.get_scoreboard(league_lower, target_date)

        if not games:
            console.print(f"\n[yellow]No games found for {date_display}[/yellow]")
            return

        # Build table
        table = Table(
            title=f"{SUPPORTED_LEAGUES[league_lower]} Scores ({date_display}) - {len(games)} games"
        )
        table.add_column("Away", style="white", no_wrap=True)
        table.add_column("Home", style="white", no_wrap=True)
        table.add_column("Score", style="cyan", justify="center")
        table.add_column("Status", justify="center")
        table.add_column("Time/Clock", style="dim", justify="center")

        for game in games:
            metadata = game.get("metadata", {})
            state = game.get("state", {})

            away_team = metadata.get("away_team", {})
            home_team = metadata.get("home_team", {})

            # Format team names with optional rank
            away_name = away_team.get("team_code", "???")
            home_name = home_team.get("team_code", "???")

            away_rank = away_team.get("rank")
            home_rank = home_team.get("rank")

            if away_rank and away_rank <= 25:
                away_name = f"#{away_rank} {away_name}"
            if home_rank and home_rank <= 25:
                home_name = f"#{home_rank} {home_name}"

            table.add_row(
                away_name,
                home_name,
                _format_score(dict(game)),
                _format_game_status(state.get("game_status", "unknown")),
                _format_clock(dict(game)),
            )

        console.print(table)

        if verbose:
            remaining = client.get_remaining_requests()
            console.print(f"\n[dim]Rate limit: {remaining} requests remaining this hour[/dim]")

    except Exception as e:
        cli_error(
            f"Failed to fetch scores: {e}",
            ExitCode.NETWORK_ERROR,
            hint="Check network connection and try again",
        )


@app.command()
def schedule(
    league: str = typer.Argument(
        ...,
        help="League to fetch schedule for (nfl, ncaaf, nba, ncaab, nhl, wnba)",
    ),
    date: str | None = typer.Option(
        None,
        "--date",
        "-d",
        help="Date in YYYY-MM-DD format (default: today)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose output",
    ),
) -> None:
    """Show game schedule for a specific date.

    Displays all scheduled games with teams, venue, and broadcast info.
    For past dates, this shows completed game results.

    Examples:
        precog espn schedule nfl
        precog espn schedule nba --date 2025-01-15
        precog espn schedule ncaaf --date 2025-01-01 --verbose
    """
    # Validate league
    league_lower = league.lower()
    if league_lower not in SUPPORTED_LEAGUES:
        cli_error(
            f"Unsupported league: {league}",
            ExitCode.USAGE_ERROR,
            hint=f"Supported leagues: {', '.join(SUPPORTED_LEAGUES.keys())}",
        )

    # Parse date
    target_date = _parse_date(date)
    date_display = target_date.strftime("%Y-%m-%d") if target_date else "Today"

    console.print(
        f"\n[bold cyan]Fetching {SUPPORTED_LEAGUES[league_lower]} schedule for {date_display}...[/bold cyan]"
    )

    try:
        client = get_espn_client()
        games = client.get_scoreboard(league_lower, target_date)

        if not games:
            console.print(f"\n[yellow]No games scheduled for {date_display}[/yellow]")
            return

        # Build detailed schedule table
        table = Table(
            title=f"{SUPPORTED_LEAGUES[league_lower]} Schedule ({date_display}) - {len(games)} games"
        )
        table.add_column("Game", style="white", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Venue", style="dim", overflow="fold", max_width=25)
        table.add_column("TV", style="cyan", no_wrap=True)

        for game in games:
            metadata = game.get("metadata", {})
            state = game.get("state", {})

            away_team = metadata.get("away_team", {})
            home_team = metadata.get("home_team", {})
            venue = metadata.get("venue", {})

            # Format matchup
            away_code = away_team.get("team_code", "???")
            home_code = home_team.get("team_code", "???")
            matchup = f"{away_code} @ {home_code}"

            # Format venue
            venue_name = venue.get("venue_name", "TBD")
            venue_city = venue.get("city", "")
            venue_str = f"{venue_name}"
            if venue_city and verbose:
                venue_str += f", {venue_city}"

            # Broadcast
            broadcast = metadata.get("broadcast", "") or "[dim]--[/dim]"

            table.add_row(
                matchup,
                _format_game_status(state.get("game_status", "unknown")),
                venue_str,
                broadcast,
            )

        console.print(table)

        if verbose:
            remaining = client.get_remaining_requests()
            console.print(f"\n[dim]Rate limit: {remaining} requests remaining this hour[/dim]")

    except Exception as e:
        cli_error(
            f"Failed to fetch schedule: {e}",
            ExitCode.NETWORK_ERROR,
            hint="Check network connection and try again",
        )


@app.command()
def live(
    league: str = typer.Argument(
        ...,
        help="League to fetch live games for (nfl, ncaaf, nba, ncaab, nhl, wnba)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose output (show situation data)",
    ),
) -> None:
    """Show only games currently in progress.

    Filters to only show live games with detailed status including
    period, clock, and possession information.

    Examples:
        precog espn live nfl
        precog espn live nba --verbose
    """
    # Validate league
    league_lower = league.lower()
    if league_lower not in SUPPORTED_LEAGUES:
        cli_error(
            f"Unsupported league: {league}",
            ExitCode.USAGE_ERROR,
            hint=f"Supported leagues: {', '.join(SUPPORTED_LEAGUES.keys())}",
        )

    console.print(
        f"\n[bold cyan]Fetching live {SUPPORTED_LEAGUES[league_lower]} games...[/bold cyan]"
    )

    try:
        client = get_espn_client()
        games = client.get_live_games(league_lower)

        if not games:
            console.print("\n[yellow]No live games at the moment[/yellow]")
            return

        # Build live game table with more detail
        table = Table(
            title=f"Live {SUPPORTED_LEAGUES[league_lower]} Games - {len(games)} in progress"
        )
        table.add_column("Away", style="white", no_wrap=True)
        table.add_column("Home", style="white", no_wrap=True)
        table.add_column("Score", style="cyan", justify="center")
        table.add_column("Period", style="yellow", justify="center")
        table.add_column("Clock", style="green", justify="center")

        if verbose and league_lower in ("nfl", "ncaaf"):
            table.add_column("Situation", style="dim")

        for game in games:
            metadata = game.get("metadata", {})
            state = game.get("state", {})
            situation = state.get("situation", {})

            away_team = metadata.get("away_team", {})
            home_team = metadata.get("home_team", {})

            away_code = away_team.get("team_code", "???")
            home_code = home_team.get("team_code", "???")

            period = state.get("period", 0)
            period_name = f"Q{period}" if period <= 4 else f"OT{period - 4}"

            row_data = [
                away_code,
                home_code,
                f"{state.get('away_score', 0)} - {state.get('home_score', 0)}",
                period_name,
                state.get("clock_display", "0:00"),
            ]

            if verbose and league_lower in ("nfl", "ncaaf"):
                # Format situation for football
                down = situation.get("down")
                distance = situation.get("distance")
                yard_line = situation.get("yard_line")
                possession = situation.get("possession")

                if down and distance and yard_line:
                    sit_str = f"{possession or '?'} ball, {down}&{distance} at {yard_line}"
                else:
                    sit_str = "[dim]--[/dim]"
                row_data.append(sit_str)

            table.add_row(*row_data)

        console.print(table)

        if verbose:
            remaining = client.get_remaining_requests()
            console.print(f"\n[dim]Rate limit: {remaining} requests remaining this hour[/dim]")

    except Exception as e:
        cli_error(
            f"Failed to fetch live games: {e}",
            ExitCode.NETWORK_ERROR,
            hint="Check network connection and try again",
        )


@app.command()
def status(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose output",
    ),
) -> None:
    """Show ESPN client status and rate limits.

    Displays current API client status including remaining rate limit
    capacity and supported leagues.

    Examples:
        precog espn status
        precog espn status --verbose
    """
    console.print("\n[bold cyan]ESPN API Client Status[/bold cyan]\n")

    try:
        client = get_espn_client()
        remaining = client.get_remaining_requests()
        rate_limit = client.rate_limit_per_hour

        table = Table(title="ESPN Client Status")
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")

        # Rate limit info
        used = rate_limit - remaining
        pct_used = (used / rate_limit) * 100 if rate_limit > 0 else 0

        if pct_used > 90:
            remaining_str = f"[red]{remaining}[/red]"
        elif pct_used > 75:
            remaining_str = f"[yellow]{remaining}[/yellow]"
        else:
            remaining_str = f"[green]{remaining}[/green]"

        table.add_row("Rate Limit", f"{rate_limit}/hour")
        table.add_row("Requests Used", str(used))
        table.add_row("Requests Remaining", remaining_str)
        table.add_row("Usage", f"{pct_used:.1f}%")

        console.print(table)

        if verbose:
            console.print("\n[bold]Supported Leagues:[/bold]")
            league_table = Table(show_header=False)
            league_table.add_column("Code", style="cyan")
            league_table.add_column("Name", style="white")

            for code, name in SUPPORTED_LEAGUES.items():
                league_table.add_row(code, name)

            console.print(league_table)

            console.print("\n[bold]Client Configuration:[/bold]")
            config_table = Table(show_header=False)
            config_table.add_column("Setting", style="cyan")
            config_table.add_column("Value", style="white")

            config_table.add_row("Timeout", f"{client.timeout_seconds}s")
            config_table.add_row("Max Retries", str(client.max_retries))

            console.print(config_table)

    except Exception as e:
        cli_error(
            f"Failed to get ESPN status: {e}",
            ExitCode.NETWORK_ERROR,
        )
