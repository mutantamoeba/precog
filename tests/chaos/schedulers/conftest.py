"""Shared fixtures for scheduler chaos tests."""

import pytest


@pytest.fixture(autouse=True)
def _clean_scheduler_status():
    """Clean stale scheduler_status entries before each chaos test.

    The startup guard (Issue #363) detects active scheduler entries and blocks
    subsequent supervisor starts. Chaos tests that share a DB need cleanup
    between tests to prevent false positives.
    """
    from precog.database.crud_schedulers import cleanup_stale_schedulers

    try:
        cleanup_stale_schedulers(stale_threshold_seconds=0)
    except Exception:
        pass  # Table may not exist in test environments
    yield
    try:
        cleanup_stale_schedulers(stale_threshold_seconds=0)
    except Exception:
        pass
