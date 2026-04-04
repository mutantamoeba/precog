"""CRUD operations for series and events.

Extracted from crud_operations.py during Phase 1b domain split.

Tables covered:
    - series: Top-level grouping in Kalshi hierarchy (Series -> Events -> Markets)
    - events: Real-world occurrences that markets are based on
"""

import json
import logging
from typing import Any, cast

from .connection import fetch_one, get_cursor

logger = logging.getLogger(__name__)


# =============================================================================
# SERIES OPERATIONS
# =============================================================================


def get_series(series_id: str) -> dict[str, Any] | None:
    """
    Get a series by series_id (business key).

    Series represent recurring market groups (e.g., "NFL Game Markets" contains
    all individual game betting markets). This is the first level in the
    Kalshi hierarchy: Series -> Events -> Markets.

    Args:
        series_id: The series business key (e.g., "KXNFLGAME"). This is the
            human-readable identifier from the Kalshi API, NOT the surrogate
            integer PK.

    Returns:
        Dict containing series data if found, None otherwise.
        Keys: id, series_id, platform_id, external_id, category, subcategory,
              title, frequency, tags, metadata, created_at, updated_at

    Example:
        >>> series = get_series("KXNFLGAME")
        >>> if series:
        ...     print(f"Found: {series['title']} (internal id: {series['id']})")
        ...     print(f"Tags: {series['tags']}")  # ['Football']
        ... else:
        ...     print("Series not found")

    Educational Note:
        The series table uses a surrogate integer PK (id) for internal identity
        and foreign key references. The series_id VARCHAR column is kept as a
        UNIQUE business key for human readability and API compatibility.

        The `tags` column (TEXT[]) is particularly useful for sport filtering:
        - ["Football"] -> NFL, NCAAF
        - ["Basketball"] -> NBA, NCAAB, NCAAW
        - ["Hockey"] -> NHL

        Using PostgreSQL arrays with GIN index enables efficient queries:
        SELECT * FROM series WHERE 'Football' = ANY(tags)

    Reference:
        - docs/database/DATABASE_SCHEMA_SUMMARY.md
        - src/precog/api_connectors/kalshi_client.py (get_series, get_sports_series)
        - Migration 0019: Added surrogate PK, demoted series_id to business key
    """
    query = """
        SELECT id, series_id, platform_id, external_id, category, subcategory,
               title, frequency, tags, metadata, created_at, updated_at
        FROM series
        WHERE series_id = %s
    """
    with get_cursor() as cur:
        cur.execute(query, (series_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_series(
    platform_id: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    List series with optional filtering and pagination.

    Retrieves series records with support for filtering by platform, category,
    and tags. Results are paginated for efficient querying of large datasets.

    Args:
        platform_id: Filter by platform (e.g., 'kalshi')
        category: Filter by category (e.g., 'sports', 'politics')
        tags: Filter by tags - series must contain ALL specified tags
        limit: Maximum number of results (default: 100, max: 1000)
        offset: Number of records to skip for pagination (default: 0)

    Returns:
        List of series dicts. Empty list if no matches.

    Example:
        >>> # Get all sports series
        >>> sports = list_series(category='sports', limit=50)
        >>> print(f"Found {len(sports)} sports series")

        >>> # Get all NFL-related series using tags
        >>> nfl = list_series(tags=['Football'])
        >>> for s in nfl:
        ...     print(f"{s['series_id']}: {s['title']}")

        >>> # Paginate through results
        >>> page1 = list_series(limit=100, offset=0)
        >>> page2 = list_series(limit=100, offset=100)

    Educational Note:
        Pagination is critical for API modules that may return large datasets.
        Using LIMIT/OFFSET allows clients to:
        1. Fetch data in manageable chunks (reduces memory usage)
        2. Implement infinite scroll or page-based navigation
        3. Avoid timeouts on large result sets

        The tags filter uses PostgreSQL's array containment operator (@>):
        WHERE tags @> ARRAY['Football'] means "tags contains 'Football'"

    Reference:
        - PostgreSQL array operators: https://www.postgresql.org/docs/current/functions-array.html
    """
    # Validate limit
    if limit > 1000:
        limit = 1000
    if limit < 1:
        limit = 1

    # Build query with optional filters
    conditions = []
    params: list[Any] = []

    if platform_id:
        conditions.append("platform_id = %s")
        params.append(platform_id)

    if category:
        conditions.append("category = %s")
        params.append(category)

    if tags:
        # Use array containment: tags must contain ALL specified tags
        conditions.append("tags @> %s")
        params.append(tags)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT id, series_id, platform_id, external_id, category, subcategory,
               title, frequency, tags, metadata, created_at, updated_at
        FROM series
        {where_clause}
        ORDER BY id
        LIMIT %s OFFSET %s
    """  # noqa: S608
    params.extend([limit, offset])

    with get_cursor() as cur:
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return [dict(row) for row in rows]


def create_series(
    series_id: str,
    platform_id: str,
    external_id: str,
    category: str,
    title: str,
    subcategory: str | None = None,
    frequency: str | None = None,
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> int:
    """
    Create a new series record.

    Series are the top-level grouping in Kalshi's market hierarchy:
    Series -> Events -> Markets. Each series represents a category of
    related markets (e.g., "NFL Game Markets" or "Presidential Election").

    Args:
        series_id: Unique business key (e.g., "KXNFLGAME"). Stored as
            VARCHAR(100) UNIQUE, but the surrogate integer PK (id) is
            used for all internal references and FK relationships.
        platform_id: Foreign key to platforms table (e.g., 'kalshi')
        external_id: External ID from the platform API
        category: Series category - one of: 'sports', 'politics',
                  'entertainment', 'economics', 'weather', 'other'
        title: Human-readable series title
        subcategory: Optional subcategory (e.g., 'nfl', 'nba')
        frequency: Optional frequency from Kalshi API (e.g., 'daily', 'weekly', 'event', 'custom')
        tags: Optional list of tags for filtering (e.g., ['Football'])
        metadata: Optional additional metadata as JSONB

    Returns:
        Integer surrogate PK (id) of the created series

    Raises:
        psycopg2.IntegrityError: If series_id already exists, platform_id
            invalid, or (platform_id, external_id) pair already exists

    Example:
        >>> series_pk = create_series(
        ...     series_id="KXNFLGAME",
        ...     platform_id="kalshi",
        ...     external_id="KXNFLGAME",
        ...     category="sports",
        ...     title="NFL Game Markets",
        ...     subcategory="nfl",
        ...     frequency="daily",
        ...     tags=["Football"]
        ... )
        >>> print(f"Created series with internal id: {series_pk}")

    Educational Note:
        The category CHECK constraint ensures data integrity at the database
        level. PostgreSQL will reject invalid categories before the data is
        even inserted, preventing corrupted records.

        Tags stored as TEXT[] (PostgreSQL array) enable efficient filtering
        with the ANY() operator and GIN indexes:
        SELECT * FROM series WHERE 'Football' = ANY(tags)

    Reference:
        - docs/database/DATABASE_SCHEMA_SUMMARY.md
        - Migration 0010: Added tags column with GIN index
        - Migration 0019: Added surrogate PK (id SERIAL)
    """
    query = """
        INSERT INTO series (
            series_id, platform_id, external_id, category, subcategory,
            title, frequency, tags, metadata, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        RETURNING id
    """

    params = (
        series_id,
        platform_id,
        external_id,
        category,
        subcategory,
        title,
        frequency,
        tags,  # PostgreSQL handles list -> TEXT[] conversion
        json.dumps(metadata) if metadata else None,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def update_series(
    series_id: str,
    title: str | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    frequency: str | None = None,
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> bool:
    """
    Update an existing series record.

    Updates only the fields that are provided (not None). This allows
    partial updates without affecting other fields.

    Args:
        series_id: The series to update
        title: New title (optional)
        category: New category (optional)
        subcategory: New subcategory (optional)
        frequency: New frequency (optional)
        tags: New tags list (optional) - replaces existing tags
        metadata: New metadata (optional) - replaces existing metadata

    Returns:
        True if series was updated, False if series not found

    Example:
        >>> # Update tags only
        >>> updated = update_series("KXNFLGAME", tags=["Football", "NFL"])
        >>> if updated:
        ...     print("Tags updated!")

        >>> # Update multiple fields
        >>> updated = update_series(
        ...     "KXNFLGAME",
        ...     title="NFL Regular Season Games",
        ...     frequency="daily"
        ... )

    Educational Note:
        This function builds a dynamic UPDATE query based on provided fields.
        This pattern is common for REST PATCH operations where clients only
        send the fields they want to change.

        Alternative approach: Always update all fields (simpler but overwrites
        unchanged fields with stale values if client doesn't fetch first).

    Reference: REQ-DATA-001 (Data Integrity)
    """
    # Build SET clause dynamically
    set_clauses = ["updated_at = NOW()"]
    params: list[Any] = []

    if title is not None:
        set_clauses.append("title = %s")
        params.append(title)

    if category is not None:
        set_clauses.append("category = %s")
        params.append(category)

    if subcategory is not None:
        set_clauses.append("subcategory = %s")
        params.append(subcategory)

    if frequency is not None:
        set_clauses.append("frequency = %s")
        params.append(frequency)

    if tags is not None:
        set_clauses.append("tags = %s")
        params.append(tags)

    if metadata is not None:
        set_clauses.append("metadata = %s")
        params.append(json.dumps(metadata))

    # Add series_id for WHERE clause
    params.append(series_id)

    # S608 false positive: set_clauses are hardcoded column names, not user input
    query = f"""
        UPDATE series
        SET {", ".join(set_clauses)}
        WHERE series_id = %s
    """  # noqa: S608

    with get_cursor(commit=True) as cur:
        cur.execute(query, tuple(params))
        return cast("bool", cur.rowcount > 0)


def get_or_create_series(
    series_id: str,
    platform_id: str,
    external_id: str,
    category: str,
    title: str,
    subcategory: str | None = None,
    frequency: str | None = None,
    tags: list[str] | None = None,
    metadata: dict | None = None,
    update_if_exists: bool = True,
) -> tuple[int, bool]:
    """
    Get an existing series or create it if it doesn't exist.

    This upsert pattern is essential for polling services that repeatedly
    fetch data from external APIs. When the same series appears in multiple
    API responses, this function ensures we don't fail on duplicate inserts.

    Args:
        series_id: Business key (e.g., "KXNFLGAME") used for lookup
        platform_id: Platform foreign key
        external_id: External API identifier
        category: Series category
        title: Series title
        subcategory: Optional subcategory
        frequency: Optional frequency
        tags: Optional tags list
        metadata: Optional metadata
        update_if_exists: If True, update existing series with new data (default: True)

    Returns:
        Tuple of (id, created) where id is the integer surrogate PK and
        created is True if series was newly created, False if it already existed.

    Example:
        >>> series_pk, created = get_or_create_series(
        ...     series_id="KXNFLGAME",
        ...     platform_id="kalshi",
        ...     external_id="KXNFLGAME",
        ...     category="sports",
        ...     title="NFL Game Markets",
        ...     tags=["Football"]
        ... )
        >>> if created:
        ...     print(f"Created new series (id={series_pk})")
        ... else:
        ...     print(f"Series already exists (id={series_pk})")

    Educational Note:
        This pattern is critical for the KalshiPoller service. When syncing
        series data before markets, the poller calls get_or_create_series()
        for each series returned by the API. This ensures:
        1. New series are created automatically
        2. Existing series are optionally updated with fresh data
        3. No duplicate insert errors occur

        The returned integer PK is used by downstream callers (e.g., the
        poller) to set events.series_internal_id when creating events.

        The update_if_exists flag allows the caller to control whether
        existing records should be refreshed with API data. Set to False
        if you only want to create missing records without modifying existing.

    Reference:
        - src/precog/schedulers/kalshi_poller.py
        - Pattern similar to get_or_create_event()
        - Migration 0019: series now uses surrogate integer PK
    """
    # Check if series already exists
    existing = get_series(series_id)

    if existing is not None:
        # Optionally update with new data
        if update_if_exists:
            update_series(
                series_id=series_id,
                title=title,
                category=category,
                subcategory=subcategory,
                frequency=frequency,
                tags=tags,
                metadata=metadata,
            )
        return cast("int", existing["id"]), False

    # Create new series - returns integer surrogate PK
    new_id = create_series(
        series_id=series_id,
        platform_id=platform_id,
        external_id=external_id,
        category=category,
        title=title,
        subcategory=subcategory,
        frequency=frequency,
        tags=tags,
        metadata=metadata,
    )
    return new_id, True


# =============================================================================
# EVENT OPERATIONS
# =============================================================================


def get_event(event_id: str) -> dict[str, Any] | None:
    """
    Get an event by its external_id (platform-scoped business key).

    Args:
        event_id: The event business key (from Kalshi API).
            Note: Parameter name is a legacy holdover; the DB column
            queried is ``external_id``.  This is NOT the integer
            surrogate PK.  The surrogate PK is available in the
            returned dict as result["id"].

    Returns:
        Dictionary with event data (including 'id' surrogate PK), or None if not found

    Example:
        >>> event = get_event("KXNFL-24DEC22-KC-SEA")
        >>> if event:
        ...     print(event['id'])     # Integer surrogate PK
        ...     print(event['title'])  # Event title

    Reference:
        - Migration 0020: id is SERIAL PK, external_id is the business key
        - Migration 0047: Dropped redundant event_id column; external_id is canonical
    """
    query = """
        SELECT *
        FROM events
        WHERE external_id = %s
    """
    return fetch_one(query, (event_id,))


def create_event(
    event_id: str,
    platform_id: str,
    external_id: str,
    category: str,
    title: str,
    series_internal_id: int | None = None,
    subcategory: str | None = None,
    description: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    status: str | None = None,
    metadata: dict | None = None,
    game_id: int | None = None,
) -> int:
    """
    Create a new event record.

    Events are the parent entities for markets. Each market belongs to an event,
    enforced via foreign key constraint (markets.event_internal_id -> events.id).

    Args:
        event_id: Legacy parameter name kept for caller compatibility.
            The value is stored in the ``external_id`` column.
            Callers typically pass the same value for both ``event_id``
            and ``external_id``; only ``external_id`` is written to the DB.
        platform_id: Foreign key to platforms table (e.g., 'kalshi')
        external_id: External ID from the platform API (stored as the
            business key in ``events.external_id``)
        category: Event category ('sports', 'politics', 'entertainment',
                  'economics', 'weather', 'other')
        title: Event title/description
        series_internal_id: Optional integer FK to series(id). This is the
            surrogate PK from the series table (migration 0019), NOT the
            VARCHAR business key.
        subcategory: Optional subcategory (e.g., 'nfl', 'nba')
        description: Optional detailed description
        start_time: Optional event start time (ISO format)
        end_time: Optional event end time (ISO format)
        status: Optional status ('scheduled', 'live', 'final', 'cancelled', 'postponed')
        metadata: Optional additional metadata as JSONB
        game_id: Optional integer FK to games(id). Links this Kalshi event
            to the corresponding ESPN game. NULL for non-sports events or
            when the matching game hasn't been identified yet.

    Returns:
        Integer surrogate PK (id) of the created event. Callers use this
        to set markets.event_internal_id FK.

    Raises:
        psycopg2.IntegrityError: If external_id+platform_id already exists
            or platform_id invalid

    Example:
        >>> event_pk = create_event(
        ...     event_id="KXNFL-24DEC22-KC-SEA",
        ...     platform_id="kalshi",
        ...     external_id="KXNFL-24DEC22-KC-SEA",
        ...     category="sports",
        ...     title="Chiefs vs Seahawks - Dec 22, 2024",
        ...     series_internal_id=42,
        ...     subcategory="nfl",
        ...     game_id=15,
        ... )
        >>> # event_pk is an integer, e.g. 7

    Educational Note:
        Events represent real-world occurrences (games, elections, etc.) that
        markets are based on. One event can have multiple markets:
        - Event: "Chiefs vs Seahawks - Dec 22"
        - Markets: "Chiefs to win", "Total points over 45.5", "Kelce 100+ yards"

        The foreign key constraint ensures data integrity - you can't create
        a market for a non-existent event.

    Reference:
        - docs/database/DATABASE_SCHEMA_SUMMARY.md
        - Migration 0019: events.series_internal_id replaces events.series_id
        - Migration 0020: events.id SERIAL PK, markets.event_internal_id INTEGER FK
        - Migration 0038: events.game_id FK to games(id)
        - Migration 0047: Dropped redundant event_id column
    """
    query = """
        INSERT INTO events (
            platform_id, series_internal_id, external_id,
            category, subcategory, title, description,
            start_time, end_time, status, metadata,
            game_id,
            created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        RETURNING id
    """

    params = (
        platform_id,
        series_internal_id,
        external_id,
        category,
        subcategory,
        title,
        description,
        start_time,
        end_time,
        status,
        json.dumps(metadata) if metadata else None,
        game_id,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def _fill_event_null_fields(
    existing: dict[str, Any],
    start_time: str | None = None,
    end_time: str | None = None,
    status: str | None = None,
    game_id: int | None = None,
) -> None:
    """Fill NULL enrichment fields on an existing event row.

    This is a "fill gaps" helper — it only writes values where the existing
    column is NULL *and* the caller has provided a non-None replacement.
    Non-NULL values are never overwritten.  Called by ``get_or_create_event()``
    on the hot path so it short-circuits when there is nothing to update.

    The events table is NOT SCD Type 2, so a direct UPDATE is correct.

    Args:
        existing: The current event row dict (from ``get_event()``).
        start_time: Candidate start time (ISO 8601 string).
        end_time: Candidate end time (ISO 8601 string).
        status: Candidate status string.
        game_id: Candidate FK to games(id).

    Educational Note:
        This pattern avoids a separate SELECT + UPDATE round-trip.  Because
        ``get_or_create_event()`` already calls ``get_event()``, we inspect
        the returned dict in Python and only issue an UPDATE when at least
        one NULL field can be filled.  On a steady-state poll cycle where
        events are already enriched, zero UPDATEs are executed.

    Reference:
        - Issue #513: Enrichment data gaps
        - get_or_create_event() — sole caller
    """
    set_parts: list[str] = []
    params: list[Any] = []

    if start_time and existing.get("start_time") is None:
        set_parts.append("start_time = %s")
        params.append(start_time)
    if end_time and existing.get("end_time") is None:
        set_parts.append("end_time = %s")
        params.append(end_time)
    if status and existing.get("status") is None:
        set_parts.append("status = %s")
        params.append(status)
    if game_id is not None and existing.get("game_id") is None:
        set_parts.append("game_id = %s")
        params.append(game_id)

    if not set_parts:
        return  # Nothing to fill — hot path exits here

    set_parts.append("updated_at = NOW()")
    query = f"UPDATE events SET {', '.join(set_parts)} WHERE id = %s"  # noqa: S608
    params.append(existing["id"])

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)


def get_or_create_event(
    event_id: str,
    platform_id: str,
    external_id: str,
    category: str,
    title: str,
    series_internal_id: int | None = None,
    subcategory: str | None = None,
    description: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    status: str | None = None,
    metadata: dict | None = None,
    game_id: int | None = None,
) -> tuple[int, bool]:
    """
    Get an existing event or create it if it doesn't exist.

    This is a convenience function that combines get_event() and create_event()
    to handle the common pattern of "upsert" behavior for events.

    Args:
        event_id: Legacy parameter name kept for caller compatibility.
            The value is looked up via ``external_id`` in the DB.
        platform_id: Foreign key to platforms table
        external_id: External ID from the platform API
        category: Event category
        title: Event title
        series_internal_id: Optional integer FK to series(id) surrogate PK
        subcategory: Optional subcategory
        description: Optional description
        start_time: Optional start time
        end_time: Optional end time
        status: Optional status
        metadata: Optional metadata
        game_id: Optional integer FK to games(id). Links event to ESPN game.

    Returns:
        Tuple of (id, created) where id is the integer surrogate PK and
        created is True if event was newly created, False if it already existed.
        Callers use the returned id to set markets.event_internal_id FK.

    Example:
        >>> event_pk, created = get_or_create_event(
        ...     event_id="KXNFL-24DEC22-KC-SEA",
        ...     platform_id="kalshi",
        ...     external_id="KXNFL-24DEC22-KC-SEA",
        ...     category="sports",
        ...     title="Chiefs vs Seahawks - Dec 22, 2024",
        ...     series_internal_id=42,
        ...     game_id=15,
        ... )
        >>> if created:
        ...     print(f"Created new event with PK: {event_pk}")
        ... else:
        ...     print(f"Event already exists with PK: {event_pk}")

    Educational Note:
        This pattern is essential for polling services like KalshiMarketPoller.
        When polling API data, the same events appear repeatedly. This function
        ensures we don't attempt duplicate inserts (which would fail due to
        UNIQUE constraint on external_id+platform_id) while still creating
        new events when they appear.

    Reference:
        - src/precog/schedulers/kalshi_poller.py
        - Migration 0019: events.series_internal_id replaces events.series_id
        - Migration 0020: events.id SERIAL PK, returns integer instead of VARCHAR
        - Migration 0047: Dropped redundant event_id column
        - Migration 0038: events.game_id FK to games(id)
    """
    # Check if event already exists — fill NULL enrichment fields if caller
    # provides values, then return surrogate PK.  This is a "fill gaps" pattern:
    # we never overwrite a non-NULL value, only backfill NULLs.  The existing
    # get_event() SELECT is already on the hot path so the NULL checks are
    # essentially free; the UPDATE only fires when there are actual gaps.
    existing = get_event(event_id)
    if existing is not None:
        _fill_event_null_fields(existing, start_time, end_time, status, game_id)
        return cast("int", existing["id"]), False

    # Create new event — create_event() now returns the integer PK
    event_pk = create_event(
        event_id=event_id,
        platform_id=platform_id,
        external_id=external_id,
        category=category,
        title=title,
        series_internal_id=series_internal_id,
        subcategory=subcategory,
        description=description,
        start_time=start_time,
        end_time=end_time,
        status=status,
        metadata=metadata,
        game_id=game_id,
    )
    return event_pk, True
