"""
Scheduler module for Precog live data polling and streaming.

This module provides scheduling infrastructure for periodic and real-time tasks:
- Live game state polling from ESPN APIs (ESPNGamePoller)
- Market price polling from Kalshi REST APIs (KalshiMarketPoller)
- Real-time market price streaming via Kalshi WebSocket (KalshiWebSocketHandler)
- Multi-service orchestration (ServiceSupervisor)
- Base polling infrastructure (BasePoller)

Components:
    BasePoller: Abstract base class for all polling-based services
        - Template Method pattern for consistent polling infrastructure
        - Thread-safe statistics tracking
        - APScheduler-based job scheduling

    ESPNGamePoller: APScheduler-based live game polling service (ESPN)
    create_espn_poller: Factory function for creating ESPN pollers
    run_single_espn_poll: Execute a one-time ESPN poll without scheduling
    refresh_all_scoreboards: Convenience function for scoreboard refresh

    KalshiMarketPoller: APScheduler-based market price polling (Kalshi REST)
    create_kalshi_poller: Factory function for creating Kalshi pollers
    run_single_kalshi_poll: Execute a one-time Kalshi poll without scheduling

    KalshiWebSocketHandler: Real-time market streaming (Kalshi WebSocket)
    create_websocket_handler: Factory function for creating WebSocket handlers

    ServiceSupervisor: Multi-service orchestration with health monitoring
    create_supervisor: Factory for creating configured supervisors
    create_services: Factory for creating service instances

Naming Convention:
    {Platform}{Entity}Poller pattern for consistency:
    - ESPNGamePoller: Polls ESPN for game states
    - KalshiMarketPoller: Polls Kalshi for market prices
    - Future: PolymarketPricePoller, etc.

Hybrid Architecture:
    KalshiMarketPoller + KalshiWebSocketHandler work together:
    - WebSocket provides real-time updates (<1 second latency)
    - Polling provides reliability (fallback if WebSocket fails)
    - Polling validates WebSocket data (detect missed messages)

Service Supervisor:
    For production deployments, use ServiceSupervisor to manage all services:
    - Health monitoring with configurable intervals
    - Auto-restart with exponential backoff
    - Circuit breaker for repeated failures
    - Metrics aggregation across all services

Example:
    >>> # ESPN game state polling (new name)
    >>> from precog.schedulers import ESPNGamePoller
    >>> poller = ESPNGamePoller(leagues=["nfl"])
    >>> poller.start()  # Starts polling in background
    >>> poller.stop()   # Clean shutdown
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
    >>>
    >>> # Multi-service supervisor (production)
    >>> from precog.schedulers import create_supervisor
    >>> supervisor = create_supervisor(
    ...     environment="development",
    ...     enabled_services={"espn", "kalshi_rest"}
    ... )
    >>> supervisor.start_all()  # Starts all services with monitoring
    >>> supervisor.stop_all()   # Graceful shutdown

Reference: Phase 2.5 Live Data Collection Service
Related: docs/guides/ESPN_DATA_MODEL_V1.0.md
Related: ADR-100 (Service Supervisor Pattern)
"""

# Base poller infrastructure
from precog.schedulers.base_poller import BasePoller, PollerStats

# ESPN game polling (new naming)
from precog.schedulers.espn_game_poller import (
    ESPNGamePoller,
    create_espn_poller,
    refresh_all_scoreboards,
    run_single_espn_poll,
)

# Kalshi market polling
from precog.schedulers.kalshi_poller import (
    KalshiMarketPoller,
    create_kalshi_poller,
    run_single_kalshi_poll,
)

# Kalshi WebSocket streaming
from precog.schedulers.kalshi_websocket import (
    ConnectionState,
    KalshiWebSocketHandler,
    create_websocket_handler,
)

# Market data management
from precog.schedulers.market_data_manager import (
    DataSourceStatus,
    MarketDataManager,
    create_market_data_manager,
)

# Service supervision
from precog.schedulers.service_supervisor import (
    Environment,
    EventLoopService,
    RunnerConfig,
    ServiceConfig,
    ServiceState,
    ServiceSupervisor,
    create_services,
    create_supervisor,
)

# =============================================================================
# Backward Compatibility Aliases
# =============================================================================
# These aliases maintain compatibility during the transition period.
# TODO: Remove after all external code is updated (Phase 2.5 completion)

# Old ESPN class names -> new names
MarketUpdater = ESPNGamePoller
create_market_updater = create_espn_poller
run_single_poll = run_single_espn_poll

__all__ = [
    # Base infrastructure
    "BasePoller",
    # Connection and status enums
    "ConnectionState",
    "DataSourceStatus",
    # ESPN services (new names)
    "ESPNGamePoller",
    "Environment",
    # Service protocols and state
    "EventLoopService",
    # Kalshi services
    "KalshiMarketPoller",
    "KalshiWebSocketHandler",
    # Market data services
    "MarketDataManager",
    # =============================================================================
    # Backward Compatibility Aliases (deprecated - will be removed)
    # =============================================================================
    "MarketUpdater",  # Use ESPNGamePoller instead
    "PollerStats",
    # Configuration dataclasses
    "RunnerConfig",
    "ServiceConfig",
    "ServiceState",
    # Supervisor
    "ServiceSupervisor",
    "create_espn_poller",
    # Factory functions
    "create_kalshi_poller",
    "create_market_data_manager",
    "create_market_updater",  # Use create_espn_poller instead
    "create_services",
    "create_supervisor",
    "create_websocket_handler",
    # Utility functions
    "refresh_all_scoreboards",
    "run_single_espn_poll",
    "run_single_kalshi_poll",
    "run_single_poll",  # Use run_single_espn_poll instead
]
