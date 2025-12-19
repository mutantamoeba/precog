"""
Database Operations CLI Commands.

Provides commands for database initialization, migrations, and status.

Commands:
    init    - Initialize database schema and apply migrations
    status  - Show database connection and table status
    migrate - Apply pending database migrations
    tables  - List all database tables

Usage:
    precog db init
    precog db status
    precog db migrate
    precog db tables

Related:
    - Issue #204: CLI Refactor
    - docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md
    - docs/planning/CLI_REFACTOR_COMPREHENSIVE_PLAN_V1.0.md Section 4.2.4
"""

from __future__ import annotations

import typer
from rich.table import Table

from precog.cli._common import (
    ExitCode,
    cli_error,
    console,
    echo_error,
    echo_success,
)

app = typer.Typer(
    name="db",
    help="Database operations (init, status, migrate, tables)",
    no_args_is_help=True,
)


# Critical tables that must exist for Precog to function
CRITICAL_TABLES = [
    "account_balance",
    "games",
    "game_states",
    "markets",
    "market_prices",
    "positions",
    "strategies",
    "models",
    "teams",
]


@app.command()
def init(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without making changes",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Show detailed output including SQL statements",
    ),
) -> None:
    """Initialize database schema and apply migrations.

    Sets up the Precog database from scratch:
    1. Tests database connection
    2. Creates all required tables
    3. Applies pending migrations
    4. Validates schema integrity

    Examples:
        precog db init
        precog db init --dry-run
        precog db init --verbose
    """
    console.print("\n[bold cyan]Database Initialization[/bold cyan]\n")

    try:
        from precog.database.connection import test_connection
        from precog.database.initialization import (
            apply_migrations,
            apply_schema,
            get_database_url,
            validate_critical_tables,
            validate_schema_file,
        )

        # Step 1: Test connection
        console.print("[1/4] Testing database connection...")
        if not test_connection():
            echo_error("Database connection failed")
            raise typer.Exit(code=1)
        echo_success("Database connection successful")

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
            cli_error(
                f"Schema file not found: {schema_file}",
                ExitCode.CONFIG_ERROR,
            )

        db_url = get_database_url()
        if not db_url:
            cli_error(
                "DATABASE_URL environment variable not set",
                ExitCode.CONFIG_ERROR,
                hint="Set DATABASE_URL in .env file",
            )

        success, error = apply_schema(db_url, schema_file)
        if not success:
            if "psql command not found" in error:
                console.print("[yellow]psql command not found, skipping schema creation[/yellow]")
                console.print("  Note: Tables may need to be created manually")
            else:
                cli_error(
                    f"Schema creation failed: {error}",
                    ExitCode.DATABASE_ERROR,
                )
        else:
            echo_success("Tables created successfully")

        # Step 3: Apply migrations
        console.print("\n[3/4] Applying database migrations...")
        applied, failed = apply_migrations(db_url, "database/migrations")

        if failed:
            console.print(
                f"[yellow]{len(failed)} migration(s) failed:[/yellow] {', '.join(failed)}"
            )

        if applied > 0:
            echo_success(f"{applied} migration(s) applied")
            if verbose and failed:
                for migration_file in failed:
                    console.print(f"  Failed: {migration_file}")
        else:
            console.print("[yellow]No migrations to apply[/yellow]")

        # Step 4: Validate schema
        console.print("\n[4/4] Validating schema integrity...")
        missing_tables = validate_critical_tables()

        if missing_tables:
            cli_error(
                f"Missing critical tables: {', '.join(missing_tables)}",
                ExitCode.DATABASE_ERROR,
            )

        echo_success("All critical tables exist")
        console.print("\n[bold green]Database initialization complete![/bold green]")

    except typer.Exit:
        raise
    except Exception as e:
        cli_error(
            f"Database initialization failed: {e}",
            ExitCode.DATABASE_ERROR,
            hint="Use --verbose for error details" if not verbose else None,
        )


@app.command()
def status(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Show detailed connection information",
    ),
) -> None:
    """Show database connection and table status.

    Displays:
    - Connection status
    - Database name and version
    - Table counts
    - Critical table status

    Examples:
        precog db status
        precog db status --verbose
    """
    console.print("\n[bold cyan]Database Status[/bold cyan]\n")

    try:
        from precog.database.connection import get_connection, test_connection

        # Test connection
        console.print("[bold]Connection:[/bold]")
        if test_connection():
            echo_success("Connected")
        else:
            echo_error("Connection failed")
            raise typer.Exit(code=1)

        # Get connection info
        conn = get_connection()

        # Get PostgreSQL version
        result = conn.execute("SELECT version()").fetchone()
        if result:
            version = result[0].split(",")[0] if result else "Unknown"
            console.print(f"  Database: {version}")

        # Get current database name
        result = conn.execute("SELECT current_database()").fetchone()
        if result:
            console.print(f"  Database name: {result[0]}")

        # Count tables
        result = conn.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'public'
        """).fetchone()
        table_count = result[0] if result else 0
        console.print(f"  Tables: {table_count}")

        console.print()

        # Check critical tables
        console.print("[bold]Critical Tables:[/bold]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Table", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Rows", justify="right")

        all_ok = True
        for table_name in CRITICAL_TABLES:
            try:
                # table_name from hardcoded CRITICAL_TABLES constant, not user input
                result = conn.execute(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = '{table_name}'
                    )
                """).fetchone()
                exists = result[0] if result else False

                if exists:
                    # Get row count
                    count_result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
                    row_count = count_result[0] if count_result else 0
                    table.add_row(table_name, "[green]OK[/green]", str(row_count))
                else:
                    table.add_row(table_name, "[red]MISSING[/red]", "-")
                    all_ok = False
            except Exception:
                table.add_row(table_name, "[red]ERROR[/red]", "-")
                all_ok = False

        console.print(table)

        if verbose:
            # Show environment info
            import os

            console.print("\n[bold]Environment:[/bold]")
            db_host = os.getenv("PRECOG_DB_HOST", "[dim]not set[/dim]")
            db_name = os.getenv("PRECOG_DB_NAME", "[dim]not set[/dim]")
            console.print(f"  PRECOG_DB_HOST: {db_host}")
            console.print(f"  PRECOG_DB_NAME: {db_name}")

        if not all_ok:
            console.print("\n[yellow]Some critical tables missing. Run 'precog db init'[/yellow]")
            raise typer.Exit(code=1)

        console.print()

    except typer.Exit:
        raise
    except Exception as e:
        cli_error(
            f"Failed to get database status: {e}",
            ExitCode.DATABASE_ERROR,
        )


@app.command()
def migrate(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Show detailed migration output",
    ),
) -> None:
    """Apply pending database migrations.

    Checks for and applies any pending migrations in order.
    Migrations are idempotent - running multiple times is safe.

    Examples:
        precog db migrate
        precog db migrate --verbose
    """
    console.print("\n[bold cyan]Applying Database Migrations[/bold cyan]\n")

    try:
        from precog.database.initialization import apply_migrations, get_database_url

        db_url = get_database_url()
        if not db_url:
            cli_error(
                "DATABASE_URL environment variable not set",
                ExitCode.CONFIG_ERROR,
                hint="Set DATABASE_URL in .env file",
            )

        console.print("Checking for pending migrations...")
        applied, failed = apply_migrations(db_url, "database/migrations")

        if applied > 0:
            echo_success(f"{applied} migration(s) applied")
        else:
            console.print("[dim]No pending migrations[/dim]")

        if failed:
            console.print(f"\n[yellow]{len(failed)} migration(s) failed:[/yellow]")
            for migration_file in failed:
                console.print(f"  - {migration_file}")

            if verbose:
                console.print("\n[dim]Check logs for detailed error messages[/dim]")

            raise typer.Exit(code=1)

        console.print()

    except typer.Exit:
        raise
    except Exception as e:
        cli_error(
            f"Migration failed: {e}",
            ExitCode.DATABASE_ERROR,
        )


@app.command()
def tables(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Show column details for each table",
    ),
) -> None:
    """List all database tables.

    Shows all tables in the public schema with row counts.

    Examples:
        precog db tables
        precog db tables --verbose
    """
    console.print("\n[bold cyan]Database Tables[/bold cyan]\n")

    try:
        from precog.database.connection import get_connection

        conn = get_connection()

        # Get all tables
        result = conn.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """).fetchall()

        if not result:
            console.print("[yellow]No tables found[/yellow]")
            return

        table = Table(title=f"Tables ({len(result)} total)")
        table.add_column("Table", style="cyan")
        table.add_column("Rows", justify="right")

        if verbose:
            table.add_column("Columns", justify="right")
            table.add_column("Size", justify="right")

        for row in result:
            table_name = row[0]

            # Get row count (table_name from trusted information_schema)
            try:
                count_result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
                row_count = count_result[0] if count_result else 0
            except Exception:
                row_count = "?"

            if verbose:
                # Get column count (table_name from trusted information_schema)
                col_result = conn.execute(f"""
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = '{table_name}'
                """).fetchone()
                col_count = col_result[0] if col_result else "?"

                # Get table size
                try:
                    size_result = conn.execute(f"""
                        SELECT pg_size_pretty(pg_total_relation_size('{table_name}'))
                    """).fetchone()
                    size = size_result[0] if size_result else "?"
                except Exception:
                    size = "?"

                table.add_row(table_name, str(row_count), str(col_count), size)
            else:
                table.add_row(table_name, str(row_count))

        console.print(table)
        console.print()

    except Exception as e:
        cli_error(
            f"Failed to list tables: {e}",
            ExitCode.DATABASE_ERROR,
        )
