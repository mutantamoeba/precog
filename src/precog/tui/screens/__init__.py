"""
Precog TUI Screens.

Each screen represents a major functional area of the application.

Screens:
    MainMenuScreen: Landing screen with navigation menu
    MarketBrowserScreen: Market browsing with filters
    PositionViewerScreen: Current positions and P&L
    SchedulerControlScreen: Poller control panel
    MonitoringDashboardScreen: System health monitoring
    SettingsScreen: Configuration viewer/editor
    TradesScreen: Trade execution interface (planned)
    StrategyScreen: Strategy management (planned)
    ModelsScreen: Model management (planned)
"""

from precog.tui.screens.main_menu import MainMenuScreen
from precog.tui.screens.market_browser import MarketBrowserScreen
from precog.tui.screens.monitoring_dashboard import MonitoringDashboardScreen
from precog.tui.screens.position_viewer import PositionViewerScreen
from precog.tui.screens.scheduler_control import SchedulerControlScreen
from precog.tui.screens.settings import SettingsScreen

__all__ = [
    "MainMenuScreen",
    "MarketBrowserScreen",
    "MonitoringDashboardScreen",
    "PositionViewerScreen",
    "SchedulerControlScreen",
    "SettingsScreen",
]
