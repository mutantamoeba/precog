"""
Scheduler module for Precog live data polling and streaming.

This module provides scheduling infrastructure for periodic and real-time tasks:
- Live game state polling from ESPN APIs (MarketUpdater)
- Market price polling from Kalshi REST APIs (KalshiMarketPoller)
- Real-time market price streaming via Kalshi WebSocket (KalshiWebSocketHandler)

Components:
    MarketUpdater: APScheduler-based live game polling service (ESPN)
    create_market_updater: Factory function for creating ESPN updaters
    run_single_poll: Execute a one-time ESPN poll without scheduling

    KalshiMarketPoller: APScheduler-based market price polling (Kalshi REST)
    create_kalshi_poller: Factory function for creating Kalshi pollers
    run_single_kalshi_poll: Execute a one-time Kalshi poll without scheduling

    KalshiWebSocketHandler: Real-time market streaming (Kalshi WebSocket)
    create_websocket_handler: Factory function for creating WebSocket handlers

Hybrid Architecture:
    KalshiMarketPoller + KalshiWebSocketHandler work together:
    - WebSocket provides real-time updates (<1 second latency)
    - Polling provides reliability (fallback if WebSocket fails)
    - Polling validates WebSocket data (detect missed messages)

Example:
    >>> # ESPN game state polling
    >>> from precog.schedulers import MarketUpdater
    >>> updater = MarketUpdater(leagues=["nfl"])
    >>> updater.start()  # Starts polling in background
    >>> updater.stop()   # Clean shutdown
    >>>
    >>> # Kalshi market price polling (REST API)
    >>> from precog.schedulers import KalshiMarketPoller
    >>> poller = KalshiMarketPoller(series_tickers=["KXNFLGAME"])
    >>> poller.start()   # Starts polling in background
    >>> poller.stop()    # Clean shutdown
    >>>
    >>> # Kalshi real-time streaming (WebSocket)
    >>> from precog.schedulers import KalshiWebSocketHandler
    >>> handler = KalshiWebSocketHandler(environment="demo")
    >>> handler.subscribe(["INXD-25AUXA-T64"])
    >>> handler.start()  # Real-time updates flow
    >>> handler.stop()   # Clean shutdown

Reference: Phase 2 Live Data Integration
Related: docs/guides/ESPN_DATA_MODEL_V1.0.md
"""

from precog.schedulers.kalshi_poller import (
    KalshiMarketPoller,
    create_kalshi_poller,
    run_single_kalshi_poll,
)
from precog.schedulers.kalshi_websocket import (
    ConnectionState,
    KalshiWebSocketHandler,
    create_websocket_handler,
)
from precog.schedulers.market_updater import (
    MarketUpdater,
    create_market_updater,
    run_single_poll,
)

__all__ = [
    "ConnectionState",
    "KalshiMarketPoller",
    "KalshiWebSocketHandler",
    "MarketUpdater",
    "create_kalshi_poller",
    "create_market_updater",
    "create_websocket_handler",
    "run_single_kalshi_poll",
    "run_single_poll",
]
