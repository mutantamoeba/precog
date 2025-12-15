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

import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, NoReturn

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Local imports
from precog.api_connectors.kalshi_client import KalshiClient
from precog.config.environment import (
    AppEnvironment,
    MarketMode,
    get_app_environment,
    get_market_mode,
    load_environment_config,
)

# Phase 1.5: Database CRUD operations
from precog.database.crud_operations import (
    create_market,
    create_settlement,
    get_current_market,
    update_account_balance_with_versioning,
    update_market_with_versioning,
)

# Phase 2.5: Scheduler components
from precog.schedulers import (
    KalshiMarketPoller,
    MarketUpdater,
    ServiceSupervisor,
    create_supervisor,
)
from precog.utils.logger import get_logger

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


@app.callback()
def main_callback(
    app_env: str | None = typer.Option(
        None,
        "--app-env",
        help="Override application environment (dev, test, staging, prod). Sets PRECOG_ENV.",
        envvar="PRECOG_ENV",
    ),
) -> None:
    """
    Precog CLI - Kalshi trading operations and data management.

    Global Options:
        --app-env: Override the application environment (database selection).
                   Valid values: dev, test, staging, prod.
                   Can also be set via PRECOG_ENV environment variable.

    The CLI uses a two-axis environment model:
        1. Application Environment (--app-env / PRECOG_ENV): Controls which database
           to use (precog_dev, precog_test, precog_staging, precog_prod).
        2. Market Mode (KALSHI_MODE): Controls API endpoints (demo/live).

    Safety:
        - Test environment NEVER uses live API (blocked at startup)
        - Production environment ALWAYS uses live API (enforced)
        - Dev/staging with live API shows warning

    Reference: docs/guides/ENVIRONMENT_CONFIGURATION_GUIDE_V1.0.md
    Related: Issue #202 (Two-Axis Environment Configuration)
    """
    if app_env is not None:
        # Override PRECOG_ENV in current process
        # This affects all subsequent environment lookups
        try:
            # Validate the environment value
            validated_env = AppEnvironment.from_string(app_env)
            os.environ["PRECOG_ENV"] = validated_env.value
            logger.debug(f"Application environment set to: {validated_env.value}")
        except ValueError:
            cli_error(
                f"Invalid --app-env value: '{app_env}'",
                hint="Valid options: dev, test, staging, prod",
            )


def cli_error(message: str, hint: str | None = None) -> NoReturn:
    """
    Display error message and exit with code 1.

    Uses NoReturn type hint to indicate this function never returns normally.
    This helps type checkers understand control flow in error handling.

    Args:
        message: Error message to display
        hint: Optional hint for fixing the error

    Raises:
        typer.Exit: Always raises with code=1

    Example:
        >>> if not api_key:
        ...     cli_error("API key not found", "Set KALSHI_API_KEY in .env")

    Reference: Issue #68 (NoReturn Type Hint for Exit Paths)
    """
    console.print(f"[red]Error:[/red] {message}")
    if hint:
        console.print(f"[dim]Hint:[/dim] {hint}")
    raise typer.Exit(code=1)


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
        if balance is None:
            console.print(
                "\n[yellow]Warning:[/yellow] Balance endpoint unavailable (DEMO API instability)"
            )
            console.print("  Use --environment prod for production balance")
            raise typer.Exit(code=1)
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
                    f"\n[green][OK] Success:[/green] Balance saved to database (ID: {balance_id})"
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
        # Security: Don't expose internal error details to user (Issue #42)
        console.print("\n[red]Error:[/red] Failed to fetch balance from API")
        if verbose:
            console.print(f"[dim]Details: {e}[/dim]")
        else:
            console.print("[dim]Use --verbose for error details[/dim]")
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

    # Validate limit parameter (Kalshi API maximum is 200)
    if limit < 1:
        console.print("[red]Error:[/red] Limit must be at least 1")
        console.print("[dim]Tip:[/dim] Use --limit between 1 and 200")
        raise typer.Exit(code=1)

    if limit > 200:
        console.print("[red]Error:[/red] Limit cannot exceed 200 (Kalshi API maximum)")
        console.print("[dim]Tip:[/dim] Use --limit 200 for maximum results")
        raise typer.Exit(code=1)

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

                # Map Kalshi API status to Precog database status
                # Kalshi API: "active", "finalized", "closed", etc.
                # Precog DB: "open", "closed", "settled", "halted" (markets_status_check constraint)
                # Reference: ADR-002, DATABASE_SCHEMA_SUMMARY_V1.12.md
                kalshi_status_mapping: dict[str, str] = {
                    "active": "open",  # Live/tradable market
                    "finalized": "settled",  # Market has settled with result
                    "closed": "closed",  # Market closed for trading
                    "halted": "halted",  # Trading temporarily halted
                }

                for market in markets:
                    try:
                        # Map Kalshi status to Precog database status
                        kalshi_status = market["status"]
                        mapped_status = kalshi_status_mapping.get(kalshi_status, kalshi_status)
                        if kalshi_status != mapped_status:
                            logger.debug(
                                f"Mapped Kalshi status '{kalshi_status}' -> '{mapped_status}' "
                                f"for market {market['ticker']}"
                            )

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
                        # Use *_dollars fields for Decimal precision (ADR-002)
                        try:
                            update_market_with_versioning(
                                ticker=market["ticker"],
                                yes_price=market["yes_bid_dollars"],  # Use Decimal bid
                                no_price=market["no_bid_dollars"],
                                status=mapped_status,
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
                                yes_price=market["yes_bid_dollars"],  # Use Decimal bid
                                no_price=market["no_bid_dollars"],
                                market_type="binary",
                                status=mapped_status,
                                volume=market.get("volume"),
                                open_interest=market.get("open_interest"),
                                spread=market["yes_ask_dollars"]
                                - market["yes_bid_dollars"],  # Calculate spread
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
                    f"\n[green][OK] Success:[/green] {created_count} markets created, {updated_count} updated"
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
        # Security: Don't expose internal error details to user (Issue #42)
        console.print("\n[red]Error:[/red] Failed to fetch markets from API")
        if verbose:
            console.print(f"[dim]Details: {e}[/dim]")
        else:
            console.print("[dim]Use --verbose for error details[/dim]")
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

        if positions is None:
            console.print(
                "\n[yellow]Warning:[/yellow] Positions endpoint unavailable (DEMO API instability)"
            )
            console.print("  Use --environment prod for production positions")
            raise typer.Exit(code=1)

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
        #   3. Add lookup logic: ticker -> market_id
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
        # Security: Don't expose internal error details to user (Issue #42)
        console.print("\n[red]Error:[/red] Failed to fetch positions from API")
        if verbose:
            console.print(f"[dim]Details: {e}[/dim]")
        else:
            console.print("[dim]Use --verbose for error details[/dim]")
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
        #   2. Add lookup logic: ticker + side -> position_id
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
        # Security: Don't expose internal error details to user (Issue #42)
        console.print("\n[red]Error:[/red] Failed to fetch trade fills from API")
        if verbose:
            console.print(f"[dim]Details: {e}[/dim]")
        else:
            console.print("[dim]Use --verbose for error details[/dim]")
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
                    f"\n[green][OK] Success:[/green] {settlement_count} settlements saved, {market_update_count} markets updated to 'settled'"
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
        # Security: Don't expose internal error details to user (Issue #42)
        console.print("\n[red]Error:[/red] Failed to fetch settlements from API")
        if verbose:
            console.print(f"[dim]Details: {e}[/dim]")
        else:
            console.print("[dim]Use --verbose for error details[/dim]")
        raise typer.Exit(code=1) from e


@app.command(name="db-init")
def db_init(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without making changes"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """
    Initialize database schema and apply migrations.

    **Database Initialization Explained:**
    This command sets up your Precog database from scratch. Think of it like
    preparing a new notebook before you can start writing in it.

    **What This Command Does:**
    1. Checks if database connection is working
    2. Creates all required tables (markets, positions, trades, etc.)
    3. Applies any pending database migrations
    4. Validates schema integrity

    **When to Use:**
    - First-time setup on a new machine
    - After database corruption or reset
    - When switching between environments (dev/test/prod)

    Args:
        dry_run: Show what would be done without making changes
        verbose: Show detailed output including SQL statements

    Returns:
        None: Exits with code 0 on success, 1 on failure

    Educational Note:
        Database initialization is idempotent - running it multiple times is safe.
        Existing data won't be deleted, but missing tables will be created.

    Example:
        ```bash
        # Dry run to see what would happen
        python main.py db-init --dry-run

        # Actually initialize database
        python main.py db-init

        # Verbose mode to see SQL statements
        python main.py db-init --verbose
        ```

    References:
        - DEVELOPMENT_PHASES_V1.8.md: Phase 1, Task 2 (Database Implementation)
        - docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md: Complete schema reference
        - REQ-SYS-002: Database initialization requirements
    """
    if verbose:
        logger.info("Verbose mode enabled")

    console.print("\n[bold cyan]Precog Database Initialization[/bold cyan]\n")

    try:
        # Import business logic functions
        from precog.database.connection import test_connection
        from precog.database.initialization import (
            apply_migrations,
            apply_schema,
            get_database_url,
            validate_critical_tables,
            validate_schema_file,
        )

        # Step 1: Test database connection
        console.print("[1/4] Testing database connection...")
        if not test_connection():
            console.print("[red][FAIL] Database connection failed[/red]")
            raise typer.Exit(code=1)

        console.print("[green][OK] Database connection successful[/green]")

        if dry_run:
            console.print("\n[yellow]Dry-run mode:[/yellow] Would initialize database schema")
            console.print("\nActions that would be performed:")
            console.print("  - Create missing tables")
            console.print("  - Apply pending migrations")
            console.print("  - Validate schema integrity")
            console.print("  - Create indexes and constraints")
            return

        # Step 2: Create tables
        console.print("\n[2/4] Creating database tables...")
        schema_file = "database/precog_schema_v1.7.sql"

        if not validate_schema_file(schema_file):
            console.print(f"[red][FAIL] Schema file not found: {schema_file}[/red]")
            raise typer.Exit(code=1)

        db_url = get_database_url()
        if not db_url:
            console.print("[red][FAIL] DATABASE_URL environment variable not set[/red]")
            raise typer.Exit(code=1)

        success, error = apply_schema(db_url, schema_file)
        if not success:
            if "psql command not found" in error:
                console.print(
                    "[yellow][WARN] psql command not found, skipping schema creation[/yellow]"
                )
                console.print("  Note: Tables may need to be created manually")
            else:
                console.print(f"[red][FAIL] Schema creation failed:[/red] {error}")
                raise typer.Exit(code=1)
        else:
            console.print("[green][OK] Tables created successfully[/green]")

        # Step 3: Apply migrations
        console.print("\n[3/4] Applying database migrations...")
        applied, failed = apply_migrations(db_url, "database/migrations")

        if failed:
            console.print(
                f"[yellow][WARN] {len(failed)} migration(s) failed:[/yellow] {', '.join(failed)}"
            )

        if applied > 0:
            console.print(f"[green][OK] {applied} migration(s) applied[/green]")
            if verbose and failed:
                for migration_file in failed:
                    console.print(f"  Failed: {migration_file}")
        else:
            console.print("[yellow][WARN] No migrations to apply[/yellow]")

        # Step 4: Validate schema
        console.print("\n[4/4] Validating schema integrity...")
        missing_tables = validate_critical_tables()

        if missing_tables:
            console.print(f"[red][FAIL] Missing critical tables:[/red] {', '.join(missing_tables)}")
            raise typer.Exit(code=1)

        console.print("[green][OK] All critical tables exist[/green]")
        console.print("\n[bold green][OK] Database initialization complete![/bold green]")
        logger.info("Database initialization completed successfully")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=verbose)
        # Security: Don't expose internal error details to user (Issue #42)
        console.print("\n[red]Error:[/red] Database initialization failed")
        if verbose:
            console.print(f"[dim]Details: {e}[/dim]")
        else:
            console.print("[dim]Use --verbose for error details[/dim]")
        raise typer.Exit(code=1) from e


@app.command(name="health-check")
def health_check(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """
    Check system health and connectivity.

    **Health Check Explained:**
    This command verifies that all Precog systems are operational. Think of it
    like a doctor's checkup for your trading system - it tests each component
    to ensure everything is working correctly.

    **What This Command Checks:**
    1. Database connectivity (can we connect to PostgreSQL?)
    2. Configuration files (can we load all YAML files?)
    3. API credentials (are environment variables set?)
    4. Directory structure (do all required folders exist?)

    **When to Use:**
    - Before starting trading operations
    - After configuration changes
    - When diagnosing system issues
    - As part of deployment verification

    Args:
        verbose: Show detailed output including error traces

    Returns:
        None: Exits with code 0 if all checks pass, 1 if any check fails

    Educational Note:
        Health checks are critical for production systems. Running this before
        trading prevents discovering issues mid-trade. It's like checking your
        car's oil before a road trip.

    Example:
        ```bash
        # Basic health check
        python main.py health-check

        # Detailed health check with error traces
        python main.py health-check --verbose
        ```

    References:
        - DEVELOPMENT_PHASES_V1.8.md: Phase 1, Task 5 (Logging Infrastructure)
        - REQ-SYS-003: System health monitoring requirements
    """
    if verbose:
        logger.info("Verbose mode enabled")

    console.print("\n[bold cyan]Precog System Health Check[/bold cyan]\n")

    checks_passed = 0
    checks_failed = 0

    # Check 1: Database connectivity
    console.print("[1/4] Checking database connectivity...")
    try:
        from precog.database.connection import test_connection

        if test_connection():
            console.print("[green][OK] Database connection OK[/green]")
            checks_passed += 1
        else:
            console.print("[red][FAIL] Database connection failed[/red]")
            checks_failed += 1
    except Exception as e:
        console.print(f"[red][FAIL] Database check failed: {e}[/red]")
        if verbose:
            logger.error(f"Database health check error: {e}", exc_info=True)
        checks_failed += 1

    # Check 2: Configuration files
    console.print("\n[2/4] Checking configuration files...")
    try:
        from precog.config.config_loader import ConfigLoader

        config_loader = ConfigLoader()
        config_files = [
            "db_config.yaml",
            "trading_config.yaml",
            "strategy_config.yaml",
            "model_config.yaml",
            "market_config.yaml",
            "kalshi_config.yaml",
            "env_config.yaml",
        ]

        missing_configs = []
        for config_file in config_files:
            try:
                config_loader.get(config_file)
            except Exception as config_error:
                missing_configs.append(config_file)
                if verbose:
                    logger.warning(f"Config file {config_file} failed to load: {config_error}")

        if not missing_configs:
            console.print(f"[green][OK] All {len(config_files)} configuration files loaded[/green]")
            checks_passed += 1
        else:
            console.print(
                f"[yellow][WARN] {len(missing_configs)} configuration files missing or invalid:[/yellow] {', '.join(missing_configs)}"
            )
            checks_failed += 1

    except Exception as e:
        console.print(f"[red][FAIL] Configuration check failed: {e}[/red]")
        if verbose:
            logger.error(f"Configuration health check error: {e}", exc_info=True)
        checks_failed += 1

    # Check 3: API credentials
    console.print("\n[3/4] Checking API credentials...")
    required_env_vars = [
        "KALSHI_API_KEY_ID",
        "KALSHI_PRIVATE_KEY_PATH",
        "DATABASE_URL",
    ]

    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if not missing_vars:
        console.print(
            f"[green][OK] All {len(required_env_vars)} required environment variables set[/green]"
        )
        checks_passed += 1
    else:
        console.print(f"[red][FAIL] Missing environment variables:[/red] {', '.join(missing_vars)}")
        checks_failed += 1

    # Check 4: Directory structure
    console.print("\n[4/4] Checking directory structure...")
    required_dirs = [
        "src/precog/database",
        "src/precog/api_connectors",
        "src/precog/config",
        "src/precog/utils",
        "tests",
        "_keys",
    ]

    missing_dirs = []
    for directory in required_dirs:
        if not os.path.exists(directory):
            missing_dirs.append(directory)

    if not missing_dirs:
        console.print(f"[green][OK] All {len(required_dirs)} required directories exist[/green]")
        checks_passed += 1
    else:
        console.print(f"[yellow][WARN] Missing directories:[/yellow] {', '.join(missing_dirs)}")
        checks_failed += 1

    # Summary
    total_checks = checks_passed + checks_failed
    console.print("\n[bold]Health Check Summary:[/bold]")
    console.print(f"  Checks passed: [green]{checks_passed}/{total_checks}[/green]")
    console.print(f"  Checks failed: [red]{checks_failed}/{total_checks}[/red]")

    if checks_failed == 0:
        console.print("\n[bold green][OK] All systems operational![/bold green]")
        logger.info("Health check passed: all systems operational")
    else:
        console.print("\n[bold yellow][WARN] Some checks failed[/bold yellow]")
        console.print("Please review the errors above and fix issues before proceeding.")
        logger.warning(f"Health check completed with {checks_failed} failures")
        raise typer.Exit(code=1)


@app.command(name="config-show")
def config_show(
    config_file: str = typer.Argument(
        ..., help="Configuration file to display (e.g., 'trading' without .yaml extension)"
    ),
    key_path: str = typer.Option(
        None,
        "--key",
        "-k",
        help="Specific configuration key path (e.g., 'account.max_total_exposure_dollars')",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """
    Display configuration values.

    **Configuration Display Explained:**
    This command shows the current configuration values loaded from YAML files.
    Think of it like opening your settings menu - you can see all your current
    preferences and parameters.

    **What This Command Shows:**
    - Configuration file contents (YAML format)
    - Specific key values (when --key is provided)
    - Configuration source (YAML file location)
    - Default values (when keys are missing)

    **When to Use:**
    - Verifying configuration before trading
    - Debugging unexpected behavior
    - Checking parameter values
    - Understanding system settings

    Args:
        config_file: Name of configuration file WITHOUT .yaml extension (e.g., 'trading', 'markets')
        key_path: Optional dot-separated path to specific key
        verbose: Show detailed output including file paths

    Returns:
        None: Exits with code 0 on success, 1 if configuration not found

    Educational Note:
        Configuration precedence: Database overrides > YAML files > Defaults.
        This command shows YAML values only (database overrides not yet implemented).

    Example:
        ```bash
        # Show entire trading configuration
        python main.py config-show trading

        # Show specific key
        python main.py config-show trading --key account.max_total_exposure_dollars

        # Verbose mode with file paths
        python main.py config-show trading --verbose
        ```

    References:
        - DEVELOPMENT_PHASES_V1.8.md: Phase 1, Task 4 (Configuration System)
        - docs/guides/CONFIGURATION_GUIDE_V3.1.md: Complete configuration reference
        - REQ-SYS-001: Configuration management requirements
    """
    if verbose:
        logger.info("Verbose mode enabled")

    console.print(f"\n[bold cyan]Configuration: {config_file}[/bold cyan]\n")

    try:
        from precog.config.config_loader import ConfigLoader

        config_loader = ConfigLoader()

        # Show specific key if provided
        if key_path:
            try:
                value = config_loader.get(config_file, key_path)
                console.print(f"[bold]Key:[/bold] {key_path}")
                console.print(f"[bold]Value:[/bold] {value}")

                if verbose:
                    console.print(f"\n[dim]Source: config/{config_file}[/dim]")
                    logger.info(f"Retrieved config key: {config_file}:{key_path} = {value}")

            except KeyError:
                console.print(f"[red][FAIL] Key not found:[/red] {key_path}")
                console.print(f"\nAvailable keys in {config_file}:")
                # Show top-level keys
                full_config = config_loader.get(config_file)
                for key in full_config:
                    console.print(f"  - {key}")
                raise typer.Exit(code=1) from None

        # Show entire configuration file
        else:
            config = config_loader.get(config_file)

            # Pretty print configuration
            import yaml

            yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False)
            console.print(yaml_str)

            if verbose:
                console.print(f"[dim]Source: config/{config_file}[/dim]")
                console.print(f"[dim]Keys: {len(config)}[/dim]")
                logger.info(f"Displayed configuration: {config_file}")

    except FileNotFoundError:
        console.print(f"[red][FAIL] Configuration file not found:[/red] {config_file}")
        console.print("\nAvailable configuration files (use name without .yaml extension):")
        config_files = [
            "trading",
            "trade_strategies",
            "position_management",
            "probability_models",
            "markets",
            "data_sources",
            "system",
        ]
        for cf in config_files:
            console.print(f"  - {cf}")
        raise typer.Exit(code=1) from None
    except Exception as e:
        logger.error(f"Failed to display configuration: {e}", exc_info=verbose)
        # Security: Don't expose internal error details to user (Issue #42)
        console.print("\n[red]Error:[/red] Failed to display configuration")
        if verbose:
            console.print(f"[dim]Details: {e}[/dim]")
        else:
            console.print("[dim]Use --verbose for error details[/dim]")
        raise typer.Exit(code=1) from e


@app.command(name="config-validate")
def config_validate(
    config_file: str = typer.Option(
        None, "--file", "-f", help="Specific configuration file to validate (default: all)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """
    Validate configuration files.

    **Configuration Validation Explained:**
    This command checks that your configuration files are valid and contain
    sensible values. Think of it like spell-check for your settings - it catches
    errors before they cause problems.

    **What This Command Validates:**
    1. YAML syntax (can files be parsed?)
    2. Required keys (are all mandatory settings present?)
    3. Value ranges (are parameters within valid bounds?)
    4. Type checking (are values the correct type?)
    5. Decimal precision (are financial values using Decimal?)

    **When to Use:**
    - After editing configuration files
    - Before deploying to production
    - When diagnosing configuration errors
    - As part of CI/CD pipeline

    Args:
        config_file: Optional specific file to validate (default: validate all)
        verbose: Show detailed validation results

    Returns:
        None: Exits with code 0 if all validations pass, 1 if any fail

    Educational Note:
        Configuration validation prevents runtime errors. Catching config issues
        at startup is much better than discovering them mid-trade!

    Example:
        ```bash
        # Validate all configuration files
        python main.py config-validate

        # Validate specific file
        python main.py config-validate --file trading_config.yaml

        # Verbose validation with detailed checks
        python main.py config-validate --verbose
        ```

    References:
        - DEVELOPMENT_PHASES_V1.8.md: Phase 1, Task 4 (Configuration System)
        - docs/guides/CONFIGURATION_GUIDE_V3.1.md: Configuration validation rules
        - REQ-SYS-001: Configuration validation requirements
    """
    if verbose:
        logger.info("Verbose mode enabled")

    console.print("\n[bold cyan]Configuration Validation[/bold cyan]\n")

    try:
        from precog.config.config_loader import ConfigLoader

        config_loader = ConfigLoader()

        # Determine which files to validate
        if config_file:
            config_files = [config_file]
            console.print(f"Validating: {config_file}\n")
        else:
            config_files = [
                "trading",
                "trade_strategies",
                "position_management",
                "probability_models",
                "markets",
                "data_sources",
                "system",
            ]
            console.print(f"Validating all {len(config_files)} configuration files\n")

        validation_results = {}
        files_passed = 0
        files_failed = 0

        for cf in config_files:
            console.print(f"[bold]{cf}[/bold]")
            errors = []
            warnings = []

            # Normalize config file name (strip .yaml extension, handle _config suffix)
            cf_normalized = cf.replace(".yaml", "").replace("_config", "")

            try:
                # Check 1: Can we load the file?
                config = config_loader.get(cf)
                console.print("  [OK] YAML syntax valid")

                # Check 2: Is the file empty?
                if not config:
                    errors.append("Configuration file is empty")
                    console.print("  [FAIL] File is empty")
                else:
                    console.print(f"  [OK] Contains {len(config)} top-level keys")

                # Check 3: Check for float contamination in financial configs
                if cf_normalized in ["trading", "trade_strategies", "markets"]:
                    import yaml

                    # Build correct file path (handle both "trading" and "trading.yaml" inputs)
                    file_path = f"src/precog/config/{cf_normalized}.yaml"
                    with open(file_path, encoding="utf-8") as f:
                        raw_content = f.read()
                        # Look for float notation (e.g., 0.05 instead of "0.05")
                        if any(
                            char.isdigit() and "." in line
                            for line in raw_content.split("\n")
                            for char in line
                        ):
                            # More sophisticated check would use YAML parser
                            warnings.append(
                                "May contain float values (should use string format for Decimal)"
                            )
                            console.print("  [WARN] Possible float contamination detected")

                if not errors:
                    console.print("[green]  [OK] Validation passed[/green]\n")
                    files_passed += 1
                else:
                    console.print(f"[red]  [FAIL] Validation failed: {len(errors)} errors[/red]\n")
                    files_failed += 1

                if verbose and (errors or warnings):
                    if errors:
                        console.print("  [red]Errors:[/red]")
                        for error in errors:
                            console.print(f"    - {error}")
                    if warnings:
                        console.print("  [yellow]Warnings:[/yellow]")
                        for warning in warnings:
                            console.print(f"    - {warning}")
                    console.print()

                validation_results[cf] = {
                    "passed": len(errors) == 0,
                    "errors": errors,
                    "warnings": warnings,
                }

            except FileNotFoundError:
                console.print(f"  [red][FAIL] File not found: config/{cf}[/red]\n")
                files_failed += 1
                validation_results[cf] = {
                    "passed": False,
                    "errors": [f"File not found: {cf}"],
                    "warnings": [],
                }
            except yaml.YAMLError as yaml_error:
                console.print(f"  [red][FAIL] YAML parsing error: {yaml_error}[/red]\n")
                files_failed += 1
                validation_results[cf] = {
                    "passed": False,
                    "errors": [f"YAML error: {yaml_error}"],
                    "warnings": [],
                }
            except Exception as validation_error:
                console.print(f"  [red][FAIL] Validation error: {validation_error}[/red]\n")
                files_failed += 1
                validation_results[cf] = {
                    "passed": False,
                    "errors": [f"Validation error: {validation_error}"],
                    "warnings": [],
                }

        # Summary
        total_files = len(config_files)
        console.print("[bold]Validation Summary:[/bold]")
        console.print(f"  Files passed: [green]{files_passed}/{total_files}[/green]")
        console.print(f"  Files failed: [red]{files_failed}/{total_files}[/red]")

        if files_failed == 0:
            console.print("\n[bold green][OK] All configuration files valid![/bold green]")
            logger.info("Configuration validation passed")
        else:
            console.print(
                "\n[bold red][FAIL] Some configuration files failed validation[/bold red]"
            )
            logger.error(f"Configuration validation failed: {files_failed} files with errors")
            raise typer.Exit(code=1)

    except Exception as e:
        logger.error(f"Configuration validation failed: {e}", exc_info=verbose)
        # Security: Don't expose internal error details to user (Issue #42)
        console.print("\n[red]Error:[/red] Configuration validation failed")
        if verbose:
            console.print(f"[dim]Details: {e}[/dim]")
        else:
            console.print("[dim]Use --verbose for error details[/dim]")
        raise typer.Exit(code=1) from e


# =============================================================================
# ENVIRONMENT COMMANDS (Issue #161)
# =============================================================================


@app.command(name="env")
def show_environment(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed environment configuration",
    ),
) -> None:
    """
    Display current two-axis environment configuration.

    Shows both axes of the environment model:
        1. Application Environment (PRECOG_ENV): Controls database selection
        2. Market Mode (KALSHI_MODE): Controls API endpoints (demo/live)

    The two-axis model allows independent configuration of:
        - Internal infrastructure (database, logging, safety guards)
        - External API connections (demo vs live prediction markets)

    Environment Detection Priority:
        1. --app-env CLI option (highest priority)
        2. PRECOG_ENV environment variable
        3. DB_NAME inference (from database name)
        4. Default to 'development' (safe default)

    Example:
        python main.py env
        python main.py env --verbose
        python main.py --app-env staging env

    Reference: docs/guides/ENVIRONMENT_CONFIGURATION_GUIDE_V1.0.md
    Related: Issue #202 (Two-Axis Environment Configuration)
    """
    if verbose:
        logger.info("Verbose mode enabled")

    # Get current environment using the two-axis system
    app_env = get_app_environment()
    kalshi_mode = get_market_mode("kalshi")

    # Environment colors and risk levels (Axis 1: Application Environment)
    app_env_info = {
        AppEnvironment.DEVELOPMENT: {"color": "green", "risk": "Low", "desc": "Local development"},
        AppEnvironment.TEST: {"color": "blue", "risk": "Low", "desc": "Automated testing"},
        AppEnvironment.STAGING: {
            "color": "yellow",
            "risk": "Medium",
            "desc": "Pre-production validation",
        },
        AppEnvironment.PRODUCTION: {"color": "red", "risk": "CRITICAL", "desc": "Live trading"},
    }

    # Market mode info (Axis 2: Market API Mode)
    market_mode_info = {
        MarketMode.DEMO: {"color": "green", "risk": "None", "desc": "Demo API (fake money)"},
        MarketMode.LIVE: {"color": "red", "risk": "FINANCIAL", "desc": "Live API (real money!)"},
    }

    app_info = app_env_info.get(app_env, {"color": "white", "risk": "Unknown", "desc": "Unknown"})
    market_info = market_mode_info.get(
        kalshi_mode, {"color": "white", "risk": "Unknown", "desc": "Unknown"}
    )

    # Display header
    console.print()
    console.print("[bold]Two-Axis Environment Configuration[/bold]")
    console.print()

    # Create Axis 1 table: Application Environment
    table1 = Table(title="Axis 1: Application Environment (Database)")
    table1.add_column("Setting", style="cyan", no_wrap=True)
    table1.add_column("Value", style="white")

    table1.add_row("Environment", f"[{app_info['color']}]{app_env.value}[/{app_info['color']}]")
    table1.add_row(
        "Database", f"[{app_info['color']}]{app_env.database_name}[/{app_info['color']}]"
    )
    table1.add_row("Risk Level", f"[{app_info['color']}]{app_info['risk']}[/{app_info['color']}]")
    table1.add_row("Description", app_info["desc"])

    console.print(table1)
    console.print()

    # Create Axis 2 table: Market Mode
    table2 = Table(title="Axis 2: Market API Mode (Kalshi)")
    table2.add_column("Setting", style="cyan", no_wrap=True)
    table2.add_column("Value", style="white")

    table2.add_row("Mode", f"[{market_info['color']}]{kalshi_mode.value}[/{market_info['color']}]")
    table2.add_row(
        "Risk Level", f"[{market_info['color']}]{market_info['risk']}[/{market_info['color']}]"
    )
    table2.add_row("Description", market_info["desc"])

    console.print(table2)
    console.print()

    # Validate combination and show safety status
    try:
        config = load_environment_config(validate=True)
        safety = config.get_combination_safety()

        safety_colors = {
            "allowed": "green",
            "warning": "yellow",
            "blocked": "red",
        }
        safety_color = safety_colors.get(safety.value, "white")
        console.print(
            f"[bold]Combination Safety:[/bold] [{safety_color}]{safety.value.upper()}[/{safety_color}]"
        )
    except OSError as e:
        console.print("[bold red]Combination Safety: BLOCKED[/bold red]")
        console.print(f"[red]{e}[/red]")

    if verbose:
        # Show environment variables
        console.print()
        table3 = Table(title="Environment Variables")
        table3.add_column("Variable", style="cyan", no_wrap=True)
        table3.add_column("Value", style="white")

        table3.add_row("PRECOG_ENV", os.getenv("PRECOG_ENV", "[dim]not set[/dim]"))
        table3.add_row(
            "KALSHI_MODE", os.getenv("KALSHI_MODE", "[dim]not set (default: demo)[/dim]")
        )
        table3.add_row("", "")  # Spacer
        table3.add_row("DB_NAME", os.getenv("DB_NAME", "[dim]not set[/dim]"))
        table3.add_row("DB_HOST", os.getenv("DB_HOST", "[dim]not set[/dim]"))
        table3.add_row("DB_PORT", os.getenv("DB_PORT", "[dim]not set[/dim]"))
        table3.add_row("DB_USER", os.getenv("DB_USER", "[dim]not set[/dim]"))
        table3.add_row(
            "DB_PASSWORD",
            "[dim]****** (hidden)[/dim]" if os.getenv("DB_PASSWORD") else "[dim]not set[/dim]",
        )

        console.print(table3)

    # Show safety warnings
    if app_env == AppEnvironment.PRODUCTION or kalshi_mode == MarketMode.LIVE:
        console.print()
        if app_env == AppEnvironment.PRODUCTION:
            console.print("[bold red]WARNING:[/bold red] Production database selected!")
            console.print("[dim]All database operations will affect real data.[/dim]")
        if kalshi_mode == MarketMode.LIVE:
            console.print("[bold red]WARNING:[/bold red] Live API mode selected!")
            console.print("[dim]Trading operations will use REAL MONEY.[/dim]")
        console.print("[dim]Double-check commands before executing.[/dim]")

    console.print()


# =============================================================================
# SCHEDULER COMMANDS (Phase 2.5 - Issue #193)
# =============================================================================

# Create scheduler sub-app
scheduler_app = typer.Typer(
    name="scheduler",
    help="Data collection scheduler commands for ESPN game states and Kalshi market prices",
)
app.add_typer(scheduler_app, name="scheduler")

# Global scheduler instances (for stop/status commands)
_espn_updater: MarketUpdater | None = None
_kalshi_poller: KalshiMarketPoller | None = None
_supervisor: ServiceSupervisor | None = None  # For supervised mode (production)


def _start_supervised_mode(
    espn: bool,
    kalshi: bool,
    espn_interval: int,
    kalshi_interval: int,
    kalshi_env: str,
    leagues: str,
    series: str,
    max_restarts: int,
    health_interval: int,
    foreground: bool,
    verbose: bool,
) -> None:
    """
    Start services using ServiceSupervisor for production-grade management.

    ServiceSupervisor provides health monitoring, auto-restart with exponential
    backoff, and circuit breaker functionality for long-running data collection.

    Args:
        espn: Enable ESPN game state polling
        kalshi: Enable Kalshi market price polling
        espn_interval: ESPN poll interval in seconds
        kalshi_interval: Kalshi poll interval in seconds
        kalshi_env: Kalshi environment (demo or prod)
        leagues: Comma-separated list of ESPN leagues
        series: Comma-separated list of Kalshi series
        max_restarts: Maximum service restarts before circuit breaker
        health_interval: Health check interval in seconds
        foreground: Run in foreground (blocks until Ctrl+C)
        verbose: Enable verbose output

    Educational Note:
        ServiceSupervisor implements the "let it crash" philosophy from Erlang/OTP,
        where services are allowed to fail and are automatically restarted by a
        supervisor. This is more resilient than trying to handle every possible
        error within each service.

    Reference: ADR-100 (Service Supervisor Pattern)
    """
    global _supervisor, _espn_updater, _kalshi_poller

    console.print("\n[bold cyan]Starting Data Collection (Supervised Mode)[/bold cyan]\n")
    console.print("[dim]ServiceSupervisor provides health monitoring and auto-restart[/dim]\n")

    # Determine enabled services
    enabled_services: set[str] = set()
    if espn:
        enabled_services.add("espn")
    if kalshi:
        enabled_services.add("kalshi_rest")

    if not enabled_services:
        console.print("[yellow]No services enabled. Use --espn or --kalshi.[/yellow]")
        raise typer.Exit(code=1)

    # Parse configuration
    league_list = [lg.strip().lower() for lg in leagues.split(",")]
    series_list = [s.strip() for s in series.split(",")]

    console.print("[bold]Configuration:[/bold]")
    if espn:
        console.print(f"  ESPN: {', '.join(league_list)} (interval: {espn_interval}s)")
    if kalshi:
        console.print(
            f"  Kalshi: {', '.join(series_list)} ({kalshi_env}, interval: {kalshi_interval}s)"
        )
    console.print(f"  Health check interval: {health_interval}s")
    console.print(f"  Max restarts: {max_restarts}")
    console.print()

    try:
        # Create supervisor using factory function
        # Note: leagues and series_tickers are now configured via ServiceConfig
        _supervisor = create_supervisor(
            environment=kalshi_env,  # development, staging, or production
            enabled_services=enabled_services,
            poll_interval=espn_interval,  # Use ESPN interval as default
            health_check_interval=health_interval,
        )

        # Register alert callback for console output
        def alert_handler(service_name: str, message: str, context: dict[str, Any]) -> None:
            console.print(f"[yellow]ALERT [{service_name}]:[/yellow] {message}")
            if verbose and context:
                console.print(f"  [dim]Context: {context}[/dim]")

        _supervisor.register_alert_callback(alert_handler)

        # Start all services
        console.print("[bold]Starting services...[/bold]")
        _supervisor.start_all()

        console.print(
            f"[bold green][OK] Supervisor started with {len(enabled_services)} service(s)[/bold green]"
        )

        if foreground:
            console.print("\n[dim]Running in foreground. Press Ctrl+C to stop.[/dim]")
            try:
                import signal as sig
                import time

                # Set up signal handler for graceful shutdown
                def signal_handler(signum: int, frame: Any) -> None:
                    console.print("\n[yellow]Received shutdown signal...[/yellow]")
                    _stop_supervised_mode()
                    raise typer.Exit(code=0)

                sig.signal(sig.SIGINT, signal_handler)
                sig.signal(sig.SIGTERM, signal_handler)

                # Keep running and show periodic status
                while _supervisor and _supervisor.is_running:
                    time.sleep(60)
                    # Show supervisor metrics
                    if _supervisor:
                        metrics = _supervisor.get_aggregate_metrics()
                        console.print(
                            f"[dim]Uptime: {metrics['uptime_seconds']:.0f}s | "
                            f"Services: {metrics['services_healthy']}/{metrics['services_total']} healthy | "
                            f"Restarts: {metrics['total_restarts']} | "
                            f"Errors: {metrics['total_errors']}[/dim]"
                        )

            except typer.Exit:
                raise
            except Exception as e:
                console.print(f"[red]Error in foreground loop: {e}[/red]")
                _stop_supervised_mode()
                raise typer.Exit(code=1) from e
        else:
            console.print("\n[dim]Supervisor running in background.[/dim]")
            console.print("[dim]Use 'python main.py scheduler status' to check progress.[/dim]")
            console.print("[dim]Use 'python main.py scheduler stop' to stop.[/dim]")

    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        console.print("[dim]Hint: Check KALSHI_API_KEY and KALSHI_PRIVATE_KEY_PATH[/dim]")
        raise typer.Exit(code=1) from e
    except Exception as e:
        console.print(f"[red]Failed to start supervisor: {e}[/red]")
        if verbose:
            logger.error(f"Supervisor startup error: {e}", exc_info=True)
        raise typer.Exit(code=1) from e


def _stop_supervised_mode() -> None:
    """Stop services managed by ServiceSupervisor."""
    global _supervisor

    if _supervisor and _supervisor.is_running:
        console.print("Stopping supervisor...")
        _supervisor.stop_all()
        metrics = _supervisor.get_aggregate_metrics()
        console.print(
            f"[green][OK] Supervisor stopped after {metrics['uptime_seconds']:.0f}s "
            f"({metrics['total_restarts']} restarts, {metrics['total_errors']} errors)[/green]"
        )
        _supervisor = None
    else:
        console.print("[dim]Supervisor not running[/dim]")


def _show_supervisor_status(verbose: bool) -> None:
    """Display status for supervised mode with aggregate metrics."""
    if not _supervisor:
        console.print("[yellow]Supervisor not initialized[/yellow]")
        return

    metrics = _supervisor.get_aggregate_metrics()

    console.print("[bold magenta]Supervisor Mode Active[/bold magenta]")
    console.print("[dim]Health monitoring and auto-restart enabled[/dim]\n")

    # Supervisor overview
    overview_table = Table(show_header=False, box=None)
    overview_table.add_column("Field", style="cyan")
    overview_table.add_column("Value", style="white")

    status = "[green]Running[/green]" if _supervisor.is_running else "[red]Stopped[/red]"
    overview_table.add_row("Status", status)
    overview_table.add_row("Uptime", f"{metrics['uptime_seconds']:.0f}s")
    overview_table.add_row(
        "Services", f"{metrics['services_healthy']}/{metrics['services_total']} healthy"
    )
    overview_table.add_row("Total Restarts", str(metrics["total_restarts"]))
    overview_table.add_row("Total Errors", str(metrics["total_errors"]))

    console.print("[bold]Supervisor Overview:[/bold]")
    console.print(overview_table)
    console.print()

    # Per-service status
    if metrics["per_service"]:
        console.print("[bold]Per-Service Status:[/bold]")
        for service_name, service_data in metrics["per_service"].items():
            healthy = service_data.get("healthy", False)
            health_icon = "[green]OK[/green]" if healthy else "[red]UNHEALTHY[/red]"
            restarts = service_data.get("restart_count", 0)
            errors = service_data.get("error_count", 0)
            console.print(
                f"  {service_name}: {health_icon} (restarts: {restarts}, errors: {errors})"
            )

            if verbose:
                if service_data.get("started_at"):
                    console.print(f"    [dim]Started: {service_data['started_at']}[/dim]")
                if service_data.get("last_health_check"):
                    console.print(f"    [dim]Last check: {service_data['last_health_check']}[/dim]")
    else:
        console.print("[dim]No services registered yet[/dim]")

    console.print()


@scheduler_app.command(name="start")
def scheduler_start(
    espn: bool = typer.Option(
        True,
        "--espn/--no-espn",
        help="Enable/disable ESPN game state polling",
    ),
    kalshi: bool = typer.Option(
        True,
        "--kalshi/--no-kalshi",
        help="Enable/disable Kalshi market price polling",
    ),
    espn_interval: int = typer.Option(
        15,
        "--espn-interval",
        help="ESPN poll interval in seconds (default: 15)",
    ),
    kalshi_interval: int = typer.Option(
        15,
        "--kalshi-interval",
        help="Kalshi poll interval in seconds (default: 15)",
    ),
    kalshi_env: str = typer.Option(
        "demo",
        "--kalshi-env",
        help="Kalshi environment (demo or prod)",
    ),
    leagues: str = typer.Option(
        "nfl,ncaaf",
        "--leagues",
        help="Comma-separated list of ESPN leagues to poll",
    ),
    series: str = typer.Option(
        "KXNFLGAME",
        "--series",
        help="Comma-separated list of Kalshi series to poll",
    ),
    foreground: bool = typer.Option(
        False,
        "--foreground",
        "-f",
        help="Run in foreground (blocks until Ctrl+C)",
    ),
    supervised: bool = typer.Option(
        False,
        "--supervised",
        "-s",
        help="Use ServiceSupervisor for health monitoring and auto-restart (production mode)",
    ),
    max_restarts: int = typer.Option(
        5,
        "--max-restarts",
        help="Maximum service restarts before circuit breaker (supervised mode)",
    ),
    health_interval: int = typer.Option(
        30,
        "--health-interval",
        help="Health check interval in seconds (supervised mode)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
) -> None:
    """
    Start data collection schedulers for ESPN and/or Kalshi.

    **Data Collection Explained:**
    This command starts background services that continuously poll external APIs
    and store data in the database. Think of it as turning on a "data vacuum"
    that keeps your database updated with the latest game states and market prices.

    **What This Command Does:**
    1. ESPN Polling: Fetches live game states (scores, periods, situations)
    2. Kalshi Polling: Fetches market prices (yes/no bids, volumes)
    3. Both run in background threads at configurable intervals

    **When to Use:**
    - Before game days to capture live data
    - For long-running data collection (training data accumulation)
    - Testing scheduler reliability

    Example:
        ```bash
        # Start both ESPN and Kalshi polling (default)
        python main.py scheduler start

        # Start only ESPN polling
        python main.py scheduler start --no-kalshi

        # Start with custom intervals
        python main.py scheduler start --espn-interval 30 --kalshi-interval 60

        # Start in foreground mode (blocks until Ctrl+C)
        python main.py scheduler start --foreground

        # Start with production Kalshi credentials
        python main.py scheduler start --kalshi-env prod

        # Start in supervised mode (production-grade health monitoring)
        python main.py scheduler start --supervised --foreground

        # Supervised mode with custom health check interval
        python main.py scheduler start -s -f --health-interval 60
        ```

    **Supervised Mode (--supervised/-s):**
    When using supervised mode, services are managed by ServiceSupervisor which provides:
    - Health monitoring at configurable intervals
    - Auto-restart with exponential backoff on failures
    - Circuit breaker (stops restarting after max_restarts)
    - Aggregate metrics across all services
    - Alert callback support for external monitoring

    Reference: docs/foundation/DEVELOPMENT_PHASES_V1.8.md (Phase 2.5)
    Related Issue: GitHub Issue #193
    Related ADR: ADR-100 (Service Supervisor Pattern)
    """
    global _espn_updater, _kalshi_poller, _supervisor

    if verbose:
        logger.info("Verbose mode enabled")

    # Use supervised mode for production-grade service management
    if supervised:
        _start_supervised_mode(
            espn=espn,
            kalshi=kalshi,
            espn_interval=espn_interval,
            kalshi_interval=kalshi_interval,
            kalshi_env=kalshi_env,
            leagues=leagues,
            series=series,
            max_restarts=max_restarts,
            health_interval=health_interval,
            foreground=foreground,
            verbose=verbose,
        )
        return

    # Non-supervised mode (existing simple implementation)
    console.print("\n[bold cyan]Starting Data Collection Schedulers[/bold cyan]\n")

    started_services = []

    # Parse leagues and series
    league_list = [lg.strip().lower() for lg in leagues.split(",")]
    series_list = [s.strip() for s in series.split(",")]

    # Start ESPN updater
    if espn:
        console.print("[1/2] Starting ESPN game state polling...")
        console.print(f"  Leagues: {', '.join(league_list)}")
        console.print(f"  Interval: {espn_interval} seconds")

        try:
            _espn_updater = MarketUpdater(
                leagues=league_list,
                poll_interval=espn_interval,
            )
            _espn_updater.start()
            console.print("[green][OK] ESPN polling started[/green]")
            started_services.append("ESPN")
        except Exception as e:
            console.print(f"[red][FAIL] Failed to start ESPN polling: {e}[/red]")
            if verbose:
                logger.error(f"ESPN polling error: {e}", exc_info=True)

    # Start Kalshi poller
    if kalshi:
        console.print("\n[2/2] Starting Kalshi market price polling...")
        console.print(f"  Environment: {kalshi_env}")
        console.print(f"  Series: {', '.join(series_list)}")
        console.print(f"  Interval: {kalshi_interval} seconds")

        try:
            _kalshi_poller = KalshiMarketPoller(
                series_tickers=series_list,
                poll_interval=kalshi_interval,
                environment=kalshi_env,
            )
            _kalshi_poller.start()
            console.print("[green][OK] Kalshi polling started[/green]")
            started_services.append("Kalshi")
        except ValueError as e:
            # Likely missing credentials
            console.print(f"[red][FAIL] Failed to start Kalshi polling: {e}[/red]")
            console.print("[dim]Hint: Check KALSHI_API_KEY and KALSHI_PRIVATE_KEY_PATH[/dim]")
            if verbose:
                logger.error(f"Kalshi polling error: {e}", exc_info=True)
        except Exception as e:
            console.print(f"[red][FAIL] Failed to start Kalshi polling: {e}[/red]")
            if verbose:
                logger.error(f"Kalshi polling error: {e}", exc_info=True)

    # Summary
    if started_services:
        console.print(f"\n[bold green][OK] Started: {', '.join(started_services)}[/bold green]")

        if foreground:
            console.print("\n[dim]Running in foreground. Press Ctrl+C to stop.[/dim]")
            try:
                import signal as sig
                import time

                # Set up signal handler for graceful shutdown
                def signal_handler(signum: int, frame: Any) -> None:
                    console.print("\n[yellow]Received shutdown signal...[/yellow]")
                    scheduler_stop_impl()
                    raise typer.Exit(code=0)

                sig.signal(sig.SIGINT, signal_handler)
                sig.signal(sig.SIGTERM, signal_handler)

                # Keep running and show periodic status
                while True:
                    time.sleep(60)
                    # Show periodic status update
                    if _espn_updater and _espn_updater.enabled:
                        espn_stats = _espn_updater.stats
                        console.print(
                            f"[dim]ESPN: {espn_stats['polls_completed']} polls, "
                            f"{espn_stats['items_updated']} games updated[/dim]"
                        )
                    if _kalshi_poller and _kalshi_poller.enabled:
                        kalshi_stats = _kalshi_poller.stats
                        console.print(
                            f"[dim]Kalshi: {kalshi_stats['polls_completed']} polls, "
                            f"{kalshi_stats['items_updated']} markets updated[/dim]"
                        )

            except typer.Exit:
                raise
            except Exception as e:
                console.print(f"[red]Error in foreground loop: {e}[/red]")
                scheduler_stop_impl()
                raise typer.Exit(code=1) from e
        else:
            console.print("\n[dim]Schedulers running in background.[/dim]")
            console.print("[dim]Use 'python main.py scheduler status' to check progress.[/dim]")
            console.print("[dim]Use 'python main.py scheduler stop' to stop.[/dim]")
    else:
        console.print("\n[yellow]No services started[/yellow]")
        raise typer.Exit(code=1)


def scheduler_stop_impl() -> None:
    """Implementation of scheduler stop (shared by command and signal handler)."""
    global _espn_updater, _kalshi_poller, _supervisor

    stopped_services = []

    # First, check if running in supervised mode
    if _supervisor and _supervisor.is_running:
        _stop_supervised_mode()
        return

    # Non-supervised mode: stop individual services
    if _espn_updater and _espn_updater.enabled:
        console.print("Stopping ESPN polling...")
        _espn_updater.stop()
        _espn_updater = None
        stopped_services.append("ESPN")

    if _kalshi_poller and _kalshi_poller.enabled:
        console.print("Stopping Kalshi polling...")
        _kalshi_poller.stop()
        _kalshi_poller = None
        stopped_services.append("Kalshi")

    if stopped_services:
        console.print(f"[green][OK] Stopped: {', '.join(stopped_services)}[/green]")
    else:
        console.print("[yellow]No schedulers were running[/yellow]")


@scheduler_app.command(name="stop")
def scheduler_stop(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
) -> None:
    """
    Stop all running data collection schedulers.

    Gracefully shuts down ESPN and Kalshi polling services, waiting for
    any in-progress database operations to complete.

    Example:
        ```bash
        python main.py scheduler stop
        ```

    Reference: docs/foundation/DEVELOPMENT_PHASES_V1.8.md (Phase 2.5)
    """
    if verbose:
        logger.info("Verbose mode enabled")

    console.print("\n[bold cyan]Stopping Data Collection Schedulers[/bold cyan]\n")
    scheduler_stop_impl()


@scheduler_app.command(name="status")
def scheduler_status(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
) -> None:
    """
    Show status of data collection schedulers.

    Displays current state, polling statistics, and recent activity for
    both ESPN and Kalshi polling services.

    Example:
        ```bash
        python main.py scheduler status
        python main.py scheduler status --verbose
        ```

    Reference: docs/foundation/DEVELOPMENT_PHASES_V1.8.md (Phase 2.5)
    """
    if verbose:
        logger.info("Verbose mode enabled")

    console.print("\n[bold cyan]Data Collection Scheduler Status[/bold cyan]\n")

    # Check if running in supervised mode
    if _supervisor and _supervisor.is_running:
        _show_supervisor_status(verbose)
        return

    # Non-supervised mode: show individual service status
    # ESPN Status
    console.print("[bold]ESPN Game State Polling:[/bold]")
    if _espn_updater and _espn_updater.enabled:
        espn_stats = _espn_updater.stats
        status_table = Table(show_header=False, box=None)
        status_table.add_column("Field", style="cyan")
        status_table.add_column("Value", style="white")

        status_table.add_row("Status", "[green]Running[/green]")
        status_table.add_row("Leagues", ", ".join(_espn_updater.leagues))
        status_table.add_row("Poll Interval", f"{_espn_updater.poll_interval}s")
        status_table.add_row("Polls Completed", str(espn_stats["polls_completed"]))
        status_table.add_row("Games Updated", str(espn_stats["items_updated"]))
        status_table.add_row("Errors", str(espn_stats["errors"]))
        status_table.add_row("Last Poll", espn_stats["last_poll"] or "Never")
        if espn_stats["last_error"]:
            status_table.add_row("Last Error", f"[red]{espn_stats['last_error']}[/red]")

        console.print(status_table)
    else:
        console.print("  [dim]Not running[/dim]")

    console.print()

    # Kalshi Status
    console.print("[bold]Kalshi Market Price Polling:[/bold]")
    if _kalshi_poller and _kalshi_poller.enabled:
        kalshi_stats = _kalshi_poller.stats
        status_table = Table(show_header=False, box=None)
        status_table.add_column("Field", style="cyan")
        status_table.add_column("Value", style="white")

        status_table.add_row("Status", "[green]Running[/green]")
        status_table.add_row("Environment", _kalshi_poller.environment)
        status_table.add_row("Series", ", ".join(_kalshi_poller.series_tickers))
        status_table.add_row("Poll Interval", f"{_kalshi_poller.poll_interval}s")
        status_table.add_row("Polls Completed", str(kalshi_stats["polls_completed"]))
        status_table.add_row("Markets Fetched", str(kalshi_stats["items_fetched"]))
        status_table.add_row("Markets Updated", str(kalshi_stats["items_updated"]))
        status_table.add_row("Markets Created", str(kalshi_stats["items_created"]))
        status_table.add_row("Errors", str(kalshi_stats["errors"]))
        status_table.add_row("Last Poll", kalshi_stats["last_poll"] or "Never")
        if kalshi_stats["last_error"]:
            status_table.add_row("Last Error", f"[red]{kalshi_stats['last_error']}[/red]")

        console.print(status_table)
    else:
        console.print("  [dim]Not running[/dim]")

    console.print()


@scheduler_app.command(name="poll-once")
def scheduler_poll_once(
    espn: bool = typer.Option(
        True,
        "--espn/--no-espn",
        help="Poll ESPN game states",
    ),
    kalshi: bool = typer.Option(
        True,
        "--kalshi/--no-kalshi",
        help="Poll Kalshi market prices",
    ),
    kalshi_env: str = typer.Option(
        "demo",
        "--kalshi-env",
        help="Kalshi environment (demo or prod)",
    ),
    leagues: str = typer.Option(
        "nfl,ncaaf",
        "--leagues",
        help="Comma-separated list of ESPN leagues to poll",
    ),
    series: str = typer.Option(
        "KXNFLGAME",
        "--series",
        help="Comma-separated list of Kalshi series to poll",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
) -> None:
    """
    Execute a single poll cycle (no background scheduling).

    Useful for testing, on-demand data refresh, or verifying API connectivity
    without starting the full scheduler.

    Example:
        ```bash
        # Poll both ESPN and Kalshi once
        python main.py scheduler poll-once

        # Poll only ESPN for NFL
        python main.py scheduler poll-once --no-kalshi --leagues nfl

        # Poll Kalshi production
        python main.py scheduler poll-once --no-espn --kalshi-env prod
        ```

    Reference: docs/foundation/DEVELOPMENT_PHASES_V1.8.md (Phase 2.5)
    """
    if verbose:
        logger.info("Verbose mode enabled")

    console.print("\n[bold cyan]Executing Single Poll Cycle[/bold cyan]\n")

    # Parse leagues and series
    league_list = [lg.strip().lower() for lg in leagues.split(",")]
    series_list = [s.strip() for s in series.split(",")]

    # Poll ESPN
    if espn:
        console.print(f"[bold]Polling ESPN ({', '.join(league_list)})...[/bold]")
        try:
            updater = MarketUpdater(leagues=league_list)
            result = updater.poll_once()
            console.print(
                f"[green][OK] ESPN: {result['games_fetched']} games fetched, "
                f"{result['games_updated']} updated[/green]"
            )
        except Exception as e:
            console.print(f"[red][FAIL] ESPN poll failed: {e}[/red]")
            if verbose:
                logger.error(f"ESPN poll error: {e}", exc_info=True)

    # Poll Kalshi
    if kalshi:
        series_str = ", ".join(series_list)
        console.print(f"\n[bold]Polling Kalshi ({series_str}, {kalshi_env})...[/bold]")
        try:
            poller = KalshiMarketPoller(
                series_tickers=series_list,
                environment=kalshi_env,
            )
            result = poller.poll_once()
            console.print(
                f"[green][OK] Kalshi: {result['markets_fetched']} markets fetched, "
                f"{result['markets_updated']} updated, {result['markets_created']} created[/green]"
            )
            poller.kalshi_client.close()
        except ValueError as e:
            console.print(f"[red][FAIL] Kalshi poll failed: {e}[/red]")
            console.print("[dim]Hint: Check KALSHI_API_KEY and KALSHI_PRIVATE_KEY_PATH[/dim]")
        except Exception as e:
            console.print(f"[red][FAIL] Kalshi poll failed: {e}[/red]")
            if verbose:
                logger.error(f"Kalshi poll error: {e}", exc_info=True)

    console.print()


# =============================================================================
# Database Seeding Commands
# =============================================================================


@app.command(name="db-seed")
def db_seed(
    sports: str = typer.Option(
        "nfl,nba,nhl,wnba,ncaaf,ncaab,ncaaw",
        "--sports",
        "-s",
        help="Comma-separated list of sports to seed (e.g., nfl,nba,ncaaw)",
    ),
    categories: str = typer.Option(
        "teams",
        "--categories",
        "-c",
        help="Comma-separated list of categories to seed (teams,venues)",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without making changes"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """
    Seed the database with static reference data.

    **Database Seeding Explained:**
    Seeding populates the database with required reference data like teams,
    venues, and initial Elo ratings. This data is required before live
    polling can work (e.g., ESPN game data references teams by ESPN ID).

    **What This Command Does:**
    1. Reads SQL seed files from src/precog/database/seeds/
    2. Executes them against the database in order (001_, 002_, etc.)
    3. Uses ON CONFLICT for idempotent upserts (safe to re-run)
    4. Reports counts of records created/updated

    **Seeding Categories:**
    - teams: Team reference data with ESPN IDs (NFL, NBA, NHL, etc.)
    - venues: Stadium/arena information (future)

    **When to Use:**
    - After initial database setup (db-init)
    - After adding new sports support
    - After database reset or migration

    Args:
        sports: Comma-separated sports (nfl,nba,nhl,wnba,ncaaf,ncaab,ncaaw)
        categories: Comma-separated categories (teams,venues)
        dry_run: Show what would be done without making changes
        verbose: Show detailed output

    Returns:
        None: Exits with code 0 on success, 1 on failure

    Educational Note:
        Seeding is idempotent - running it multiple times is safe.
        SQL files use ON CONFLICT DO UPDATE so existing data is refreshed,
        not duplicated. This allows re-running after adding new teams
        to seed files.

    Example:
        ```bash
        # Seed all sports teams
        python main.py db-seed

        # Seed only NFL and NBA teams
        python main.py db-seed --sports nfl,nba

        # Dry run to see what would happen
        python main.py db-seed --dry-run

        # Verbose mode to see SQL execution details
        python main.py db-seed --verbose
        ```

    References:
        - ADR-029: ESPN Data Model
        - REQ-DATA-003: Multi-Sport Team Support
        - Phase 2.5: Live Data Collection Service
    """
    if verbose:
        logger.info("Verbose mode enabled for seeding")

    console.print("\n[bold cyan]Precog Database Seeding[/bold cyan]\n")

    # Parse sports and categories
    sport_list = [s.strip().lower() for s in sports.split(",")]
    category_list = [c.strip().lower() for c in categories.split(",")]

    console.print(f"[dim]Sports: {', '.join(sport_list)}[/dim]")
    console.print(f"[dim]Categories: {', '.join(category_list)}[/dim]")
    console.print()

    try:
        # Import SeedingManager
        from precog.database.seeding import SeedingConfig, SeedingManager

        # Create config
        config = SeedingConfig(
            sports=sport_list,
            dry_run=dry_run,
        )

        # Create manager and run seeding
        manager = SeedingManager(config=config)

        if dry_run:
            console.print("[yellow]Dry-run mode:[/yellow] Showing what would be done\n")

        # Seed teams if requested
        total_processed = 0
        total_created = 0
        total_errors = 0

        if "teams" in category_list:
            console.print("[1/2] Seeding teams...")
            stats = manager.seed_teams(sports=sport_list)

            # stats is a SeedingStats TypedDict - access as dict, not attributes
            total_processed = stats["records_processed"]
            total_created = stats["records_created"]
            total_errors = stats["errors"]

            console.print(
                f"  [green][OK] Teams: {total_created} created, "
                f"{total_processed} processed, {total_errors} errors[/green]"
            )

        # Verify seeding worked
        console.print("\n[2/2] Verifying seeds...")
        result = manager.verify_seeds()

        # verify_seeds() returns {"success": bool, "categories": {"teams": {...}}}
        teams = result.get("categories", {}).get("teams", {})
        overall_success = result.get("success", False)

        if overall_success:
            console.print(
                f"  [green][OK] All {teams.get('expected', '?')} expected teams found[/green]"
            )
        else:
            console.print(
                f"  [yellow][WARN] Expected {teams.get('expected', '?')}, "
                f"found {teams.get('actual', '?')}[/yellow]"
            )
            if teams.get("missing_sports"):
                console.print(
                    f"  [yellow]Missing sports: {', '.join(teams['missing_sports'])}[/yellow]"
                )

        # Show summary using stats from seed_teams
        console.print("\n[bold]Summary:[/bold]")
        console.print(f"  Total processed: {total_processed}")
        console.print(f"  Total created: {total_created}")
        console.print(f"  Total errors: {total_errors}")

        if total_errors > 0:
            console.print("\n[red]Some seeding operations failed. Check logs for details.[/red]")
            raise typer.Exit(code=1)

        console.print("\n[green]Seeding completed successfully![/green]\n")

    except ImportError as e:
        console.print(f"[red][FAIL] Failed to import seeding module: {e}[/red]")
        console.print("[dim]Hint: Ensure precog.database.seeding package exists[/dim]")
        raise typer.Exit(code=1) from None
    except Exception as e:
        console.print(f"[red][FAIL] Seeding failed: {e}[/red]")
        if verbose:
            logger.error(f"Seeding error: {e}", exc_info=True)
        raise typer.Exit(code=1) from None


@app.command(name="db-verify-seeds")
def db_verify_seeds(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """
    Verify that required seed data exists in the database.

    **Seed Verification Explained:**
    This command checks that the database contains the expected reference
    data (teams, venues, etc.) needed for live polling to work. Use this
    to diagnose "team not found" errors.

    **What This Command Checks:**
    - Team counts per sport (NFL=32, NBA=30, etc.)
    - Teams with ESPN IDs populated (required for live data matching)
    - Missing sports that need seeding

    **When to Use:**
    - After running db-seed to verify it worked
    - Debugging "team not found" warnings from pollers
    - Before starting live polling for a new sport

    Args:
        verbose: Show detailed per-sport breakdown

    Returns:
        None: Exits with code 0 if all seeds exist, 1 if missing

    Educational Note:
        This verification is lightweight (COUNT queries only) and safe
        to run frequently. It doesn't modify any data.

    Example:
        ```bash
        # Quick verification
        python main.py db-verify-seeds

        # Detailed per-sport breakdown
        python main.py db-verify-seeds --verbose
        ```

    References:
        - ADR-029: ESPN Data Model
        - REQ-DATA-003: Multi-Sport Team Support
    """
    console.print("\n[bold cyan]Precog Seed Verification[/bold cyan]\n")

    try:
        from precog.database.seeding import SeedingManager

        manager = SeedingManager()
        result = manager.verify_seeds()

        # verify_seeds() returns {"success": bool, "categories": {"teams": {...}}}
        # The teams data is nested under categories.teams
        teams = result.get("categories", {}).get("teams", {})
        overall_success = result.get("success", False)

        # Overall status
        if overall_success:
            console.print("[green][OK] All required seeds present[/green]")
            console.print(f"  Total teams: {teams.get('actual', '?')}/{teams.get('expected', '?')}")
            console.print(f"  Teams with ESPN IDs: {teams.get('has_espn_ids', '?')}")
        else:
            console.print("[yellow][WARN] Some seeds missing[/yellow]")
            console.print(f"  Total teams: {teams.get('actual', '?')}/{teams.get('expected', '?')}")
            missing = teams.get("missing_sports", [])
            if missing:
                console.print(f"  Missing sports: {', '.join(missing)}")

        # Detailed breakdown if verbose
        by_sport = teams.get("by_sport", {})
        if verbose and by_sport:
            console.print("\n[bold]Per-Sport Breakdown:[/bold]")

            from rich.table import Table

            table = Table(show_header=True, header_style="bold")
            table.add_column("Sport")
            table.add_column("Expected", justify="right")
            table.add_column("Actual", justify="right")
            table.add_column("ESPN IDs", justify="right")
            table.add_column("Status")

            for sport, data in sorted(by_sport.items()):
                status = "[green]OK[/green]" if data.get("ok") else "[red]MISSING[/red]"
                table.add_row(
                    sport.upper(),
                    str(data.get("expected", "?")),
                    str(data.get("actual", "?")),
                    str(data.get("has_espn_ids", "?")),
                    status,
                )

            console.print(table)

        if not overall_success:
            console.print(
                "\n[yellow]Hint: Run 'python main.py db-seed' to populate missing data[/yellow]"
            )
            raise typer.Exit(code=1)

        console.print()

    except ImportError as e:
        console.print(f"[red][FAIL] Failed to import seeding module: {e}[/red]")
        raise typer.Exit(code=1) from None
    except Exception as e:
        console.print(f"[red][FAIL] Verification failed: {e}[/red]")
        if verbose:
            logger.error(f"Verification error: {e}", exc_info=True)
        raise typer.Exit(code=1) from None


@app.command(name="db-seed-historical")
def db_seed_historical(
    csv_file: str = typer.Option(
        None,
        "--csv",
        "-f",
        help="Path to CSV file with historical Elo data",
    ),
    sport: str = typer.Option(
        "nfl",
        "--sport",
        "-s",
        help="Sport code (nfl, ncaaf, nba, etc.)",
    ),
    seasons: str = typer.Option(
        None,
        "--seasons",
        help="Comma-separated seasons to load (e.g., 2022,2023,2024)",
    ),
    source: str = typer.Option(
        "fivethirtyeight",
        "--source",
        help="Data source format (fivethirtyeight, simple)",
    ),
    stats_only: bool = typer.Option(
        False,
        "--stats",
        help="Show current historical Elo statistics without loading",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """
    Seed historical Elo ratings from CSV files.

    **Historical Elo Seeding Explained:**
    Loads historical Elo ratings from external data sources into the
    historical_elo table. This data is used for model training, backtesting,
    and analyzing historical team performance.

    **Data Sources:**
    - FiveThirtyEight: NFL Elo ratings from 1920 to present
    - Simple CSV: Custom format with team_code, date, elo_rating columns

    **FiveThirtyEight Format:**
    The FiveThirtyEight NFL Elo CSV has game-by-game data with:
    - date, season, team1, team2: Game identification
    - elo1_pre, elo2_pre: Pre-game Elo ratings
    - qbelo1_pre, qbelo2_pre: QB-adjusted ratings (NFL-specific)

    **When to Use:**
    - After initial database setup to load historical data
    - Before running backtests or training ML models
    - To update with new season data

    Args:
        csv_file: Path to CSV file (required unless --stats)
        sport: Sport code (default: nfl)
        seasons: Filter to specific seasons
        source: CSV format (fivethirtyeight or simple)
        stats_only: Show current data statistics
        verbose: Show detailed output

    Returns:
        None: Exits with code 0 on success, 1 on failure

    Example:
        ```bash
        # Show current historical Elo statistics
        python main.py db-seed-historical --stats

        # Load FiveThirtyEight NFL Elo data
        python main.py db-seed-historical --csv nfl_elo.csv

        # Load specific seasons only
        python main.py db-seed-historical --csv nfl_elo.csv --seasons 2022,2023,2024

        # Load simple CSV format
        python main.py db-seed-historical --csv my_elo.csv --source simple --sport nba
        ```

    References:
        - Issue #208: Historical Data Seeding
        - Migration 030: historical_elo table
        - FiveThirtyEight NFL Elo: https://github.com/fivethirtyeight/data/tree/master/nfl-elo
    """
    from pathlib import Path

    console.print("\n[bold cyan]Precog Historical Elo Seeding[/bold cyan]\n")

    try:
        from precog.database.seeding import (
            get_historical_elo_stats,
            load_csv_elo,
            load_fivethirtyeight_elo,
        )

        # Stats-only mode
        if stats_only:
            console.print("[dim]Fetching historical Elo statistics...[/dim]\n")

            try:
                stats = get_historical_elo_stats()

                console.print(f"[bold]Total records:[/bold] {stats['total']}")

                if stats["by_sport"]:
                    console.print("\n[bold]By Sport:[/bold]")
                    for sport_name, count in stats["by_sport"].items():
                        console.print(f"  {sport_name.upper()}: {count:,}")

                if stats["by_season"]:
                    console.print("\n[bold]By Season (recent):[/bold]")
                    for season, count in stats["by_season"].items():
                        console.print(f"  {season}: {count:,}")

                if stats["by_source"]:
                    console.print("\n[bold]By Source:[/bold]")
                    for source_name, count in stats["by_source"].items():
                        console.print(f"  {source_name}: {count:,}")

            except Exception as e:
                console.print(f"[yellow]Note: {e}[/yellow]")
                console.print("[dim]The historical_elo table may not exist yet.[/dim]")
                console.print(
                    "[dim]Run migration 030 first: python scripts/run_migrations.py[/dim]"
                )

            console.print()
            return

        # Require CSV file for loading
        if not csv_file:
            console.print("[red]Error: --csv option required for loading data[/red]")
            console.print("[dim]Use --stats to view current data without loading[/dim]")
            raise typer.Exit(code=1)

        csv_path = Path(csv_file)
        if not csv_path.exists():
            console.print(f"[red]Error: CSV file not found: {csv_file}[/red]")
            raise typer.Exit(code=1)

        # Parse seasons filter
        season_list = None
        if seasons:
            try:
                season_list = [int(s.strip()) for s in seasons.split(",")]
                console.print(f"[dim]Filtering to seasons: {season_list}[/dim]")
            except ValueError:
                console.print(f"[red]Error: Invalid seasons format: {seasons}[/red]")
                raise typer.Exit(code=1) from None

        console.print(f"[dim]Loading from: {csv_path}[/dim]")
        console.print(f"[dim]Sport: {sport}[/dim]")
        console.print(f"[dim]Source format: {source}[/dim]")
        console.print()

        # Load based on source format
        if source == "fivethirtyeight":
            result = load_fivethirtyeight_elo(csv_path, sport=sport, seasons=season_list)
        elif source == "simple":
            result = load_csv_elo(csv_path, sport=sport, source="imported")
        else:
            console.print(f"[red]Error: Unknown source format: {source}[/red]")
            console.print("[dim]Supported formats: fivethirtyeight, simple[/dim]")
            raise typer.Exit(code=1)

        # Report results
        console.print("[bold]Load Results:[/bold]")
        console.print(f"  Records processed: {result.records_processed:,}")
        console.print(f"  Records inserted: {result.records_inserted:,}")
        console.print(f"  Records skipped: {result.records_skipped:,}")
        console.print(f"  Errors: {result.errors}")

        if result.records_skipped > 0:
            console.print("\n[yellow]Note: Skipped records may be due to missing teams.[/yellow]")
            console.print("[dim]Ensure teams are seeded first: python main.py db-seed[/dim]")

        if result.errors > 0:
            console.print("\n[red]Some errors occurred during loading.[/red]")
            if verbose and result.error_messages:
                for msg in result.error_messages[:10]:
                    console.print(f"  [dim]{msg}[/dim]")
            raise typer.Exit(code=1)

        console.print("\n[green]Historical Elo seeding completed successfully![/green]\n")

    except ImportError as e:
        console.print(f"[red][FAIL] Failed to import seeding module: {e}[/red]")
        raise typer.Exit(code=1) from None
    except Exception as e:
        console.print(f"[red][FAIL] Historical seeding failed: {e}[/red]")
        if verbose:
            logger.error(f"Historical seeding error: {e}", exc_info=True)
        raise typer.Exit(code=1) from None


# =============================================================================
# Run Services Command (Production Data Collection)
# =============================================================================


@app.command(name="run-services")
def run_services(
    stop: bool = typer.Option(False, "--stop", help="Stop running data collection service"),
    status: bool = typer.Option(False, "--status", help="Check service status"),
    no_espn: bool = typer.Option(False, "--no-espn", help="Disable ESPN game polling"),
    no_kalshi: bool = typer.Option(False, "--no-kalshi", help="Disable Kalshi market polling"),
    espn_interval: int = typer.Option(15, "--espn-interval", help="ESPN poll interval in seconds"),
    kalshi_interval: int = typer.Option(
        30, "--kalshi-interval", help="Kalshi poll interval in seconds"
    ),
    leagues: str = typer.Option(
        "nfl,nba,nhl,ncaaf,ncaab",
        "--leagues",
        help="Comma-separated list of leagues to poll",
    ),
    health_interval: int = typer.Option(
        60, "--health-interval", help="Health check interval in seconds"
    ),
    metrics_interval: int = typer.Option(
        300, "--metrics-interval", help="Metrics reporting interval in seconds"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
) -> None:
    """
    Start the production data collection service.

    **What This Command Does:**
    Runs the Precog data collection services (ESPN game polling, Kalshi market
    polling) with production-grade features: signal handling, PID management,
    startup validation, and graceful shutdown.

    **Services Started:**
    - **ESPN Poller**: Fetches live game data for configured leagues
    - **Kalshi Poller**: Fetches market prices and positions

    **When to Use:**
    - Local development: Run in foreground with Ctrl+C to stop
    - Production: Run as systemd service or with process supervisor

    **Examples:**
        # Start all services (default)
        python main.py run-services

        # Start ESPN only
        python main.py run-services --no-kalshi

        # Custom intervals
        python main.py run-services --espn-interval 30 --kalshi-interval 60

        # Check if service is running
        python main.py run-services --status

        # Stop running service
        python main.py run-services --stop

        # Debug mode
        python main.py run-services --debug

    **Exit Codes:**
    - 0: Clean shutdown
    - 1: Startup error
    - 3: Already running

    **Signal Handling:**
    - SIGTERM/SIGINT: Graceful shutdown (finish current operations)
    - SIGHUP: Graceful shutdown (Unix only)

    References:
        - Issue #193: Phase 2.5 Live Data Collection Service
        - ADR-100: Service Supervisor Pattern
        - REQ-DATA-001: Live Data Collection
    """
    from precog.runners import DataCollectorService

    # Parse leagues
    league_list = [league.strip() for league in leagues.split(",")]

    # Create service
    service = DataCollectorService(
        espn_enabled=not no_espn,
        kalshi_enabled=not no_kalshi,
        espn_interval=espn_interval,
        kalshi_interval=kalshi_interval,
        health_interval=health_interval,
        metrics_interval=metrics_interval,
        leagues=league_list,
        debug=debug,
    )

    # Handle commands
    if status:
        exit_code = service.status()
        raise typer.Exit(code=exit_code)

    if stop:
        exit_code = service.stop()
        raise typer.Exit(code=exit_code)

    # Start the service (blocks until shutdown)
    console.print("\n[bold cyan]Starting Precog Data Collection Service[/bold cyan]\n")
    exit_code = service.start()
    raise typer.Exit(code=exit_code)


def main():
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
