"""
End-to-End tests for environment configuration.

Tests complete environment configuration workflows with real env vars.

Reference: TESTING_STRATEGY_V3.2.md Section "E2E Tests"
"""

import pytest

from precog.config.environment import (
    AppEnvironment,
    CombinationSafety,
    EnvironmentConfig,
    MarketMode,
    get_app_environment,
    get_database_name,
    get_market_mode,
    load_environment_config,
)


@pytest.mark.e2e
class TestEnvironmentDetectionE2E:
    """E2E tests for environment detection from real env vars."""

    def test_get_app_environment_from_precog_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test PRECOG_ENV detection works end-to-end."""
        monkeypatch.setenv("PRECOG_ENV", "staging")

        result = get_app_environment()

        assert result == AppEnvironment.STAGING

    def test_get_app_environment_infers_from_db_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test environment inference from DB_NAME works."""
        monkeypatch.delenv("PRECOG_ENV", raising=False)
        monkeypatch.setenv("DB_NAME", "precog_test")

        result = get_app_environment()

        assert result == AppEnvironment.TEST

    def test_get_market_mode_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test market mode detection from KALSHI_MODE."""
        monkeypatch.setenv("KALSHI_MODE", "live")

        result = get_market_mode("kalshi")

        assert result == MarketMode.LIVE

    def test_get_database_name_explicit_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test DB_NAME takes precedence over derived name."""
        monkeypatch.setenv("PRECOG_ENV", "development")
        monkeypatch.setenv("DB_NAME", "custom_db")

        result = get_database_name()

        assert result == "custom_db"


@pytest.mark.e2e
class TestEnvironmentConfigLoadingE2E:
    """E2E tests for loading complete environment configuration."""

    def test_load_development_demo_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading a typical development configuration."""
        monkeypatch.setenv("PRECOG_ENV", "dev")
        monkeypatch.setenv("KALSHI_MODE", "demo")
        monkeypatch.delenv("DB_NAME", raising=False)

        config = load_environment_config(validate=True)

        assert config.app_env == AppEnvironment.DEVELOPMENT
        assert config.kalshi_mode == MarketMode.DEMO
        assert config.database_name == "precog_dev"
        assert config.get_combination_safety() == CombinationSafety.ALLOWED

    def test_load_test_demo_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading a test environment configuration."""
        monkeypatch.setenv("PRECOG_ENV", "test")
        monkeypatch.setenv("KALSHI_MODE", "demo")
        monkeypatch.delenv("DB_NAME", raising=False)

        config = load_environment_config(validate=True)

        assert config.app_env == AppEnvironment.TEST
        assert config.kalshi_mode == MarketMode.DEMO
        assert config.get_combination_safety() == CombinationSafety.ALLOWED

    def test_load_blocked_combination_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that blocked combinations raise during validation."""
        monkeypatch.setenv("PRECOG_ENV", "test")
        monkeypatch.setenv("KALSHI_MODE", "live")
        monkeypatch.delenv("DB_NAME", raising=False)

        with pytest.raises(OSError):
            load_environment_config(validate=True)

    def test_load_without_validation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that validation can be skipped."""
        monkeypatch.setenv("PRECOG_ENV", "test")
        monkeypatch.setenv("KALSHI_MODE", "live")
        monkeypatch.delenv("DB_NAME", raising=False)

        # Should not raise with validate=False
        config = load_environment_config(validate=False)

        assert config.app_env == AppEnvironment.TEST
        assert config.kalshi_mode == MarketMode.LIVE


@pytest.mark.e2e
class TestEnvironmentValidationE2E:
    """E2E tests for environment validation behavior."""

    def test_validate_allowed_combination(self) -> None:
        """Test that allowed combinations pass validation."""
        config = EnvironmentConfig(
            app_env=AppEnvironment.DEVELOPMENT,
            kalshi_mode=MarketMode.DEMO,
            database_name="precog_dev",
        )

        # Should not raise
        config.validate()

    def test_validate_blocked_combination_raises(self) -> None:
        """Test that blocked combinations raise OSError."""
        config = EnvironmentConfig(
            app_env=AppEnvironment.TEST,
            kalshi_mode=MarketMode.LIVE,
            database_name="precog_test",
        )

        with pytest.raises(OSError, match="BLOCKED"):
            config.validate()

    def test_validate_warning_combination_logs_warning(self) -> None:
        """Test that warning combinations log but don't raise."""
        config = EnvironmentConfig(
            app_env=AppEnvironment.DEVELOPMENT,
            kalshi_mode=MarketMode.LIVE,
            database_name="precog_dev",
        )

        # Should not raise (just warns)
        with pytest.warns(UserWarning, match="WARNING"):
            config.validate(require_confirmation=False)
