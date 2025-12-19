"""
Common CLI Utilities.

Shared utilities, type annotations, and helper functions used across
all CLI command modules. Centralizes error handling, client factories,
console output, and common patterns.

Usage:
    from precog.cli._common import (
        cli_error,
        get_kalshi_client,
        get_espn_client,
        console,
        format_table,
        get_env_mode,
    )

Design Principles:
    - DRY: Common patterns extracted here
    - Consistent error handling across all commands
    - Type-safe client factories with environment awareness
    - Rich console output with graceful fallback

Related:
    - Issue #204: Refactor main.py into modular CLI
    - docs/planning/CLI_REFACTOR_COMPREHENSIVE_PLAN_V1.0.md
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, NoReturn

import typer
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from precog.api_connectors.espn_client import ESPNClient
    from precog.api_connectors.kalshi_client import KalshiClient

# =============================================================================
# Console Output
# =============================================================================

# Rich console for formatted output
# Use force_terminal=False on Windows for better compatibility
console = Console(force_terminal=sys.platform != "win32")


def echo(message: str, *, err: bool = False) -> None:
    """Print message to console.

    Simple wrapper around typer.echo for consistency.
    Handles both stdout and stderr.

    Args:
        message: Message to print
        err: If True, print to stderr
    """
    typer.echo(message, err=err)


def echo_success(message: str) -> None:
    """Print success message in green."""
    console.print(f"[green]{message}[/green]")


def echo_warning(message: str) -> None:
    """Print warning message in yellow."""
    console.print(f"[yellow]Warning: {message}[/yellow]")


def echo_error(message: str) -> None:
    """Print error message in red."""
    console.print(f"[red]Error: {message}[/red]")


def echo_info(message: str) -> None:
    """Print info message in blue."""
    console.print(f"[blue]{message}[/blue]")


# =============================================================================
# Error Handling
# =============================================================================


class ExitCode(int, Enum):
    """Standard CLI exit codes.

    Following Unix conventions:
        0: Success
        1: General error
        2: Command line usage error
        3: Configuration error
        4: Network/API error
        5: Database error
    """

    SUCCESS = 0
    ERROR = 1
    USAGE_ERROR = 2
    CONFIG_ERROR = 3
    NETWORK_ERROR = 4
    DATABASE_ERROR = 5


def cli_error(
    message: str,
    exit_code: ExitCode = ExitCode.ERROR,
    *,
    hint: str | None = None,
) -> NoReturn:
    """Print error message and exit with code.

    Provides consistent error handling across all CLI commands.
    Optionally includes a hint for how to resolve the error.

    Args:
        message: Error message to display
        exit_code: Exit code (default: 1)
        hint: Optional hint for resolution

    Raises:
        typer.Exit: Always raises to exit the CLI

    Example:
        >>> cli_error("API key not found", ExitCode.CONFIG_ERROR,
        ...           hint="Set KALSHI_API_KEY_ID in .env")
    """
    echo_error(message)
    if hint:
        console.print(f"[dim]Hint: {hint}[/dim]")
    raise typer.Exit(code=exit_code.value)


# =============================================================================
# Environment Helpers
# =============================================================================


class EnvMode(str, Enum):
    """Environment mode for API connections."""

    DEMO = "demo"
    PROD = "prod"
    LIVE = "live"  # Alias for prod


def get_env_mode() -> str:
    """Get current environment mode from PRECOG_ENV.

    Returns:
        Environment mode string (dev, test, production)
    """
    return os.getenv("PRECOG_ENV", "dev")


def get_kalshi_mode() -> str:
    """Get Kalshi API mode from KALSHI_MODE.

    Returns:
        Kalshi mode string (demo, live)
    """
    return os.getenv("KALSHI_MODE", "demo")


def is_production() -> bool:
    """Check if running in production environment."""
    return get_env_mode().lower() == "production"


def require_confirmation(message: str, *, default: bool = False) -> bool:
    """Require user confirmation for dangerous operations.

    Args:
        message: Confirmation prompt
        default: Default value if user presses Enter

    Returns:
        True if confirmed, False otherwise
    """
    return typer.confirm(message, default=default)


# =============================================================================
# Client Factories
# =============================================================================


def get_kalshi_client(
    env: EnvMode | None = None,
    *,
    use_demo: bool | None = None,
) -> KalshiClient:
    """Create Kalshi API client with environment awareness.

    Factory function that creates a properly configured KalshiClient
    based on environment settings or explicit parameters.

    Args:
        env: Explicit environment mode (overrides KALSHI_MODE)
        use_demo: If True, force demo mode; if False, force prod mode

    Returns:
        Configured KalshiClient instance

    Raises:
        typer.Exit: If credentials not configured

    Example:
        >>> client = get_kalshi_client()  # Uses KALSHI_MODE env var
        >>> client = get_kalshi_client(env=EnvMode.DEMO)  # Force demo
        >>> client = get_kalshi_client(use_demo=False)  # Force production
    """
    from precog.api_connectors.kalshi_client import KalshiClient

    # Determine demo mode
    if use_demo is not None:
        demo = use_demo
    elif env is not None:
        demo = env in (EnvMode.DEMO,)
    else:
        demo = get_kalshi_mode().lower() == "demo"

    try:
        environment = "demo" if demo else "prod"
        return KalshiClient(environment=environment)
    except ValueError as e:
        cli_error(
            f"Kalshi client configuration error: {e}",
            ExitCode.CONFIG_ERROR,
            hint="Check KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH in .env",
        )


def get_espn_client() -> ESPNClient:
    """Create ESPN API client.

    Returns:
        Configured ESPNClient instance

    Example:
        >>> client = get_espn_client()
        >>> scores = client.get_scoreboard("nfl")
    """
    from precog.api_connectors.espn_client import ESPNClient

    return ESPNClient()


# =============================================================================
# Table Formatting
# =============================================================================


def format_table(
    title: str,
    columns: list[str],
    rows: list[list[Any]],
    *,
    show_header: bool = True,
) -> Table:
    """Create a Rich table for console output.

    Args:
        title: Table title
        columns: Column headers
        rows: Table rows (list of lists)
        show_header: Whether to show header row

    Returns:
        Configured Rich Table object

    Example:
        >>> table = format_table(
        ...     "Markets",
        ...     ["Ticker", "Title", "Status"],
        ...     [["KXNFL-1", "Chiefs vs Raiders", "open"]]
        ... )
        >>> console.print(table)
    """
    table = Table(title=title, show_header=show_header)

    for col in columns:
        table.add_column(col)

    for row in rows:
        table.add_row(*[str(cell) for cell in row])

    return table


def format_decimal(
    value: Decimal | float | int | None,
    *,
    places: int = 4,
) -> str:
    """Format Decimal/numeric value for display.

    Args:
        value: Numeric value to format (Decimal, float, int, or None)
        places: Decimal places to show

    Returns:
        Formatted string or "-" if None
    """
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        value = Decimal(str(value))
    return f"{value:.{places}f}"


def format_currency(
    value: Decimal | float | int | None,
    *,
    symbol: str = "$",
) -> str:
    """Format numeric value as currency.

    Args:
        value: Numeric value to format (Decimal, float, int, or None)
        symbol: Currency symbol

    Returns:
        Formatted currency string or "-" if None
    """
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        value = Decimal(str(value))
    return f"{symbol}{value:.2f}"


# =============================================================================
# Common Options & Arguments
# =============================================================================

# Reusable Typer options for consistency across commands
VerboseOption = typer.Option(
    False,
    "--verbose",
    "-V",
    help="Enable verbose output",
)

DryRunOption = typer.Option(
    False,
    "--dry-run",
    help="Show what would be done without executing",
)

ForceOption = typer.Option(
    False,
    "--force",
    "-f",
    help="Force operation without confirmation",
)

OutputFormatOption = typer.Option(
    "table",
    "--format",
    "-o",
    help="Output format (table, json, csv)",
)


# =============================================================================
# Validation Helpers
# =============================================================================


def validate_sport(sport: str) -> str:
    """Validate sport code.

    Args:
        sport: Sport code to validate

    Returns:
        Normalized sport code (lowercase)

    Raises:
        typer.Exit: If invalid sport
    """
    valid_sports = {"nfl", "nba", "mlb", "nhl", "ncaaf", "ncaab", "wnba"}
    sport_lower = sport.lower()

    if sport_lower not in valid_sports:
        cli_error(
            f"Invalid sport: {sport}",
            ExitCode.USAGE_ERROR,
            hint=f"Valid sports: {', '.join(sorted(valid_sports))}",
        )

    return sport_lower


def validate_seasons(seasons_str: str) -> list[int]:
    """Parse and validate seasons string.

    Accepts formats:
        - Single year: "2023"
        - Range: "2020-2024"
        - List: "2020,2022,2024"

    Args:
        seasons_str: Seasons string to parse

    Returns:
        List of season years

    Raises:
        typer.Exit: If invalid format
    """
    try:
        if "-" in seasons_str and "," not in seasons_str:
            # Range format: "2020-2024"
            start, end = seasons_str.split("-")
            return list(range(int(start), int(end) + 1))
        if "," in seasons_str:
            # List format: "2020,2022,2024"
            return [int(s.strip()) for s in seasons_str.split(",")]
        # Single year: "2023"
        return [int(seasons_str)]
    except ValueError:
        cli_error(
            f"Invalid seasons format: {seasons_str}",
            ExitCode.USAGE_ERROR,
            hint="Use format: 2023, 2020-2024, or 2020,2022,2024",
        )


__all__ = [
    "DryRunOption",
    # Environment
    "EnvMode",
    # Error handling
    "ExitCode",
    "ForceOption",
    "OutputFormatOption",
    # Options
    "VerboseOption",
    "cli_error",
    # Console
    "console",
    "echo",
    "echo_error",
    "echo_info",
    "echo_success",
    "echo_warning",
    "format_currency",
    "format_decimal",
    # Formatting
    "format_table",
    "get_env_mode",
    "get_espn_client",
    # Client factories
    "get_kalshi_client",
    "get_kalshi_mode",
    "is_production",
    "require_confirmation",
    "validate_seasons",
    # Validation
    "validate_sport",
]
