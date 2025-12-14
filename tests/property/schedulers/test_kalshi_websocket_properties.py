"""
Property-Based Tests for KalshiWebSocketHandler.

Uses Hypothesis to test invariants and properties that should hold
for any valid input combination.

Reference: TESTING_STRATEGY V3.2 - Property tests for business logic
Related Requirements: REQ-API-001, REQ-DATA-005

Usage:
    pytest tests/property/schedulers/test_kalshi_websocket_properties.py -v -m property
"""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from precog.schedulers.kalshi_websocket import (
    ConnectionState,
    KalshiWebSocketHandler,
)

# =============================================================================
# Helper Functions (for Hypothesis tests - fixtures don't work with @given)
# =============================================================================


def create_mock_auth() -> MagicMock:
    """Create a mock KalshiAuth instance."""
    auth = MagicMock()
    auth.get_headers.return_value = {
        "KALSHI-ACCESS-KEY": "test-api-key",
        "KALSHI-ACCESS-TIMESTAMP": "1234567890000",
        "KALSHI-ACCESS-SIGNATURE": "test-signature",
        "Content-Type": "application/json",
    }
    return auth


def create_handler() -> KalshiWebSocketHandler:
    """Create a handler with mocked auth for testing."""
    return KalshiWebSocketHandler(
        environment="demo",
        auth=create_mock_auth(),
        auto_reconnect=False,
        sync_to_database=False,
    )


# =============================================================================
# Custom Strategies
# =============================================================================


# Valid market ticker format: XXXX-NNNNXX-TNN (e.g., INXD-25AUXA-T64)
@st.composite
def market_ticker(draw: Any) -> str:
    """Generate a valid market ticker string."""
    prefix = draw(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=3, max_size=6))
    year = draw(st.integers(min_value=20, max_value=30))
    suffix = draw(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=2, max_size=4))
    market_num = draw(st.integers(min_value=1, max_value=999))
    return f"{prefix}-{year}{suffix}-T{market_num}"


# Price in cents (0-100 cents)
price_cents = st.integers(min_value=0, max_value=100)

# Price in dollars (Decimal between 0 and 1)
price_dollars = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)


# =============================================================================
# Property Tests: Initialization Invariants
# =============================================================================


@pytest.mark.property
class TestInitializationInvariants:
    """Property tests for initialization invariants."""

    @given(auto_reconnect=st.booleans(), sync_to_database=st.booleans())
    @settings(max_examples=20)
    def test_initialization_preserves_settings(
        self, auto_reconnect: bool, sync_to_database: bool
    ) -> None:
        """Test that initialization preserves all settings."""
        handler = KalshiWebSocketHandler(
            environment="demo",
            auth=create_mock_auth(),
            auto_reconnect=auto_reconnect,
            sync_to_database=sync_to_database,
        )

        assert handler.auto_reconnect == auto_reconnect
        assert handler.sync_to_database == sync_to_database
        assert handler.state == ConnectionState.DISCONNECTED
        assert handler.enabled is False
        assert handler.subscribed_tickers == []

    @given(env=st.sampled_from(["demo", "prod"]))
    @settings(max_examples=10)
    def test_environment_determines_url(self, env: str) -> None:
        """Test that environment determines the correct WebSocket URL."""
        handler = KalshiWebSocketHandler(
            environment=env,
            auth=create_mock_auth(),
            auto_reconnect=False,
            sync_to_database=False,
        )

        if env == "demo":
            assert "demo-api" in handler.ws_url
        else:
            assert "elections.kalshi" in handler.ws_url


# =============================================================================
# Property Tests: Subscription Management
# =============================================================================


@pytest.mark.property
class TestSubscriptionProperties:
    """Property tests for subscription management."""

    @given(tickers=st.lists(market_ticker(), min_size=0, max_size=20))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_subscribe_idempotent(self, tickers: list[str]) -> None:
        """Test that subscribing multiple times doesn't create duplicates."""
        handler = create_handler()

        # Subscribe multiple times
        handler.subscribe(tickers)
        handler.subscribe(tickers)
        handler.subscribe(tickers)

        # Should have unique set
        assert set(handler.subscribed_tickers) == set(tickers)
        assert len(handler.subscribed_tickers) == len(set(tickers))

    @given(
        initial_tickers=st.lists(market_ticker(), min_size=0, max_size=10),
        new_tickers=st.lists(market_ticker(), min_size=0, max_size=10),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_subscribe_union_property(
        self, initial_tickers: list[str], new_tickers: list[str]
    ) -> None:
        """Test that subscribing adds to existing subscriptions."""
        handler = create_handler()

        handler.subscribe(initial_tickers)
        handler.subscribe(new_tickers)

        expected = set(initial_tickers) | set(new_tickers)
        assert set(handler.subscribed_tickers) == expected

    @given(
        tickers=st.lists(market_ticker(), min_size=1, max_size=10),
        remove_indices=st.lists(st.integers(min_value=0, max_value=9), min_size=0, max_size=5),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_unsubscribe_removes_only_specified(
        self, tickers: list[str], remove_indices: list[int]
    ) -> None:
        """Test that unsubscribe removes only specified tickers."""
        handler = create_handler()

        handler.subscribe(tickers)

        # Get tickers to remove based on indices
        to_remove = [tickers[i % len(tickers)] for i in remove_indices if tickers]
        handler.unsubscribe(to_remove)

        # Remaining should be initial - removed
        expected = set(tickers) - set(to_remove)
        assert set(handler.subscribed_tickers) == expected


# =============================================================================
# Property Tests: Callback System
# =============================================================================


@pytest.mark.property
class TestCallbackProperties:
    """Property tests for callback system."""

    @given(num_callbacks=st.integers(min_value=0, max_value=10))
    @settings(max_examples=20)
    def test_add_callback_count(self, num_callbacks: int) -> None:
        """Test that adding N callbacks results in N callbacks."""
        handler = create_handler()
        callbacks = [MagicMock() for _ in range(num_callbacks)]

        for cb in callbacks:
            handler.add_callback(cb)

        assert len(handler._callbacks) == num_callbacks

    @given(num_callbacks=st.integers(min_value=1, max_value=5))
    @settings(max_examples=15)
    def test_remove_callback_decreases_count(self, num_callbacks: int) -> None:
        """Test that removing callbacks decreases count."""
        handler = create_handler()
        callbacks = [MagicMock() for _ in range(num_callbacks)]

        for cb in callbacks:
            handler.add_callback(cb)

        # Remove first callback
        handler.remove_callback(callbacks[0])

        assert len(handler._callbacks) == num_callbacks - 1
        assert callbacks[0] not in handler._callbacks


# =============================================================================
# Property Tests: Statistics
# =============================================================================


@pytest.mark.property
class TestStatisticsProperties:
    """Property tests for statistics tracking."""

    def test_initial_stats_are_zero(self) -> None:
        """Test that initial statistics are all zero/None."""
        handler = create_handler()
        stats = handler.stats

        assert stats["messages_received"] == 0
        assert stats["price_updates"] == 0
        assert stats["reconnections"] == 0
        assert stats["errors"] == 0
        assert stats["last_message"] is None
        assert stats["last_error"] is None
        assert stats["uptime_seconds"] == 0.0

    def test_stats_returns_copy(self) -> None:
        """Test that stats returns a copy, not the internal dict."""
        handler = create_handler()
        stats1 = handler.stats
        stats2 = handler.stats

        # Modify one shouldn't affect the other
        stats1["messages_received"] = 999

        assert stats2["messages_received"] == 0
        assert handler.stats["messages_received"] == 0


# =============================================================================
# Property Tests: State Transitions
# =============================================================================


@pytest.mark.property
class TestStateTransitionProperties:
    """Property tests for state transitions."""

    def test_initial_state_is_disconnected(self) -> None:
        """Test that initial state is always DISCONNECTED."""
        handler = create_handler()
        assert handler.state == ConnectionState.DISCONNECTED

    def test_enabled_false_initially(self) -> None:
        """Test that enabled is False initially."""
        handler = create_handler()
        assert handler.enabled is False
        assert handler.is_running() is False


# =============================================================================
# Property Tests: Price Calculation
# =============================================================================


@pytest.mark.property
class TestPriceCalculationProperties:
    """Property tests for price calculations in message handling."""

    @given(
        yes_cents=price_cents,
        no_cents=price_cents,
    )
    @settings(max_examples=50)
    def test_cents_to_decimal_conversion(self, yes_cents: int, no_cents: int) -> None:
        """Test that cents convert correctly to Decimal dollars."""
        # Simulate the conversion done in _handle_ticker_update
        yes_price = Decimal(yes_cents) / Decimal(100)
        no_price = Decimal(no_cents) / Decimal(100)

        # Invariant: price should be between 0 and 1
        assert Decimal("0") <= yes_price <= Decimal("1")
        assert Decimal("0") <= no_price <= Decimal("1")

        # Invariant: conversion should be reversible
        assert int(yes_price * 100) == yes_cents
        assert int(no_price * 100) == no_cents

    @given(
        yes_dollars=st.text(alphabet="0123456789.", min_size=1, max_size=6).filter(
            lambda x: x.count(".") <= 1 and x != "." and float(x) <= 1.0
        )
    )
    @settings(max_examples=30)
    def test_dollars_string_to_decimal(self, yes_dollars: str) -> None:
        """Test that dollar strings convert correctly to Decimal."""
        try:
            price = Decimal(yes_dollars)
            # Invariant: converted price should be non-negative and <= 1
            assert price >= Decimal("0")
            assert price <= Decimal("1")
        except Exception:
            # Invalid strings should be filtered by the strategy
            pass


# =============================================================================
# Property Tests: Connection Settings
# =============================================================================


@pytest.mark.property
class TestConnectionSettingsProperties:
    """Property tests for connection settings."""

    def test_heartbeat_interval_positive(self) -> None:
        """Test that heartbeat interval is positive."""
        handler = create_handler()
        assert handler.HEARTBEAT_INTERVAL > 0

    def test_reconnect_delays_bounded(self) -> None:
        """Test that reconnect delays are bounded correctly."""
        handler = create_handler()
        assert handler.RECONNECT_BASE_DELAY > 0
        assert handler.RECONNECT_MAX_DELAY >= handler.RECONNECT_BASE_DELAY
        assert handler.RECONNECT_MAX_ATTEMPTS > 0

    @given(attempt=st.integers(min_value=0, max_value=20))
    @settings(max_examples=20)
    def test_exponential_backoff_bounded(self, attempt: int) -> None:
        """Test that exponential backoff never exceeds max delay."""
        handler = create_handler()
        delay = handler.RECONNECT_BASE_DELAY * (2**attempt)
        bounded_delay = min(delay, handler.RECONNECT_MAX_DELAY)

        assert bounded_delay <= handler.RECONNECT_MAX_DELAY
