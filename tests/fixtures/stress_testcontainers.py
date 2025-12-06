"""
Stress Test Specific Testcontainers Fixtures.

Provides function-scoped PostgreSQL containers for stress tests that need
complete database isolation. Unlike the session-scoped fixtures in
testcontainers_fixtures.py, these create a fresh container per test.

Why Function Scope for Stress Tests?
    Stress tests intentionally exhaust database resources (connections, locks).
    Session-scoped containers would cause cascading failures as one test's
    exhausted connections affect subsequent tests.

    Function scope ensures:
    - Each test gets a fresh PostgreSQL instance
    - Connection pools start clean (no exhaustion from previous tests)
    - No state leakage between stress scenarios
    - Proper isolation for concurrent connection tests

Performance Trade-off:
    - Session scope: ~10s startup once, shared across all tests
    - Function scope: ~10s startup per test (slower but isolated)

    For stress tests, isolation trumps speed because these tests specifically
    test edge cases that break shared resources.

References:
    - Issue #168: Implement testcontainers for database stress tests
    - ADR-057: Testcontainers for Database Test Isolation
    - Pattern 28: CI-Safe Stress Testing (DEVELOPMENT_PATTERNS_V1.15.md)
"""

import os
import shutil
import subprocess
import threading
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from functools import wraps
from typing import Any, TypeVar

import psycopg2
import pytest

# Import connection pool management for reinitializing with testcontainer
from precog.database.connection import close_pool, initialize_pool

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


def _check_docker_available() -> bool:
    """
    Check if Docker is available for testcontainers.

    Returns:
        True if Docker daemon is running and accessible, False otherwise.

    Educational Note:
        This check runs before container creation to provide a clear skip
        message rather than a cryptic Docker connection error.
    """
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


# Detect Docker availability at module load time
DOCKER_AVAILABLE = _check_docker_available()

# Try to import testcontainers
try:
    from testcontainers.postgres import PostgresContainer

    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False
    PostgresContainer = None  # type: ignore[misc, assignment]


# CI environment detection
_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"


def _apply_minimal_schema(connection: psycopg2.extensions.connection) -> None:
    """
    Apply minimal schema for connection stress tests.

    Connection stress tests only need basic tables to test connection behavior.
    This is faster than applying full migrations.

    Args:
        connection: Active PostgreSQL connection with autocommit enabled
    """
    cursor = connection.cursor()

    # Minimal schema for connection stress tests
    schema_sql = """
    -- Basic table for stress test queries
    CREATE TABLE IF NOT EXISTS stress_test_table (
        id SERIAL PRIMARY KEY,
        value INTEGER,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Insert some test data
    INSERT INTO stress_test_table (value)
    SELECT generate_series(1, 100);
    """

    cursor.execute(schema_sql)
    connection.commit()
    cursor.close()


def _apply_full_schema(host: str, port: int, database: str, user: str, password: str) -> None:
    """
    Apply full Precog schema using Alembic migrations.

    CRUD stress tests need the full schema (venues, teams, game_states, etc.)
    to test actual database operations under load.

    Args:
        host: Database host
        port: Database port
        database: Database name
        user: Database user
        password: Database password

    Educational Note:
        We use Alembic programmatically here to ensure stress tests have
        the same schema as production. This prevents "works in test, fails
        in prod" scenarios caused by schema drift.
    """
    import subprocess
    import sys
    from pathlib import Path

    # Run Alembic migrations from the database directory
    alembic_dir = Path(__file__).parent.parent.parent / "src" / "precog" / "database"
    alembic_dir = alembic_dir.resolve()

    # Set environment for Alembic
    env = os.environ.copy()
    env["DB_HOST"] = host
    env["DB_PORT"] = str(port)
    env["DB_NAME"] = database
    env["DB_USER"] = user
    env["DB_PASSWORD"] = password

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(alembic_dir),
        env=env,
        capture_output=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Alembic migration failed: {result.stderr.decode()}")


@pytest.fixture
def stress_postgres_container() -> Generator[dict[str, str], None, None]:
    """
    Create a fresh PostgreSQL container for each stress test.

    Scope: function - New container per test for complete isolation.

    Yields:
        Dictionary with connection parameters:
        - host: Container hostname
        - port: Exposed PostgreSQL port
        - database: Database name
        - user: Database user
        - password: Database password

    Educational Note:
        Unlike session-scoped fixtures, this creates a new container per test.
        This is slower (~10s per test) but ensures:
        - Fresh connection pool for each test
        - No exhausted resources from previous tests
        - Complete isolation for concurrent connection scenarios

    Configuration:
        - max_connections=200: Higher than default (100) for stress testing
        - shared_buffers=128MB: Adequate for stress test workloads
    """
    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("testcontainers not installed - run: pip install testcontainers[postgres]")

    if not DOCKER_AVAILABLE:
        pytest.skip("Docker not available - start Docker Desktop to run stress tests")

    # Start PostgreSQL container with higher connection limits
    container = PostgresContainer(
        image="postgres:15",
        user="stress_user",
        password="stress_password",
        dbname="stress_test_db",
    ).with_command(
        # Higher connection limit for stress tests
        "postgres -c max_connections=200 -c shared_buffers=128MB"
    )

    with container:
        # Get connection parameters
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)

        connection_params = {
            "host": host,
            "port": str(port),
            "database": "stress_test_db",
            "user": "stress_user",
            "password": "stress_password",
        }

        # Apply full Precog schema using Alembic migrations
        # This ensures CRUD stress tests have all required tables (venues, teams, game_states)
        # Connection stress tests don't require specific schema (just SELECT 1, etc.)
        _apply_full_schema(
            host=host,
            port=port,
            database="stress_test_db",
            user="stress_user",
            password="stress_password",
        )

        # Set environment variables for precog.database.connection
        original_env = {
            "DB_HOST": os.environ.get("DB_HOST"),
            "DB_PORT": os.environ.get("DB_PORT"),
            "DB_NAME": os.environ.get("DB_NAME"),
            "DB_USER": os.environ.get("DB_USER"),
            "DB_PASSWORD": os.environ.get("DB_PASSWORD"),
        }

        os.environ["DB_HOST"] = host
        os.environ["DB_PORT"] = str(port)
        os.environ["DB_NAME"] = "stress_test_db"
        os.environ["DB_USER"] = "stress_user"
        os.environ["DB_PASSWORD"] = "stress_password"

        # Close existing connection pool and reinitialize with new env vars
        # This ensures get_cursor() uses the testcontainer database
        try:
            close_pool()
        except Exception:
            pass  # Pool may not exist yet

        # Initialize new pool pointing to testcontainer
        initialize_pool()

        yield connection_params

        # Close testcontainer pool before restoring environment
        try:
            close_pool()
        except Exception:
            pass

        # Restore original environment
        for key, value in original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

        # Reinitialize pool with original environment (if tests continue)
        try:
            initialize_pool()
        except Exception:
            pass  # May fail if original env vars not set


@pytest.fixture
def stress_db_connection(
    stress_postgres_container: dict[str, str],
) -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Provide a database connection to the stress test container.

    Args:
        stress_postgres_container: The running PostgreSQL container fixture

    Yields:
        Active psycopg2 connection to the containerized database
    """
    conn = psycopg2.connect(
        host=stress_postgres_container["host"],
        port=stress_postgres_container["port"],
        database=stress_postgres_container["database"],
        user=stress_postgres_container["user"],
        password=stress_postgres_container["password"],
    )

    yield conn

    conn.close()


class CISafeBarrier:
    """
    Thread barrier with timeout support for CI-safe synchronization.

    Standard threading.Barrier can hang indefinitely if threads fail or are slow.
    This wrapper adds timeout support and graceful degradation for CI environments.

    Why This Matters:
        CI runners have limited resources and unpredictable thread scheduling.
        A barrier.wait() without timeout can hang for hours (observed: 5hr+ hangs).
        This class ensures tests fail fast rather than hang.

    Usage:
        # Instead of:
        barrier = threading.Barrier(20)
        barrier.wait()  # Hangs forever if thread fails

        # Use:
        barrier = CISafeBarrier(20, timeout=10.0)
        barrier.wait()  # Raises TimeoutError after 10s

    Args:
        parties: Number of threads that must call wait()
        timeout: Maximum seconds to wait (default: 10.0)
        action: Optional callable to run when all parties arrive

    Reference:
        - Issue #168: Testcontainers for database stress tests
        - Pattern 28: CI-Safe Stress Testing (DEVELOPMENT_PATTERNS_V1.15.md)
    """

    def __init__(
        self,
        parties: int,
        timeout: float = 10.0,
        action: Callable[[], None] | None = None,
    ):
        self._barrier = threading.Barrier(parties, action=action)
        self._timeout = timeout
        self._parties = parties

    def wait(self, timeout: float | None = None) -> int:
        """
        Wait for all parties with timeout.

        Args:
            timeout: Override default timeout (optional)

        Returns:
            The arrival index (0 to parties-1)

        Raises:
            TimeoutError: If timeout exceeded (CI-friendly failure)
            threading.BrokenBarrierError: If barrier is broken
        """
        effective_timeout = timeout if timeout is not None else self._timeout
        try:
            return self._barrier.wait(timeout=effective_timeout)
        except threading.BrokenBarrierError:
            raise TimeoutError(
                f"CISafeBarrier timed out after {effective_timeout}s waiting for "
                f"{self._parties} parties. This may indicate CI resource constraints."
            ) from None

    def reset(self) -> None:
        """Reset the barrier to initial state."""
        self._barrier.reset()

    def abort(self) -> None:
        """Abort the barrier, causing all waiting threads to receive BrokenBarrierError."""
        self._barrier.abort()

    @property
    def parties(self) -> int:
        """Number of parties required to pass the barrier."""
        return self._parties

    @property
    def n_waiting(self) -> int:
        """Number of parties currently waiting."""
        return self._barrier.n_waiting

    @property
    def broken(self) -> bool:
        """True if barrier is in broken state."""
        return self._barrier.broken


def with_timeout(timeout_seconds: float = 30.0) -> Callable[[F], F]:
    """
    Decorator for stress tests that need thread-safe timeouts.

    pytest-timeout uses SIGALRM which doesn't work with Python threads.
    This decorator uses ThreadPoolExecutor for thread-safe timeouts.

    Args:
        timeout_seconds: Maximum execution time in seconds (default: 30)

    Returns:
        Decorated function that will raise TimeoutError if exceeded

    Educational Note:
        Python's signal-based timeouts (SIGALRM) can't interrupt threads
        because signals are only delivered to the main thread. For tests
        using ThreadPoolExecutor, we need this alternative approach.

    Usage:
        @with_timeout(60.0)
        def test_slow_concurrent_operation(self):
            # Test that might hang
            ...
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=timeout_seconds)
                except FuturesTimeoutError:
                    # Attempt to cancel - may not stop already-running code
                    future.cancel()
                    raise TimeoutError(
                        f"Test exceeded {timeout_seconds}s timeout. "
                        f"This may indicate a deadlock or resource exhaustion."
                    ) from None

        return wrapper  # type: ignore[return-value]

    return decorator


# Re-export for easy importing
__all__ = [
    "DOCKER_AVAILABLE",
    "TESTCONTAINERS_AVAILABLE",
    "CISafeBarrier",
    "stress_db_connection",
    "stress_postgres_container",
    "with_timeout",
]
