"""Stress test configuration — selective CI skip for poller tests only.

Most stress tests (43 of 47 files) are CI-safe: they use mocked dependencies,
short sleeps, and complete quickly. Only 2 files start real APScheduler
BackgroundSchedulers with long sleeps, which hang in CI.

This conftest selectively skips those 2 files in CI while allowing the other
43 files to run, giving us actual stress test coverage in CI.

Run all locally: PRECOG_ENV=test python -m pytest tests/stress/ -v
"""

import os

import pytest

_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"

# Files that start real APScheduler BackgroundSchedulers and cannot run in CI.
# These have long sleeps (up to 10.5s) and real scheduler timing dependencies.
_CI_UNSAFE_FILES = {
    "test_base_poller_stress.py",
    "test_espn_game_poller_stress.py",
}

_CI_SKIP_REASON = (
    "Skipped in CI: starts real APScheduler BackgroundScheduler with long sleeps. "
    "Run locally: pytest tests/stress/schedulers/ -v"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip only CI-unsafe stress tests (real scheduler tests) in CI."""
    if not _is_ci:
        return

    skip_marker = pytest.mark.skip(reason=_CI_SKIP_REASON)
    for item in items:
        # item.fspath.basename gives the filename (e.g., "test_base_poller_stress.py")
        if item.fspath.basename in _CI_UNSAFE_FILES:
            item.add_marker(skip_marker)
