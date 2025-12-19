"""
Scheduler Operations CLI Commands.

Provides commands for managing data collection schedulers (ESPN game states,
Kalshi market prices).

Commands:
    start     - Start data collection schedulers
    stop      - Stop all running schedulers
    status    - Show scheduler status and statistics
    poll-once - Execute a single poll cycle (no background scheduling)

Usage:
    precog scheduler start
    precog scheduler start --espn-interval 30 --kalshi-interval 60
    precog scheduler start --supervised --foreground
    precog scheduler stop
    precog scheduler status
    precog scheduler poll-once --no-kalshi --leagues nfl

Related:
    - Issue #204: CLI Refactor
    - Issue #193: Data Collection Scheduler
    - docs/foundation/DEVELOPMENT_PHASES_V1.8.md (Phase 2.5)
    - ADR-100: Service Supervisor Pattern
"""

from __future__ import annotations

import signal as sig
import time
from typing import TYPE_CHECKING, Any

import typer
from rich.table import Table

from precog.cli._common import (
    console,
)

if TYPE_CHECKING:
    from precog.schedulers.kalshi_market_poller import KalshiMarketPoller
    from precog.schedulers.market_updater import MarketUpdater
    from precog.schedulers.service_supervisor import ServiceSupervisor

app = typer.Typer(
    name="scheduler",
    help="Data collection scheduler operations (start, stop, status, poll-once)",
    no_args_is_help=True,
)

# Global scheduler instances (for stop/status commands)
_espn_updater: MarketUpdater | None = None
_kalshi_poller: KalshiMarketPoller | None = None
_supervisor: ServiceSupervisor | None = None


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
    """Start services using ServiceSupervisor for production-grade management.

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
    global _supervisor

    from precog.schedulers.service_supervisor import create_supervisor
    from precog.utils.logger import get_logger

    logger = get_logger(__name__)

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
        _supervisor = create_supervisor(
            environment=kalshi_env,
            enabled_services=enabled_services,
            poll_interval=espn_interval,
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
            console.print("[dim]Use 'precog scheduler status' to check progress.[/dim]")
            console.print("[dim]Use 'precog scheduler stop' to stop.[/dim]")

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


def _scheduler_stop_impl() -> None:
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


@app.command()
def start(
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
        "-V",
        help="Enable verbose output",
    ),
) -> None:
    """Start data collection schedulers for ESPN and/or Kalshi.

    Starts background services that continuously poll external APIs
    and store data in the database. Think of it as turning on a "data vacuum"
    that keeps your database updated with the latest game states and market prices.

    What this command does:
        1. ESPN Polling: Fetches live game states (scores, periods, situations)
        2. Kalshi Polling: Fetches market prices (yes/no bids, volumes)
        3. Both run in background threads at configurable intervals

    When to use:
        - Before game days to capture live data
        - For long-running data collection (training data accumulation)
        - Testing scheduler reliability

    Supervised mode (--supervised/-s) provides:
        - Health monitoring at configurable intervals
        - Auto-restart with exponential backoff on failures
        - Circuit breaker (stops restarting after max_restarts)
        - Aggregate metrics across all services

    Examples:
        precog scheduler start
        precog scheduler start --no-kalshi
        precog scheduler start --espn-interval 30 --kalshi-interval 60
        precog scheduler start --foreground
        precog scheduler start --kalshi-env prod
        precog scheduler start --supervised --foreground
    """
    global _espn_updater, _kalshi_poller

    from precog.schedulers.kalshi_market_poller import KalshiMarketPoller
    from precog.schedulers.market_updater import MarketUpdater
    from precog.utils.logger import get_logger

    logger = get_logger(__name__)

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

    # Non-supervised mode (simple implementation)
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
                # Set up signal handler for graceful shutdown
                def signal_handler(signum: int, frame: Any) -> None:
                    console.print("\n[yellow]Received shutdown signal...[/yellow]")
                    _scheduler_stop_impl()
                    raise typer.Exit(code=0)

                sig.signal(sig.SIGINT, signal_handler)
                sig.signal(sig.SIGTERM, signal_handler)

                # Keep running and show periodic status
                while True:
                    time.sleep(60)
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
                _scheduler_stop_impl()
                raise typer.Exit(code=1) from e
        else:
            console.print("\n[dim]Schedulers running in background.[/dim]")
            console.print("[dim]Use 'precog scheduler status' to check progress.[/dim]")
            console.print("[dim]Use 'precog scheduler stop' to stop.[/dim]")
    else:
        console.print("\n[yellow]No services started[/yellow]")
        raise typer.Exit(code=1)


@app.command()
def stop(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose output",
    ),
) -> None:
    """Stop all running data collection schedulers.

    Gracefully shuts down ESPN and Kalshi polling services, waiting for
    any in-progress database operations to complete.

    Examples:
        precog scheduler stop
        precog scheduler stop --verbose
    """
    from precog.utils.logger import get_logger

    logger = get_logger(__name__)

    if verbose:
        logger.info("Verbose mode enabled")

    console.print("\n[bold cyan]Stopping Data Collection Schedulers[/bold cyan]\n")
    _scheduler_stop_impl()


@app.command()
def status(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose output",
    ),
) -> None:
    """Show status of data collection schedulers.

    Displays current state, polling statistics, and recent activity for
    both ESPN and Kalshi polling services.

    Examples:
        precog scheduler status
        precog scheduler status --verbose
    """
    from precog.utils.logger import get_logger

    logger = get_logger(__name__)

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


@app.command(name="poll-once")
def poll_once(
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
        "-V",
        help="Enable verbose output",
    ),
) -> None:
    """Execute a single poll cycle (no background scheduling).

    Useful for testing, on-demand data refresh, or verifying API connectivity
    without starting the full scheduler.

    Examples:
        precog scheduler poll-once
        precog scheduler poll-once --no-kalshi --leagues nfl
        precog scheduler poll-once --no-espn --kalshi-env prod
    """
    from precog.schedulers.kalshi_market_poller import KalshiMarketPoller
    from precog.schedulers.market_updater import MarketUpdater
    from precog.utils.logger import get_logger

    logger = get_logger(__name__)

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
                f"[green][OK] ESPN: {result['items_fetched']} games fetched, "
                f"{result['items_updated']} updated[/green]"
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
                f"[green][OK] Kalshi: {result['items_fetched']} markets fetched, "
                f"{result['items_updated']} updated, {result['items_created']} created[/green]"
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
