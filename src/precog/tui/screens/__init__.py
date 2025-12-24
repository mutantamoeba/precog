"""
Precog TUI Screens.

Each screen represents a major functional area of the application.

Screens:
    MainMenuScreen: Landing screen with navigation menu
    MarketOverviewScreen: Live market data dashboard (planned)
    PositionsScreen: Current positions and P&L (planned)
    TradesScreen: Trade execution interface (planned)
    SchedulerScreen: Poller control panel (planned)
    StrategyScreen: Strategy management (planned)
    ModelsScreen: Model management (planned)
    ConfigScreen: Configuration viewer/editor (planned)
    DiagnosticsScreen: System diagnostics (planned)
"""

from precog.tui.screens.main_menu import MainMenuScreen

__all__ = ["MainMenuScreen"]
