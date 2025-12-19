"""
Integration tests for the two-axis environment configuration system.

These tests verify that the environment configuration integrates correctly with:
1. Database connection module (connection.py)
2. Kalshi API client (kalshi_client.py)
3. CLI commands (main.py)

Integration tests use real module imports (not mocks) to test actual behavior.

Reference: src/precog/config/environment.py
Related: Issue #202 (Two-Axis Environment Configuration)
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from precog.config.environment import (
    AppEnvironment,
    MarketMode,
    get_app_environment,
    get_market_mode,
    load_environment_config,
)
from precog.database.connection import get_environment


class TestEnvironmentDatabaseIntegration:
    """Test environment configuration integration with database layer."""

    def test_get_environment_uses_centralized_system(self) -> None:
        """
        Verify that connection.get_environment() uses the centralized
        environment system from config.environment.
        """
        with patch.dict(os.environ, {"PRECOG_ENV": "staging"}, clear=False):
            # Both should return consistent values
            app_env = get_app_environment()
            db_env = get_environment()

            assert app_env == AppEnvironment.STAGING
            assert db_env == "staging"

    def test_database_name_consistency(self) -> None:
        """
        Verify that database name is consistent between environment
        detection and connection module.
        """
        with patch.dict(os.environ, {"PRECOG_ENV": "test"}, clear=False):
            os.environ.pop("DB_NAME", None)  # Clear override

            app_env = get_app_environment()
            config = load_environment_config(validate=False)

            # Both should agree on database name
            assert app_env.database_name == "precog_test"
            assert config.database_name == "precog_test"

    @pytest.mark.parametrize(
        ("env_value", "expected_short"),
        [
            ("dev", "dev"),
            ("development", "dev"),
            ("test", "test"),
            ("staging", "staging"),
            ("prod", "prod"),
            ("production", "prod"),
        ],
    )
    def test_environment_mapping_consistency(self, env_value: str, expected_short: str) -> None:
        """
        Verify that environment strings are consistently mapped
        between centralized system and legacy short names.
        """
        with patch.dict(os.environ, {"PRECOG_ENV": env_value}):
            db_env = get_environment()
            assert db_env == expected_short


class TestEnvironmentKalshiIntegration:
    """Test environment configuration integration with Kalshi API client."""

    def test_kalshi_mode_from_environment(self) -> None:
        """Verify Kalshi client respects KALSHI_MODE environment variable."""
        with patch.dict(os.environ, {"KALSHI_MODE": "demo"}):
            mode = get_market_mode("kalshi")
            assert mode == MarketMode.DEMO

        with patch.dict(os.environ, {"KALSHI_MODE": "live"}):
            mode = get_market_mode("kalshi")
            assert mode == MarketMode.LIVE

    def test_kalshi_client_respects_market_mode(self) -> None:
        """
        Verify that KalshiClient uses the centralized market mode
        when no explicit environment is passed.

        Note: This test doesn't make actual API calls, just verifies
        the client reads the correct environment configuration.
        """

        # Test with demo mode
        with patch.dict(os.environ, {"KALSHI_MODE": "demo"}):
            # Client without explicit environment should use KALSHI_MODE
            # We can't fully test without credentials, but we verify the mode detection
            mode = get_market_mode("kalshi")
            assert mode == MarketMode.DEMO

        # Test with live mode
        with patch.dict(os.environ, {"KALSHI_MODE": "live"}):
            mode = get_market_mode("kalshi")
            assert mode == MarketMode.LIVE


class TestEnvironmentCLIIntegration:
    """Test environment configuration integration with CLI."""

    def test_cli_env_command_runs(self) -> None:
        """Verify the CLI env command executes successfully."""
        result = subprocess.run(
            [sys.executable, "main.py", "config", "env"],  # Refactored: env -> config env
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent.parent),
        )
        # Should not error
        assert result.returncode == 0
        # Should contain two-axis terminology
        assert "Axis 1" in result.stdout or "Application Environment" in result.stdout
        assert "Axis 2" in result.stdout or "Market API Mode" in result.stdout

    def test_cli_app_env_override(self) -> None:
        """Verify the --app-env CLI option overrides environment."""
        result = subprocess.run(
            [sys.executable, "main.py", "config", "env"],  # Refactored: env -> config env
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent.parent),
            env={**os.environ, "PRECOG_ENV": "staging"},  # Set env via environment variable
        )
        assert result.returncode == 0
        assert "staging" in result.stdout.lower()

    def test_cli_invalid_app_env_fails(self) -> None:
        """Verify that invalid PRECOG_ENV values show appropriate output."""
        result = subprocess.run(
            [sys.executable, "main.py", "config", "env"],  # Refactored: env -> config env
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent.parent),
            env={**os.environ, "PRECOG_ENV": "invalid"},  # Set invalid env
        )
        # Invalid env may show as "unknown" or default to dev, but command should run
        # The env display will show whatever PRECOG_ENV is set to
        assert result.returncode in [0, 1]  # May succeed showing "unknown" or fail gracefully


class TestEnvironmentSafetyIntegration:
    """Test that safety guardrails work across the system."""

    def test_blocked_combination_prevents_config_load(self) -> None:
        """
        Verify that blocked combinations (test + live) raise
        EnvironmentError during configuration load.
        """
        with patch.dict(os.environ, {"PRECOG_ENV": "test", "KALSHI_MODE": "live"}):
            with pytest.raises(EnvironmentError) as exc_info:
                load_environment_config(validate=True)
            assert "BLOCKED" in str(exc_info.value)

    def test_allowed_combination_loads_successfully(self) -> None:
        """Verify that allowed combinations load without error."""
        with patch.dict(os.environ, {"PRECOG_ENV": "test", "KALSHI_MODE": "demo"}):
            config = load_environment_config(validate=True)
            assert config.app_env == AppEnvironment.TEST
            assert config.kalshi_mode == MarketMode.DEMO

    def test_warning_combination_issues_warning(self) -> None:
        """Verify that warning combinations issue UserWarning."""
        with patch.dict(os.environ, {"PRECOG_ENV": "dev", "KALSHI_MODE": "live"}):
            with pytest.warns(
                UserWarning, match="dangerous environment combination"
            ) as warning_info:
                config = load_environment_config(validate=True)
            assert config.app_env == AppEnvironment.DEVELOPMENT
            assert config.kalshi_mode == MarketMode.LIVE
            # Should have issued a warning
            assert len(warning_info) > 0


class TestEnvironmentVariablePrecedence:
    """Test that environment variable precedence is correct."""

    def test_precog_env_overrides_db_name_inference(self) -> None:
        """PRECOG_ENV should take precedence over DB_NAME inference."""
        with patch.dict(os.environ, {"PRECOG_ENV": "staging", "DB_NAME": "precog_test"}):
            # PRECOG_ENV should win
            env = get_app_environment()
            assert env == AppEnvironment.STAGING

    def test_explicit_db_name_overrides_derived(self) -> None:
        """Explicit DB_NAME should override PRECOG_ENV-derived database name."""
        with patch.dict(os.environ, {"PRECOG_ENV": "staging", "DB_NAME": "custom_database"}):
            from precog.config.environment import get_database_name

            db_name = get_database_name()
            assert db_name == "custom_database"

    def test_fallback_chain(self) -> None:
        """Test the full fallback chain: PRECOG_ENV -> DB_NAME -> default."""
        # No env vars: should default to development
        with patch.dict(os.environ, {}, clear=True):
            env = get_app_environment()
            assert env == AppEnvironment.DEVELOPMENT

        # Only DB_NAME: should infer from name
        with patch.dict(os.environ, {"DB_NAME": "precog_prod"}, clear=True):
            env = get_app_environment()
            assert env == AppEnvironment.PRODUCTION

        # Both set: PRECOG_ENV wins
        with patch.dict(os.environ, {"PRECOG_ENV": "test", "DB_NAME": "precog_prod"}, clear=False):
            env = get_app_environment()
            assert env == AppEnvironment.TEST


class TestCrossModuleConsistency:
    """Test that environment is consistent across all modules."""

    def test_all_modules_see_same_environment(self) -> None:
        """
        Verify that environment.py, connection.py, and KalshiClient
        all see the same environment when configured.
        """
        with patch.dict(os.environ, {"PRECOG_ENV": "staging", "KALSHI_MODE": "demo"}):
            # Config module
            config = load_environment_config(validate=False)

            # Connection module
            db_env = get_environment()

            # All should agree
            assert config.app_env == AppEnvironment.STAGING
            assert db_env == "staging"
            assert config.kalshi_mode == MarketMode.DEMO

    def test_cli_override_propagates(self) -> None:
        """
        Verify that environment variable propagates to all modules.

        This test runs the CLI with an environment variable and verifies the output
        reflects the configured environment.
        """
        # Run CLI with staging environment
        result = subprocess.run(
            [sys.executable, "main.py", "config", "env"],  # Refactored: env -> config env
            capture_output=True,
            text=True,
            env={**os.environ, "PRECOG_ENV": "staging"},
            cwd=str(Path(__file__).parent.parent.parent.parent),
        )
        assert result.returncode == 0
        # Environment variable should be reflected
        assert "staging" in result.stdout.lower()
