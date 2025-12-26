"""Unit tests for cache_config module.

This module tests the cache configuration utility that provides
unified paths for all historical data caches (TimescaleDB migration ready).

Reference: Phase 2C - Historical data caching infrastructure
"""

from pathlib import Path

from precog.database.seeding.cache_config import (
    CACHE_BASE_DIR,
    ensure_cache_structure,
    get_espn_cache_dir,
    get_kalshi_cache_dir,
)


class TestCacheConstants:
    """Tests for cache directory constants."""

    def test_base_dir_is_path(self) -> None:
        """Verify base directory is a Path object."""
        assert isinstance(CACHE_BASE_DIR, Path)

    def test_base_dir_contains_historical(self) -> None:
        """Verify base directory includes historical."""
        assert "historical" in str(CACHE_BASE_DIR)


class TestCacheDirectoryFunctions:
    """Tests for cache directory helper functions."""

    def test_kalshi_cache_dir_returns_path(self) -> None:
        """Verify get_kalshi_cache_dir returns a path."""
        result = get_kalshi_cache_dir("markets")
        assert isinstance(result, Path)
        assert "kalshi" in str(result).lower()
        assert "markets" in str(result).lower()

    def test_espn_cache_dir_returns_path(self) -> None:
        """Verify get_espn_cache_dir returns a path."""
        result = get_espn_cache_dir("nfl")
        assert isinstance(result, Path)
        assert "espn" in str(result).lower()
        assert "nfl" in str(result).lower()


class TestEnsureCacheStructure:
    """Tests for ensure_cache_structure function."""

    def test_ensure_cache_structure_callable(self) -> None:
        """Verify ensure_cache_structure is callable."""
        assert callable(ensure_cache_structure)
