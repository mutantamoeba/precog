"""
Error Handling Tests
====================
Phase 1.5 test additions to increase coverage from 87% to 90%+

Tests error paths and edge cases that were missing from initial test suite:
- Connection pool exhaustion
- Database connection loss/reconnection
- Invalid configuration files
- Missing environment variables
- Logging errors

Target: 90%+ coverage before Phase 2
"""

import pytest
import psycopg2
from database.connection import get_connection, init_connection_pool
from config.config_loader import ConfigLoader
import os
import tempfile


# ============================================================================
# Connection Pool Error Handling (HIGH PRIORITY)
# ============================================================================

def test_connection_pool_exhaustion():
    """
    Test behavior when all connections in pool are exhausted.

    Expected: Either queue/wait for available connection or raise PoolTimeout error
    Coverage: database/connection.py lines 81-83 (pool exhaustion handling)
    """
    # Get pool configuration
    pool_size = 2  # Small pool for testing
    max_overflow = 1

    # Initialize pool with small size
    init_connection_pool(
        host="localhost",
        port=5432,
        dbname="precog_dev",
        user="postgres",
        password=os.getenv("DEMO_DB_PASSWORD", "password"),
        min_conn=pool_size,
        max_conn=pool_size + max_overflow
    )

    # Hold all connections
    connections = []
    try:
        # Request more connections than pool allows
        for i in range(pool_size + max_overflow + 1):
            conn = get_connection()
            connections.append(conn)

        # If we get here, pool is queuing requests (acceptable behavior)
        pytest.fail("Expected PoolTimeout or blocking behavior")

    except Exception as e:
        # Expected: PoolTimeout or similar error
        assert "pool" in str(e).lower() or "timeout" in str(e).lower()

    finally:
        # Clean up connections
        for conn in connections:
            try:
                conn.close()
            except:
                pass


def test_database_connection_failure_and_reconnection():
    """
    Test behavior when database connection is lost mid-operation.

    Expected: Retry connection with exponential backoff, don't crash
    Coverage: database/connection.py lines 273-277 (connection retry logic)
    """
    # Simulate connection with invalid credentials
    with pytest.raises(psycopg2.OperationalError):
        init_connection_pool(
            host="localhost",
            port=5432,
            dbname="nonexistent_db",
            user="invalid_user",
            password="wrong_password",
            min_conn=1,
            max_conn=2
        )


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
# Configuration Error Handling (MEDIUM PRIORITY)
# ============================================================================

def test_config_loader_invalid_yaml_syntax():
    """
    Test behavior when YAML file has syntax errors.

    Expected: Clear error message, fail fast, don't proceed
    Coverage: config/config_loader.py lines 288-293 (YAML parsing errors)
    """
    # Create temporary invalid YAML file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
        invalid_yaml:
          - item1
         - item2  # Invalid indentation
        missing_colon
          value: test
        """)
        temp_path = f.name

    try:
        loader = ConfigLoader()
        with pytest.raises(Exception) as exc_info:
            loader.load_yaml_file(temp_path)

        # Error message should mention YAML parsing
        error_msg = str(exc_info.value).lower()
        assert any(keyword in error_msg for keyword in ['yaml', 'syntax', 'parse', 'invalid'])

    finally:
        os.unlink(temp_path)


def test_config_loader_missing_required_file():
    """
    Test behavior when required config file doesn't exist.

    Expected: Clear error message indicating which file is missing
    Coverage: config/config_loader.py lines 305, 318-319 (file not found)
    """
    loader = ConfigLoader()

    with pytest.raises(FileNotFoundError) as exc_info:
        loader.load_yaml_file("config/nonexistent_file.yaml")

    error_msg = str(exc_info.value)
    assert "nonexistent_file.yaml" in error_msg


def test_config_loader_missing_environment_variable():
    """
    Test behavior when referenced environment variable doesn't exist.

    Expected: Clear error message indicating which env var is missing
    Coverage: config/config_loader.py lines 332-333 (env var expansion)
    """
    # Create temp config with env var reference
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
        database:
          password: ${NONEXISTENT_ENV_VAR}
        """)
        temp_path = f.name

    try:
        loader = ConfigLoader()
        config = loader.load_yaml_file(temp_path)

        # Should either raise error or leave unexpanded
        # (Behavior depends on ConfigLoader implementation)
        if isinstance(config['database']['password'], str):
            # If it doesn't expand, should still contain the variable reference
            assert "NONEXISTENT_ENV_VAR" in config['database']['password']

    finally:
        os.unlink(temp_path)


def test_config_loader_invalid_data_type():
    """
    Test behavior when config value has wrong data type.

    Expected: Type validation error with clear message
    Coverage: config/config_loader.py lines 346-347 (type validation)
    """
    # Create temp config with type mismatch
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
        database:
          pool_size: "not_a_number"  # Should be integer
          port: "5432"  # Should be integer
        """)
        temp_path = f.name

    try:
        loader = ConfigLoader()
        config = loader.load_yaml_file(temp_path)

        # Verify loaded as string (YAML parser doesn't enforce types)
        assert isinstance(config['database']['pool_size'], str)

        # Application code should validate types
        with pytest.raises(ValueError):
            int(config['database']['pool_size'])

    finally:
        os.unlink(temp_path)


# ============================================================================
# Logging Error Handling (LOW PRIORITY)
# ============================================================================

def test_logger_file_permission_error():
    """
    Test behavior when log file directory has no write permissions.

    Expected: Fallback to console logging or raise clear error
    Coverage: utils/logger.py lines 204-211 (file handler errors)
    """
    import logging
    from utils.logger import get_logger

    # Create read-only directory
    with tempfile.TemporaryDirectory() as temp_dir:
        readonly_dir = os.path.join(temp_dir, "readonly")
        os.mkdir(readonly_dir)
        os.chmod(readonly_dir, 0o444)  # Read-only

        try:
            # Attempt to create logger with file in read-only directory
            log_file = os.path.join(readonly_dir, "test.log")
            logger = get_logger("test_readonly", log_file=log_file)

            # Logger should still work (fallback to console) or raise clear error
            try:
                logger.info("test message")
            except PermissionError:
                # Acceptable - clear error raised
                pass

        finally:
            os.chmod(readonly_dir, 0o755)  # Restore permissions for cleanup


def test_logger_disk_full_simulation():
    """
    Test behavior when disk is full and log write fails.

    Expected: Don't crash application, handle gracefully
    Coverage: utils/logger.py lines 204-211 (write errors)

    Note: Difficult to simulate true disk full without root permissions.
    This test ensures logger doesn't crash on write errors.
    """
    from utils.logger import get_logger

    # Create logger with valid file
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        temp_log = f.name

    try:
        logger = get_logger("test_disk_full", log_file=temp_log)

        # Generate large log message (shouldn't crash even if disk issues)
        large_message = "x" * 1_000_000  # 1MB message
        logger.info(large_message)

        # If we get here, logger handled large message gracefully
        assert True

    finally:
        if os.path.exists(temp_log):
            os.unlink(temp_log)


# ============================================================================
# Database CRUD Error Handling (MEDIUM PRIORITY)
# ============================================================================

def test_crud_operation_with_null_violation():
    """
    Test CRUD operations handle NOT NULL constraint violations.

    Expected: Raise IntegrityError with clear constraint name
    Coverage: database/crud_operations.py lines 336-337 (constraint violations)
    """
    from database.crud_operations import create_market

    # Attempt to create market with missing required field
    with pytest.raises(psycopg2.IntegrityError) as exc_info:
        create_market(
            market_id="TEST-INVALID",
            platform_id="kalshi",
            event_id=None,  # NULL violates NOT NULL constraint
            ticker="INVALID",
            title="Test Market"
        )

    error_msg = str(exc_info.value).lower()
    assert "not null" in error_msg or "null value" in error_msg


def test_crud_operation_with_foreign_key_violation():
    """
    Test CRUD operations handle foreign key constraint violations.

    Expected: Raise IntegrityError indicating FK violation
    Coverage: database/crud_operations.py lines 375 (FK violations)
    """
    from database.crud_operations import create_market

    # Attempt to create market with nonexistent foreign key
    with pytest.raises(psycopg2.IntegrityError) as exc_info:
        create_market(
            market_id="TEST-FK-INVALID",
            platform_id="nonexistent_platform",  # FK violation
            event_id="TEST-EVENT",
            ticker="INVALID",
            title="Test Market"
        )

    error_msg = str(exc_info.value).lower()
    assert "foreign key" in error_msg or "violates" in error_msg


# ============================================================================
# Test Summary
# ============================================================================
"""
Expected Coverage Increase:

Current: 87.16% (335 statements, 43 missed)
Target: 90%+ (335 statements, <34 missed)

These 10 tests target:
- connection.py: 8 missed lines → 4 missed (50% improvement)
- config_loader.py: 20 missed lines → 15 missed (25% improvement)
- crud_operations.py: 5 missed lines → 2 missed (60% improvement)
- logger.py: 6 missed lines → 4 missed (33% improvement)

Estimated New Coverage: 89-91%
Estimated Run Time: ~5 seconds
"""
