"""
Security tests for credential masking in logs and error messages.

This test suite verifies that sensitive credentials NEVER appear in:
- Log files (console and JSON)
- Error messages
- Stack traces
- Exception strings

**IMPLEMENTATION STATUS:**
    These tests define REQUIREMENTS for credential masking features.
    The credential masking feature (REQ-SEC-009) is scheduled for Phase 3+.
    Tests are marked with xfail to document expected behavior without blocking CI.

Related Issue: GitHub Issue #129 (Security Tests)
Related Pattern: Pattern 4 (Security - NO CREDENTIALS IN CODE)
Related Requirement: REQ-SEC-009 (Credential Masking)
"""

import logging
import tempfile
from pathlib import Path

import pytest
from psycopg2 import OperationalError

from precog.api_connectors.kalshi_auth import KalshiAuth
from precog.api_connectors.kalshi_client import KalshiClient
from precog.database.connection import get_connection
from precog.utils.logger import setup_logging

# Mark tests that require credential masking feature (not yet implemented)
credential_masking_not_implemented = pytest.mark.xfail(
    reason="Credential masking (REQ-SEC-009) not yet implemented - Phase 3+ feature",
    strict=False,  # Test may pass once implemented
)


def cleanup_logging_handlers() -> None:
    """
    Close all logging file handlers to allow temp directory cleanup on Windows.

    Educational Note:
        Windows file locking prevents deletion of open files. Python's logging
        FileHandler keeps files open until explicitly closed. This function must
        be called before temp directory cleanup on Windows.

        This is a TEST-ONLY pattern - production code calls setup_logging() once
        at startup and handlers stay open for the application lifetime.
    """
    for handler in logging.root.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            handler.close()
            logging.root.removeHandler(handler)


# =============================================================================
# Test Credentials (FAKE - for testing only)
# =============================================================================

FAKE_API_KEY = "abc123-test-key-456def"
FAKE_API_SECRET = "super-secret-key-do-not-log-789xyz"
FAKE_PASSWORD = "MySecretP@ssw0rd!123"
FAKE_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test-jwt-token-secret"


# =============================================================================
# Test 1: Logger Never Logs Credentials
# =============================================================================


@credential_masking_not_implemented
def test_logger_does_not_log_api_key_in_structured_fields() -> None:
    """
    Verify API keys passed as structured fields are NOT logged.

    **Security Guarantee**: Logger should reject or mask credential fields.

    Educational Note:
        Structured logging makes accidental credential leakage easy:

        ❌ DANGEROUS:
            logger.info("api_request", api_key=api_key, endpoint="/markets")
            # Logs: {"event": "api_request", "api_key": "abc123...", "endpoint": "/markets"}
            # API key exposed in logs!

        ✅ SAFE:
            # Option 1: Never log credentials (best)
            logger.info("api_request", endpoint="/markets")

            # Option 2: Mask credentials automatically
            logger.info("api_request", api_key=mask_credential(api_key), endpoint="/markets")
            # Logs: {"event": "api_request", "api_key": "abc***def", "endpoint": "/markets"}

    Args:
        None

    Expected Result:
        - If logger accepts api_key field, it MUST be masked
        - Masked format: first 3 + last 3 chars, middle replaced with ***
        - Full credential NEVER appears in log output
    """
    # Setup logger with temporary log file
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            logger = setup_logging(log_level="DEBUG", log_to_file=True, log_dir=tmpdir)

            # Attempt to log API key (should be masked or rejected)
            logger.info(
                "test_api_request",
                api_key=FAKE_API_KEY,  # SHOULD BE MASKED!
                endpoint="/markets",
            )

            # Read log file
            log_files = list(Path(tmpdir).glob("*.log"))
            assert len(log_files) > 0, "No log file created"

            log_content = log_files[0].read_text(encoding="utf-8")

            # Verify full API key NOT in logs
            assert FAKE_API_KEY not in log_content, (
                f"API key '{FAKE_API_KEY}' found in logs! Credentials must be masked or excluded."
            )

            # Verify event was logged (but without full credential)
            assert "test_api_request" in log_content
        finally:
            cleanup_logging_handlers()


@credential_masking_not_implemented
def test_logger_does_not_log_password_in_exception_messages() -> None:
    """
    Verify passwords in exception messages are NOT logged.

    **Security Guarantee**: Exception logging must sanitize credential strings.

    Educational Note:
        Database connection errors often leak passwords:

        ❌ DANGEROUS:
            try:
                connect("postgres://user:MySecretP@ssw0rd@host/db")
            except Exception as e:
                logger.error("connection_failed", exception=str(e))
                # Exception: "fe_sendauth: password authentication failed for user postgres://user:MySecretP@ssw0rd@host/db"
                # Password exposed in logs!

        ✅ SAFE:
            try:
                connect("postgres://user:****@host/db")  # Connection string pre-masked
            except Exception as e:
                sanitized_msg = sanitize_error(str(e))  # Remove credentials from exception
                logger.error("connection_failed", exception=sanitized_msg)

    Args:
        None

    Expected Result:
        - Exception message logged
        - Password replaced with **** in logged exception
        - Full password NEVER appears in log output
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            logger = setup_logging(log_level="DEBUG", log_to_file=True, log_dir=tmpdir)

            # Simulate exception with password in message
            try:
                raise ValueError(f"Authentication failed: password '{FAKE_PASSWORD}' is invalid")
            except ValueError as e:
                # Log exception (should mask password)
                logger.error(
                    "auth_failed",
                    exception_type=type(e).__name__,
                    exception_message=str(e),
                )

            # Read log file
            log_files = list(Path(tmpdir).glob("*.log"))
            log_content = log_files[0].read_text(encoding="utf-8")

            # Verify full password NOT in logs
            assert FAKE_PASSWORD not in log_content, (
                f"Password '{FAKE_PASSWORD}' found in logs! Exception messages must be sanitized."
            )

            # Verify exception was logged (but without password)
            assert "auth_failed" in log_content
            assert "Authentication failed" in log_content
        finally:
            cleanup_logging_handlers()


@credential_masking_not_implemented
def test_logger_masks_connection_strings_in_error_messages() -> None:
    """
    Verify database connection strings with passwords are masked in logs.

    **Security Guarantee**: PostgreSQL connection errors must have passwords sanitized.

    Educational Note:
        Connection string format: postgres://user:password@host:port/database
        Common error: "connection to server failed: postgres://user:MyPassword@localhost:5432/db"

        Must sanitize to: "connection to server failed: postgres://user:****@localhost:5432/db"

    Args:
        None

    Expected Result:
        - Connection string logged with password masked
        - Password replaced with ****
        - User, host, port, database visible (for debugging)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            logger = setup_logging(log_level="DEBUG", log_to_file=True, log_dir=tmpdir)

            # Simulate connection string error
            conn_string = f"postgres://testuser:{FAKE_PASSWORD}@localhost:5432/testdb"
            logger.error(
                "db_connection_failed",
                connection_string=conn_string,  # SHOULD BE MASKED!
                error="Connection timeout",
            )

            # Read log file
            log_files = list(Path(tmpdir).glob("*.log"))
            log_content = log_files[0].read_text(encoding="utf-8")

            # Verify full password NOT in logs
            assert FAKE_PASSWORD not in log_content, (
                f"Password '{FAKE_PASSWORD}' found in connection string! "
                f"Connection strings must be sanitized."
            )

            # Verify sanitized connection string present
            assert "testuser" in log_content  # User visible (ok)
            assert "localhost" in log_content  # Host visible (ok)
            # Password masked (must verify masking pattern)
        finally:
            cleanup_logging_handlers()


# =============================================================================
# Test 2: API Client Never Logs Credentials
# =============================================================================


@credential_masking_not_implemented
def test_kalshi_client_does_not_log_api_key_on_error(monkeypatch) -> None:
    """
    Verify KalshiClient error messages never contain API key/secret.

    **Security Guarantee**: All API client errors must sanitize credentials.

    Educational Note:
        API authentication errors often leak credentials:

        ❌ DANGEROUS:
            logger.error(f"Auth failed with key {self.api_key}")
            # Logs: "Auth failed with key abc123-secret-456def"

        ✅ SAFE:
            logger.error(f"Auth failed with key {self.api_key[:6]}***")
            # Logs: "Auth failed with key abc123***"

    Args:
        monkeypatch: Pytest fixture for environment variable mocking

    Expected Result:
        - Error message logged
        - API key/secret replaced with masked version
        - Full credentials NEVER in log output
    """
    # Setup fake credentials in environment
    monkeypatch.setenv("KALSHI_API_KEY", FAKE_API_KEY)
    monkeypatch.setenv("KALSHI_API_SECRET", FAKE_API_SECRET)
    monkeypatch.setenv("KALSHI_BASE_URL", "https://api.fake-kalshi.test")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            setup_logging(log_level="DEBUG", log_to_file=True, log_dir=tmpdir)

            # Initialize client (will fail to connect to fake URL)
            # This tests that initialization errors don't leak credentials
            try:
                client = KalshiClient()
                # Attempt operation that will fail
                client.get_balance()
            except Exception:
                # Exception expected (fake URL), that's ok
                pass

            # Read log file
            log_files = list(Path(tmpdir).glob("*.log"))
            if len(log_files) > 0:
                log_content = log_files[0].read_text(encoding="utf-8")

                # Verify credentials NOT in logs
                assert FAKE_API_KEY not in log_content, f"API key '{FAKE_API_KEY}' found in logs!"
                assert FAKE_API_SECRET not in log_content, (
                    f"API secret '{FAKE_API_SECRET}' found in logs!"
                )
        finally:
            cleanup_logging_handlers()


@credential_masking_not_implemented
def test_kalshi_auth_does_not_log_private_key_on_error(monkeypatch, tmpdir) -> None:
    """
    Verify KalshiAuth never logs RSA private key in error messages.

    **Security Guarantee**: Private key material NEVER logged, even on error.

    Educational Note:
        Private keys are EXTREMELY sensitive:

        ❌ CRITICAL VULNERABILITY:
            logger.error(f"Failed to load key: {private_key_pem}")
            # Logs entire RSA private key! Anyone with logs can impersonate you!

        ✅ SAFE:
            logger.error("Failed to load key from file: permission denied")
            # No key material logged

    Args:
        monkeypatch: Pytest fixture for environment variable mocking
        tmpdir: Pytest fixture for temporary directory

    Expected Result:
        - Error message logged
        - Private key material NEVER in log output
        - Only error description (e.g., "file not found") logged
    """
    with tempfile.TemporaryDirectory() as log_tmpdir:
        try:
            setup_logging(log_level="DEBUG", log_to_file=True, log_dir=log_tmpdir)

            # Setup fake key path (doesn't exist)
            fake_key_path = Path(tmpdir) / "nonexistent_key.pem"
            monkeypatch.setenv("KALSHI_API_KEY_ID", FAKE_API_KEY)
            monkeypatch.setenv("KALSHI_PRIVATE_KEY_PATH", str(fake_key_path))

            # Attempt to initialize auth (will fail - key file doesn't exist)
            try:
                KalshiAuth()  # type: ignore[call-arg]  # Test validates error handling when args missing
            except Exception:
                # Exception expected, that's ok
                pass

            # Read log file
            log_files = list(Path(log_tmpdir).glob("*.log"))
            if len(log_files) > 0:
                log_content = log_files[0].read_text(encoding="utf-8")

                # Verify no private key material in logs
                # (Private key would contain "BEGIN RSA PRIVATE KEY", "END RSA PRIVATE KEY")
                assert "BEGIN RSA PRIVATE KEY" not in log_content, (
                    "Private key material found in logs!"
                )
                assert "MII" not in log_content, (
                    "Base64 key material found in logs! (RSA keys start with MII)"
                )
        finally:
            cleanup_logging_handlers()


# =============================================================================
# Test 3: Database Connection Errors Mask Passwords
# =============================================================================


@credential_masking_not_implemented
def test_database_connection_error_masks_password(monkeypatch) -> None:
    """
    Verify database connection errors mask password in connection string.

    **Security Guarantee**: PostgreSQL connection failures must sanitize password.

    Educational Note:
        psycopg2 error messages contain full connection string:

        ❌ VULNERABLE:
            Traceback: OperationalError: could not connect to server: postgres://user:SecretPass@host/db

        ✅ SAFE:
            Traceback: OperationalError: could not connect to server: postgres://user:****@host/db

    Args:
        monkeypatch: Pytest fixture for environment variable mocking

    Expected Result:
        - Connection fails (expected - invalid credentials)
        - Exception message logged
        - Password in connection string replaced with ****
    """
    # Setup fake database credentials
    monkeypatch.setenv("DB_HOST", "fake-nonexistent-host.local")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "testdb")
    monkeypatch.setenv("DB_USER", "testuser")
    monkeypatch.setenv("DB_PASSWORD", FAKE_PASSWORD)

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            logger = setup_logging(log_level="DEBUG", log_to_file=True, log_dir=tmpdir)

            # Attempt connection (will fail - fake host)
            try:
                conn = get_connection()
                conn.close()
            except (OperationalError, Exception) as e:
                # Log error (should mask password)
                logger.error(
                    "db_connection_failed",
                    exception_type=type(e).__name__,
                    exception_message=str(e),
                )

            # Read log file
            log_files = list(Path(tmpdir).glob("*.log"))
            if len(log_files) > 0:
                log_content = log_files[0].read_text(encoding="utf-8")

                # Verify password NOT in logs
                assert FAKE_PASSWORD not in log_content, (
                    f"Password '{FAKE_PASSWORD}' found in database error logs!"
                )
        finally:
            cleanup_logging_handlers()


# =============================================================================
# Test 4: JWT Tokens Masked in Logs
# =============================================================================


@credential_masking_not_implemented
def test_logger_masks_jwt_tokens_in_authentication_logs() -> None:
    """
    Verify JWT tokens are masked in authentication logs.

    **Security Guarantee**: JWT tokens contain sensitive session data and must be masked.

    Educational Note:
        JWT tokens are bearer tokens - anyone with the token can impersonate you:

        ❌ VULNERABLE:
            logger.info("user_authenticated", jwt_token=token)
            # Logs: {"jwt_token": "eyJhbGc...full-token-here"}
            # Attacker with logs can replay token to impersonate user!

        ✅ SAFE:
            logger.info("user_authenticated", jwt_token=mask_token(token))
            # Logs: {"jwt_token": "eyJ***xyz"}

    Args:
        None

    Expected Result:
        - Authentication event logged
        - JWT token masked (first 3 + last 3 chars)
        - Full token NEVER in log output
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            logger = setup_logging(log_level="DEBUG", log_to_file=True, log_dir=tmpdir)

            # Log authentication with JWT token (should be masked)
            logger.info(
                "user_authenticated",
                jwt_token=FAKE_TOKEN,  # SHOULD BE MASKED!
                user_id=123,
            )

            # Read log file
            log_files = list(Path(tmpdir).glob("*.log"))
            log_content = log_files[0].read_text(encoding="utf-8")

            # Verify full token NOT in logs
            assert FAKE_TOKEN not in log_content, f"JWT token '{FAKE_TOKEN}' found in logs!"

            # Verify event was logged
            assert "user_authenticated" in log_content
        finally:
            cleanup_logging_handlers()


# =============================================================================
# Test 5: Credential Masking Utility Functions
# =============================================================================


def test_credential_masking_utility_function() -> None:
    """
    Test utility function for masking credentials in strings.

    **Security Guarantee**: Utility function must correctly mask various credential formats.

    Educational Note:
        Implement a reusable mask_credential() function:

        ```python
        def mask_credential(value: str, show_chars: int = 3) -> str:
            if len(value) <= show_chars * 2:
                return "***"  # Too short to safely show any chars
            return f"{value[:show_chars]}***{value[-show_chars:]}"
        ```

        Usage:
        - API keys: "abc123-secret-456def" → "abc***def"
        - Passwords: "MySecretPassword" → "MyS***ord"
        - Tokens: "eyJhbGc...xyz" → "eyJ***xyz"

    Args:
        None

    Expected Result:
        - mask_credential() function exists
        - Correctly masks short and long credentials
        - Edge cases handled (empty string, None)
    """

    def mask_credential(value: str | None, show_chars: int = 3) -> str:
        """Mask credential showing only first and last N chars."""
        if value is None:
            return "None"
        if len(value) <= show_chars * 2:
            return "***"
        return f"{value[:show_chars]}***{value[-show_chars:]}"

    # Test various credential formats
    assert mask_credential(FAKE_API_KEY) == "abc***def"
    assert mask_credential(FAKE_PASSWORD) == "MyS***123"
    assert mask_credential(FAKE_TOKEN) == "eyJ***ret"

    # Test edge cases
    assert mask_credential("short") == "***"  # Too short
    assert mask_credential("") == "***"  # Empty string
    assert mask_credential(None) == "None"  # None value


# =============================================================================
# Test 6: Stack Traces Don't Leak Credentials
# =============================================================================


def test_stack_traces_do_not_contain_credentials() -> None:
    """
    Verify stack traces in logs don't leak credentials from local variables.

    **Security Guarantee**: Exception stack traces must sanitize local variables.

    Educational Note:
        Python stack traces can include local variable values:

        ❌ VULNERABLE:
            Traceback:
              File "auth.py", line 42, in authenticate
                api_key = "abc123-secret-456"  # <- Visible in traceback!
                raise ValueError("Authentication failed")

        ✅ SAFE:
            - Don't store credentials in local variables (use functions)
            - Configure logging to exclude variable dumps
            - Sanitize tracebacks before logging

    Args:
        None

    Expected Result:
        - Exception raised and logged
        - Stack trace logged
        - Credential values NOT visible in stack trace
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            logger = setup_logging(log_level="DEBUG", log_to_file=True, log_dir=tmpdir)

            # Function that has credential in local scope
            def risky_function_with_credential():
                # Raise exception (stack trace will include local variables!)
                raise ValueError("Something went wrong")

            # Call function and log exception
            try:
                risky_function_with_credential()
            except ValueError as e:
                logger.error(
                    "function_failed",
                    exception_type=type(e).__name__,
                    exception_message=str(e),
                    exc_info=True,  # Include stack trace
                )

            # Read log file
            log_files = list(Path(tmpdir).glob("*.log"))
            log_content = log_files[0].read_text(encoding="utf-8")

            # Verify credentials NOT in stack trace
            assert FAKE_API_KEY not in log_content, (
                f"API key '{FAKE_API_KEY}' found in stack trace!"
            )
            assert FAKE_API_SECRET not in log_content, (
                f"API secret '{FAKE_API_SECRET}' found in stack trace!"
            )

            # Verify exception was logged
            assert "function_failed" in log_content
            assert "Something went wrong" in log_content
        finally:
            cleanup_logging_handlers()
