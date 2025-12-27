"""Unit tests for TUI Monitoring Dashboard Screen.

Tests for the monitoring dashboard screen and its components.

Reference:
    - Issue #283: TUI Additional Screens
    - src/precog/tui/screens/monitoring_dashboard.py
"""

from __future__ import annotations

import pytest

# Skip all tests in this module if textual is not installed (optional dependency)
pytest.importorskip("textual")


class TestMonitoringDashboardScreen:
    """Test MonitoringDashboardScreen class."""

    def test_monitoring_dashboard_screen_has_bindings(self) -> None:
        """Verify MonitoringDashboardScreen has key bindings."""
        from precog.tui.screens.monitoring_dashboard import MonitoringDashboardScreen

        assert hasattr(MonitoringDashboardScreen, "BINDINGS")
        assert len(MonitoringDashboardScreen.BINDINGS) >= 3  # r, l, escape

    def test_monitoring_dashboard_screen_instantiates(self) -> None:
        """Verify MonitoringDashboardScreen can be instantiated."""
        from precog.tui.screens.monitoring_dashboard import MonitoringDashboardScreen

        screen = MonitoringDashboardScreen()
        assert screen is not None

    def test_monitoring_dashboard_has_refresh_interval(self) -> None:
        """Verify screen has REFRESH_INTERVAL constant."""
        from precog.tui.screens.monitoring_dashboard import MonitoringDashboardScreen

        assert hasattr(MonitoringDashboardScreen, "REFRESH_INTERVAL")
        assert MonitoringDashboardScreen.REFRESH_INTERVAL == 10

    def test_monitoring_dashboard_has_load_metrics_method(self) -> None:
        """Verify screen has _load_metrics method."""
        from precog.tui.screens.monitoring_dashboard import MonitoringDashboardScreen

        screen = MonitoringDashboardScreen()
        assert hasattr(screen, "_load_metrics")
        assert callable(screen._load_metrics)

    def test_monitoring_dashboard_has_log_stream_init(self) -> None:
        """Verify screen has _init_log_stream method."""
        from precog.tui.screens.monitoring_dashboard import MonitoringDashboardScreen

        screen = MonitoringDashboardScreen()
        assert hasattr(screen, "_init_log_stream")
        assert callable(screen._init_log_stream)
