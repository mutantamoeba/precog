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
from textual.screen import Screen
from textual.widgets import Button, DataTable, Label, RichLog, Static


class SchedulerControlScreen(Screen):
    """
    Scheduler control screen for managing background services.

    Displays the status of all registered scheduler services and
    provides controls to start, stop, or restart them.

    Educational Note:
        The scheduler uses a heartbeat pattern where services
        periodically update their status in the database. A service
        is considered "stale" if its last heartbeat exceeds the
        configured threshold (typically 2x the poll interval).
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        ("r", "refresh", "Refresh"),
        ("s", "start_all", "Start All"),
        ("x", "stop_all", "Stop All"),
        ("l", "toggle_logs", "Toggle Logs"),
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Create the scheduler control layout."""
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

    def _load_services(self) -> None:
        """Load scheduler services from the database."""
        table = self.query_one("#service-table", DataTable)
        table.clear()

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
            self.query_one("#scheduler-status", Static).update(
                f"[green]Loaded {len(services)} services[/]"
            )

        except ImportError:
            self._load_demo_data(table)
        except Exception as e:
            self.query_one("#scheduler-status", Static).update(
                f"[red]Error loading services: {e}[/]"
            )
            self._load_demo_data(table)

    def _load_demo_data(self, table: DataTable) -> None:
        """Load demonstration data when database is unavailable."""
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
        self.query_one("#scheduler-status", Static).update(
            "[yellow]Showing demo data (database unavailable)[/]"
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

    def _control_selected(self, action: str) -> None:
        """Control the selected service."""
        table = self.query_one("#service-table", DataTable)

        if table.cursor_row is None:
            self.app.notify("Select a service first", severity="warning")  # type: ignore[unreachable]
            return

        row_data = table.get_row_at(table.cursor_row)
        if row_data:
            service_name = row_data[0]
            self.app.notify(f"{action.title()} '{service_name}' - Not implemented yet")

            # Log the action
            log = self.query_one("#service-logs", RichLog)
            log.write(
                f"[dim]{datetime.now(UTC).strftime('%H:%M:%S')}[/] {action.title()} requested for {service_name}"
            )

    def action_refresh(self) -> None:
        """Refresh service data."""
        self._load_services()
        self.app.notify("Services refreshed")

    def action_start_all(self) -> None:
        """Start all stopped services."""
        self.app.notify("Starting all services - Not implemented yet")

    def action_stop_all(self) -> None:
        """Stop all running services."""
        self.app.notify("Stopping all services - Not implemented yet")

    def action_toggle_logs(self) -> None:
        """Toggle the log panel visibility."""
        log_panel = self.query_one("#log-panel")
        log_panel.toggle_class("collapsed")

    def action_go_back(self) -> None:
        """Return to main menu."""
        self.app.pop_screen()
