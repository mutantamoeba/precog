"""
Precog TUI Application.

Main Textual application class that manages screens, themes, and global state.

Design Philosophy:
    - Usability first: Clear labels, thematic elements enhance but never obscure
    - Theme support: Users can switch between minimal and immersive themes
    - Keyboard-driven: Full navigation without mouse required

Reference:
    - Issue #268: Textual-based Sci-Fi Terminal UI
    - Textual App docs: https://textual.textualize.io/guide/app/
"""

from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Footer, Header

from precog.tui.screens.help_screen import HelpScreen
from precog.tui.screens.main_menu import MainMenuScreen


class PrecogApp(App[None]):
    """
    Precog Terminal User Interface.

    A full-featured TUI for interacting with the Precog prediction market system.
    Supports multiple themes and provides access to all system functionality.

    Attributes:
        TITLE: Application title shown in header
        SUB_TITLE: Subtitle shown in header
        CSS_PATH: Path to the theme CSS file

    Key Bindings:
        q: Quit application
        ctrl+t: Cycle through themes
        ctrl+p: Open command palette
        ?: Show help
    """

    TITLE = "PRECOG"
    SUB_TITLE = "Prediction Market Intelligence"

    # Load CSS from styles directory
    CSS_PATH = Path(__file__).parent / "styles" / "precog_dark.tcss"

    # Global key bindings
    # Educational Note: Bindings with show=True appear in the footer.
    # We don't use priority=True as it would override screen-level bindings
    # (e.g., HelpScreen uses 'q' to close, not quit the app).
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit", show=True),
        Binding("?", "show_help", "Help", show=True),
        Binding("ctrl+t", "cycle_theme", "Theme", show=True),
        Binding("escape", "go_back", "Back", show=True),
        # Arrow key navigation (global - hidden to reduce footer clutter)
        Binding("up", "focus_previous", "Up", show=False),
        Binding("down", "focus_next", "Down", show=False),
        Binding("left", "focus_previous", "Left", show=False),
        Binding("right", "focus_next", "Right", show=False),
        Binding("tab", "focus_next", "Next", show=False),
        Binding("shift+tab", "focus_previous", "Prev", show=False),
    ]

    # Available themes
    THEMES: ClassVar[list[str]] = [
        "precog_dark",
        "precog_classic",
        "precog_acid",
        "precog_cyberpunk",
    ]
    _current_theme_index = 0

    # Data source modes: "auto" (try DB first, fall back to demo), "demo", "real"
    # Educational Note: This allows users to test with demo data even when
    # the database is available, or to force real data (showing errors if unavailable).
    DATA_SOURCE_MODES: ClassVar[list[str]] = ["auto", "demo", "real"]
    _data_source_mode: str = "auto"

    # API environment modes: "demo" (paper trading), "production" (real money)
    # Educational Note: This controls which Kalshi API endpoint is used.
    # Demo mode uses demo-api.kalshi.com, production uses trading-api.kalshi.com.
    # CRITICAL: Production mode involves real money - use with extreme caution!
    API_ENVIRONMENTS: ClassVar[list[str]] = ["demo", "production"]
    _api_environment: str = "demo"

    @property
    def data_source_mode(self) -> str:
        """Current data source mode."""
        return self._data_source_mode

    @data_source_mode.setter
    def data_source_mode(self, value: str) -> None:
        """Set data source mode with validation."""
        if value in self.DATA_SOURCE_MODES:
            self._data_source_mode = value
        else:
            raise ValueError(f"Invalid data source mode: {value}")

    @property
    def api_environment(self) -> str:
        """Current API environment mode.

        Educational Note:
            This property controls which Kalshi API endpoint is used:
            - demo: Paper trading (demo-api.kalshi.com)
            - production: Real money (trading-api.kalshi.com)
        """
        return self._api_environment

    @api_environment.setter
    def api_environment(self, value: str) -> None:
        """Set API environment with validation.

        Raises:
            ValueError: If value is not a valid API environment
        """
        if value in self.API_ENVIRONMENTS:
            self._api_environment = value
        else:
            raise ValueError(f"Invalid API environment: {value}")

    def compose(self) -> ComposeResult:
        """Create the application layout.

        Yields:
            Header: Top bar with title
            MainMenuScreen: The main content area (initially main menu)
            Footer: Bottom bar with key bindings
        """
        yield Header(show_clock=True)
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted. Push the main menu screen."""
        self.push_screen(MainMenuScreen())

    async def action_quit(self) -> None:
        """Quit the application."""
        self.exit()

    def action_cycle_theme(self) -> None:
        """Cycle through available themes.

        Educational Note:
            Textual's stylesheet system allows dynamic theme switching.
            We clear the internal source dictionary and load the new theme's CSS
            file, then call refresh() to re-render all widgets with the new styles.

            CRITICAL: Never set stylesheet.source to a string! The source attribute
            must remain a dict. Setting source="" breaks Toast notifications and
            any widget that tries to add CSS sources later.
        """
        self._current_theme_index = (self._current_theme_index + 1) % len(self.THEMES)
        theme_name = self.THEMES[self._current_theme_index]

        # Load new theme CSS
        theme_path = Path(__file__).parent / "styles" / f"{theme_name}.tcss"
        if theme_path.exists():
            # Read and apply new stylesheet
            try:
                css_content = theme_path.read_text(encoding="utf-8")
                # Clear existing styles by clearing the internal _source dict
                # IMPORTANT: Do NOT set source="" as that breaks the stylesheet
                if hasattr(self.stylesheet, "_source") and isinstance(
                    self.stylesheet._source, dict
                ):
                    self.stylesheet._source.clear()
                self.stylesheet.add_source(css_content, path=theme_path)
                self.stylesheet.reparse()
                # Refresh to apply new styles
                self.refresh(layout=True)
                self.notify(f"Theme: {theme_name.replace('precog_', '').title()}")
            except Exception as e:
                self.notify(f"Error loading theme: {e}", severity="error")
        else:
            self.notify(f"Theme '{theme_name}' not found", severity="warning")

    def action_show_help(self) -> None:
        """Show comprehensive help screen.

        Educational Note:
            Pushes the HelpScreen onto the screen stack, providing
            in-app documentation with keyboard shortcuts, screen
            reference, themes guide, and troubleshooting tips.
        """
        self.push_screen(HelpScreen())

    def action_go_back(self) -> None:
        """Go back to previous screen.

        Educational Note:
            We prevent popping when on MainMenuScreen to avoid showing
            the empty App base screen. MainMenuScreen is the "root" of
            the screen stack from the user's perspective.
        """
        # Don't pop if we're on the main menu - it's the root screen
        if len(self.screen_stack) > 1 and not isinstance(self.screen, MainMenuScreen):
            self.pop_screen()


def run(theme: str = "precog_dark") -> None:
    """
    Run the Precog TUI application.

    Args:
        theme: Theme name to use (default: precog_dark)

    Example:
        >>> from precog.tui import run
        >>> run()  # Launch with default theme
        >>> run(theme="precog_acid")  # Launch with ACiD theme
    """
    app = PrecogApp()

    # Set theme if specified
    if theme and theme in PrecogApp.THEMES:
        app._current_theme_index = PrecogApp.THEMES.index(theme)

    app.run()


if __name__ == "__main__":
    run()
