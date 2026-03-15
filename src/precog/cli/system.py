"""
System Utilities CLI Commands.

Provides system-level commands for health checks, version info, and diagnostics.

Commands:
    health  - Comprehensive health check (database, APIs, services)
    version - Show version information
    info    - Show system diagnostics (Python, dependencies, paths)

Usage:
    precog system health [--verbose]
    precog system version
    precog system info

Related:
    - Issue #204: CLI Refactor
    - docs/planning/CLI_REFACTOR_COMPREHENSIVE_PLAN_V1.0.md Section 4.2.7
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

import typer

from precog.cli._common import (
    console,
    echo_error,
    echo_success,
    format_table,
    get_env_mode,
    get_kalshi_mode,
)

app = typer.Typer(
    name="system",
    help="System utilities (health, version, info)",
    no_args_is_help=True,
)


@app.command()
def health(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Show detailed health information",
    ),
) -> None:
    """Comprehensive health check.

    Checks:
        - Database connectivity
        - API credentials configuration
        - Service status
        - Configuration validity

    Examples:
        precog system health
        precog system health --verbose
    """
    console.print("[bold]Precog Health Check[/bold]\n")

    checks_passed = 0
    checks_failed = 0
    checks_total = 0

    # Check 1: Database connectivity
    checks_total += 1
    console.print("Checking database connectivity...", end=" ")
    try:
        from precog.database.connection import get_cursor

        with get_cursor() as cur:
            cur.execute("SELECT 1 AS test")
            cur.fetchone()
        echo_success("OK")
        checks_passed += 1
        if verbose:
            from precog.config.config_loader import ConfigLoader

            config = ConfigLoader()
            db_config = config.get_db_config()
            console.print(f"  [dim]Database: {db_config.get('database', 'unknown')}[/dim]")
    except Exception as e:
        echo_error(f"FAILED: {e}")
        checks_failed += 1

    # Check 2: Kalshi API credentials
    checks_total += 1
    console.print("Checking Kalshi API credentials...", end=" ")
    try:
        import os

        api_key = os.getenv("KALSHI_API_KEY_ID")
        private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")

        if api_key and private_key_path:
            key_path = Path(private_key_path)
            if key_path.exists():
                echo_success("OK")
                checks_passed += 1
                if verbose:
                    console.print(f"  [dim]API Key ID: {api_key[:8]}...[/dim]")
                    console.print(f"  [dim]Key Path: {private_key_path}[/dim]")
            else:
                echo_error(f"FAILED: Private key not found at {private_key_path}")
                checks_failed += 1
        else:
            echo_error("FAILED: Credentials not configured")
            checks_failed += 1
            if verbose:
                console.print(
                    "  [dim]Set KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH in .env[/dim]"
                )
    except Exception as e:
        echo_error(f"FAILED: {e}")
        checks_failed += 1

    # Check 3: Configuration validity
    checks_total += 1
    console.print("Checking configuration...", end=" ")
    try:
        from precog.config.config_loader import ConfigLoader, get_trading_config

        config = ConfigLoader()
        # Try to load main config sections
        _ = get_trading_config()
        _ = config.get("system")
        echo_success("OK")
        checks_passed += 1
        if verbose:
            console.print(f"  [dim]Environment: {get_env_mode()}[/dim]")
            console.print(f"  [dim]Kalshi Mode: {get_kalshi_mode()}[/dim]")
    except Exception as e:
        echo_error(f"FAILED: {e}")
        checks_failed += 1

    # Check 4: ESPN API (no auth required)
    checks_total += 1
    console.print("Checking ESPN API...", end=" ")
    try:
        from precog.api_connectors.espn_client import ESPNClient

        ESPNClient()
        # Just verify client can be instantiated
        echo_success("OK")
        checks_passed += 1
    except Exception as e:
        echo_error(f"FAILED: {e}")
        checks_failed += 1

    # Check 5: Persistent Component Health (from system_health table)
    checks_total += 1
    console.print("Checking persistent component health...", end=" ")
    try:
        from precog.database.crud_operations import get_system_health

        health_records = get_system_health()
        if health_records:
            # Count statuses
            status_counts: dict[str, int] = {}
            for record in health_records:
                s = record.get("status", "unknown")
                status_counts[s] = status_counts.get(s, 0) + 1

            all_healthy = all(r.get("status") == "healthy" for r in health_records)
            any_down = any(r.get("status") == "down" for r in health_records)

            if all_healthy:
                echo_success(f"OK ({len(health_records)} components)")
                checks_passed += 1
            elif any_down:
                echo_error(
                    f"UNHEALTHY ({status_counts.get('down', 0)} down, "
                    f"{status_counts.get('degraded', 0)} degraded, "
                    f"{status_counts.get('healthy', 0)} healthy)"
                )
                checks_failed += 1
            else:
                echo_error(
                    f"DEGRADED ({status_counts.get('degraded', 0)} degraded, "
                    f"{status_counts.get('healthy', 0)} healthy)"
                )
                checks_failed += 1

            if verbose:
                # Show per-component detail table
                health_rows = []
                for record in health_records:
                    component = record.get("component", "unknown")
                    status_val = record.get("status", "unknown")
                    last_check = record.get("last_check")
                    last_check_str = (
                        last_check.strftime("%Y-%m-%d %H:%M:%S UTC") if last_check else "never"
                    )

                    # Extract key details from JSONB
                    details = record.get("details") or {}
                    error_rate = details.get("error_rate", "-")
                    reason = details.get("reason", "-")

                    health_rows.append(
                        [component, status_val, last_check_str, str(error_rate), reason]
                    )

                table = format_table(
                    "",
                    ["Component", "Status", "Last Check", "Error Rate", "Reason"],
                    health_rows,
                )
                console.print(table)
        else:
            echo_success("OK (no health data yet - services may not have run)")
            checks_passed += 1
    except Exception as e:
        echo_error(f"FAILED: {e}")
        checks_failed += 1

    # Summary
    console.print()
    if checks_failed == 0:
        console.print(f"[bold green]All {checks_total} checks passed![/bold green]")
    else:
        console.print(
            f"[bold yellow]{checks_passed}/{checks_total} checks passed, "
            f"{checks_failed} failed[/bold yellow]"
        )
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Show version information.

    Examples:
        precog system version
    """
    try:
        from precog import __version__

        version_str = __version__
    except ImportError:
        version_str = "unknown"

    console.print(f"[bold]Precog[/bold] v{version_str}")
    console.print(
        f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )


@app.command()
def info() -> None:
    """Show system diagnostics.

    Displays:
        - Python version and path
        - Key dependency versions
        - Configuration paths
        - Environment settings

    Examples:
        precog system info
    """
    console.print("[bold]Precog System Information[/bold]\n")

    # Python info
    console.print("[bold]Python Environment[/bold]")
    rows = [
        [
            "Python Version",
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        ],
        ["Python Path", sys.executable],
        ["Platform", platform.platform()],
        ["Architecture", platform.machine()],
    ]
    table = format_table("", ["Property", "Value"], rows, show_header=False)
    console.print(table)
    console.print()

    # Key dependencies
    console.print("[bold]Key Dependencies[/bold]")
    dep_rows = []

    deps_to_check = [
        ("typer", "typer"),
        ("rich", "rich"),
        ("sqlalchemy", "sqlalchemy"),
        ("psycopg2", "psycopg2"),
        ("pydantic", "pydantic"),
        ("apscheduler", "apscheduler"),
        ("requests", "requests"),
        ("nfl_data_py", "nfl_data_py"),
    ]

    for display_name, import_name in deps_to_check:
        try:
            module = __import__(import_name)
            version = getattr(module, "__version__", "installed")
            dep_rows.append([display_name, version])
        except ImportError:
            dep_rows.append([display_name, "[dim]not installed[/dim]"])

    table = format_table("", ["Package", "Version"], dep_rows, show_header=False)
    console.print(table)
    console.print()

    # Environment settings
    console.print("[bold]Environment Settings[/bold]")
    import os

    env_rows = [
        ["PRECOG_ENV", os.getenv("PRECOG_ENV", "[dim]not set (default: dev)[/dim]")],
        ["KALSHI_MODE", os.getenv("KALSHI_MODE", "[dim]not set (default: demo)[/dim]")],
        [
            "KALSHI_API_KEY_ID",
            os.getenv("KALSHI_API_KEY_ID", "[dim]not set[/dim]")[:8] + "..."
            if os.getenv("KALSHI_API_KEY_ID")
            else "[dim]not set[/dim]",
        ],
    ]
    table = format_table("", ["Variable", "Value"], env_rows, show_header=False)
    console.print(table)
    console.print()

    # Paths
    console.print("[bold]Paths[/bold]")
    cwd = Path.cwd()
    path_rows = [
        ["Working Directory", str(cwd)],
        [
            "Config Directory",
            str(cwd / "config") if (cwd / "config").exists() else "[dim]not found[/dim]",
        ],
        [
            "Data Directory",
            str(cwd / "data") if (cwd / "data").exists() else "[dim]not found[/dim]",
        ],
    ]
    table = format_table("", ["Path", "Location"], path_rows, show_header=False)
    console.print(table)
