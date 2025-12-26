"""Unit tests for kalshi_historical_cache module.

This module tests the Kalshi historical data caching infrastructure
for markets, series, and positions.

Reference: Phase 2C - Kalshi caching for TimescaleDB migration
"""

from datetime import date
from decimal import Decimal

from precog.database.seeding.kalshi_historical_cache import (
    DecimalEncoder,
    decimal_decoder,
    get_cache_path,
    is_cached,
)


class TestDecimalEncoder:
    """Tests for DecimalEncoder JSON encoder."""

    def test_encodes_decimal_to_string(self) -> None:
        """Verify Decimal values are encoded as strings."""
        import json

        result = json.dumps({"price": Decimal("0.75")}, cls=DecimalEncoder)
        assert '"price": "0.75"' in result

    def test_handles_nested_decimals(self) -> None:
        """Verify nested Decimal values are encoded."""
        import json

        data = {"market": {"yes_price": Decimal("0.55")}}
        result = json.dumps(data, cls=DecimalEncoder)
        assert "0.55" in result


class TestDecimalDecoder:
    """Tests for decimal_decoder function."""

    def test_decodes_price_strings(self) -> None:
        """Verify price strings are converted to Decimal."""
        # Uses yes_bid which is in the price_fields set
        data = {"yes_bid": "0.75", "name": "test"}
        result = decimal_decoder(data)
        assert isinstance(result.get("yes_bid"), Decimal)
        assert result["yes_bid"] == Decimal("0.75")

    def test_preserves_non_price_strings(self) -> None:
        """Verify non-price strings are preserved."""
        data = {"name": "test", "ticker": "ABC-123"}
        result = decimal_decoder(data)
        assert result["name"] == "test"
        assert result["ticker"] == "ABC-123"


class TestCachePath:
    """Tests for cache path utilities."""

    def test_get_cache_path_returns_path(self) -> None:
        """Verify get_cache_path returns a Path."""
        from pathlib import Path

        result = get_cache_path("markets", date(2024, 12, 25))
        assert isinstance(result, Path)
        assert "markets" in str(result)
        assert "2024-12-25" in str(result)

    def test_is_cached_returns_bool(self) -> None:
        """Verify is_cached returns boolean."""
        result = is_cached("markets", date(2020, 1, 1))
        assert isinstance(result, bool)
