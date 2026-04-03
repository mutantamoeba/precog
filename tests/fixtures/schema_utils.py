"""
Shared Schema Utilities for Testcontainers Fixtures.

Provides the Alembic-based schema application function used by both
property test containers (testcontainers_fixtures.py) and stress test
containers (stress_testcontainers.py).

Why Alembic Instead of Static SQL?
    A static SQL blob drifts from the real schema every time a migration
    lands.  Running `alembic upgrade head` guarantees containers match
    production exactly -- eliminating "works in test, fails in prod"
    failures caused by missing columns/tables/constraints.

References:
    - ADR-057: Testcontainers for Database Test Isolation
    - Issue #168: Implement testcontainers for database stress tests
"""

import os
import subprocess
import sys
from pathlib import Path


def apply_full_schema(
    host: str,
    port: int | str,
    database: str,
    user: str,
    password: str,
) -> None:
    """
    Apply the full Precog schema using Alembic migrations.

    Runs ``alembic upgrade head`` in a subprocess with environment variables
    configured so that Alembic's env.py connects to the target container
    database rather than the developer's local instance.

    Args:
        host: Database host (e.g. container IP).
        port: Database port (will be stringified).
        database: Database name inside the container.
        user: Database user.
        password: Database password.

    Raises:
        RuntimeError: If ``alembic upgrade head`` exits non-zero.

    Environment Handling:
        Both flat ``DB_*`` vars **and** prefixed vars (e.g. ``TEST_DB_HOST``
        when ``PRECOG_ENV=test``) are set in the subprocess environment.
        This is required because ``alembic/env.py`` calls
        ``get_prefixed_env()`` which checks the prefixed variant first.
        Without setting both, the prefixed vars from ``.env`` (pointing at
        the local database) would override the flat vars, causing Alembic
        to migrate the wrong database.
    """
    # Alembic config lives in src/precog/database/ (alembic.ini + alembic/ dir)
    alembic_dir = Path(__file__).parent.parent.parent / "src" / "precog" / "database"
    alembic_dir = alembic_dir.resolve()

    # Build subprocess environment with container connection details
    env = os.environ.copy()
    env["DB_HOST"] = str(host)
    env["DB_PORT"] = str(port)
    env["DB_NAME"] = database
    env["DB_USER"] = user
    env["DB_PASSWORD"] = password

    # Determine prefix from PRECOG_ENV (e.g., TEST -> TEST_DB_HOST)
    precog_env = env.get("PRECOG_ENV", "").lower()
    prefix_map = {
        "dev": "DEV",
        "development": "DEV",
        "test": "TEST",
        "staging": "STAGING",
        "prod": "PROD",
        "production": "PROD",
    }
    prefix = prefix_map.get(precog_env)
    if prefix:
        env[f"{prefix}_DB_HOST"] = str(host)
        env[f"{prefix}_DB_PORT"] = str(port)
        env[f"{prefix}_DB_NAME"] = database
        env[f"{prefix}_DB_USER"] = user
        env[f"{prefix}_DB_PASSWORD"] = password

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(alembic_dir),
        env=env,
        capture_output=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Alembic migration failed:\nstdout: {result.stdout.decode()}\n"
            f"stderr: {result.stderr.decode()}"
        )


# Re-export for easy importing
__all__ = [
    "apply_full_schema",
]
