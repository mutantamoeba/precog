"""Stress test configuration — auto-skip in CI environments.

Stress tests use threading, concurrent executors, and rapid start/stop cycles
that can hang or timeout in resource-constrained CI environments (Issue #292).
This conftest auto-skips ALL stress tests when CI=true or GITHUB_ACTIONS=true,
so individual test files don't need their own skip guards.

Run locally: PRECOG_ENV=test python -m pytest tests/stress/ -v
"""

import os

import pytest

_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
_CI_SKIP_REASON = (
    "Stress tests skip in CI — they can hang in resource-constrained environments. "
    "Run locally: pytest tests/stress/ -v"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-skip all stress tests when running in CI."""
    if not _is_ci:
        return

    skip_marker = pytest.mark.skip(reason=_CI_SKIP_REASON)
    for item in items:
        item.add_marker(skip_marker)
