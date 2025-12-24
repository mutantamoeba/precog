"""
Integration tests for series CRUD operations.

Tests the series-related database operations against the real database:
- get_series: Retrieve a series by series_id
- list_series: List series with filtering and pagination
- create_series: Create a new series record
- update_series: Update an existing series
- get_or_create_series: Upsert pattern for series

Reference: TESTING_STRATEGY_V3.2.md Section "Integration Tests"
Related Requirements: REQ-DATA-005 (Market Data Storage)
"""

import uuid
from collections.abc import Generator
from typing import Any

import pytest

from precog.database.crud_operations import (
    create_series,
    get_or_create_series,
    get_series,
    list_series,
    update_series,
)

# Mark all tests in this module as integration tests
pytestmark = [pytest.mark.integration]


# =============================================================================
# Module-level Setup: Clean up stale property test data
# =============================================================================


@pytest.fixture(scope="module", autouse=True)
def cleanup_stale_test_series() -> Generator[None, None, None]:
    """
    Clean up stale series from property tests before running integration tests.

    Property tests create PROP-TEST-* series that may not be cleaned up if
    tests are interrupted. This fixture ensures a clean slate for integration
    tests that rely on predictable database state.

    Educational Note:
        This is a common pattern in integration testing - ensuring test
        isolation by cleaning up data from other test types that share
        the same database.
    """
    from precog.database.connection import get_cursor

    # Clean up before tests
    with get_cursor() as cur:
        cur.execute("DELETE FROM series WHERE series_id LIKE 'PROP-TEST-%'")
        deleted = cur.rowcount
        if deleted > 0:
            # Note: This is expected during parallel test runs
            pass  # Cleaned up {deleted} stale property test series

    yield

    # Clean up after tests as well (defensive)
    with get_cursor() as cur:
        cur.execute("DELETE FROM series WHERE series_id LIKE 'PROP-TEST-%'")


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def unique_series_id() -> str:
    """Generate a unique series ID for testing."""
    return f"TEST-SERIES-{uuid.uuid4().hex[:8].upper()}"


@pytest.fixture
def created_series(unique_series_id: str) -> Generator[dict[str, Any], None, None]:
    """Create a test series and clean up after test."""
    series_id = create_series(
        series_id=unique_series_id,
        platform_id="kalshi",
        external_id=f"EXT-{unique_series_id}",
        category="sports",
        title="Test Series for Integration Tests",
        subcategory="nfl",
        frequency="daily",  # Kalshi API vocabulary
        tags=["Football", "TestTag"],
    )

    yield {
        "series_id": series_id,
        "platform_id": "kalshi",
        "external_id": f"EXT-{unique_series_id}",
        "category": "sports",
        "title": "Test Series for Integration Tests",
        "subcategory": "nfl",
        "tags": ["Football", "TestTag"],
    }

    # Cleanup: Delete the test series
    from precog.database.connection import get_cursor

    with get_cursor() as cur:
        cur.execute("DELETE FROM series WHERE series_id = %s", (series_id,))


# =============================================================================
# get_series Tests
# =============================================================================


class TestGetSeriesIntegration:
    """Integration tests for get_series function."""

    def test_get_series_returns_dict_when_found(self, created_series: dict[str, Any]) -> None:
        """get_series should return a dictionary when series exists."""
        result = get_series(created_series["series_id"])

        assert result is not None
        assert result["series_id"] == created_series["series_id"]
        assert result["category"] == "sports"
        assert result["subcategory"] == "nfl"
        assert result["tags"] == ["Football", "TestTag"]

    def test_get_series_returns_none_when_not_found(self) -> None:
        """get_series should return None when series does not exist."""
        result = get_series("NONEXISTENT-SERIES-ID-12345")

        assert result is None

    def test_get_series_returns_all_fields(self, created_series: dict[str, Any]) -> None:
        """get_series should return all series fields."""
        result = get_series(created_series["series_id"])

        assert result is not None
        expected_fields = [
            "series_id",
            "platform_id",
            "external_id",
            "category",
            "subcategory",
            "title",
            "frequency",
            "tags",
            "metadata",
            "created_at",
            "updated_at",
        ]
        for field in expected_fields:
            assert field in result, f"Missing field: {field}"


# =============================================================================
# list_series Tests
# =============================================================================


class TestListSeriesIntegration:
    """Integration tests for list_series function."""

    def test_list_series_returns_list(self, created_series: dict[str, Any]) -> None:
        """list_series should return a list including our test series.

        Educational Note:
            Use a high limit (1000) to ensure we find the test series even if
            there's leftover data from property tests. The test series starts
            with "TEST-" which is alphabetically after "PROP-TEST-*" entries.
        """
        result = list_series(limit=1000)

        assert isinstance(result, list)
        assert len(result) >= 1
        series_ids = [s["series_id"] for s in result]
        assert created_series["series_id"] in series_ids

    def test_list_series_with_platform_filter(self, created_series: dict[str, Any]) -> None:
        """list_series should filter by platform_id."""
        result = list_series(platform_id="kalshi")

        assert len(result) >= 1
        for series in result:
            assert series["platform_id"] == "kalshi"

    def test_list_series_with_category_filter(self, created_series: dict[str, Any]) -> None:
        """list_series should filter by category."""
        result = list_series(category="sports")

        assert len(result) >= 1
        for series in result:
            assert series["category"] == "sports"

    def test_list_series_with_tags_filter(self, created_series: dict[str, Any]) -> None:
        """list_series should filter by tags array containment."""
        result = list_series(tags=["TestTag"])

        assert len(result) >= 1
        for series in result:
            assert "TestTag" in series["tags"]

    def test_list_series_with_pagination_limit(self, created_series: dict[str, Any]) -> None:
        """list_series should respect limit parameter."""
        result = list_series(limit=1)

        assert len(result) <= 1

    def test_list_series_with_pagination_offset(self, created_series: dict[str, Any]) -> None:
        """list_series should respect offset parameter.

        Educational Note:
            Pagination tests need careful design. If total records > limit,
            both queries return limit items. We verify offset works by checking
            that the first item of the offset query matches the second item
            of the non-offset query.
        """
        # Get first 5 items without offset
        first_page = list_series(limit=5)

        if len(first_page) >= 2:
            # Get items with offset=1 (should skip first item)
            with_offset = list_series(limit=5, offset=1)

            # The first item with offset should be the second item without offset
            # (assuming consistent ordering by series_id)
            if with_offset:
                assert first_page[1]["series_id"] == with_offset[0]["series_id"], (
                    "Offset should skip the first item"
                )

    def test_list_series_combined_filters(self, created_series: dict[str, Any]) -> None:
        """list_series should support multiple filters together."""
        result = list_series(
            platform_id="kalshi",
            category="sports",
            tags=["Football"],
            limit=10,
        )

        for series in result:
            assert series["platform_id"] == "kalshi"
            assert series["category"] == "sports"
            assert "Football" in series["tags"]


# =============================================================================
# create_series Tests
# =============================================================================


class TestCreateSeriesIntegration:
    """Integration tests for create_series function."""

    def test_create_series_returns_series_id(self, unique_series_id: str) -> None:
        """create_series should return the created series_id."""
        result = create_series(
            series_id=unique_series_id,
            platform_id="kalshi",
            external_id=f"EXT-{unique_series_id}",
            category="sports",
            title="New Test Series",
        )

        assert result == unique_series_id

        # Cleanup
        from precog.database.connection import get_cursor

        with get_cursor() as cur:
            cur.execute("DELETE FROM series WHERE series_id = %s", (unique_series_id,))

    def test_create_series_with_all_fields(self, unique_series_id: str) -> None:
        """create_series should store all provided fields."""
        create_series(
            series_id=unique_series_id,
            platform_id="kalshi",
            external_id=f"EXT-{unique_series_id}",
            category="sports",
            title="Complete Test Series",
            subcategory="nfl",
            frequency="daily",  # Kalshi API vocabulary
            tags=["Football", "NFL"],
            metadata={"source": "test"},
        )

        result = get_series(unique_series_id)
        assert result is not None
        assert result["subcategory"] == "nfl"
        assert result["frequency"] == "daily"
        assert result["tags"] == ["Football", "NFL"]
        assert result["metadata"] == {"source": "test"}

        # Cleanup
        from precog.database.connection import get_cursor

        with get_cursor() as cur:
            cur.execute("DELETE FROM series WHERE series_id = %s", (unique_series_id,))


# =============================================================================
# update_series Tests
# =============================================================================


class TestUpdateSeriesIntegration:
    """Integration tests for update_series function."""

    def test_update_series_modifies_fields(self, created_series: dict[str, Any]) -> None:
        """update_series should modify the specified fields."""
        updated = update_series(
            series_id=created_series["series_id"],
            title="Updated Title",
            tags=["UpdatedTag"],
        )

        assert updated is True

        result = get_series(created_series["series_id"])
        assert result is not None
        assert result["title"] == "Updated Title"
        assert result["tags"] == ["UpdatedTag"]

    def test_update_series_returns_false_when_not_found(self) -> None:
        """update_series should return False when series does not exist."""
        updated = update_series(
            series_id="NONEXISTENT-SERIES-ID",
            title="New Title",
        )

        assert updated is False


# =============================================================================
# get_or_create_series Tests
# =============================================================================


class TestGetOrCreateSeriesIntegration:
    """Integration tests for get_or_create_series function."""

    def test_get_or_create_creates_new_series(self, unique_series_id: str) -> None:
        """get_or_create_series should create new series when not found."""
        series_id, created = get_or_create_series(
            series_id=unique_series_id,
            platform_id="kalshi",
            external_id=f"EXT-{unique_series_id}",
            category="sports",
            title="New Series via Upsert",
        )

        assert series_id == unique_series_id
        assert created is True

        # Verify it exists
        result = get_series(unique_series_id)
        assert result is not None

        # Cleanup
        from precog.database.connection import get_cursor

        with get_cursor() as cur:
            cur.execute("DELETE FROM series WHERE series_id = %s", (unique_series_id,))

    def test_get_or_create_returns_existing_series(self, created_series: dict[str, Any]) -> None:
        """get_or_create_series should return existing series without creating."""
        series_id, created = get_or_create_series(
            series_id=created_series["series_id"],
            platform_id="kalshi",
            external_id=created_series["external_id"],
            category="sports",
            title="Should Not Override",
            update_if_exists=False,
        )

        assert series_id == created_series["series_id"]
        assert created is False

        # Verify title was not changed
        result = get_series(created_series["series_id"])
        assert result["title"] == "Test Series for Integration Tests"

    def test_get_or_create_updates_when_flag_set(self, created_series: dict[str, Any]) -> None:
        """get_or_create_series should update existing when update_if_exists=True."""
        series_id, created = get_or_create_series(
            series_id=created_series["series_id"],
            platform_id="kalshi",
            external_id=created_series["external_id"],
            category="sports",
            title="Updated via Upsert",
            update_if_exists=True,
        )

        assert series_id == created_series["series_id"]
        assert created is False

        # Verify title was updated
        result = get_series(created_series["series_id"])
        assert result["title"] == "Updated via Upsert"
