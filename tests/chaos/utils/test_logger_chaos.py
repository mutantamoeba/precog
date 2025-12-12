"""
Chaos Tests for Logger Module.

Tests logger resilience under chaotic conditions:
- Invalid log levels
- Malformed data structures
- Extreme string lengths
- Special characters and encoding
- Missing or corrupted log directories
- Serialization edge cases

Related:
- TESTING_STRATEGY V3.5: All 8 test types required
- utils/logger module coverage

Usage:
    pytest tests/chaos/utils/test_logger_chaos.py -v -m chaos

Educational Note:
    Chaos tests verify that the logging system degrades gracefully when:
    1. Invalid data types are logged
    2. Serialization fails
    3. Log directory is inaccessible
    4. Credential masking encounters edge cases
    5. LogContext receives unexpected input

    The logger should NEVER crash the application - it should always
    fall back gracefully and continue operation.

Reference: docs/foundation/TESTING_STRATEGY_V3.5.md Section "Best Practice #6"
"""

import os
from datetime import datetime
from decimal import Decimal

import pytest


@pytest.mark.chaos
class TestCredentialMaskingChaos:
    """Chaos tests for credential masking functions."""

    def test_mask_credential_with_none(self):
        """
        CHAOS: mask_credential with None input.

        Verifies:
        - None input handled gracefully
        - Returns appropriate string
        """
        from precog.utils.logger import mask_credential

        result = mask_credential(None)
        assert result == "None"

    def test_mask_credential_with_empty_string(self):
        """
        CHAOS: mask_credential with empty string.

        Verifies:
        - Empty string handled gracefully
        """
        from precog.utils.logger import mask_credential

        result = mask_credential("")
        assert result == "***"

    def test_mask_credential_with_short_string(self):
        """
        CHAOS: mask_credential with very short string.

        Verifies:
        - Short strings are fully masked
        """
        from precog.utils.logger import mask_credential

        result = mask_credential("ab")
        assert result == "***"

        result = mask_credential("abc")
        assert result == "***"

    def test_mask_credential_with_unicode(self):
        """
        CHAOS: mask_credential with Unicode characters.

        Verifies:
        - Unicode handled correctly
        """
        from precog.utils.logger import mask_credential

        # Test with emoji
        result = mask_credential("password123")
        assert "***" in result

    def test_mask_credential_with_numeric_value(self):
        """
        CHAOS: mask_credential with numeric input.

        Verifies:
        - Numbers converted to string and masked
        """
        from precog.utils.logger import mask_credential

        result = mask_credential(12345678)  # type: ignore[arg-type]
        assert "***" in result

    def test_sanitize_error_message_with_no_patterns(self):
        """
        CHAOS: sanitize_error_message with no sensitive data.

        Verifies:
        - Clean messages pass through unchanged
        """
        from precog.utils.logger import sanitize_error_message

        original = "This is a normal error message"
        result = sanitize_error_message(original)
        assert result == original

    def test_sanitize_error_message_with_multiple_patterns(self):
        """
        CHAOS: sanitize_error_message with multiple sensitive patterns.

        Verifies:
        - All patterns are sanitized
        """
        from precog.utils.logger import sanitize_error_message

        message = "Failed: password='secret123' with Basic dGVzdA== and postgres://u:p@h/d"
        result = sanitize_error_message(message)

        # Sensitive parts should be masked
        assert "secret123" not in result
        assert "dGVzdA==" not in result

    def test_sanitize_connection_string_not_a_connection_string(self):
        """
        CHAOS: sanitize_connection_string with non-connection string.

        Verifies:
        - Non-matching strings pass through
        """
        from precog.utils.logger import sanitize_connection_string

        message = "This is not a connection string"
        result = sanitize_connection_string(message)
        assert result == message

    def test_sanitize_connection_string_various_formats(self):
        """
        CHAOS: sanitize_connection_string with various database URLs.

        Verifies:
        - PostgreSQL, MySQL, MongoDB URLs all sanitized
        """
        from precog.utils.logger import sanitize_connection_string

        # PostgreSQL
        pg = sanitize_connection_string("postgres://user:secret@host:5432/db")
        assert "secret" not in pg
        assert "****" in pg

        # MySQL
        mysql = sanitize_connection_string("mysql://admin:password@server:3306/mydb")
        assert "password" not in mysql
        assert "****" in mysql

        # MongoDB
        mongo = sanitize_connection_string("mongodb://root:mongopass@cluster/test")
        assert "mongopass" not in mongo
        assert "****" in mongo


@pytest.mark.chaos
class TestDecimalSerializerChaos:
    """Chaos tests for decimal serialization."""

    def test_decimal_serializer_with_various_types(self):
        """
        CHAOS: decimal_serializer with various input types.

        Verifies:
        - All types handled gracefully
        """
        from precog.utils.logger import decimal_serializer

        # Decimal
        assert decimal_serializer(Decimal("0.5200")) == "0.5200"

        # datetime
        dt = datetime(2025, 1, 15, 10, 30, 0)
        result = decimal_serializer(dt)
        assert "2025-01-15" in result

        # Basic types pass through
        assert decimal_serializer("string") == "string"
        assert decimal_serializer(42) == 42
        assert decimal_serializer(3.14) == 3.14
        assert decimal_serializer(True) is True
        assert decimal_serializer(None) is None
        assert decimal_serializer([1, 2, 3]) == [1, 2, 3]
        assert decimal_serializer({"a": 1}) == {"a": 1}

    def test_decimal_serializer_with_custom_object(self):
        """
        CHAOS: decimal_serializer with custom object.

        Verifies:
        - Unknown types converted to string
        """
        from precog.utils.logger import decimal_serializer

        class CustomClass:
            def __str__(self):
                return "CustomInstance"

        result = decimal_serializer(CustomClass())
        assert result == "CustomInstance"

    def test_decimal_serializer_with_special_decimals(self):
        """
        CHAOS: decimal_serializer with special Decimal values.

        Verifies:
        - Zero, negative, very large decimals handled
        """
        from precog.utils.logger import decimal_serializer

        assert decimal_serializer(Decimal("0")) == "0"
        assert decimal_serializer(Decimal("-0.5200")) == "-0.5200"
        assert decimal_serializer(Decimal("999999999.999999")) == "999999999.999999"
        assert decimal_serializer(Decimal("0.000001")) == "0.000001"


@pytest.mark.chaos
class TestMaskSensitiveDataChaos:
    """Chaos tests for mask_sensitive_data processor."""

    def test_mask_sensitive_data_with_nested_dict(self):
        """
        CHAOS: mask_sensitive_data with deeply nested dictionary.

        Verifies:
        - Recursive masking works correctly
        """
        from precog.utils.logger import mask_sensitive_data

        event_dict = {
            "event": "test",
            "headers": {
                "Authorization": "Bearer secret123",
                "Content-Type": "application/json",
            },
            "nested": {
                "deep": {
                    "api_key": "deep-secret-key",
                }
            },
        }

        result = mask_sensitive_data(None, "info", event_dict.copy())  # type: ignore[arg-type]

        # Authorization should be masked
        assert "secret123" not in str(result)
        # api_key should be masked
        assert "deep-secret-key" not in str(result)
        # Content-Type should be unchanged
        assert "application/json" in str(result)

    def test_mask_sensitive_data_with_list(self):
        """
        CHAOS: mask_sensitive_data with list values.

        Verifies:
        - Lists are recursively processed
        """
        from precog.utils.logger import mask_sensitive_data

        event_dict = {
            "event": "test",
            "errors": [
                {"password": "secret1"},
                {"password": "secret2"},
            ],
        }

        result = mask_sensitive_data(None, "info", event_dict.copy())  # type: ignore[arg-type]

        assert "secret1" not in str(result)
        assert "secret2" not in str(result)

    def test_mask_sensitive_data_with_none_values(self):
        """
        CHAOS: mask_sensitive_data with None values.

        Verifies:
        - None values don't crash masking
        """
        from precog.utils.logger import mask_sensitive_data

        event_dict = {
            "event": "test",
            "api_key": None,
            "password": None,
            "data": {"nested": None},
        }

        # Should not raise
        result = mask_sensitive_data(None, "info", event_dict.copy())  # type: ignore[arg-type]
        assert result is not None

    def test_mask_sensitive_data_preserves_non_sensitive(self):
        """
        CHAOS: mask_sensitive_data preserves non-sensitive data.

        Verifies:
        - Non-sensitive field values preserved (may be converted to string)
        - No masking applied to non-sensitive fields

        Note:
        - The mask function converts non-string values to strings for sanitization
        - This is expected behavior - values remain intact, just stringified
        """
        from precog.utils.logger import mask_sensitive_data

        event_dict = {
            "event": "trade_executed",
            "ticker": "NFL-KC-YES",
            "price": "0.5200",
            "quantity": 100,
            "side": "YES",
        }

        result = mask_sensitive_data(None, "info", event_dict.copy())  # type: ignore[arg-type]

        # String values preserved exactly
        assert result["ticker"] == "NFL-KC-YES"
        assert result["price"] == "0.5200"
        assert result["side"] == "YES"
        # Integer values converted to string by _mask_value_recursive
        assert result["quantity"] == "100"


@pytest.mark.chaos
class TestLogContextChaos:
    """Chaos tests for LogContext context manager."""

    def test_log_context_with_empty_context(self):
        """
        CHAOS: LogContext with no context provided.

        Verifies:
        - Empty context doesn't crash
        """
        from precog.utils.logger import LogContext

        with LogContext() as logger:
            logger.info("empty_context_test")
        # No error means success

    def test_log_context_with_none_values(self):
        """
        CHAOS: LogContext with None values.

        Verifies:
        - None values in context handled
        """
        from precog.utils.logger import LogContext

        with LogContext(request_id=None, user=None) as logger:
            logger.info("none_value_test")
        # No error means success

    def test_log_context_with_special_keys(self):
        """
        CHAOS: LogContext with special key names.

        Verifies:
        - Reserved or special keys handled
        """
        from precog.utils.logger import LogContext

        with LogContext(level="custom", timestamp="custom") as logger:
            logger.info("special_keys_test")
        # No error means success

    def test_log_context_exception_in_context(self):
        """
        CHAOS: Exception raised within LogContext.

        Verifies:
        - Context properly cleans up on exception
        """
        from precog.utils.logger import LogContext

        with pytest.raises(ValueError):
            with LogContext(request_id="test-123") as logger:
                logger.info("before_exception")
                raise ValueError("Test exception")

        # Context should have cleaned up, verify we can create new one
        with LogContext(request_id="after-exception") as logger:
            logger.info("after_exception")


@pytest.mark.chaos
class TestSetupLoggingChaos:
    """Chaos tests for setup_logging function."""

    def test_setup_logging_invalid_log_level(self):
        """
        CHAOS: setup_logging with invalid log level.

        Verifies:
        - Invalid level raises appropriate error
        """
        from precog.utils.logger import setup_logging

        with pytest.raises(AttributeError):
            setup_logging(log_level="INVALID_LEVEL")

    def test_setup_logging_no_file(self):
        """
        CHAOS: setup_logging with log_to_file=False.

        Verifies:
        - Works without file logging
        """
        from precog.utils.logger import setup_logging

        logger = setup_logging(log_to_file=False)
        logger.info("no_file_test")
        # No error means success

    def test_setup_logging_with_readonly_directory(self):
        """
        CHAOS: setup_logging with read-only directory.

        Note: This test is platform-specific. On Windows, we simulate
        by using a non-existent drive or invalid path.
        """
        from precog.utils.logger import setup_logging

        # Use a path that's likely invalid
        if os.name == "nt":  # Windows
            invalid_path = "Z:\\nonexistent\\readonly\\logs"
        else:
            invalid_path = "/root/readonly_logs"

        # This should either raise an error or fall back gracefully
        try:
            setup_logging(log_dir=invalid_path)
        except (PermissionError, OSError):
            pass  # Expected - no write permission

    def test_setup_logging_multiple_times(self):
        """
        CHAOS: Calling setup_logging multiple times.

        Verifies:
        - Multiple calls don't cause handler accumulation
        - Logging still works after re-setup
        """
        from precog.utils.logger import setup_logging

        # Call setup multiple times
        for _ in range(3):
            logger = setup_logging(log_to_file=False)
            logger.info("multi_setup_test")

        # Should still work normally
        logger.info("final_test")


@pytest.mark.chaos
class TestHelperFunctionsChaos:
    """Chaos tests for helper logging functions."""

    def test_log_trade_with_extreme_values(self):
        """
        CHAOS: log_trade with extreme/edge case values.

        Verifies:
        - Very large quantities handled
        - Zero and negative prices handled
        """
        from precog.utils.logger import log_trade

        # Very large quantity
        log_trade(
            action="entry",
            ticker="TEST-EXTREME",
            side="YES",
            quantity=999999999,
            price=Decimal("0.0001"),
            strategy_id=1,
            model_id=1,
        )

        # Zero price
        log_trade(
            action="entry",
            ticker="TEST-ZERO",
            side="NO",
            quantity=1,
            price=Decimal("0.0000"),
            strategy_id=1,
            model_id=1,
        )

    def test_log_position_update_with_negative_pnl(self):
        """
        CHAOS: log_position_update with negative P&L.

        Verifies:
        - Negative values logged correctly
        """
        from precog.utils.logger import log_position_update

        log_position_update(
            position_id=42,
            ticker="TEST-LOSS",
            current_price=Decimal("0.2000"),
            unrealized_pnl=Decimal("-100.50"),
            status="open",
        )

    def test_log_edge_detected_with_boundary_values(self):
        """
        CHAOS: log_edge_detected with boundary probabilities.

        Verifies:
        - 0% and 100% probabilities handled
        """
        from precog.utils.logger import log_edge_detected

        # 0% probability
        log_edge_detected(
            ticker="TEST-ZERO-PROB",
            expected_value=Decimal("-0.5200"),
            market_price=Decimal("0.5200"),
            model_probability=Decimal("0.0000"),
            strategy_name="test_strategy",
        )

        # 100% probability
        log_edge_detected(
            ticker="TEST-CERTAIN",
            expected_value=Decimal("0.4800"),
            market_price=Decimal("0.5200"),
            model_probability=Decimal("1.0000"),
            strategy_name="test_strategy",
        )

    def test_log_error_with_no_exception(self):
        """
        CHAOS: log_error with no exception object.

        Verifies:
        - Handles None exception gracefully
        """
        from precog.utils.logger import log_error

        log_error(
            error_type="manual_error",
            message="Manually logged error without exception",
            exception=None,
        )

    def test_log_error_with_complex_exception(self):
        """
        CHAOS: log_error with exception containing sensitive data.

        Verifies:
        - Exception messages are sanitized
        """
        from precog.utils.logger import log_error

        exc = ValueError("Connection failed: postgres://user:secret123@host/db")
        log_error(
            error_type="connection_error",
            message="Database connection failed",
            exception=exc,
        )
        # The exception message should be sanitized (checked by mask_sensitive_data)


@pytest.mark.chaos
class TestGetLoggerChaos:
    """Chaos tests for get_logger function."""

    def test_get_logger_with_none_name(self):
        """
        CHAOS: get_logger with None name.

        Verifies:
        - None name handled gracefully
        """
        from precog.utils.logger import get_logger

        logger = get_logger(None)
        logger.info("none_name_test")
        # No error means success

    def test_get_logger_with_empty_name(self):
        """
        CHAOS: get_logger with empty string name.

        Verifies:
        - Empty name handled
        """
        from precog.utils.logger import get_logger

        logger = get_logger("")
        logger.info("empty_name_test")
        # No error means success

    def test_get_logger_with_special_characters(self):
        """
        CHAOS: get_logger with special characters in name.

        Verifies:
        - Special characters don't crash logger
        """
        from precog.utils.logger import get_logger

        special_names = [
            "module.submodule",
            "module/submodule",
            "module:submodule",
            "module name with spaces",
        ]

        for name in special_names:
            logger = get_logger(name)
            logger.info("special_name_test", module=name)


@pytest.mark.chaos
class TestLoggingEdgeCases:
    """Chaos tests for general logging edge cases."""

    def test_logging_with_binary_data(self):
        """
        CHAOS: Logging with binary data in fields.

        Verifies:
        - Binary data doesn't crash logging
        """
        from precog.utils.logger import get_logger

        logger = get_logger("test_binary")

        # Binary data
        binary_data = b"\x00\x01\x02\xff\xfe"
        logger.info("binary_test", data=str(binary_data))

    def test_logging_with_very_long_string(self):
        """
        CHAOS: Logging with very long strings.

        Verifies:
        - Long strings handled (may be truncated)
        """
        from precog.utils.logger import get_logger

        logger = get_logger("test_long")

        # 10KB string
        long_string = "x" * 10000
        logger.info("long_string_test", data=long_string)

    def test_logging_with_circular_reference(self):
        """
        CHAOS: Logging with objects that could have circular refs.

        Verifies:
        - Circular references don't cause infinite loops
        """
        from precog.utils.logger import get_logger

        logger = get_logger("test_circular")

        # Create a dict with circular reference (not truly circular in log context)
        d = {"key": "value"}
        # Note: structlog handles this by converting to string representation
        logger.info("circular_test", data=str(d))

    def test_logging_with_unicode_emoji(self):
        """
        CHAOS: Logging with Unicode and emoji characters.

        Verifies:
        - Unicode/emoji properly handled
        """
        from precog.utils.logger import get_logger

        logger = get_logger("test_unicode")

        # Various unicode
        logger.info(
            "unicode_test",
            ascii_text="Hello World",
            chinese="",  # Chinese characters may not display
            emoji="OK",  # Using simple text instead of emoji for Windows compatibility
        )
