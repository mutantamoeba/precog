"""
Scheduler module for Precog live data polling.

This module provides scheduling infrastructure for periodic tasks:
- Live game state polling from ESPN APIs (MarketUpdater)
- Market price polling from Kalshi APIs (KalshiMarketPoller)

Components:
    MarketUpdater: APScheduler-based live game polling service (ESPN)
    create_market_updater: Factory function for creating ESPN updaters
    run_single_poll: Execute a one-time ESPN poll without scheduling

    KalshiMarketPoller: APScheduler-based market price polling (Kalshi)
    create_kalshi_poller: Factory function for creating Kalshi pollers
    run_single_kalshi_poll: Execute a one-time Kalshi poll without scheduling

Example:
    >>> # ESPN game state polling
    >>> from precog.schedulers import MarketUpdater
    >>> updater = MarketUpdater(leagues=["nfl"])
    >>> updater.start()  # Starts polling in background
    >>> updater.stop()   # Clean shutdown
    >>>
    >>> # Kalshi market price polling
    >>> from precog.schedulers import KalshiMarketPoller
    >>> poller = KalshiMarketPoller(series_tickers=["KXNFLGAME"])
    >>> poller.start()   # Starts polling in background
    >>> poller.stop()    # Clean shutdown

Reference: Phase 2 Live Data Integration
Related: docs/guides/ESPN_DATA_MODEL_V1.0.md
"""

from precog.schedulers.kalshi_poller import (
    KalshiMarketPoller,
    create_kalshi_poller,
    run_single_kalshi_poll,
)
from precog.schedulers.market_updater import (
    MarketUpdater,
    create_market_updater,
    run_single_poll,
)

__all__ = [
    "KalshiMarketPoller",
    "MarketUpdater",
    "create_kalshi_poller",
    "create_market_updater",
    "run_single_kalshi_poll",
    "run_single_poll",
]
