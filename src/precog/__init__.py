"""
Precog - Prediction Market Trading System

Automated positive expected value (EV+) trading on prediction markets.

Modules:
    api_connectors: External API integrations (Kalshi, ESPN, Balldontlie)
    database: PostgreSQL database layer (connection, CRUD, migrations)
    config: YAML configuration management
    utils: Utilities (logging, helpers)

Example:
    >>> from precog.api_connectors import KalshiClient
    >>> from precog.config import ConfigLoader
    >>> from precog.database import get_connection

Reference:
    docs/foundation/PROJECT_OVERVIEW_V1.3.md - System architecture
    CLAUDE.md - Development guidelines and patterns
"""

__version__ = "0.1.0"  # Sync with pyproject.toml

# Human: continue
