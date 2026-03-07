"""
Environment Bar Widget.

Displays the current API environment and data source mode at the top of screens.
Provides at-a-glance visibility of which environment is active.

Design:
    - Shows API environment: Demo (paper trading) or Production (real money)
    - Shows data source mode: Auto, Demo, or Real
    - Color-coded for quick visual identification
    - Production mode highlighted in red as a warning

Reference:
    - Issue #282: TUI Usability Improvements
"""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static


class EnvironmentBar(Horizontal):
    """
    A status bar showing current API and data source environments.

    Educational Note:
        This widget provides constant visibility of which environment
        is active, which is critical for avoiding confusion between
        demo (paper trading) and production (real money) modes.
        The bar is color-coded:
        - Demo API: Green text (safe for testing)
        - Production API: Red background (real money - be careful!)
        - Data Demo: Yellow (sample data, not real)
        - Data Real: Cyan (live database data)
        - Data Auto: Dim (tries DB, falls back to demo)
    """

    DEFAULT_CSS = """
    EnvironmentBar {
        height: 1;
        width: 100%;
        background: $surface;
        padding: 0 1;
    }

    EnvironmentBar .env-label {
        width: auto;
        padding: 0 1;
    }

    EnvironmentBar .env-production {
        background: $error;
        color: $text;
    }

    EnvironmentBar .env-demo {
        color: $success;
    }

    EnvironmentBar .data-demo {
        color: $warning;
    }

    EnvironmentBar .data-real {
        color: $primary;
    }

    EnvironmentBar .separator {
        color: $text-muted;
    }
    """

    def __init__(
        self,
        api_environment: str = "demo",
        data_source_mode: str = "auto",
        **kwargs,
    ) -> None:
        """
        Create the environment bar.

        Args:
            api_environment: Current API environment ("demo" or "production")
            data_source_mode: Current data source mode ("auto", "demo", or "real")
        """
        super().__init__(**kwargs)
        self._api_environment = api_environment
        self._data_source_mode = data_source_mode

    def compose(self) -> ComposeResult:
        """Create the environment bar layout."""
        # API environment indicator
        if self._api_environment == "production":
            yield Static(
                " API: PRODUCTION ",
                classes="env-label env-production",
            )
        else:
            yield Static(
                "[green]API: Demo[/]",
                classes="env-label env-demo",
            )

        yield Static(" | ", classes="separator")

        # Data source mode indicator
        if self._data_source_mode == "demo":
            yield Static(
                "[yellow]Data: Demo[/]",
                classes="env-label data-demo",
            )
        elif self._data_source_mode == "real":
            yield Static(
                "[cyan]Data: Live DB[/]",
                classes="env-label data-real",
            )
        else:
            yield Static(
                "[dim]Data: Auto[/]",
                classes="env-label",
            )

    def update_environment(self, api_environment: str, data_source_mode: str) -> None:
        """
        Update the displayed environment values.

        Args:
            api_environment: New API environment
            data_source_mode: New data source mode
        """
        self._api_environment = api_environment
        self._data_source_mode = data_source_mode
        # Re-compose the widget to update display
        self.remove_children()
        for widget in self.compose():
            self.mount(widget)

    @classmethod
    def from_app(cls, app) -> "EnvironmentBar":
        """
        Create an EnvironmentBar with values from the app.

        Args:
            app: The PrecogApp instance

        Returns:
            EnvironmentBar configured with current app settings

        Educational Note:
            This factory method allows screens to create an
            EnvironmentBar without directly importing PrecogApp,
            avoiding circular import issues.
        """
        api_env = "demo"
        data_mode = "auto"

        try:
            from precog.tui.app import PrecogApp

            if isinstance(app, PrecogApp):
                api_env = app.api_environment
                data_mode = app.data_source_mode
        except ImportError:
            pass

        return cls(api_environment=api_env, data_source_mode=data_mode)
