"""
Pytest configuration and shared fixtures.

Fixtures are reusable test setup/teardown functions.
They run before each test that uses them.

Environment Safety:
    This module enforces test environment via require_environment("test").
    Tests will fail immediately if DB_NAME doesn't contain 'test' or
    PRECOG_ENV isn't set to 'test'. This prevents accidental test runs
    against dev/staging/prod databases.

    See: docs/guides/DATABASE_ENVIRONMENT_STRATEGY_V1.0.md
"""

import os
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from precog.config.config_loader import ConfigLoader

# Import modules to test
from precog.database.connection import (
    close_pool,
    get_cursor,
    get_environment,
    initialize_pool,
)
from precog.database.crud_operations import create_strategy
from precog.utils.logger import setup_logging

# =============================================================================
# DATABASE FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def db_pool():
    """
    Create database connection pool once per test session.

    Scope: session - created once, shared across all tests
    """
    # Initialize pool
    pool = initialize_pool(minconn=2, maxconn=5)

    yield pool  # Return pool object to tests

    # Cleanup: close pool after all tests complete
    close_pool()


@pytest.fixture
def db_cursor(db_pool):
    """
    Provide database cursor with automatic rollback.

    Each test gets a fresh cursor, changes are rolled back after test.
    This ensures tests don't affect each other.

    Scope: function - new cursor for each test
    """
    with get_cursor(commit=False) as cur:
        yield cur
        # Rollback happens automatically in finally block


@pytest.fixture
def clean_test_data(db_cursor):
    """
    Clean up test data before and after each test.

    Creates required parent records (platforms, events) for testing.
    Deletes any test records (IDs starting with 'TEST-')
    """
    # Cleanup before test (in reverse FK order)
    # Delete child records first (trades and positions reference strategies/models/markets)
    db_cursor.execute("DELETE FROM trades WHERE market_id LIKE 'MKT-TEST-%'")
    db_cursor.execute(
        "DELETE FROM positions WHERE market_id LIKE 'MKT-TEST-%' OR market_id LIKE 'KALSHI-%' OR strategy_id > 1 OR model_id > 1"
    )
    # Then delete parent records
    db_cursor.execute("DELETE FROM markets WHERE market_id LIKE 'MKT-TEST-%'")
    db_cursor.execute("DELETE FROM events WHERE event_id LIKE 'TEST-%'")
    db_cursor.execute("DELETE FROM series WHERE series_id LIKE 'TEST-%'")
    # Clean up test models and strategies (models/strategies created during tests)
    db_cursor.execute("DELETE FROM probability_models WHERE model_id > 1")  # Keep model_id=1 for FK
    db_cursor.execute("DELETE FROM strategies WHERE strategy_id > 1")  # Keep strategy_id=1 for FK
    # Delete both uppercase TEST-PLATFORM- and lowercase test_ platforms
    db_cursor.execute(
        "DELETE FROM platforms WHERE platform_id LIKE 'test_%' OR platform_id LIKE 'TEST-PLATFORM-%'"
    )

    # Create test platform if not exists
    db_cursor.execute("""
        INSERT INTO platforms (platform_id, platform_type, display_name, base_url, status)
        VALUES ('test_platform', 'trading', 'Test Platform', 'https://test.example.com', 'active')
        ON CONFLICT (platform_id) DO NOTHING
    """)

    # Create test series
    db_cursor.execute("""
        INSERT INTO series (series_id, platform_id, external_id, title, category)
        VALUES ('TEST-SERIES-NFL', 'test_platform', 'TEST-EXT-SERIES', 'Test NFL Series', 'sports')
        ON CONFLICT (series_id) DO NOTHING
    """)

    # Create test event
    db_cursor.execute("""
        INSERT INTO events (event_id, platform_id, series_id, external_id, category, title, status)
        VALUES ('TEST-EVT-NFL-KC-BUF', 'test_platform', 'TEST-SERIES-NFL', 'TEST-EXT-EVT', 'sports', 'Test Event: KC vs BUF', 'scheduled')
        ON CONFLICT (event_id) DO NOTHING
    """)

    # Create additional test event for test_execute_query
    db_cursor.execute("""
        INSERT INTO events (event_id, platform_id, series_id, external_id, category, title, status)
        VALUES ('TEST-EVT', 'test_platform', 'TEST-SERIES-NFL', 'TEST-EVT-2', 'sports', 'Test Event 2', 'scheduled')
        ON CONFLICT (event_id) DO NOTHING
    """)

    # Create test strategy (required parent record for positions and trades)
    db_cursor.execute("""
        INSERT INTO strategies (strategy_id, strategy_name, strategy_version, strategy_type, config, status)
        VALUES (1, 'test_strategy', 'v1.0', 'value', '{"test": true}', 'active')
        ON CONFLICT (strategy_id) DO NOTHING
    """)

    # Create test probability model (required parent record for positions and trades)
    db_cursor.execute("""
        INSERT INTO probability_models (model_id, model_name, model_version, model_class, config, status)
        VALUES (1, 'test_model', 'v1.0', 'elo', '{"test": true}', 'active')
        ON CONFLICT (model_id) DO NOTHING
    """)

    db_cursor.connection.commit()

    yield  # Test runs here

    # Cleanup after test (in reverse FK order)
    # Delete child records first (trades and positions reference strategies/models/markets)
    db_cursor.execute("DELETE FROM trades WHERE market_id LIKE 'MKT-TEST-%'")
    db_cursor.execute(
        "DELETE FROM positions WHERE market_id LIKE 'MKT-TEST-%' OR market_id LIKE 'KALSHI-%' OR strategy_id > 1 OR model_id > 1"
    )
    # Then delete parent records
    db_cursor.execute("DELETE FROM markets WHERE market_id LIKE 'MKT-TEST-%'")
    db_cursor.execute("DELETE FROM events WHERE event_id LIKE 'TEST-%'")
    db_cursor.execute("DELETE FROM series WHERE series_id LIKE 'TEST-%'")
    # Clean up test models and strategies (models/strategies created during tests)
    db_cursor.execute("DELETE FROM probability_models WHERE model_id > 1")  # Keep model_id=1 for FK
    db_cursor.execute("DELETE FROM strategies WHERE strategy_id > 1")  # Keep strategy_id=1 for FK
    # Don't delete test platform - keep it for other tests
    db_cursor.connection.commit()


# =============================================================================
# TEST DATA FIXTURES
# =============================================================================


@pytest.fixture
def sample_market_data():
    """Sample market data for testing."""
    return {
        "platform_id": "test_platform",  # Must match clean_test_data fixture
        "event_id": "TEST-EVT-NFL-KC-BUF",  # Must match clean_test_data fixture
        "external_id": "TEST-EXT-123",
        "ticker": "TEST-NFL-KC-BUF-YES",
        "title": "TEST: Chiefs to beat Bills",
        "yes_price": Decimal("0.5200"),
        "no_price": Decimal("0.4800"),
        "market_type": "binary",
        "status": "open",
        "volume": 1000,
        "open_interest": 500,
    }


@pytest.fixture
def sample_position_data():
    """Sample position data for testing."""
    return {
        "strategy_id": 1,
        "model_id": 1,
        "side": "YES",
        "quantity": 100,
        "entry_price": Decimal("0.5200"),
        "target_price": Decimal("0.6000"),
        "stop_loss_price": Decimal("0.4800"),
    }


@pytest.fixture
def sample_trade_data():
    """Sample trade data for testing."""
    return {
        "strategy_id": 1,
        "model_id": 1,
        "side": "buy",  # trades use 'buy'/'sell', not 'yes'/'no'
        "quantity": 100,
        "price": Decimal("0.5200"),
        "order_type": "market",
    }


# =============================================================================
# CONFIG FIXTURES
# =============================================================================


@pytest.fixture
def temp_config_dir():
    """
    Create temporary directory with test config files.

    Returns path to temp directory, cleans up after test.
    """
    temp_dir = tempfile.mkdtemp(prefix="precog_test_")
    temp_path = Path(temp_dir)

    # Create sample config file
    (temp_path / "test_config.yaml").write_text("""
# Test configuration
trading:
  max_position_size: 1000.00
  min_ev_threshold: 0.05
  kelly_fraction: 0.25

strategy:
  name: test_strategy
  version: 1
""")

    yield temp_path

    # Cleanup: remove temp directory
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def config_loader(temp_config_dir):
    """Provide ConfigLoader instance with test configs."""
    return ConfigLoader(config_dir=str(temp_config_dir))


# =============================================================================
# LOGGER FIXTURES
# =============================================================================


@pytest.fixture
def temp_log_dir():
    """Create temporary directory for test logs."""
    temp_dir = tempfile.mkdtemp(prefix="precog_logs_")
    temp_path = Path(temp_dir)

    yield temp_path

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_logger(temp_log_dir):
    """Provide logger that writes to temp directory."""
    import logging

    logger = setup_logging(log_level="DEBUG", log_to_file=True, log_dir=str(temp_log_dir))

    yield logger

    # Cleanup: Properly shutdown all logging handlers to prevent ResourceWarning
    logging.shutdown()


# =============================================================================
# UTILITY FIXTURES
# =============================================================================


@pytest.fixture
def decimal_prices():
    """
    Common price values for testing Decimal precision.

    Tests edge cases:
    - Minimum price (0.0001)
    - Maximum price (0.9999)
    - Typical prices (0.5000)
    - Sub-penny precision (0.4275)
    """
    return {
        "min": Decimal("0.0001"),
        "max": Decimal("0.9999"),
        "mid": Decimal("0.5000"),
        "sub_penny": Decimal("0.4275"),
        "tight_spread_bid": Decimal("0.7550"),
        "tight_spread_ask": Decimal("0.7551"),  # Only 0.01¢ spread
    }


@pytest.fixture
def assert_decimal_precision():
    """
    Helper function to verify Decimal precision is preserved.

    Usage:
        assert_decimal_precision(value, expected, places=4)
    """

    def _assert(value, expected, places=4):
        """
        Assert that value equals expected with exact decimal precision.

        Args:
            value: Actual value (should be Decimal)
            expected: Expected value (can be string or Decimal)
            places: Number of decimal places to check (default: 4)
        """
        # Convert to Decimal if needed
        if not isinstance(value, Decimal):
            pytest.fail(f"Expected Decimal, got {type(value)}: {value}")

        if isinstance(expected, str):
            expected = Decimal(expected)

        # Compare as strings to ensure exact representation
        assert str(value) == str(expected), f"Decimal precision mismatch: {value} != {expected}"

    return _assert


# =============================================================================
# MARKER HELPERS
# =============================================================================


# =============================================================================
# ATTRIBUTION TEST FIXTURES
# =============================================================================


@pytest.fixture
def sample_strategy_config_nested() -> dict[str, Any]:
    """
    Strategy configuration with nested entry/exit versioning (ADR-090).

    Educational Note:
        This represents the NEW nested versioning strategy where:
        - entry.version tracks entry rule version independently
        - exit.version tracks exit rule version independently
        - Enables A/B testing: "Did entry v1.5 outperform entry v1.6?"
    """
    return {
        "entry": {
            "version": "1.5",
            "rules": {
                "min_lead": 10,
                "max_spread": "0.08",
                "min_edge": "0.05",
                "min_probability": "0.55",
            },
        },
        "exit": {
            "version": "2.3",
            "rules": {
                "profit_target": "0.25",
                "stop_loss": "-0.10",
                "trailing_stop_activation": "0.15",
                "trailing_stop_distance": "0.05",
            },
        },
    }


@pytest.fixture
def sample_platform(db_pool, clean_test_data) -> str:
    """Create sample platform for testing."""
    from precog.database.connection import execute_query

    query = """
        INSERT INTO platforms (platform_id, platform_type, display_name, base_url)
        VALUES ('kalshi', 'trading', 'Kalshi', 'https://api.elections.kalshi.com/trade-api/v2')
        ON CONFLICT (platform_id) DO NOTHING
        RETURNING platform_id
    """
    execute_query(query)
    return "kalshi"


@pytest.fixture
def sample_series(db_pool, clean_test_data, sample_platform) -> str:
    """Create sample series for testing."""
    from precog.database.connection import execute_query

    query = """
        INSERT INTO series (series_id, platform_id, external_id, category, subcategory, title, frequency)
        VALUES ('NFL-2025', 'kalshi', 'NFL-2025-ext', 'sports', 'nfl', 'NFL 2025 Season', 'recurring')
        ON CONFLICT (series_id) DO NOTHING
        RETURNING series_id
    """
    execute_query(query)
    return "NFL-2025"


@pytest.fixture
def sample_event(db_pool, clean_test_data, sample_platform, sample_series) -> str:
    """Create sample event for testing."""
    from precog.database.connection import execute_query

    query = """
        INSERT INTO events (event_id, platform_id, series_id, external_id, category, subcategory, title, status)
        VALUES ('HIGHTEST', 'kalshi', 'NFL-2025', 'HIGHTEST-ext', 'sports', 'nfl', 'Super Bowl LIX', 'scheduled')
        ON CONFLICT (event_id) DO NOTHING
        RETURNING event_id
    """
    execute_query(query)
    return "HIGHTEST"


@pytest.fixture
def sample_market(db_pool, clean_test_data, sample_platform, sample_event) -> str:
    """Create sample market for testing."""
    from precog.database.connection import fetch_one

    # Check if market already exists
    existing = fetch_one(
        "SELECT market_id FROM markets WHERE market_id = %s AND row_current_ind = TRUE",
        ("MKT-HIGHTEST-25FEB05",),
    )
    if existing:
        return "MKT-HIGHTEST-25FEB05"

    # Create new market
    query = """
        INSERT INTO markets (
            market_id, platform_id, event_id, external_id, ticker, title,
            market_type, yes_price, no_price, status, metadata, row_current_ind, updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW()
        )
        RETURNING market_id
    """
    from precog.database.connection import get_cursor

    with get_cursor(commit=True) as cur:
        cur.execute(
            query,
            (
                "MKT-HIGHTEST-25FEB05",
                "kalshi",
                "HIGHTEST",
                "HIGHTEST-25FEB05-ext",
                "HIGHTEST-25FEB05",
                "Will HIGHTEST win Super Bowl?",
                "binary",
                0.5200,
                0.4800,
                "open",
                '{"market_category": "sports", "event_category": "nfl", "expected_expiry": "2025-02-05 18:00:00"}',
            ),
        )
        result = cur.fetchone()
        return result["market_id"] if result else "MKT-HIGHTEST-25FEB05"


@pytest.fixture
def sample_model(db_pool, clean_test_data) -> int:
    """
    Create sample probability models for testing.

    Educational Note:
        Creates two models (Model A and Model B) for attribution analytics tests.
        Models are immutable records with unique model_id values.
        Used to test ROI comparison between different models.

    Returns:
        model_id of first model (Model A)
    """
    from precog.database.connection import execute_query

    # Create Model A (model_id=1)
    query_a = """
        INSERT INTO probability_models (
            model_id, model_name, model_version, model_class, domain,
            config, status, description
        )
        VALUES (
            1, 'Test Model A', 'v1.0', 'elo', 'nfl',
            '{"k_factor": 32, "initial_rating": 1500}', 'active',
            'Elo-based model for testing'
        )
        ON CONFLICT (model_id) DO NOTHING
    """
    execute_query(query_a)

    # Create Model B (model_id=2)
    query_b = """
        INSERT INTO probability_models (
            model_id, model_name, model_version, model_class, domain,
            config, status, description
        )
        VALUES (
            2, 'Test Model B', 'v1.0', 'ensemble', 'nfl',
            '{"models": ["elo", "power_rankings"], "weights": [0.6, 0.4]}', 'active',
            'Ensemble model for testing'
        )
        ON CONFLICT (model_id) DO NOTHING
    """
    execute_query(query_b)

    return 1


@pytest.fixture
def sample_strategy(db_pool, clean_test_data, sample_strategy_config_nested) -> int:
    """Create sample strategy with nested versioning for testing."""
    return create_strategy(  # type: ignore[return-value]
        strategy_name="NFL Model Ensemble",
        strategy_version="v1.0",
        strategy_type="value",
        config=sample_strategy_config_nested,
        status="active",
        subcategory="nfl",
        notes="Ensemble of Elo + ESPN Power Rankings",
    )


def pytest_configure(config):
    """
    Register custom markers and enforce test environment.

    Environment Safety:
        This hook runs BEFORE any tests execute. We enforce PRECOG_ENV=test
        here to fail fast if someone accidentally runs tests against dev/prod.

    Markers:
        - unit: Isolated unit tests (no external dependencies)
        - integration: Tests requiring database or external services
        - slow: Tests that take >1s (can skip with -m "not slow")
        - critical: Must-pass tests for CI/CD gates
    """
    # ==========================================================================
    # ENVIRONMENT SAFETY GUARD (Issue #161)
    # ==========================================================================
    # Ensure we're in test environment BEFORE any database access
    # This prevents accidental test runs against dev/staging/prod databases
    #
    # If this fails, set PRECOG_ENV=test or ensure DB_NAME contains 'test'
    # See: docs/guides/DATABASE_ENVIRONMENT_STRATEGY_V1.0.md
    # ==========================================================================

    # Set PRECOG_ENV if not already set (for local dev convenience)
    if not os.getenv("PRECOG_ENV"):
        os.environ["PRECOG_ENV"] = "test"

    # Verify we're in test environment
    current_env = get_environment()
    if current_env != "test":
        raise RuntimeError(
            f"\n"
            f"{'=' * 70}\n"
            f"ENVIRONMENT SAFETY ERROR\n"
            f"{'=' * 70}\n"
            f"Tests attempted to run in '{current_env}' environment!\n"
            f"\n"
            f"Tests MUST run in 'test' environment to prevent data corruption.\n"
            f"\n"
            f"To fix, either:\n"
            f"  1. Set PRECOG_ENV=test before running tests\n"
            f"  2. Ensure DB_NAME contains 'test' (e.g., precog_test)\n"
            f"\n"
            f"Example:\n"
            f"  PRECOG_ENV=test python -m pytest tests/\n"
            f"{'=' * 70}\n"
        )

    # Register custom markers
    config.addinivalue_line("markers", "unit: Unit tests (isolated, fast)")
    config.addinivalue_line(
        "markers", "integration: Integration tests (database, external dependencies)"
    )
    config.addinivalue_line("markers", "slow: Slow tests (can skip during development)")
    config.addinivalue_line("markers", "critical: Critical path tests (must always pass)")
