"""
Storage backend registry.

Maps backend names (from YAML config) to their implementation classes.
Factory function creates configured backend instances.

To add a new backend:
    1. Implement StorageBackend in storage_<name>.py
    2. Add entry to BACKEND_REGISTRY below
    3. Add config block under backup.storage.<name> in system.yaml
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from precog.backup._types import ConfigurationError

if TYPE_CHECKING:
    from precog.backup._base import StorageBackend

# Registry: backend name -> (module_path, class_name)
# Lazy imports to avoid loading unused backends and their dependencies.
_BACKEND_REGISTRY: dict[str, tuple[str, str]] = {
    "local": ("precog.backup.storage_local", "LocalStorageBackend"),
    "filen": ("precog.backup.storage_filen", "FilenStorageBackend"),
    # Future backends:
    # "s3": ("precog.backup.storage_s3", "S3StorageBackend"),
    # "google_drive": ("precog.backup.storage_gdrive", "GoogleDriveStorageBackend"),
    # "onedrive": ("precog.backup.storage_onedrive", "OneDriveStorageBackend"),
}


def get_available_backends() -> list[str]:
    """Return list of registered backend names."""
    return list(_BACKEND_REGISTRY.keys())


def get_storage_backend(backend_name: str, config: dict[str, Any]) -> StorageBackend:
    """Create a configured storage backend instance.

    Args:
        backend_name: Name from backup.storage_backend config key.
            Must match a key in BACKEND_REGISTRY.
        config: Backend-specific config dict from backup.storage.<name>.

    Returns:
        Configured StorageBackend instance.

    Raises:
        ConfigurationError: If backend_name is not registered or
            backend-specific config is invalid.

    Example:
        >>> backend = get_storage_backend("local", {"directory": "backups"})
        >>> backend.validate_config()
    """
    if backend_name not in _BACKEND_REGISTRY:
        available = ", ".join(sorted(_BACKEND_REGISTRY.keys()))
        raise ConfigurationError(
            f"Unknown storage backend: '{backend_name}'. Available backends: {available}"
        )

    module_path, class_name = _BACKEND_REGISTRY[backend_name]

    try:
        import importlib

        module = importlib.import_module(module_path)
        backend_class = getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        raise ConfigurationError(
            f"Failed to load storage backend '{backend_name}': {e}. "
            f"Check that required dependencies are installed."
        ) from e

    backend = backend_class(config)
    backend.validate_config()
    return cast("StorageBackend", backend)
