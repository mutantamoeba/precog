"""
Stress Test Specific Testcontainers Fixtures.

Provides PostgreSQL containers for stress tests that need database isolation.

CI vs Local Strategy:
    - CI: Uses the existing PostgreSQL service container (already running with
          migrations applied). No container startup overhead (~0s).
    - Local: Uses testcontainers to create fresh containers when Docker available.
          Skips gracefully if Docker not running.

Why This Dual Strategy?
    CI environments already have a PostgreSQL service container running (see
    ci.yml integration-tests job). Creating additional testcontainers would:
    - Add 15s+ startup per test (container + migrations)
    - Compete for Docker resources with the service container
    - Potentially exhaust CI memory

    By reusing the CI service container:
    - Zero container startup overhead
    - Migrations already applied by CI workflow
    - Tests run in seconds, not minutes

Isolation Approach:
    - Session-scoped fixture shares one container/connection across tests
    - Per-test cleanup (pool reset) provides isolation without restart overhead
    - Tests that truly exhaust resources should handle their own cleanup

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

        On Windows, `docker info` may fail with exit code 1 due to named pipe
        access issues even when Docker Desktop is running. We use multiple
        fallback checks:
        1. Try `docker info` (works on most Unix systems)
        2. Try `docker version --format "{{.Server.Version}}"` (more reliable on Windows)
        3. Try `docker ps` (simple connectivity check)

        Reference: Issue #202 - Windows Docker Desktop compatibility
    """
    # Check if docker command exists
    if not shutil.which("docker"):
        return False

    # Check if Docker daemon is running with multiple fallback methods
    # Windows Docker Desktop sometimes fails `docker info` but works with other commands
    check_commands = [
        ["docker", "info"],
        ["docker", "version", "--format", "{{.Server.Version}}"],
        ["docker", "ps", "-q"],
    ]

    for cmd in check_commands:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue

    return False


# Detect Docker availability at module load time
DOCKER_AVAILABLE = _check_docker_available()

# Try to import testcontainers
try:
    from testcontainers.postgres import PostgresContainer

    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False
    PostgresContainer = None


# CI environment detection
_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"

# Database stress tests should skip in CI because:
# 1. CI uses a shared PostgreSQL service container (not isolated testcontainers)
# 2. Connection pool limits are shared across all test types
# 3. Stress tests need isolated containers with configurable max_connections
# Non-database stress tests (logger, config) can run in CI since they don't need isolation.
SKIP_DB_STRESS_IN_CI = _is_ci


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


@pytest.fixture(scope="session")
def _stress_postgres_container_session() -> Generator[dict[str, str], None, None]:
    """
    Internal session-scoped fixture for PostgreSQL container.

    CI vs Local Strategy:
        - CI: Uses existing PostgreSQL service container (env vars already set)
        - Local: Creates testcontainer when Docker available

    This is session-scoped so container startup (~10s) and migrations (~5s)
    happen only ONCE per test session, not per test.

    Yields:
        Dictionary with connection parameters
    """
    # In CI, use the existing PostgreSQL service container
    if _is_ci:
        # CI workflow already has PostgreSQL running with migrations applied
        # Environment variables are already set by the workflow
        connection_params = {
            "host": os.environ.get("DB_HOST", "localhost"),
            "port": os.environ.get("DB_PORT", "5432"),
            "database": os.environ.get("DB_NAME", "precog_test"),
            "user": os.environ.get("DB_USER", "precog_test"),
            "password": os.environ.get("DB_PASSWORD", "precog_test_password"),
        }

        # Initialize connection pool
        try:
            close_pool()
        except Exception:
            pass
        initialize_pool()

        yield connection_params

        # Cleanup
        try:
            close_pool()
        except Exception:
            pass
        return

    # Local: Use testcontainers
    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("testcontainers not installed - run: pip install testcontainers[postgres]")

    if not DOCKER_AVAILABLE:
        pytest.skip("Docker not available - start Docker Desktop to run stress tests")

    # Start PostgreSQL container with higher connection limits
    # NOTE: testcontainers 4.x uses 'username' instead of deprecated 'user'
    container = PostgresContainer(
        image="postgres:15",
        username="stress_user",
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

        # Apply full Precog schema using Alembic migrations (ONCE for whole session)
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

        # Initialize pool
        try:
            close_pool()
        except Exception:
            pass
        initialize_pool()

        yield connection_params

        # Cleanup
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


@pytest.fixture
def stress_postgres_container(
    _stress_postgres_container_session: dict[str, str],
) -> Generator[dict[str, str], None, None]:
    """
    Provide PostgreSQL container with per-test isolation.

    Scope: function - Wraps session container with per-test pool reset.

    CI vs Local Behavior:
        - CI (~0s): Uses existing service container, just resets pool
        - Local (~15s first test, ~0s subsequent): Session container reused

    Yields:
        Dictionary with connection parameters:
        - host: Database hostname
        - port: Database port
        - database: Database name
        - user: Database user
        - password: Database password

    Educational Note:
        This fixture provides test isolation WITHOUT container restart:
        1. Session fixture starts container once (CI: use existing)
        2. Each test gets a fresh connection pool
        3. Pool reset ensures no connection exhaustion carryover

        This trades complete isolation for speed:
        - Function-scoped container: ~15s x N tests = ~285s for 19 tests
        - Session-scoped + pool reset: ~15s + ~0.1s x N = ~17s for 19 tests

    Configuration:
        Inherits from session fixture:
        - max_connections=200 (local testcontainer)
        - CI uses whatever the service container has
    """
    # Get connection params from session fixture
    params = _stress_postgres_container_session

    # Reset connection pool for isolation
    try:
        close_pool()
    except Exception:
        pass
    initialize_pool()

    yield params

    # Cleanup: Close connections after test
    try:
        close_pool()
    except Exception:
        pass


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
    "SKIP_DB_STRESS_IN_CI",
    "TESTCONTAINERS_AVAILABLE",
    "CISafeBarrier",
    "_is_ci",
    "_stress_postgres_container_session",
    "stress_db_connection",
    "stress_postgres_container",
    "with_timeout",
]
