"""Chaos test configuration — auto-skip in CI environments.

Chaos tests inject failures, corrupt state, and stress error recovery paths
using threading and concurrent operations that can hang or timeout in
resource-constrained CI environments (Issue #292).
This conftest auto-skips ALL chaos tests when CI=true or GITHUB_ACTIONS=true,
so individual test files don't need their own skip guards.

Run locally: PRECOG_ENV=test python -m pytest tests/chaos/ -v
"""

import os

import pytest

_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
_CI_SKIP_REASON = (
    "Chaos tests skip in CI — they can hang in resource-constrained environments. "
    "Run locally: pytest tests/chaos/ -v"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-skip all chaos tests when running in CI."""
    if not _is_ci:
        return

    skip_marker = pytest.mark.skip(reason=_CI_SKIP_REASON)
    for item in items:
        item.add_marker(skip_marker)
