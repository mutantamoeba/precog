"""
Main Menu Screen.

The landing screen showing the application logo and navigation menu.
Provides access to all major functional areas.

Design:
    - ASCII art header (ACiD-inspired)
    - Clear menu options with keyboard shortcuts
    - Status bar showing connection state
"""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, Static

# Import screens for navigation
from precog.tui.screens.market_browser import MarketBrowserScreen
from precog.tui.screens.monitoring_dashboard import MonitoringDashboardScreen
from precog.tui.screens.position_viewer import PositionViewerScreen
from precog.tui.screens.scheduler_control import SchedulerControlScreen
from precog.tui.screens.settings import SettingsScreen
from precog.tui.widgets.header import AsciiHeader


class MenuOption(Button):
    """A styled menu option button."""

    def __init__(self, label: str, key: str, description: str, screen_id: str) -> None:
        """
        Create a menu option.

        Args:
            label: Display label for the option
            key: Keyboard shortcut key
            description: Brief description of the option
            screen_id: ID of the screen to navigate to
        """
        super().__init__(f"[{key}] {label}", id=f"menu_{screen_id}")
        self.screen_id = screen_id
        self.description = description


class MainMenuScreen(Screen):
    """
    Main menu screen with navigation to all functional areas.

    This is the landing screen users see when launching the TUI.
    Provides clear navigation with keyboard shortcuts.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        ("1", "goto_markets", "Markets"),
        ("2", "goto_positions", "Positions"),
        ("3", "goto_trades", "Trades"),
        ("4", "goto_scheduler", "Scheduler"),
        ("5", "goto_strategy", "Strategy"),
        ("6", "goto_models", "Models"),
        ("7", "goto_config", "Config"),
        ("8", "goto_diagnostics", "Diagnostics"),
    ]

    def compose(self) -> ComposeResult:
        """Create the main menu layout."""
        yield AsciiHeader()

        with Container(id="menu-container"):
            with Horizontal(id="menu-columns"):
                # Left column
                with Vertical(id="menu-left", classes="menu-column"):
                    yield Label("Navigation", classes="menu-section-header")
                    yield MenuOption(
                        "Market Overview",
                        "1",
                        "Live market prices and edge calculations",
                        "markets",
                    )
                    yield MenuOption(
                        "Positions",
                        "2",
                        "Current positions and P&L",
                        "positions",
                    )
                    yield MenuOption(
                        "Execute Trades",
                        "3",
                        "Order entry and execution",
                        "trades",
                    )
                    yield MenuOption(
                        "Scheduler",
                        "4",
                        "Control ESPN and Kalshi pollers",
                        "scheduler",
                    )

                # Right column
                with Vertical(id="menu-right", classes="menu-column"):
                    yield Label("Management", classes="menu-section-header")
                    yield MenuOption(
                        "Strategy Manager",
                        "5",
                        "Create and manage trading strategies",
                        "strategy",
                    )
                    yield MenuOption(
                        "Model Manager",
                        "6",
                        "ML models and predictions",
                        "models",
                    )
                    yield MenuOption(
                        "Configuration",
                        "7",
                        "System settings and connections",
                        "config",
                    )
                    yield MenuOption(
                        "Diagnostics",
                        "8",
                        "Logs, health checks, debugging",
                        "diagnostics",
                    )

            # Status bar at bottom
            with Horizontal(id="status-bar"):
                yield Static("ESPN: [dim]Not connected[/]", id="status-espn")
                yield Static("Kalshi: [dim]Not connected[/]", id="status-kalshi")
                yield Static("DB: [dim]Checking...[/]", id="status-db")

    def on_mount(self) -> None:
        """Called when screen is mounted. Check connection status."""
        self._check_connections()

    def _check_connections(self) -> None:
        """Check and update connection status indicators."""
        # TODO: Implement actual connection checks
        # For now, show placeholder status
        self.query_one("#status-db", Static).update("DB: [green]Connected[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle menu button presses."""
        button = event.button
        if isinstance(button, MenuOption):
            self._navigate_to(button.screen_id)

    def _navigate_to(self, screen_id: str) -> None:
        """Navigate to the specified screen."""
        # Map screen IDs to screen classes
        screen_map = {
            "markets": MarketBrowserScreen,
            "positions": PositionViewerScreen,
            "scheduler": SchedulerControlScreen,
            "config": SettingsScreen,
            "diagnostics": MonitoringDashboardScreen,
        }

        if screen_id in screen_map:
            self.app.push_screen(screen_map[screen_id]())
        else:
            # Screens not yet implemented
            self.app.notify(f"Screen '{screen_id}' coming soon!", severity="information")

    # Action methods for keyboard shortcuts
    def action_goto_markets(self) -> None:
        """Navigate to Market Overview."""
        self._navigate_to("markets")

    def action_goto_positions(self) -> None:
        """Navigate to Positions."""
        self._navigate_to("positions")

    def action_goto_trades(self) -> None:
        """Navigate to Trades."""
        self._navigate_to("trades")

    def action_goto_scheduler(self) -> None:
        """Navigate to Scheduler."""
        self._navigate_to("scheduler")

    def action_goto_strategy(self) -> None:
        """Navigate to Strategy Manager."""
        self._navigate_to("strategy")

    def action_goto_models(self) -> None:
        """Navigate to Model Manager."""
        self._navigate_to("models")

    def action_goto_config(self) -> None:
        """Navigate to Configuration."""
        self._navigate_to("config")

    def action_goto_diagnostics(self) -> None:
        """Navigate to Diagnostics."""
        self._navigate_to("diagnostics")
