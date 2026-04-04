"""
Monitoring Dashboard Screen.

Real-time system health monitoring without external tools.
Replaces the need for Grafana/Prometheus in early phases.

Design:
    - Health status cards for all services
    - Database connection pool stats
    - API rate limit status
    - Error rate trends (line charts via textual-plotext)
    - Live log stream

Reference:
    - Issue #283: TUI Additional Screens
    - This replaces Issue #198 (Grafana/Prometheus) temporarily

Educational Note:
    Uses textual-plotext for rich line charts. PlotextPlot provides
    terminal-based plotting with proper axes, labels, and styling.
    Falls back to Sparkline if textual-plotext is not installed.
"""

from datetime import UTC, datetime
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Container, Grid, Horizontal
from textual.widgets import DataTable, Label, RichLog, Sparkline, Static

from precog.tui.screens.base_screen import BaseScreen
from precog.tui.widgets.breadcrumb import Breadcrumb
from precog.tui.widgets.environment_bar import EnvironmentBar

# Try to import PlotextPlot for enhanced charts, fall back to Sparkline
try:
    from textual_plotext import PlotextPlot

    HAS_PLOTEXT = True
except ImportError:
    HAS_PLOTEXT = False


class HealthCard(Container):
    """A status card widget for displaying service health."""

    def __init__(
        self,
        title: str,
        status: str = "unknown",
        details: str = "",
        card_id: str = "",
    ) -> None:
        super().__init__(id=card_id, classes="health-card")
        self._title = title
        self._status = status
        self._details = details

    def compose(self) -> ComposeResult:
        yield Label(self._title, classes="card-title")
        yield Static(self._get_status_display(), id=f"{self.id}-status", classes="card-status")
        yield Static(self._details, id=f"{self.id}-details", classes="card-details")

    def _get_status_display(self) -> str:
        if self._status == "healthy":
            return "[bold green]HEALTHY[/]"
        if self._status == "degraded":
            return "[bold yellow]DEGRADED[/]"
        if self._status == "error":
            return "[bold red]ERROR[/]"
        return "[dim]UNKNOWN[/]"


class MonitoringDashboardScreen(BaseScreen):
    """
    System monitoring dashboard.

    Provides real-time visibility into system health without
    requiring external monitoring infrastructure (Grafana/Prometheus).

    Educational Note:
        This screen serves as the primary monitoring interface until
        production requirements demand historical trend analysis and
        remote access, at which point Grafana (#198) would be added.
        Inherits from BaseScreen to get global keybindings in footer.

    Metrics Displayed:
        - Database: Connection pool usage, query latency
        - APIs: Kalshi/ESPN rate limits, error rates
        - Services: Poller health, heartbeat status
        - System: Memory usage, CPU (when available)

    Data Sources:
        - Database health: test_connection() from connection.py
        - Scheduler status: list_scheduler_services() from crud_operations.py
        - API health: Tested via client initialization
    """

    BINDINGS: ClassVar[list[BindingType]] = BaseScreen.BINDINGS + [
        ("r", "refresh", "Refresh"),
        ("t", "test_connections", "Test Connections"),
        ("l", "toggle_logs", "Toggle Logs"),
    ]

    # Auto-refresh interval in seconds
    REFRESH_INTERVAL = 10

    def compose(self) -> ComposeResult:
        """Create the monitoring dashboard layout."""
        yield Breadcrumb.for_screen("monitoring_dashboard")
        yield EnvironmentBar.from_app(self.app)
        yield Label("System Monitoring", id="screen-title", classes="screen-title")

        # Last refresh time
        yield Static(
            f"[dim]Last refresh: {datetime.now(UTC).strftime('%H:%M:%S')} UTC[/]",
            id="last-refresh",
        )

        # Health cards grid
        with Grid(id="health-grid"):
            # Database health
            with Container(classes="health-card"):
                yield Label("Database", classes="card-title")
                yield Static("[green]HEALTHY[/]", id="db-status", classes="card-status")
                yield Static("Pool: 2/10 connections", id="db-details", classes="card-details")

            # Kalshi API health
            with Container(classes="health-card"):
                yield Label("Kalshi API", classes="card-title")
                yield Static("[green]HEALTHY[/]", id="kalshi-status", classes="card-status")
                yield Static("Rate: 45/100 req/min", id="kalshi-details", classes="card-details")

            # ESPN API health
            with Container(classes="health-card"):
                yield Label("ESPN API", classes="card-title")
                yield Static("[green]HEALTHY[/]", id="espn-status", classes="card-status")
                yield Static("Last poll: 12s ago", id="espn-details", classes="card-details")

            # Scheduler health
            with Container(classes="health-card"):
                yield Label("Scheduler", classes="card-title")
                yield Static("[yellow]DEGRADED[/]", id="scheduler-status", classes="card-status")
                yield Static("3/4 services running", id="scheduler-details", classes="card-details")

        # Metrics section - Enhanced charts with textual-plotext if available
        with Horizontal(id="metrics-section"):
            # Left: Error rate chart
            with Container(id="error-rate-container"):
                yield Label("Error Rate (last hour)", classes="metric-header")
                if HAS_PLOTEXT:
                    yield PlotextPlot(id="error-chart")
                else:
                    yield Sparkline(
                        [0, 0, 1, 0, 0, 0, 2, 0, 0, 0, 0, 1],
                        id="error-sparkline",
                    )
                yield Static("[dim]Avg: 0.3 errors/5min[/]", id="error-avg")

            # Right: API response time chart
            with Container(id="response-time-container"):
                yield Label("API Response Time (ms)", classes="metric-header")
                if HAS_PLOTEXT:
                    yield PlotextPlot(id="response-chart")
                else:
                    yield Sparkline(
                        [120, 130, 125, 140, 135, 128, 145, 132, 138, 141, 129, 136],
                        id="response-sparkline",
                    )
                yield Static("[dim]Avg: 133ms[/]", id="response-avg")

        # Detailed metrics table
        with Container(id="metrics-table-container"):
            yield Label("Detailed Metrics", classes="section-header")
            yield DataTable(id="metrics-table")

        # Live log stream
        with Container(id="log-container"):
            yield Label("Live Events", classes="section-header")
            yield RichLog(id="live-logs", highlight=True, markup=True, max_lines=50)

        # Status bar
        yield Static("Monitoring active", id="monitor-status")

    def on_mount(self) -> None:
        """Initialize the dashboard and start monitoring."""
        # Set up metrics table
        table = self.query_one("#metrics-table", DataTable)
        table.add_columns("Metric", "Current", "Min", "Max", "Avg")
        table.zebra_stripes = True

        # Initialize line charts if PlotextPlot is available
        if HAS_PLOTEXT:
            self._init_plotext_charts()

        # Load initial metrics
        self._load_metrics()

        # Initialize log stream
        self._init_log_stream()

        # Set up auto-refresh timer
        self.set_interval(self.REFRESH_INTERVAL, self._refresh_data)

    def _init_plotext_charts(self) -> None:
        """Initialize PlotextPlot charts with sample data.

        Educational Note:
            PlotextPlot provides rich terminal plotting via the plotext library.
            We use line plots with custom styling to show time-series data.
            The plt object is accessed via chart.plt to draw on the canvas.
        """
        # Time points (last 12 5-minute intervals = 1 hour)
        time_points = list(range(12))
        time_labels = [f"-{(12 - i) * 5}m" for i in range(12)]

        # Error rate chart
        try:
            error_chart = self.query_one("#error-chart", PlotextPlot)
            error_data = [0, 0, 1, 0, 0, 0, 2, 0, 0, 0, 0, 1]
            error_chart.plt.clear_figure()
            error_chart.plt.plot(time_points, error_data, marker="braille")
            error_chart.plt.title("Errors per 5min")
            error_chart.plt.xlabel("Time")
            error_chart.plt.ylabel("Count")
            error_chart.plt.xticks(time_points[::2], time_labels[::2])
            error_chart.plt.theme("dark")
            error_chart.refresh()
        except Exception:
            pass  # Chart might not exist if HAS_PLOTEXT changed

        # Response time chart
        try:
            response_chart = self.query_one("#response-chart", PlotextPlot)
            response_data = [120, 130, 125, 140, 135, 128, 145, 132, 138, 141, 129, 136]
            response_chart.plt.clear_figure()
            response_chart.plt.plot(time_points, response_data, marker="braille")
            response_chart.plt.title("API Response (ms)")
            response_chart.plt.xlabel("Time")
            response_chart.plt.ylabel("ms")
            response_chart.plt.xticks(time_points[::2], time_labels[::2])
            response_chart.plt.theme("dark")
            response_chart.refresh()
        except Exception:
            pass

    def _get_data_source_mode(self) -> str:
        """Get the current data source mode from the app.

        Educational Note:
            Accesses the app's data_source_mode property which controls whether
            screens use real database data, demo data, or auto-fallback behavior.
        """
        from precog.tui.app import PrecogApp

        if isinstance(self.app, PrecogApp):
            return self.app.data_source_mode
        return "auto"  # Default to auto mode

    def _get_api_environment(self) -> str:
        """Get the current API environment from the app.

        Educational Note:
            The API environment controls which Kalshi endpoint is used:
            - "demo": Paper trading (demo-api.kalshi.com)
            - "production": Real money (trading-api.kalshi.com)
        """
        from precog.tui.app import PrecogApp

        if isinstance(self.app, PrecogApp):
            return self.app.api_environment
        return "demo"

    def _test_database_health(self) -> tuple[str, str]:
        """Test database connectivity.

        Returns:
            Tuple of (status, details) where status is 'healthy', 'error', or 'unknown'
        """
        try:
            from precog.database.connection import test_connection

            if test_connection():
                return ("healthy", "Connection OK")
            return ("error", "Connection failed")
        except ImportError:
            return ("unknown", "Module unavailable")
        except Exception as e:
            return ("error", f"Error: {str(e)[:30]}")

    def _test_kalshi_api_health(self) -> tuple[str, str]:
        """Test Kalshi API connectivity.

        Returns:
            Tuple of (status, details) where status is 'healthy', 'degraded', 'error', or 'unknown'
        """
        api_env = self._get_api_environment()

        try:
            from precog.api_connectors.kalshi_client import KalshiClient

            client = KalshiClient(use_demo=api_env == "demo")
            # Try to get exchange status - a lightweight call
            status = client.get_exchange_status()
            if status.get("trading_active", False):
                env_label = "DEMO" if api_env == "demo" else "LIVE"
                return ("healthy", f"[{env_label}] Trading active")
            return ("degraded", "Exchange not trading")
        except ImportError:
            return ("unknown", "Client unavailable")
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                return ("error", "Auth failed - check API keys")
            if "timeout" in error_msg.lower():
                return ("degraded", "Timeout - slow connection")
            return ("error", f"Error: {error_msg[:25]}")

    def _get_scheduler_health(self) -> tuple[str, str, int, int]:
        """Get scheduler service health status.

        Returns:
            Tuple of (status, details, running_count, total_count)
        """
        try:
            from precog.database.crud_schedulers import list_scheduler_services

            services = list_scheduler_services(include_stale=True, stale_threshold_seconds=120)

            if not services:
                return ("unknown", "No services registered", 0, 0)

            running = sum(
                1 for s in services if s.get("status") == "running" and not s.get("is_stale", False)
            )
            stale = sum(1 for s in services if s.get("is_stale", False))
            total = len(services)

            if stale > 0:
                return ("degraded", f"{stale} stale service(s)", running, total)
            if running == 0:
                return ("error", "All services stopped", running, total)
            if running < total:
                return ("degraded", f"{running}/{total} running", running, total)
            return ("healthy", f"{running}/{total} running", running, total)
        except ImportError:
            return ("unknown", "CRUD unavailable", 0, 0)
        except Exception as e:
            return ("error", f"Error: {str(e)[:25]}", 0, 0)

    def _load_metrics(self) -> None:
        """Load current system metrics.

        Educational Note:
            This method attempts to load REAL metrics from:
            1. Database connection test (connection.py)
            2. Scheduler services (crud_operations.py)
            3. API connectivity tests (kalshi_client.py)

            Falls back to demo data in demo mode or when services unavailable.
        """
        table = self.query_one("#metrics-table", DataTable)
        table.clear()

        data_mode = self._get_data_source_mode()
        log = self.query_one("#live-logs", RichLog)
        now = datetime.now(UTC).strftime("%H:%M:%S")

        # Track what real data we could load
        real_data_loaded = False
        status_messages = []

        # --- Test Database Health ---
        if data_mode != "demo":
            db_status, db_details = self._test_database_health()
            self._update_health_card("db", db_status, db_details)
            if db_status == "healthy":
                real_data_loaded = True
                log.write(f"[dim]{now}[/] [green]INFO[/] Database connection verified")
            elif db_status == "error":
                log.write(f"[dim]{now}[/] [red]ERROR[/] Database: {db_details}")
        else:
            self._update_health_card("db", "healthy", "Demo mode - skipped")

        # --- Test Kalshi API Health ---
        if data_mode != "demo":
            kalshi_status, kalshi_details = self._test_kalshi_api_health()
            self._update_health_card("kalshi", kalshi_status, kalshi_details)
            if kalshi_status == "healthy":
                real_data_loaded = True
                log.write(f"[dim]{now}[/] [green]INFO[/] Kalshi API: {kalshi_details}")
            elif kalshi_status in ("error", "degraded"):
                log.write(f"[dim]{now}[/] [yellow]WARN[/] Kalshi API: {kalshi_details}")
        else:
            api_env = self._get_api_environment()
            env_label = "DEMO" if api_env == "demo" else "LIVE"
            self._update_health_card("kalshi", "unknown", f"[{env_label}] Demo mode")

        # --- Test ESPN API Health ---
        # ESPN doesn't require auth, so we just show static status
        self._update_health_card("espn", "healthy", "Public API - no auth required")

        # --- Get Scheduler Health ---
        if data_mode != "demo":
            sched_status, sched_details, running, total = self._get_scheduler_health()
            self._update_health_card("scheduler", sched_status, sched_details)
            if total > 0:
                real_data_loaded = True
                log.write(f"[dim]{now}[/] [blue]DEBUG[/] Scheduler: {running}/{total} services")
            else:
                status_messages.append("No scheduler services - run: precog scheduler start")
        else:
            self._update_health_card("scheduler", "unknown", "Demo mode - skipped")

        # --- Load Metrics Table ---
        if data_mode == "demo" or not real_data_loaded:
            # Load demo metrics
            demo_metrics = [
                ("DB Pool Usage", "20%", "10%", "45%", "22%"),
                ("DB Query Latency", "12ms", "5ms", "89ms", "18ms"),
                ("Kalshi Rate Limit", "45/100", "0/100", "95/100", "35/100"),
                ("ESPN Poll Rate", "60s", "60s", "60s", "60s"),
                ("Active Positions", "3", "0", "12", "4"),
                ("Open Orders", "1", "0", "5", "2"),
                ("Memory Usage", "245MB", "180MB", "312MB", "238MB"),
                ("Error Rate", "0.3/min", "0/min", "2.1/min", "0.4/min"),
            ]
            for metric in demo_metrics:
                table.add_row(*metric)

            # Show appropriate status message
            if data_mode == "demo":
                self.query_one("#monitor-status", Static).update(
                    "[bold cyan on #003344]  DEMO MODE  [/] "
                    "[dim]Showing demonstration metrics. Change mode in Settings.[/]"
                )
            else:
                self.query_one("#monitor-status", Static).update(
                    "[bold yellow on #3D2A00]  SAMPLE DATA  [/] "
                    "[dim]Could not load real metrics. Check connections with 't' key.[/]"
                )
        else:
            # Load real metrics where available
            self._load_real_metrics(table)
            api_env = self._get_api_environment()
            env_label = "[DEMO API]" if api_env == "demo" else "[LIVE API]"
            self.query_one("#monitor-status", Static).update(
                f"[bold green on #003D00]  LIVE DATA  [/] {env_label} "
                "[dim]Monitoring real system metrics. Press 't' to test connections.[/]"
            )

    def _update_health_card(self, card_prefix: str, status: str, details: str) -> None:
        """Update a health card's status and details.

        Args:
            card_prefix: The card ID prefix (e.g., 'db', 'kalshi', 'scheduler')
            status: Health status ('healthy', 'degraded', 'error', 'unknown')
            details: Detail text to display
        """
        status_display = {
            "healthy": "[bold green]HEALTHY[/]",
            "degraded": "[bold yellow]DEGRADED[/]",
            "error": "[bold red]ERROR[/]",
            "unknown": "[dim]UNKNOWN[/]",
        }.get(status, "[dim]UNKNOWN[/]")

        try:
            self.query_one(f"#{card_prefix}-status", Static).update(status_display)
            self.query_one(f"#{card_prefix}-details", Static).update(details)
        except Exception:
            pass  # Card might not exist yet

    def _load_real_metrics(self, table: DataTable) -> None:
        """Load real metrics from available sources.

        Educational Note:
            This method attempts to gather actual metrics from the system.
            Since we don't have a full metrics collection system yet, we
            provide real status where possible and placeholder values where not.
        """
        # Try to get position and order counts from database
        positions_count = "N/A"
        orders_count = "N/A"

        # TODO: Implement get_open_positions_count / get_open_orders_count
        # These functions don't exist yet — placeholders for Phase 2.

        metrics = [
            ("DB Connection", "Connected", "-", "-", "-"),
            ("Kalshi API", "Connected", "-", "-", "-"),
            ("ESPN API", "Available", "-", "-", "-"),
            ("Active Positions", positions_count, "-", "-", "-"),
            ("Open Orders", orders_count, "-", "-", "-"),
            ("Scheduler Services", "See cards above", "-", "-", "-"),
        ]

        for metric in metrics:
            table.add_row(*metric)

    def _init_log_stream(self) -> None:
        """Initialize the live log stream with status information.

        Educational Note:
            Instead of showing fake demo events, we now show the actual
            startup status and any initial health check results.
        """
        log = self.query_one("#live-logs", RichLog)
        now = datetime.now(UTC).strftime("%H:%M:%S")

        data_mode = self._get_data_source_mode()
        api_env = self._get_api_environment()

        # Log initialization status
        log.write(f"[dim]{now}[/] [green]INFO[/] Monitoring dashboard initialized")
        log.write(f"[dim]{now}[/] [blue]DEBUG[/] Data source mode: {data_mode}, API env: {api_env}")

        if data_mode == "demo":
            log.write(f"[dim]{now}[/] [cyan]INFO[/] Running in demo mode - metrics simulated")
        else:
            log.write(f"[dim]{now}[/] [cyan]INFO[/] Testing connections...")
            log.write(f"[dim]{now}[/] [dim]Press 't' to manually test all connections[/]")

    def _refresh_data(self) -> None:
        """Refresh all dashboard data."""
        self._load_metrics()

        # Update last refresh time
        self.query_one("#last-refresh", Static).update(
            f"[dim]Last refresh: {datetime.now(UTC).strftime('%H:%M:%S')} UTC[/]"
        )

        # Add log entry
        log = self.query_one("#live-logs", RichLog)
        log.write(
            f"[dim]{datetime.now(UTC).strftime('%H:%M:%S')}[/] [blue]DEBUG[/] Dashboard refreshed"
        )

    def action_refresh(self) -> None:
        """Manual refresh."""
        self._refresh_data()
        self.app.notify("Dashboard refreshed")

    def action_test_connections(self) -> None:
        """Manually test all connections and update health cards.

        Educational Note:
            This provides an explicit way to test connectivity without
            waiting for the auto-refresh interval. Useful for diagnosing
            connection issues after configuration changes.
        """
        log = self.query_one("#live-logs", RichLog)
        now = datetime.now(UTC).strftime("%H:%M:%S")

        log.write(f"[dim]{now}[/] [cyan]INFO[/] === Testing all connections ===")
        self.app.notify("Testing connections...")

        results = []

        # Test database
        db_status, db_details = self._test_database_health()
        self._update_health_card("db", db_status, db_details)
        results.append(f"Database: {db_status}")
        status_color = (
            "green" if db_status == "healthy" else "red" if db_status == "error" else "yellow"
        )
        log.write(f"[dim]{now}[/] [{status_color}]{db_status.upper()}[/] Database: {db_details}")

        # Test Kalshi API
        kalshi_status, kalshi_details = self._test_kalshi_api_health()
        self._update_health_card("kalshi", kalshi_status, kalshi_details)
        results.append(f"Kalshi: {kalshi_status}")
        status_color = (
            "green"
            if kalshi_status == "healthy"
            else "red"
            if kalshi_status == "error"
            else "yellow"
        )
        log.write(
            f"[dim]{now}[/] [{status_color}]{kalshi_status.upper()}[/] Kalshi API: {kalshi_details}"
        )

        # ESPN is always healthy (public API)
        self._update_health_card("espn", "healthy", "Public API - OK")
        results.append("ESPN: healthy")
        log.write(f"[dim]{now}[/] [green]HEALTHY[/] ESPN API: Public API - OK")

        # Test scheduler
        sched_status, sched_details, _running, _total = self._get_scheduler_health()
        self._update_health_card("scheduler", sched_status, sched_details)
        results.append(f"Scheduler: {sched_status}")
        status_color = (
            "green" if sched_status == "healthy" else "red" if sched_status == "error" else "yellow"
        )
        log.write(
            f"[dim]{now}[/] [{status_color}]{sched_status.upper()}[/] Scheduler: {sched_details}"
        )

        # Summary notification
        healthy_count = sum(1 for r in results if "healthy" in r)
        total_count = len(results)
        if healthy_count == total_count:
            self.app.notify(f"All {total_count} connections healthy!", severity="information")
        else:
            self.app.notify(
                f"{healthy_count}/{total_count} connections healthy",
                severity="warning" if healthy_count > 0 else "error",
            )

        log.write(f"[dim]{now}[/] [cyan]INFO[/] === Connection test complete ===")

    def action_toggle_logs(self) -> None:
        """Toggle log panel visibility."""
        log_container = self.query_one("#log-container")
        log_container.toggle_class("collapsed")

    def action_go_back(self) -> None:
        """Return to main menu."""
        self.app.pop_screen()
