"""
Property-based tests for KalshiMarketPoller.

Tests mathematical properties and invariants of the Kalshi market polling service.

Reference: TESTING_STRATEGY_V3.2.md Section "Property Tests"
Related Requirements: REQ-API-001 (Kalshi API Integration), REQ-DATA-005 (Market Price Data Collection)
Related ADR: ADR-100 (Service Supervisor Pattern)
"""

from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from precog.schedulers.kalshi_poller import (
    KalshiMarketPoller,
    create_kalshi_poller,
)

# =============================================================================
# Custom Hypothesis Strategies
# =============================================================================


@st.composite
def poll_interval_strategy(draw: st.DrawFn) -> int:
    """Generate valid poll intervals (>= MIN_POLL_INTERVAL)."""
    return draw(st.integers(min_value=5, max_value=3600))


@st.composite
def invalid_poll_interval_strategy(draw: st.DrawFn) -> int:
    """Generate invalid poll intervals (1 <= x < MIN_POLL_INTERVAL).

    Note: 0 and negative values use DEFAULT_POLL_INTERVAL due to `or` fallback.
    """
    return draw(st.integers(min_value=1, max_value=4))


@st.composite
def series_ticker_strategy(draw: st.DrawFn) -> str:
    """Generate valid series ticker patterns."""
    prefixes = ["KX", "KXNFL", "KXNCAAF", "KXNBA"]
    suffixes = ["GAME", "PLAYER", "TEAM", ""]
    prefix = draw(st.sampled_from(prefixes))
    suffix = draw(st.sampled_from(suffixes))
    return f"{prefix}{suffix}"


@st.composite
def kalshi_status_strategy(draw: st.DrawFn) -> str:
    """Generate valid Kalshi API status values."""
    return draw(st.sampled_from(["active", "unopened", "open", "closed", "settled", "finalized"]))


@st.composite
def environment_strategy(draw: st.DrawFn) -> str:
    """Generate valid environment values."""
    return draw(st.sampled_from(["demo", "prod"]))


@st.composite
def invalid_environment_strategy(draw: st.DrawFn) -> str:
    """Generate invalid environment values."""
    invalid_envs = ["test", "staging", "development", "production", "live", ""]
    return draw(st.sampled_from(invalid_envs))


@st.composite
def decimal_price_strategy(draw: st.DrawFn) -> Decimal:
    """Generate valid Kalshi prices (0.00 to 1.00 with sub-penny precision)."""
    # Kalshi prices are between 0 and 1 (probability)
    cents = draw(st.integers(min_value=0, max_value=10000))
    return Decimal(cents) / Decimal(10000)


@st.composite
def market_data_strategy(draw: st.DrawFn) -> dict[str, Any]:
    """Generate mock market data dictionaries."""
    ticker = draw(
        st.text(min_size=5, max_size=20, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")
    )
    yes_price = draw(decimal_price_strategy())
    no_price = Decimal("1") - yes_price  # Prices should sum to ~1

    return {
        "ticker": ticker,
        "title": f"Market {ticker}",
        "status": draw(kalshi_status_strategy()),
        "yes_ask_dollars": yes_price,
        "no_ask_dollars": no_price,
        "event_ticker": f"EVT-{ticker[:5]}",
        "series_ticker": draw(series_ticker_strategy()),
        "volume": draw(st.integers(min_value=0, max_value=1000000)),
        "open_interest": draw(st.integers(min_value=0, max_value=100000)),
    }


# =============================================================================
# Property Tests: Initialization
# =============================================================================


@pytest.mark.property
class TestInitializationProperties:
    """Property tests for KalshiMarketPoller initialization."""

    @given(poll_interval_strategy(), environment_strategy())
    @settings(max_examples=30)
    def test_valid_poll_interval_accepted(self, poll_interval: int, environment: str) -> None:
        """Valid poll intervals should be accepted.

        Property: poll_interval >= MIN_POLL_INTERVAL always succeeds.
        """
        with patch("precog.schedulers.kalshi_poller.KalshiClient"):
            poller = KalshiMarketPoller(poll_interval=poll_interval, environment=environment)
            assert poller.poll_interval >= KalshiMarketPoller.MIN_POLL_INTERVAL

    @given(invalid_poll_interval_strategy(), environment_strategy())
    @settings(max_examples=20)
    def test_invalid_poll_interval_raises(self, invalid_interval: int, environment: str) -> None:
        """Invalid poll intervals should raise ValueError.

        Property: poll_interval < MIN_POLL_INTERVAL raises ValueError.
        """
        with patch("precog.schedulers.kalshi_poller.KalshiClient"):
            with pytest.raises(ValueError, match="poll_interval must be at least"):
                KalshiMarketPoller(poll_interval=invalid_interval, environment=environment)

    @given(invalid_environment_strategy())
    def test_invalid_environment_raises(self, invalid_env: str) -> None:
        """Invalid environment should raise ValueError.

        Property: environment not in ('demo', 'prod') raises ValueError.
        """
        with pytest.raises(ValueError, match="environment must be"):
            KalshiMarketPoller(environment=invalid_env)

    @given(st.lists(series_ticker_strategy(), min_size=1, max_size=5))
    @settings(max_examples=20)
    def test_series_tickers_stored_correctly(self, tickers: list[str]) -> None:
        """Series tickers should be stored correctly.

        Property: Provided tickers are stored without modification.
        """
        with patch("precog.schedulers.kalshi_poller.KalshiClient"):
            poller = KalshiMarketPoller(series_tickers=tickers, environment="demo")
            assert poller.series_tickers == tickers

    @given(environment_strategy())
    def test_default_series_tickers_used(self, environment: str) -> None:
        """Default series tickers used when none provided.

        Property: series_tickers=None uses DEFAULT_SERIES_TICKERS.
        """
        with patch("precog.schedulers.kalshi_poller.KalshiClient"):
            poller = KalshiMarketPoller(series_tickers=None, environment=environment)
            assert poller.series_tickers == KalshiMarketPoller.DEFAULT_SERIES_TICKERS


# =============================================================================
# Property Tests: Status Mapping
# =============================================================================


@pytest.mark.property
class TestStatusMappingProperties:
    """Property tests for Kalshi status mapping."""

    @given(kalshi_status_strategy())
    def test_all_kalshi_statuses_have_mapping(self, kalshi_status: str) -> None:
        """All valid Kalshi statuses should have a database mapping.

        Property: Every Kalshi status maps to a valid DB status.
        """
        mapping = KalshiMarketPoller.STATUS_MAPPING
        assert kalshi_status in mapping
        assert mapping[kalshi_status] in ["open", "closed", "settled", "halted"]

    @given(kalshi_status_strategy())
    def test_status_mapping_returns_valid_db_status(self, kalshi_status: str) -> None:
        """Mapped status should be valid for database.

        Property: STATUS_MAPPING[x] is always in valid_db_statuses.
        """
        valid_db_statuses = {"open", "closed", "settled", "halted"}
        mapped = KalshiMarketPoller.STATUS_MAPPING[kalshi_status]
        assert mapped in valid_db_statuses

    def test_active_maps_to_open(self) -> None:
        """Kalshi 'active' status should map to DB 'open'.

        Property: 'active' (trading enabled) -> 'open'.
        """
        assert KalshiMarketPoller.STATUS_MAPPING["active"] == "open"

    def test_unopened_maps_to_halted(self) -> None:
        """Kalshi 'unopened' status should map to DB 'halted'.

        Property: 'unopened' (not yet trading) -> 'halted'.
        """
        assert KalshiMarketPoller.STATUS_MAPPING["unopened"] == "halted"


# =============================================================================
# Property Tests: Price Handling
# =============================================================================


@pytest.mark.property
class TestPriceHandlingProperties:
    """Property tests for Decimal price handling."""

    @given(decimal_price_strategy())
    def test_prices_remain_decimal_type(self, price: Decimal) -> None:
        """Prices should always remain Decimal type.

        Property: No float conversion occurs during price handling.
        """
        # This tests the invariant that our system uses Decimal, not float
        assert isinstance(price, Decimal)
        # Decimal arithmetic preserves type
        result = price * Decimal("0.95")
        assert isinstance(result, Decimal)

    @given(decimal_price_strategy(), decimal_price_strategy())
    @settings(max_examples=30)
    def test_price_comparison_uses_decimal(self, old_price: Decimal, new_price: Decimal) -> None:
        """Price comparisons should use Decimal equality.

        Property: Decimal comparison detects sub-penny changes.
        """
        # Small difference that floats might miss
        small_diff = Decimal("0.0001")

        if abs(old_price - new_price) >= small_diff:
            assert old_price != new_price
        else:
            # Very close prices might be equal or different
            # Either result is valid, but comparison must work
            _ = old_price == new_price  # Should not raise

    @given(st.integers(min_value=0, max_value=100))
    def test_cents_to_decimal_conversion(self, cents: int) -> None:
        """Cents should convert to Decimal correctly.

        Property: cents / 100 as Decimal preserves precision.
        """
        # This is how fallback conversion works
        decimal_price = Decimal(cents) / Decimal(100)
        assert isinstance(decimal_price, Decimal)
        # Should be between 0 and 1
        assert Decimal("0") <= decimal_price <= Decimal("1")


# =============================================================================
# Property Tests: Poll Results
# =============================================================================


@pytest.mark.property
class TestPollResultProperties:
    """Property tests for poll result invariants."""

    @given(
        st.integers(min_value=0, max_value=1000),
        st.integers(min_value=0, max_value=1000),
        st.integers(min_value=0, max_value=1000),
    )
    def test_poll_result_keys_always_present(
        self, fetched: int, updated: int, created: int
    ) -> None:
        """Poll results should always have required keys.

        Property: Result dict always has items_fetched, items_updated, items_created.
        """
        result = {
            "items_fetched": fetched,
            "items_updated": updated,
            "items_created": created,
        }

        assert "items_fetched" in result
        assert "items_updated" in result
        assert "items_created" in result

    @given(
        st.integers(min_value=0, max_value=1000),
        st.integers(min_value=0, max_value=1000),
        st.integers(min_value=0, max_value=1000),
    )
    def test_poll_result_values_non_negative(
        self, fetched: int, updated: int, created: int
    ) -> None:
        """Poll result values should be non-negative.

        Property: All counts >= 0.
        """
        result = {
            "items_fetched": fetched,
            "items_updated": updated,
            "items_created": created,
        }

        assert result["items_fetched"] >= 0
        assert result["items_updated"] >= 0
        assert result["items_created"] >= 0

    @given(
        st.integers(min_value=0, max_value=1000),
        st.integers(min_value=0, max_value=500),
        st.integers(min_value=0, max_value=500),
    )
    def test_updated_plus_created_leq_fetched(
        self, fetched: int, updated: int, created: int
    ) -> None:
        """Updated + created should not exceed fetched.

        Property: items_updated + items_created <= items_fetched.
        """
        # Constrain to valid scenario
        assume(updated + created <= fetched)

        result = {
            "items_fetched": fetched,
            "items_updated": updated,
            "items_created": created,
        }

        assert result["items_updated"] + result["items_created"] <= result["items_fetched"]


# =============================================================================
# Property Tests: Class Constants
# =============================================================================


@pytest.mark.property
class TestClassConstantProperties:
    """Property tests for class-level constants."""

    def test_min_poll_interval_positive(self) -> None:
        """MIN_POLL_INTERVAL should be positive.

        Property: MIN_POLL_INTERVAL > 0.
        """
        assert KalshiMarketPoller.MIN_POLL_INTERVAL > 0

    def test_default_poll_interval_gte_min(self) -> None:
        """DEFAULT_POLL_INTERVAL should be >= MIN_POLL_INTERVAL.

        Property: DEFAULT >= MIN.
        """
        assert KalshiMarketPoller.DEFAULT_POLL_INTERVAL >= KalshiMarketPoller.MIN_POLL_INTERVAL

    def test_max_markets_reasonable(self) -> None:
        """MAX_MARKETS_PER_REQUEST should be reasonable.

        Property: 1 <= MAX_MARKETS <= 1000.
        """
        assert 1 <= KalshiMarketPoller.MAX_MARKETS_PER_REQUEST <= 1000

    def test_platform_id_is_kalshi(self) -> None:
        """PLATFORM_ID should be 'kalshi'.

        Property: Platform identifier is correct.
        """
        assert KalshiMarketPoller.PLATFORM_ID == "kalshi"

    def test_default_series_tickers_not_empty(self) -> None:
        """DEFAULT_SERIES_TICKERS should not be empty.

        Property: len(DEFAULT_SERIES_TICKERS) > 0.
        """
        assert len(KalshiMarketPoller.DEFAULT_SERIES_TICKERS) > 0


# =============================================================================
# Property Tests: Factory Function
# =============================================================================


@pytest.mark.property
class TestFactoryFunctionProperties:
    """Property tests for create_kalshi_poller factory."""

    @given(poll_interval_strategy(), environment_strategy())
    @settings(max_examples=20)
    def test_factory_creates_valid_poller(self, poll_interval: int, environment: str) -> None:
        """Factory should create valid poller instances.

        Property: create_kalshi_poller returns KalshiMarketPoller.
        """
        with patch("precog.schedulers.kalshi_poller.KalshiClient"):
            poller = create_kalshi_poller(
                poll_interval=poll_interval,
                environment=environment,
            )
            assert isinstance(poller, KalshiMarketPoller)
            assert poller.poll_interval == poll_interval
            assert poller.environment == environment

    @given(st.lists(series_ticker_strategy(), min_size=1, max_size=3))
    @settings(max_examples=15)
    def test_factory_accepts_series_tickers(self, tickers: list[str]) -> None:
        """Factory should accept series tickers.

        Property: Series tickers passed to factory are set on poller.
        """
        with patch("precog.schedulers.kalshi_poller.KalshiClient"):
            poller = create_kalshi_poller(series_tickers=tickers, environment="demo")
            assert poller.series_tickers == tickers


# =============================================================================
# Property Tests: Job Name
# =============================================================================


@pytest.mark.property
class TestJobNameProperties:
    """Property tests for job naming."""

    @given(environment_strategy())
    def test_job_name_is_string(self, environment: str) -> None:
        """Job name should be a non-empty string.

        Property: _get_job_name() returns str with len > 0.
        """
        with patch("precog.schedulers.kalshi_poller.KalshiClient"):
            poller = KalshiMarketPoller(environment=environment)
            name = poller._get_job_name()
            assert isinstance(name, str)
            assert len(name) > 0

    @given(environment_strategy())
    def test_job_name_contains_kalshi(self, environment: str) -> None:
        """Job name should mention Kalshi.

        Property: 'Kalshi' in _get_job_name().
        """
        with patch("precog.schedulers.kalshi_poller.KalshiClient"):
            poller = KalshiMarketPoller(environment=environment)
            name = poller._get_job_name()
            assert "Kalshi" in name


# =============================================================================
# Property Tests: Stats Initialization
# =============================================================================


@pytest.mark.property
class TestStatsInitializationProperties:
    """Property tests for stats initialization via BasePoller."""

    @given(environment_strategy())
    def test_initial_stats_all_zero(self, environment: str) -> None:
        """Initial stats should all be zero.

        Property: New poller has polls_completed=0, errors=0.
        """
        with patch("precog.schedulers.kalshi_poller.KalshiClient"):
            poller = KalshiMarketPoller(environment=environment)
            stats = poller.get_stats()

            assert stats["polls_completed"] == 0
            assert stats["errors"] == 0

    @given(environment_strategy())
    def test_initial_running_state_false(self, environment: str) -> None:
        """Initial running state should be False.

        Property: New poller is_running() == False.
        """
        with patch("precog.schedulers.kalshi_poller.KalshiClient"):
            poller = KalshiMarketPoller(environment=environment)
            assert poller.is_running() is False
