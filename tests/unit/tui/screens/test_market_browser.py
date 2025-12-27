"""Unit tests for TUI Market Browser Screen.

Tests for the market browser screen and its components.

Reference:
    - Issue #283: TUI Additional Screens
    - src/precog/tui/screens/market_browser.py
"""

from __future__ import annotations

import pytest

# Skip all tests in this module if textual is not installed (optional dependency)
pytest.importorskip("textual")


class TestMarketBrowserScreen:
    """Test MarketBrowserScreen class."""

    def test_market_browser_screen_has_bindings(self) -> None:
        """Verify MarketBrowserScreen has key bindings."""
        from precog.tui.screens.market_browser import MarketBrowserScreen

        assert hasattr(MarketBrowserScreen, "BINDINGS")
        assert len(MarketBrowserScreen.BINDINGS) >= 3  # r, f, escape

    def test_market_browser_screen_instantiates(self) -> None:
        """Verify MarketBrowserScreen can be instantiated."""
        from precog.tui.screens.market_browser import MarketBrowserScreen

        screen = MarketBrowserScreen()
        assert screen is not None

    def test_market_browser_has_load_markets_method(self) -> None:
        """Verify screen has _load_markets method."""
        from precog.tui.screens.market_browser import MarketBrowserScreen

        screen = MarketBrowserScreen()
        assert hasattr(screen, "_load_markets")
        assert callable(screen._load_markets)

    def test_market_browser_has_demo_data_fallback(self) -> None:
        """Verify screen has _load_demo_data method for graceful fallback."""
        from precog.tui.screens.market_browser import MarketBrowserScreen

        screen = MarketBrowserScreen()
        assert hasattr(screen, "_load_demo_data")
        assert callable(screen._load_demo_data)
