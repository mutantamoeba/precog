"""
Kalshi Market Operations CLI Commands.

Provides commands for interacting with the Kalshi prediction market API.

Commands:
    balance     - Fetch and display account balance
    markets     - List available markets with pricing
    positions   - Show open positions
    fills       - Show trade/fill history
    settlements - Show settled markets

Usage:
    precog kalshi balance [--env demo|prod]
    precog kalshi markets [--series TICKER] [--limit N]
    precog kalshi positions [--env demo|prod]
    precog kalshi fills [--days N]
    precog kalshi settlements [--days N]

Related:
    - Issue #204: CLI Refactor
    - docs/guides/KALSHI_CLIENT_USER_GUIDE_V1.0.md
    - docs/planning/CLI_REFACTOR_COMPREHENSIVE_PLAN_V1.0.md Section 4.2.1
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import typer
from rich.table import Table

from precog.cli._common import (
    ExitCode,
    cli_error,
    console,
    echo_success,
    format_currency,
    format_decimal,
    get_kalshi_client,
)

app = typer.Typer(
    name="kalshi",
    help="Kalshi market operations (balance, markets, positions, fills)",
    no_args_is_help=True,
)


@app.command()
def balance(
    env: str = typer.Option(
        "demo",
        "--env",
        "-e",
        help="Environment (demo or prod)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Fetch data but don't write to database",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose output",
    ),
) -> None:
    """Fetch account balance from Kalshi API.

    Retrieves current account balance including available balance and
    pending payouts. Optionally stores the balance snapshot in the database.

    Examples:
        precog kalshi balance
        precog kalshi balance --env prod
        precog kalshi balance --dry-run --verbose
    """
    console.print(f"\n[bold cyan]Fetching balance from Kalshi {env.upper()} API...[/bold cyan]")

    use_demo = env.lower() == "demo"
    client = get_kalshi_client(use_demo=use_demo)

    try:
        # Fetch balance from API
        balance_value = client.get_balance()

        if balance_value is None:
            console.print(
                "\n[yellow]Warning:[/yellow] Balance endpoint unavailable (DEMO API instability)"
            )
            console.print("  Use --env prod for production balance")
            raise typer.Exit(code=1)

        # Display balance
        table = Table(title=f"Account Balance ({env.upper()})")
        table.add_column("Field", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        table.add_row("Balance", f"${balance_value:,.4f}")
        table.add_row("Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        console.print(table)

        # Store in database (Phase 1.5+)
        if not dry_run:
            try:
                from precog.database.crud_operations import update_account_balance_with_versioning

                balance_id = update_account_balance_with_versioning(
                    platform_id="kalshi",
                    new_balance=balance_value,
                    currency="USD",
                )
                echo_success(f"Balance saved to database (ID: {balance_id})")
            except ImportError:
                if verbose:
                    console.print("[dim]Database integration not available[/dim]")
            except Exception as db_error:
                console.print(f"[yellow]Warning:[/yellow] Failed to save to database: {db_error}")
        else:
            console.print("\n[yellow]Dry-run mode:[/yellow] Balance not saved to database")

    except typer.Exit:
        raise
    except Exception as e:
        cli_error(
            f"Failed to fetch balance: {e}",
            ExitCode.NETWORK_ERROR,
            hint="Check API credentials and network connection",
        )


@app.command()
def markets(
    series: str | None = typer.Option(
        None,
        "--series",
        "-s",
        help="Filter by series ticker (e.g., 'KXNFLGAME')",
    ),
    event: str | None = typer.Option(
        None,
        "--event",
        "-e",
        help="Filter by event ticker",
    ),
    limit: int = typer.Option(
        100,
        "--limit",
        "-l",
        help="Maximum markets to fetch (1-200)",
    ),
    env: str = typer.Option(
        "demo",
        "--env",
        help="Environment (demo or prod)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose output",
    ),
) -> None:
    """List available markets from Kalshi API.

    Retrieves markets with current pricing data. Can filter by series
    or event ticker to narrow results.

    Examples:
        precog kalshi markets
        precog kalshi markets --series KXNFLGAME --limit 50
        precog kalshi markets --event KXNFLGAME-25OCT05-NEBUF
    """
    # Validate limit
    if limit < 1 or limit > 200:
        cli_error(
            f"Limit must be between 1 and 200 (got {limit})",
            ExitCode.USAGE_ERROR,
        )

    console.print(f"\n[bold cyan]Fetching markets from Kalshi {env.upper()} API...[/bold cyan]")

    use_demo = env.lower() == "demo"
    client = get_kalshi_client(use_demo=use_demo)

    try:
        markets_data = client.get_markets(
            series_ticker=series,
            event_ticker=event,
            limit=limit,
        )

        if not markets_data:
            console.print("\n[yellow]No markets found[/yellow]")
            return

        # Build filter info for title
        filter_info = []
        if series:
            filter_info.append(f"Series: {series}")
        if event:
            filter_info.append(f"Event: {event}")
        filter_str = f" ({', '.join(filter_info)})" if filter_info else ""

        table = Table(
            title=f"Available Markets ({env.upper()}){filter_str} - {len(markets_data)} total"
        )
        table.add_column("Ticker", style="cyan", no_wrap=True)
        table.add_column("Title", style="white", overflow="fold", max_width=40)
        table.add_column("Status", style="magenta")
        table.add_column("Yes Bid", style="green", justify="right")
        table.add_column("Yes Ask", style="yellow", justify="right")
        table.add_column("Volume", style="blue", justify="right")

        for market in markets_data:
            ticker = market.get("ticker", "N/A")
            title = market.get("title", "N/A")
            status = market.get("status", "N/A")
            yes_bid = market.get("yes_bid", Decimal("0"))
            yes_ask = market.get("yes_ask", Decimal("0"))
            volume = market.get("volume", 0)

            # Truncate title if needed
            if len(title) > 40:
                title = title[:37] + "..."

            table.add_row(
                ticker,
                title,
                status,
                format_decimal(yes_bid),
                format_decimal(yes_ask),
                str(volume),
            )

        console.print(table)

        if verbose:
            console.print(f"\n[dim]Fetched {len(markets_data)} markets[/dim]")

    except Exception as e:
        cli_error(
            f"Failed to fetch markets: {e}",
            ExitCode.NETWORK_ERROR,
        )


@app.command()
def positions(
    env: str = typer.Option(
        "demo",
        "--env",
        "-e",
        help="Environment (demo or prod)",
    ),
    ticker: str | None = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Filter by market ticker",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose output",
    ),
) -> None:
    """Show open positions from Kalshi API.

    Retrieves current positions with P&L information.

    Examples:
        precog kalshi positions
        precog kalshi positions --env prod
        precog kalshi positions --ticker KXNFLGAME-25OCT05
    """
    console.print(f"\n[bold cyan]Fetching positions from Kalshi {env.upper()} API...[/bold cyan]")

    use_demo = env.lower() == "demo"
    client = get_kalshi_client(use_demo=use_demo)

    try:
        positions_data = client.get_positions(ticker=ticker)

        if not positions_data:
            console.print("\n[yellow]No open positions[/yellow]")
            return

        table = Table(title=f"Open Positions ({env.upper()}) - {len(positions_data)} total")
        table.add_column("Ticker", style="cyan", no_wrap=True)
        table.add_column("Side", style="white")
        table.add_column("Quantity", style="blue", justify="right")
        table.add_column("Avg Price", style="green", justify="right")
        table.add_column("Market Price", style="yellow", justify="right")
        table.add_column("Unrealized P&L", justify="right")

        for position in positions_data:
            pos_ticker = position.get("ticker", "N/A")
            side = "YES" if position.get("position", 0) > 0 else "NO"
            quantity = abs(int(position.get("position", 0)))
            avg_price_raw = position.get("average_price", Decimal("0"))
            avg_price = Decimal(str(avg_price_raw)) if avg_price_raw else Decimal("0")
            market_price_raw = position.get("market_price", Decimal("0"))
            market_price = Decimal(str(market_price_raw)) if market_price_raw else Decimal("0")

            # Calculate unrealized P&L
            if side == "YES":
                pnl = (market_price - avg_price) * quantity
            else:
                pnl = (avg_price - market_price) * quantity

            pnl_style = "green" if pnl >= 0 else "red"
            pnl_str = f"[{pnl_style}]{format_currency(pnl)}[/{pnl_style}]"

            table.add_row(
                pos_ticker,
                side,
                str(quantity),
                format_decimal(avg_price),
                format_decimal(market_price),
                pnl_str,
            )

        console.print(table)

    except Exception as e:
        cli_error(
            f"Failed to fetch positions: {e}",
            ExitCode.NETWORK_ERROR,
        )


@app.command()
def fills(
    days: int = typer.Option(
        7,
        "--days",
        "-d",
        help="Number of days of history to fetch",
    ),
    ticker: str | None = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Filter by market ticker",
    ),
    env: str = typer.Option(
        "demo",
        "--env",
        "-e",
        help="Environment (demo or prod)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose output",
    ),
) -> None:
    """Show trade/fill history from Kalshi API.

    Retrieves recent fills (executed trades) with pricing and fees.

    Examples:
        precog kalshi fills
        precog kalshi fills --days 30
        precog kalshi fills --ticker KXNFLGAME-25OCT05
    """
    console.print(f"\n[bold cyan]Fetching fills from Kalshi {env.upper()} API...[/bold cyan]")

    use_demo = env.lower() == "demo"
    client = get_kalshi_client(use_demo=use_demo)

    try:
        fills_data = client.get_fills(ticker=ticker)

        if not fills_data:
            console.print("\n[yellow]No fills found[/yellow]")
            return

        table = Table(title=f"Trade History ({env.upper()}) - {len(fills_data)} fills")
        table.add_column("Ticker", style="cyan", no_wrap=True)
        table.add_column("Side", style="white")
        table.add_column("Quantity", style="blue", justify="right")
        table.add_column("Price", style="green", justify="right")
        table.add_column("Cost", style="yellow", justify="right")
        table.add_column("Time", style="dim")

        for fill in fills_data:
            fill_ticker = fill.get("ticker", "N/A")
            side = fill.get("side", "N/A")
            count = fill.get("count", 0)
            price_raw = fill.get("price", Decimal("0"))
            price = Decimal(str(price_raw)) if price_raw else Decimal("0")
            cost_raw = fill.get("cost", Decimal("0"))
            cost = Decimal(str(cost_raw)) if cost_raw else Decimal("0")
            created_time = fill.get("created_time", "N/A")

            # Format timestamp
            if isinstance(created_time, str) and created_time != "N/A":
                try:
                    dt = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
                    time_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    time_str = created_time[:16] if len(created_time) > 16 else created_time
            else:
                time_str = str(created_time)

            table.add_row(
                fill_ticker,
                side.upper() if side else "N/A",
                str(count),
                format_decimal(price),
                format_currency(cost),
                time_str,
            )

        console.print(table)

    except Exception as e:
        cli_error(
            f"Failed to fetch fills: {e}",
            ExitCode.NETWORK_ERROR,
        )


@app.command()
def settlements(
    days: int = typer.Option(
        30,
        "--days",
        "-d",
        help="Number of days of history to fetch",
    ),
    env: str = typer.Option(
        "demo",
        "--env",
        "-e",
        help="Environment (demo or prod)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose output",
    ),
) -> None:
    """Show settled markets from Kalshi API.

    Retrieves markets that have settled with final results.

    Examples:
        precog kalshi settlements
        precog kalshi settlements --days 90
        precog kalshi settlements --env prod
    """
    console.print(f"\n[bold cyan]Fetching settlements from Kalshi {env.upper()} API...[/bold cyan]")

    use_demo = env.lower() == "demo"
    client = get_kalshi_client(use_demo=use_demo)

    try:
        settlements_data = client.get_settlements()

        if not settlements_data:
            console.print("\n[yellow]No settlements found[/yellow]")
            return

        table = Table(title=f"Settled Markets ({env.upper()}) - {len(settlements_data)} total")
        table.add_column("Ticker", style="cyan", no_wrap=True)
        table.add_column("Result", style="white")
        table.add_column("Revenue", style="green", justify="right")
        table.add_column("Settled At", style="dim")

        for settlement in settlements_data:
            ticker = settlement.get("ticker", "N/A")
            result = str(settlement.get("result", "N/A"))
            revenue_raw = settlement.get("revenue", Decimal("0"))
            revenue = Decimal(str(revenue_raw)) if revenue_raw else Decimal("0")
            settled_time = settlement.get("settled_time", "N/A")

            # Format result with color
            result_str = (
                "[green]YES[/green]"
                if result == "yes"
                else "[red]NO[/red]"
                if result == "no"
                else result
            )

            # Format timestamp
            if isinstance(settled_time, str) and settled_time != "N/A":
                try:
                    dt = datetime.fromisoformat(settled_time.replace("Z", "+00:00"))
                    time_str = dt.strftime("%Y-%m-%d")
                except Exception:
                    time_str = settled_time[:10] if len(settled_time) > 10 else settled_time
            else:
                time_str = str(settled_time)

            table.add_row(
                ticker,
                result_str,
                format_currency(revenue),
                time_str,
            )

        console.print(table)

    except Exception as e:
        cli_error(
            f"Failed to fetch settlements: {e}",
            ExitCode.NETWORK_ERROR,
        )
