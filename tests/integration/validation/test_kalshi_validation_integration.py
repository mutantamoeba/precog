"""
Integration Tests for Kalshi Data Validation.

Tests validation with real Kalshi data structures and integration
with other system components.

Reference: TESTING_STRATEGY V3.2 - Integration tests for component interaction
Related Requirements: REQ-DATA-002 (Data Quality Monitoring)

Usage:
    pytest tests/integration/validation/test_kalshi_validation_integration.py -v -m integration
"""

from decimal import Decimal
from typing import Any

import pytest

from precog.validation.kalshi_validation import (
    KalshiDataValidator,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def validator() -> KalshiDataValidator:
    """Create a validator for testing."""
    return KalshiDataValidator()


@pytest.fixture
def active_market_data() -> dict[str, Any]:
    """Create realistic active market data."""
    return {
        "ticker": "KXBTC-25DEC14-T100000",
        "event_ticker": "KXBTC-25DEC14",
        "title": "Will Bitcoin be above $100,000 on December 14?",
        "status": "open",
        "yes_bid_dollars": Decimal("0.45"),
        "yes_ask_dollars": Decimal("0.48"),
        "no_bid_dollars": Decimal("0.52"),
        "no_ask_dollars": Decimal("0.55"),
        "volume": 15000,
        "open_interest": 8500,
        "last_price": Decimal("0.46"),
    }


@pytest.fixture
def position_data() -> dict[str, Any]:
    """Create realistic position data."""
    return {
        "ticker": "KXBTC-25DEC14-T100000",
        "position": 100,
        "market_exposure": Decimal("46.00"),
        "realized_pnl": Decimal("12.50"),
        "total_traded": Decimal("150.00"),
        "resting_orders_count": 2,
        "fees_paid": Decimal("0.75"),
    }


@pytest.fixture
def fill_data() -> dict[str, Any]:
    """Create realistic fill data."""
    return {
        "trade_id": "trade-abc123",
        "ticker": "KXBTC-25DEC14-T100000",
        "side": "yes",
        "action": "buy",
        "count": 50,
        "yes_price_fixed": Decimal("0.46"),
        "no_price_fixed": Decimal("0.54"),
        "created_time": "2025-12-14T12:30:00Z",
    }


@pytest.fixture
def settlement_data() -> dict[str, Any]:
    """Create realistic settlement data."""
    return {
        "ticker": "KXBTC-25DEC13-T99000",
        "market_result": "yes",
        "settlement_value": Decimal("1"),
        "settled_time": "2025-12-14T00:05:00Z",
    }


# =============================================================================
# Integration Tests: Multi-Market Validation
# =============================================================================


@pytest.mark.integration
class TestMultiMarketValidation:
    """Integration tests for validation across different market types."""

    def test_active_market_validation(
        self, validator: KalshiDataValidator, active_market_data: dict[str, Any]
    ) -> None:
        """Test full validation of active market data."""
        result = validator.validate_market_data(active_market_data)

        assert result.is_valid
        assert not result.has_errors
        assert result.entity_id == "KXBTC-25DEC14-T100000"

    def test_closed_market_validation(
        self, validator: KalshiDataValidator, active_market_data: dict[str, Any]
    ) -> None:
        """Test validation of closed market."""
        market = active_market_data.copy()
        market["status"] = "closed"

        result = validator.validate_market_data(market)
        assert result.is_valid

    def test_settled_market_validation(
        self, validator: KalshiDataValidator, active_market_data: dict[str, Any]
    ) -> None:
        """Test validation of settled market."""
        market = active_market_data.copy()
        market["status"] = "settled"

        result = validator.validate_market_data(market)
        assert result.is_valid


# =============================================================================
# Integration Tests: Position Tracking
# =============================================================================


@pytest.mark.integration
class TestPositionValidationIntegration:
    """Integration tests for position data validation."""

    def test_long_position_validation(
        self, validator: KalshiDataValidator, position_data: dict[str, Any]
    ) -> None:
        """Test validation of long position."""
        result = validator.validate_position_data(position_data)

        assert result.is_valid
        assert not result.has_errors

    def test_short_position_validation(
        self, validator: KalshiDataValidator, position_data: dict[str, Any]
    ) -> None:
        """Test validation of short (negative) position."""
        position = position_data.copy()
        position["position"] = -50

        result = validator.validate_position_data(position)
        assert result.is_valid

    def test_flat_position_validation(
        self, validator: KalshiDataValidator, position_data: dict[str, Any]
    ) -> None:
        """Test validation of flat (zero) position."""
        position = position_data.copy()
        position["position"] = 0

        result = validator.validate_position_data(position)
        assert result.is_valid


# =============================================================================
# Integration Tests: Fill Validation
# =============================================================================


@pytest.mark.integration
class TestFillValidationIntegration:
    """Integration tests for fill/trade data validation."""

    def test_buy_fill_validation(
        self, validator: KalshiDataValidator, fill_data: dict[str, Any]
    ) -> None:
        """Test validation of buy fill."""
        result = validator.validate_fill_data(fill_data)

        assert result.is_valid
        assert not result.has_errors

    def test_sell_fill_validation(
        self, validator: KalshiDataValidator, fill_data: dict[str, Any]
    ) -> None:
        """Test validation of sell fill."""
        fill = fill_data.copy()
        fill["action"] = "sell"

        result = validator.validate_fill_data(fill)
        assert result.is_valid

    def test_no_side_fill_validation(
        self, validator: KalshiDataValidator, fill_data: dict[str, Any]
    ) -> None:
        """Test validation of 'no' side fill."""
        fill = fill_data.copy()
        fill["side"] = "no"

        result = validator.validate_fill_data(fill)
        assert result.is_valid


# =============================================================================
# Integration Tests: Settlement Validation
# =============================================================================


@pytest.mark.integration
class TestSettlementValidationIntegration:
    """Integration tests for settlement data validation."""

    def test_yes_settlement_validation(
        self, validator: KalshiDataValidator, settlement_data: dict[str, Any]
    ) -> None:
        """Test validation of yes settlement."""
        result = validator.validate_settlement_data(settlement_data)

        assert result.is_valid
        assert not result.has_errors

    def test_no_settlement_validation(
        self, validator: KalshiDataValidator, settlement_data: dict[str, Any]
    ) -> None:
        """Test validation of no settlement."""
        settlement = settlement_data.copy()
        settlement["market_result"] = "no"
        settlement["settlement_value"] = Decimal("0")

        result = validator.validate_settlement_data(settlement)
        assert result.is_valid


# =============================================================================
# Integration Tests: Batch Validation
# =============================================================================


@pytest.mark.integration
class TestBatchValidationIntegration:
    """Integration tests for batch validation operations."""

    def test_validate_multiple_markets(
        self, validator: KalshiDataValidator, active_market_data: dict[str, Any]
    ) -> None:
        """Test batch validation of multiple markets."""
        markets = []
        for i in range(5):
            market = active_market_data.copy()
            market["ticker"] = f"MARKET-{i}"
            markets.append(market)

        results = validator.validate_markets(markets)

        assert len(results) == 5
        assert all(r.is_valid for r in results)

    def test_batch_with_mixed_validity(
        self, validator: KalshiDataValidator, active_market_data: dict[str, Any]
    ) -> None:
        """Test batch validation with some invalid markets."""
        markets = [
            active_market_data,
            {"ticker": "", "status": "open"},  # Invalid - empty ticker
            active_market_data.copy(),
        ]

        results = validator.validate_markets(markets)

        assert len(results) == 3
        assert results[0].is_valid
        assert not results[1].is_valid  # Empty ticker should fail
        assert results[2].is_valid


# =============================================================================
# Integration Tests: Anomaly Tracking Across Sessions
# =============================================================================


@pytest.mark.integration
class TestAnomalyTrackingIntegration:
    """Integration tests for anomaly tracking across validation sessions."""

    def test_anomaly_accumulation(self, validator: KalshiDataValidator) -> None:
        """Test that anomalies accumulate correctly."""
        invalid_market = {
            "ticker": "TEST-MARKET",
            "yes_bid_dollars": Decimal("-0.5"),  # Invalid
            "yes_ask_dollars": Decimal("0.5"),
            "status": "open",
        }

        for _ in range(3):
            validator.validate_market_data(invalid_market)

        count = validator.get_anomaly_count("TEST-MARKET")
        assert count >= 3

    def test_clear_anomalies(self, validator: KalshiDataValidator) -> None:
        """Test clearing anomaly counts."""
        invalid_market = {
            "ticker": "CLEAR-TEST",
            "yes_bid_dollars": Decimal("-0.5"),
            "yes_ask_dollars": Decimal("0.5"),
            "status": "open",
        }

        validator.validate_market_data(invalid_market)
        assert validator.get_anomaly_count("CLEAR-TEST") >= 1

        validator.clear_anomaly_counts()
        assert validator.get_anomaly_count("CLEAR-TEST") == 0


# =============================================================================
# Integration Tests: Validation Summary
# =============================================================================


@pytest.mark.integration
class TestValidationSummaryIntegration:
    """Integration tests for validation summary generation."""

    def test_summary_with_all_valid(
        self, validator: KalshiDataValidator, active_market_data: dict[str, Any]
    ) -> None:
        """Test summary when all validations pass."""
        markets = [active_market_data.copy() for _ in range(3)]
        for i, m in enumerate(markets):
            m["ticker"] = f"VALID-{i}"

        results = validator.validate_markets(markets)
        summary = validator.get_validation_summary(results)

        assert summary["total"] == 3
        assert summary["valid_count"] == 3
        assert summary["error_count"] == 0

    def test_summary_with_errors(self, validator: KalshiDataValidator) -> None:
        """Test summary with some errors."""
        markets = [
            {
                "ticker": "GOOD",
                "yes_bid_dollars": Decimal("0.4"),
                "yes_ask_dollars": Decimal("0.5"),
                "status": "open",
            },
            {"ticker": "", "status": "open"},  # Invalid
        ]

        results = validator.validate_markets(markets)
        summary = validator.get_validation_summary(results)

        assert summary["total"] == 2
        assert summary["valid_count"] == 1
        assert summary["error_count"] >= 1
