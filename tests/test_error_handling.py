"""
Error Handling Tests
====================
Tests error paths and edge cases for database and configuration handling.

Tests included:
- Transaction rollback on connection loss
- Invalid YAML configuration files
- Missing configuration files
- Foreign key constraint violations

Note: Tests for features not yet implemented (connection pool control,
environment variable expansion, type validation, logger file params)
were removed in Issue #175 cleanup.
"""

import psycopg2
import pytest
import yaml

from precog.config.config_loader import ConfigLoader
from precog.database.connection import get_connection

# ============================================================================
# Connection Error Handling
# ============================================================================


def test_transaction_rollback_on_connection_loss():
    """
    Test that transactions rollback gracefully if connection is lost.

    Expected: Transaction rolled back, error raised, no data corruption
    Coverage: database/connection.py lines 283-285 (transaction cleanup)
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Start transaction
        cur.execute("BEGIN")

        # Insert test data
        cur.execute("""
            INSERT INTO platforms (platform_id, platform_type, display_name)
            VALUES ('TEST_DISCONNECT', 'trading', 'Test Platform')
        """)

        # Simulate connection loss by closing connection
        conn.close()

        # Attempt to commit (should fail)
        with pytest.raises(psycopg2.InterfaceError):
            conn.commit()

    finally:
        # Verify data was NOT committed (rollback on connection loss)
        new_conn = get_connection()
        new_cur = new_conn.cursor()
        new_cur.execute("""
            SELECT COUNT(*) FROM platforms
            WHERE platform_id = 'TEST_DISCONNECT'
        """)
        count = new_cur.fetchone()[0]
        assert count == 0, "Transaction should have rolled back on connection loss"
        new_cur.close()
        new_conn.close()


# ============================================================================
# Configuration Error Handling
# ============================================================================


def test_config_loader_invalid_yaml_syntax(tmp_path):
    """
    Test behavior when YAML file has syntax errors.

    Expected: yaml.YAMLError raised with clear error message
    Coverage: config/config_loader.py line 382 (yaml.safe_load)
    """
    # Create temp config directory with invalid YAML
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    invalid_yaml_file = config_dir / "invalid.yaml"
    invalid_yaml_file.write_text(
        "key1: value1\n"
        "key2: [unclosed list\n"  # Invalid YAML - unclosed bracket
        "key3: value3\n",
        encoding="utf-8",
    )

    loader = ConfigLoader(config_dir=config_dir)

    with pytest.raises(yaml.YAMLError) as exc_info:
        loader.load("invalid")

    # Verify error message is informative
    error_msg = str(exc_info.value)
    assert "while parsing" in error_msg.lower() or "expected" in error_msg.lower()


def test_config_loader_missing_required_file():
    """
    Test behavior when required config file doesn't exist.

    Expected: Clear error message indicating which file is missing
    Coverage: config/config_loader.py lines 305, 318-319 (file not found)
    """
    loader = ConfigLoader()

    with pytest.raises(FileNotFoundError) as exc_info:
        loader.load("nonexistent_config")

    error_msg = str(exc_info.value)
    assert "nonexistent_config" in error_msg


# ============================================================================
# Database CRUD Error Handling
# ============================================================================


def test_crud_operation_with_foreign_key_violation():
    """
    Test CRUD operations handle foreign key constraint violations.

    Expected: Raise IntegrityError indicating FK violation
    Coverage: database/crud_operations.py lines 375 (FK violations)
    """
    # Attempt to create market with nonexistent foreign key
    from decimal import Decimal

    from precog.database.crud_operations import create_market

    with pytest.raises(psycopg2.IntegrityError) as exc_info:
        create_market(
            platform_id="nonexistent_platform",  # FK violation
            event_id="TEST-EVENT",
            external_id="TEST",
            ticker="INVALID",
            title="Test Market",
            yes_price=Decimal("0.50"),
            no_price=Decimal("0.50"),
        )

    error_msg = str(exc_info.value).lower()
    assert "foreign key" in error_msg or "violates" in error_msg
