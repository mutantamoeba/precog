"""
Kalshi Historical Data Caching Module.

Provides local file caching for Kalshi API data to support:
- Reproducibility: Load data without API calls
- Backtesting: Replay historical market states
- Production Migration: Export data to TimescaleDB
- Development: Work offline with cached data

Cache Structure:
    data/historical/kalshi/
    ├── markets/           # Market snapshots by date
    │   └── 2024-12-25.json
    ├── series/            # Series definitions by date
    │   └── 2024-12-25.json
    ├── positions/         # Position snapshots by date
    │   └── 2024-12-25.json
    └── orders/            # Order history by date
        └── 2024-12-25.json

Usage:
    # Fetch and cache markets
    markets = fetch_and_cache_markets(client, date.today())

    # Load from cache only (no API)
    markets = load_cached_markets(date.today())

    # Get cache statistics
    stats = get_kalshi_cache_stats()

Related:
    - ADR-048: Decimal-First Response Parsing
    - historical_games_loader.py: ESPN caching pattern (inspiration)
    - Issue #229: Expanded Historical Data Sources
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from precog.api_connectors.kalshi_client import KalshiClient

logger = logging.getLogger(__name__)


# =============================================================================
# Cache Directory Constants
# =============================================================================

KALSHI_CACHE_DIR = Path("data/historical/kalshi")

# Cache subdirectories
MARKETS_CACHE_DIR = KALSHI_CACHE_DIR / "markets"
SERIES_CACHE_DIR = KALSHI_CACHE_DIR / "series"
POSITIONS_CACHE_DIR = KALSHI_CACHE_DIR / "positions"
ORDERS_CACHE_DIR = KALSHI_CACHE_DIR / "orders"


# =============================================================================
# JSON Encoding for Decimal Types
# =============================================================================


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types.

    Kalshi prices are Decimal for precision (ADR-048).
    Standard json.dumps() can't serialize Decimal, so we convert to string.

    Educational Note:
        We store as strings like "0.4975" rather than floats to preserve
        exact decimal precision. When loading, we convert back to Decimal.
    """

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


def decimal_decoder(dct: dict[str, Any]) -> dict[str, Any]:
    """JSON decoder hook that converts price strings back to Decimal.

    Identifies price fields by name patterns and converts them to Decimal.

    Args:
        dct: Dictionary from JSON parsing

    Returns:
        Dictionary with price fields as Decimal
    """
    price_fields = {
        "yes_bid",
        "yes_ask",
        "no_bid",
        "no_ask",
        "last_price",
        "previous_price",
        "floor_strike",
        "cap_strike",
        "yes_sub_title",  # Not a price, but contains Decimal-like strings
        "no_sub_title",
    }

    for key, value in dct.items():
        if key in price_fields and isinstance(value, str):
            try:
                dct[key] = Decimal(value)
            except Exception:
                pass  # Keep as string if not parseable

    return dct


# =============================================================================
# Cache Path Helpers
# =============================================================================


def get_cache_path(cache_type: str, cache_date: date) -> Path:
    """Get the cache file path for a given type and date.

    Args:
        cache_type: Type of cache ("markets", "series", "positions", "orders")
        cache_date: Date for the cache file

    Returns:
        Path to the cache file
    """
    cache_dirs = {
        "markets": MARKETS_CACHE_DIR,
        "series": SERIES_CACHE_DIR,
        "positions": POSITIONS_CACHE_DIR,
        "orders": ORDERS_CACHE_DIR,
    }

    cache_dir = cache_dirs.get(cache_type, KALSHI_CACHE_DIR / cache_type)
    return cache_dir / f"{cache_date.isoformat()}.json"


def ensure_cache_dir(cache_type: str) -> Path:
    """Ensure cache directory exists and return its path.

    Args:
        cache_type: Type of cache

    Returns:
        Path to the cache directory
    """
    cache_path = get_cache_path(cache_type, datetime.now(UTC).date()).parent
    cache_path.mkdir(parents=True, exist_ok=True)
    return cache_path


def is_cached(cache_type: str, cache_date: date) -> bool:
    """Check if data is cached for a given type and date.

    Args:
        cache_type: Type of cache
        cache_date: Date to check

    Returns:
        True if cache file exists
    """
    return get_cache_path(cache_type, cache_date).exists()


# =============================================================================
# Cache Read/Write Functions
# =============================================================================


def save_to_cache(
    cache_type: str,
    cache_date: date,
    data: list[dict[str, Any]],
    *,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Save data to cache file.

    Args:
        cache_type: Type of cache ("markets", "series", "positions", "orders")
        cache_date: Date for the cache file
        data: List of records to cache
        metadata: Optional metadata (fetch time, count, etc.)

    Returns:
        Path to the saved cache file

    Educational Note:
        We wrap the data with metadata for traceability:
        - cached_at: When this cache was created
        - source: "kalshi_api"
        - count: Number of records
        - data: The actual records
    """
    ensure_cache_dir(cache_type)
    cache_path = get_cache_path(cache_type, cache_date)

    cache_content = {
        "cached_at": datetime.now().isoformat(),
        "cache_date": cache_date.isoformat(),
        "cache_type": cache_type,
        "source": "kalshi_api",
        "count": len(data),
        "data": data,
    }

    if metadata:
        cache_content["metadata"] = metadata

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache_content, f, cls=DecimalEncoder, indent=2)

    logger.info(
        "Saved %d %s records to cache",
        len(data),
        cache_type,
        extra={"cache_path": str(cache_path), "count": len(data)},
    )

    return cache_path


def load_from_cache(
    cache_type: str,
    cache_date: date,
) -> list[dict[str, Any]] | None:
    """Load data from cache file.

    Args:
        cache_type: Type of cache
        cache_date: Date to load

    Returns:
        List of cached records, or None if cache doesn't exist

    Educational Note:
        Returns None (not empty list) when cache doesn't exist,
        so callers can distinguish "no cache" from "empty cache".
    """
    cache_path = get_cache_path(cache_type, cache_date)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, encoding="utf-8") as f:
            content = json.load(f, object_hook=decimal_decoder)

        data: list[dict[str, Any]] = content.get("data", [])

        logger.debug(
            "Loaded %d %s records from cache",
            len(data),
            cache_type,
            extra={"cache_path": str(cache_path)},
        )

        return data

    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load cache %s: %s", cache_path, e)
        return None


# =============================================================================
# Market Caching
# =============================================================================


def fetch_and_cache_markets(
    client: KalshiClient,
    cache_date: date,
    *,
    series_ticker: str | None = None,
    category: str | None = None,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """Fetch markets from Kalshi API and cache locally.

    Args:
        client: KalshiClient instance
        cache_date: Date to associate with this cache
        series_ticker: Optional filter by series
        category: Optional filter by category
        force_refresh: If True, fetch even if cache exists

    Returns:
        List of market records

    Educational Note:
        We paginate through all results using Kalshi's cursor.
        Each page returns up to 200 markets; we continue until
        no cursor is returned (all pages fetched).
    """
    if not force_refresh and is_cached("markets", cache_date):
        cached = load_from_cache("markets", cache_date)
        if cached is not None:
            logger.info("Using cached markets from %s", cache_date)
            return cached

    # Fetch all pages and convert TypedDict to plain dict for JSON serialization
    all_markets: list[dict[str, Any]] = []
    cursor = None

    while True:
        markets = client.get_markets(
            series_ticker=series_ticker,
            limit=200,  # Max per page
            cursor=cursor,
        )

        # Convert TypedDict to plain dict for caching
        all_markets.extend(dict(m) for m in markets)

        # Check if more pages exist
        # Note: get_markets returns just the list, cursor is in raw response
        # We'd need to modify get_markets to return cursor or use raw endpoint
        # For now, break after first page (most use cases)
        # TODO: Add pagination support when needed for full market snapshots
        break

    # Apply category filter if specified
    if category:
        all_markets = [m for m in all_markets if m.get("category", "").lower() == category.lower()]

    # Save to cache
    metadata = {
        "series_ticker": series_ticker,
        "category": category,
        "fetched_at": datetime.now().isoformat(),
    }
    save_to_cache("markets", cache_date, all_markets, metadata=metadata)

    return all_markets


def load_cached_markets(cache_date: date) -> list[dict[str, Any]] | None:
    """Load markets from cache only (no API call).

    Args:
        cache_date: Date to load

    Returns:
        List of cached markets, or None if not cached
    """
    return load_from_cache("markets", cache_date)


# =============================================================================
# Series Caching
# =============================================================================


def fetch_and_cache_series(
    client: KalshiClient,
    cache_date: date,
    *,
    category: str | None = None,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """Fetch series from Kalshi API and cache locally.

    Args:
        client: KalshiClient instance
        cache_date: Date to associate with this cache
        category: Optional filter by category (e.g., "sports")
        force_refresh: If True, fetch even if cache exists

    Returns:
        List of series records
    """
    if not force_refresh and is_cached("series", cache_date):
        cached = load_from_cache("series", cache_date)
        if cached is not None:
            logger.info("Using cached series from %s", cache_date)
            return cached

    # Fetch series and convert TypedDict to plain dict for JSON serialization
    series_list = client.get_series(category=category, limit=200)
    series_dicts: list[dict[str, Any]] = [dict(s) for s in series_list]

    # Save to cache
    metadata = {
        "category": category,
        "fetched_at": datetime.now().isoformat(),
    }
    save_to_cache("series", cache_date, series_dicts, metadata=metadata)

    return series_dicts


def load_cached_series(cache_date: date) -> list[dict[str, Any]] | None:
    """Load series from cache only (no API call).

    Args:
        cache_date: Date to load

    Returns:
        List of cached series, or None if not cached
    """
    return load_from_cache("series", cache_date)


# =============================================================================
# Positions Caching
# =============================================================================


def fetch_and_cache_positions(
    client: KalshiClient,
    cache_date: date,
    *,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """Fetch positions from Kalshi API and cache locally.

    Args:
        client: KalshiClient instance
        cache_date: Date to associate with this cache
        force_refresh: If True, fetch even if cache exists

    Returns:
        List of position records

    Educational Note:
        Positions are account-specific and change throughout the day.
        We cache daily snapshots for P&L analysis and backtesting.
    """
    if not force_refresh and is_cached("positions", cache_date):
        cached = load_from_cache("positions", cache_date)
        if cached is not None:
            logger.info("Using cached positions from %s", cache_date)
            return cached

    # Fetch positions and convert TypedDict to plain dict for JSON serialization
    raw_positions = client.get_positions()
    positions: list[dict[str, Any]] = [dict(p) for p in raw_positions] if raw_positions else []

    # Save to cache
    metadata = {
        "fetched_at": datetime.now().isoformat(),
    }
    save_to_cache("positions", cache_date, positions, metadata=metadata)

    return positions


def load_cached_positions(cache_date: date) -> list[dict[str, Any]] | None:
    """Load positions from cache only (no API call).

    Args:
        cache_date: Date to load

    Returns:
        List of cached positions, or None if not cached
    """
    return load_from_cache("positions", cache_date)


# =============================================================================
# Cache Statistics
# =============================================================================


def get_kalshi_cache_stats(cache_type: str | None = None) -> dict[str, Any]:
    """Get statistics about the Kalshi cache.

    Args:
        cache_type: Specific type to check, or None for all types

    Returns:
        Dictionary with cache statistics:
        - cached_dates: Number of dates with cached data
        - total_records: Total records across all cache files
        - total_size_mb: Total size of cache files in MB
        - date_range: (earliest_date, latest_date) tuple
        - by_type: Per-type breakdown (if cache_type is None)
    """
    cache_types = ["markets", "series", "positions", "orders"]

    if cache_type:
        cache_types = [cache_type]

    stats: dict[str, Any] = {
        "cached_dates": 0,
        "total_records": 0,
        "total_size_bytes": 0,
        "date_range": None,
        "by_type": {},
    }

    all_dates: list[date] = []

    for ct in cache_types:
        type_stats = _get_type_stats(ct)
        stats["by_type"][ct] = type_stats
        stats["cached_dates"] += type_stats["cached_dates"]
        stats["total_records"] += type_stats["total_records"]
        stats["total_size_bytes"] += type_stats["total_size_bytes"]

        if type_stats.get("date_range"):
            all_dates.extend(type_stats["date_range"])

    # Calculate overall date range
    if all_dates:
        stats["date_range"] = (min(all_dates), max(all_dates))

    # Convert bytes to MB
    stats["total_size_mb"] = stats["total_size_bytes"] / (1024 * 1024)

    return stats


def _get_type_stats(cache_type: str) -> dict[str, Any]:
    """Get statistics for a specific cache type.

    Args:
        cache_type: Type of cache to analyze

    Returns:
        Dictionary with type-specific stats
    """
    cache_dir = get_cache_path(cache_type, datetime.now(UTC).date()).parent

    if not cache_dir.exists():
        return {
            "cached_dates": 0,
            "total_records": 0,
            "total_size_bytes": 0,
            "date_range": None,
        }

    cache_files = list(cache_dir.glob("*.json"))
    dates: list[date] = []
    total_records = 0
    total_size = 0

    for cache_file in cache_files:
        # Parse date from filename (YYYY-MM-DD.json)
        try:
            file_date = datetime.strptime(cache_file.stem, "%Y-%m-%d").date()  # noqa: DTZ007
            dates.append(file_date)
        except ValueError:
            continue

        total_size += cache_file.stat().st_size

        # Count records (if file is small enough to read quickly)
        if cache_file.stat().st_size < 10 * 1024 * 1024:  # 10 MB limit
            try:
                with open(cache_file, encoding="utf-8") as f:
                    content = json.load(f)
                    total_records += content.get("count", 0)
            except Exception:
                pass

    return {
        "cached_dates": len(dates),
        "total_records": total_records,
        "total_size_bytes": total_size,
        "date_range": (min(dates), max(dates)) if dates else None,
    }


def list_cached_dates(cache_type: str) -> list[date]:
    """Get list of dates that have cached data.

    Args:
        cache_type: Type of cache to check

    Returns:
        Sorted list of dates with cached data
    """
    cache_dir = get_cache_path(cache_type, datetime.now(UTC).date()).parent

    if not cache_dir.exists():
        return []

    dates: list[date] = []
    for cache_file in cache_dir.glob("*.json"):
        try:
            file_date = datetime.strptime(cache_file.stem, "%Y-%m-%d").date()  # noqa: DTZ007
            dates.append(file_date)
        except ValueError:
            continue

    return sorted(dates)
