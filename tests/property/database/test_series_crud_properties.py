"""
Property-based tests for series CRUD operations.

Tests mathematical properties and invariants of series database operations
using Hypothesis.

Reference: TESTING_STRATEGY_V3.2.md Section "Property Tests"
Related Requirements: REQ-DATA-005 (Market Data Storage)
Related Pattern: Pattern 33 (API Vocabulary Alignment)
"""

import uuid

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from precog.database.connection import get_cursor
from precog.database.crud_operations import (
    create_series,
    get_or_create_series,
    get_series,
    list_series,
    update_series,
)

pytestmark = [pytest.mark.property, pytest.mark.integration]


# =============================================================================
# Custom Strategies
# =============================================================================

# Valid platform IDs (must exist in platforms table - currently only kalshi)
platform_strategy = st.just("kalshi")

# Valid categories (matches database CHECK constraint)
category_strategy = st.sampled_from(
    ["sports", "politics", "entertainment", "economics", "weather", "other"]
)

# Valid frequency values (Kalshi API vocabulary - Pattern 33)
frequency_strategy = st.sampled_from(["daily", "weekly", "monthly", "event", "once"])

# Subcategory values
subcategory_strategy = st.sampled_from(["nfl", "nba", "mlb", "nhl", "ncaaf", "ncaab", None])

# Tags list
tags_strategy = st.lists(
    st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
    min_size=0,
    max_size=5,
)


# Generate unique series ID
@st.composite
def series_id_strategy(draw: st.DrawFn) -> str:
    """Generate a unique series ID for testing."""
    suffix = draw(st.text(min_size=4, max_size=8, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"))
    return f"PROP-TEST-{suffix}"


# Generate valid title
title_strategy = st.text(
    min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("L", "N", "Zs"))
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def cleanup_test_series():
    """Clean up test series after each test."""
    yield
    with get_cursor() as cur:
        cur.execute("DELETE FROM series WHERE series_id LIKE 'PROP-TEST-%'")


# =============================================================================
# Property Tests: Create/Read Roundtrip
# =============================================================================


class TestSeriesCreateReadRoundtrip:
    """Property tests for create/read consistency."""

    @given(
        platform=platform_strategy,
        category=category_strategy,
        title=title_strategy,
        frequency=frequency_strategy,
    )
    @settings(max_examples=20)
    def test_create_then_get_returns_same_data(
        self,
        platform: str,
        category: str,
        title: str,
        frequency: str,
    ) -> None:
        """Created series should be retrievable with same data."""
        assume(len(title.strip()) > 0)

        series_id = f"PROP-TEST-{uuid.uuid4().hex[:8].upper()}"
        external_id = f"EXT-{series_id}"

        created_id = create_series(
            series_id=series_id,
            platform_id=platform,
            external_id=external_id,
            category=category,
            title=title.strip(),
            frequency=frequency,
        )

        assert created_id == series_id

        result = get_series(series_id)
        assert result is not None
        assert result["series_id"] == series_id
        assert result["platform_id"] == platform
        assert result["category"] == category
        assert result["frequency"] == frequency

    @given(
        category=category_strategy,
        tags=tags_strategy,
    )
    @settings(max_examples=15)
    def test_tags_roundtrip_preserves_order(
        self,
        category: str,
        tags: list[str],
    ) -> None:
        """Tags should be stored and retrieved in same order."""
        # Filter out empty tags
        valid_tags = [t for t in tags if t and len(t.strip()) > 0]
        if not valid_tags:
            valid_tags = None

        series_id = f"PROP-TEST-{uuid.uuid4().hex[:8].upper()}"

        create_series(
            series_id=series_id,
            platform_id="kalshi",
            external_id=f"EXT-{series_id}",
            category=category,
            title="Property Test Series",
            tags=valid_tags,
        )

        result = get_series(series_id)
        assert result is not None
        assert result["tags"] == valid_tags


# =============================================================================
# Property Tests: Get Or Create Idempotence
# =============================================================================


class TestSeriesGetOrCreateIdempotence:
    """Property tests for get_or_create idempotence."""

    @given(
        category=category_strategy,
        frequency=frequency_strategy,
    )
    @settings(max_examples=15)
    def test_get_or_create_is_idempotent(
        self,
        category: str,
        frequency: str,
    ) -> None:
        """Multiple get_or_create calls should return same series."""
        series_id = f"PROP-TEST-{uuid.uuid4().hex[:8].upper()}"

        # First call creates
        id1, created1 = get_or_create_series(
            series_id=series_id,
            platform_id="kalshi",
            external_id=f"EXT-{series_id}",
            category=category,
            title="Idempotence Test",
            frequency=frequency,
        )

        # Second call returns existing
        id2, created2 = get_or_create_series(
            series_id=series_id,
            platform_id="kalshi",
            external_id=f"EXT-{series_id}",
            category=category,
            title="Should Not Override",
            frequency=frequency,
            update_if_exists=False,
        )

        assert id1 == id2 == series_id
        assert created1 is True
        assert created2 is False

        # Verify original data preserved
        result = get_series(series_id)
        assert result["title"] == "Idempotence Test"

    @given(
        original_title=title_strategy,
        updated_title=title_strategy,
        category=category_strategy,
    )
    @settings(max_examples=10)
    def test_get_or_create_updates_when_flag_set(
        self,
        original_title: str,
        updated_title: str,
        category: str,
    ) -> None:
        """get_or_create with update_if_exists=True should update."""
        assume(len(original_title.strip()) > 0)
        assume(len(updated_title.strip()) > 0)
        assume(original_title.strip() != updated_title.strip())

        series_id = f"PROP-TEST-{uuid.uuid4().hex[:8].upper()}"

        # Create original
        get_or_create_series(
            series_id=series_id,
            platform_id="kalshi",
            external_id=f"EXT-{series_id}",
            category=category,
            title=original_title.strip(),
        )

        # Update via get_or_create
        _, created = get_or_create_series(
            series_id=series_id,
            platform_id="kalshi",
            external_id=f"EXT-{series_id}",
            category=category,
            title=updated_title.strip(),
            update_if_exists=True,
        )

        assert created is False

        # Verify updated
        result = get_series(series_id)
        assert result["title"] == updated_title.strip()


# =============================================================================
# Property Tests: Update Persistence
# =============================================================================


class TestSeriesUpdatePersistence:
    """Property tests for update operation persistence."""

    @given(
        original_title=title_strategy,
        new_title=title_strategy,
    )
    @settings(max_examples=15)
    def test_update_modifies_only_specified_fields(
        self,
        original_title: str,
        new_title: str,
    ) -> None:
        """Update should only modify fields that are passed."""
        assume(len(original_title.strip()) > 0)
        assume(len(new_title.strip()) > 0)

        series_id = f"PROP-TEST-{uuid.uuid4().hex[:8].upper()}"
        original_tags = ["OriginalTag"]

        create_series(
            series_id=series_id,
            platform_id="kalshi",
            external_id=f"EXT-{series_id}",
            category="sports",
            title=original_title.strip(),
            tags=original_tags,
            frequency="daily",
        )

        # Update only title
        success = update_series(
            series_id=series_id,
            title=new_title.strip(),
        )

        assert success is True

        result = get_series(series_id)
        assert result["title"] == new_title.strip()
        assert result["tags"] == original_tags  # Unchanged
        assert result["frequency"] == "daily"  # Unchanged

    @given(frequency=frequency_strategy)
    @settings(max_examples=10)
    def test_update_nonexistent_returns_false(self, frequency: str) -> None:
        """Updating nonexistent series should return False."""
        result = update_series(
            series_id=f"NONEXISTENT-{uuid.uuid4().hex[:8]}",
            frequency=frequency,
        )

        assert result is False


# =============================================================================
# Property Tests: List Filtering
# =============================================================================


class TestSeriesListFiltering:
    """Property tests for list filtering invariants."""

    @given(
        category=category_strategy,
        limit=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=10)
    def test_list_respects_limit(self, category: str, limit: int) -> None:
        """list_series should never return more than limit items."""
        result = list_series(category=category, limit=limit)

        assert len(result) <= limit

    @given(
        category=category_strategy,
    )
    @settings(max_examples=10)
    def test_list_category_filter_is_exact(self, category: str) -> None:
        """All returned series should match the category filter exactly."""
        # Create a series with this category
        series_id = f"PROP-TEST-{uuid.uuid4().hex[:8].upper()}"
        create_series(
            series_id=series_id,
            platform_id="kalshi",
            external_id=f"EXT-{series_id}",
            category=category,
            title="Filter Test Series",
        )

        result = list_series(category=category)

        for series in result:
            assert series["category"] == category

    @given(
        tag=st.text(min_size=3, max_size=15, alphabet=st.characters(whitelist_categories=("L",))),
    )
    @settings(max_examples=10)
    def test_list_tags_filter_contains_tag(self, tag: str) -> None:
        """All returned series should contain the filtered tag."""
        assume(len(tag.strip()) >= 3)
        clean_tag = tag.strip()

        # Create a series with this tag
        series_id = f"PROP-TEST-{uuid.uuid4().hex[:8].upper()}"
        create_series(
            series_id=series_id,
            platform_id="kalshi",
            external_id=f"EXT-{series_id}",
            category="sports",
            title="Tag Filter Test",
            tags=[clean_tag],
        )

        result = list_series(tags=[clean_tag])

        for series in result:
            assert clean_tag in series["tags"]


# =============================================================================
# Property Tests: Return Type Invariants
# =============================================================================


class TestSeriesReturnTypes:
    """Property tests for return type consistency."""

    @given(category=category_strategy)
    @settings(max_examples=10)
    def test_get_series_returns_dict_or_none(self, category: str) -> None:
        """get_series should return dict or None, never raise."""
        # Test with random ID (might exist, might not)
        random_id = f"RANDOM-{uuid.uuid4().hex[:8].upper()}"
        result = get_series(random_id)

        assert result is None or isinstance(result, dict)

    @given(limit=st.integers(min_value=1, max_value=100))
    @settings(max_examples=10)
    def test_list_series_always_returns_list(self, limit: int) -> None:
        """list_series should always return a list."""
        result = list_series(limit=limit)

        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, dict)

    @given(category=category_strategy)
    @settings(max_examples=5)
    def test_create_series_returns_string(self, category: str) -> None:
        """create_series should return the series_id string."""
        series_id = f"PROP-TEST-{uuid.uuid4().hex[:8].upper()}"

        result = create_series(
            series_id=series_id,
            platform_id="kalshi",
            external_id=f"EXT-{series_id}",
            category=category,
            title="Return Type Test",
        )

        assert isinstance(result, str)
        assert result == series_id
