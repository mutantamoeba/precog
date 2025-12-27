"""Unit tests for TUI Scheduler Control Screen.

Tests for the scheduler control screen and its components.

Reference:
    - Issue #283: TUI Additional Screens
    - src/precog/tui/screens/scheduler_control.py
"""

from __future__ import annotations

import pytest

# Skip all tests in this module if textual is not installed (optional dependency)
pytest.importorskip("textual")


class TestSchedulerControlScreen:
    """Test SchedulerControlScreen class."""

    def test_scheduler_control_screen_has_bindings(self) -> None:
        """Verify SchedulerControlScreen has key bindings."""
        from precog.tui.screens.scheduler_control import SchedulerControlScreen

        assert hasattr(SchedulerControlScreen, "BINDINGS")
        assert len(SchedulerControlScreen.BINDINGS) >= 5  # r, s, x, l, escape

    def test_scheduler_control_screen_instantiates(self) -> None:
        """Verify SchedulerControlScreen can be instantiated."""
        from precog.tui.screens.scheduler_control import SchedulerControlScreen

        screen = SchedulerControlScreen()
        assert screen is not None

    def test_scheduler_control_has_load_services_method(self) -> None:
        """Verify screen has _load_services method."""
        from precog.tui.screens.scheduler_control import SchedulerControlScreen

        screen = SchedulerControlScreen()
        assert hasattr(screen, "_load_services")
        assert callable(screen._load_services)

    def test_scheduler_control_has_format_time_ago_method(self) -> None:
        """Verify screen has _format_time_ago method for heartbeat display."""
        from precog.tui.screens.scheduler_control import SchedulerControlScreen

        screen = SchedulerControlScreen()
        assert hasattr(screen, "_format_time_ago")
        assert callable(screen._format_time_ago)

    def test_scheduler_control_has_demo_data_fallback(self) -> None:
        """Verify screen has _load_demo_data method for graceful fallback."""
        from precog.tui.screens.scheduler_control import SchedulerControlScreen

        screen = SchedulerControlScreen()
        assert hasattr(screen, "_load_demo_data")
        assert callable(screen._load_demo_data)
