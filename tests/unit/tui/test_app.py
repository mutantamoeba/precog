"""Unit tests for TUI App module.

Tests for the Precog TUI application core functionality.

Reference:
    - Issue #268: Textual-based Sci-Fi Terminal UI
    - src/precog/tui/app.py
"""

from __future__ import annotations


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


class TestRunFunction:
    """Test the run() function."""

    def test_run_function_exists(self) -> None:
        """Verify run function is exported."""
        from precog.tui.app import run

        assert callable(run)
