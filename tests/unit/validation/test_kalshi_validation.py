"""
Unit tests for Kalshi Data Validation module.

Tests comprehensive validation of Kalshi API response data including:
- Price validation (0-1 range, Decimal type)
- Spread validation (bid/ask relationship)
- Market data validation (prices, volume, open interest)
- Position data validation (quantity, P&L, fees)
- Fill data validation (trade ID, prices, side/action)
- Settlement data validation (settlement value 0/1)
- Balance validation (non-negative, Decimal type)

Reference: Issue #222 (Kalshi Validation Module)
Related: src/precog/validation/kalshi_validation.py
"""

from decimal import Decimal

import pytest

from precog.validation.kalshi_validation import (
    KalshiDataValidator,
    ValidationIssue,
    ValidationLevel,
    ValidationResult,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def validator() -> KalshiDataValidator:
    """Create a fresh validator for each test."""
    return KalshiDataValidator()


@pytest.fixture
def valid_market_data() -> dict:
    """Create valid Kalshi market data for testing."""
    return {
        "ticker": "KXNFLGAME-25DEC25-CHI-GB",
        "status": "open",
        "yes_bid_dollars": Decimal("0.45"),
        "yes_ask_dollars": Decimal("0.47"),
        "no_bid_dollars": Decimal("0.53"),
        "no_ask_dollars": Decimal("0.55"),
        "volume": 1000,
        "open_interest": 500,
    }


@pytest.fixture
def valid_position_data() -> dict:
    """Create valid Kalshi position data for testing."""
    return {
        "ticker": "KXNFLGAME-25DEC25-CHI-GB",
        "position": 100,
        "user_average_price": Decimal("0.45"),
        "realized_pnl": Decimal("25.50"),
        "total_traded": 200,
        "fees": Decimal("2.00"),
    }


@pytest.fixture
def valid_fill_data() -> dict:
    """Create valid Kalshi fill data for testing."""
    return {
        "trade_id": "abc123",
        "ticker": "KXNFLGAME-25DEC25-CHI-GB",
        "count": 10,
        "yes_price_fixed": Decimal("0.45"),
        "side": "yes",
        "action": "buy",
    }


@pytest.fixture
def valid_settlement_data() -> dict:
    """Create valid Kalshi settlement data for testing."""
    return {
        "ticker": "KXNFLGAME-25DEC25-CHI-GB",
        "settlement_value": Decimal("1"),
        "revenue": Decimal("50.00"),
        "settled_time": "2025-01-01T12:00:00Z",
    }


# =============================================================================
# ValidationResult Tests
# =============================================================================


class TestValidationResult:
    """Tests for ValidationResult class."""

    def test_empty_result_is_valid(self) -> None:
        """Empty result should be valid."""
        result = ValidationResult()
        assert result.is_valid
        assert not result.has_errors
        assert not result.has_warnings

    def test_add_error_makes_invalid(self) -> None:
        """Adding an error should make result invalid."""
        result = ValidationResult(entity_id="test", entity_type="market")
        result.add_error("field", "error message")
        assert not result.is_valid
        assert result.has_errors
        assert len(result.errors) == 1

    def test_add_warning_stays_valid(self) -> None:
        """Adding a warning should not make result invalid."""
        result = ValidationResult(entity_id="test", entity_type="market")
        result.add_warning("field", "warning message")
        assert result.is_valid
        assert result.has_warnings
        assert len(result.warnings) == 1

    def test_add_info_stays_valid(self) -> None:
        """Adding info should not affect validity."""
        result = ValidationResult(entity_id="test", entity_type="market")
        result.add_info("field", "info message")
        assert result.is_valid
        assert not result.has_errors
        assert not result.has_warnings

    def test_error_with_value_and_expected(self) -> None:
        """Errors can include value and expected."""
        result = ValidationResult()
        result.add_error("price", "Price out of range", value=1.5, expected="0-1")
        assert len(result.errors) == 1
        assert result.errors[0].value == 1.5
        assert result.errors[0].expected == "0-1"


class TestValidationIssue:
    """Tests for ValidationIssue class."""

    def test_str_representation(self) -> None:
        """Test string representation of issue."""
        issue = ValidationIssue(
            level=ValidationLevel.ERROR,
            field="price",
            message="Invalid price",
            value=Decimal("1.5"),
            expected="0-1",
        )
        str_repr = str(issue)
        assert "ERROR" in str_repr
        assert "price" in str_repr
        assert "Invalid price" in str_repr

    def test_str_without_value_expected(self) -> None:
        """Test string representation without value/expected."""
        issue = ValidationIssue(
            level=ValidationLevel.WARNING,
            field="spread",
            message="Wide spread",
        )
        str_repr = str(issue)
        assert "WARNING" in str_repr
        assert "spread" in str_repr


# =============================================================================
# Price Validation Tests
# =============================================================================


class TestPriceValidation:
    """Tests for price validation logic."""

    def test_valid_price_at_zero(self, validator: KalshiDataValidator) -> None:
        """Price of 0 is valid."""
        result = ValidationResult()
        is_valid = validator.validate_price(Decimal("0"), "test_price", result)
        assert is_valid
        assert result.is_valid

    def test_valid_price_at_one(self, validator: KalshiDataValidator) -> None:
        """Price of 1 is valid."""
        result = ValidationResult()
        is_valid = validator.validate_price(Decimal("1"), "test_price", result)
        assert is_valid
        assert result.is_valid

    def test_valid_price_mid_range(self, validator: KalshiDataValidator) -> None:
        """Price of 0.50 is valid."""
        result = ValidationResult()
        is_valid = validator.validate_price(Decimal("0.50"), "test_price", result)
        assert is_valid
        assert result.is_valid

    def test_invalid_price_negative(self, validator: KalshiDataValidator) -> None:
        """Negative price is invalid."""
        result = ValidationResult()
        is_valid = validator.validate_price(Decimal("-0.1"), "test_price", result)
        assert not is_valid
        assert result.has_errors

    def test_invalid_price_above_one(self, validator: KalshiDataValidator) -> None:
        """Price above 1 is invalid."""
        result = ValidationResult()
        is_valid = validator.validate_price(Decimal("1.1"), "test_price", result)
        assert not is_valid
        assert result.has_errors

    def test_none_price_allowed_by_default(self, validator: KalshiDataValidator) -> None:
        """None price is allowed by default."""
        result = ValidationResult()
        is_valid = validator.validate_price(None, "test_price", result)
        assert is_valid
        assert result.is_valid

    def test_none_price_rejected_when_required(self, validator: KalshiDataValidator) -> None:
        """None price is rejected when allow_none=False."""
        result = ValidationResult()
        is_valid = validator.validate_price(None, "test_price", result, allow_none=False)
        assert not is_valid
        assert result.has_errors

    def test_float_price_rejected(self, validator: KalshiDataValidator) -> None:
        """Float price (non-Decimal) is rejected."""
        result = ValidationResult()
        is_valid = validator.validate_price(0.5, "test_price", result)  # type: ignore
        assert not is_valid
        assert result.has_errors
        assert "Decimal" in result.errors[0].message


# =============================================================================
# Spread Validation Tests
# =============================================================================


class TestSpreadValidation:
    """Tests for bid/ask spread validation."""

    def test_valid_spread(self, validator: KalshiDataValidator) -> None:
        """Normal spread (bid < ask) is valid."""
        result = ValidationResult()
        validator.validate_spread(Decimal("0.45"), Decimal("0.47"), result)
        assert result.is_valid

    def test_crossed_market_error(self, validator: KalshiDataValidator) -> None:
        """Crossed market (bid > ask) generates error."""
        result = ValidationResult()
        validator.validate_spread(Decimal("0.50"), Decimal("0.45"), result)
        assert result.has_errors
        assert "Crossed market" in result.errors[0].message

    def test_wide_spread_warning(self, validator: KalshiDataValidator) -> None:
        """Wide spread (>10 cents) generates warning."""
        result = ValidationResult()
        validator.validate_spread(Decimal("0.35"), Decimal("0.50"), result)
        assert result.has_warnings
        assert "Wide" in result.warnings[0].message

    def test_very_wide_spread_warning(self, validator: KalshiDataValidator) -> None:
        """Very wide spread (>20 cents) generates warning."""
        result = ValidationResult()
        validator.validate_spread(Decimal("0.30"), Decimal("0.55"), result)
        assert result.has_warnings
        assert "Very wide" in result.warnings[0].message

    def test_none_bid_skipped(self, validator: KalshiDataValidator) -> None:
        """None bid skips spread validation."""
        result = ValidationResult()
        validator.validate_spread(None, Decimal("0.50"), result)
        assert result.is_valid

    def test_none_ask_skipped(self, validator: KalshiDataValidator) -> None:
        """None ask skips spread validation."""
        result = ValidationResult()
        validator.validate_spread(Decimal("0.45"), None, result)
        assert result.is_valid


# =============================================================================
# Market Data Validation Tests
# =============================================================================


class TestMarketDataValidation:
    """Tests for market data validation."""

    def test_valid_market_data(
        self, validator: KalshiDataValidator, valid_market_data: dict
    ) -> None:
        """Valid market data passes validation."""
        result = validator.validate_market_data(valid_market_data)
        assert result.is_valid
        assert result.entity_id == valid_market_data["ticker"]
        assert result.entity_type == "market"

    def test_missing_ticker_error(self, validator: KalshiDataValidator) -> None:
        """Missing ticker generates error."""
        market = {"status": "open"}
        result = validator.validate_market_data(market)
        assert result.has_errors
        assert any("ticker" in e.field for e in result.errors)

    def test_empty_ticker_error(self, validator: KalshiDataValidator) -> None:
        """Empty ticker generates error."""
        market = {"ticker": "", "status": "open"}
        result = validator.validate_market_data(market)
        assert result.has_errors

    def test_unknown_status_warning(self, validator: KalshiDataValidator) -> None:
        """Unknown status generates warning."""
        market = {"ticker": "TEST", "status": "unknown_status"}
        result = validator.validate_market_data(market)
        assert result.has_warnings

    def test_valid_statuses_accepted(self, validator: KalshiDataValidator) -> None:
        """Valid statuses (open, closed, settled) are accepted."""
        for status in ["open", "closed", "settled"]:
            market = {"ticker": "TEST", "status": status}
            result = validator.validate_market_data(market)
            # Should not have status-related warnings
            assert not any("status" in w.field for w in result.warnings)

    def test_negative_volume_error(self, validator: KalshiDataValidator) -> None:
        """Negative volume generates error."""
        market = {"ticker": "TEST", "volume": -100}
        result = validator.validate_market_data(market)
        assert result.has_errors
        assert any("volume" in e.field for e in result.errors)

    def test_high_volume_warning(self, validator: KalshiDataValidator) -> None:
        """Unusually high volume generates warning."""
        market = {"ticker": "TEST", "volume": 200000}
        result = validator.validate_market_data(market)
        assert result.has_warnings
        assert any("volume" in w.field for w in result.warnings)

    def test_negative_open_interest_error(self, validator: KalshiDataValidator) -> None:
        """Negative open interest generates error."""
        market = {"ticker": "TEST", "open_interest": -50}
        result = validator.validate_market_data(market)
        assert result.has_errors

    def test_arbitrage_warning_low_combined_ask(self, validator: KalshiDataValidator) -> None:
        """Combined ask < $0.98 generates arbitrage warning."""
        market = {
            "ticker": "TEST",
            "yes_ask_dollars": Decimal("0.45"),
            "no_ask_dollars": Decimal("0.50"),  # Combined = 0.95
        }
        result = validator.validate_market_data(market)
        assert result.has_warnings
        assert any("arbitrage" in w.field for w in result.warnings)


# =============================================================================
# Position Data Validation Tests
# =============================================================================


class TestPositionDataValidation:
    """Tests for position data validation."""

    def test_valid_position_data(
        self, validator: KalshiDataValidator, valid_position_data: dict
    ) -> None:
        """Valid position data passes validation."""
        result = validator.validate_position_data(valid_position_data)
        assert result.is_valid
        assert result.entity_type == "position"

    def test_missing_ticker_error(self, validator: KalshiDataValidator) -> None:
        """Missing ticker generates error."""
        position = {"position": 100}
        result = validator.validate_position_data(position)
        assert result.has_errors

    def test_non_integer_position_warning(self, validator: KalshiDataValidator) -> None:
        """Non-integer position generates warning."""
        position = {"ticker": "TEST", "position": 100.5}
        result = validator.validate_position_data(position)
        assert result.has_warnings

    def test_negative_position_allowed(self, validator: KalshiDataValidator) -> None:
        """Negative position (short) is allowed."""
        position = {"ticker": "TEST", "position": -50}
        result = validator.validate_position_data(position)
        # Negative positions are valid (shorts)
        assert not any(e.field == "position" for e in result.errors)

    def test_invalid_avg_price_error(self, validator: KalshiDataValidator) -> None:
        """Invalid average price generates error."""
        position = {"ticker": "TEST", "user_average_price": Decimal("1.5")}
        result = validator.validate_position_data(position)
        assert result.has_errors

    def test_negative_total_traded_error(self, validator: KalshiDataValidator) -> None:
        """Negative total traded generates error."""
        position = {"ticker": "TEST", "total_traded": -100}
        result = validator.validate_position_data(position)
        assert result.has_errors

    def test_negative_fees_error(self, validator: KalshiDataValidator) -> None:
        """Negative fees generates error."""
        position = {"ticker": "TEST", "fees": Decimal("-5.00")}
        result = validator.validate_position_data(position)
        assert result.has_errors


# =============================================================================
# Fill Data Validation Tests
# =============================================================================


class TestFillDataValidation:
    """Tests for fill data validation."""

    def test_valid_fill_data(self, validator: KalshiDataValidator, valid_fill_data: dict) -> None:
        """Valid fill data passes validation."""
        result = validator.validate_fill_data(valid_fill_data)
        assert result.is_valid
        assert result.entity_type == "fill"

    def test_missing_trade_id_error(self, validator: KalshiDataValidator) -> None:
        """Missing trade ID generates error."""
        fill = {"ticker": "TEST", "count": 10}
        result = validator.validate_fill_data(fill)
        assert result.has_errors

    def test_missing_ticker_error(self, validator: KalshiDataValidator) -> None:
        """Missing ticker generates error."""
        fill = {"trade_id": "abc123", "count": 10}
        result = validator.validate_fill_data(fill)
        assert result.has_errors

    def test_zero_count_error(self, validator: KalshiDataValidator) -> None:
        """Zero count generates error."""
        fill = {"trade_id": "abc", "ticker": "TEST", "count": 0}
        result = validator.validate_fill_data(fill)
        assert result.has_errors

    def test_negative_count_error(self, validator: KalshiDataValidator) -> None:
        """Negative count generates error."""
        fill = {"trade_id": "abc", "ticker": "TEST", "count": -5}
        result = validator.validate_fill_data(fill)
        assert result.has_errors

    def test_unknown_side_warning(self, validator: KalshiDataValidator) -> None:
        """Unknown side generates warning."""
        fill = {"trade_id": "abc", "ticker": "TEST", "side": "unknown"}
        result = validator.validate_fill_data(fill)
        assert result.has_warnings

    def test_valid_sides_accepted(self, validator: KalshiDataValidator) -> None:
        """Valid sides (yes, no) are accepted."""
        for side in ["yes", "no"]:
            fill = {"trade_id": "abc", "ticker": "TEST", "side": side}
            result = validator.validate_fill_data(fill)
            assert not any("side" in w.field for w in result.warnings)

    def test_unknown_action_warning(self, validator: KalshiDataValidator) -> None:
        """Unknown action generates warning."""
        fill = {"trade_id": "abc", "ticker": "TEST", "action": "hold"}
        result = validator.validate_fill_data(fill)
        assert result.has_warnings

    def test_valid_actions_accepted(self, validator: KalshiDataValidator) -> None:
        """Valid actions (buy, sell) are accepted."""
        for action in ["buy", "sell"]:
            fill = {"trade_id": "abc", "ticker": "TEST", "action": action}
            result = validator.validate_fill_data(fill)
            assert not any("action" in w.field for w in result.warnings)


# =============================================================================
# Settlement Data Validation Tests
# =============================================================================


class TestSettlementDataValidation:
    """Tests for settlement data validation."""

    def test_valid_settlement_data(
        self, validator: KalshiDataValidator, valid_settlement_data: dict
    ) -> None:
        """Valid settlement data passes validation."""
        result = validator.validate_settlement_data(valid_settlement_data)
        assert result.is_valid
        assert result.entity_type == "settlement"

    def test_missing_ticker_error(self, validator: KalshiDataValidator) -> None:
        """Missing ticker generates error."""
        settlement = {"settlement_value": Decimal("1")}
        result = validator.validate_settlement_data(settlement)
        assert result.has_errors

    def test_settlement_value_zero_valid(self, validator: KalshiDataValidator) -> None:
        """Settlement value of 0 is valid."""
        settlement = {"ticker": "TEST", "settlement_value": Decimal("0")}
        result = validator.validate_settlement_data(settlement)
        assert not any(e.field == "settlement_value" for e in result.errors)

    def test_settlement_value_one_valid(self, validator: KalshiDataValidator) -> None:
        """Settlement value of 1 is valid."""
        settlement = {"ticker": "TEST", "settlement_value": Decimal("1")}
        result = validator.validate_settlement_data(settlement)
        assert not any(e.field == "settlement_value" for e in result.errors)

    def test_invalid_settlement_value_error(self, validator: KalshiDataValidator) -> None:
        """Settlement value other than 0/1 generates error."""
        settlement = {"ticker": "TEST", "settlement_value": Decimal("0.5")}
        result = validator.validate_settlement_data(settlement)
        assert result.has_errors
        assert any("settlement_value" in e.field for e in result.errors)

    def test_missing_settled_time_warning(self, validator: KalshiDataValidator) -> None:
        """Missing settled time generates warning."""
        settlement = {"ticker": "TEST", "settlement_value": Decimal("1")}
        result = validator.validate_settlement_data(settlement)
        assert result.has_warnings


# =============================================================================
# Balance Validation Tests
# =============================================================================


class TestBalanceValidation:
    """Tests for balance validation."""

    def test_valid_balance(self, validator: KalshiDataValidator) -> None:
        """Valid balance passes validation."""
        result = validator.validate_balance(Decimal("1234.56"))
        assert result.is_valid
        assert result.entity_type == "balance"

    def test_zero_balance_valid(self, validator: KalshiDataValidator) -> None:
        """Zero balance is valid."""
        result = validator.validate_balance(Decimal("0"))
        assert result.is_valid

    def test_none_balance_error(self, validator: KalshiDataValidator) -> None:
        """None balance generates error."""
        result = validator.validate_balance(None)
        assert result.has_errors

    def test_negative_balance_error(self, validator: KalshiDataValidator) -> None:
        """Negative balance generates error."""
        result = validator.validate_balance(Decimal("-100"))
        assert result.has_errors

    def test_float_balance_error(self, validator: KalshiDataValidator) -> None:
        """Float balance (non-Decimal) generates error."""
        result = validator.validate_balance(1234.56)  # type: ignore
        assert result.has_errors
        assert "Decimal" in result.errors[0].message

    def test_high_balance_warning(self, validator: KalshiDataValidator) -> None:
        """Unusually high balance generates warning."""
        result = validator.validate_balance(Decimal("50000000"))  # $50M
        assert result.has_warnings


# =============================================================================
# Batch Validation Tests
# =============================================================================


class TestBatchValidation:
    """Tests for batch validation methods."""

    def test_validate_markets_batch(
        self, validator: KalshiDataValidator, valid_market_data: dict
    ) -> None:
        """Batch market validation returns list of results."""
        markets = [valid_market_data, valid_market_data.copy()]
        results = validator.validate_markets(markets)
        assert len(results) == 2
        assert all(r.is_valid for r in results)

    def test_validate_positions_batch(
        self, validator: KalshiDataValidator, valid_position_data: dict
    ) -> None:
        """Batch position validation returns list of results."""
        positions = [valid_position_data, valid_position_data.copy()]
        results = validator.validate_positions(positions)
        assert len(results) == 2
        assert all(r.is_valid for r in results)

    def test_validate_fills_batch(
        self, validator: KalshiDataValidator, valid_fill_data: dict
    ) -> None:
        """Batch fill validation returns list of results."""
        fills = [valid_fill_data, valid_fill_data.copy()]
        results = validator.validate_fills(fills)
        assert len(results) == 2
        assert all(r.is_valid for r in results)

    def test_validate_settlements_batch(
        self, validator: KalshiDataValidator, valid_settlement_data: dict
    ) -> None:
        """Batch settlement validation returns list of results."""
        settlements = [valid_settlement_data, valid_settlement_data.copy()]
        results = validator.validate_settlements(settlements)
        assert len(results) == 2
        assert all(r.is_valid for r in results)


# =============================================================================
# Anomaly Tracking Tests
# =============================================================================


class TestAnomalyTracking:
    """Tests for anomaly tracking."""

    def test_anomaly_count_starts_zero(self, validator: KalshiDataValidator) -> None:
        """Anomaly count starts at zero."""
        assert validator.get_anomaly_count("unknown_entity") == 0

    def test_anomaly_count_increments(self, validator: KalshiDataValidator) -> None:
        """Anomaly count increments on validation issues."""
        market = {"ticker": "TEST", "volume": -100}  # Error
        validator.validate_market_data(market)
        assert validator.get_anomaly_count("TEST") > 0

    def test_get_all_anomaly_counts(self, validator: KalshiDataValidator) -> None:
        """Get all anomaly counts returns dict."""
        market1 = {"ticker": "TEST1", "volume": -100}
        market2 = {"ticker": "TEST2", "volume": -200}
        validator.validate_market_data(market1)
        validator.validate_market_data(market2)
        counts = validator.get_all_anomaly_counts()
        assert "TEST1" in counts
        assert "TEST2" in counts

    def test_clear_anomaly_counts(self, validator: KalshiDataValidator) -> None:
        """Clear anomaly counts resets all counts."""
        market = {"ticker": "TEST", "volume": -100}
        validator.validate_market_data(market)
        assert validator.get_anomaly_count("TEST") > 0
        validator.clear_anomaly_counts()
        assert validator.get_anomaly_count("TEST") == 0


# =============================================================================
# Validation Summary Tests
# =============================================================================


class TestValidationSummary:
    """Tests for validation summary generation."""

    def test_summary_with_valid_data(
        self, validator: KalshiDataValidator, valid_market_data: dict
    ) -> None:
        """Summary shows 100% valid for valid data."""
        results = validator.validate_markets([valid_market_data])
        summary = validator.get_validation_summary(results)
        assert summary["total"] == 1
        assert summary["valid_count"] == 1
        assert summary["error_count"] == 0
        assert summary["valid_percentage"] == 100

    def test_summary_with_errors(self, validator: KalshiDataValidator) -> None:
        """Summary counts errors correctly."""
        markets: list[dict[str, object]] = [
            {"ticker": "GOOD", "status": "open"},
            {"ticker": "BAD", "volume": -100},  # Error
        ]
        results = validator.validate_markets(markets)  # type: ignore[arg-type]
        summary = validator.get_validation_summary(results)
        assert summary["total"] == 2
        assert summary["error_count"] == 1
        assert summary["valid_count"] == 1

    def test_summary_empty_list(self, validator: KalshiDataValidator) -> None:
        """Summary handles empty list."""
        summary = validator.get_validation_summary([])
        assert summary["total"] == 0
        assert summary["valid_percentage"] == 100  # No errors in empty list


# =============================================================================
# Log Issues Tests
# =============================================================================


class TestLogIssues:
    """Tests for issue logging."""

    def test_log_issues_no_exception(self, validator: KalshiDataValidator) -> None:
        """log_issues should not raise exceptions."""
        result = ValidationResult(entity_id="test", entity_type="market")
        result.add_error("field", "error message")
        result.add_warning("field", "warning message")
        result.add_info("field", "info message")
        # Should not raise
        result.log_issues()
