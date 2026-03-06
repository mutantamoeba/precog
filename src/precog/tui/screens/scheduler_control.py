"""
Scheduler Control Screen.

View and control the background scheduler services.
Displays ESPN poller, Kalshi poller, and other background services.

Design:
    - Service list with status indicators
    - Start/stop/restart controls
    - Last update timestamps
    - Error log viewer

Reference:
    - Issue #283: TUI Additional Screens
    - ADR-101: Unified Scheduler Service Architecture
"""

from datetime import UTC, datetime
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Container, Horizontal
from textual.widgets import Button, DataTable, Label, RichLog, Static

from precog.tui.screens.base_screen import BaseScreen
from precog.tui.widgets.breadcrumb import Breadcrumb
from precog.tui.widgets.environment_bar import EnvironmentBar


class SchedulerControlScreen(BaseScreen):
    """
    Scheduler control screen for managing background services.

    Displays the status of all registered scheduler services and
    provides controls to start, stop, or restart them.

    Educational Note:
        The scheduler uses a heartbeat pattern where services
        periodically update their status in the database. A service
        is considered "stale" if its last heartbeat exceeds the
        configured threshold (typically 2x the poll interval).
        Inherits from BaseScreen to get global keybindings in footer.
    """

    BINDINGS: ClassVar[list[BindingType]] = BaseScreen.BINDINGS + [
        ("r", "refresh", "Refresh"),
        ("s", "start_all", "Start All"),
        ("x", "stop_all", "Stop All"),
        ("l", "toggle_logs", "Toggle Logs"),
    ]

    def compose(self) -> ComposeResult:
        """Create the scheduler control layout."""
        yield Breadcrumb.for_screen("scheduler_control")
        yield EnvironmentBar.from_app(self.app)
        yield Label("Scheduler Control", id="screen-title", classes="screen-title")

        # Summary bar
        with Horizontal(id="summary-bar"):
            yield Static("[bold]Services:[/] 0 running, 0 stopped", id="service-summary")
            yield Static("[bold]Last Update:[/] Never", id="last-update")

        # Service table
        with Container(id="table-container"):
            yield Label("Registered Services", classes="section-header")
            yield DataTable(id="service-table")

        # Control buttons
        with Horizontal(id="control-buttons"):
            yield Button("Start Selected", id="btn-start", variant="success")
            yield Button("Stop Selected", id="btn-stop", variant="error")
            yield Button("Restart Selected", id="btn-restart", variant="warning")
            yield Button("Refresh", id="btn-refresh", variant="default")

        # Log viewer (initially collapsed)
        with Container(id="log-panel"):
            yield Label("Service Logs", classes="section-header")
            yield RichLog(id="service-logs", highlight=True, markup=True)

        # Status bar
        yield Static("Loading services...", id="scheduler-status")

    def on_mount(self) -> None:
        """Initialize the service table and load data."""
        table = self.query_one("#service-table", DataTable)

        # Configure table columns
        table.add_columns(
            "Service",
            "Type",
            "Status",
            "Last Heartbeat",
            "Poll Interval",
            "Errors",
        )

        table.cursor_type = "row"
        table.zebra_stripes = True

        # Initialize log viewer
        log = self.query_one("#service-logs", RichLog)
        log.write("[dim]Waiting for log entries...[/]")

        # Load initial data
        self._load_services()

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

    def _load_services(self) -> None:
        """Load scheduler services from the database.

        Educational Note:
            The data source mode determines behavior:
            - "demo": Always use demo data, skip database query
            - "real": Only use database, show error if unavailable
            - "auto": Try database first, fall back to demo on error
        """
        table = self.query_one("#service-table", DataTable)
        table.clear()

        data_mode = self._get_data_source_mode()

        # Demo mode: Skip database, use demo data directly
        if data_mode == "demo":
            self._load_demo_data(table)
            return

        try:
            from precog.database.crud_operations import list_scheduler_services

            services = list_scheduler_services(include_stale=True, stale_threshold_seconds=120)

            running = 0
            stopped = 0

            for svc in services:
                status = svc.get("status", "unknown")
                is_stale = svc.get("is_stale", False)

                # Format status with color
                if status == "running" and not is_stale:
                    status_str = "[green]Running[/]"
                    running += 1
                elif status == "running" and is_stale:
                    status_str = "[yellow]Stale[/]"
                    stopped += 1
                elif status == "stopped":
                    status_str = "[dim]Stopped[/]"
                    stopped += 1
                elif status == "error":
                    status_str = "[red]Error[/]"
                    stopped += 1
                else:
                    status_str = f"[dim]{status}[/]"
                    stopped += 1

                # Format last heartbeat
                last_hb = svc.get("last_heartbeat")
                hb_str = self._format_time_ago(last_hb) if last_hb else "[dim]Never[/]"

                # Format poll interval
                interval = svc.get("poll_interval_seconds", 0)
                interval_str = f"{interval}s" if interval else "[dim]N/A[/]"

                # Format error count
                errors = svc.get("error_count", 0)
                error_str = str(errors) if errors == 0 else f"[red]{errors}[/]"

                table.add_row(
                    svc.get("service_name", "Unknown"),
                    svc.get("service_type", "unknown"),
                    status_str,
                    hb_str,
                    interval_str,
                    error_str,
                )

            self._update_summary(running, stopped)

            if len(services) == 0:
                # Database connected but no services registered
                self._load_demo_data(table, show_empty_message=True)
            else:
                # Count stale services to provide better feedback
                stale_count = sum(1 for s in services if s.get("is_stale", False))
                if stale_count > 0:
                    self.query_one("#scheduler-status", Static).update(
                        f"[bold yellow]⚠ {stale_count} service(s) are STALE[/] - "
                        "[dim]Heartbeat not received in 120+ seconds. "
                        "The scheduler process may have crashed or stopped.\n"
                        "To restart:[/] [bold white]precog scheduler start --kalshi --foreground[/]"
                    )
                else:
                    self.query_one("#scheduler-status", Static).update(
                        f"[green]Loaded {len(services)} services - all healthy[/]"
                    )

        except ImportError:
            if data_mode == "real":
                self.query_one("#scheduler-status", Static).update(
                    "[red]Database module not available - real mode requires database[/]"
                )
            else:
                self._load_demo_data(table, show_import_error=True)
        except Exception as e:
            if data_mode == "real":
                self.query_one("#scheduler-status", Static).update(f"[red]Database error: {e}[/]")
            else:
                self.query_one("#scheduler-status", Static).update(
                    f"[red]Error loading services: {e}[/]"
                )
                self._load_demo_data(table)

    def _load_demo_data(
        self,
        table: DataTable,
        show_empty_message: bool = False,
        show_import_error: bool = False,
    ) -> None:
        """Load demonstration data when database is unavailable or empty.

        Args:
            table: The DataTable to populate
            show_empty_message: If True, database is connected but no services exist
            show_import_error: If True, CRUD operations couldn't be imported

        Educational Note:
            This provides different status messages based on WHY demo data is shown:
            - No services registered: Need to start scheduler processes
            - Import error: CRUD operations not available (development mode)
            - Other exceptions: Database connection issue
        """
        demo_services = [
            ("ESPN Game Poller", "poller", "[green]Running[/]", "12s ago", "60s", "0"),
            ("ESPN Rankings Poller", "poller", "[green]Running[/]", "45s ago", "300s", "0"),
            ("Kalshi Market Poller", "poller", "[yellow]Stale[/]", "5m ago", "30s", "2"),
            ("Position Monitor", "monitor", "[green]Running[/]", "3s ago", "5s", "0"),
            ("Alert Dispatcher", "worker", "[dim]Stopped[/]", "1h ago", "10s", "0"),
        ]

        for svc in demo_services:
            table.add_row(*svc)

        self._update_summary(3, 2)

        # Provide context-appropriate status message with actionable instructions
        if show_empty_message:
            self.query_one("#scheduler-status", Static).update(
                "[bold cyan on #003344]  NO SERVICES RUNNING  [/]\n"
                "[dim]To start data collection, run in a terminal:[/]\n"
                "[bold white]  precog scheduler start --kalshi --foreground[/]\n"
                "[dim]Or for production with auto-restart:[/]\n"
                "[bold white]  precog scheduler start --kalshi --supervised --foreground[/]"
            )
        elif show_import_error:
            self.query_one("#scheduler-status", Static).update(
                "[bold yellow on #3D2A00]  SAMPLE DATA  [/] "
                "[dim]CRUD operations unavailable - running in UI-only mode. "
                "Install database dependencies to enable real service monitoring.[/]"
            )
        else:
            self.query_one("#scheduler-status", Static).update(
                "[bold yellow on #3D2A00]  SAMPLE DATA  [/] "
                "[dim]Database error - showing demonstration services. "
                "Check database connection and try again.[/]"
            )

        # Add demo log entries
        log = self.query_one("#service-logs", RichLog)
        log.clear()
        log.write("[dim]2025-12-26 10:30:45[/] [green]ESPN Game Poller[/] Started successfully")
        log.write("[dim]2025-12-26 10:30:46[/] [green]ESPN Rankings Poller[/] Started successfully")
        log.write(
            "[dim]2025-12-26 10:30:47[/] [yellow]Kalshi Market Poller[/] Connection timeout, retrying..."
        )
        log.write("[dim]2025-12-26 10:31:15[/] [red]Kalshi Market Poller[/] Failed after 3 retries")

    def _update_summary(self, running: int, stopped: int) -> None:
        """Update the summary bar."""
        self.query_one("#service-summary", Static).update(
            f"[bold]Services:[/] [green]{running} running[/], [dim]{stopped} stopped[/]"
        )
        self.query_one("#last-update", Static).update(
            f"[bold]Last Update:[/] {datetime.now(UTC).strftime('%H:%M:%S')}"
        )

    def _format_time_ago(self, dt: datetime) -> str:
        """Format a datetime as a relative time string."""
        now = datetime.now(UTC)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        delta = now - dt
        seconds = int(delta.total_seconds())

        if seconds < 60:
            return f"{seconds}s ago"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        if seconds < 86400:
            return f"{seconds // 3600}h ago"
        return f"{seconds // 86400}d ago"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle control button presses."""
        button_id = event.button.id

        if button_id == "btn-start":
            self._control_selected("start")
        elif button_id == "btn-stop":
            self._control_selected("stop")
        elif button_id == "btn-restart":
            self._control_selected("restart")
        elif button_id == "btn-refresh":
            self.action_refresh()

    def _get_api_environment(self) -> str:
        """Get the current API environment from the app."""
        from precog.tui.app import PrecogApp

        if isinstance(self.app, PrecogApp):
            return self.app.api_environment
        return "demo"

    def _control_selected(self, action: str) -> None:
        """Control the selected service.

        Educational Note:
            Textual DataTable's cursor_row returns the visual row index, but
            get_row_at() can fail if the table is empty or not yet populated.
            We must validate both that a row is selected AND that the table
            has data before attempting to access the row.

            For service control, we use poll_once() to run a single poll cycle
            rather than starting a background thread, which is more appropriate
            for a TUI interaction model.
        """
        table = self.query_one("#service-table", DataTable)
        cursor_row: int | None = table.cursor_row

        if cursor_row is None:
            self.app.notify("Select a service first", severity="warning")
            return

        # Validate table has data before accessing row
        if table.row_count == 0:
            self.app.notify("No services loaded yet", severity="warning")
            return

        if not table.is_valid_row_index(cursor_row):
            self.app.notify("Invalid row selected", severity="warning")
            return

        try:
            row_data = table.get_row_at(cursor_row)
            if row_data:
                service_name = str(row_data[0])
                log = self.query_one("#service-logs", RichLog)
                now = datetime.now(UTC).strftime("%H:%M:%S")

                if action == "start":
                    self._run_poll_once(service_name, log)
                elif action == "stop":
                    log.write(f"[dim]{now}[/] [yellow]Stop not available for {service_name}[/]")
                    log.write(
                        f"[dim]{now}[/] [dim]Scheduler processes run independently. "
                        "Use 'precog scheduler stop' in terminal.[/]"
                    )
                    self.app.notify(
                        "Use 'precog scheduler stop' in terminal to stop services",
                        severity="warning",
                    )
                elif action == "restart":
                    log.write(
                        f"[dim]{now}[/] [cyan]Restart = running poll-once for {service_name}[/]"
                    )
                    self._run_poll_once(service_name, log)

        except Exception as e:
            self.app.notify(f"Error accessing row: {e}", severity="error")

    def _run_poll_once(self, service_name: str, log: RichLog) -> None:
        """Run a single poll cycle for the specified service.

        Args:
            service_name: Name of the service to poll
            log: RichLog widget to write status messages

        Educational Note:
            Instead of trying to control external scheduler processes,
            we run poll_once() directly from the TUI. This:
            1. Immediately populates the database with fresh data
            2. Works regardless of whether background scheduler is running
            3. Provides instant feedback to the user
        """
        now = datetime.now(UTC).strftime("%H:%M:%S")
        api_env = self._get_api_environment()

        log.write(f"[dim]{now}[/] [cyan]Starting poll for {service_name}...[/]")
        self.app.notify(f"Polling {service_name}...")

        try:
            # Determine which poller to use based on service name
            service_lower = service_name.lower()

            if "kalshi" in service_lower:
                from precog.schedulers.kalshi_poller import KalshiMarketPoller

                poller = KalshiMarketPoller(
                    series_tickers=["KXNFLGAME"],
                    environment=api_env,
                )
                result = poller.poll_once()
                poller.kalshi_client.close()

                log.write(
                    f"[dim]{now}[/] [green]Kalshi: {result['items_fetched']} markets fetched, "
                    f"{result['items_updated']} updated, {result['items_created']} created[/]"
                )
                self.app.notify(
                    f"Kalshi: {result['items_fetched']} markets, {result['items_updated']} updated",
                    severity="information",
                )

            elif "espn" in service_lower:
                from precog.schedulers.espn_game_poller import ESPNGamePoller

                # Determine leagues based on service name
                leagues = ["nfl", "ncaaf"]

                poller = ESPNGamePoller(leagues=leagues)
                result = poller.poll_once()

                log.write(
                    f"[dim]{now}[/] [green]ESPN: {result['items_fetched']} games fetched, "
                    f"{result['items_updated']} updated[/]"
                )
                self.app.notify(
                    f"ESPN: {result['items_fetched']} games, {result['items_updated']} updated",
                    severity="information",
                )

            elif "position" in service_lower or "monitor" in service_lower:
                log.write(
                    f"[dim]{now}[/] [yellow]Position Monitor is read-only - no poll needed[/]"
                )
                self.app.notify("Position Monitor doesn't poll external APIs")

            elif "alert" in service_lower:
                log.write(f"[dim]{now}[/] [yellow]Alert Dispatcher is triggered by events[/]")
                self.app.notify("Alert Dispatcher doesn't poll - it responds to events")

            else:
                log.write(f"[dim]{now}[/] [yellow]Unknown service type: {service_name}[/]")
                self.app.notify(f"Unknown service: {service_name}", severity="warning")

            # Refresh the service list to show updated status
            self._load_services()

        except ValueError as e:
            error_msg = str(e)
            log.write(f"[dim]{now}[/] [red]Error: {error_msg}[/]")
            if "KALSHI_API_KEY" in error_msg or "KALSHI_PRIVATE_KEY" in error_msg:
                self.app.notify("Kalshi API credentials not configured", severity="error")
                log.write(
                    f"[dim]{now}[/] [dim]Set KALSHI_API_KEY and KALSHI_PRIVATE_KEY_PATH in .env[/]"
                )
            else:
                self.app.notify(f"Configuration error: {error_msg[:50]}", severity="error")

        except Exception as e:
            log.write(f"[dim]{now}[/] [red]Poll failed: {e}[/]")
            self.app.notify(f"Poll failed: {str(e)[:50]}", severity="error")

    def action_refresh(self) -> None:
        """Refresh service data."""
        self._load_services()
        self.app.notify("Services refreshed")

    def action_start_all(self) -> None:
        """Start all services by running poll-once for each.

        Educational Note:
            Rather than starting background processes, we run a single poll
            cycle for each service type. This immediately populates the database
            with fresh data from all sources.
        """
        log = self.query_one("#service-logs", RichLog)
        now = datetime.now(UTC).strftime("%H:%M:%S")

        log.write(f"[dim]{now}[/] [bold cyan]=== Starting all services (poll-once) ===[/]")
        self.app.notify("Starting poll for all services...")

        # Poll Kalshi
        self._run_poll_once("Kalshi Market Poller", log)

        # Poll ESPN
        self._run_poll_once("ESPN Game Poller", log)

        log.write(f"[dim]{now}[/] [bold cyan]=== All services polled ===[/]")

    def action_stop_all(self) -> None:
        """Stop all running services.

        Educational Note:
            The scheduler runs as a separate process, not within the TUI.
            To stop it, users need to run 'precog scheduler stop' in terminal
            or press Ctrl+C in the terminal running the scheduler.
        """
        log = self.query_one("#service-logs", RichLog)
        now = datetime.now(UTC).strftime("%H:%M:%S")

        log.write(f"[dim]{now}[/] [yellow]Stop All requested[/]")
        log.write(f"[dim]{now}[/] [dim]Scheduler processes run independently from TUI.[/]")
        log.write(f"[dim]{now}[/] [dim]To stop: Run 'precog scheduler stop' in terminal,[/]")
        log.write(f"[dim]{now}[/] [dim]or press Ctrl+C in the scheduler terminal.[/]")

        self.app.notify(
            "Use 'precog scheduler stop' in terminal",
            severity="warning",
        )

    def action_toggle_logs(self) -> None:
        """Toggle the log panel visibility."""
        log_panel = self.query_one("#log-panel")
        log_panel.toggle_class("collapsed")

    def action_go_back(self) -> None:
        """Return to main menu."""
        self.app.pop_screen()
