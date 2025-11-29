"""
Scheduler module for Precog live data polling.

This module provides scheduling infrastructure for periodic tasks,
primarily focused on live game state polling from ESPN APIs.

Components:
    MarketUpdater: APScheduler-based live game polling service
    create_market_updater: Factory function for creating updaters
    run_single_poll: Execute a one-time poll without scheduling

Example:
    >>> from precog.schedulers import MarketUpdater
    >>> updater = MarketUpdater(leagues=["nfl"])
    >>> updater.start()  # Starts polling in background
    >>> # ... application runs ...
    >>> updater.stop()   # Clean shutdown

Reference: Phase 2 Live Data Integration
Related: docs/guides/ESPN_DATA_MODEL_V1.0.md
"""

from precog.schedulers.market_updater import (
    MarketUpdater,
    create_market_updater,
    run_single_poll,
)

__all__ = [
    "MarketUpdater",
    "create_market_updater",
    "run_single_poll",
]
