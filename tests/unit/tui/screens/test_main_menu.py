"""Unit tests for TUI Main Menu Screen.

Tests for the main menu screen and its components.

Reference:
    - Issue #268: Textual-based Sci-Fi Terminal UI
    - src/precog/tui/screens/main_menu.py
"""

from __future__ import annotations


class TestMenuOptionButton:
    """Test MenuOption button class."""

    def test_menu_option_has_screen_id(self) -> None:
        """Verify MenuOption stores screen_id."""
        from precog.tui.screens.main_menu import MenuOption

        option = MenuOption("Test Label", "T", "Test description", "test_screen")
        assert option.screen_id == "test_screen"
        assert option.description == "Test description"

    def test_menu_option_formats_label(self) -> None:
        """Verify MenuOption formats label with key."""
        from precog.tui.screens.main_menu import MenuOption

        option = MenuOption("Markets", "1", "View markets", "markets")
        # Button label should include the key
        assert "1" in str(option.label)


class TestMainMenuScreen:
    """Test MainMenuScreen class."""

    def test_main_menu_screen_has_bindings(self) -> None:
        """Verify MainMenuScreen has key bindings."""
        from precog.tui.screens.main_menu import MainMenuScreen

        assert hasattr(MainMenuScreen, "BINDINGS")
        assert len(MainMenuScreen.BINDINGS) >= 8  # 1-8 for menu options

    def test_main_menu_screen_instantiates(self) -> None:
        """Verify MainMenuScreen can be instantiated."""
        from precog.tui.screens.main_menu import MainMenuScreen

        screen = MainMenuScreen()
        assert screen is not None
