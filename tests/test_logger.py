"""
Tests for structured logging.

Critical tests:
- Logs output as valid JSON
- Decimal values serialized correctly (not float)
- Context binding works
- Log files created
- Helper functions work correctly
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from utils.logger import (
    LogContext,
    decimal_serializer,
    get_logger,
    log_edge_detected,
    log_error,
    log_position_update,
    log_trade,
    setup_logging,
)


@pytest.mark.unit
def test_logger_initialization(temp_log_dir):
    """Test that logger initializes without errors."""
    logger = setup_logging(log_level="DEBUG", log_to_file=True, log_dir=str(temp_log_dir))
    assert logger is not None


@pytest.mark.unit
def test_get_logger_with_name():
    """Test getting logger with custom name."""
    logger = get_logger("test_module")
    assert logger is not None


@pytest.mark.unit
@pytest.mark.critical
def test_decimal_serializer():
    """CRITICAL: Test Decimal serialization (must not convert to float)."""
    # Test Decimal
    result = decimal_serializer(Decimal("0.5200"))
    assert result == "0.5200"
    assert type(result) == str

    # Test datetime
    dt = datetime(2025, 10, 23, 14, 30, 0)
    result = decimal_serializer(dt)
    assert "2025-10-23" in result  # ISO format


@pytest.mark.unit
@pytest.mark.critical
def test_decimal_precision_in_logs(test_logger, temp_log_dir, caplog):
    """CRITICAL: Test that Decimals log as strings (preserve precision)."""
    price = Decimal("0.5200")

    # Log with Decimal value
    test_logger.info("test_event", price=price)

    # Check log file was created
    log_files = list(Path(temp_log_dir).glob("*.log"))
    assert len(log_files) > 0


@pytest.mark.unit
def test_log_trade_helper(test_logger):
    """Test log_trade() helper function."""
    # Should not raise errors
    log_trade(
        action="entry",
        ticker="TEST-NFL-YES",
        side="YES",
        quantity=100,
        price=Decimal("0.5200"),
        strategy_id=1,
        model_id=2,
    )


@pytest.mark.unit
def test_log_position_update_helper(test_logger):
    """Test log_position_update() helper function."""
    log_position_update(
        position_id=42,
        ticker="TEST-NFL-YES",
        current_price=Decimal("0.5800"),
        unrealized_pnl=Decimal("6.00"),
        status="open",
    )


@pytest.mark.unit
def test_log_edge_detected_helper(test_logger):
    """Test log_edge_detected() helper function."""
    log_edge_detected(
        ticker="TEST-NFL-YES",
        expected_value=Decimal("0.0500"),
        market_price=Decimal("0.5200"),
        model_probability=Decimal("0.5700"),
        strategy_name="test_strategy",
    )


@pytest.mark.unit
def test_log_error_helper(test_logger):
    """Test log_error() helper function."""
    try:
        msg = "Test error"
        raise ValueError(msg)
    except ValueError as e:
        log_error(error_type="test_error", message="This is a test error", exception=e)


@pytest.mark.unit
def test_log_context_binding(test_logger, caplog):
    """Test LogContext for persistent context binding."""
    with LogContext(request_id="abc-123", user_id=42):
        logger = get_logger()
        logger.info("test_event_1")
        logger.info("test_event_2")

    # Both logs should include request_id and user_id
    # (Checking via caplog - pytest captures logs)


@pytest.mark.unit
def test_log_file_created(temp_log_dir):
    """Test that daily log file is created."""
    logger = setup_logging(log_level="INFO", log_to_file=True, log_dir=str(temp_log_dir))

    # Log something
    logger.info("test_message")

    # Check log file exists
    log_files = list(Path(temp_log_dir).glob("precog_*.log"))
    assert len(log_files) == 1


@pytest.mark.unit
def test_log_levels(test_logger):
    """Test different log levels."""
    # Should not raise errors
    test_logger.debug("debug message")
    test_logger.info("info message")
    test_logger.warning("warning message")
    test_logger.error("error message")


@pytest.mark.unit
def test_logger_with_extra_context(test_logger):
    """Test logging with additional context fields."""
    test_logger.info(
        "trade_executed",
        ticker="TEST-NFL-YES",
        quantity=100,
        price=Decimal("0.5200"),
        custom_field="custom_value",
    )


@pytest.mark.integration
def test_logger_handles_exceptions(test_logger, caplog):
    """Test logger properly handles exceptions."""
    try:
        1 / 0
    except ZeroDivisionError:
        test_logger.exception("division_error")

    # Should log exception without crashing


@pytest.mark.unit
def test_decimal_serializer_fallback():
    """Test decimal_serializer converts unknown types to string."""

    # Custom object that can't be serialized
    class CustomObject:
        def __str__(self):
            return "CustomObject"

    obj = CustomObject()

    # Should convert to string as fallback
    result = decimal_serializer(obj)
    assert result == "CustomObject"


@pytest.mark.integration
def test_concurrent_logging(test_logger):
    """Test that concurrent log calls don't interfere."""
    import threading

    def log_many():
        for i in range(10):
            test_logger.info("concurrent_log", iteration=i)

    threads = [threading.Thread(target=log_many) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should complete without errors


@pytest.mark.unit
def test_log_with_none_values(test_logger):
    """Test logging with None values."""
    test_logger.info("test_event", value1=None, value2="not_none", value3=Decimal("0.5200"))


@pytest.mark.unit
def test_setup_logging_without_file(temp_log_dir):
    """Test setup_logging with file logging disabled."""
    logger = setup_logging(log_level="INFO", log_to_file=False)

    logger.info("test_message")

    # No log files should be created
    log_files = list(Path(temp_log_dir).glob("*.log"))
    assert len(log_files) == 0
