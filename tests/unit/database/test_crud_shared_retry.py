"""Unit tests for the SCD race-prevention retry helper.

Covers ``retry_on_scd_unique_conflict`` in ``precog.database.crud_shared``.

These tests use direct stubs (no DB) to exercise:
    - Happy path: operation succeeds on first attempt, no retry.
    - Targeted retry: operation raises matching UniqueViolation on attempt 1,
      succeeds on attempt 2. WARNING logged exactly once.
    - Non-matching constraint: operation raises UniqueViolation with a
      DIFFERENT constraint_name. Helper re-raises immediately, NO retry,
      NO warning log.
    - Different IntegrityError subclass (CheckViolation): no retry, no warning.
    - Retry exhaustion: matching UniqueViolation on both attempts. ERROR logged
      once, original exception re-raised.
    - Generic exception: arbitrary exception in operation re-raises immediately
      without retry.
    - Logger override: warnings/errors route to caller-supplied logger.
    - Business key in logs: identifiers appear in WARNING/ERROR records.

Reference: Issue #613 (Holden's seven conditions, Condition 6).
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock, Mock

import psycopg2.errors
import pytest

from precog.database.crud_shared import retry_on_scd_unique_conflict
from tests.unit.database._psycopg2_stubs import (
    _make_check_violation,
    _make_unique_violation,
)

# =============================================================================
# Happy path
# =============================================================================


@pytest.mark.unit
class TestRetryHelperHappyPath:
    """First attempt succeeds; helper returns the value, no retry, no logs."""

    def test_returns_value_when_operation_succeeds_first_attempt(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Helper forwards the return value and does not invoke operation twice."""
        operation = MagicMock(return_value=42)

        with caplog.at_level(logging.WARNING):
            result = retry_on_scd_unique_conflict(
                operation,
                "idx_balance_unique_current",
                business_key={"platform_id": "kalshi"},
            )

        assert result == 42
        assert operation.call_count == 1
        # No WARNING or ERROR records should be emitted on the happy path.
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


# =============================================================================
# Targeted retry path
# =============================================================================


@pytest.mark.unit
class TestRetryHelperTargetedRetry:
    """Matching UniqueViolation on attempt 1 -> retry -> success on attempt 2."""

    def test_retries_once_on_matching_constraint_then_succeeds(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Operation called twice, value from second call returned."""
        attempts: list[int] = []

        def operation() -> int:
            attempts.append(len(attempts) + 1)
            if len(attempts) == 1:
                raise _make_unique_violation("idx_balance_unique_current")
            return 99

        with caplog.at_level(logging.WARNING):
            result = retry_on_scd_unique_conflict(
                operation,
                "idx_balance_unique_current",
                business_key={"platform_id": "kalshi"},
            )

        assert result == 99
        assert attempts == [1, 2]

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1, "expected exactly one WARNING between attempts"
        msg = warnings[0].getMessage()
        assert "idx_balance_unique_current" in msg
        assert "kalshi" in msg

        # No ERROR records should be emitted when the retry succeeds.
        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert errors == []

    def test_business_key_appears_in_warning_log(self, caplog: pytest.LogCaptureFixture) -> None:
        """Business key dict is rendered into the WARNING message."""
        call_count = {"n": 0}

        def operation() -> str:
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise _make_unique_violation("idx_balance_unique_current")
            return "ok"

        with caplog.at_level(logging.WARNING):
            retry_on_scd_unique_conflict(
                operation,
                "idx_balance_unique_current",
                business_key={"platform_id": "polymarket", "currency": "USDC"},
            )

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        msg = warnings[0].getMessage()
        assert "polymarket" in msg
        assert "USDC" in msg


# =============================================================================
# Non-matching constraint discrimination
# =============================================================================


@pytest.mark.unit
class TestRetryHelperConstraintDiscrimination:
    """Wrong constraint_name -> immediate re-raise, no retry, no warning."""

    def test_unique_violation_on_different_constraint_reraises_immediately(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Different constraint_name -> no retry, no warning, original re-raised."""
        operation = MagicMock(side_effect=_make_unique_violation("some_other_index"))

        with caplog.at_level(logging.WARNING):
            with pytest.raises(psycopg2.errors.UniqueViolation):
                retry_on_scd_unique_conflict(
                    operation,
                    "idx_balance_unique_current",
                    business_key={"platform_id": "kalshi"},
                )

        assert operation.call_count == 1, "operation must NOT be retried"
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_unique_violation_with_none_constraint_name_reraises(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """diag.constraint_name=None must NOT match a real constraint_name."""
        operation = MagicMock(side_effect=_make_unique_violation(None))

        with caplog.at_level(logging.WARNING):
            with pytest.raises(psycopg2.errors.UniqueViolation):
                retry_on_scd_unique_conflict(
                    operation,
                    "idx_balance_unique_current",
                )

        assert operation.call_count == 1
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_check_violation_reraises_without_retry(self, caplog: pytest.LogCaptureFixture) -> None:
        """CheckViolation is a sibling IntegrityError; helper must NOT retry it.

        This is the critical safety property: a buggy API response sending a
        negative balance would trip a CHECK constraint. A bare except on
        IntegrityError would mask this as a "SCD race retry, both failed"
        error -- exactly the confusion Holden's Condition 1 prevents.
        """
        operation = MagicMock(side_effect=_make_check_violation())

        with caplog.at_level(logging.WARNING):
            with pytest.raises(psycopg2.errors.CheckViolation):
                retry_on_scd_unique_conflict(
                    operation,
                    "idx_balance_unique_current",
                )

        assert operation.call_count == 1
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_attempt1_matching_attempt2_different_constraint(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Attempt 1 hits idx_balance_unique_current (matches -> retry);
        attempt 2 hits a DIFFERENT unique constraint.

        Verifies (Glokta Issue 2 / FIX 2 asymmetric-logging branch):
            - exactly 2 operation calls
            - exactly 1 WARNING (retry between attempts)
            - exactly 1 ERROR (asymmetric attempt-2 transition)
            - second exception is re-raised
            - __cause__ is set to the first exception
        """
        first_exc = _make_unique_violation("idx_balance_unique_current")
        second_exc = _make_unique_violation("some_other_unrelated_index")
        operation = Mock(side_effect=[first_exc, second_exc])

        with caplog.at_level(logging.WARNING):
            with pytest.raises(psycopg2.errors.UniqueViolation) as exc_info:
                retry_on_scd_unique_conflict(
                    operation,
                    "idx_balance_unique_current",
                    business_key={"platform_id": "kalshi"},
                )

        assert operation.call_count == 2
        assert exc_info.value is second_exc
        assert exc_info.value.__cause__ is first_exc

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(warnings) == 1, "expected exactly one WARNING between attempts"
        assert len(errors) == 1, "expected exactly one ERROR on asymmetric attempt-2 failure"
        assert "DIFFERENT constraint" in errors[0].getMessage()

    def test_attempt1_matching_attempt2_non_unique_exception(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Attempt 1 hits idx_balance_unique_current (matches -> retry);
        attempt 2 raises a completely unrelated exception type.

        Verifies (Glokta Issue 2 / FIX 2 non-UniqueViolation branch):
            - exactly 2 operation calls
            - exactly 1 WARNING (retry between attempts)
            - exactly 1 ERROR (asymmetric attempt-2 transition)
            - the non-UniqueViolation exception is re-raised
            - __cause__ is set to the first (UniqueViolation) exception
        """
        first_exc = _make_unique_violation("idx_balance_unique_current")
        second_exc = RuntimeError("unrelated retry failure")
        operation = Mock(side_effect=[first_exc, second_exc])

        with caplog.at_level(logging.WARNING):
            with pytest.raises(RuntimeError, match="unrelated retry failure") as exc_info:
                retry_on_scd_unique_conflict(
                    operation,
                    "idx_balance_unique_current",
                    business_key={"platform_id": "kalshi"},
                )

        assert operation.call_count == 2
        assert exc_info.value is second_exc
        assert exc_info.value.__cause__ is first_exc

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(warnings) == 1
        assert len(errors) == 1
        assert "non-UniqueViolation" in errors[0].getMessage()


# =============================================================================
# Retry exhaustion
# =============================================================================


@pytest.mark.unit
class TestRetryHelperRetryExhaustion:
    """Two consecutive matching UniqueViolations -> ERROR + re-raise original."""

    def test_two_matching_violations_logs_error_and_reraises(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """ERROR logged once, second exception re-raised, no third attempt."""
        first_exc = _make_unique_violation("idx_balance_unique_current")
        second_exc = _make_unique_violation("idx_balance_unique_current")
        operation = MagicMock(side_effect=[first_exc, second_exc])

        with caplog.at_level(logging.WARNING):
            with pytest.raises(psycopg2.errors.UniqueViolation) as exc_info:
                retry_on_scd_unique_conflict(
                    operation,
                    "idx_balance_unique_current",
                    business_key={"platform_id": "kalshi"},
                )

        assert operation.call_count == 2, "must attempt exactly twice (1 + 1 retry)"
        # The re-raised exception is the SECOND one (current exception in
        # the inner try block), but its identity preserves the stack.
        assert exc_info.value is second_exc

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(warnings) == 1, "one WARNING between attempts"
        assert len(errors) == 1, "one ERROR on exhaustion"

        err_msg = errors[0].getMessage()
        assert "idx_balance_unique_current" in err_msg
        assert "kalshi" in err_msg

    def test_retry_exhaustion_chains_first_exception_via_cause(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """On retry exhaustion, verify that attempt 2's exception carries
        attempt 1's exception in ``__cause__`` (explicit PEP 3134 chain).

        Without explicit chaining, attempt 1's exception would be lost to
        garbage collection because its ``except`` clause exits cleanly
        before attempt 2 runs (severing Python's automatic ``__context__``
        chain). This test verifies FIX 1 keeps the first exception on the
        raised exception's ``__cause__`` slot for postmortem analysis.
        """
        first_exc = _make_unique_violation("idx_balance_unique_current")
        second_exc = _make_unique_violation("idx_balance_unique_current")
        operation = Mock(side_effect=[first_exc, second_exc])

        with caplog.at_level(logging.WARNING):
            with pytest.raises(psycopg2.errors.UniqueViolation) as exc_info:
                retry_on_scd_unique_conflict(
                    operation,
                    "idx_balance_unique_current",
                    business_key={"platform_id": "kalshi"},
                )

        assert exc_info.value is second_exc
        # Explicit PEP 3134 chain -- NOT the automatic __context__ chain
        # (which is severed by the clean exit of attempt 1's except clause).
        assert exc_info.value.__cause__ is first_exc
        assert operation.call_count == 2


# =============================================================================
# Input validation (FIX 3 / Marvin Scenario 12)
# =============================================================================


@pytest.mark.unit
class TestRetryHelperInputValidation:
    """constraint_name must be a non-empty string; otherwise ValueError."""

    def test_none_constraint_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            retry_on_scd_unique_conflict(
                lambda: None,
                None,  # type: ignore[arg-type]
            )

    def test_empty_constraint_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            retry_on_scd_unique_conflict(
                lambda: None,
                "",
            )

    def test_non_string_constraint_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            retry_on_scd_unique_conflict(
                lambda: None,
                42,  # type: ignore[arg-type]
            )


# =============================================================================
# Generic exception passthrough
# =============================================================================


@pytest.mark.unit
class TestRetryHelperGenericException:
    """Non-IntegrityError exceptions propagate immediately without retry."""

    def test_value_error_propagates_immediately(self, caplog: pytest.LogCaptureFixture) -> None:
        """A ValueError from operation is not caught -- single attempt, no logs."""
        operation = MagicMock(side_effect=ValueError("validation failed"))

        with caplog.at_level(logging.WARNING):
            with pytest.raises(ValueError, match="validation failed"):
                retry_on_scd_unique_conflict(
                    operation,
                    "idx_balance_unique_current",
                )

        assert operation.call_count == 1
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_runtime_error_propagates_immediately(self, caplog: pytest.LogCaptureFixture) -> None:
        """Any unrelated exception type propagates without retry."""
        operation = MagicMock(side_effect=RuntimeError("boom"))

        with caplog.at_level(logging.WARNING):
            with pytest.raises(RuntimeError, match="boom"):
                retry_on_scd_unique_conflict(
                    operation,
                    "idx_balance_unique_current",
                )

        assert operation.call_count == 1


# =============================================================================
# Logger override
# =============================================================================


@pytest.mark.unit
class TestRetryHelperLoggerOverride:
    """logger_override routes WARNING/ERROR to the caller's logger."""

    def test_logger_override_receives_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A custom logger captures the retry WARNING message."""
        custom_logger = logging.getLogger("test.precog.retry.override")
        # Ensure caplog captures records from this logger.
        custom_logger.propagate = True

        first_call = {"done": False}

        def operation() -> int:
            if not first_call["done"]:
                first_call["done"] = True
                raise _make_unique_violation("idx_balance_unique_current")
            return 7

        with caplog.at_level(logging.WARNING, logger="test.precog.retry.override"):
            result = retry_on_scd_unique_conflict(
                operation,
                "idx_balance_unique_current",
                business_key={"platform_id": "kalshi"},
                logger_override=custom_logger,
            )

        assert result == 7
        warnings = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING and r.name == "test.precog.retry.override"
        ]
        assert len(warnings) == 1


# =============================================================================
# Optional business_key
# =============================================================================


@pytest.mark.unit
class TestRetryHelperOptionalBusinessKey:
    """business_key=None still produces a valid log message."""

    def test_none_business_key_renders_safely(self, caplog: pytest.LogCaptureFixture) -> None:
        """The helper does not crash when business_key is omitted."""
        first_call = {"done": False}

        def operation() -> str:
            if not first_call["done"]:
                first_call["done"] = True
                raise _make_unique_violation("idx_balance_unique_current")
            return "ok"

        with caplog.at_level(logging.WARNING):
            result = retry_on_scd_unique_conflict(
                operation,
                "idx_balance_unique_current",
            )

        assert result == "ok"
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        # Empty dict renders as "{}" -- helper must not raise on missing key.
        assert "idx_balance_unique_current" in warnings[0].getMessage()


# =============================================================================
# Type / parameter sanity
# =============================================================================


@pytest.mark.unit
class TestRetryHelperReturnTypes:
    """The helper is generic over the operation's return type."""

    def test_returns_none_when_operation_returns_none(self) -> None:
        operation = MagicMock(return_value=None)
        result = retry_on_scd_unique_conflict(operation, "idx_balance_unique_current")
        assert result is None

    def test_returns_dict_when_operation_returns_dict(self) -> None:
        payload: dict[str, Any] = {"id": 1, "platform_id": "kalshi"}
        operation = MagicMock(return_value=payload)
        result = retry_on_scd_unique_conflict(operation, "idx_balance_unique_current")
        assert result is payload
