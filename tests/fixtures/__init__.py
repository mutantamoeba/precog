"""Test fixtures and factories for Precog testing.

This module exports all test fixtures and factory classes for use in tests.

Usage:
    from tests.fixtures import ESPN_NFL_SCOREBOARD_LIVE
    from tests.fixtures import ESPNScoreboardFactory, MarketDataFactory
"""

# API Response Fixtures
from tests.fixtures.api_responses import (
    DECIMAL_ARITHMETIC_TESTS,
    EXPECTED_BALANCE,
    EXPECTED_MARKET_DATA,
    EXPECTED_POSITION_DATA,
    KALSHI_BALANCE_RESPONSE,
    KALSHI_ERROR_400_RESPONSE,
    KALSHI_ERROR_401_RESPONSE,
    KALSHI_ERROR_429_RESPONSE,
    KALSHI_ERROR_500_RESPONSE,
    KALSHI_FILLS_RESPONSE,
    KALSHI_MARKET_RESPONSE,
    KALSHI_POSITIONS_RESPONSE,
    KALSHI_SETTLEMENTS_RESPONSE,
    KALSHI_SINGLE_MARKET_RESPONSE,
    SUB_PENNY_TEST_CASES,
)

# ESPN Response Fixtures
from tests.fixtures.espn_responses import (
    ESPN_ERROR_404_RESPONSE,
    ESPN_ERROR_500_RESPONSE,
    ESPN_ERROR_503_RESPONSE,
    ESPN_NCAAF_SCOREBOARD_LIVE,
    ESPN_NFL_SCOREBOARD_EMPTY,
    ESPN_NFL_SCOREBOARD_FINAL,
    ESPN_NFL_SCOREBOARD_HALFTIME,
    ESPN_NFL_SCOREBOARD_LIVE,
    ESPN_NFL_SCOREBOARD_OVERTIME,
    ESPN_NFL_SCOREBOARD_PREGAME,
    ESPN_NFL_SCOREBOARD_REDZONE,
    ESPN_RESPONSE_MISSING_COMPETITORS,
    ESPN_RESPONSE_MISSING_EVENTS,
    ESPN_RESPONSE_NULL_SCORES,
    EXPECTED_GAME_STATE_FINAL,
    EXPECTED_GAME_STATE_HALFTIME,
    EXPECTED_GAME_STATE_LIVE,
    EXPECTED_GAME_STATE_PREGAME,
    RATE_LIMIT_TEST_SCENARIOS,
)

# Factories
from tests.fixtures.factories import (
    # Base
    BaseFactory,
    # Market/Trading
    DecimalEdgeCaseFactory,
    # ESPN Factories (Phase 2)
    ESPNCompetitionFactory,
    ESPNCompetitorFactory,
    ESPNEventFactory,
    ESPNGameStatusFactory,
    ESPNScoreboardFactory,
    ESPNSituationFactory,
    ESPNTeamFactory,
    # Game State
    GameStateDataFactory,
    MarketDataFactory,
    PositionDataFactory,
    ProbabilityModelDataFactory,
    StrategyDataFactory,
    TradeDataFactory,
    # Helper Functions
    create_test_market_with_position,
    create_test_trade_sequence,
    create_versioned_strategies,
)

# Logical grouping by category - Kalshi, ESPN, Factories, Helpers
__all__ = [  # noqa: RUF022
    # Kalshi API Responses
    "KALSHI_MARKET_RESPONSE",
    "KALSHI_SINGLE_MARKET_RESPONSE",
    "KALSHI_BALANCE_RESPONSE",
    "KALSHI_POSITIONS_RESPONSE",
    "KALSHI_FILLS_RESPONSE",
    "KALSHI_SETTLEMENTS_RESPONSE",
    "KALSHI_ERROR_401_RESPONSE",
    "KALSHI_ERROR_429_RESPONSE",
    "KALSHI_ERROR_500_RESPONSE",
    "KALSHI_ERROR_400_RESPONSE",
    "EXPECTED_MARKET_DATA",
    "EXPECTED_BALANCE",
    "EXPECTED_POSITION_DATA",
    "SUB_PENNY_TEST_CASES",
    "DECIMAL_ARITHMETIC_TESTS",
    # ESPN Response Fixtures
    "ESPN_NFL_SCOREBOARD_LIVE",
    "ESPN_NFL_SCOREBOARD_PREGAME",
    "ESPN_NFL_SCOREBOARD_FINAL",
    "ESPN_NFL_SCOREBOARD_HALFTIME",
    "ESPN_NFL_SCOREBOARD_EMPTY",
    "ESPN_NFL_SCOREBOARD_OVERTIME",
    "ESPN_NFL_SCOREBOARD_REDZONE",
    "ESPN_NCAAF_SCOREBOARD_LIVE",
    "ESPN_ERROR_404_RESPONSE",
    "ESPN_ERROR_500_RESPONSE",
    "ESPN_ERROR_503_RESPONSE",
    "ESPN_RESPONSE_MISSING_EVENTS",
    "ESPN_RESPONSE_MISSING_COMPETITORS",
    "ESPN_RESPONSE_NULL_SCORES",
    "EXPECTED_GAME_STATE_LIVE",
    "EXPECTED_GAME_STATE_PREGAME",
    "EXPECTED_GAME_STATE_FINAL",
    "EXPECTED_GAME_STATE_HALFTIME",
    "RATE_LIMIT_TEST_SCENARIOS",
    # Factories
    "BaseFactory",
    "MarketDataFactory",
    "PositionDataFactory",
    "TradeDataFactory",
    "StrategyDataFactory",
    "ProbabilityModelDataFactory",
    "DecimalEdgeCaseFactory",
    "GameStateDataFactory",
    # ESPN Factories
    "ESPNTeamFactory",
    "ESPNCompetitorFactory",
    "ESPNGameStatusFactory",
    "ESPNSituationFactory",
    "ESPNCompetitionFactory",
    "ESPNEventFactory",
    "ESPNScoreboardFactory",
    # Helper Functions
    "create_test_market_with_position",
    "create_test_trade_sequence",
    "create_versioned_strategies",
    # Testcontainers (ADR-057)
    "postgres_container",
    "container_db_connection",
    "container_cursor",
    "TESTCONTAINERS_AVAILABLE",
    # Detection flags for test configuration
    "DOCKER_AVAILABLE",
    "USE_TESTCONTAINERS",
]


# Testcontainers fixtures (ADR-057: Testcontainers for Database Test Isolation)
# These provide ephemeral PostgreSQL containers for ALL database tests
# Strategy:
#   - Local (Docker available): Uses testcontainers for isolation
#   - CI (testcontainers not installed): Uses PostgreSQL service container
try:
    from tests.fixtures.testcontainers_fixtures import (
        TESTCONTAINERS_AVAILABLE,
        container_cursor,
        container_db_connection,
        postgres_container,
    )
except ImportError:
    # testcontainers not installed - fixtures will skip tests
    TESTCONTAINERS_AVAILABLE = False
    # These fixtures are only available when testcontainers is installed
    postgres_container = None  # type: ignore[assignment]
    container_db_connection = None  # type: ignore[assignment]
    container_cursor = None  # type: ignore[assignment]


def _check_docker_available() -> bool:
    """Check if Docker is available for testcontainers."""
    import shutil
    import subprocess

    # Check if docker command exists
    if not shutil.which("docker"):
        return False

    # Check if Docker daemon is running
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


# Detection flags for test configuration
DOCKER_AVAILABLE = _check_docker_available()
USE_TESTCONTAINERS = DOCKER_AVAILABLE and TESTCONTAINERS_AVAILABLE
