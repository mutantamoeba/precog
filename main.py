"""
Precog CLI - Command-line interface for Kalshi trading operations.

This is the main entry point for all CLI commands using the Typer framework.
Provides commands to fetch and manage Kalshi API data with database persistence.

Usage:
    python main.py fetch-balance          # Fetch account balance
    python main.py fetch-positions        # Fetch open positions
    python main.py fetch-fills            # Fetch trade fills
    python main.py fetch-settlements      # Fetch market settlements
    python main.py --help                 # Show all commands

Educational Notes:
    Typer provides automatic type validation, help generation, and IDE support.
    All commands use type hints for safety and automatic validation.
    Rich library provides beautiful console output with tables and colors.

Related Requirements:
    REQ-CLI-001: CLI Framework with Typer
    REQ-CLI-002: Balance Fetch Command
    REQ-CLI-003: Positions Fetch Command
    REQ-CLI-004: Fills Fetch Command
    REQ-CLI-005: Settlements Fetch Command

Related ADR: ADR-051 (CLI Framework Choice - Typer)
"""

from datetime import datetime, timedelta
from decimal import Decimal

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Local imports
from api_connectors.kalshi_client import KalshiClient
from utils.logger import get_logger

# TODO Phase 1.5: Add database CRUD operations
# from database.connection import get_db_session
# from database.crud_operations import (
#     create_account_balance_record,
#     update_position,
#     create_trade_record,
# )

# Load environment variables
load_dotenv()

# Initialize Typer app
app = typer.Typer(
    name="precog",
    help="Precog CLI - Kalshi trading operations and data management",
    add_completion=False,  # Disable shell completion for now
)

# Initialize Rich console for beautiful output
console = Console()

# Initialize logger
logger = get_logger(__name__)


def get_kalshi_client(environment: str = "demo") -> KalshiClient:
    """
    Create and return a KalshiClient instance.

    Args:
        environment: "demo" or "prod" environment

    Returns:
        Initialized KalshiClient

    Raises:
        typer.Exit: If credentials are missing or invalid
    """
    try:
        client = KalshiClient(environment=environment)
        logger.info(f"Kalshi client initialized for {environment} environment")
        return client
    except ValueError as e:
        console.print(f"[red]Error:[/red] Failed to initialize Kalshi client: {e}")
        console.print("\n[yellow]Please ensure your .env file contains:[/yellow]")
        console.print("  - KALSHI_DEMO_API_KEY or KALSHI_PROD_API_KEY")
        console.print("  - KALSHI_DEMO_KEYFILE or KALSHI_PROD_KEYFILE")
        console.print("  - KALSHI_DEMO_API_BASE or KALSHI_PROD_API_BASE")
        raise typer.Exit(code=1) from e
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(code=1) from e


@app.command()
def fetch_balance(
    environment: str = typer.Option(
        "demo",
        "--env",
        "-e",
        help="Environment to use (demo or prod)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Fetch data but don't write to database",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output for debugging",
    ),
) -> None:
    """
    Fetch account balance from Kalshi API and store in database.

    Retrieves current account balance including available balance and
    pending payouts. Stores the balance snapshot in the account_balance
    table with timestamp.

    Example:
        python main.py fetch-balance --env demo
        python main.py fetch-balance --env prod --verbose
        python main.py fetch-balance --dry-run
    """
    if verbose:
        logger.info("Verbose mode enabled")

    console.print(f"\n[bold cyan]Fetching balance from Kalshi {environment} API...[/bold cyan]")

    # Initialize Kalshi client
    client = get_kalshi_client(environment)

    try:
        # Fetch balance from API (returns Decimal directly)
        balance = client.get_balance()
        logger.info(f"Balance fetched successfully: {balance}")

        # Display balance in a nice table
        table = Table(title=f"Account Balance ({environment.upper()})")
        table.add_column("Field", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        table.add_row("Balance", f"${balance:,.4f}")
        table.add_row("Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        console.print(table)

        # TODO Phase 1.5: Store in database
        if not dry_run:
            console.print(
                "\n[yellow]Note:[/yellow] Database persistence not yet implemented (Phase 1.5)"
            )
            console.print("  Balance fetched successfully from API")
        else:
            console.print("\n[yellow]Dry-run mode:[/yellow] Balance not saved to database")

    except Exception as e:
        logger.error(f"Failed to fetch balance: {e}", exc_info=verbose)
        console.print(f"\n[red]Error:[/red] Failed to fetch balance: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def fetch_positions(
    environment: str = typer.Option(
        "demo",
        "--env",
        "-e",
        help="Environment to use (demo or prod)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Fetch data but don't write to database",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output for debugging",
    ),
) -> None:
    """
    Fetch open positions from Kalshi API and store/update in database.

    Retrieves all current open positions and updates the positions table
    using SCD Type 2 versioning (sets old positions to row_current_ind=False,
    inserts new positions with row_current_ind=True).

    Example:
        python main.py fetch-positions --env demo
        python main.py fetch-positions --env prod --verbose
    """
    if verbose:
        logger.info("Verbose mode enabled")

    console.print(f"\n[bold cyan]Fetching positions from Kalshi {environment} API...[/bold cyan]")

    # Initialize Kalshi client
    client = get_kalshi_client(environment)

    try:
        # Fetch positions from API (returns list directly)
        positions = client.get_positions()
        logger.info(f"Fetched {len(positions)} positions")

        if not positions:
            console.print("\n[yellow]No open positions found[/yellow]")
            return

        # Display positions in a table
        table = Table(title=f"Open Positions ({environment.upper()}) - {len(positions)} total")
        table.add_column("Ticker", style="cyan", no_wrap=True)
        table.add_column("Side", style="magenta")
        table.add_column("Quantity", style="yellow", justify="right")
        table.add_column("Avg Price", style="green", justify="right")
        table.add_column("Total Cost", style="blue", justify="right")

        total_exposure = Decimal("0.0000")

        for position in positions:
            ticker = position.get("ticker", "N/A")
            side = position.get("side", "N/A")
            quantity = position.get("position", 0)
            avg_price = position.get("user_average_price", Decimal("0.0000"))
            total_cost = position.get("total_cost", Decimal("0.0000"))

            total_exposure += total_cost

            table.add_row(
                ticker,
                side.upper(),
                str(quantity),
                f"${avg_price:,.4f}",
                f"${total_cost:,.2f}",
            )

        console.print(table)
        console.print(f"\n[bold]Total Exposure:[/bold] ${total_exposure:,.2f}")

        # TODO Phase 1.5: Store in database with SCD Type 2 versioning
        if not dry_run:
            console.print(
                "\n[yellow]Note:[/yellow] Database persistence not yet implemented (Phase 1.5)"
            )
            console.print(f"  Fetched {len(positions)} positions successfully from API")
        else:
            console.print("\n[yellow]Dry-run mode:[/yellow] Positions not saved to database")

    except Exception as e:
        logger.error(f"Failed to fetch positions: {e}", exc_info=verbose)
        console.print(f"\n[red]Error:[/red] Failed to fetch positions: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def fetch_fills(
    environment: str = typer.Option(
        "demo",
        "--env",
        "-e",
        help="Environment to use (demo or prod)",
    ),
    days: int = typer.Option(
        7,
        "--days",
        "-d",
        help="Number of days of fills to fetch (default: 7)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Fetch data but don't write to database",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output for debugging",
    ),
) -> None:
    """
    Fetch trade fills from Kalshi API and store in database.

    Retrieves trade execution records (fills) and inserts new fills
    into the trades table (append-only, no updates).

    Example:
        python main.py fetch-fills --env demo
        python main.py fetch-fills --env prod --days 30
        python main.py fetch-fills --dry-run
    """
    if verbose:
        logger.info("Verbose mode enabled")

    console.print(
        f"\n[bold cyan]Fetching fills (last {days} days) from Kalshi {environment} API...[/bold cyan]"
    )

    # Initialize Kalshi client
    client = get_kalshi_client(environment)

    try:
        # Calculate timestamp range for days parameter
        # Kalshi uses Unix milliseconds for timestamps
        now = datetime.now()
        min_datetime = now - timedelta(days=days)
        min_ts = int(min_datetime.timestamp() * 1000)  # Convert to milliseconds

        # Fetch fills from API (returns list directly)
        fills = client.get_fills(min_ts=min_ts)
        logger.info(f"Fetched {len(fills)} fills")

        if not fills:
            console.print("\n[yellow]No fills found[/yellow]")
            return

        # Display fills in a table
        table = Table(title=f"Trade Fills ({environment.upper()}) - {len(fills)} total")
        table.add_column("Trade ID", style="cyan", no_wrap=True)
        table.add_column("Ticker", style="magenta")
        table.add_column("Side", style="yellow")
        table.add_column("Action", style="blue")
        table.add_column("Quantity", style="green", justify="right")
        table.add_column("Price", style="green", justify="right")
        table.add_column("Created", style="dim")

        total_volume = 0

        for fill in fills[:10]:  # Show first 10 fills
            trade_id = fill.get("trade_id", "N/A")
            ticker = fill.get("ticker", "N/A")
            side = fill.get("side", "N/A")
            action = fill.get("action", "N/A")
            count = fill.get("count", 0)
            price = fill.get("price", Decimal("0.0000"))
            created = fill.get("created_time", "N/A")

            total_volume += count

            table.add_row(
                trade_id[:12] + "...",  # Truncate trade ID
                ticker,
                side.upper(),
                action.upper(),
                str(count),
                f"${price:,.4f}",
                created[:10] if created != "N/A" else "N/A",  # Date only
            )

        console.print(table)
        if len(fills) > 10:
            console.print(f"[dim]... and {len(fills) - 10} more fills[/dim]")

        console.print(f"\n[bold]Total Volume:[/bold] {total_volume} contracts")

        # TODO Phase 1.5: Store in database (append-only trades table)
        if not dry_run:
            console.print(
                "\n[yellow]Note:[/yellow] Database persistence not yet implemented (Phase 1.5)"
            )
            console.print(f"  Fetched {len(fills)} fills successfully from API")
        else:
            console.print("\n[yellow]Dry-run mode:[/yellow] Fills not saved to database")

    except Exception as e:
        logger.error(f"Failed to fetch fills: {e}", exc_info=verbose)
        console.print(f"\n[red]Error:[/red] Failed to fetch fills: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def fetch_settlements(
    environment: str = typer.Option(
        "demo",
        "--env",
        "-e",
        help="Environment to use (demo or prod)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Fetch data but don't write to database",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output for debugging",
    ),
) -> None:
    """
    Fetch market settlements from Kalshi API and update database.

    Retrieves settled markets and updates the markets and positions
    tables with settlement data and realized P&L.

    Example:
        python main.py fetch-settlements --env demo
        python main.py fetch-settlements --env prod --verbose
    """
    if verbose:
        logger.info("Verbose mode enabled")

    console.print(f"\n[bold cyan]Fetching settlements from Kalshi {environment} API...[/bold cyan]")

    # Initialize Kalshi client
    client = get_kalshi_client(environment)

    try:
        # Fetch settlements from API (returns list directly)
        settlements = client.get_settlements()
        logger.info(f"Fetched {len(settlements)} settlements")

        if not settlements:
            console.print("\n[yellow]No settlements found[/yellow]")
            return

        # Display settlements in a table
        table = Table(
            title=f"Market Settlements ({environment.upper()}) - {len(settlements)} total"
        )
        table.add_column("Ticker", style="cyan", no_wrap=True)
        table.add_column("Result", style="magenta")
        table.add_column("Settlement Value", style="yellow", justify="right")
        table.add_column("Revenue", style="green", justify="right")
        table.add_column("Fees", style="red", justify="right")
        table.add_column("Settled Time", style="dim")

        total_revenue = Decimal("0.0000")
        total_fees = Decimal("0.0000")

        for settlement in settlements:
            ticker = settlement.get("ticker", "N/A")
            result = settlement.get("market_result", "N/A")
            settlement_value = settlement.get("settlement_value", Decimal("0.0000"))
            revenue = settlement.get("revenue", Decimal("0.0000"))
            fees = settlement.get("total_fees", Decimal("0.0000"))
            settled_time = settlement.get("settled_time", "N/A")

            total_revenue += revenue
            total_fees += fees

            table.add_row(
                ticker,
                result.upper(),
                f"${settlement_value:,.4f}",
                f"${revenue:,.2f}",
                f"${fees:,.2f}",
                settled_time[:10] if settled_time != "N/A" else "N/A",  # Date only
            )

        console.print(table)
        console.print(f"\n[bold]Total Revenue:[/bold] ${total_revenue:,.2f}")
        console.print(f"[bold]Total Fees:[/bold] ${total_fees:,.2f}")
        console.print(f"[bold green]Net P&L:[/bold green] ${(total_revenue - total_fees):,.2f}")

        # Store in database (unless dry-run)
        if not dry_run:
            console.print("\n[yellow]Note:[/yellow] Settlement database update not yet implemented")
            console.print("  (Will update markets and positions tables in Phase 1.5)")
        else:
            console.print("\n[yellow]Dry-run mode:[/yellow] Settlements not saved to database")

    except Exception as e:
        logger.error(f"Failed to fetch settlements: {e}", exc_info=verbose)
        console.print(f"\n[red]Error:[/red] Failed to fetch settlements: {e}")
        raise typer.Exit(code=1) from e


def main():
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
