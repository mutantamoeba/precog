"""Unit tests for TUI App module.

Tests for the Precog TUI application core functionality.

Reference:
    - Issue #268: Textual-based Sci-Fi Terminal UI
    - src/precog/tui/app.py
"""

from __future__ import annotations

import pytest

# Skip all tests in this module if textual is not installed (optional dependency)
pytest.importorskip("textual")


class TestPrecogAppConfiguration:
    """Test PrecogApp class configuration and attributes."""

    def test_precog_app_has_title(self) -> None:
        """Verify PrecogApp has TITLE attribute."""
        from precog.tui.app import PrecogApp

        assert hasattr(PrecogApp, "TITLE")
        assert PrecogApp.TITLE == "PRECOG"

    def test_precog_app_has_subtitle(self) -> None:
        """Verify PrecogApp has SUB_TITLE attribute."""
        from precog.tui.app import PrecogApp

        assert hasattr(PrecogApp, "SUB_TITLE")
        assert PrecogApp.SUB_TITLE == "Prediction Market Intelligence"

    def test_precog_app_has_themes(self) -> None:
        """Verify PrecogApp has THEMES list."""
        from precog.tui.app import PrecogApp

        assert hasattr(PrecogApp, "THEMES")
        assert isinstance(PrecogApp.THEMES, list)
        assert len(PrecogApp.THEMES) >= 4
        assert "precog_dark" in PrecogApp.THEMES

    def test_precog_app_has_bindings(self) -> None:
        """Verify PrecogApp has BINDINGS for keyboard shortcuts."""
        from precog.tui.app import PrecogApp

        assert hasattr(PrecogApp, "BINDINGS")
        assert len(PrecogApp.BINDINGS) >= 3  # q, ctrl+t, ?


class TestDataSourceMode:
    """Test PrecogApp data source mode functionality.

    Educational Note:
        The data source mode controls whether screens use:
        - "auto": Try database first, fall back to demo data on error
        - "demo": Always use demo data, skip database queries
        - "real": Only use database, show errors if unavailable
    """

    def test_precog_app_has_data_source_modes(self) -> None:
        """Verify PrecogApp has DATA_SOURCE_MODES list."""
        from precog.tui.app import PrecogApp

        assert hasattr(PrecogApp, "DATA_SOURCE_MODES")
        assert isinstance(PrecogApp.DATA_SOURCE_MODES, list)
        assert "auto" in PrecogApp.DATA_SOURCE_MODES
        assert "demo" in PrecogApp.DATA_SOURCE_MODES
        assert "real" in PrecogApp.DATA_SOURCE_MODES

    def test_precog_app_default_data_source_mode_is_auto(self) -> None:
        """Verify default data source mode is 'auto'."""
        from precog.tui.app import PrecogApp

        app = PrecogApp()
        assert app.data_source_mode == "auto"

    def test_precog_app_can_set_data_source_mode(self) -> None:
        """Verify data source mode can be changed."""
        from precog.tui.app import PrecogApp

        app = PrecogApp()
        app.data_source_mode = "demo"
        assert app.data_source_mode == "demo"

        app.data_source_mode = "real"
        assert app.data_source_mode == "real"

        app.data_source_mode = "auto"
        assert app.data_source_mode == "auto"

    def test_precog_app_rejects_invalid_data_source_mode(self) -> None:
        """Verify invalid data source mode raises ValueError."""
        from precog.tui.app import PrecogApp

        app = PrecogApp()
        with pytest.raises(ValueError, match="Invalid data source mode"):
            app.data_source_mode = "invalid_mode"


class TestApiEnvironmentMode:
    """Test PrecogApp API environment mode functionality.

    Educational Note:
        The API environment mode controls which Kalshi API endpoint is used:
        - "demo": Paper trading with test accounts (demo-api.kalshi.com)
        - "production": Real money trading (trading-api.kalshi.com)
    """

    def test_precog_app_has_api_environments(self) -> None:
        """Verify PrecogApp has API_ENVIRONMENTS list."""
        from precog.tui.app import PrecogApp

        assert hasattr(PrecogApp, "API_ENVIRONMENTS")
        assert isinstance(PrecogApp.API_ENVIRONMENTS, list)
        assert "demo" in PrecogApp.API_ENVIRONMENTS
        assert "production" in PrecogApp.API_ENVIRONMENTS

    def test_precog_app_default_api_environment_is_demo(self) -> None:
        """Verify default API environment is 'demo' for safety."""
        from precog.tui.app import PrecogApp

        app = PrecogApp()
        assert app.api_environment == "demo"

    def test_precog_app_can_set_api_environment(self) -> None:
        """Verify API environment can be changed."""
        from precog.tui.app import PrecogApp

        app = PrecogApp()
        app.api_environment = "production"
        assert app.api_environment == "production"

        app.api_environment = "demo"
        assert app.api_environment == "demo"

    def test_precog_app_rejects_invalid_api_environment(self) -> None:
        """Verify invalid API environment raises ValueError."""
        from precog.tui.app import PrecogApp

        app = PrecogApp()
        with pytest.raises(ValueError, match="Invalid API environment"):
            app.api_environment = "invalid_env"


class TestRunFunction:
    """Test the run() function."""

    def test_run_function_exists(self) -> None:
        """Verify run function is exported."""
        from precog.tui.app import run

        assert callable(run)
