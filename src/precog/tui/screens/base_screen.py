"""
Base Screen for Precog TUI.

Provides common bindings, environment indicators, and styling that all screens inherit.
This ensures consistent global keybindings and environment display across the application.

Design Philosophy:
    - All screens show the same global keybindings (help, quit, theme)
    - Environment indicators (API mode, data source) visible on every screen
    - Consistent navigation patterns (escape to go back)

Reference:
    - Issue #282: TUI Usability Improvements
"""

from typing import ClassVar

from textual.binding import Binding, BindingType
from textual.screen import Screen


class BaseScreen(Screen):
    """
    Base screen class that all Precog TUI screens should inherit from.

    Provides:
        - Global keybindings (q=quit, ?=help, ctrl+t=theme, escape=back)
        - Helper methods for environment indicators
        - Consistent behavior across all screens

    Educational Note:
        In Textual, when a Screen defines BINDINGS, those bindings appear
        in the Footer widget. By having all screens inherit from BaseScreen,
        we ensure the global keybindings (help, quit, theme) are always
        visible regardless of which screen is active.

    Usage:
        Instead of inheriting from Screen directly:

            class MyScreen(Screen):
                BINDINGS = [...]

        Inherit from BaseScreen and extend BINDINGS:

            class MyScreen(BaseScreen):
                BINDINGS = BaseScreen.BINDINGS + [
                    ("r", "refresh", "Refresh"),
                ]
    """

    # Global keybindings shown on ALL screens
    # Educational Note: These are deliberately ordered to show the most
    # commonly used actions first. 'Escape=Back' provides consistent
    # navigation, while 'q=Quit' provides a quick exit.
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("q", "quit_app", "Quit", show=True, priority=False),
        Binding("?", "show_help", "Help", show=True),
        Binding("ctrl+t", "cycle_theme", "Theme", show=True),
    ]

    def action_go_back(self) -> None:
        """Return to previous screen.

        Educational Note:
            Uses app.pop_screen() to remove the current screen from the stack.
            The main menu handles the edge case where popping would leave
            an empty stack.
        """
        self.app.pop_screen()

    def action_quit_app(self) -> None:
        """Quit the entire application.

        Educational Note:
            Delegates to the app's quit action. Using priority=False ensures
            that screen-specific 'q' bindings (like closing a modal) take
            precedence when needed.
        """
        self.app.exit()

    def action_show_help(self) -> None:
        """Show comprehensive help screen.

        Educational Note:
            Pushes HelpScreen onto the stack. We import here to avoid
            circular imports since HelpScreen also inherits from BaseScreen.
        """
        from precog.tui.screens.help_screen import HelpScreen

        self.app.push_screen(HelpScreen())

    def action_cycle_theme(self) -> None:
        """Cycle through available themes.

        Educational Note:
            Delegates to the app's theme cycling method. The PrecogApp class
            handles the actual theme loading and CSS application.
        """
        # Call the app's theme cycling action
        if hasattr(self.app, "action_cycle_theme"):
            self.app.action_cycle_theme()

    def _get_data_source_mode(self) -> str:
        """Get the current data source mode from the app.

        Returns:
            Current mode: "auto", "demo", or "real"

        Educational Note:
            Accesses the app's data_source_mode property which controls whether
            screens use real database data, demo data, or auto-fallback behavior.
        """
        from precog.tui.app import PrecogApp

        if isinstance(self.app, PrecogApp):
            return self.app.data_source_mode
        return "auto"

    def _get_api_environment(self) -> str:
        """Get the current API environment from the app.

        Returns:
            Current environment: "demo" or "production"

        Educational Note:
            Controls which Kalshi API endpoint is used:
            - demo: Paper trading at demo-api.kalshi.com
            - production: Real money at trading-api.kalshi.com
        """
        from precog.tui.app import PrecogApp

        if isinstance(self.app, PrecogApp):
            return self.app.api_environment
        return "demo"

    def _format_environment_indicator(self) -> str:
        """Format a compact environment indicator string.

        Returns:
            Formatted string like "[API: Demo] [Data: Auto]"

        Educational Note:
            This provides at-a-glance visibility of the current mode,
            which is critical for avoiding confusion between demo and
            production environments.
        """
        api_env = self._get_api_environment()
        data_mode = self._get_data_source_mode()

        # Color code based on environment
        api_str = "[bold red]PROD[/]" if api_env == "production" else "[green]Demo[/]"

        if data_mode == "demo":
            data_str = "[yellow]Demo[/]"
        elif data_mode == "real":
            data_str = "[cyan]Real[/]"
        else:
            data_str = "[dim]Auto[/]"

        return f"[API: {api_str}] [Data: {data_str}]"
