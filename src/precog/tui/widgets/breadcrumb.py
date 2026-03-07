"""
Breadcrumb Navigation Widget.

Displays the current navigation path to help users understand
their location within the application hierarchy.

Design:
    - Shows path as: Home > Section > Current Screen
    - Clickable segments for quick navigation back
    - Styled to match current theme

Reference:
    - Issue #268: TUI Navigation Improvements

Educational Note:
    Breadcrumbs are a navigation pattern that shows users their current
    location in a hierarchical structure. In a TUI context, they help
    orient users who may have navigated several levels deep.
"""

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static


class BreadcrumbSegment(Static):
    """A clickable segment in the breadcrumb trail."""

    class Clicked(Message):
        """Message sent when a breadcrumb segment is clicked."""

        def __init__(self, segment: "BreadcrumbSegment") -> None:
            self.segment = segment
            self.screen_id = segment.screen_id
            super().__init__()

    def __init__(self, label: str, screen_id: str, is_current: bool = False) -> None:
        """Create a breadcrumb segment.

        Args:
            label: Display text for this segment
            screen_id: ID of the screen this segment represents
            is_current: Whether this is the current (rightmost) segment
        """
        self.screen_id = screen_id
        self.is_current = is_current

        # Style current segment differently
        content = f"[bold cyan]{label}[/]" if is_current else f"[dim]{label}[/]"

        super().__init__(content, classes="breadcrumb-segment")

    def on_click(self) -> None:
        """Handle click on breadcrumb segment."""
        if not self.is_current:
            self.post_message(self.Clicked(self))


class Breadcrumb(Widget):
    """
    Breadcrumb navigation showing the current screen path.

    Displays a trail like: Home > Markets > Market Details
    allowing users to quickly navigate back to previous screens.

    Educational Note:
        The breadcrumb maintains a list of (label, screen_id) tuples
        representing the navigation path. When a segment is clicked,
        screens are popped from the stack until reaching the target.
    """

    DEFAULT_CSS = """
    Breadcrumb {
        height: 1;
        width: 100%;
        background: $surface;
        padding: 0 1;
    }

    Breadcrumb > Horizontal {
        height: 1;
        width: 100%;
    }

    .breadcrumb-segment {
        height: 1;
    }

    .breadcrumb-separator {
        height: 1;
        color: $text-muted;
    }
    """

    # Screen name mappings for display
    SCREEN_NAMES: ClassVar[dict[str, str]] = {
        "main_menu": "Home",
        "market_browser": "Markets",
        "position_viewer": "Positions",
        "trade_execution": "Trades",
        "scheduler_control": "Scheduler",
        "strategy_manager": "Strategies",
        "model_manager": "Models",
        "settings": "Settings",
        "monitoring_dashboard": "Diagnostics",
        "help_screen": "Help",
    }

    def __init__(self, path: list[tuple[str, str]] | None = None) -> None:
        """Create a breadcrumb widget.

        Args:
            path: List of (label, screen_id) tuples representing the path.
                  If None, defaults to just "Home".
        """
        super().__init__()
        self._path = path or [("Home", "main_menu")]

    def compose(self) -> ComposeResult:
        """Create the breadcrumb layout."""
        with Horizontal():
            for i, (label, screen_id) in enumerate(self._path):
                is_current = i == len(self._path) - 1

                # Add separator except before first item
                if i > 0:
                    yield Static(" > ", classes="breadcrumb-separator")

                yield BreadcrumbSegment(label, screen_id, is_current)

    def update_path(self, path: list[tuple[str, str]]) -> None:
        """Update the breadcrumb path.

        Args:
            path: New path as list of (label, screen_id) tuples
        """
        self._path = path
        self.remove_children()
        self.mount_all(list(self.compose()))

    def push(self, label: str, screen_id: str) -> None:
        """Add a new segment to the path.

        Args:
            label: Display label for the new segment
            screen_id: Screen ID for the new segment
        """
        self._path.append((label, screen_id))
        self.update_path(self._path)

    def pop(self) -> tuple[str, str] | None:
        """Remove and return the last segment.

        Returns:
            The removed (label, screen_id) tuple, or None if path is empty
        """
        if len(self._path) > 1:
            removed = self._path.pop()
            self.update_path(self._path)
            return removed
        return None

    @classmethod
    def for_screen(cls, screen_id: str) -> "Breadcrumb":
        """Create a breadcrumb for a specific screen.

        Args:
            screen_id: The current screen's ID

        Returns:
            Breadcrumb with path from Home to current screen
        """
        label = cls.SCREEN_NAMES.get(screen_id, screen_id.replace("_", " ").title())
        if screen_id == "main_menu":
            return cls([("Home", "main_menu")])
        return cls([("Home", "main_menu"), (label, screen_id)])
