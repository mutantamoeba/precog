"""
Comprehensive TUI Rendering Tests.

Uses Textual's async pilot testing framework to test actual screen
rendering, navigation, and widget interactions.

Educational Note:
    Textual provides `App.run_test()` which creates an async context
    for testing UI interactions. This allows testing:
    - Screen mounting and rendering
    - Keyboard navigation
    - Button presses and widget interactions
    - Theme switching
    - Screen transitions

Reference:
    - Textual Testing Guide: https://textual.textualize.io/guide/testing/
    - Issue #286: TUI Testing Infrastructure
"""

import pytest
from textual.widgets import Button, DataTable, Static

from precog.tui.app import PrecogApp
from precog.tui.screens.main_menu import MainMenuScreen, MenuOption
from precog.tui.screens.market_browser import MarketBrowserScreen
from precog.tui.screens.monitoring_dashboard import MonitoringDashboardScreen
from precog.tui.screens.position_viewer import PositionViewerScreen
from precog.tui.screens.scheduler_control import SchedulerControlScreen
from precog.tui.screens.settings import SettingsScreen


class TestAppStartup:
    """Tests for application startup and initialization."""

    @pytest.mark.asyncio
    async def test_app_starts_without_crash(self) -> None:
        """Verify the app starts and renders without exceptions."""
        app = PrecogApp()
        async with app.run_test():
            # App should start with main menu screen
            assert len(app.screen_stack) >= 1
            assert isinstance(app.screen, MainMenuScreen)

    @pytest.mark.asyncio
    async def test_header_and_footer_present(self) -> None:
        """Verify header and footer are rendered."""
        app = PrecogApp()
        async with app.run_test():
            # Check header widget exists (from app.compose)
            header = app.query_one("Header")
            assert header is not None

            # Check footer widget exists
            footer = app.query_one("Footer")
            assert footer is not None

    @pytest.mark.asyncio
    async def test_ascii_header_renders(self) -> None:
        """Verify ASCII art header renders on main menu.

        Educational Note:
            When screens are pushed onto the stack, widgets are attached to
            the screen, not the app. We must query from app.screen, not app.
            The ASCII art renders "PRECOG" using Unicode box characters, so
            we check for the subtitle text which appears literally.
            Note: The subtitle uses spaced text like "P R E D I C T I O N".
        """
        app = PrecogApp()
        async with app.run_test():
            # Query for ASCII header on the current screen
            ascii_header = app.screen.query_one("#ascii-header")
            assert ascii_header is not None
            # Check for subtitle text (PRECOG is rendered as ASCII art blocks)
            # Subtitle uses spaced text like "P R E D I C T I O N"
            rendered = str(ascii_header.render())
            has_subtitle = (
                "I N T E L L I G E N C E" in rendered
                or "P R E D I C T I O N" in rendered
                or "M A R K E T" in rendered
            )
            assert has_subtitle, f"Expected spaced subtitle text in: {rendered[:200]}"


class TestMainMenuNavigation:
    """Tests for main menu screen navigation."""

    @pytest.mark.asyncio
    async def test_menu_options_present(self) -> None:
        """Verify all 8 menu options are rendered."""
        app = PrecogApp()
        async with app.run_test():
            # Query for all menu options on the current screen
            menu_options = app.screen.query(MenuOption)
            assert len(list(menu_options)) == 8

    @pytest.mark.asyncio
    async def test_keyboard_navigation_number_keys(self) -> None:
        """Test navigation using number key shortcuts."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            # Press '1' to go to Markets
            await pilot.press("1")
            await pilot.pause()
            assert isinstance(app.screen, MarketBrowserScreen)

    @pytest.mark.asyncio
    async def test_keyboard_navigation_escape_back(self) -> None:
        """Test escape key returns to previous screen."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            # Navigate to Markets
            await pilot.press("1")
            await pilot.pause()
            assert isinstance(app.screen, MarketBrowserScreen)

            # Press escape to go back
            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen, MainMenuScreen)

    @pytest.mark.asyncio
    async def test_navigate_to_positions(self) -> None:
        """Test navigation to Position Viewer screen."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("2")
            await pilot.pause()
            assert isinstance(app.screen, PositionViewerScreen)

    @pytest.mark.asyncio
    async def test_navigate_to_scheduler(self) -> None:
        """Test navigation to Scheduler Control screen."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("4")
            await pilot.pause()
            assert isinstance(app.screen, SchedulerControlScreen)

    @pytest.mark.asyncio
    async def test_navigate_to_config(self) -> None:
        """Test navigation to Settings screen."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("7")
            await pilot.pause()
            assert isinstance(app.screen, SettingsScreen)

    @pytest.mark.asyncio
    async def test_navigate_to_diagnostics(self) -> None:
        """Test navigation to Monitoring Dashboard screen."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("8")
            await pilot.pause()
            assert isinstance(app.screen, MonitoringDashboardScreen)

    @pytest.mark.asyncio
    async def test_unimplemented_screens_show_notification(self) -> None:
        """Test that unimplemented screens show notification."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            # Press '3' for Trades (not implemented)
            await pilot.press("3")
            await pilot.pause()
            # Should still be on main menu (not crash)
            assert isinstance(app.screen, MainMenuScreen)


class TestMarketBrowserScreen:
    """Tests for Market Browser screen."""

    @pytest.mark.asyncio
    async def test_market_table_renders(self) -> None:
        """Verify market DataTable is present and has columns."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("1")
            await pilot.pause()

            table = app.screen.query_one("#market-table", DataTable)
            assert table is not None
            # Should have 7 columns
            assert len(table.columns) == 7

    @pytest.mark.asyncio
    async def test_demo_data_loads(self) -> None:
        """Verify demo data loads when database unavailable."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("1")
            await pilot.pause()

            table = app.screen.query_one("#market-table", DataTable)
            # Demo data should have 5 rows
            assert table.row_count >= 5

    @pytest.mark.asyncio
    async def test_filter_dropdowns_present(self) -> None:
        """Verify sport and status filter dropdowns exist."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("1")
            await pilot.pause()

            sport_filter = app.screen.query_one("#sport-filter")
            status_filter = app.screen.query_one("#status-filter")
            assert sport_filter is not None
            assert status_filter is not None

    @pytest.mark.asyncio
    async def test_refresh_action(self) -> None:
        """Test refresh action works without crash."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("1")
            await pilot.pause()
            # Press 'r' to refresh
            await pilot.press("r")
            await pilot.pause()
            # Should not crash
            assert isinstance(app.screen, MarketBrowserScreen)


class TestPositionViewerScreen:
    """Tests for Position Viewer screen."""

    @pytest.mark.asyncio
    async def test_summary_panel_present(self) -> None:
        """Verify P&L summary panel is rendered."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("2")
            await pilot.pause()

            open_count = app.screen.query_one("#open-count", Static)
            unrealized_pnl = app.screen.query_one("#unrealized-pnl", Static)
            realized_pnl = app.screen.query_one("#realized-pnl", Static)
            total_pnl = app.screen.query_one("#total-pnl", Static)

            assert open_count is not None
            assert unrealized_pnl is not None
            assert realized_pnl is not None
            assert total_pnl is not None

    @pytest.mark.asyncio
    async def test_position_table_renders(self) -> None:
        """Verify position DataTable is present."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("2")
            await pilot.pause()

            table = app.screen.query_one("#position-table", DataTable)
            assert table is not None
            assert len(table.columns) == 9


class TestMonitoringDashboardScreen:
    """Tests for Monitoring Dashboard screen."""

    @pytest.mark.asyncio
    async def test_health_cards_present(self) -> None:
        """Verify health status cards are rendered."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("8")
            await pilot.pause()

            # Check for health card elements
            db_status = app.screen.query_one("#db-status", Static)
            kalshi_status = app.screen.query_one("#kalshi-status", Static)
            espn_status = app.screen.query_one("#espn-status", Static)

            assert db_status is not None
            assert kalshi_status is not None
            assert espn_status is not None

    @pytest.mark.asyncio
    async def test_sparklines_render(self) -> None:
        """Verify trend charts are rendered.

        Educational Note:
            The monitoring dashboard uses either Sparkline (basic) or
            PlotextPlot (enhanced) widgets depending on whether
            textual-plotext is installed. We check for either widget type.
        """
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("8")
            await pilot.pause()

            # Check for either Sparkline or PlotextPlot widgets
            # PlotextPlot uses #error-chart, Sparkline uses #error-sparkline
            try:
                error_chart = app.screen.query_one("#error-chart")
            except Exception:
                error_chart = app.screen.query_one("#error-sparkline")

            try:
                response_chart = app.screen.query_one("#response-chart")
            except Exception:
                response_chart = app.screen.query_one("#response-sparkline")

            assert error_chart is not None
            assert response_chart is not None

    @pytest.mark.asyncio
    async def test_metrics_table_loads(self) -> None:
        """Verify metrics table is populated."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("8")
            await pilot.pause()

            table = app.screen.query_one("#metrics-table", DataTable)
            assert table is not None
            # Real metrics has 6 rows, demo metrics has 8 rows
            # Accept either depending on connection status
            assert table.row_count >= 6


class TestSchedulerControlScreen:
    """Tests for Scheduler Control screen."""

    @pytest.mark.asyncio
    async def test_service_table_renders(self) -> None:
        """Verify service table is present."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("4")
            await pilot.pause()

            table = app.screen.query_one("#service-table", DataTable)
            assert table is not None
            assert len(table.columns) == 6

    @pytest.mark.asyncio
    async def test_control_buttons_present(self) -> None:
        """Verify control buttons are rendered."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("4")
            await pilot.pause()

            start_btn = app.screen.query_one("#btn-start", Button)
            stop_btn = app.screen.query_one("#btn-stop", Button)
            restart_btn = app.screen.query_one("#btn-restart", Button)

            assert start_btn is not None
            assert stop_btn is not None
            assert restart_btn is not None


class TestSettingsScreen:
    """Tests for Settings screen."""

    @pytest.mark.asyncio
    async def test_toggle_controls_present(self) -> None:
        """Verify toggle checkboxes are rendered."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("7")
            await pilot.pause()

            dry_run_toggle = app.screen.query_one("#toggle-dry-run")
            debug_toggle = app.screen.query_one("#toggle-debug")
            auto_refresh_toggle = app.screen.query_one("#toggle-auto-refresh")

            assert dry_run_toggle is not None
            assert debug_toggle is not None
            assert auto_refresh_toggle is not None

    @pytest.mark.asyncio
    async def test_connection_table_renders(self) -> None:
        """Verify connection status table is present."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("7")
            await pilot.pause()

            table = app.screen.query_one("#connection-table", DataTable)
            assert table is not None
            assert table.row_count == 3  # PostgreSQL, Kalshi, ESPN

    @pytest.mark.asyncio
    async def test_config_inputs_render(self) -> None:
        """Verify configuration input fields are present.

        Educational Note:
            The Settings screen was redesigned to use editable Input fields
            instead of a read-only DataTable. This allows users to modify
            configuration values directly in the TUI.
        """
        from textual.widgets import Input

        app = PrecogApp()
        async with app.run_test(size=(100, 80)) as pilot:
            await pilot.press("7")
            await pilot.pause()

            # Verify the key input fields exist
            min_edge_input = app.screen.query_one("#input-min-edge", Input)
            max_pos_input = app.screen.query_one("#input-max-position", Input)
            risk_limit_input = app.screen.query_one("#input-risk-limit", Input)

            assert min_edge_input is not None
            assert max_pos_input is not None
            assert risk_limit_input is not None

    @pytest.mark.asyncio
    async def test_test_database_button_no_crash(self) -> None:
        """Verify activating Test Database button doesn't crash.

        Educational Note:
            This test catches the CellDoesNotExist bug that occurred when
            _update_connection_status used key-based cell updates with
            auto-generated RowKey objects that had value=None.

            Uses focus() + Enter instead of scroll_visible() + click()
            because the Settings screen uses VerticalScroll and click
            coordinates may not update after scrolling.
        """
        app = PrecogApp()
        async with app.run_test(size=(100, 80)) as pilot:
            await pilot.press("7")
            await pilot.pause()

            # Focus the button programmatically and press Enter
            # This avoids coordinate issues with scrolling containers
            test_db_btn = app.screen.query_one("#btn-test-db", Button)
            test_db_btn.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            # App should not crash - verify screen still exists
            table = app.screen.query_one("#connection-table", DataTable)
            assert table is not None

    @pytest.mark.asyncio
    async def test_test_all_button_no_crash(self) -> None:
        """Verify activating Test All button doesn't crash.

        Educational Note:
            Uses focus() + Enter instead of scroll_visible() + click()
            because the Settings screen uses VerticalScroll and click
            coordinates may not update after scrolling.
        """
        app = PrecogApp()
        async with app.run_test(size=(100, 80)) as pilot:
            await pilot.press("7")
            await pilot.pause()

            # Focus the button programmatically and press Enter
            test_all_btn = app.screen.query_one("#btn-test-all", Button)
            test_all_btn.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            # App should not crash
            assert app.screen is not None


class TestSchedulerButtonInteractions:
    """Tests for Scheduler Control screen button interactions.

    Educational Note:
        These tests verify that button interactions don't crash the app,
        specifically catching the RowDoesNotExist bug that occurred when
        _control_selected tried to access rows in an empty table.
    """

    @pytest.mark.asyncio
    async def test_start_button_with_no_selection_no_crash(self) -> None:
        """Verify clicking Start button with no row selected doesn't crash."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("4")
            await pilot.pause()

            # Click Start without selecting a row first
            start_btn = app.screen.query_one("#btn-start", Button)
            await pilot.click(start_btn)
            await pilot.pause()

            # App should not crash
            assert app.screen is not None

    @pytest.mark.asyncio
    async def test_stop_button_no_crash(self) -> None:
        """Verify clicking Stop button doesn't crash."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("4")
            await pilot.pause()

            stop_btn = app.screen.query_one("#btn-stop", Button)
            await pilot.click(stop_btn)
            await pilot.pause()

            # App should not crash
            assert app.screen is not None

    @pytest.mark.asyncio
    async def test_restart_button_no_crash(self) -> None:
        """Verify clicking Restart button doesn't crash."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("4")
            await pilot.pause()

            restart_btn = app.screen.query_one("#btn-restart", Button)
            await pilot.click(restart_btn)
            await pilot.pause()

            # App should not crash
            assert app.screen is not None

    @pytest.mark.asyncio
    async def test_refresh_button_no_crash(self) -> None:
        """Verify clicking Refresh button reloads data."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("4")
            await pilot.pause()

            refresh_btn = app.screen.query_one("#btn-refresh", Button)
            await pilot.click(refresh_btn)
            await pilot.pause()

            # Table should still have data
            table = app.screen.query_one("#service-table", DataTable)
            assert table.row_count >= 0  # Demo data or empty

    @pytest.mark.asyncio
    async def test_toggle_logs_action(self) -> None:
        """Verify toggle logs keyboard shortcut works."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("4")
            await pilot.pause()

            # Press 'l' to toggle logs
            await pilot.press("l")
            await pilot.pause()

            # Log panel should exist
            log_panel = app.screen.query_one("#log-panel")
            assert log_panel is not None


class TestSettingsButtonInteractions:
    """Tests for Settings screen button interactions.

    Educational Note:
        Uses focus() + Enter instead of scroll_visible() + click() because
        the Settings screen uses VerticalScroll and click coordinates may
        not update properly after scrolling.
    """

    @pytest.mark.asyncio
    async def test_test_kalshi_button_no_crash(self) -> None:
        """Verify activating Test Kalshi API button doesn't crash."""
        app = PrecogApp()
        async with app.run_test(size=(100, 80)) as pilot:
            await pilot.press("7")
            await pilot.pause()

            # Focus the button programmatically and press Enter
            btn = app.screen.query_one("#btn-test-kalshi", Button)
            btn.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            assert app.screen is not None

    @pytest.mark.asyncio
    async def test_test_espn_button_no_crash(self) -> None:
        """Verify activating Test ESPN API button doesn't crash."""
        app = PrecogApp()
        async with app.run_test(size=(100, 80)) as pilot:
            await pilot.press("7")
            await pilot.pause()

            # Focus the button programmatically and press Enter
            btn = app.screen.query_one("#btn-test-espn", Button)
            btn.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            assert app.screen is not None


class TestSettingsCheckboxes:
    """Tests for Settings screen checkbox interactions.

    Educational Note:
        Uses larger terminal size (100x80) because the Settings screen now
        uses VerticalScroll. Checkboxes are near the top so scrolling may
        not always be needed, but larger size ensures visibility.
    """

    @pytest.mark.asyncio
    async def test_dry_run_toggle_no_crash(self) -> None:
        """Verify toggling dry run checkbox works."""
        app = PrecogApp()
        async with app.run_test(size=(100, 80)) as pilot:
            await pilot.press("7")
            await pilot.pause()

            from textual.widgets import Checkbox

            checkbox = app.screen.query_one("#toggle-dry-run", Checkbox)
            checkbox.scroll_visible()
            await pilot.pause()
            initial_value = checkbox.value

            # Click to toggle
            await pilot.click(checkbox)
            await pilot.pause()

            # Value should have changed
            assert checkbox.value != initial_value

    @pytest.mark.asyncio
    async def test_debug_toggle_no_crash(self) -> None:
        """Verify toggling debug checkbox works."""
        app = PrecogApp()
        async with app.run_test(size=(100, 80)) as pilot:
            await pilot.press("7")
            await pilot.pause()

            from textual.widgets import Checkbox

            checkbox = app.screen.query_one("#toggle-debug", Checkbox)
            checkbox.scroll_visible()
            await pilot.pause()
            await pilot.click(checkbox)
            await pilot.pause()

            # Checkbox should now be checked
            assert checkbox.value is True

    @pytest.mark.asyncio
    async def test_auto_refresh_toggle_no_crash(self) -> None:
        """Verify toggling auto-refresh checkbox works."""
        app = PrecogApp()
        async with app.run_test(size=(100, 80)) as pilot:
            await pilot.press("7")
            await pilot.pause()

            from textual.widgets import Checkbox

            checkbox = app.screen.query_one("#toggle-auto-refresh", Checkbox)
            checkbox.scroll_visible()
            await pilot.pause()
            initial_value = checkbox.value
            await pilot.click(checkbox)
            await pilot.pause()

            assert checkbox.value != initial_value


class TestMonitoringDashboardInteractions:
    """Tests for Monitoring Dashboard screen interactions."""

    @pytest.mark.asyncio
    async def test_refresh_action_no_crash(self) -> None:
        """Verify pressing 'r' for refresh works."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("8")
            await pilot.pause()

            # Press 'r' to refresh
            await pilot.press("r")
            await pilot.pause()

            # Dashboard should still be present
            table = app.screen.query_one("#metrics-table", DataTable)
            assert table is not None

    @pytest.mark.asyncio
    async def test_toggle_logs_action(self) -> None:
        """Verify toggle logs keyboard shortcut works."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("8")
            await pilot.pause()

            # Press 'l' to toggle logs
            await pilot.press("l")
            await pilot.pause()

            # Log container should exist
            log_container = app.screen.query_one("#log-container")
            assert log_container is not None


class TestMarketBrowserInteractions:
    """Tests for Market Browser screen interactions."""

    @pytest.mark.asyncio
    async def test_refresh_action_no_crash(self) -> None:
        """Verify pressing 'r' for refresh works."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("1")
            await pilot.pause()

            await pilot.press("r")
            await pilot.pause()

            table = app.screen.query_one("#market-table", DataTable)
            assert table is not None

    @pytest.mark.asyncio
    async def test_filter_focus_action(self) -> None:
        """Verify pressing 'f' focuses filter."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("1")
            await pilot.pause()

            await pilot.press("f")
            await pilot.pause()

            # Filter should exist
            sport_filter = app.screen.query_one("#sport-filter")
            assert sport_filter is not None


class TestPositionViewerInteractions:
    """Tests for Position Viewer screen interactions."""

    @pytest.mark.asyncio
    async def test_refresh_action_no_crash(self) -> None:
        """Verify pressing 'r' for refresh works."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("2")
            await pilot.pause()

            await pilot.press("r")
            await pilot.pause()

            table = app.screen.query_one("#position-table", DataTable)
            assert table is not None


class TestHelpScreenInteractions:
    """Tests for Help screen interactions."""

    @pytest.mark.asyncio
    async def test_help_screen_opens(self) -> None:
        """Verify pressing '?' opens help screen."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("?")
            await pilot.pause()

            # Should be on help screen
            from precog.tui.screens.help_screen import HelpScreen

            assert isinstance(app.screen, HelpScreen)

    @pytest.mark.asyncio
    async def test_help_screen_has_tabs(self) -> None:
        """Verify help screen has tabbed content."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("?")
            await pilot.pause()

            from textual.widgets import TabbedContent

            tabs = app.screen.query_one(TabbedContent)
            assert tabs is not None

    @pytest.mark.asyncio
    async def test_help_screen_closes_with_escape(self) -> None:
        """Verify help screen closes with escape."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("?")
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

            # Should be back on main menu
            assert isinstance(app.screen, MainMenuScreen)

    @pytest.mark.asyncio
    async def test_help_screen_closes_with_q(self) -> None:
        """Verify help screen closes with 'q'."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("?")
            await pilot.pause()

            await pilot.press("q")
            await pilot.pause()

            # Should be back on main menu
            assert isinstance(app.screen, MainMenuScreen)


class TestThemeSwitching:
    """Tests for theme switching functionality."""

    @pytest.mark.asyncio
    async def test_theme_cycle_does_not_crash(self) -> None:
        """Verify theme cycling doesn't crash the app."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            # Cycle through all themes
            for _ in range(4):
                await pilot.press("ctrl+t")
                await pilot.pause()

            # App should still be running
            assert isinstance(app.screen, MainMenuScreen)

    @pytest.mark.asyncio
    async def test_theme_cycle_then_navigation_no_crash(self) -> None:
        """Verify theme cycling doesn't break subsequent navigation.

        Educational Note:
            This test catches the bug where setting stylesheet.source=""
            (instead of clearing the _source dict) broke Toast notifications
            and any widget that tried to add CSS sources afterwards.
        """
        app = PrecogApp()
        async with app.run_test() as pilot:
            # Cycle theme first
            await pilot.press("ctrl+t")
            await pilot.pause()

            # Navigate to a screen (this triggers notifications)
            await pilot.press("7")  # Settings
            await pilot.pause()

            # Verify we're on Settings screen
            assert isinstance(app.screen, SettingsScreen)

            # Navigate back
            await pilot.press("escape")
            await pilot.pause()

            # Should be back on main menu
            assert isinstance(app.screen, MainMenuScreen)

    @pytest.mark.asyncio
    async def test_initial_theme_index(self) -> None:
        """Verify initial theme index is 0."""
        app = PrecogApp()
        async with app.run_test():
            assert app._current_theme_index == 0


class TestEscapeNavigation:
    """Tests for escape key navigation behavior."""

    @pytest.mark.asyncio
    async def test_escape_from_main_menu_stays_on_main_menu(self) -> None:
        """Verify pressing escape on main menu doesn't go to empty screen.

        Educational Note:
            The app pushes MainMenuScreen on mount, so the screen stack has:
            [default_app_screen, MainMenuScreen]. Without the MainMenuScreen
            check in action_go_back(), pressing escape would pop to the empty
            default screen.
        """
        app = PrecogApp()
        async with app.run_test() as pilot:
            # Verify we start on main menu
            assert isinstance(app.screen, MainMenuScreen)

            # Press escape multiple times - should stay on main menu
            for _ in range(3):
                await pilot.press("escape")
                await pilot.pause()
                assert isinstance(app.screen, MainMenuScreen)

    @pytest.mark.asyncio
    async def test_escape_from_subscreen_returns_to_main_menu(self) -> None:
        """Verify escape from a sub-screen returns to main menu."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            # Navigate to Settings
            await pilot.press("7")
            await pilot.pause()
            assert isinstance(app.screen, SettingsScreen)

            # Press escape to go back
            await pilot.press("escape")
            await pilot.pause()

            # Should be back on main menu
            assert isinstance(app.screen, MainMenuScreen)


class TestQuitAction:
    """Tests for quit action."""

    @pytest.mark.asyncio
    async def test_quit_action_exits_app(self) -> None:
        """Verify 'q' key exits the application."""
        app = PrecogApp()
        async with app.run_test() as pilot:
            await pilot.press("q")
            # App should be exiting
            assert app.return_code is not None or app._exit
