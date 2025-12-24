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

Testcontainers Support (ADR-057):
    For property tests that need true database isolation, use the
    testcontainers fixtures from tests.fixtures.testcontainers_fixtures.
    These provide ephemeral PostgreSQL containers per test class.

Test Key Generation:
    The test_private_key fixture generates an RSA private key for testing
    Kalshi API authentication. The key is generated on-the-fly and NOT
    committed to git (security best practice). This ensures CI and local
    environments both have valid test keys without exposing real credentials.
"""

import os
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from precog.config.config_loader import ConfigLoader

# Import testcontainers fixtures for property tests (ADR-057)
# These are re-exported here so pytest can discover them
try:
    from tests.fixtures.testcontainers_fixtures import (
        TESTCONTAINERS_AVAILABLE,
        container_cursor,
        container_db_connection,
        postgres_container,
    )
except ImportError:
    TESTCONTAINERS_AVAILABLE = False
    postgres_container = None  # type: ignore[assignment]
    container_db_connection = None  # type: ignore[assignment]
    container_cursor = None  # type: ignore[assignment]

# Import stress testcontainers fixtures (Issue #168)
# Function-scoped containers for stress tests that exhaust connection pools
# NOTE: Must import _stress_postgres_container_session for pytest to discover
# the session-scoped fixture that stress_postgres_container depends on
try:
    from tests.fixtures.stress_testcontainers import (
        DOCKER_AVAILABLE as STRESS_DOCKER_AVAILABLE,
    )
    from tests.fixtures.stress_testcontainers import (
        _stress_postgres_container_session,
        stress_db_connection,
        stress_postgres_container,
    )
except ImportError:
    STRESS_DOCKER_AVAILABLE = False
    _stress_postgres_container_session = None  # type: ignore[assignment]
    stress_postgres_container = None  # type: ignore[assignment]
    stress_db_connection = None  # type: ignore[assignment]

# Import transaction-based isolation fixtures (Issue #171 - Layer 1)
# These provide ~0ms overhead test isolation via transaction rollback
# Use db_transaction for most tests, db_transaction_with_setup for tests
# needing standard test data (platform, series, event, strategy, model)
try:
    from tests.fixtures.transaction_fixtures import (
        db_savepoint,
        db_transaction,
        db_transaction_with_setup,
    )
except ImportError:
    db_transaction = None  # type: ignore[assignment]
    db_transaction_with_setup = None  # type: ignore[assignment]
    db_savepoint = None  # type: ignore[assignment]

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


# Detect environment at module load time
DOCKER_AVAILABLE = _check_docker_available()
USE_TESTCONTAINERS = DOCKER_AVAILABLE and TESTCONTAINERS_AVAILABLE


@pytest.fixture(scope="session")
def db_pool(request):
    """
    Create database connection pool once per test session.

    Strategy (ADR-057 - Testcontainers for Database Test Isolation):
        1. If Docker + testcontainers available: Use ephemeral PostgreSQL container
           - Provides fresh schema, no state leakage, proper isolation
           - Best for local development and pre-push hooks
        2. Otherwise: Use environment variables (DB_HOST, DB_PORT, etc.)
           - Works with CI PostgreSQL service container
           - Falls back to local PostgreSQL if configured

    Scope: session - created once, shared across all tests

    Educational Note:
        Using testcontainers provides TRUE database isolation:
        - Fresh PostgreSQL container with clean schema
        - All migrations applied from scratch
        - No interference from previous test runs
        - Hypothesis caching issues eliminated

        Without testcontainers, tests share a database which can cause:
        - State leakage between tests
        - Schema drift (local DB may be outdated)
        - Flaky tests from leftover data
    """
    if USE_TESTCONTAINERS:
        # Request the testcontainers fixture first - it sets DB_* env vars
        # This ensures initialize_pool() uses the containerized database
        container_params = request.getfixturevalue("postgres_container")
        print(
            f"\n[TESTCONTAINERS] Using ephemeral PostgreSQL container at "
            f"{container_params['host']}:{container_params['port']}"
        )

    # Initialize pool (uses DB_* env vars set by testcontainers or from environment)
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
    # CRITICAL: If a prior transaction failed, we need to rollback first
    # This prevents 'InFailedSqlTransaction' errors cascading to cleanup
    try:
        db_cursor.connection.rollback()
    except Exception:
        pass  # Already rolled back or no active transaction

    # Cleanup before test (in reverse FK order)
    # Delete child records first - trades/positions reference strategies/models/markets
    db_cursor.execute("DELETE FROM trades WHERE market_id LIKE 'MKT-TEST-%'")
    # Delete settlements (child of markets) - clean ALL settlements for test isolation
    # Settlements table is append-only in production, but must be cleaned between tests
    db_cursor.execute("DELETE FROM settlements")
    # Delete positions by test market pattern
    db_cursor.execute(
        "DELETE FROM positions WHERE market_id LIKE 'MKT-TEST-%' OR market_id LIKE 'KALSHI-%'"
    )
    # Try to delete positions/trades referencing test strategies/models (may fail in CI)
    # In CI, strategy_id/model_id columns may not exist if migrations 001/003 failed
    # Delete fixture data (99901+) AND any SERIAL-generated data (1-99900)
    try:
        db_cursor.execute(
            "DELETE FROM trades WHERE strategy_id IS NOT NULL OR model_id IS NOT NULL"
        )
        db_cursor.execute(
            "DELETE FROM positions WHERE strategy_id IS NOT NULL OR model_id IS NOT NULL"
        )
    except Exception:
        db_cursor.connection.rollback()  # CRITICAL: Clear aborted transaction state
    # Then delete parent records
    db_cursor.execute("DELETE FROM markets WHERE market_id LIKE 'MKT-TEST-%'")
    db_cursor.execute("DELETE FROM events WHERE event_id LIKE 'TEST-%'")
    db_cursor.execute("DELETE FROM series WHERE series_id LIKE 'TEST-%'")
    # Clean up ALL test models and strategies (fixture data + SERIAL-generated)
    # This ensures clean state for property tests that create many strategies
    try:
        db_cursor.execute("DELETE FROM probability_models")
        db_cursor.execute("DELETE FROM strategies")
    except Exception:
        db_cursor.connection.rollback()  # CRITICAL: Clear aborted transaction state
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

    # Create test strategy and probability model (required parent records for positions/trades)
    # Use HIGH IDs (99901) to avoid SERIAL sequence collision with property tests
    # Property tests use create_strategy() which auto-generates IDs via SERIAL starting at 1
    # Using high IDs ensures no collision: SERIAL generates 1,2,3... while fixtures use 99901,99902...
    # This mirrors the teams pattern (99001, 99002) in test_crud_operations_properties.py
    try:
        db_cursor.execute("""
            INSERT INTO strategies (strategy_id, strategy_name, strategy_version, strategy_type, config, status)
            VALUES (99901, 'test_strategy', 'v1.0', 'value', '{"test": true}', 'active')
            ON CONFLICT (strategy_id) DO NOTHING
        """)
        db_cursor.execute("""
            INSERT INTO probability_models (model_id, model_name, model_version, model_class, config, status)
            VALUES (99901, 'test_model', 'v1.0', 'elo', '{"test": true}', 'active')
            ON CONFLICT (model_id) DO NOTHING
        """)
    except Exception:
        db_cursor.connection.rollback()  # CRITICAL: Clear aborted transaction state

    db_cursor.connection.commit()

    yield  # Test runs here

    # Cleanup after test (in reverse FK order)
    # Delete child records first - trades/positions reference strategies/models/markets
    db_cursor.execute("DELETE FROM trades WHERE market_id LIKE 'MKT-TEST-%'")
    db_cursor.execute(
        "DELETE FROM positions WHERE market_id LIKE 'MKT-TEST-%' OR market_id LIKE 'KALSHI-%'"
    )
    # Try to delete positions/trades referencing test strategies/models (may fail in CI)
    # Delete ALL positions/trades with strategy_id/model_id (fixture data + SERIAL-generated)
    try:
        db_cursor.execute(
            "DELETE FROM trades WHERE strategy_id IS NOT NULL OR model_id IS NOT NULL"
        )
        db_cursor.execute(
            "DELETE FROM positions WHERE strategy_id IS NOT NULL OR model_id IS NOT NULL"
        )
    except Exception:
        db_cursor.connection.rollback()  # CRITICAL: Clear aborted transaction state
    # Then delete parent records
    db_cursor.execute("DELETE FROM markets WHERE market_id LIKE 'MKT-TEST-%'")
    db_cursor.execute("DELETE FROM events WHERE event_id LIKE 'TEST-%'")
    db_cursor.execute("DELETE FROM series WHERE series_id LIKE 'TEST-%'")
    # Clean up ALL test models and strategies (fixture data + SERIAL-generated)
    # This ensures clean state for next test
    try:
        db_cursor.execute("DELETE FROM probability_models")
        db_cursor.execute("DELETE FROM strategies")
    except Exception:
        db_cursor.connection.rollback()  # CRITICAL: Clear aborted transaction state
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
    """Sample position data for testing.

    Uses high IDs (99901) to match fixture data and avoid SERIAL collision.
    """
    return {
        "strategy_id": 99901,
        "model_id": 99901,
        "side": "YES",
        "quantity": 100,
        "entry_price": Decimal("0.5200"),
        "target_price": Decimal("0.6000"),
        "stop_loss_price": Decimal("0.4800"),
    }


@pytest.fixture
def sample_trade_data():
    """Sample trade data for testing.

    Uses high IDs (99901) to match fixture data and avoid SERIAL collision.
    """
    return {
        "strategy_id": 99901,
        "model_id": 99901,
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
# TEST PRIVATE KEY FIXTURE (Kalshi API Authentication Testing)
# =============================================================================


def _generate_test_private_key() -> str:
    """
    Generate a test RSA private key for Kalshi API authentication testing.

    Educational Note:
        This generates a valid RSA private key programmatically instead of
        committing a key file to git. This is a security best practice:
        - Real private keys should NEVER be committed to version control
        - Test keys can be generated on-the-fly
        - CI environments get valid test keys without secrets management

        The key is used for testing RSA-PSS signature generation in
        KalshiAuth. Since the tests mock the actual API calls, the key
        doesn't need to be registered with Kalshi - it just needs to be
        a valid RSA key format.

    Returns:
        PEM-encoded RSA private key as a string
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    # Generate a 2048-bit RSA key (matches Kalshi's requirements)
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Serialize to PEM format
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return pem.decode("utf-8")


@pytest.fixture(scope="session", autouse=True)
def ensure_test_private_key():
    """
    Ensure test_private_key.pem exists for Kalshi API integration tests.

    This fixture runs automatically (autouse=True) at session start and:
    1. Checks if tests/fixtures/test_private_key.pem exists
    2. If not, generates a valid RSA private key
    3. Saves it to the expected location
    4. Sets TEST_KALSHI_* environment variables for CI compatibility

    The key is NOT committed to git (*.pem is in .gitignore).
    This ensures CI and local development both have valid test keys.

    Educational Note:
        KalshiClient uses PRECOG_ENV to determine credential prefix:
        - PRECOG_ENV=test -> looks for TEST_KALSHI_API_KEY, TEST_KALSHI_PRIVATE_KEY_PATH
        - PRECOG_ENV=dev -> looks for DEV_KALSHI_API_KEY, DEV_KALSHI_PRIVATE_KEY_PATH
        CI sets PRECOG_ENV=test, so we must set TEST_KALSHI_* env vars here.

    Scope: session - only generates key once per test run
    """
    test_key_path = Path(__file__).parent / "fixtures" / "test_private_key.pem"

    # Ensure fixtures directory exists
    test_key_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate key if it doesn't exist
    if not test_key_path.exists():
        print(f"\n[TEST SETUP] Generating test private key at {test_key_path}")
        key_pem = _generate_test_private_key()
        test_key_path.write_text(key_pem)
        print("[TEST SETUP] Test private key generated successfully")

    # Set environment variables for KalshiClient credential lookup in CI
    # When PRECOG_ENV=test (CI default), KalshiClient looks for TEST_KALSHI_* vars
    # Only set if not already configured (preserves real credentials for local e2e tests)
    if not os.getenv("TEST_KALSHI_API_KEY"):
        os.environ["TEST_KALSHI_API_KEY"] = "test-key-id-for-ci-vcr-tests"
    if not os.getenv("TEST_KALSHI_PRIVATE_KEY_PATH"):
        os.environ["TEST_KALSHI_PRIVATE_KEY_PATH"] = str(test_key_path)

    return test_key_path


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

        Uses HIGH IDs (99901, 99902) to avoid SERIAL sequence collision with
        property tests that use create_model() which auto-generates IDs via SERIAL.
        This mirrors the teams pattern (99001, 99002) in test_crud_operations_properties.py

    Returns:
        model_id of first model (Model A) - 99901
    """
    from precog.database.connection import execute_query

    # Create Model A (model_id=99901) - high ID to avoid SERIAL collision
    query_a = """
        INSERT INTO probability_models (
            model_id, model_name, model_version, model_class, domain,
            config, status, description
        )
        VALUES (
            99901, 'Test Model A', 'v1.0', 'elo', 'nfl',
            '{"k_factor": 32, "initial_rating": 1500}', 'active',
            'Elo-based model for testing'
        )
        ON CONFLICT (model_id) DO NOTHING
    """
    execute_query(query_a)

    # Create Model B (model_id=99902) - high ID to avoid SERIAL collision
    query_b = """
        INSERT INTO probability_models (
            model_id, model_name, model_version, model_class, domain,
            config, status, description
        )
        VALUES (
            99902, 'Test Model B', 'v1.0', 'ensemble', 'nfl',
            '{"models": ["elo", "power_rankings"], "weights": [0.6, 0.4]}', 'active',
            'Ensemble model for testing'
        )
        ON CONFLICT (model_id) DO NOTHING
    """
    execute_query(query_b)

    return 99901


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


# =============================================================================
# CLI TEST FIXTURES (Issue #258)
# =============================================================================


@pytest.fixture
def cli_runner():
    """
    Provide a CliRunner instance for Typer CLI testing.

    This fixture provides the Typer test runner used to invoke CLI commands
    in an isolated environment. Output is captured for assertion.

    Scope: function - new runner for each test

    Usage:
        def test_cli_command(cli_runner, cli_app):
            result = cli_runner.invoke(cli_app, ["system", "version"])
            assert result.exit_code == 0

    Educational Note:
        CliRunner provides test isolation for CLI applications:
        - Captures stdout/stderr for inspection
        - Isolates environment variables
        - Simulates terminal input/output
        - Returns Result object with exit_code, stdout, exception

    Related:
        - tests/helpers/cli_helpers.py: Shared CLI testing utilities
        - REQ-CLI-001: CLI Framework (Typer)
    """
    from typer.testing import CliRunner

    return CliRunner()


@pytest.fixture
def cli_app():
    """
    Provide the Precog CLI Typer application with all commands registered.

    This fixture returns the main Typer app after registering all subcommands.
    Use with cli_runner fixture to invoke CLI commands in tests.

    Scope: function - fresh app for each test

    Usage:
        def test_db_init(cli_runner, cli_app):
            result = cli_runner.invoke(cli_app, ["db", "init"])
            assert "Database" in result.stdout

    Educational Note:
        Precog CLI uses Typer's subcommand pattern:
        - main.py: Root app with register_commands()
        - cli/db.py: Database subcommands (init, status, migrate)
        - cli/system.py: System subcommands (version, health)
        - cli/markets.py: Market subcommands (list, fetch)
        - cli/api.py: API subcommands (status, balance)
        - cli/data.py: Data subcommands (seed, clear)
        - cli/pollers.py: Poller subcommands (start, stop, status)

        Each test gets a fresh app to ensure command registration isolation.

    Related:
        - main.py: CLI entry point
        - tests/helpers/cli_helpers.py: Shared CLI testing utilities
        - REQ-CLI-001: CLI Framework (Typer)
    """
    from main import app, register_commands

    # Register all CLI subcommands
    register_commands()
    return app


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
