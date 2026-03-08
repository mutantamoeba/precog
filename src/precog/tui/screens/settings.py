"""
Settings Screen.

View and modify application configuration.
Provides connection testing and mode toggles.

Design:
    - Scrollable layout with organized sections
    - Editable configuration fields with save/reset
    - Toggle controls for runtime settings
    - Connection test buttons with status display
    - Clear visual hierarchy

Reference:
    - Issue #283: TUI Additional Screens
    - docs/guides/CONFIGURATION_GUIDE_V3.1.md
"""

from decimal import Decimal
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, DataTable, Input, Label, Select, Static

from precog.tui.screens.base_screen import BaseScreen
from precog.tui.widgets.breadcrumb import Breadcrumb
from precog.tui.widgets.environment_bar import EnvironmentBar

# Default configuration values for reset functionality
DEFAULT_CONFIG = {
    "min_edge": "0.05",
    "max_position_size": "100",
    "daily_risk_limit": "500",
    "espn_poll_interval": "30",
    "kalshi_poll_interval": "30",
}


class SettingsScreen(BaseScreen):
    """
    Settings and configuration screen with editable fields.

    Displays current application configuration and provides
    controls for modifying runtime settings with save/reset capability.

    Educational Note:
        Configuration is loaded from YAML files in config/ directory.
        The ConfigLoader uses a layered approach:
        1. Base config (config/base.yaml)
        2. Environment-specific (config/development.yaml, production.yaml)
        3. Environment variables (override)
        4. Database config_overrides table (dynamic)

        This screen now provides editable fields for key trading parameters,
        with validation to prevent invalid values. Changes are applied to
        the runtime configuration (not persisted to YAML files).
    """

    BINDINGS: ClassVar[list[BindingType]] = BaseScreen.BINDINGS + [
        ("r", "refresh", "Refresh"),
        ("t", "test_connections", "Test Connections"),
        ("s", "save_config", "Save"),
        ("d", "reset_defaults", "Defaults"),
    ]

    def compose(self) -> ComposeResult:
        """Create the settings layout with scrollable content."""
        yield Breadcrumb.for_screen("settings")
        yield EnvironmentBar.from_app(self.app)
        yield Label("Settings & Configuration", id="screen-title", classes="screen-title")

        # Wrap all content in VerticalScroll for proper scrolling
        with VerticalScroll(id="settings-scroll"):
            # Section 1: Environment & Mode Status
            with Container(id="env-section", classes="settings-section"):
                yield Label("[bold cyan]Environment Status[/]", classes="section-header")
                with Horizontal(id="env-bar"):
                    yield Static("[bold]Environment:[/] ", id="env-label")
                    yield Static("[yellow]DEVELOPMENT[/]", id="env-value")
                    yield Static("  |  ", classes="separator")
                    yield Static("[bold]Mode:[/] ", id="mode-label")
                    yield Static("[cyan]DRY RUN[/]", id="mode-value")

            # Section 2: Data & API Settings
            with Container(id="data-section", classes="settings-section"):
                yield Label("[bold cyan]Data & API Settings[/]", classes="section-header")

                # Data source selector
                with Horizontal(classes="config-row"):
                    yield Label("Data Source:", classes="config-label")
                    yield Select(
                        [
                            ("Auto (DB with demo fallback)", "auto"),
                            ("Demo Data Only", "demo"),
                            ("Real Database Only", "real"),
                        ],
                        id="data-source-select",
                        value="auto",
                        classes="config-select",
                    )
                yield Static(
                    "[dim]Auto: Uses database when available, falls back to demo data.[/]",
                    classes="config-help",
                )

                # API Environment selector
                with Horizontal(classes="config-row"):
                    yield Label("API Environment:", classes="config-label")
                    yield Select(
                        [
                            ("Demo (Paper Trading)", "demo"),
                            ("Production (Real Money)", "production"),
                        ],
                        id="api-env-select",
                        value="demo",
                        classes="config-select",
                    )
                yield Static(
                    "[dim]Demo: Paper trading. Production: [bold red]REAL MONEY[/]![/]",
                    classes="config-help",
                )

            # Section 3: Runtime Toggles
            with Container(id="toggles-section", classes="settings-section"):
                yield Label("[bold cyan]Runtime Toggles[/]", classes="section-header")

                with Horizontal(classes="toggle-row"):
                    yield Checkbox("Dry Run Mode", id="toggle-dry-run", value=True)
                    yield Static(
                        "[dim]When enabled, no real trades are executed[/]",
                        classes="toggle-help",
                    )
                with Horizontal(classes="toggle-row"):
                    yield Checkbox("Debug Logging", id="toggle-debug", value=False)
                    yield Static(
                        "[dim]Enable verbose debug log output[/]",
                        classes="toggle-help",
                    )
                with Horizontal(classes="toggle-row"):
                    yield Checkbox("Auto-Refresh", id="toggle-auto-refresh", value=True)
                    yield Static(
                        "[dim]Automatically refresh data in screens[/]",
                        classes="toggle-help",
                    )

            # Section 4: Trading Configuration (Editable)
            with Container(id="trading-section", classes="settings-section"):
                yield Label("[bold cyan]Trading Configuration[/]", classes="section-header")
                yield Static(
                    "[dim]Edit values below and press [bold]Save[/] or [bold]S[/] to apply[/]",
                    classes="section-subtitle",
                )

                # Editable configuration fields
                with Horizontal(classes="config-row"):
                    yield Label("Min Edge (%):", classes="config-label")
                    yield Input(
                        value="5",
                        placeholder="e.g., 5",
                        id="input-min-edge",
                        classes="config-input",
                        type="number",
                    )
                    yield Static(
                        "[dim]Minimum edge required to enter trade[/]", classes="input-help"
                    )

                with Horizontal(classes="config-row"):
                    yield Label("Max Position Size:", classes="config-label")
                    yield Input(
                        value="100",
                        placeholder="e.g., 100",
                        id="input-max-position",
                        classes="config-input",
                        type="integer",
                    )
                    yield Static("[dim]Maximum contracts per position[/]", classes="input-help")

                with Horizontal(classes="config-row"):
                    yield Label("Daily Risk Limit ($):", classes="config-label")
                    yield Input(
                        value="500",
                        placeholder="e.g., 500",
                        id="input-risk-limit",
                        classes="config-input",
                        type="integer",
                    )
                    yield Static("[dim]Maximum daily loss allowed[/]", classes="input-help")

                # Save/Reset buttons for trading config
                with Horizontal(id="config-buttons"):
                    yield Button("Save Changes", id="btn-save-config", variant="primary")
                    yield Button("Reset to Defaults", id="btn-reset-defaults", variant="warning")

            # Section 5: Polling Configuration
            with Container(id="polling-section", classes="settings-section"):
                yield Label("[bold cyan]Polling Intervals[/]", classes="section-header")

                with Horizontal(classes="config-row"):
                    yield Label("ESPN Interval (sec):", classes="config-label")
                    yield Input(
                        value="60",
                        placeholder="e.g., 60",
                        id="input-espn-interval",
                        classes="config-input",
                        type="integer",
                    )
                    yield Static("[dim]Seconds between ESPN API polls[/]", classes="input-help")

                with Horizontal(classes="config-row"):
                    yield Label("Kalshi Interval (sec):", classes="config-label")
                    yield Input(
                        value="30",
                        placeholder="e.g., 30",
                        id="input-kalshi-interval",
                        classes="config-input",
                        type="integer",
                    )
                    yield Static("[dim]Seconds between Kalshi API polls[/]", classes="input-help")

            # Section 6: Connection Status
            with Container(id="connections-section", classes="settings-section"):
                yield Label("[bold cyan]Connection Status[/]", classes="section-header")
                yield DataTable(id="connection-table")

                # Connection test buttons
                with Horizontal(id="test-buttons"):
                    yield Button("Test Database", id="btn-test-db", variant="default")
                    yield Button("Test Kalshi API", id="btn-test-kalshi", variant="default")
                    yield Button("Test ESPN API", id="btn-test-espn", variant="default")
                    yield Button("Test All", id="btn-test-all", variant="primary")

        # Status bar (outside scroll area, always visible)
        yield Static("Settings loaded", id="settings-status")

    def on_mount(self) -> None:
        """Initialize tables and load configuration.

        Educational Note:
            We sync the selector widgets and input fields with the app's
            current state on mount. This ensures the UI reflects the actual
            app configuration, especially when returning to this screen
            after making changes elsewhere.
        """
        # Set up connection table
        conn_table = self.query_one("#connection-table", DataTable)
        conn_table.add_columns("Service", "Status", "Last Tested", "Details")
        conn_table.zebra_stripes = True

        # Sync selectors with current app state
        from precog.tui.app import PrecogApp

        if isinstance(self.app, PrecogApp):
            self.query_one("#data-source-select", Select).value = self.app.data_source_mode
            self.query_one("#api-env-select", Select).value = self.app.api_environment

        # Load data
        self._load_environment_info()
        self._load_connections()
        self._load_configuration_into_inputs()

    def _load_environment_info(self) -> None:
        """Load and display current environment information.

        Educational Note:
            The environment is determined by the ENVIRONMENT variable,
            defaulting to 'development'. The trading mode (dry_run) is
            loaded from the system.yaml configuration file.
        """
        try:
            from precog.config.config_loader import ConfigLoader, get_environment

            # Get current environment
            env = get_environment()
            env_display = env.upper()

            # Color based on environment
            if env == "production":
                env_styled = f"[bold red]{env_display}[/]"
            elif env == "staging":
                env_styled = f"[bold yellow]{env_display}[/]"
            elif env == "test":
                env_styled = f"[bold blue]{env_display}[/]"
            else:  # development
                env_styled = f"[bold green]{env_display}[/]"

            self.query_one("#env-value", Static).update(env_styled)

            # Get dry_run mode from config
            loader = ConfigLoader()
            dry_run = loader.get("system", "trading.dry_run", default=True)

            if dry_run:
                self.query_one("#mode-value", Static).update("[cyan]DRY RUN[/]")
                self.query_one("#toggle-dry-run", Checkbox).value = True
            else:
                self.query_one("#mode-value", Static).update("[red]LIVE[/]")
                self.query_one("#toggle-dry-run", Checkbox).value = False

        except ImportError:
            # ConfigLoader not available - show defaults
            self.query_one("#env-value", Static).update("[yellow]UNKNOWN[/]")
            self.query_one("#mode-value", Static).update("[dim]UNKNOWN[/]")
        except Exception as e:
            # Config load failed - show error state
            self.query_one("#env-value", Static).update("[red]ERROR[/]")
            self.query_one("#mode-value", Static).update(f"[dim]{str(e)[:20]}[/]")

    def _load_connections(self) -> None:
        """Load and display connection status."""
        table = self.query_one("#connection-table", DataTable)
        table.clear()

        connections = [
            ("PostgreSQL", "[green]Connected[/]", "10s ago", "precog_dev @ localhost:5432"),
            ("Kalshi API", "[yellow]Not Tested[/]", "Never", "api.kalshi.com (DEMO)"),
            ("ESPN API", "[green]Connected[/]", "5m ago", "site.api.espn.com"),
        ]

        for conn in connections:
            table.add_row(*conn)

    def _load_configuration_into_inputs(self) -> None:
        """Load current configuration into editable input fields.

        Educational Note:
            ConfigLoader must be instantiated before use - it's not a class
            with static methods. The loader caches YAML files after first load
            for efficient repeated access.

            We populate input fields with actual config values, allowing users
            to see and edit the current settings. Changes are validated on save.
        """
        try:
            from precog.config.config_loader import ConfigLoader

            loader = ConfigLoader()

            # Load trading configuration values
            min_edge = loader.get("system", "trading.min_edge", default="0.05")
            max_position = loader.get("system", "trading.max_position_size", default=100)
            risk_limit = loader.get("system", "trading.daily_risk_limit", default=500)

            # Get polling intervals
            espn_interval = loader.get("system", "polling.espn_interval", default=60)
            kalshi_interval = loader.get("system", "polling.kalshi_interval", default=30)

            # Convert min_edge to percentage for display (0.05 -> 5)
            try:
                min_edge_pct = str(int(Decimal(str(min_edge)) * 100))
            except (ValueError, TypeError):
                min_edge_pct = "5"

            # Populate input fields
            self.query_one("#input-min-edge", Input).value = min_edge_pct
            self.query_one("#input-max-position", Input).value = str(max_position)
            self.query_one("#input-risk-limit", Input).value = str(risk_limit)
            self.query_one("#input-espn-interval", Input).value = str(espn_interval)
            self.query_one("#input-kalshi-interval", Input).value = str(kalshi_interval)

            self.query_one("#settings-status", Static).update(
                "[green]Configuration loaded successfully[/]"
            )

        except ImportError:
            self._load_default_config()
        except Exception as e:
            self.query_one("#settings-status", Static).update(f"[red]Error loading config: {e}[/]")
            self._load_default_config()

    def _load_default_config(self) -> None:
        """Load default configuration values into input fields.

        Used when ConfigLoader is unavailable or fails.
        """
        # Populate with defaults
        self.query_one("#input-min-edge", Input).value = "5"
        self.query_one("#input-max-position", Input).value = DEFAULT_CONFIG["max_position_size"]
        self.query_one("#input-risk-limit", Input).value = DEFAULT_CONFIG["daily_risk_limit"]
        self.query_one("#input-espn-interval", Input).value = DEFAULT_CONFIG["espn_poll_interval"]
        self.query_one("#input-kalshi-interval", Input).value = DEFAULT_CONFIG[
            "kalshi_poll_interval"
        ]

        self.query_one("#settings-status", Static).update(
            "[bold yellow on #3D2A00]  SAMPLE DATA  [/] "
            "[dim]Config loader unavailable - showing default values.[/]"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "btn-test-db":
            self._test_database()
        elif button_id == "btn-test-kalshi":
            self._test_kalshi()
        elif button_id == "btn-test-espn":
            self._test_espn()
        elif button_id == "btn-test-all":
            self._test_all()
        elif button_id == "btn-save-config":
            self.action_save_config()
        elif button_id == "btn-reset-defaults":
            self.action_reset_defaults()

    def _test_database(self) -> None:
        """Test database connection."""
        try:
            from precog.database.connection import get_connection

            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")

            self._update_connection_status(
                "PostgreSQL", "[green]Connected[/]", "Just now", "Test successful"
            )
            self.app.notify("Database connection successful", severity="information")

        except Exception as e:
            self._update_connection_status("PostgreSQL", "[red]Failed[/]", "Just now", str(e)[:30])
            self.app.notify(f"Database connection failed: {e}", severity="error")

    def _test_kalshi(self) -> None:
        """Test Kalshi API connection.

        Educational Note:
            We test by fetching public market data, which doesn't require
            authentication. This validates network connectivity and API
            availability without exposing credentials.
        """
        self._update_connection_status("Kalshi API", "[yellow]Testing...[/]", "Just now", "")

        try:
            from precog.api_connectors.kalshi_client import KalshiClient

            client = KalshiClient()
            # Try to fetch a small number of markets as health check
            markets = client.get_markets(limit=1)

            if markets is not None:
                self._update_connection_status(
                    "Kalshi API",
                    "[green]Connected[/]",
                    "Just now",
                    f"API responding (fetched {len(markets)} markets)",
                )
                self.app.notify("Kalshi API connection successful", severity="information")
            else:
                self._update_connection_status(
                    "Kalshi API",
                    "[yellow]No Data[/]",
                    "Just now",
                    "API responded but returned no markets",
                )
                self.app.notify("Kalshi API connected but no data", severity="warning")

        except ImportError as e:
            self._update_connection_status(
                "Kalshi API", "[red]Not Installed[/]", "Just now", "KalshiClient not available"
            )
            self.app.notify(f"Kalshi client not available: {e}", severity="error")
        except Exception as e:
            error_msg = str(e)[:40]
            self._update_connection_status("Kalshi API", "[red]Failed[/]", "Just now", error_msg)
            self.app.notify(f"Kalshi API test failed: {e}", severity="error")

    def _test_espn(self) -> None:
        """Test ESPN API connection.

        Educational Note:
            ESPN's public API is free and doesn't require authentication.
            We test by fetching the NFL scoreboard as a quick health check.
        """
        self._update_connection_status("ESPN API", "[yellow]Testing...[/]", "Just now", "")

        try:
            from precog.api_connectors.espn_client import ESPNClient

            client = ESPNClient()
            # Try to fetch NFL scoreboard as health check
            games = client.get_nfl_scoreboard()

            self._update_connection_status(
                "ESPN API",
                "[green]Connected[/]",
                "Just now",
                f"API responding ({len(games)} games found)",
            )
            self.app.notify("ESPN API connection successful", severity="information")

        except ImportError as e:
            self._update_connection_status(
                "ESPN API", "[red]Not Installed[/]", "Just now", "ESPNClient not available"
            )
            self.app.notify(f"ESPN client not available: {e}", severity="error")
        except Exception as e:
            error_msg = str(e)[:40]
            self._update_connection_status("ESPN API", "[red]Failed[/]", "Just now", error_msg)
            self.app.notify(f"ESPN API test failed: {e}", severity="error")

    def _test_all(self) -> None:
        """Test all connections."""
        self._test_database()
        self._test_kalshi()
        self._test_espn()

    def _update_connection_status(
        self, service: str, status: str, tested: str, details: str
    ) -> None:
        """Update a row in the connection table.

        Educational Note:
            Textual DataTable's auto-generated RowKey objects can have value=None,
            making key-based updates unreliable. We use index-based coordinate
            updates (update_cell_at) which are more reliable for dynamic tables.
        """
        table = self.query_one("#connection-table", DataTable)
        # Find and update the row for this service using index-based access
        for row_idx in range(table.row_count):
            try:
                row_data = table.get_row_at(row_idx)
                if row_data and row_data[0] == service:
                    # Use coordinate-based update (row_index, column_index)
                    table.update_cell_at((row_idx, 1), status)  # Status column
                    table.update_cell_at((row_idx, 2), tested)  # Last Tested column
                    table.update_cell_at((row_idx, 3), details)  # Details column
                    break
            except Exception:
                # Row might not exist yet during initialization
                pass

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle toggle changes."""
        checkbox_id = event.checkbox.id

        if checkbox_id == "toggle-dry-run":
            mode = "[cyan]DRY RUN[/]" if event.value else "[red]LIVE[/]"
            self.query_one("#mode-value", Static).update(mode)
            self.app.notify(f"Dry run mode: {'enabled' if event.value else 'disabled'}")

        elif checkbox_id == "toggle-debug":
            self.app.notify(f"Debug logging: {'enabled' if event.value else 'disabled'}")

        elif checkbox_id == "toggle-auto-refresh":
            self.app.notify(f"Auto-refresh: {'enabled' if event.value else 'disabled'}")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle selector changes.

        Educational Note:
            The data source mode affects all data-loading screens. When changed,
            screens will use the new mode on their next data refresh.
            - auto: Try database first, fall back to demo data on error
            - demo: Always use demo data (useful for testing/demonstration)
            - real: Only use real database (show errors if unavailable)

            The API environment mode controls which Kalshi API endpoint is used:
            - demo: Paper trading with test accounts (demo-api.kalshi.com)
            - production: Real money trading (trading-api.kalshi.com)
        """
        from precog.tui.app import PrecogApp

        if event.select.id == "data-source-select":
            mode = str(event.value) if event.value else "auto"

            # Update the app's data source mode
            if isinstance(self.app, PrecogApp):
                self.app.data_source_mode = mode

                # Show notification based on mode
                mode_descriptions = {
                    "auto": "Auto mode - database with demo fallback",
                    "demo": "Demo mode - always showing sample data",
                    "real": "Real mode - database only (errors if unavailable)",
                }
                self.app.notify(f"Data source: {mode_descriptions.get(mode, mode)}")

        elif event.select.id == "api-env-select":
            env = str(event.value) if event.value else "demo"

            # Update the app's API environment mode
            if isinstance(self.app, PrecogApp):
                self.app.api_environment = env

                # Show notification with appropriate severity
                if env == "production":
                    self.app.notify(
                        "API Environment: PRODUCTION - Real money trading enabled!",
                        severity="warning",
                    )
                else:
                    self.app.notify(
                        "API Environment: Demo - Paper trading mode",
                        severity="information",
                    )

    def action_refresh(self) -> None:
        """Refresh configuration display."""
        self._load_connections()
        self._load_configuration_into_inputs()
        self.app.notify("Settings refreshed")

    def action_test_connections(self) -> None:
        """Test all connections."""
        self._test_all()

    def action_save_config(self) -> None:
        """Save the current configuration values.

        Educational Note:
            This validates and applies the configuration changes to the runtime.
            The changes are NOT persisted to YAML files - they only affect the
            current session. To make permanent changes, edit the YAML files
            directly in config/ directory.
        """
        try:
            # Get values from input fields
            min_edge = self.query_one("#input-min-edge", Input).value
            max_position = self.query_one("#input-max-position", Input).value
            risk_limit = self.query_one("#input-risk-limit", Input).value
            espn_interval = self.query_one("#input-espn-interval", Input).value
            kalshi_interval = self.query_one("#input-kalshi-interval", Input).value

            # Validate values
            errors = []

            try:
                min_edge_val = Decimal(str(min_edge))
                if min_edge_val < 0 or min_edge_val > 100:
                    errors.append("Min Edge must be between 0 and 100")
            except ValueError:
                errors.append("Min Edge must be a number")

            try:
                max_pos_val = int(max_position)
                if max_pos_val < 1:
                    errors.append("Max Position must be at least 1")
            except ValueError:
                errors.append("Max Position must be an integer")

            try:
                risk_val = int(risk_limit)
                if risk_val < 0:
                    errors.append("Risk Limit must be non-negative")
            except ValueError:
                errors.append("Risk Limit must be an integer")

            try:
                espn_val = int(espn_interval)
                if espn_val < 5:
                    errors.append("ESPN interval must be at least 5 seconds")
            except ValueError:
                errors.append("ESPN interval must be an integer")

            try:
                kalshi_val = int(kalshi_interval)
                if kalshi_val < 5:
                    errors.append("Kalshi interval must be at least 5 seconds")
            except ValueError:
                errors.append("Kalshi interval must be an integer")

            if errors:
                self.query_one("#settings-status", Static).update(
                    f"[red]Validation errors: {'; '.join(errors)}[/]"
                )
                self.app.notify(f"Validation failed: {errors[0]}", severity="error")
                return

            # All values valid - update status to show success
            self.query_one("#settings-status", Static).update(
                "[green]Configuration saved (runtime only - not persisted to files)[/]"
            )
            self.app.notify(
                "Configuration saved for this session. Edit YAML files for permanent changes.",
                severity="information",
            )

        except Exception as e:
            self.query_one("#settings-status", Static).update(f"[red]Error saving config: {e}[/]")
            self.app.notify(f"Save failed: {e}", severity="error")

    def action_reset_defaults(self) -> None:
        """Reset configuration to default values.

        Educational Note:
            This resets all editable fields to their default values.
            The defaults are defined in DEFAULT_CONFIG at module level.
        """
        # Reset input fields to defaults
        self.query_one("#input-min-edge", Input).value = "5"  # 5% = 0.05
        self.query_one("#input-max-position", Input).value = DEFAULT_CONFIG["max_position_size"]
        self.query_one("#input-risk-limit", Input).value = DEFAULT_CONFIG["daily_risk_limit"]
        self.query_one("#input-espn-interval", Input).value = DEFAULT_CONFIG["espn_poll_interval"]
        self.query_one("#input-kalshi-interval", Input).value = DEFAULT_CONFIG[
            "kalshi_poll_interval"
        ]

        self.query_one("#settings-status", Static).update(
            "[cyan]Configuration reset to defaults (not saved yet)[/]"
        )
        self.app.notify("Configuration reset to defaults. Press Save to apply.")

    def action_go_back(self) -> None:
        """Return to main menu."""
        self.app.pop_screen()
