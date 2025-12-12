"""
End-to-End Tests for ServiceSupervisor Credential Detection.

These tests validate that the ServiceSupervisor correctly detects Kalshi
credentials using the two-axis environment model naming convention.

Educational Note:
    This E2E test was created after discovering a bug where service_supervisor.py
    was checking for the wrong environment variable name (KALSHI_API_KEY_ID instead
    of DEV_KALSHI_API_KEY). Unit tests passed because they mocked the same wrong
    variable. This E2E test uses REAL environment variables to catch such bugs.

    Key lesson: E2E tests for credential detection MUST use real env vars, not mocks.

Prerequisites:
    - DEV_KALSHI_API_KEY set in .env
    - DEV_KALSHI_PRIVATE_KEY_PATH set in .env (path to RSA private key)

Run with:
    pytest tests/e2e/schedulers/test_service_supervisor_e2e.py -v -m e2e

References:
    - Issue #217: Add missing modules to MODULE_TIERS audit
    - PR #216: Fix credential naming bug
    - ADR-100: Service Supervisor Pattern
    - docs/guides/ENVIRONMENT_CONFIGURATION_GUIDE_V1.0.md

Phase: 2.5 (Service Infrastructure)
"""

import os
from pathlib import Path

import pytest


def _real_kalshi_credentials_available() -> bool:
    """Check if REAL Kalshi credentials are available for E2E tests.

    Returns True only if DEV_KALSHI_* credentials are set AND the key file exists.

    Educational Note:
        This function checks for the CORRECT credential naming convention
        ({PRECOG_ENV}_KALSHI_API_KEY). If we had this E2E test before PR #216,
        it would have caught that service_supervisor.py was checking the wrong
        env var name.
    """
    dev_api_key = os.getenv("DEV_KALSHI_API_KEY")
    dev_key_path = os.getenv("DEV_KALSHI_PRIVATE_KEY_PATH")

    if not dev_api_key or not dev_key_path:
        return False

    # Also verify the key file actually exists
    return Path(dev_key_path).exists()


# Skip entire module if credentials not available
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not _real_kalshi_credentials_available(),
        reason=(
            "Real Kalshi credentials not configured. "
            "Set DEV_KALSHI_API_KEY and DEV_KALSHI_PRIVATE_KEY_PATH in .env"
        ),
    ),
]


class TestServiceSupervisorCredentialDetection:
    """E2E tests for credential detection in ServiceSupervisor.

    Educational Note:
        These tests verify that the _has_kalshi_credentials() function
        correctly detects credentials using the two-axis naming convention.
        This is the test that would have caught the PR #216 bug.
    """

    def test_has_kalshi_credentials_detects_dev_credentials(self) -> None:
        """Verify _has_kalshi_credentials() detects DEV_KALSHI_* when set.

        This is THE test that would have caught the credential naming bug.
        Before PR #216, service_supervisor checked for KALSHI_API_KEY_ID,
        but the correct naming is DEV_KALSHI_API_KEY.

        Educational Note:
            This test uses REAL environment variables (not mocks) because:
            1. Mocking can hide bugs if you mock the wrong variable name
            2. E2E tests should validate actual system integration
            3. The credential detection logic MUST work with real env vars
        """
        from precog.schedulers.service_supervisor import (
            Environment,
            _has_kalshi_credentials,
        )

        # Test with DEVELOPMENT environment (uses DEV_KALSHI_* prefix)
        result = _has_kalshi_credentials(Environment.DEVELOPMENT)

        assert result is True, (
            "Expected _has_kalshi_credentials() to return True when "
            "DEV_KALSHI_API_KEY and DEV_KALSHI_PRIVATE_KEY_PATH are set. "
            "This test failing indicates the credential naming convention bug."
        )

    def test_has_kalshi_credentials_with_precog_env_dev(self) -> None:
        """Verify credentials detected when PRECOG_ENV=dev.

        Educational Note:
            The two-axis model uses PRECOG_ENV to determine which credential
            prefix to use. When PRECOG_ENV=dev (or unset), it should look for
            DEV_KALSHI_* credentials.
        """
        from precog.schedulers.service_supervisor import (
            Environment,
            _has_kalshi_credentials,
        )

        # Ensure PRECOG_ENV is set to dev (or use default)
        original_env = os.getenv("PRECOG_ENV")
        try:
            os.environ["PRECOG_ENV"] = "dev"
            result = _has_kalshi_credentials(Environment.DEVELOPMENT)
            assert result is True
        finally:
            if original_env is not None:
                os.environ["PRECOG_ENV"] = original_env
            elif "PRECOG_ENV" in os.environ:
                del os.environ["PRECOG_ENV"]

    def test_supervisor_creation_succeeds(self) -> None:
        """Verify ServiceSupervisor can be created with valid configuration.

        Educational Note:
            This test validates the full integration path - that a supervisor
            can be instantiated with the correct configuration objects.
        """
        from precog.schedulers.service_supervisor import (
            Environment,
            RunnerConfig,
            ServiceSupervisor,
        )

        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=60,
            metrics_interval=300,
        )

        supervisor = ServiceSupervisor(config)

        # Supervisor should be created successfully
        assert supervisor is not None
        assert supervisor.config.environment == Environment.DEVELOPMENT

    def test_credential_env_var_names_match_convention(self) -> None:
        """Verify the expected env var names are what we check for.

        Educational Note:
            This is a documentation test - it verifies that our understanding
            of the credential naming convention matches reality. If the
            convention changes, this test should be updated.

        Two-Axis Credential Naming Convention:
            - DEV_KALSHI_API_KEY (for PRECOG_ENV=dev)
            - DEV_KALSHI_PRIVATE_KEY_PATH (for PRECOG_ENV=dev)
            - TEST_KALSHI_API_KEY (for PRECOG_ENV=test)
            - STAGING_KALSHI_API_KEY (for PRECOG_ENV=staging)
            - PROD_KALSHI_API_KEY (for PRECOG_ENV=prod)
        """
        # These are the env vars that MUST be checked (not KALSHI_API_KEY_ID!)
        expected_api_key_var = "DEV_KALSHI_API_KEY"
        expected_key_path_var = "DEV_KALSHI_PRIVATE_KEY_PATH"

        # Verify they are set (this is what makes E2E tests valuable)
        api_key = os.getenv(expected_api_key_var)
        key_path = os.getenv(expected_key_path_var)

        assert api_key is not None, f"{expected_api_key_var} must be set for E2E tests"
        assert key_path is not None, f"{expected_key_path_var} must be set for E2E tests"

        # Verify the key file exists
        assert Path(key_path).exists(), f"Key file at {key_path} must exist"


class TestServiceSupervisorWithMissingCredentials:
    """Tests for behavior when credentials are missing.

    Educational Note:
        These tests verify graceful degradation when credentials are not
        available. They temporarily unset ALL credential env vars to test
        this scenario (including TEST_KALSHI_* set by conftest.py).
    """

    def test_has_kalshi_credentials_returns_false_without_any_credentials(
        self,
    ) -> None:
        """Verify False returned when no credentials are set at all.

        Educational Note:
            conftest.py sets TEST_KALSHI_* for CI. We must remove ALL credential
            env vars to properly test the "no credentials" scenario.
        """
        from precog.schedulers.service_supervisor import (
            Environment,
            _has_kalshi_credentials,
        )

        # Save and remove ALL credential env vars
        saved_vars = {}
        credential_vars = [
            "DEV_KALSHI_API_KEY",
            "DEV_KALSHI_PRIVATE_KEY_PATH",
            "TEST_KALSHI_API_KEY",
            "TEST_KALSHI_PRIVATE_KEY_PATH",
            "STAGING_KALSHI_API_KEY",
            "STAGING_KALSHI_PRIVATE_KEY_PATH",
            "PROD_KALSHI_API_KEY",
            "PROD_KALSHI_PRIVATE_KEY_PATH",
        ]

        for var in credential_vars:
            if var in os.environ:
                saved_vars[var] = os.environ.pop(var)

        try:
            result = _has_kalshi_credentials(Environment.DEVELOPMENT)
            assert result is False, "Should return False when no credentials are set"
        finally:
            # Restore all saved vars
            for var, value in saved_vars.items():
                os.environ[var] = value

    def test_has_kalshi_credentials_returns_false_with_only_api_key(self) -> None:
        """Verify False returned when only API key is set (no key path).

        Educational Note:
            Both API key AND private key path are required. Having only one
            should return False.
        """
        from precog.schedulers.service_supervisor import (
            Environment,
            _has_kalshi_credentials,
        )

        # Save current values
        saved_vars = {}
        credential_vars = [
            "DEV_KALSHI_API_KEY",
            "DEV_KALSHI_PRIVATE_KEY_PATH",
            "TEST_KALSHI_API_KEY",
            "TEST_KALSHI_PRIVATE_KEY_PATH",
        ]

        for var in credential_vars:
            if var in os.environ:
                saved_vars[var] = os.environ.pop(var)

        try:
            # Set only API key, no path
            os.environ["DEV_KALSHI_API_KEY"] = "test-api-key"
            os.environ["PRECOG_ENV"] = "dev"

            result = _has_kalshi_credentials(Environment.DEVELOPMENT)
            assert result is False, "Should return False when key path is missing"
        finally:
            # Clean up test var
            os.environ.pop("DEV_KALSHI_API_KEY", None)
            os.environ.pop("PRECOG_ENV", None)

            # Restore all saved vars
            for var, value in saved_vars.items():
                os.environ[var] = value
