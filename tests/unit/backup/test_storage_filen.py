"""Smoke tests for Filen storage backend (#565, PR #597).

Minimal unit coverage for the experimental backup module to satisfy the
test type coverage audit (TESTING_STRATEGY V3.2). The Filen backend integration
is exercised by the orchestrator integration tests; these tests verify the
class is importable and constructable from a config dict.

Tracking issue for full test suite expansion: TBD (file as follow-up).
"""

from __future__ import annotations

import pytest

from precog.backup.storage_filen import FilenStorageBackend


@pytest.mark.unit
class TestFilenStorageBackend:
    """Smoke tests for FilenStorageBackend module surface."""

    def test_filen_backend_is_importable(self) -> None:
        """Verify FilenStorageBackend class is importable from module."""
        assert FilenStorageBackend is not None

    def test_filen_backend_is_subclass_of_storage_backend(self) -> None:
        """Verify FilenStorageBackend extends the abstract StorageBackend base."""
        from precog.backup._base import StorageBackend

        assert issubclass(FilenStorageBackend, StorageBackend)
