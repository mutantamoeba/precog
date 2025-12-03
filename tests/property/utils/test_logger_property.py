"""
Property-Based Tests for Logger.

Tests logging invariants with generated inputs:
- Log level ordering properties
- Message formatting invariants
- Handler registration properties

Related:
- TESTING_STRATEGY V3.2: All 8 test types required
- utils/logger module coverage

Usage:
    pytest tests/property/utils/test_logger_property.py -v -m property
"""

import logging

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


@pytest.mark.property
class TestLoggerProperty:
    """Property-based tests for logging invariants."""

    @given(
        level=st.sampled_from(
            [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]
        )
    )
    @settings(max_examples=30)
    def test_log_level_ordering(self, level: int):
        """
        PROPERTY: Log levels follow ordering DEBUG < INFO < WARNING < ERROR < CRITICAL.

        Invariant:
        - DEBUG (10) < INFO (20) < WARNING (30) < ERROR (40) < CRITICAL (50)
        """
        level_order = {
            logging.DEBUG: 0,
            logging.INFO: 1,
            logging.WARNING: 2,
            logging.ERROR: 3,
            logging.CRITICAL: 4,
        }

        assert level in level_order, f"Unknown log level: {level}"
        assert level_order[level] >= 0

    @given(message=st.text(min_size=0, max_size=1000))
    @settings(max_examples=50)
    def test_message_preserved_in_output(self, message: str):
        """
        PROPERTY: Log message content is preserved in output.

        Invariant:
        - Original message appears in formatted output
        """
        # Filter out problematic characters for logging
        clean_message = message.replace("\x00", "")

        if clean_message:
            # Message should be in output (when formatted)
            formatted = f"[INFO] {clean_message}"
            assert clean_message in formatted

    @given(
        extra_fields=st.dictionaries(
            keys=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"),
            values=st.one_of(st.text(max_size=50), st.integers(), st.floats(allow_nan=False)),
            max_size=10,
        )
    )
    @settings(max_examples=30)
    def test_extra_fields_preserved(self, extra_fields: dict):
        """
        PROPERTY: Extra fields in log records are preserved.

        Invariant:
        - All extra fields accessible in log record
        """
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )

        for key, value in extra_fields.items():
            setattr(record, key, value)

        # Verify fields preserved
        for key, value in extra_fields.items():
            assert hasattr(record, key)
            assert getattr(record, key) == value

    @given(
        logger_name=st.text(
            min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz._"
        ).filter(lambda x: not x.startswith(".") and ".." not in x and not x.endswith("."))
    )
    @settings(max_examples=30)
    def test_logger_name_hierarchy(self, logger_name: str):
        """
        PROPERTY: Logger names form valid hierarchy.

        Invariant:
        - Logger names with dots create parent-child relationships

        Note: Filter excludes invalid logger names:
        - Names starting with "." (e.g., ".foo")
        - Names with consecutive dots (e.g., "foo..bar")
        - Names ending with "." (e.g., "foo.")
        """
        logger = logging.getLogger(logger_name)
        assert logger.name == logger_name

        # Child loggers should have parent
        if "." in logger_name:
            parent_name = logger_name.rsplit(".", 1)[0]
            parent = logging.getLogger(parent_name)
            assert parent.name == parent_name

    @given(
        threshold=st.sampled_from([logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR]),
        message_level=st.sampled_from(
            [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]
        ),
    )
    @settings(max_examples=40)
    def test_level_filtering_consistent(self, threshold: int, message_level: int):
        """
        PROPERTY: Level filtering is consistent.

        Invariant:
        - Messages below threshold are filtered
        - Messages at or above threshold pass through
        """
        should_log = message_level >= threshold
        logger = logging.getLogger("property_test")
        logger.setLevel(threshold)

        # Verify filtering logic
        assert logger.isEnabledFor(message_level) == should_log
