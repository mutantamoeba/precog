"""
Precog CLI - Command-line interface for Kalshi trading operations.

CLI (Command-Line Interface) Explained:
----------------------------------------
Think of the CLI as your "mission control" for talking to the Kalshi API.
Instead of writing Python scripts for every operation, you run simple commands:

```bash
# Before CLI (manual script execution):
$ python fetch_balance_script.py --environment demo --api_key xxx
# ^ Tedious, error-prone, no validation

# After CLI (Typer framework):
$ python main.py fetch-balance --env demo
# ^ Clean, type-safe, automatic validation, beautiful output
```

Why CLI Over Scripts:
---------------------
**1. Type Safety & Validation**
   - Typer uses type hints to validate inputs BEFORE execution
   - Invalid environment? Error shown immediately (no API call wasted)
   - Missing required parameters? Typer shows what's missing

**2. Automatic Help Generation**
   - Every command has --help flag automatically
   - No need to write help text manually
   - IDE autocomplete for parameters

**3. Beautiful Console Output**
   - Rich library provides tables, colors, progress bars
   - Much easier to read than plain print() statements
   - Professional user experience

**4. Consistent Error Handling**
   - Graceful failures with clear error messages
   - Exit codes (0 = success, 1 = error) for automation
   - Verbose mode for debugging

Typer Framework Explained:
---------------------------
Typer converts Python functions into CLI commands automatically.

**Magic Transformation:**
```python
# Python function (before Typer):
def fetch_balance(environment: str, verbose: bool = False):
    # ... implementation ...

# Typer command (after @app.command() decorator):
$ python main.py fetch-balance --env demo --verbose
# Typer automatically:
#   - Converts function arguments to CLI flags
#   - Validates types (environment must be string)
#   - Parses --env demo into environment="demo" parameter
#   - Generates help text from docstring
```

**Type Safety Example:**
```bash
# ✅ Valid command:
$ python main.py fetch-fills --days 30
# Typer validates: days is int, converts "30" string to 30

# ❌ Invalid command:
$ python main.py fetch-fills --days abc
# Typer error: "Invalid value for '--days': 'abc' is not a valid integer"
# ^ Fails BEFORE making API call (saves time and API quota)
```

Rich Console Output - Why Beautiful Tables Matter:
---------------------------------------------------
**Plain print() vs Rich tables:**

```
# ❌ Plain print() - Hard to read:
Balance: 1234.5678
Timestamp: 2024-01-01 14:15:37

Position 1: NFL-KC-YES, YES, 100, 0.5200, 52.00
Position 2: NFL-BUF-YES, NO, 50, 0.4800, 24.00

# ✅ Rich table - Professional and scannable:
╭──────────── Account Balance (DEMO) ────────────╮
│ Field     │ Value                              │
├───────────┼────────────────────────────────────┤
│ Balance   │ $1,234.5678                        │
│ Timestamp │ 2024-01-01 14:15:37                │
╰───────────┴────────────────────────────────────╯

╭──────────── Open Positions (DEMO) - 2 total ───────────╮
│ Ticker      │ Side │ Quantity │ Avg Price │ Total Cost │
├─────────────┼──────┼──────────┼───────────┼────────────┤
│ NFL-KC-YES  │ YES  │      100 │   $0.5200 │    $52.00  │
│ NFL-BUF-YES │ NO   │       50 │   $0.4800 │    $24.00  │
╰─────────────┴──────┴──────────┴───────────┴────────────╯
```

**Why this matters:**
- Easier to scan data visually (columns aligned)
- Colors highlight important info (green = profit, red = loss)
- Professional appearance (looks like real trading software)
- Less mental effort to parse information

Environment Separation Pattern (Demo vs Prod):
-----------------------------------------------
**CRITICAL Safety Feature:**

```python
# Demo environment (safe for testing):
$ python main.py fetch-balance --env demo
# Uses: KALSHI_DEMO_API_KEY, KALSHI_DEMO_KEYFILE
# Trades with FAKE money (Kalshi provides $10,000 demo balance)
# No risk of real financial loss

# Production environment (real money!):
$ python main.py fetch-balance --env prod
# Uses: KALSHI_PROD_API_KEY, KALSHI_PROD_KEYFILE
# Trades with REAL money from your bank account
# ⚠️ Financial risk! Only use when ready to trade for real
```

**Why separate environments:**
1. **Testing**: Develop and test strategies with fake money
2. **Safety**: Prevent accidental real trades during development
3. **Debugging**: Reproduce prod issues in demo without financial risk
4. **Credentials**: Different API keys prevent mixing environments

**Default = Demo:**
All commands default to demo environment for safety. Must explicitly pass
`--env prod` to trade with real money. This prevents "oops, I just spent
$1000 testing my buggy code" disasters.

Dry-Run Pattern (Test Without Side Effects):
---------------------------------------------
Every command supports `--dry-run` flag for testing:

```bash
# ✅ Dry-run mode (safe):
$ python main.py fetch-positions --dry-run
# Fetches data from API ✅
# Shows data in console ✅
# Does NOT write to database ❌
# Useful for: testing API connectivity, viewing data, debugging

# ❌ Normal mode (has side effects):
$ python main.py fetch-positions
# Fetches data from API ✅
# Shows data in console ✅
# Writes to database ✅ (creates rows, updates timestamps)
```

**When to use dry-run:**
- Testing new commands before trusting them
- Viewing current API data without persisting
- Debugging API responses without polluting database
- Running in CI/CD to verify API connectivity

Error Handling Pattern:
-----------------------
**Graceful failures with clear actionable messages:**

```python
# If credentials missing:
$ python main.py fetch-balance
[ERROR] Failed to initialize Kalshi client: Missing API credentials

[YELLOW] Please ensure your .env file contains:
  - KALSHI_DEMO_API_KEY or KALSHI_PROD_API_KEY
  - KALSHI_DEMO_KEYFILE or KALSHI_PROD_KEYFILE
  - KALSHI_DEMO_API_BASE or KALSHI_PROD_API_BASE

Exit Code: 1

# If API call fails:
$ python main.py fetch-positions
[ERROR] Failed to fetch positions: HTTP 401 Unauthorized

Exit Code: 1
```

**Exit codes for automation:**
- `0` = Success (all operations completed)
- `1` = Error (credential failure, API error, network timeout)

**Use in scripts:**
```bash
#!/bin/bash
python main.py fetch-balance --env demo
if [ $? -ne 0 ]; then
    echo "Balance fetch failed! Aborting."
    exit 1
fi
# Continue with other commands...
```

Verbose Mode for Debugging:
----------------------------
**Every command supports --verbose flag:**

```bash
# Normal mode (quiet):
$ python main.py fetch-fills
Fetching fills from Kalshi demo API...
[Table with 10 fills displayed]

# Verbose mode (detailed):
$ python main.py fetch-fills --verbose
[2024-01-01 14:15:37] INFO: Verbose mode enabled
[2024-01-01 14:15:37] INFO: Kalshi client initialized for demo environment
[2024-01-01 14:15:38] INFO: Fetched 23 fills
[Table with 10 fills displayed]

# Verbose + error (shows full stack trace):
$ python main.py fetch-fills --verbose
[2024-01-01 14:15:37] INFO: Verbose mode enabled
[2024-01-01 14:15:37] ERROR: Failed to fetch fills: Connection timeout
Traceback (most recent call last):
  File "api_connectors/kalshi_client.py", line 123, in get_fills
    response = requests.get(...)
  ...
```

**When to use verbose:**
- Debugging API errors (see full stack trace)
- Understanding command execution flow
- Logging detailed info for troubleshooting
- Submitting bug reports (include verbose output)

Database Integration (Phase 1.5 - Future):
-------------------------------------------
**Current State (Phase 1):**
- Commands fetch data from Kalshi API ✅
- Commands display data in Rich tables ✅
- Commands do NOT persist to database ❌

**Future State (Phase 1.5):**
```python
# fetch-balance will:
1. Fetch balance from API
2. Insert into account_balance table (append-only)
3. Show "Saved to database" confirmation

# fetch-positions will:
1. Fetch positions from API
2. Update positions table using SCD Type 2 versioning
   - Mark old positions as row_current_ind = FALSE
   - Insert new positions as row_current_ind = TRUE
3. Show "Updated X positions in database"

# fetch-fills will:
1. Fetch fills from API (last N days)
2. Insert NEW fills into trades table (append-only)
3. Skip fills already in database (deduplicate by trade_id)
4. Show "Inserted X new fills"

# fetch-settlements will:
1. Fetch settlements from API
2. Update markets table status to 'settled'
3. Update positions table with realized P&L
4. Insert settlement records
5. Show "Settled X markets, realized P&L: $XXX"
```

**Why deferred to Phase 1.5:**
API connectivity and CLI commands are higher priority than persistence.
Database integration requires CRUD operations and versioning logic (complex).
Better to get API working first, then add persistence layer.

Command-Specific Usage Examples:
---------------------------------

**1. fetch-balance - Check account balance**
```bash
# Demo environment (default):
$ python main.py fetch-balance
$ python main.py fetch-balance --env demo

# Production environment:
$ python main.py fetch-balance --env prod

# Dry-run (no database write):
$ python main.py fetch-balance --dry-run

# Verbose mode (debugging):
$ python main.py fetch-balance --verbose
```

**2. fetch-positions - View open positions**
```bash
# Basic usage:
$ python main.py fetch-positions

# Production:
$ python main.py fetch-positions --env prod

# Dry-run + verbose:
$ python main.py fetch-positions --dry-run --verbose
```

**3. fetch-fills - Get trade history**
```bash
# Last 7 days (default):
$ python main.py fetch-fills

# Last 30 days:
$ python main.py fetch-fills --days 30

# Short flag:
$ python main.py fetch-fills -d 14

# Production fills:
$ python main.py fetch-fills --env prod --days 90
```

**4. fetch-settlements - Get settled markets**
```bash
# Basic usage:
$ python main.py fetch-settlements

# Production settlements:
$ python main.py fetch-settlements --env prod

# Dry-run (view without database update):
$ python main.py fetch-settlements --dry-run
```

**5. Help for any command**
```bash
# List all commands:
$ python main.py --help

# Help for specific command:
$ python main.py fetch-balance --help
$ python main.py fetch-fills --help
```

Performance Considerations:
---------------------------
**API Rate Limits:**
- Kalshi demo: ~100 requests/minute
- Commands make 1 API call each (efficient)
- Verbose logging adds <1ms overhead (negligible)

**Console Output Speed:**
- Rich tables render in ~5-10ms (unnoticeable to user)
- Faster than plain print() for large tables (buffered rendering)

**Database Writes (Phase 1.5):**
- Bulk inserts for fills (1 transaction for N fills, not N transactions)
- SCD Type 2 updates use 2 queries (UPDATE old, INSERT new)
- Connection pooling reuses connections (no new connection per command)

Common Mistakes to Avoid:
--------------------------
```bash
# ❌ WRONG - Using prod without thinking:
$ python main.py fetch-balance --env prod
# ^ ARE YOU SURE? This uses REAL credentials and REAL money!

# ✅ CORRECT - Always start with demo:
$ python main.py fetch-balance
# ^ Safe default (demo environment)

# ❌ WRONG - Forgetting to check exit code in scripts:
python main.py fetch-balance
python main.py fetch-positions  # Runs even if balance fetch failed!

# ✅ CORRECT - Check exit codes:
python main.py fetch-balance || exit 1
python main.py fetch-positions || exit 1
# ^ Stops script on first error

# ❌ WRONG - Running without --dry-run for first time:
$ python main.py fetch-settlements  # Unknown consequences!

# ✅ CORRECT - Test with dry-run first:
$ python main.py fetch-settlements --dry-run  # See what it does
$ python main.py fetch-settlements             # Then run for real
```

Reference: docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md (Kalshi API details)
Related Requirements:
    REQ-CLI-001: CLI Framework with Typer
    REQ-CLI-002: Balance Fetch Command
    REQ-CLI-003: Positions Fetch Command
    REQ-CLI-004: Fills Fetch Command
    REQ-CLI-005: Settlements Fetch Command
    REQ-OBSERV-001: Structured Logging (verbose mode uses this)
Related ADR: ADR-051 (CLI Framework Choice - Typer)
Related Guide: docs/guides/CONFIGURATION_GUIDE_V3.1.md (Environment variables)
"""

from datetime import datetime, timedelta
from decimal import Decimal

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Local imports
from api_connectors.kalshi_client import KalshiClient

# Phase 1.5: Database CRUD operations
from database.crud_operations import (
    create_market,
    create_settlement,
    get_current_market,
    update_account_balance_with_versioning,
    update_market_with_versioning,
)
from utils.logger import get_logger

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

        # Phase 1.5: Store balance in database
        if not dry_run:
            try:
                platform_id = "kalshi"  # Hardcoded for Phase 1 (single platform)
                balance_id = update_account_balance_with_versioning(
                    platform_id=platform_id, new_balance=balance, currency="USD"
                )
                logger.info(f"Balance stored in database (balance_id: {balance_id})")
                console.print(
                    f"\n[green]✓ Success:[/green] Balance saved to database (ID: {balance_id})"
                )
            except Exception as db_error:
                logger.error(f"Failed to save balance to database: {db_error}", exc_info=verbose)
                console.print(
                    f"\n[yellow]Warning:[/yellow] Balance fetched but failed to save to database: {db_error}"
                )
                console.print("  Balance fetched successfully from API but not persisted")
        else:
            console.print("\n[yellow]Dry-run mode:[/yellow] Balance not saved to database")

    except Exception as e:
        logger.error(f"Failed to fetch balance: {e}", exc_info=verbose)
        console.print(f"\n[red]Error:[/red] Failed to fetch balance: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def fetch_markets(
    series_ticker: str | None = typer.Option(
        None,
        "--series",
        "-s",
        help="Filter by series ticker (e.g., 'KXNFLGAME')",
    ),
    event_ticker: str | None = typer.Option(
        None,
        "--event",
        "-e",
        help="Filter by event ticker (e.g., 'KXNFLGAME-25OCT05-NEBUF')",
    ),
    limit: int = typer.Option(
        100,
        "--limit",
        "-l",
        help="Maximum number of markets to fetch (default 100, max 200)",
    ),
    environment: str = typer.Option(
        "demo",
        "--env",
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
    Fetch available markets from Kalshi API and display/store in database.

    Retrieves markets with current pricing data. Can filter by series or event
    ticker to narrow results.

    Example:
        python main.py fetch-markets --env demo
        python main.py fetch-markets --series KXNFLGAME --limit 50
        python main.py fetch-markets --event KXNFLGAME-25OCT05-NEBUF --verbose
    """
    if verbose:
        logger.info("Verbose mode enabled")

    console.print(f"\n[bold cyan]Fetching markets from Kalshi {environment} API...[/bold cyan]")

    # Initialize Kalshi client
    client = get_kalshi_client(environment)

    try:
        # Fetch markets from API (returns list of ProcessedMarketData)
        markets = client.get_markets(
            series_ticker=series_ticker,
            event_ticker=event_ticker,
            limit=limit,
        )
        logger.info(f"Fetched {len(markets)} markets")

        if not markets:
            console.print("\n[yellow]No markets found[/yellow]")
            return

        # Display markets in a table
        filter_info = []
        if series_ticker:
            filter_info.append(f"Series: {series_ticker}")
        if event_ticker:
            filter_info.append(f"Event: {event_ticker}")
        filter_str = f" ({', '.join(filter_info)})" if filter_info else ""

        table = Table(
            title=f"Available Markets ({environment.upper()}){filter_str} - {len(markets)} total"
        )
        table.add_column("Ticker", style="cyan", no_wrap=True)
        table.add_column("Title", style="white", overflow="fold")
        table.add_column("Status", style="magenta")
        table.add_column("Yes Bid", style="green", justify="right")
        table.add_column("Yes Ask", style="yellow", justify="right")
        table.add_column("Volume", style="blue", justify="right")
        table.add_column("Last Price", style="dim", justify="right")

        for market in markets:
            ticker = market.get("ticker", "N/A")
            title = market.get("title", "N/A")
            status = market.get("status", "N/A")
            yes_bid = market.get("yes_bid", Decimal("0.0000"))
            yes_ask = market.get("yes_ask", Decimal("0.0000"))
            volume = market.get("volume", 0)
            last_price = market.get("last_price", Decimal("0.0000"))

            # Truncate title if too long
            if len(title) > 50:
                title = title[:47] + "..."

            table.add_row(
                ticker,
                title,
                status.upper(),
                f"${yes_bid:,.4f}",
                f"${yes_ask:,.4f}",
                f"{volume:,}",
                f"${last_price:,.4f}",
            )

        console.print(table)

        # Phase 1.5: Store markets in database
        if not dry_run:
            try:
                platform_id = "kalshi"  # Hardcoded for Phase 1 (single platform)
                created_count = 0
                updated_count = 0
                error_count = 0

                for market in markets:
                    try:
                        # Prepare metadata (extra fields not in main table)
                        metadata = {
                            "subtitle": market.get("subtitle"),
                            "series_ticker": market.get("series_ticker"),
                            "open_time": market.get("open_time"),
                            "close_time": market.get("close_time"),
                            "expiration_time": market.get("expiration_time"),
                            "can_close_early": market.get("can_close_early"),
                            "result": market.get("result"),
                            "liquidity": market.get("liquidity"),
                        }

                        # Try to update first (market may already exist)
                        try:
                            update_market_with_versioning(
                                ticker=market["ticker"],
                                yes_price=market["yes_bid"],  # Use bid as current price
                                no_price=market["no_bid"],
                                status=market["status"],
                                volume=market.get("volume"),
                                open_interest=market.get("open_interest"),
                                market_metadata=metadata,
                            )
                            updated_count += 1
                        except ValueError:
                            # Market doesn't exist, create it
                            create_market(
                                platform_id=platform_id,
                                event_id=market["event_ticker"],
                                external_id=market["ticker"],  # Use ticker as external_id
                                ticker=market["ticker"],
                                title=market["title"],
                                yes_price=market["yes_bid"],
                                no_price=market["no_bid"],
                                market_type="binary",
                                status=market["status"],
                                volume=market.get("volume"),
                                open_interest=market.get("open_interest"),
                                spread=market["yes_ask"] - market["yes_bid"],  # Calculate spread
                                metadata=metadata,
                            )
                            created_count += 1
                    except Exception as market_error:
                        logger.error(
                            f"Failed to save market {market.get('ticker')}: {market_error}"
                        )
                        error_count += 1

                logger.info(
                    f"Markets saved: {created_count} created, {updated_count} updated, {error_count} errors"
                )
                console.print(
                    f"\n[green]✓ Success:[/green] {created_count} markets created, {updated_count} updated"
                )
                if error_count > 0:
                    console.print(f"[yellow]Warning:[/yellow] {error_count} markets failed to save")

            except Exception as db_error:
                logger.error(f"Failed to save markets to database: {db_error}", exc_info=verbose)
                console.print(
                    f"\n[yellow]Warning:[/yellow] Markets fetched but failed to save to database: {db_error}"
                )
        else:
            console.print("\n[yellow]Dry-run mode:[/yellow] Markets not saved to database")

    except Exception as e:
        logger.error(f"Failed to fetch markets: {e}", exc_info=verbose)
        console.print(f"\n[red]Error:[/red] Failed to fetch markets: {e}")
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

        # Phase 1.5+: Store positions in database (DEFERRED)
        # Why deferred: Positions table requires strategy_id and model_id for trade attribution
        # Setup needed:
        #   1. Create "manual" strategy record (for API-fetched positions not created by our system)
        #   2. Create "manual" model record (placeholder for positions without ensemble predictions)
        #   3. Add lookup logic: ticker → market_id
        #   4. Use create_position() with strategy_id=1 (manual), model_id=1 (manual)
        # Target: Phase 1.5+ (after strategy/model infrastructure exists)
        if not dry_run:
            console.print(
                "\n[yellow]Note:[/yellow] Database persistence deferred to Phase 1.5+ (requires strategy/model setup)"
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

        # Phase 1.5+: Store fills in database (DEFERRED)
        # Why deferred: Fills (trades) require position_id for linking to open positions
        # Setup needed:
        #   1. Positions must exist in database first (see fetch-positions deferral above)
        #   2. Add lookup logic: ticker + side → position_id
        #   3. Use create_trade() with proper position_id linking
        #   4. Handle deduplication (don't insert same trade_id twice)
        # Note: Trades table is append-only (no versioning), but requires position linkage
        # Target: Phase 1.5+ (after position infrastructure exists)
        if not dry_run:
            console.print(
                "\n[yellow]Note:[/yellow] Database persistence deferred to Phase 1.5+ (requires position records)"
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

        # Phase 1.5: Store settlements in database and update market status
        if not dry_run:
            try:
                platform_id = "kalshi"  # Hardcoded for Phase 1 (single platform)
                settlement_count = 0
                market_update_count = 0
                error_count = 0

                for settlement in settlements:
                    try:
                        settlement_ticker = settlement.get("ticker")
                        if not settlement_ticker:
                            logger.warning("Settlement missing ticker, skipping")
                            error_count += 1
                            continue

                        # Get market_id from ticker
                        market = get_current_market(settlement_ticker)
                        if not market:
                            logger.warning(
                                f"Market not found for ticker {settlement_ticker}, skipping settlement"
                            )
                            error_count += 1
                            continue

                        market_id = market["market_id"]

                        # Create settlement record
                        create_settlement(
                            market_id=market_id,
                            platform_id=platform_id,
                            outcome=settlement["market_result"],  # "yes" or "no"
                            payout=settlement["settlement_value"],
                        )
                        settlement_count += 1

                        # Update market status to "settled"
                        update_market_with_versioning(
                            ticker=settlement_ticker,
                            status="settled",
                        )
                        market_update_count += 1

                    except Exception as settlement_error:
                        logger.error(
                            f"Failed to process settlement for {settlement_ticker}: {settlement_error}"
                        )
                        error_count += 1

                logger.info(
                    f"Settlements processed: {settlement_count} settlements created, {market_update_count} markets updated, {error_count} errors"
                )
                console.print(
                    f"\n[green]✓ Success:[/green] {settlement_count} settlements saved, {market_update_count} markets updated to 'settled'"
                )
                if error_count > 0:
                    console.print(
                        f"[yellow]Warning:[/yellow] {error_count} settlements failed to process"
                    )

            except Exception as db_error:
                logger.error(
                    f"Failed to save settlements to database: {db_error}", exc_info=verbose
                )
                console.print(
                    f"\n[yellow]Warning:[/yellow] Settlements fetched but failed to save to database: {db_error}"
                )
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
