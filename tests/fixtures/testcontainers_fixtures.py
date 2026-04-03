"""
Testcontainers PostgreSQL Fixtures for Property Tests.

Provides ephemeral PostgreSQL containers for database isolation in property tests.
This implements ADR-057: Testcontainers for Database Test Isolation.

Why Testcontainers?
    Property-based tests with Hypothesis generate 100+ test cases per test.
    Hypothesis caches examples in `.hypothesis/examples/` and replays them.
    When schema constraints change (e.g., season range 2020-2050), cached
    examples with old values (e.g., season=2099) cause test failures.

    Testcontainers provides TRUE isolation:
    - Fresh PostgreSQL container per test class
    - All Alembic migrations applied from scratch (always matches production)
    - No state leakage between tests
    - Reproducible CI/CD runs

Schema Application:
    Uses ``alembic upgrade head`` via the shared ``apply_full_schema()``
    utility (tests/fixtures/schema_utils.py).  This replaced a static
    ~800-line SQL blob that was frozen at migration 0044 and drifted from
    production every time a new migration landed.

Usage:
    @pytest.mark.usefixtures("postgres_container")
    class TestPropertyBasedCRUD:
        def test_some_property(self, db_connection):
            # Uses the containerized database
            ...

References:
    - ADR-057: Testcontainers for Database Test Isolation
    - TEST_ISOLATION_PATTERNS_V1.0.md
    - DATABASE_ENVIRONMENT_STRATEGY_V1.0.md
"""

import os
import sys
from collections.abc import Generator
from pathlib import Path

import psycopg2
import pytest

from tests.fixtures.schema_utils import apply_full_schema

# Add src to path for imports (needed by downstream code that imports from precog)
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


# Try to import testcontainers - gracefully handle if not available
try:
    from testcontainers.postgres import PostgresContainer

    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False
    PostgresContainer = None


@pytest.fixture(scope="session")
def postgres_container() -> Generator[dict[str, str], None, None]:
    """
    Create an ephemeral PostgreSQL container for ALL database tests.

    Scope: session - One container for entire test run (optimal for pre-push hooks).

    Yields:
        Dictionary with connection parameters:
        - host: Container hostname
        - port: Exposed PostgreSQL port
        - database: Database name
        - user: Database user
        - password: Database password
        - connection_url: Full connection URL

    Educational Note:
        Using session scope means:
        1. Container starts once when first database test runs
        2. ALL tests share the same container (fast startup)
        3. Container stops after all tests complete
        4. Tests should use transactions/cleanup for isolation

        This provides BEST PERFORMANCE for pre-push hooks (~10s startup once
        vs ~10s per test class with class scope).

    Why Session Scope for Pre-Push:
        Pre-push runs ALL 8 test types (1196 tests). With class scope,
        we'd spin up ~50+ containers (one per test class). Session scope
        spins up ONE container, making pre-push run in ~8-12 min vs ~30+ min.

    Isolation Strategy:
        - Each test should use clean_test_data fixture for data isolation
        - Tests should NOT rely on auto-increment IDs (use UUIDs)
        - Use unique identifiers per test to avoid collisions
    """
    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("testcontainers not installed - run: pip install testcontainers[postgres]")

    # Start PostgreSQL container
    # NOTE: testcontainers 4.x uses 'username' instead of deprecated 'user'
    container = PostgresContainer(
        image="postgres:15",
        username="test_user",
        password="test_password",
        dbname="precog_test",
    )

    with container:
        # Get connection parameters
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)

        connection_params = {
            "host": host,
            "port": str(port),
            "database": "precog_test",
            "user": "test_user",
            "password": "test_password",
            "connection_url": container.get_connection_url(),
        }

        # Apply full schema using Alembic migrations.
        # This runs `alembic upgrade head` in a subprocess, ensuring the
        # container schema always matches production exactly.
        apply_full_schema(
            host=host,
            port=port,
            database="precog_test",
            user="test_user",
            password="test_password",
        )

        # Set environment variables for precog.database.connection.
        # Must set BOTH flat vars (DB_HOST) AND prefixed vars (TEST_DB_HOST)
        # because get_prefixed_env() checks TEST_DB_HOST first when PRECOG_ENV=test.
        # Without the prefixed vars, .env values win and the pool connects to
        # the local PostgreSQL instead of the container.
        original_env = {
            "DB_HOST": os.environ.get("DB_HOST"),
            "DB_PORT": os.environ.get("DB_PORT"),
            "DB_NAME": os.environ.get("DB_NAME"),
            "DB_USER": os.environ.get("DB_USER"),
            "DB_PASSWORD": os.environ.get("DB_PASSWORD"),
            "TEST_DB_HOST": os.environ.get("TEST_DB_HOST"),
            "TEST_DB_PORT": os.environ.get("TEST_DB_PORT"),
            "TEST_DB_NAME": os.environ.get("TEST_DB_NAME"),
            "TEST_DB_USER": os.environ.get("TEST_DB_USER"),
            "TEST_DB_PASSWORD": os.environ.get("TEST_DB_PASSWORD"),
        }

        os.environ["DB_HOST"] = host
        os.environ["DB_PORT"] = str(port)
        os.environ["DB_NAME"] = "precog_test"
        os.environ["DB_USER"] = "test_user"
        os.environ["DB_PASSWORD"] = "test_password"
        # Override prefixed vars so get_prefixed_env() uses the container
        os.environ["TEST_DB_HOST"] = host
        os.environ["TEST_DB_PORT"] = str(port)
        os.environ["TEST_DB_NAME"] = "precog_test"
        os.environ["TEST_DB_USER"] = "test_user"
        os.environ["TEST_DB_PASSWORD"] = "test_password"

        yield connection_params

        # Restore original environment
        for key, value in original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]


@pytest.fixture
def container_db_connection(
    postgres_container: dict[str, str],
) -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Provide a database connection to the testcontainer.

    Args:
        postgres_container: The running PostgreSQL container fixture

    Yields:
        Active psycopg2 connection to the containerized database

    Usage:
        def test_something(self, container_db_connection):
            with container_db_connection.cursor() as cur:
                cur.execute("SELECT 1")
    """
    conn = psycopg2.connect(
        host=postgres_container["host"],
        port=postgres_container["port"],
        database=postgres_container["database"],
        user=postgres_container["user"],
        password=postgres_container["password"],
    )

    yield conn

    conn.close()


@pytest.fixture
def container_cursor(
    container_db_connection: psycopg2.extensions.connection,
) -> Generator[psycopg2.extensions.cursor, None, None]:
    """
    Provide a cursor with automatic rollback for test isolation.

    Args:
        container_db_connection: Active connection to containerized database

    Yields:
        Cursor for executing queries. Changes are rolled back after test.
    """
    cursor = container_db_connection.cursor()

    yield cursor

    # Rollback any uncommitted changes
    container_db_connection.rollback()
    cursor.close()
