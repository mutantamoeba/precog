"""
Integration tests for Kalshi series fetching and pagination.

Tests the fetch_all_series() cursor-chasing pagination and get_series()
single-page fetch. Uses mocked HTTP responses to verify:
- Cursor-chasing across multiple pages
- Client-side category filtering
- No silent truncation (the bug this fixes)
- Empty response handling
- max_pages safety limit

Pattern 13 Exception: External API mock
These tests mock HTTP responses to test API client behavior.

Related Requirements:
    - REQ-API-001: Kalshi API Integration
"""

from unittest.mock import MagicMock, Mock

import pytest

from precog.api_connectors.kalshi_client import KalshiClient


def _make_mock_client() -> KalshiClient:
    """Create a KalshiClient with mocked auth (no real credentials needed)."""
    mock_auth = MagicMock()
    mock_auth.get_headers.return_value = {"Authorization": "Bearer mock"}
    return KalshiClient(
        environment="demo",
        auth=mock_auth,
        session=MagicMock(),
        rate_limiter=MagicMock(),
    )


def _mock_series(ticker: str, category: str = "Sports") -> dict:
    """Create a minimal series dict for testing."""
    return {
        "ticker": ticker,
        "title": f"Test {ticker}",
        "category": category,
        "tags": [],
    }


@pytest.mark.integration
@pytest.mark.api
class TestFetchAllSeries:
    """Tests for fetch_all_series() cursor-chasing pagination."""

    def test_single_page_no_cursor(self) -> None:
        """fetch_all_series returns all results when API has one page (cursor=None)."""
        client = _make_mock_client()
        series_data = [_mock_series("KXNFLGAME"), _mock_series("KXNBAGAME")]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"series": series_data, "cursor": ""}
        mock_response.raise_for_status = Mock()
        client.session.request.return_value = mock_response

        result = client.fetch_all_series(category="Sports")

        assert len(result) == 2
        assert result[0]["ticker"] == "KXNFLGAME"
        assert result[1]["ticker"] == "KXNBAGAME"

    def test_cursor_chasing_across_pages(self) -> None:
        """fetch_all_series follows cursors until no more pages.

        Educational Note:
            This simulates the scenario where Kalshi adds server-side pagination
            to the /series endpoint. The method should chase cursors automatically,
            returning the combined results from all pages.
        """
        client = _make_mock_client()

        page1_response = Mock()
        page1_response.status_code = 200
        page1_response.json.return_value = {
            "series": [_mock_series("KXNFLGAME"), _mock_series("KXNBAGAME")],
            "cursor": "page2_cursor",
        }
        page1_response.raise_for_status = Mock()

        page2_response = Mock()
        page2_response.status_code = 200
        page2_response.json.return_value = {
            "series": [_mock_series("KXNHLGAME")],
            "cursor": "",  # No more pages
        }
        page2_response.raise_for_status = Mock()

        client.session.request.side_effect = [page1_response, page2_response]

        result = client.fetch_all_series(category="Sports")

        assert len(result) == 3
        assert [s["ticker"] for s in result] == ["KXNFLGAME", "KXNBAGAME", "KXNHLGAME"]
        assert client.session.request.call_count == 2

    def test_max_pages_safety_limit(self) -> None:
        """fetch_all_series stops at max_pages to prevent infinite loops."""
        client = _make_mock_client()

        # Every page returns data + cursor (infinite pagination)
        infinite_response = Mock()
        infinite_response.status_code = 200
        infinite_response.json.return_value = {
            "series": [_mock_series("KXTEST")],
            "cursor": "next_page",
        }
        infinite_response.raise_for_status = Mock()
        client.session.request.return_value = infinite_response

        result = client.fetch_all_series(max_pages=3)

        assert len(result) == 3  # 1 series per page * 3 pages
        assert client.session.request.call_count == 3

    def test_empty_first_page(self) -> None:
        """fetch_all_series returns empty list when API returns no series."""
        client = _make_mock_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"series": [], "cursor": ""}
        mock_response.raise_for_status = Mock()
        client.session.request.return_value = mock_response

        result = client.fetch_all_series(category="Sports")

        assert result == []

    def test_category_filtering_applied(self) -> None:
        """fetch_all_series applies client-side category filtering.

        Educational Note:
            Kalshi's /series endpoint ignores the category param and returns
            all series. Client-side filtering in _get_series_page() ensures
            only the requested category is returned.
        """
        client = _make_mock_client()

        mixed_series = [
            _mock_series("KXNFLGAME", category="Sports"),
            _mock_series("KXPRES2028", category="Politics"),
            _mock_series("KXNBAGAME", category="Sports"),
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"series": mixed_series, "cursor": ""}
        mock_response.raise_for_status = Mock()
        client.session.request.return_value = mock_response

        result = client.fetch_all_series(category="Sports")

        assert len(result) == 2
        assert all(s["category"] == "Sports" for s in result)

    def test_no_silent_truncation(self) -> None:
        """fetch_all_series does NOT truncate results (the bug this fixes).

        Educational Note:
            The old code used get_series(limit=200) which client-side truncated
            1,533 Sports series to 200. fetch_all_series() has no limit param
            and returns everything the API provides.
        """
        client = _make_mock_client()

        # Simulate 500 series in one response (more than old limit=200)
        large_series = [_mock_series(f"KX{i:04d}", category="Sports") for i in range(500)]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"series": large_series, "cursor": ""}
        mock_response.raise_for_status = Mock()
        client.session.request.return_value = mock_response

        result = client.fetch_all_series(category="Sports")

        assert len(result) == 500  # All 500, not truncated to 200


@pytest.mark.integration
@pytest.mark.api
class TestGetSeriesLimitBehavior:
    """Tests for get_series() limit parameter behavior."""

    def test_limit_none_returns_all(self) -> None:
        """get_series with limit=None (default) returns all results."""
        client = _make_mock_client()

        series = [_mock_series(f"KX{i:03d}") for i in range(300)]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"series": series, "cursor": ""}
        mock_response.raise_for_status = Mock()
        client.session.request.return_value = mock_response

        result = client.get_series()

        assert len(result) == 300  # No truncation

    def test_explicit_limit_truncates(self) -> None:
        """get_series with explicit limit truncates client-side."""
        client = _make_mock_client()

        series = [_mock_series(f"KX{i:03d}") for i in range(300)]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"series": series, "cursor": ""}
        mock_response.raise_for_status = Mock()
        client.session.request.return_value = mock_response

        result = client.get_series(limit=10)

        assert len(result) == 10  # Explicitly truncated
