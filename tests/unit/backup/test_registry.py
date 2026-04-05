"""Tests for storage backend registry and factory."""

from __future__ import annotations

import pytest

from precog.backup._base import StorageBackend
from precog.backup._registry import get_available_backends, get_storage_backend
from precog.backup._types import ConfigurationError
from precog.backup.storage_local import LocalStorageBackend


class TestRegistry:
    """Tests for backend registry operations."""

    def test_available_backends(self) -> None:
        """get_available_backends returns known backends."""
        backends = get_available_backends()
        assert "local" in backends
        assert "filen" in backends

    def test_get_local_backend(self, tmp_path) -> None:
        """Factory creates LocalStorageBackend for 'local' name."""
        backend = get_storage_backend("local", {"directory": str(tmp_path)})
        assert isinstance(backend, LocalStorageBackend)
        assert isinstance(backend, StorageBackend)

    def test_unknown_backend_raises(self) -> None:
        """Unknown backend name raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Unknown storage backend"):
            get_storage_backend("nonexistent", {})

    def test_error_message_lists_available(self) -> None:
        """Error message includes available backend names."""
        with pytest.raises(ConfigurationError, match="local"):
            get_storage_backend("nonexistent", {})
