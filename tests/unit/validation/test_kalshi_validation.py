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
- Timestamp validation (ISO 8601, logical ordering, status-temporal consistency)
- Price staleness detection (unchanged prices across consecutive polls)
- Cross-field consistency (volume/OI anomalies)

Reference: Issue #222 (Kalshi Validation Module), #387 (Staleness + Timestamps)
Related: src/precog/validation/kalshi_validation.py
"""

from datetime import UTC, datetime, timedelta
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
    now = datetime.now(UTC)
    return {
        "ticker": "KXNFLGAME-25DEC25-CHI-GB",
        "status": "open",
        "yes_bid_dollars": Decimal("0.45"),
        "yes_ask_dollars": Decimal("0.47"),
        "no_bid_dollars": Decimal("0.53"),
        "no_ask_dollars": Decimal("0.55"),
        "volume": 1000,
        "open_interest": 500,
        "open_time": (now - timedelta(hours=2)).isoformat(),
        "close_time": (now + timedelta(hours=24)).isoformat(),
        "expiration_time": (now + timedelta(hours=48)).isoformat(),
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
        """Test string representation of issue.

        Note: __str__ no longer includes level prefix (e.g. [ERROR]) because
        the caller (log_issues / Python logger) already routes to the correct
        log level. Including it would produce redundant output.
        """
        issue = ValidationIssue(
            level=ValidationLevel.ERROR,
            field="price",
            message="Invalid price",
            value=Decimal("1.5"),
            expected="0-1",
        )
        str_repr = str(issue)
        assert "price" in str_repr
        assert "Invalid price" in str_repr
        assert "1.5" in str_repr
        assert "0-1" in str_repr

    def test_str_without_value_expected(self) -> None:
        """Test string representation without value/expected."""
        issue = ValidationIssue(
            level=ValidationLevel.WARNING,
            field="spread",
            message="Wide spread",
        )
        str_repr = str(issue)
        assert "spread" in str_repr
        assert "Wide spread" in str_repr
        # No value/expected means no "(got: ...)" or "(expected: ...)"
        assert "(got:" not in str_repr
        assert "(expected:" not in str_repr


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
        """All valid statuses (DB-mapped and raw Kalshi API) are accepted."""
        # Database-mapped statuses
        db_statuses = ["open", "closed", "settled", "halted"]
        # Raw Kalshi API statuses (mapped by poller before DB insert)
        api_statuses = ["active", "unopened", "determined", "finalized", "initialized", "inactive"]
        for status in db_statuses + api_statuses:
            market = {"ticker": "TEST", "status": status}
            result = validator.validate_market_data(market)
            # Should not have status-related warnings
            assert not any("status" in w.field for w in result.warnings), (
                f"Status '{status}' should be accepted but generated a warning"
            )

    def test_negative_volume_error(self, validator: KalshiDataValidator) -> None:
        """Negative volume generates error."""
        market = {"ticker": "TEST", "volume": -100}
        result = validator.validate_market_data(market)
        assert result.has_errors
        assert any("volume" in e.field for e in result.errors)

    def test_high_volume_warning(self, validator: KalshiDataValidator) -> None:
        """Unusually high lifetime volume generates warning."""
        market = {"ticker": "TEST", "volume": 2_000_000}  # Above 1M threshold
        result = validator.validate_market_data(market)
        assert result.has_warnings
        assert any("volume" in w.field for w in result.warnings)

    def test_moderate_volume_no_warning(self, validator: KalshiDataValidator) -> None:
        """Moderate lifetime volume (below 1M) does not generate warning."""
        market = {"ticker": "TEST", "volume": 200_000}
        result = validator.validate_market_data(market)
        assert not any("volume" in w.field for w in result.warnings)

    def test_negative_open_interest_error(self, validator: KalshiDataValidator) -> None:
        """Negative open interest generates error."""
        market = {"ticker": "TEST", "open_interest": -50}
        result = validator.validate_market_data(market)
        assert result.has_errors

    def test_arbitrage_warning_low_combined_ask(self, validator: KalshiDataValidator) -> None:
        """Combined ask < $0.98 generates arbitrage warning (active markets only)."""
        market = {
            "ticker": "TEST",
            "status": "active",
            "yes_ask_dollars": Decimal("0.45"),
            "no_ask_dollars": Decimal("0.50"),  # Combined = 0.95
        }
        result = validator.validate_market_data(market)
        assert result.has_warnings
        assert any("arbitrage" in w.field for w in result.warnings)

    def test_arbitrage_skipped_for_settled_market(self, validator: KalshiDataValidator) -> None:
        """Settled markets do not generate arbitrage warnings."""
        market = {
            "ticker": "TEST",
            "status": "settled",
            "yes_ask_dollars": Decimal("0.00"),
            "no_ask_dollars": Decimal("0.00"),  # Combined = 0.00 — normal for settled
        }
        result = validator.validate_market_data(market)
        assert not any("arbitrage" in w.field for w in result.warnings)

    def test_spread_skipped_for_settled_market(self, validator: KalshiDataValidator) -> None:
        """Settled markets do not generate spread warnings (bid=0/ask=1 is expected)."""
        market = {
            "ticker": "TEST",
            "status": "settled",
            "yes_bid_dollars": Decimal("0.00"),
            "yes_ask_dollars": Decimal("1.00"),  # Spread = 1.0 — normal for settled
            "no_bid_dollars": Decimal("0.00"),
            "no_ask_dollars": Decimal("1.00"),
        }
        result = validator.validate_market_data(market)
        assert not any("spread" in w.field for w in result.warnings)
        assert not any("spread" in e.field for e in result.errors)

    @pytest.mark.parametrize("status", ["active", "open"])
    def test_spread_checked_for_active_market(
        self, validator: KalshiDataValidator, status: str
    ) -> None:
        """Both ACTIVE_STATUSES members generate spread warnings for wide spreads."""
        market = {
            "ticker": "TEST",
            "status": status,
            "yes_bid_dollars": Decimal("0.30"),
            "yes_ask_dollars": Decimal("0.55"),  # 25-cent spread
        }
        result = validator.validate_market_data(market)
        assert any("spread" in w.field for w in result.warnings)

    @pytest.mark.parametrize("status", ["settled", "finalized"])
    def test_settlement_consistency_warning(
        self, validator: KalshiDataValidator, status: str
    ) -> None:
        """Both settlement statuses flag non-{0,1} prices (both sides checked)."""
        market = {
            "ticker": "TEST",
            "status": status,
            "yes_bid_dollars": Decimal("0.45"),  # Should be 0 or 1
            "yes_ask_dollars": Decimal("0.47"),  # Should be 0 or 1
            "no_bid_dollars": Decimal("0.55"),  # Should be 0 or 1
            "no_ask_dollars": Decimal("0.53"),  # Should be 0 or 1
        }
        result = validator.validate_market_data(market)
        assert result.has_warnings
        settlement_warnings = [w for w in result.warnings if "Settled market price" in w.message]
        assert len(settlement_warnings) == 4  # All four prices flagged

    def test_settlement_consistency_clean(self, validator: KalshiDataValidator) -> None:
        """Settled market with prices at 0 or 1 has no settlement warnings."""
        market = {
            "ticker": "TEST",
            "status": "settled",
            "yes_bid_dollars": Decimal("1"),
            "yes_ask_dollars": Decimal("1"),
            "no_bid_dollars": Decimal("0"),
            "no_ask_dollars": Decimal("0"),
        }
        result = validator.validate_market_data(market)
        assert not any("Settled market price" in w.message for w in result.warnings)

    def test_bid_sum_error_active_market(self, validator: KalshiDataValidator) -> None:
        """YES_bid + NO_bid > $1.01 on active market generates error."""
        market = {
            "ticker": "TEST",
            "status": "active",
            "yes_bid_dollars": Decimal("0.60"),
            "no_bid_dollars": Decimal("0.50"),  # Combined = 1.10
        }
        result = validator.validate_market_data(market)
        assert result.has_errors
        assert any("bid_sum" in e.field for e in result.errors)

    def test_bid_sum_skipped_for_settled_market(self, validator: KalshiDataValidator) -> None:
        """Settled markets do not check bid sum."""
        market = {
            "ticker": "TEST",
            "status": "settled",
            "yes_bid_dollars": Decimal("1.00"),
            "no_bid_dollars": Decimal("1.00"),  # Would be impossible if active
        }
        result = validator.validate_market_data(market)
        assert not any("bid_sum" in e.field for e in result.errors)


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

    def test_should_log_anomaly_at_thresholds(self, validator: KalshiDataValidator) -> None:
        """should_log_anomaly returns True at 1st, 10th, 100th occurrence."""
        entity = "DEDUP-TEST"
        # Manually set counts to check threshold behavior
        validator._anomaly_counts[entity] = 1
        assert validator.should_log_anomaly(entity)

        validator._anomaly_counts[entity] = 10
        assert validator.should_log_anomaly(entity)

        validator._anomaly_counts[entity] = 100
        assert validator.should_log_anomaly(entity)

    def test_should_log_anomaly_between_thresholds(self, validator: KalshiDataValidator) -> None:
        """should_log_anomaly returns False between thresholds."""
        entity = "DEDUP-TEST"
        for count in [2, 5, 9, 11, 50, 99, 101]:
            validator._anomaly_counts[entity] = count
            assert not validator.should_log_anomaly(entity), f"count={count} should be suppressed"

    def test_should_log_anomaly_after_100(self, validator: KalshiDataValidator) -> None:
        """After 100, should_log_anomaly fires every 100th occurrence."""
        entity = "DEDUP-TEST"
        validator._anomaly_counts[entity] = 200
        assert validator.should_log_anomaly(entity)

        validator._anomaly_counts[entity] = 201
        assert not validator.should_log_anomaly(entity)

        validator._anomaly_counts[entity] = 300
        assert validator.should_log_anomaly(entity)

    def test_should_log_anomaly_unknown_entity(self, validator: KalshiDataValidator) -> None:
        """Unknown entity (count=0) should not log."""
        assert not validator.should_log_anomaly("NEVER-SEEN")


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
        results = validator.validate_markets(markets)
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


# =============================================================================
# Timestamp Validation Tests (#387)
# =============================================================================


class TestTimestampValidation:
    """Tests for timestamp parsing, ordering, and status-temporal consistency."""

    def test_valid_timestamps_no_issues(
        self, validator: KalshiDataValidator, valid_market_data: dict
    ) -> None:
        """Market with valid, correctly ordered timestamps should pass."""
        result = validator.validate_market_data(valid_market_data)
        timestamp_issues = [
            i
            for i in result.issues
            if i.field in {"open_time", "close_time", "expiration_time", "settlement_lag"}
        ]
        assert len(timestamp_issues) == 0

    def test_malformed_open_time(self, validator: KalshiDataValidator) -> None:
        """Malformed open_time should produce a warning."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-TICKER",
            "status": "open",
            "open_time": "not-a-timestamp",
            "close_time": (now + timedelta(hours=24)).isoformat(),
            "expiration_time": (now + timedelta(hours=48)).isoformat(),
        }
        result = validator.validate_market_data(market)
        warnings = [i for i in result.warnings if i.field == "open_time"]
        assert len(warnings) == 1
        assert "Malformed" in warnings[0].message

    def test_malformed_close_time(self, validator: KalshiDataValidator) -> None:
        """Malformed close_time should produce a warning."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-TICKER",
            "status": "settled",
            "close_time": "garbage",
            "open_time": (now - timedelta(hours=48)).isoformat(),
        }
        result = validator.validate_market_data(market)
        warnings = [i for i in result.warnings if i.field == "close_time"]
        assert len(warnings) == 1

    def test_open_time_after_close_time_error(self, validator: KalshiDataValidator) -> None:
        """open_time > close_time is a logical impossibility — should be ERROR."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-TICKER",
            "status": "settled",
            "open_time": (now + timedelta(hours=10)).isoformat(),
            "close_time": (now - timedelta(hours=10)).isoformat(),
            "expiration_time": (now + timedelta(hours=48)).isoformat(),
        }
        result = validator.validate_market_data(market)
        errors = [i for i in result.errors if i.field == "open_time"]
        assert len(errors) == 1
        assert "after close_time" in errors[0].message

    def test_close_time_after_expiration_time_error(self, validator: KalshiDataValidator) -> None:
        """close_time > expiration_time is a logical impossibility."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-TICKER",
            "status": "settled",
            "open_time": (now - timedelta(hours=48)).isoformat(),
            "close_time": (now + timedelta(hours=100)).isoformat(),
            "expiration_time": (now + timedelta(hours=50)).isoformat(),
        }
        result = validator.validate_market_data(market)
        errors = [i for i in result.errors if i.field == "close_time"]
        assert len(errors) == 1
        assert "after expiration_time" in errors[0].message

    def test_active_market_close_time_in_past_warning(self, validator: KalshiDataValidator) -> None:
        """Active market with close_time in the past = missed closure."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-TICKER",
            "status": "active",
            "open_time": (now - timedelta(hours=48)).isoformat(),
            "close_time": (now - timedelta(hours=1)).isoformat(),
            "expiration_time": (now + timedelta(hours=24)).isoformat(),
        }
        result = validator.validate_market_data(market)
        warnings = [i for i in result.warnings if i.field == "close_time"]
        assert any("missed closure" in w.message for w in warnings)

    def test_active_market_open_time_in_future_warning(
        self, validator: KalshiDataValidator
    ) -> None:
        """Active market with open_time in the future = premature activation."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-TICKER",
            "status": "active",
            "open_time": (now + timedelta(hours=24)).isoformat(),
            "close_time": (now + timedelta(hours=48)).isoformat(),
            "expiration_time": (now + timedelta(hours=72)).isoformat(),
        }
        result = validator.validate_market_data(market)
        warnings = [i for i in result.warnings if i.field == "open_time"]
        assert any("premature activation" in w.message for w in warnings)

    def test_settled_market_skips_active_temporal_checks(
        self, validator: KalshiDataValidator
    ) -> None:
        """Settled market with close_time in the past is normal, not a warning."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-TICKER",
            "status": "settled",
            "open_time": (now - timedelta(hours=96)).isoformat(),
            "close_time": (now - timedelta(hours=48)).isoformat(),
            "expiration_time": (now - timedelta(hours=24)).isoformat(),
        }
        result = validator.validate_market_data(market)
        # Should NOT have "missed closure" warning (that's only for active markets)
        close_warnings = [
            i for i in result.warnings if i.field == "close_time" and "missed" in i.message
        ]
        assert len(close_warnings) == 0

    def test_settlement_lag_over_72h_info(self, validator: KalshiDataValidator) -> None:
        """Settled market with >72h settlement lag gets an info note."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-TICKER",
            "status": "settled",
            "open_time": (now - timedelta(days=10)).isoformat(),
            "close_time": (now - timedelta(days=7)).isoformat(),
            "expiration_time": (now - timedelta(days=2)).isoformat(),
            "settlement_time": (now - timedelta(days=2)).isoformat(),
        }
        result = validator.validate_market_data(market)
        infos = [i for i in result.issues if i.field == "settlement_lag"]
        assert len(infos) == 1
        assert ">72h" in infos[0].message

    def test_settlement_lag_without_settlement_time_no_alert(
        self, validator: KalshiDataValidator
    ) -> None:
        """Without explicit settlement_time, no lag check is performed."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-TICKER",
            "status": "settled",
            "open_time": (now - timedelta(days=10)).isoformat(),
            "close_time": (now - timedelta(days=7)).isoformat(),
            "expiration_time": (now - timedelta(days=2)).isoformat(),
        }
        result = validator.validate_market_data(market)
        lag_infos = [i for i in result.issues if i.field == "settlement_lag"]
        assert len(lag_infos) == 0

    def test_missing_timestamps_no_crash(self, validator: KalshiDataValidator) -> None:
        """Market with no timestamp fields should not crash."""
        market = {
            "ticker": "TEST-TICKER",
            "status": "open",
            "volume": 100,
            "open_interest": 50,
        }
        result = validator.validate_market_data(market)
        # Should complete without raising — no timestamp issues expected
        assert result is not None


# =============================================================================
# Cross-Field Consistency Tests (#387)
# =============================================================================


class TestCrossFieldConsistency:
    """Tests for cross-field validation rules."""

    def test_oi_on_never_active_market(self, validator: KalshiDataValidator) -> None:
        """OI > 0 on an unopened market is suspicious."""
        market = {
            "ticker": "TEST-TICKER",
            "status": "unopened",
            "open_interest": 100,
            "volume": 0,
        }
        result = validator.validate_market_data(market)
        warnings = [i for i in result.warnings if i.field == "open_interest"]
        assert any("never-active" in w.message for w in warnings)

    def test_oi_on_initialized_market(self, validator: KalshiDataValidator) -> None:
        """OI > 0 on an initialized market is also suspicious."""
        market = {
            "ticker": "TEST-TICKER",
            "status": "initialized",
            "open_interest": 50,
            "volume": 0,
        }
        result = validator.validate_market_data(market)
        warnings = [i for i in result.warnings if i.field == "open_interest"]
        assert any("never-active" in w.message for w in warnings)

    def test_volume_24h_exceeds_lifetime(self, validator: KalshiDataValidator) -> None:
        """24h volume > lifetime volume is an API data error."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-TICKER",
            "status": "active",
            "volume": 100,
            "volume_24h": 500,
            "open_interest": 50,
            "open_time": (now - timedelta(hours=48)).isoformat(),
            "close_time": (now + timedelta(hours=24)).isoformat(),
            "expiration_time": (now + timedelta(hours=48)).isoformat(),
        }
        result = validator.validate_market_data(market)
        warnings = [i for i in result.warnings if i.field == "volume_24h"]
        assert len(warnings) == 1
        assert "exceeds lifetime" in warnings[0].message

    def test_volume_24h_equal_to_lifetime_ok(self, validator: KalshiDataValidator) -> None:
        """24h volume == lifetime volume is fine (new market)."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-TICKER",
            "status": "active",
            "volume": 100,
            "volume_24h": 100,
            "open_interest": 50,
            "open_time": (now - timedelta(hours=12)).isoformat(),
            "close_time": (now + timedelta(hours=24)).isoformat(),
            "expiration_time": (now + timedelta(hours=48)).isoformat(),
        }
        result = validator.validate_market_data(market)
        vol_warnings = [i for i in result.warnings if i.field == "volume_24h"]
        assert len(vol_warnings) == 0

    def test_ghost_market_info(self, validator: KalshiDataValidator) -> None:
        """Active market with zero volume and zero OI is a ghost market."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-GHOST",
            "status": "active",
            "volume": 0,
            "open_interest": 0,
            "open_time": (now - timedelta(hours=48)).isoformat(),
            "close_time": (now + timedelta(hours=24)).isoformat(),
            "expiration_time": (now + timedelta(hours=48)).isoformat(),
        }
        result = validator.validate_market_data(market)
        ghost_infos = [i for i in result.issues if i.field == "ghost_market"]
        assert len(ghost_infos) == 1

    def test_active_market_with_volume_not_ghost(self, validator: KalshiDataValidator) -> None:
        """Active market with volume > 0 is not a ghost."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-TICKER",
            "status": "active",
            "volume": 100,
            "open_interest": 0,
            "open_time": (now - timedelta(hours=48)).isoformat(),
            "close_time": (now + timedelta(hours=24)).isoformat(),
            "expiration_time": (now + timedelta(hours=48)).isoformat(),
        }
        result = validator.validate_market_data(market)
        ghost_infos = [i for i in result.issues if i.field == "ghost_market"]
        assert len(ghost_infos) == 0


# =============================================================================
# Price Staleness Detection Tests (#387)
# =============================================================================


class TestPriceStaleness:
    """Tests for price staleness detection across consecutive polls."""

    def test_no_staleness_below_threshold(self, validator: KalshiDataValidator) -> None:
        """No warning if fewer than threshold consecutive polls."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-STALE",
            "status": "active",
            "yes_bid_dollars": Decimal("0.50"),
            "open_time": (now - timedelta(hours=2)).isoformat(),
            "close_time": (now + timedelta(hours=24)).isoformat(),
            "expiration_time": (now + timedelta(hours=48)).isoformat(),
        }
        # Poll 5 times (below threshold of 10)
        for _ in range(5):
            result = validator.validate_market_data(market)
        stale = [i for i in result.issues if i.field == "price_staleness"]
        assert len(stale) == 0

    def test_staleness_at_threshold(self, validator: KalshiDataValidator) -> None:
        """Warning when price unchanged for exactly threshold polls."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-STALE",
            "status": "active",
            "yes_bid_dollars": Decimal("0.50"),
            "open_time": (now - timedelta(hours=2)).isoformat(),
            "close_time": (now + timedelta(hours=24)).isoformat(),
            "expiration_time": (now + timedelta(hours=48)).isoformat(),
        }
        for _ in range(validator.STALE_PRICE_POLL_THRESHOLD):
            result = validator.validate_market_data(market)
        stale = [i for i in result.issues if i.field == "price_staleness"]
        assert len(stale) == 1
        assert "unchanged" in stale[0].message

    def test_price_change_resets_staleness(self, validator: KalshiDataValidator) -> None:
        """Price change should prevent staleness warning."""
        now = datetime.now(UTC)
        threshold = validator.STALE_PRICE_POLL_THRESHOLD
        base = {
            "ticker": "TEST-STALE",
            "status": "active",
            "open_time": (now - timedelta(hours=2)).isoformat(),
            "close_time": (now + timedelta(hours=24)).isoformat(),
            "expiration_time": (now + timedelta(hours=48)).isoformat(),
        }
        # Poll at same price just under threshold
        for _ in range(threshold - 2):
            validator.validate_market_data({**base, "yes_bid_dollars": Decimal("0.50")})
        # Change price — resets the consecutive run
        validator.validate_market_data({**base, "yes_bid_dollars": Decimal("0.51")})
        # Poll at new price, again just under threshold
        for _ in range(threshold - 2):
            result = validator.validate_market_data({**base, "yes_bid_dollars": Decimal("0.51")})
        stale = [i for i in result.issues if i.field == "price_staleness"]
        assert len(stale) == 0

    def test_staleness_not_checked_for_settled(self, validator: KalshiDataValidator) -> None:
        """Settled markets should not trigger staleness checks."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-SETTLED",
            "status": "settled",
            "yes_bid_dollars": Decimal("1.00"),
            "open_time": (now - timedelta(hours=96)).isoformat(),
            "close_time": (now - timedelta(hours=48)).isoformat(),
            "expiration_time": (now - timedelta(hours=24)).isoformat(),
        }
        for _ in range(15):
            result = validator.validate_market_data(market)
        stale = [i for i in result.issues if i.field == "price_staleness"]
        assert len(stale) == 0

    def test_staleness_per_ticker_isolation(self, validator: KalshiDataValidator) -> None:
        """Staleness tracking is per-ticker, not global."""
        now = datetime.now(UTC)
        base = {
            "status": "active",
            "yes_bid_dollars": Decimal("0.50"),
            "open_time": (now - timedelta(hours=2)).isoformat(),
            "close_time": (now + timedelta(hours=24)).isoformat(),
            "expiration_time": (now + timedelta(hours=48)).isoformat(),
        }
        # Poll ticker A 10 times
        for _ in range(10):
            validator.validate_market_data({**base, "ticker": "TICKER-A"})
        # Poll ticker B only 3 times
        for _ in range(3):
            result_b = validator.validate_market_data({**base, "ticker": "TICKER-B"})
        stale_b = [i for i in result_b.issues if i.field == "price_staleness"]
        assert len(stale_b) == 0  # B should not be flagged

    def test_none_price_not_stale(self, validator: KalshiDataValidator) -> None:
        """None prices should not trigger staleness (no meaningful comparison)."""
        now = datetime.now(UTC)
        market = {
            "ticker": "TEST-NONE",
            "status": "active",
            "yes_bid_dollars": None,
            "open_time": (now - timedelta(hours=2)).isoformat(),
            "close_time": (now + timedelta(hours=24)).isoformat(),
            "expiration_time": (now + timedelta(hours=48)).isoformat(),
        }
        for _ in range(15):
            result = validator.validate_market_data(market)
        stale = [i for i in result.issues if i.field == "price_staleness"]
        assert len(stale) == 0

    def test_staleness_recurs_after_threshold(self, validator: KalshiDataValidator) -> None:
        """Staleness warning should fire on every poll after the threshold, not just once."""
        now = datetime.now(UTC)
        threshold = validator.STALE_PRICE_POLL_THRESHOLD
        market = {
            "ticker": "TEST-RECUR",
            "status": "active",
            "yes_bid_dollars": Decimal("0.50"),
            "open_time": (now - timedelta(hours=2)).isoformat(),
            "close_time": (now + timedelta(hours=24)).isoformat(),
            "expiration_time": (now + timedelta(hours=48)).isoformat(),
        }
        # Poll past threshold + 2 more
        for _ in range(threshold + 2):
            result = validator.validate_market_data(market)
        # The last poll should still have the staleness warning
        stale = [i for i in result.issues if i.field == "price_staleness"]
        assert len(stale) == 1

    def test_clear_price_history(self, validator: KalshiDataValidator) -> None:
        """clear_price_history() should reset all staleness tracking."""
        now = datetime.now(UTC)
        threshold = validator.STALE_PRICE_POLL_THRESHOLD
        market = {
            "ticker": "TEST-CLEAR",
            "status": "active",
            "yes_bid_dollars": Decimal("0.50"),
            "open_time": (now - timedelta(hours=2)).isoformat(),
            "close_time": (now + timedelta(hours=24)).isoformat(),
            "expiration_time": (now + timedelta(hours=48)).isoformat(),
        }
        # Build up history to just under threshold
        for _ in range(threshold - 1):
            validator.validate_market_data(market)
        # Clear history
        validator.clear_price_history()
        # One more poll should not trigger (history was reset)
        result = validator.validate_market_data(market)
        stale = [i for i in result.issues if i.field == "price_staleness"]
        assert len(stale) == 0


# =============================================================================
# Timestamp Parsing Edge Cases (#387 — S3/CG-1)
# =============================================================================


class TestTimestampParsing:
    """Direct tests for _parse_iso8601 and edge cases."""

    def test_parse_z_suffix(self) -> None:
        """Kalshi API sends timestamps with Z suffix."""
        result = KalshiDataValidator._parse_iso8601("2025-12-14T12:00:00Z")
        assert result is not None
        assert result.tzinfo is not None

    def test_parse_offset_suffix(self) -> None:
        """Some APIs send +00:00 instead of Z."""
        result = KalshiDataValidator._parse_iso8601("2025-12-14T12:00:00+00:00")
        assert result is not None
        assert result.tzinfo is not None

    def test_naive_datetime_returns_none(self) -> None:
        """Timezone-naive strings should return None to prevent TypeError."""
        result = KalshiDataValidator._parse_iso8601("2025-12-14T12:00:00")
        assert result is None

    def test_naive_datetime_triggers_malformed_warning(
        self, validator: KalshiDataValidator
    ) -> None:
        """Naive timestamp in market data should produce a malformed warning."""
        market = {
            "ticker": "TEST-NAIVE",
            "status": "settled",
            "open_time": "2025-12-14T12:00:00",  # No timezone
        }
        result = validator.validate_market_data(market)
        warnings = [i for i in result.warnings if i.field == "open_time"]
        assert any("Malformed" in w.message for w in warnings)

    def test_garbage_string_returns_none(self) -> None:
        """Completely invalid string returns None."""
        assert KalshiDataValidator._parse_iso8601("not-a-date") is None

    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None."""
        assert KalshiDataValidator._parse_iso8601("") is None

    def test_none_input_returns_none(self) -> None:
        """None input returns None (TypeError caught)."""
        assert KalshiDataValidator._parse_iso8601(None) is None  # type: ignore[arg-type]

    def test_fractional_seconds(self) -> None:
        """Fractional seconds should parse correctly."""
        result = KalshiDataValidator._parse_iso8601("2025-12-14T12:00:00.123456Z")
        assert result is not None
        assert result.microsecond == 123456
