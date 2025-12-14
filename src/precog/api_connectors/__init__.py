"""
API Connectors module for external integrations.

Provides clients for:
- Kalshi API (prediction markets)
- ESPN API (sports data) - Phase 2
- Balldontlie API (NBA data) - Phase 2
"""

from precog.api_connectors.kalshi_client import KalshiClient, KalshiDemoUnavailableError

__all__ = ["KalshiClient", "KalshiDemoUnavailableError"]
