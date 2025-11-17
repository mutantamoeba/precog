"""
Pytest configuration and shared fixtures.

Fixtures are reusable test setup/teardown functions.
They run before each test that uses them.
"""

import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from precog.config.config_loader import ConfigLoader

# Import modules to test
from precog.database.connection import close_pool, get_cursor, initialize_pool
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
    initialize_pool(minconn=2, maxconn=5)

    yield  # Tests run here

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
    db_cursor.execute("DELETE FROM trades WHERE market_id LIKE 'MKT-TEST-%'")
    db_cursor.execute("DELETE FROM positions WHERE market_id LIKE 'MKT-TEST-%'")
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
        INSERT INTO strategies (strategy_id, strategy_name, strategy_version, approach, config, status)
        VALUES (1, 'test_strategy', 'v1.0', 'value', '{"test": true}', 'active')
        ON CONFLICT (strategy_id) DO NOTHING
    """)

    # Create test probability model (required parent record for positions and trades)
    db_cursor.execute("""
        INSERT INTO probability_models (model_id, model_name, model_version, approach, config, status)
        VALUES (1, 'test_model', 'v1.0', 'elo', '{"test": true}', 'active')
        ON CONFLICT (model_id) DO NOTHING
    """)

    db_cursor.connection.commit()

    yield  # Test runs here

    # Cleanup after test (in reverse FK order)
    db_cursor.execute("DELETE FROM trades WHERE market_id LIKE 'MKT-TEST-%'")
    db_cursor.execute("DELETE FROM positions WHERE market_id LIKE 'MKT-TEST-%'")
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


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (isolated, fast)")
    config.addinivalue_line(
        "markers", "integration: Integration tests (database, external dependencies)"
    )
    config.addinivalue_line("markers", "slow: Slow tests (can skip during development)")
    config.addinivalue_line("markers", "critical: Critical path tests (must always pass)")
