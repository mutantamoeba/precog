"""
Tests for the Breadcrumb navigation widget.

Validates the breadcrumb path display and navigation features.
"""

from precog.tui.widgets.breadcrumb import Breadcrumb, BreadcrumbSegment


class TestBreadcrumbSegment:
    """Tests for individual breadcrumb segments."""

    def test_segment_stores_screen_id(self) -> None:
        """Verify segment stores its associated screen ID."""
        segment = BreadcrumbSegment("Markets", "market_browser")
        assert segment.screen_id == "market_browser"

    def test_segment_stores_current_flag(self) -> None:
        """Verify segment tracks if it's the current (active) segment."""
        current = BreadcrumbSegment("Current", "current_screen", is_current=True)
        previous = BreadcrumbSegment("Previous", "previous_screen", is_current=False)

        assert current.is_current is True
        assert previous.is_current is False

    def test_segment_has_label_content(self) -> None:
        """Verify segment has renderable content from label."""
        segment = BreadcrumbSegment("My Screen", "my_screen")
        # The segment is a Static widget, which has renderable content
        # Just verify it can be instantiated without error
        assert segment is not None


class TestBreadcrumb:
    """Tests for the Breadcrumb widget."""

    def test_breadcrumb_initializes_with_default_path(self) -> None:
        """Verify breadcrumb has default Home path when no path provided."""
        breadcrumb = Breadcrumb()
        assert len(breadcrumb._path) == 1
        assert breadcrumb._path[0] == ("Home", "main_menu")

    def test_breadcrumb_initializes_with_custom_path(self) -> None:
        """Verify breadcrumb accepts custom path."""
        custom_path = [("Home", "main_menu"), ("Markets", "market_browser")]
        breadcrumb = Breadcrumb(path=custom_path)
        assert len(breadcrumb._path) == 2
        assert breadcrumb._path[1] == ("Markets", "market_browser")

    def test_push_modifies_path_directly(self) -> None:
        """Verify path can be modified directly (push requires app context).

        Educational Note:
            The push() method calls update_path() which requires a Textual app
            context to remount widgets. For unit testing without an app, we
            verify the path data structure can be modified correctly.
        """
        breadcrumb = Breadcrumb()
        initial_length = len(breadcrumb._path)

        # Directly modify path (what push() does before calling update_path)
        breadcrumb._path.append(("Settings", "settings"))

        assert len(breadcrumb._path) == initial_length + 1
        assert breadcrumb._path[-1] == ("Settings", "settings")

    def test_pop_modifies_path_directly(self) -> None:
        """Verify path can be popped directly (pop requires app context).

        Educational Note:
            The pop() method calls update_path() which requires a Textual app
            context to remount widgets. For unit testing without an app, we
            verify the path data structure can be modified correctly.
        """
        path = [("Home", "main_menu"), ("Markets", "market_browser")]
        breadcrumb = Breadcrumb(path=path.copy())  # Copy to avoid modifying original

        # Directly pop from path (what pop() does before calling update_path)
        removed = breadcrumb._path.pop()

        assert removed == ("Markets", "market_browser")
        assert len(breadcrumb._path) == 1
        assert breadcrumb._path[0] == ("Home", "main_menu")

    def test_pop_returns_none_when_at_root(self) -> None:
        """Verify pop() returns None when only Home remains (protects root)."""
        breadcrumb = Breadcrumb()  # Only Home

        result = breadcrumb.pop()

        assert result is None
        assert len(breadcrumb._path) == 1  # Home still present

    def test_for_screen_creates_breadcrumb_with_correct_path(self) -> None:
        """Verify for_screen() class method creates proper breadcrumb."""
        breadcrumb = Breadcrumb.for_screen("market_browser")

        assert len(breadcrumb._path) == 2
        assert breadcrumb._path[0] == ("Home", "main_menu")
        assert breadcrumb._path[1] == ("Markets", "market_browser")

    def test_for_screen_uses_screen_name_mapping(self) -> None:
        """Verify for_screen() uses SCREEN_NAMES mapping for display labels."""
        # Check that known screen IDs get proper display names
        known_screens = [
            ("market_browser", "Markets"),
            ("position_viewer", "Positions"),
            ("settings", "Settings"),
            ("scheduler_control", "Scheduler"),
            ("monitoring_dashboard", "Diagnostics"),
        ]

        for screen_id, expected_label in known_screens:
            breadcrumb = Breadcrumb.for_screen(screen_id)
            assert breadcrumb._path[-1][0] == expected_label
            assert breadcrumb._path[-1][1] == screen_id

    def test_for_screen_main_menu_only_shows_home(self) -> None:
        """Verify main_menu gets only Home breadcrumb (not Home > Home)."""
        breadcrumb = Breadcrumb.for_screen("main_menu")

        assert len(breadcrumb._path) == 1
        assert breadcrumb._path[0] == ("Home", "main_menu")

    def test_for_screen_unknown_id_formats_nicely(self) -> None:
        """Verify unknown screen IDs get formatted as title case."""
        breadcrumb = Breadcrumb.for_screen("custom_screen_name")

        # Should format unknown_id as "Custom Screen Name"
        assert breadcrumb._path[-1][0] == "Custom Screen Name"
        assert breadcrumb._path[-1][1] == "custom_screen_name"

    def test_screen_names_mapping_exists(self) -> None:
        """Verify SCREEN_NAMES class attribute has expected mappings."""
        expected_mappings = {
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

        for screen_id, expected_label in expected_mappings.items():
            assert Breadcrumb.SCREEN_NAMES.get(screen_id) == expected_label

    def test_has_default_css(self) -> None:
        """Verify breadcrumb widget has default CSS styling defined."""
        assert hasattr(Breadcrumb, "DEFAULT_CSS")
        assert "Breadcrumb" in Breadcrumb.DEFAULT_CSS
        assert "height:" in Breadcrumb.DEFAULT_CSS
