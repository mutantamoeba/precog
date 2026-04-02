"""
Kalshi Data Validation Module.

Validates Kalshi API response data for anomalies, invalid values, and data quality issues.
Uses soft validation (logs warnings but doesn't block storage) to maintain data flow
while flagging issues for review.

Architecture:
    This module follows the same pattern as ESPN validation (espn_validation.py):
    1. ValidationLevel enum for categorizing issues (ERROR, WARNING, INFO)
    2. ValidationIssue dataclass for individual issues
    3. ValidationResult dataclass for aggregating issues per entity
    4. KalshiDataValidator class for running validations

Why Soft Validation?
    In live trading scenarios, we want to:
    - Store all data (even potentially invalid) for later analysis
    - Alert operators about anomalies
    - Not block data flow due to temporary API inconsistencies
    - Track anomaly frequency per market/position

Reference: docs/api-integration/KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md
Related Issue: #222 (Kalshi Validation Module)
Related Requirements: REQ-DATA-003 (Data Quality Monitoring)
Related Pattern: ESPN validation (src/precog/validation/espn_validation.py)
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, ClassVar

from precog.utils.logger import get_logger

logger = get_logger(__name__)


def _parse_fp_int(raw: str | None) -> int | None:
    """Parse a Kalshi _fp string field (e.g., "8981763.00") into an integer.

    Returns None if the value is absent or unparseable.
    """
    if raw is None:
        return None
    try:
        return int(float(raw))
    except (ValueError, TypeError, OverflowError):
        return None


# =============================================================================
# Validation Level Enum
# =============================================================================


class ValidationLevel(Enum):
    """
    Severity level for validation issues.

    Levels:
        ERROR: Data is definitely invalid (e.g., negative prices, impossible values)
        WARNING: Data is suspicious but may be valid (e.g., unusual spreads, high volumes)
        INFO: Informational note (e.g., market closed, no open interest)

    Educational Note:
        Using enum instead of strings provides:
        - Type safety (IDE autocomplete, type checking)
        - Exhaustive pattern matching
        - Protection against typos ("ERORR" vs ERROR)
    """

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# =============================================================================
# Validation Data Classes
# =============================================================================


@dataclass
class ValidationIssue:
    """
    Individual validation issue found during data validation.

    Attributes:
        level: Severity of the issue (ERROR, WARNING, INFO)
        field: Name of the field with the issue
        message: Human-readable description of the issue
        value: Actual value found (optional)
        expected: Expected value or range (optional)

    Educational Note:
        Using dataclass provides:
        - Automatic __init__, __repr__, __eq__
        - Type hints for IDE support
        - Immutable data container
    """

    level: ValidationLevel
    field: str
    message: str
    value: Any = None
    expected: Any = None

    def __str__(self) -> str:
        """Human-readable string representation.

        Note: Does NOT include level prefix — the caller (log_issues or Python
        logger) already routes to the correct log level. Including [WARNING]
        here would produce redundant output like "WARNING ... [WARNING] ...".
        """
        parts = [f"{self.field}: {self.message}"]
        if self.value is not None:
            parts.append(f" (got: {self.value})")
        if self.expected is not None:
            parts.append(f" (expected: {self.expected})")
        return "".join(parts)


@dataclass
class ValidationResult:
    """
    Aggregated validation result for a single entity (market, position, etc.).

    Attributes:
        entity_id: Identifier for the entity being validated (ticker, position ID, etc.)
        entity_type: Type of entity ("market", "position", "fill", "settlement", "balance")
        issues: List of validation issues found

    Properties:
        has_errors: True if any ERROR-level issues exist
        has_warnings: True if any WARNING-level issues exist
        is_valid: True if no ERROR-level issues exist

    Educational Note:
        Separating has_errors from is_valid allows for nuanced handling:
        - has_errors = critical issues that may indicate data corruption
        - has_warnings = suspicious data that should be reviewed
        - is_valid = safe to use data (may still have warnings)
    """

    entity_id: str = ""
    entity_type: str = "unknown"
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if any ERROR-level issues exist."""
        return any(issue.level == ValidationLevel.ERROR for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        """Check if any WARNING-level issues exist."""
        return any(issue.level == ValidationLevel.WARNING for issue in self.issues)

    @property
    def is_valid(self) -> bool:
        """Check if data is valid (no ERROR-level issues)."""
        return not self.has_errors

    @property
    def errors(self) -> list[ValidationIssue]:
        """Get all ERROR-level issues."""
        return [issue for issue in self.issues if issue.level == ValidationLevel.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Get all WARNING-level issues."""
        return [issue for issue in self.issues if issue.level == ValidationLevel.WARNING]

    def add_error(
        self, field_name: str, message: str, value: Any = None, expected: Any = None
    ) -> None:
        """Add an ERROR-level issue."""
        self.issues.append(
            ValidationIssue(
                level=ValidationLevel.ERROR,
                field=field_name,
                message=message,
                value=value,
                expected=expected,
            )
        )

    def add_warning(
        self, field_name: str, message: str, value: Any = None, expected: Any = None
    ) -> None:
        """Add a WARNING-level issue."""
        self.issues.append(
            ValidationIssue(
                level=ValidationLevel.WARNING,
                field=field_name,
                message=message,
                value=value,
                expected=expected,
            )
        )

    def add_info(
        self, field_name: str, message: str, value: Any = None, expected: Any = None
    ) -> None:
        """Add an INFO-level issue."""
        self.issues.append(
            ValidationIssue(
                level=ValidationLevel.INFO,
                field=field_name,
                message=message,
                value=value,
                expected=expected,
            )
        )

    def log_issues(self, logger_instance: logging.Logger | None = None) -> None:
        """
        Log all issues at appropriate log levels.

        Args:
            logger_instance: Logger to use (defaults to module logger)
        """
        log = logger_instance or logger
        for issue in self.issues:
            log_msg = f"[{self.entity_type}:{self.entity_id}] {issue}"
            if issue.level == ValidationLevel.ERROR:
                log.error(log_msg)
            elif issue.level == ValidationLevel.WARNING:
                log.warning(log_msg)
            else:
                log.info(log_msg)


# =============================================================================
# Kalshi Data Validator
# =============================================================================


class KalshiDataValidator:
    """
    Validator for Kalshi API response data.

    Validates market data, positions, fills, settlements, and balance
    for anomalies and invalid values.

    Features:
        - Price validation (must be 0-1 range in dollars)
        - Bid/ask spread validation
        - Volume and open interest validation
        - Position quantity validation
        - P&L consistency checks
        - Settlement value validation (must be 0 or 1)
        - Anomaly tracking per entity

    Educational Note:
        All Kalshi prices are in the range [0, 1] representing
        probability-based pricing:
        - $0.50 = 50% implied probability
        - $0.75 = 75% implied probability
        - Prices outside 0-1 are invalid

        The API returns prices in *_dollars fields (Decimal)
        or *_cents fields (int). This validator expects dollar values.

    Example:
        >>> validator = KalshiDataValidator()
        >>> result = validator.validate_market_data({
        ...     "ticker": "KXNFLGAME-25DEC25-CHI-GB",
        ...     "status": "open",
        ...     "yes_bid_dollars": Decimal("0.45"),
        ...     "yes_ask_dollars": Decimal("0.47"),
        ... })
        >>> print(result.is_valid)
        True
    """

    # Price bounds (Kalshi prices are probabilities 0-1)
    MIN_PRICE = Decimal("0")
    MAX_PRICE = Decimal("1")

    # Spread thresholds for warnings (only meaningful for active/open markets)
    WIDE_SPREAD_THRESHOLD = Decimal("0.10")  # 10 cents is wide
    VERY_WIDE_SPREAD_THRESHOLD = Decimal("0.20")  # 20 cents is very wide

    # Statuses where spread/arbitrage checks are meaningful.
    # Non-active markets (settled, determined, inactive, etc.) have no live
    # orderbook — wide spreads and "arbitrage" are expected, not anomalous.
    ACTIVE_STATUSES: ClassVar[set[str]] = {"active", "open"}

    # Statuses for markets that have never been tradeable.
    # OI or volume on these markets indicates a database inconsistency.
    NEVER_ACTIVE_STATUSES: ClassVar[set[str]] = {"unopened", "initialized"}

    # Volume thresholds for warnings.
    # Note: Kalshi volume is cumulative lifetime, not per-update delta.
    # Popular markets easily exceed 100k over their lifetime.
    UNUSUALLY_HIGH_VOLUME = 1_000_000  # 1M lifetime contracts is unusual
    UNUSUALLY_HIGH_OPEN_INTEREST = 500000  # 500k OI is unusual

    # Balance thresholds
    MAX_REASONABLE_BALANCE = Decimal("10000000")  # $10M seems like a reasonable upper bound

    # Anomaly deduplication thresholds: log at 1st, 10th, 100th occurrence.
    # Between thresholds, anomalies are counted but not individually logged,
    # reducing noise from markets that repeatedly fail the same check.
    ANOMALY_LOG_THRESHOLDS: ClassVar[tuple[int, ...]] = (1, 10, 100)

    # Staleness detection: if a market's yes_bid price hasn't changed
    # in this many consecutive polls, flag it. At 15s poll intervals,
    # 10 polls = ~2.5 minutes of unchanged price.
    STALE_PRICE_POLL_THRESHOLD = 10
    # Max history to keep per ticker (bounded memory)
    STALE_PRICE_HISTORY_SIZE = 20

    # Settlement lag: flag if settlement happens >72h after close_time
    SETTLEMENT_LAG_THRESHOLD_HOURS = 72

    def __init__(self) -> None:
        """Initialize the validator with anomaly tracking and staleness state."""
        # Track anomaly counts per entity (ticker, position, etc.)
        self._anomaly_counts: dict[str, int] = {}
        # Track recent yes_bid prices per ticker for staleness detection.
        # Uses deque with maxlen to bound memory automatically.
        self._price_history: dict[str, deque[Decimal | None]] = {}

    def _increment_anomaly_count(self, entity_id: str) -> None:
        """Increment anomaly count for an entity by one occurrence."""
        self._anomaly_counts[entity_id] = self._anomaly_counts.get(entity_id, 0) + 1

    def should_log_anomaly(self, entity_id: str) -> bool:
        """Check if this entity's anomaly count is at a logging threshold.

        Returns True at the 1st, 10th, and 100th occurrence. After 100,
        logs every 100th occurrence. This prevents log flooding from
        markets that repeatedly fail the same check while still surfacing
        new anomalies immediately.
        """
        count = self._anomaly_counts.get(entity_id, 0)
        if count in self.ANOMALY_LOG_THRESHOLDS:
            return True
        # After 100, log every 100th
        return count > 100 and count % 100 == 0

    def get_anomaly_count(self, entity_id: str) -> int:
        """Get anomaly count for an entity."""
        return self._anomaly_counts.get(entity_id, 0)

    def get_all_anomaly_counts(self) -> dict[str, int]:
        """Get all anomaly counts."""
        return dict(self._anomaly_counts)

    def clear_anomaly_counts(self) -> None:
        """Clear all anomaly counts."""
        self._anomaly_counts.clear()

    def clear_price_history(self) -> None:
        """Clear all price staleness tracking history."""
        self._price_history.clear()

    # -------------------------------------------------------------------------
    # Price Validation
    # -------------------------------------------------------------------------

    def validate_price(
        self,
        price: Decimal | None,
        field_name: str,
        result: ValidationResult,
        allow_none: bool = True,
    ) -> bool:
        """
        Validate a single price value.

        Args:
            price: Price value to validate (Decimal in dollars)
            field_name: Name of the field for error reporting
            result: ValidationResult to add issues to
            allow_none: Whether None is acceptable (default True)

        Returns:
            True if price is valid, False otherwise

        Validation Rules:
            - Price must be Decimal type (not float!)
            - Price must be in range [0, 1]
            - None is allowed if allow_none=True
        """
        if price is None:
            if not allow_none:
                result.add_error(field_name, "Price is required but was None")
                return False
            return True

        # Runtime type check for external data (API responses may be incorrectly typed)
        if not isinstance(price, Decimal):
            result.add_error(  # type: ignore[unreachable]
                field_name,
                "Price must be Decimal type (float contamination detected)",
                value=type(price).__name__,
                expected="Decimal",
            )
            return False

        if price < self.MIN_PRICE:
            result.add_error(
                field_name,
                "Price below minimum",
                value=price,
                expected=f">= {self.MIN_PRICE}",
            )
            return False

        if price > self.MAX_PRICE:
            result.add_error(
                field_name,
                "Price above maximum",
                value=price,
                expected=f"<= {self.MAX_PRICE}",
            )
            return False

        return True

    def validate_spread(
        self,
        bid: Decimal | None,
        ask: Decimal | None,
        result: ValidationResult,
    ) -> None:
        """
        Validate bid/ask spread.

        Args:
            bid: Bid price (Decimal in dollars)
            ask: Ask price (Decimal in dollars)
            result: ValidationResult to add issues to

        Validation Rules:
            - If both exist, bid <= ask (no crossed market)
            - Spread > 10 cents generates WARNING
            - Spread > 20 cents generates WARNING (more severe)
        """
        if bid is None or ask is None:
            return  # Can't validate spread without both prices

        if bid > ask:
            result.add_error(
                "spread",
                "Crossed market (bid > ask)",
                value=f"bid={bid}, ask={ask}",
                expected="bid <= ask",
            )
            return

        spread = ask - bid

        if spread > self.VERY_WIDE_SPREAD_THRESHOLD:
            result.add_warning(
                "spread",
                "Very wide bid/ask spread",
                value=spread,
                expected=f"<= {self.VERY_WIDE_SPREAD_THRESHOLD}",
            )
        elif spread > self.WIDE_SPREAD_THRESHOLD:
            result.add_warning(
                "spread",
                "Wide bid/ask spread",
                value=spread,
                expected=f"<= {self.WIDE_SPREAD_THRESHOLD}",
            )

    # -------------------------------------------------------------------------
    # Timestamp Validation
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_iso8601(timestamp_str: str) -> datetime | None:
        """Parse an ISO 8601 timestamp string to a timezone-aware datetime.

        Returns None if the string is malformed or timezone-naive (to avoid
        TypeError when comparing with timezone-aware ``datetime.now(UTC)``).
        Handles both 'Z' suffix and '+00:00' offset formats from the Kalshi API.
        """
        try:
            dt = datetime.fromisoformat(timestamp_str)
        except (ValueError, TypeError):
            return None
        # Reject naive datetimes — comparing with now(UTC) would raise TypeError
        if dt.tzinfo is None:
            return None
        return dt

    def validate_timestamps(
        self,
        market: dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """Validate timestamp fields for logical consistency.

        Checks:
            - Timestamps are valid ISO 8601
            - open_time < close_time < expiration_time (logical ordering)
            - Active market with close_time in the past (missed closure)
            - Active market with open_time in the future (premature activation)
            - Settled market with settlement lag > 72h (unusually long)
        """
        now = datetime.now(UTC)

        open_time_str = market.get("open_time")
        close_time_str = market.get("close_time")
        expiration_time_str = market.get("expiration_time")
        status = market.get("status")
        is_active = status in self.ACTIVE_STATUSES

        # Parse timestamps (None if missing or malformed)
        open_time = self._parse_iso8601(open_time_str) if open_time_str else None
        close_time = self._parse_iso8601(close_time_str) if close_time_str else None
        expiration_time = self._parse_iso8601(expiration_time_str) if expiration_time_str else None

        # Flag malformed timestamps (string present but unparseable)
        if open_time_str and open_time is None:
            result.add_warning("open_time", "Malformed ISO 8601 timestamp", value=open_time_str)
        if close_time_str and close_time is None:
            result.add_warning("close_time", "Malformed ISO 8601 timestamp", value=close_time_str)
        if expiration_time_str and expiration_time is None:
            result.add_warning(
                "expiration_time",
                "Malformed ISO 8601 timestamp",
                value=expiration_time_str,
            )

        # Logical ordering checks
        if open_time and close_time and open_time > close_time:
            result.add_error(
                "open_time",
                "open_time is after close_time",
                value=open_time_str,
                expected=f"before {close_time_str}",
            )
        if close_time and expiration_time and close_time > expiration_time:
            result.add_error(
                "close_time",
                "close_time is after expiration_time",
                value=close_time_str,
                expected=f"before {expiration_time_str}",
            )

        # Status-temporal consistency (only for active/open markets)
        if is_active:
            if close_time and close_time < now:
                result.add_warning(
                    "close_time",
                    "Active market with close_time in the past (missed closure)",
                    value=close_time_str,
                    expected="future",
                )
            if open_time and open_time > now:
                result.add_warning(
                    "open_time",
                    "Active market with open_time in the future (premature activation)",
                    value=open_time_str,
                    expected="past",
                )

        # Settled market settlement lag check — only when explicit settlement_time
        # is present. Using expiration_time as a fallback would be misleading
        # (close-to-expiration gap != actual settlement delay).
        is_settled = status in {"settled", "finalized"}
        if is_settled and close_time:
            settled_time_str = market.get("settlement_time")
            settled_time = self._parse_iso8601(settled_time_str) if settled_time_str else None
            if settled_time:
                lag = settled_time - close_time
                threshold_seconds = self.SETTLEMENT_LAG_THRESHOLD_HOURS * 3600
                if lag.total_seconds() > threshold_seconds:
                    result.add_info(
                        "settlement_lag",
                        f"Unusually long settlement (>{self.SETTLEMENT_LAG_THRESHOLD_HOURS}h after close)",
                        value=f"{lag.total_seconds() / 3600:.1f}h",
                        expected=f"<= {self.SETTLEMENT_LAG_THRESHOLD_HOURS}h",
                    )

    def validate_cross_field_consistency(
        self,
        market: dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """Validate cross-field consistency rules.

        Checks:
            - OI > 0 on a market that was never active (database inconsistency)
            - volume_24h > volume (API data error)
            - Active market with volume=0 AND OI=0 for extended period (ghost market)
        """
        status = market.get("status")
        volume = _parse_fp_int(market.get("volume_fp"))
        open_interest = _parse_fp_int(market.get("open_interest_fp"))
        volume_24h = _parse_fp_int(market.get("volume_24h_fp"))

        # OI on never-active market
        if status in self.NEVER_ACTIVE_STATUSES and open_interest and open_interest > 0:
            result.add_warning(
                "open_interest",
                "Open interest > 0 on a never-active market",
                value=open_interest,
                expected="0",
            )

        # 24h volume exceeds lifetime volume
        if volume_24h is not None and volume is not None and volume_24h > volume:
            result.add_warning(
                "volume_24h",
                "24h volume exceeds lifetime volume (API data error)",
                value=volume_24h,
                expected=f"<= {volume}",
            )

        # Ghost market: active with zero volume AND zero OI.
        # Note: None == 0 is False in Python, so missing fields won't false-positive.
        is_active = status in self.ACTIVE_STATUSES
        if is_active and volume == 0 and open_interest == 0:
            result.add_info(
                "ghost_market",
                "Active market with zero volume and zero open interest",
            )

    def check_price_staleness(
        self,
        ticker: str,
        yes_bid: Decimal | None,
        result: ValidationResult,
    ) -> None:
        """Check if a market's price has been unchanged across consecutive polls.

        Tracks the last N yes_bid prices per ticker. If the price is identical
        for STALE_PRICE_POLL_THRESHOLD consecutive polls, emits a warning.
        """
        if ticker not in self._price_history:
            self._price_history[ticker] = deque(maxlen=self.STALE_PRICE_HISTORY_SIZE)

        history = self._price_history[ticker]
        history.append(yes_bid)

        # Need at least threshold entries to judge staleness
        if len(history) < self.STALE_PRICE_POLL_THRESHOLD:
            return

        # Check if the last N prices are all identical
        recent = list(history)[-self.STALE_PRICE_POLL_THRESHOLD :]
        if all(p == recent[0] for p in recent) and recent[0] is not None:
            result.add_warning(
                "price_staleness",
                f"Price unchanged for {self.STALE_PRICE_POLL_THRESHOLD} consecutive polls",
                value=recent[0],
                expected="price movement",
            )

    # -------------------------------------------------------------------------
    # Market Data Validation
    # -------------------------------------------------------------------------

    def validate_market_data(self, market: dict[str, Any]) -> ValidationResult:
        """
        Validate processed market data from Kalshi API.

        Args:
            market: ProcessedMarketData dict from kalshi_client

        Returns:
            ValidationResult with any issues found

        Validates:
            - Ticker exists and is non-empty
            - Status is valid ("open", "closed", "settled")
            - YES bid/ask prices are in valid range [0, 1]
            - NO bid/ask prices are in valid range [0, 1]
            - Bid/ask spread is reasonable
            - YES + NO prices sum to ~$1 (arbitrage check)
            - Volume and open_interest are non-negative

        Example:
            >>> validator = KalshiDataValidator()
            >>> market = {
            ...     "ticker": "KXNFLGAME-25DEC25-CHI-GB",
            ...     "status": "open",
            ...     "yes_bid_dollars": Decimal("0.45"),
            ...     "yes_ask_dollars": Decimal("0.47"),
            ...     "no_bid_dollars": Decimal("0.53"),
            ...     "no_ask_dollars": Decimal("0.55"),
            ...     "volume_fp": "1000.00",
            ...     "open_interest_fp": "500.00",
            ... }
            >>> result = validator.validate_market_data(market)
            >>> print(result.is_valid)
        """
        ticker = market.get("ticker", "unknown")
        result = ValidationResult(entity_id=ticker, entity_type="market")

        # Validate ticker
        if not ticker or ticker == "unknown":
            result.add_error("ticker", "Missing or empty ticker")

        # Validate status
        # Includes both database-mapped statuses (open, closed, settled, halted)
        # and raw Kalshi API statuses (active, unopened, determined, finalized,
        # initialized, inactive). The poller maps API statuses to DB statuses
        # via STATUS_MAPPING, but validation runs on raw API data before mapping.
        status = market.get("status")
        valid_statuses = {
            # Database-mapped statuses
            "open",
            "closed",
            "settled",
            "halted",
            # Raw Kalshi API statuses (mapped to DB statuses by the poller)
            "active",
            "unopened",
            "determined",
            "finalized",
            "initialized",
            "inactive",
        }
        if status and status not in valid_statuses:
            result.add_warning(
                "status",
                "Unknown market status",
                value=status,
                expected=valid_statuses,
            )

        # Validate YES prices (range check applies to all statuses)
        yes_bid = market.get("yes_bid_dollars")
        yes_ask = market.get("yes_ask_dollars")
        self.validate_price(yes_bid, "yes_bid_dollars", result)
        self.validate_price(yes_ask, "yes_ask_dollars", result)

        # Validate NO prices (range check applies to all statuses)
        no_bid = market.get("no_bid_dollars")
        no_ask = market.get("no_ask_dollars")
        self.validate_price(no_bid, "no_bid_dollars", result)
        self.validate_price(no_ask, "no_ask_dollars", result)

        is_active = status in self.ACTIVE_STATUSES
        is_settled = status in {"settled", "finalized"}

        # Spread and arbitrage checks: only meaningful for active/open markets.
        # Non-active markets have no live orderbook — bid=0/ask=1 (spread=1.0)
        # is expected for settled markets, not an anomaly.
        if is_active:
            self.validate_spread(yes_bid, yes_ask, result)
            self.validate_spread(no_bid, no_ask, result)

            # Arbitrage check: YES_ask + NO_ask should be ~$1
            # (Can't buy both YES and NO for less than $1 combined)
            if yes_ask is not None and no_ask is not None:
                combined_ask = yes_ask + no_ask
                if combined_ask < Decimal("0.98"):
                    result.add_warning(
                        "arbitrage",
                        "Potential arbitrage: YES_ask + NO_ask < $0.98",
                        value=combined_ask,
                        expected=">= $0.98",
                    )

            # Bid sum check: YES_bid + NO_bid should be <= $1.01
            # (Unlike asks which include spread, bids summing over 1.0 is impossible)
            if yes_bid is not None and no_bid is not None:
                combined_bid = yes_bid + no_bid
                if combined_bid > Decimal("1.01"):
                    result.add_error(
                        "bid_sum",
                        "Impossible bid sum: YES_bid + NO_bid > $1.01",
                        value=combined_bid,
                        expected="<= $1.01",
                    )

        # Settlement consistency checks: settled markets should have prices
        # at exactly 0.0000 or 1.0000 (binary outcome resolved).
        # Note: "determined" (outcome decided, awaiting payout) is NOT included
        # because it's a short-lived transitional state where prices may still
        # be adjusting. The poller maps it to "closed" before DB insert.
        if is_settled:
            for field_name, price in [
                ("yes_bid_dollars", yes_bid),
                ("yes_ask_dollars", yes_ask),
                ("no_bid_dollars", no_bid),
                ("no_ask_dollars", no_ask),
            ]:
                if price is not None and price not in {Decimal("0"), Decimal("1")}:
                    result.add_warning(
                        field_name,
                        "Settled market price not at 0 or 1",
                        value=price,
                        expected="{0, 1}",
                    )

        # Validate volume (cumulative lifetime — not per-update delta)
        volume = _parse_fp_int(market.get("volume_fp"))
        if volume is not None:
            if volume < 0:
                result.add_error("volume", "Negative volume", value=volume, expected=">= 0")
            elif volume > self.UNUSUALLY_HIGH_VOLUME:
                result.add_warning(
                    "volume",
                    "Unusually high lifetime volume",
                    value=volume,
                    expected=f"<= {self.UNUSUALLY_HIGH_VOLUME}",
                )

        # Validate open interest
        open_interest = _parse_fp_int(market.get("open_interest_fp"))
        if open_interest is not None:
            if open_interest < 0:
                result.add_error(
                    "open_interest", "Negative open interest", value=open_interest, expected=">= 0"
                )
            elif open_interest > self.UNUSUALLY_HIGH_OPEN_INTEREST:
                result.add_warning(
                    "open_interest",
                    "Unusually high open interest",
                    value=open_interest,
                    expected=f"<= {self.UNUSUALLY_HIGH_OPEN_INTEREST}",
                )

        # Timestamp validation (logical ordering + status-temporal consistency)
        self.validate_timestamps(market, result)

        # Cross-field consistency checks
        self.validate_cross_field_consistency(market, result)

        # Price staleness detection (stateful — tracks across polls)
        if is_active:
            self.check_price_staleness(ticker, yes_bid, result)

        # Track anomalies
        if result.has_errors or result.has_warnings:
            self._increment_anomaly_count(ticker)

        return result

    # -------------------------------------------------------------------------
    # Position Data Validation
    # -------------------------------------------------------------------------

    def validate_position_data(self, position: dict[str, Any]) -> ValidationResult:
        """
        Validate processed position data from Kalshi API.

        Args:
            position: ProcessedPositionData dict from kalshi_client

        Returns:
            ValidationResult with any issues found

        Validates:
            - Ticker exists
            - Position quantity is an integer (can be negative for short)
            - Average price is in valid range [0, 1]
            - Realized P&L is a valid Decimal
            - Total cost and fees_paid are non-negative

        Example:
            >>> validator = KalshiDataValidator()
            >>> position = {
            ...     "ticker": "KXNFLGAME-25DEC25-CHI-GB",
            ...     "position": 100,
            ...     "user_average_price": Decimal("0.45"),
            ...     "realized_pnl": Decimal("25.50"),
            ...     "total_cost": Decimal("45.00"),
            ...     "fees_paid": Decimal("1.50"),
            ... }
            >>> result = validator.validate_position_data(position)
        """
        ticker = position.get("ticker", "unknown")
        result = ValidationResult(entity_id=ticker, entity_type="position")

        # Validate ticker
        if not ticker or ticker == "unknown":
            result.add_error("ticker", "Missing or empty ticker")

        # Validate position quantity
        pos_qty = position.get("position")
        if pos_qty is not None and not isinstance(pos_qty, int):
            result.add_warning(
                "position",
                "Position quantity should be integer",
                value=type(pos_qty).__name__,
                expected="int",
            )

        # Validate average price
        avg_price = position.get("user_average_price")
        if avg_price is not None:
            self.validate_price(avg_price, "user_average_price", result)

        # Validate realized P&L (can be negative)
        realized_pnl = position.get("realized_pnl")
        if realized_pnl is not None and not isinstance(realized_pnl, Decimal):
            result.add_warning(
                "realized_pnl",
                "Realized P&L should be Decimal",
                value=type(realized_pnl).__name__,
                expected="Decimal",
            )

        # Validate total cost (should be non-negative)
        total_cost = position.get("total_cost")
        if total_cost is not None:
            if not isinstance(total_cost, (int, Decimal)):
                result.add_warning(
                    "total_cost",
                    "Total cost should be numeric",
                    value=type(total_cost).__name__,
                )
            elif total_cost < 0:
                result.add_error(
                    "total_cost", "Negative total cost", value=total_cost, expected=">= 0"
                )

        # Validate fees_paid (should be non-negative)
        fees_paid = position.get("fees_paid")
        if fees_paid is not None and isinstance(fees_paid, Decimal) and fees_paid < Decimal("0"):
            result.add_error("fees_paid", "Negative fees", value=fees_paid, expected=">= 0")

        # Track anomalies
        if result.has_errors or result.has_warnings:
            self._increment_anomaly_count(ticker)

        return result

    # -------------------------------------------------------------------------
    # Fill Data Validation
    # -------------------------------------------------------------------------

    def validate_fill_data(self, fill: dict[str, Any]) -> ValidationResult:
        """
        Validate processed fill data from Kalshi API.

        Args:
            fill: ProcessedFillData dict from kalshi_client

        Returns:
            ValidationResult with any issues found

        Validates:
            - Trade ID exists
            - Ticker exists
            - Count is positive integer
            - Prices are in valid range [0, 1]
            - Side is valid ("yes" or "no")
            - Action is valid ("buy" or "sell")

        Example:
            >>> validator = KalshiDataValidator()
            >>> fill = {
            ...     "trade_id": "abc123",
            ...     "ticker": "KXNFLGAME-25DEC25-CHI-GB",
            ...     "count": 10,
            ...     "yes_price_fixed": Decimal("0.45"),
            ...     "side": "yes",
            ...     "action": "buy",
            ... }
            >>> result = validator.validate_fill_data(fill)
        """
        trade_id = fill.get("trade_id", "unknown")
        ticker = fill.get("ticker", "unknown")
        result = ValidationResult(entity_id=f"{ticker}:{trade_id}", entity_type="fill")

        # Validate trade ID
        if not trade_id or trade_id == "unknown":
            result.add_error("trade_id", "Missing or empty trade ID")

        # Validate ticker
        if not ticker or ticker == "unknown":
            result.add_error("ticker", "Missing or empty ticker")

        # Validate count
        count = fill.get("count")
        if count is not None:
            if not isinstance(count, int):
                result.add_warning(
                    "count",
                    "Count should be integer",
                    value=type(count).__name__,
                    expected="int",
                )
            elif count <= 0:
                result.add_error("count", "Count must be positive", value=count, expected="> 0")

        # Validate prices
        yes_price = fill.get("yes_price_fixed")
        no_price = fill.get("no_price_fixed")
        if yes_price is not None:
            self.validate_price(yes_price, "yes_price_fixed", result)
        if no_price is not None:
            self.validate_price(no_price, "no_price_fixed", result)

        # Validate side
        side = fill.get("side")
        if side is not None and side not in {"yes", "no"}:
            result.add_warning(
                "side",
                "Unknown side value",
                value=side,
                expected={"yes", "no"},
            )

        # Validate action
        action = fill.get("action")
        if action is not None and action not in {"buy", "sell"}:
            result.add_warning(
                "action",
                "Unknown action value",
                value=action,
                expected={"buy", "sell"},
            )

        # Track anomalies
        if result.has_errors or result.has_warnings:
            self._increment_anomaly_count(ticker)

        return result

    # -------------------------------------------------------------------------
    # Settlement Data Validation
    # -------------------------------------------------------------------------

    def validate_settlement_data(self, settlement: dict[str, Any]) -> ValidationResult:
        """
        Validate processed settlement data from Kalshi API.

        Args:
            settlement: ProcessedSettlementData dict from kalshi_client

        Returns:
            ValidationResult with any issues found

        Validates:
            - Ticker exists
            - Market result is "yes" or "no"
            - Settlement value is either 0 or 1 (binary outcome)
            - Revenue is a valid Decimal
            - Total fees is non-negative Decimal
            - Settled time exists

        Example:
            >>> validator = KalshiDataValidator()
            >>> settlement = {
            ...     "ticker": "KXNFLGAME-25DEC25-CHI-GB",
            ...     "market_result": "yes",
            ...     "settlement_value": Decimal("1"),
            ...     "revenue": Decimal("50.00"),
            ...     "total_fees": Decimal("2.50"),
            ...     "settled_time": "2025-01-01T12:00:00Z",
            ... }
            >>> result = validator.validate_settlement_data(settlement)
        """
        ticker = settlement.get("ticker", "unknown")
        result = ValidationResult(entity_id=ticker, entity_type="settlement")

        # Validate ticker
        if not ticker or ticker == "unknown":
            result.add_error("ticker", "Missing or empty ticker")

        # Validate market result (must be "yes" or "no")
        market_result = settlement.get("market_result")
        if market_result is not None and market_result not in {"yes", "no"}:
            result.add_warning(
                "market_result",
                "Unknown market result value",
                value=market_result,
                expected={"yes", "no"},
            )

        # Validate settlement value (must be 0 or 1 for binary markets)
        settlement_value = settlement.get("settlement_value")
        if settlement_value is not None:
            if isinstance(settlement_value, Decimal):
                if settlement_value not in {Decimal("0"), Decimal("1")}:
                    result.add_error(
                        "settlement_value",
                        "Settlement value must be 0 or 1",
                        value=settlement_value,
                        expected={Decimal("0"), Decimal("1")},
                    )
            else:
                result.add_warning(
                    "settlement_value",
                    "Settlement value should be Decimal",
                    value=type(settlement_value).__name__,
                    expected="Decimal",
                )

        # Validate revenue (can be negative if position lost)
        revenue = settlement.get("revenue")
        if revenue is not None and not isinstance(revenue, Decimal):
            result.add_warning(
                "revenue",
                "Revenue should be Decimal",
                value=type(revenue).__name__,
                expected="Decimal",
            )

        # Validate total fees (should be non-negative)
        total_fees = settlement.get("total_fees")
        if total_fees is not None:
            if not isinstance(total_fees, Decimal):
                result.add_warning(
                    "total_fees",
                    "Total fees should be Decimal",
                    value=type(total_fees).__name__,
                    expected="Decimal",
                )
            elif total_fees < Decimal("0"):
                result.add_error(
                    "total_fees", "Negative total fees", value=total_fees, expected=">= 0"
                )

        # Validate settled time
        settled_time = settlement.get("settled_time")
        if not settled_time:
            result.add_warning("settled_time", "Missing settled time")

        # Track anomalies
        if result.has_errors or result.has_warnings:
            self._increment_anomaly_count(ticker)

        return result

    # -------------------------------------------------------------------------
    # Balance Validation
    # -------------------------------------------------------------------------

    def validate_balance(self, balance: Decimal | None) -> ValidationResult:
        """
        Validate account balance from Kalshi API.

        Args:
            balance: Account balance in dollars (Decimal)

        Returns:
            ValidationResult with any issues found

        Validates:
            - Balance is Decimal type (not float!)
            - Balance is non-negative
            - Balance is within reasonable bounds

        Example:
            >>> validator = KalshiDataValidator()
            >>> result = validator.validate_balance(Decimal("1234.56"))
            >>> print(result.is_valid)
            True
        """
        result = ValidationResult(entity_id="account", entity_type="balance")

        if balance is None:
            result.add_error("balance", "Balance is None")
            return result

        # Runtime type check for external data (API responses may be incorrectly typed)
        if not isinstance(balance, Decimal):
            result.add_error(  # type: ignore[unreachable]
                "balance",
                "Balance must be Decimal type (float contamination detected)",
                value=type(balance).__name__,
                expected="Decimal",
            )
            return result

        if balance < Decimal("0"):
            result.add_error("balance", "Negative balance", value=balance, expected=">= 0")

        if balance > self.MAX_REASONABLE_BALANCE:
            result.add_warning(
                "balance",
                "Unusually high balance",
                value=balance,
                expected=f"<= {self.MAX_REASONABLE_BALANCE}",
            )

        # Track anomalies
        if result.has_errors or result.has_warnings:
            self._increment_anomaly_count("account_balance")

        return result

    # -------------------------------------------------------------------------
    # Batch Validation Methods
    # -------------------------------------------------------------------------

    def validate_markets(self, markets: list[dict[str, Any]]) -> list[ValidationResult]:
        """
        Validate a batch of market data.

        Args:
            markets: List of ProcessedMarketData dicts

        Returns:
            List of ValidationResult, one per market
        """
        return [self.validate_market_data(market) for market in markets]

    def validate_positions(self, positions: list[dict[str, Any]]) -> list[ValidationResult]:
        """
        Validate a batch of position data.

        Args:
            positions: List of ProcessedPositionData dicts

        Returns:
            List of ValidationResult, one per position
        """
        return [self.validate_position_data(position) for position in positions]

    def validate_fills(self, fills: list[dict[str, Any]]) -> list[ValidationResult]:
        """
        Validate a batch of fill data.

        Args:
            fills: List of ProcessedFillData dicts

        Returns:
            List of ValidationResult, one per fill
        """
        return [self.validate_fill_data(fill) for fill in fills]

    def validate_settlements(self, settlements: list[dict[str, Any]]) -> list[ValidationResult]:
        """
        Validate a batch of settlement data.

        Args:
            settlements: List of ProcessedSettlementData dicts

        Returns:
            List of ValidationResult, one per settlement
        """
        return [self.validate_settlement_data(settlement) for settlement in settlements]

    # -------------------------------------------------------------------------
    # Summary Methods
    # -------------------------------------------------------------------------

    def get_validation_summary(self, results: list[ValidationResult]) -> dict[str, Any]:
        """
        Generate a summary of validation results.

        Args:
            results: List of ValidationResult objects

        Returns:
            Summary dict with counts and statistics

        Example:
            >>> results = validator.validate_markets(markets)
            >>> summary = validator.get_validation_summary(results)
            >>> print(summary["error_count"])
        """
        total = len(results)
        valid_count = sum(1 for r in results if r.is_valid)
        error_count = sum(1 for r in results if r.has_errors)
        warning_count = sum(1 for r in results if r.has_warnings and not r.has_errors)

        all_errors = [
            {"entity": r.entity_id, "issue": str(issue)} for r in results for issue in r.errors
        ]

        all_warnings = [
            {"entity": r.entity_id, "issue": str(issue)} for r in results for issue in r.warnings
        ]

        return {
            "total": total,
            "valid_count": valid_count,
            "error_count": error_count,
            "warning_count": warning_count,
            "valid_percentage": (valid_count / total * 100) if total > 0 else 100,
            "errors": all_errors[:10],  # Limit to first 10
            "warnings": all_warnings[:10],  # Limit to first 10
            "anomaly_counts": self.get_all_anomaly_counts(),
        }
