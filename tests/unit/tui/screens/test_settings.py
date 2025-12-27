"""Unit tests for TUI Settings Screen.

Tests for the settings screen and its components.

Reference:
    - Issue #283: TUI Additional Screens
    - src/precog/tui/screens/settings.py
"""

from __future__ import annotations

import pytest

# Skip all tests in this module if textual is not installed (optional dependency)
pytest.importorskip("textual")


class TestSettingsScreen:
    """Test SettingsScreen class."""

    def test_settings_screen_has_bindings(self) -> None:
        """Verify SettingsScreen has key bindings."""
        from precog.tui.screens.settings import SettingsScreen

        assert hasattr(SettingsScreen, "BINDINGS")
        assert len(SettingsScreen.BINDINGS) >= 3  # r, t, escape

    def test_settings_screen_instantiates(self) -> None:
        """Verify SettingsScreen can be instantiated."""
        from precog.tui.screens.settings import SettingsScreen

        screen = SettingsScreen()
        assert screen is not None

    def test_settings_has_load_connections_method(self) -> None:
        """Verify screen has _load_connections method."""
        from precog.tui.screens.settings import SettingsScreen

        screen = SettingsScreen()
        assert hasattr(screen, "_load_connections")
        assert callable(screen._load_connections)

    def test_settings_has_load_configuration_method(self) -> None:
        """Verify screen has _load_configuration method."""
        from precog.tui.screens.settings import SettingsScreen

        screen = SettingsScreen()
        assert hasattr(screen, "_load_configuration")
        assert callable(screen._load_configuration)

    def test_settings_has_test_database_method(self) -> None:
        """Verify screen has _test_database method for connection testing."""
        from precog.tui.screens.settings import SettingsScreen

        screen = SettingsScreen()
        assert hasattr(screen, "_test_database")
        assert callable(screen._test_database)

    def test_settings_has_demo_config_fallback(self) -> None:
        """Verify screen has _load_demo_config method for graceful fallback."""
        from precog.tui.screens.settings import SettingsScreen

        screen = SettingsScreen()
        assert hasattr(screen, "_load_demo_config")
        assert callable(screen._load_demo_config)
