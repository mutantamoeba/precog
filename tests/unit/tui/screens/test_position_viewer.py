"""Unit tests for TUI Position Viewer Screen.

Tests for the position viewer screen and its components.

Reference:
    - Issue #283: TUI Additional Screens
    - src/precog/tui/screens/position_viewer.py
"""

from __future__ import annotations

import pytest

# Skip all tests in this module if textual is not installed (optional dependency)
pytest.importorskip("textual")


class TestPositionViewerScreen:
    """Test PositionViewerScreen class."""

    def test_position_viewer_screen_has_bindings(self) -> None:
        """Verify PositionViewerScreen has key bindings."""
        from precog.tui.screens.position_viewer import PositionViewerScreen

        assert hasattr(PositionViewerScreen, "BINDINGS")
        assert len(PositionViewerScreen.BINDINGS) >= 4  # r, o, a, escape

    def test_position_viewer_screen_instantiates(self) -> None:
        """Verify PositionViewerScreen can be instantiated."""
        from precog.tui.screens.position_viewer import PositionViewerScreen

        screen = PositionViewerScreen()
        assert screen is not None

    def test_position_viewer_has_load_positions_method(self) -> None:
        """Verify screen has _load_positions method."""
        from precog.tui.screens.position_viewer import PositionViewerScreen

        screen = PositionViewerScreen()
        assert hasattr(screen, "_load_positions")
        assert callable(screen._load_positions)

    def test_position_viewer_has_update_summary_method(self) -> None:
        """Verify screen has _update_summary method for P&L display."""
        from precog.tui.screens.position_viewer import PositionViewerScreen

        screen = PositionViewerScreen()
        assert hasattr(screen, "_update_summary")
        assert callable(screen._update_summary)

    def test_position_viewer_has_demo_data_fallback(self) -> None:
        """Verify screen has _load_demo_data method for graceful fallback."""
        from precog.tui.screens.position_viewer import PositionViewerScreen

        screen = PositionViewerScreen()
        assert hasattr(screen, "_load_demo_data")
        assert callable(screen._load_demo_data)
