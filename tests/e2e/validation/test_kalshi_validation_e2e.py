"""
End-to-End Tests for Kalshi Data Validation.

Tests complete validation workflows from raw data to final results.

Reference: TESTING_STRATEGY V3.2 - E2E tests for complete workflows
Related Requirements: REQ-DATA-002 (Data Quality Monitoring)

Usage:
    pytest tests/e2e/validation/test_kalshi_validation_e2e.py -v -m e2e
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
def complete_market_snapshot() -> dict[str, Any]:
    """Create a complete market snapshot like Kalshi API returns."""
    return {
        "ticker": "KXNFL-25DEC14-KC-WIN",
        "event_ticker": "KXNFL-25DEC14-KC",
        "market_type": "binary",
        "title": "Will the Chiefs win on December 14?",
        "subtitle": "Kansas City Chiefs vs Denver Broncos",
        "status": "open",
        "yes_bid_dollars": Decimal("0.65"),
        "yes_ask_dollars": Decimal("0.67"),
        "no_bid_dollars": Decimal("0.33"),
        "no_ask_dollars": Decimal("0.35"),
        "last_price": Decimal("0.66"),
        "volume": 25000,
        "volume_24h": 8500,
        "open_interest": 12000,
        "liquidity": Decimal("5000.00"),
        "open_time": "2025-12-01T00:00:00Z",
        "close_time": "2025-12-14T23:59:00Z",
        "expiration_time": "2025-12-15T04:00:00Z",
    }


@pytest.fixture
def complete_portfolio() -> dict[str, Any]:
    """Create a complete portfolio snapshot."""
    return {
        "balance": Decimal("5000.00"),
        "positions": [
            {
                "ticker": "KXNFL-25DEC14-KC-WIN",
                "position": 100,
                "market_exposure": Decimal("66.00"),
                "realized_pnl": Decimal("25.50"),
                "total_traded": Decimal("200.00"),
                "resting_orders_count": 1,
                "fees_paid": Decimal("1.00"),
            },
            {
                "ticker": "KXBTC-25DEC14-T100000",
                "position": -50,
                "market_exposure": Decimal("-25.00"),
                "realized_pnl": Decimal("-5.00"),
                "total_traded": Decimal("75.00"),
                "resting_orders_count": 0,
                "fees_paid": Decimal("0.38"),
            },
        ],
    }


# =============================================================================
# E2E Tests: Complete Market Validation Flow
# =============================================================================


@pytest.mark.e2e
class TestCompleteMarketValidationFlow:
    """E2E tests for complete market validation workflows."""

    def test_validate_complete_market_snapshot(
        self, validator: KalshiDataValidator, complete_market_snapshot: dict[str, Any]
    ) -> None:
        """Test validating a complete market snapshot end-to-end."""
        result = validator.validate_market_data(complete_market_snapshot)

        assert result.is_valid
        assert not result.has_errors
        assert result.entity_id == "KXNFL-25DEC14-KC-WIN"

    def test_validate_market_lifecycle(
        self, validator: KalshiDataValidator, complete_market_snapshot: dict[str, Any]
    ) -> None:
        """Test validating market through its lifecycle states."""
        market = complete_market_snapshot.copy()

        # Open state
        market["status"] = "open"
        result1 = validator.validate_market_data(market)
        assert result1.is_valid

        # Closed state
        market["status"] = "closed"
        result2 = validator.validate_market_data(market)
        assert result2.is_valid

        # Settled state
        market["status"] = "settled"
        result3 = validator.validate_market_data(market)
        assert result3.is_valid


# =============================================================================
# E2E Tests: Complete Portfolio Validation Flow
# =============================================================================


@pytest.mark.e2e
class TestCompletePortfolioValidationFlow:
    """E2E tests for complete portfolio validation workflows."""

    def test_validate_complete_portfolio(
        self, validator: KalshiDataValidator, complete_portfolio: dict[str, Any]
    ) -> None:
        """Test validating a complete portfolio end-to-end."""
        # Validate balance
        balance_result = validator.validate_balance(complete_portfolio["balance"])
        assert balance_result.is_valid

        # Validate all positions
        position_results = validator.validate_positions(complete_portfolio["positions"])
        assert all(r.is_valid for r in position_results)

    def test_validate_portfolio_with_mixed_positions(self, validator: KalshiDataValidator) -> None:
        """Test validating portfolio with long, short, and flat positions."""
        positions = [
            {"ticker": "LONG-POS", "position": 100, "resting_orders_count": 0},
            {"ticker": "SHORT-POS", "position": -50, "resting_orders_count": 0},
            {"ticker": "FLAT-POS", "position": 0, "resting_orders_count": 0},
        ]

        results = validator.validate_positions(positions)
        assert all(r.is_valid for r in results)


# =============================================================================
# E2E Tests: Trade Execution Validation Flow
# =============================================================================


@pytest.mark.e2e
class TestTradeExecutionValidationFlow:
    """E2E tests for trade execution validation workflows."""

    def test_validate_trade_sequence(self, validator: KalshiDataValidator) -> None:
        """Test validating a sequence of trades."""
        trades = [
            {
                "trade_id": "trade-001",
                "ticker": "KXNFL-25DEC14-KC-WIN",
                "side": "yes",
                "action": "buy",
                "count": 50,
                "yes_price": Decimal("0.65"),
                "no_price": Decimal("0.35"),
                "created_time": "2025-12-14T10:00:00Z",
            },
            {
                "trade_id": "trade-002",
                "ticker": "KXNFL-25DEC14-KC-WIN",
                "side": "yes",
                "action": "buy",
                "count": 50,
                "yes_price": Decimal("0.66"),
                "no_price": Decimal("0.34"),
                "created_time": "2025-12-14T10:05:00Z",
            },
            {
                "trade_id": "trade-003",
                "ticker": "KXNFL-25DEC14-KC-WIN",
                "side": "yes",
                "action": "sell",
                "count": 25,
                "yes_price": Decimal("0.68"),
                "no_price": Decimal("0.32"),
                "created_time": "2025-12-14T11:00:00Z",
            },
        ]

        results = validator.validate_fills(trades)
        assert len(results) == 3
        assert all(r.is_valid for r in results)


# =============================================================================
# E2E Tests: Settlement Flow
# =============================================================================


@pytest.mark.e2e
class TestSettlementValidationFlow:
    """E2E tests for settlement validation workflows."""

    def test_validate_settlement_batch(self, validator: KalshiDataValidator) -> None:
        """Test validating a batch of settlements."""
        settlements = [
            {
                "ticker": "KXNFL-25DEC07-KC-WIN",
                "market_result": "yes",
                "settlement_value": Decimal("1"),
                "settled_time": "2025-12-08T04:00:00Z",
            },
            {
                "ticker": "KXNFL-25DEC07-DEN-WIN",
                "market_result": "no",
                "settlement_value": Decimal("0"),
                "settled_time": "2025-12-08T04:00:00Z",
            },
        ]

        results = validator.validate_settlements(settlements)
        assert len(results) == 2
        assert all(r.is_valid for r in results)


# =============================================================================
# E2E Tests: Error Detection Flow
# =============================================================================


@pytest.mark.e2e
class TestErrorDetectionFlow:
    """E2E tests for error detection workflows."""

    def test_detect_invalid_market_data(self, validator: KalshiDataValidator) -> None:
        """Test detection of various invalid market data scenarios."""
        invalid_markets = [
            # Empty ticker
            {"ticker": "", "status": "open"},
            # Crossed market
            {
                "ticker": "CROSSED",
                "yes_bid_dollars": Decimal("0.60"),
                "yes_ask_dollars": Decimal("0.55"),
                "status": "open",
            },
            # Negative price
            {
                "ticker": "NEG-PRICE",
                "yes_bid_dollars": Decimal("-0.10"),
                "yes_ask_dollars": Decimal("0.50"),
                "status": "open",
            },
        ]

        for market in invalid_markets:
            # Deliberately pass potentially invalid types to test validation
            result = validator.validate_market_data(market)  # type: ignore[arg-type]
            assert result.has_errors, (
                f"Should detect error in {market.get('ticker', 'empty') if isinstance(market, dict) else 'empty'}"
            )

    def test_detect_invalid_balance(self, validator: KalshiDataValidator) -> None:
        """Test detection of invalid balance scenarios."""
        invalid_balances = [
            None,
            Decimal("-100.00"),
            0.5,  # Float instead of Decimal
        ]

        for balance in invalid_balances:
            # Testing invalid types - float is not allowed
            result = validator.validate_balance(balance)  # type: ignore[arg-type]
            assert result.has_errors


# =============================================================================
# E2E Tests: Complete Validation Summary
# =============================================================================


@pytest.mark.e2e
class TestCompleteValidationSummary:
    """E2E tests for complete validation summary generation."""

    def test_generate_comprehensive_summary(
        self, validator: KalshiDataValidator, complete_market_snapshot: dict[str, Any]
    ) -> None:
        """Test generating a comprehensive validation summary."""
        # Create a mix of valid and invalid markets
        markets = [
            complete_market_snapshot,
            complete_market_snapshot.copy(),
            {"ticker": "", "status": "open"},  # Invalid
        ]

        results = validator.validate_markets(markets)
        summary = validator.get_validation_summary(results)

        assert summary["total"] == 3
        assert summary["valid_count"] == 2
        assert "error_count" in summary
        assert "warning_count" in summary
