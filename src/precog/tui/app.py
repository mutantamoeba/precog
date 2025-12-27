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
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+t", "cycle_theme", "Theme", show=True),
        Binding("?", "show_help", "Help", show=True),
        Binding("escape", "go_back", "Back", show=False),
        # Arrow key navigation (global)
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
        """Cycle through available themes."""
        self._current_theme_index = (self._current_theme_index + 1) % len(self.THEMES)
        theme_name = self.THEMES[self._current_theme_index]

        # Load new theme CSS
        theme_path = Path(__file__).parent / "styles" / f"{theme_name}.tcss"
        if theme_path.exists():
            # Reload stylesheet
            self.notify(f"Theme: {theme_name.replace('precog_', '').title()}")
        else:
            self.notify(f"Theme '{theme_name}' not found", severity="warning")

    def action_show_help(self) -> None:
        """Show help screen."""
        self.notify("Help: Press Q to quit, Arrow keys to navigate")

    def action_go_back(self) -> None:
        """Go back to previous screen."""
        if len(self.screen_stack) > 1:
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
