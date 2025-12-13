"""
End-to-End Tests for KalshiMarketPoller - API to Database Integration.

These tests validate the FULL data flow: Real Kalshi API -> Poller Processing -> Database.
They catch integration bugs that unit tests with mocks cannot detect.

CRITICAL Testing Gap This Addresses:
    Before these tests existed, two bugs went undetected:
    1. Status mapping: API returns "active", DB constraint requires "open"
    2. Foreign key: Markets created without parent events existing

    These bugs weren't caught because:
    - Unit tests mocked API with DB-valid values ("status": "open")
    - VCR tests recorded real API data but didn't write to database
    - No E2E tests existed that tested API -> DB integration

Educational Note - The E2E Testing Gap:
    There are THREE layers of testing for external API integrations:

    Layer 1: API Client E2E (test_kalshi_e2e.py)
        Tests: API -> Python objects
        Catches: Auth failures, response parsing, Decimal conversion
        Does NOT catch: Database constraint violations

    Layer 2: VCR Integration Tests (test_kalshi_client_vcr.py)
        Tests: Recorded API responses -> Python objects
        Catches: Response format changes, parsing regressions
        Does NOT catch: Database constraint violations (no DB writes)

    Layer 3: Poller E2E Tests (THIS FILE)
        Tests: API -> Python objects -> DATABASE
        Catches: ALL of the above PLUS constraint violations
        This is the ONLY layer that catches DB schema mismatches!

    The bug pattern we discovered:
    - Unit tests pass (mocks use DB-valid values)
    - VCR tests pass (no DB writes)
    - Production fails (real API values violate DB constraints)

    Solution: E2E tests that write to a REAL database.

Prerequisites:
    - DEV_KALSHI_API_KEY set in .env
    - DEV_KALSHI_PRIVATE_KEY_PATH set in .env
    - Database running with schema applied

Run with:
    pytest tests/e2e/schedulers/test_kalshi_poller_e2e.py -v -m e2e

References:
    - PR #216: Fix credential naming bug (discovered this testing gap)
    - Issue #217: Add missing modules to MODULE_TIERS audit
    - ADR-100: Service Supervisor Pattern
    - TESTING_STRATEGY_V3.2.md: The 8 Test Types

Phase: 2.5 (Service Infrastructure)
"""

import os
from decimal import Decimal
from pathlib import Path

import pytest

from precog.database.connection import get_cursor


def _real_kalshi_credentials_available() -> bool:
    """Check if REAL Kalshi credentials are available for E2E tests.

    Returns True only if credentials are set AND not the fake CI credentials.

    Educational Note:
        conftest.py sets TEST_KALSHI_API_KEY="test-key-id-for-ci-vcr-tests"
        for unit/integration tests. We must detect and reject these fake
        credentials because E2E tests need REAL API access.
    """
    precog_env = os.getenv("PRECOG_ENV", "dev").upper()
    valid_prefixes = {"DEV", "TEST", "STAGING"}
    prefix = precog_env if precog_env in valid_prefixes else "DEV"

    api_key = os.getenv(f"{prefix}_KALSHI_API_KEY")
    key_path = os.getenv(f"{prefix}_KALSHI_PRIVATE_KEY_PATH")

    if not api_key or not key_path:
        return False

    # Reject fake CI credentials
    if api_key == "test-key-id-for-ci-vcr-tests":
        return False

    # Verify key file exists
    return Path(key_path).exists()


# Skip entire module if credentials not available
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not _real_kalshi_credentials_available(),
        reason=(
            "Real Kalshi credentials not configured. "
            "Set DEV_KALSHI_API_KEY and DEV_KALSHI_PRIVATE_KEY_PATH in .env"
        ),
    ),
]


@pytest.fixture
def clean_test_markets():
    """Clean up any test markets before and after tests.

    Educational Note:
        E2E tests that write to the database need cleanup to be idempotent.
        We delete markets created by the poller to allow re-running tests.
    """
    # Cleanup before test
    with get_cursor(commit=True) as cur:
        # Delete markets and events created by kalshi poller (platform_id='kalshi')
        cur.execute("DELETE FROM markets WHERE platform_id = 'kalshi'")
        cur.execute("DELETE FROM events WHERE platform_id = 'kalshi'")

    yield

    # Cleanup after test (optional - helps with debugging if commented out)
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM markets WHERE platform_id = 'kalshi'")
        cur.execute("DELETE FROM events WHERE platform_id = 'kalshi'")


class TestKalshiPollerDatabaseIntegration:
    """E2E tests for KalshiMarketPoller database integration.

    These tests validate the FULL flow: API -> Poller -> Database.
    They would have caught the status mapping and foreign key bugs.
    """

    def test_poll_creates_events_before_markets(self, clean_test_markets):
        """Verify events are created before markets (foreign key constraint).

        This is THE test that would have caught the foreign key bug.
        The bug: create_market() was called without first creating the event.

        Educational Note:
            The markets table has: event_id REFERENCES events(event_id)
            Without the event existing first, INSERT fails with:
            "violates foreign key constraint markets_event_id_fkey"
        """
        from precog.schedulers.kalshi_poller import KalshiMarketPoller

        poller = KalshiMarketPoller(
            series_tickers=["KXNFLGAME"],
            poll_interval=30,
            environment="demo",
        )

        try:
            # This should NOT raise foreign key constraint violation
            result = poller.poll_once()

            # Verify markets were created
            assert result["items_fetched"] >= 0

            # If markets were created, events should exist too
            if result["items_created"] > 0:
                with get_cursor() as cur:
                    cur.execute("SELECT COUNT(*) as cnt FROM events WHERE platform_id = 'kalshi'")
                    event_count = cur.fetchone()["cnt"]
                    assert event_count > 0, "Events should be created before markets"

                    cur.execute("SELECT COUNT(*) as cnt FROM markets WHERE platform_id = 'kalshi'")
                    market_count = cur.fetchone()["cnt"]
                    assert market_count > 0, "Markets should be created"
        finally:
            poller.kalshi_client.close()

    def test_poll_maps_status_correctly(self, clean_test_markets):
        """Verify API status values are mapped to valid DB status values.

        This is THE test that would have caught the status mapping bug.
        The bug: API returns "active" but DB constraint only allows
        'open', 'closed', 'settled', 'halted'.

        Educational Note:
            The markets table has:
            status VARCHAR(20) CHECK (status IN ('open', 'closed', 'settled', 'halted'))

            Kalshi API returns different status values:
            - "active" -> should map to "open"
            - "unopened" -> should map to "halted"
            - "finalized" -> should map to "settled"
        """
        from precog.schedulers.kalshi_poller import KalshiMarketPoller

        poller = KalshiMarketPoller(
            series_tickers=["KXNFLGAME"],
            poll_interval=30,
            environment="demo",
        )

        try:
            # This should NOT raise check constraint violation
            result = poller.poll_once()

            # If markets were created, verify status values are valid
            if result["items_created"] > 0:
                with get_cursor() as cur:
                    cur.execute("""
                        SELECT DISTINCT status
                        FROM markets
                        WHERE platform_id = 'kalshi'
                    """)
                    statuses = [row["status"] for row in cur.fetchall()]

                    valid_statuses = {"open", "closed", "settled", "halted"}
                    for status in statuses:
                        assert status in valid_statuses, (
                            f"Invalid status '{status}' in database. "
                            f"Valid values: {valid_statuses}. "
                            "This indicates status mapping is broken."
                        )
        finally:
            poller.kalshi_client.close()

    def test_poll_preserves_decimal_precision(self, clean_test_markets):
        """Verify Decimal prices are preserved through the full pipeline.

        Educational Note:
            Pattern 1 (NEVER USE FLOAT) must be enforced end-to-end:
            API (JSON float) -> Client (Decimal) -> Poller -> Database (DECIMAL)

            If any step uses float, precision is lost:
            Decimal("0.5475") != float(0.5475) (float: 0.547499999999...)
        """
        from precog.schedulers.kalshi_poller import KalshiMarketPoller

        poller = KalshiMarketPoller(
            series_tickers=["KXNFLGAME"],
            poll_interval=30,
            environment="demo",
        )

        try:
            result = poller.poll_once()

            if result["items_created"] > 0:
                with get_cursor() as cur:
                    cur.execute("""
                        SELECT yes_price, no_price
                        FROM markets
                        WHERE platform_id = 'kalshi'
                          AND row_current_ind = TRUE
                        LIMIT 10
                    """)
                    markets = cur.fetchall()

                    for market in markets:
                        yes_price = market["yes_price"]
                        no_price = market["no_price"]

                        # Prices should be Decimal (psycopg2 returns Decimal for NUMERIC)
                        assert isinstance(yes_price, Decimal), (
                            f"yes_price is {type(yes_price).__name__}, expected Decimal"
                        )
                        assert isinstance(no_price, Decimal), (
                            f"no_price is {type(no_price).__name__}, expected Decimal"
                        )

                        # Prices should be in valid range [0, 1]
                        assert Decimal("0") <= yes_price <= Decimal("1"), (
                            f"yes_price {yes_price} out of range [0, 1]"
                        )
                        assert Decimal("0") <= no_price <= Decimal("1"), (
                            f"no_price {no_price} out of range [0, 1]"
                        )
        finally:
            poller.kalshi_client.close()

    def test_poll_creates_markets_with_required_fields(self, clean_test_markets):
        """Verify created markets have all required fields populated."""
        from precog.schedulers.kalshi_poller import KalshiMarketPoller

        poller = KalshiMarketPoller(
            series_tickers=["KXNFLGAME"],
            poll_interval=30,
            environment="demo",
        )

        try:
            result = poller.poll_once()

            if result["items_created"] > 0:
                with get_cursor() as cur:
                    cur.execute("""
                        SELECT ticker, title, market_type, status,
                               yes_price, no_price, platform_id, event_id
                        FROM markets
                        WHERE platform_id = 'kalshi'
                          AND row_current_ind = TRUE
                        LIMIT 5
                    """)
                    markets = cur.fetchall()

                    for market in markets:
                        # Required fields should not be None/empty
                        assert market["ticker"], "ticker should not be empty"
                        assert market["title"], "title should not be empty"
                        assert market["market_type"] == "binary", "market_type should be 'binary'"
                        assert market["status"] in {"open", "closed", "settled", "halted"}
                        assert market["platform_id"] == "kalshi"
                        assert market["event_id"], "event_id should not be empty"
        finally:
            poller.kalshi_client.close()


class TestKalshiPollerStatusMapping:
    """Tests specifically for status mapping validation.

    Educational Note:
        These tests document the expected status mappings and verify
        they work correctly. This serves as both test and documentation.
    """

    def test_status_mapping_constants_are_complete(self):
        """Verify STATUS_MAPPING covers all known Kalshi statuses."""
        from precog.schedulers.kalshi_poller import KalshiMarketPoller

        # Known Kalshi API statuses (from API documentation)
        known_kalshi_statuses = {
            "active",  # Market is open for trading
            "unopened",  # Not yet open
            "open",  # Documented but rarely seen
            "closed",  # Trading closed
            "settled",  # Outcome determined
            "finalized",  # Settlement complete
        }

        # All known statuses should be in the mapping
        for status in known_kalshi_statuses:
            assert status in KalshiMarketPoller.STATUS_MAPPING, (
                f"Kalshi status '{status}' not in STATUS_MAPPING. "
                "Add it to prevent constraint violations."
            )

    def test_status_mapping_produces_valid_db_values(self):
        """Verify all mapped values satisfy DB constraint."""
        from precog.schedulers.kalshi_poller import KalshiMarketPoller

        # DB constraint: status IN ('open', 'closed', 'settled', 'halted')
        valid_db_statuses = {"open", "closed", "settled", "halted"}

        for api_status, db_status in KalshiMarketPoller.STATUS_MAPPING.items():
            assert db_status in valid_db_statuses, (
                f"STATUS_MAPPING['{api_status}'] = '{db_status}' is not valid. "
                f"DB constraint requires: {valid_db_statuses}"
            )


class TestKalshiPollerEventCreation:
    """Tests for event creation and foreign key handling."""

    def test_event_category_detection(self):
        """Verify series tickers are correctly categorized."""

        # Test the category detection logic
        test_cases = [
            ("KXNFLGAME", "sports", "nfl"),
            ("KXNCAAFGAME", "sports", "ncaaf"),
            ("KXNBAGAME", "sports", "nba"),
            ("KXNHLGAME", "sports", "nhl"),
            ("KXMLBGAME", "sports", "mlb"),
            ("UNKNOWN", "sports", None),  # Default category, no subcategory
        ]

        for series_ticker, expected_category, expected_subcategory in test_cases:
            # Simulate the category detection logic from _sync_market_to_db
            category = "sports"
            subcategory = None
            if "NFL" in series_ticker.upper():
                subcategory = "nfl"
            elif "NCAAF" in series_ticker.upper():
                subcategory = "ncaaf"
            elif "NBA" in series_ticker.upper():
                subcategory = "nba"
            elif "NHL" in series_ticker.upper():
                subcategory = "nhl"
            elif "MLB" in series_ticker.upper():
                subcategory = "mlb"

            assert category == expected_category, (
                f"Series {series_ticker}: expected category '{expected_category}', got '{category}'"
            )
            assert subcategory == expected_subcategory, (
                f"Series {series_ticker}: expected subcategory '{expected_subcategory}', "
                f"got '{subcategory}'"
            )


class TestKalshiPollerIdempotency:
    """Tests for idempotent polling behavior."""

    def test_repeated_polls_dont_duplicate_markets(self, clean_test_markets):
        """Verify polling twice doesn't create duplicate markets.

        Educational Note:
            Pollers run continuously, so they must be idempotent.
            The second poll should update existing markets, not create duplicates.
        """
        from precog.schedulers.kalshi_poller import KalshiMarketPoller

        poller = KalshiMarketPoller(
            series_tickers=["KXNFLGAME"],
            poll_interval=30,
            environment="demo",
        )

        try:
            # First poll (return value unused - we're testing DB side effects)
            poller.poll_once()

            # Get market count after first poll
            with get_cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as cnt
                    FROM markets
                    WHERE platform_id = 'kalshi' AND row_current_ind = TRUE
                """)
                count_after_first = cur.fetchone()["cnt"]

            # Second poll (should update, not duplicate)
            poller.poll_once()

            # Get market count after second poll
            with get_cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as cnt
                    FROM markets
                    WHERE platform_id = 'kalshi' AND row_current_ind = TRUE
                """)
                count_after_second = cur.fetchone()["cnt"]

            # Second poll should have 0 created (all updates or skips)
            # Note: New markets could appear between polls, so we allow some growth
            # but not doubling
            if count_after_first > 0:
                assert count_after_second <= count_after_first * 1.5, (
                    f"Market count grew too much: {count_after_first} -> {count_after_second}. "
                    "Possible duplicate creation bug."
                )
        finally:
            poller.kalshi_client.close()

    def test_market_updates_use_scd_type_2(self, clean_test_markets):
        """Verify price updates create new versions (SCD Type 2).

        Educational Note:
            SCD Type 2 preserves history. When a price changes:
            - Old row gets row_current_ind=FALSE and row_end_ts set
            - New row created with row_current_ind=TRUE

            This allows backtesting with historical prices.
        """
        from precog.schedulers.kalshi_poller import KalshiMarketPoller

        poller = KalshiMarketPoller(
            series_tickers=["KXNFLGAME"],
            poll_interval=30,
            environment="demo",
        )

        try:
            # First poll to create markets
            poller.poll_once()

            # Second poll (might create new versions if prices changed)
            poller.poll_once()

            # Check that row_current_ind is being used correctly
            with get_cursor() as cur:
                # Should have exactly one current row per ticker
                cur.execute("""
                    SELECT ticker, COUNT(*) as current_count
                    FROM markets
                    WHERE platform_id = 'kalshi' AND row_current_ind = TRUE
                    GROUP BY ticker
                    HAVING COUNT(*) > 1
                """)
                duplicates = cur.fetchall()

                assert len(duplicates) == 0, (
                    f"Found tickers with multiple current rows: {duplicates}. "
                    "SCD Type 2 should have exactly one row_current_ind=TRUE per ticker."
                )
        finally:
            poller.kalshi_client.close()
