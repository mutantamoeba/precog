"""Chaos test configuration — selective CI skip for poller tests only.

Most chaos tests (25 of 27 files) are CI-safe: they use mocked dependencies
and complete quickly. Only 2 files start real APScheduler BackgroundSchedulers
with chaos patterns (rapid start/stop, fault injection), which hang in CI.

This conftest selectively skips those 2 files in CI while allowing the other
25 files to run, giving us actual chaos test coverage in CI.

Run all locally: PRECOG_ENV=test python -m pytest tests/chaos/ -v
"""

import os

import pytest

_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"

# Files that start real APScheduler BackgroundSchedulers and cannot run in CI.
# These use rapid start/stop cycles and real scheduler timing dependencies.
_CI_UNSAFE_FILES = {
    "test_base_poller_chaos.py",
    "test_espn_game_poller_chaos.py",
}

_CI_SKIP_REASON = (
    "Skipped in CI: starts real APScheduler BackgroundScheduler with chaos patterns. "
    "Run locally: pytest tests/chaos/schedulers/ -v"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip only CI-unsafe chaos tests (real scheduler tests) in CI."""
    if not _is_ci:
        return

    skip_marker = pytest.mark.skip(reason=_CI_SKIP_REASON)
    for item in items:
        if item.fspath.basename in _CI_UNSAFE_FILES:
            item.add_marker(skip_marker)
