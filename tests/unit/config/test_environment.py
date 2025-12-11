"""
Unit tests for the two-axis environment configuration system.

Tests cover:
1. AppEnvironment enum parsing and properties
2. MarketMode enum parsing and properties
3. EnvironmentConfig safety validation
4. Environment detection functions
5. Edge cases and error handling

Reference: src/precog/config/environment.py
Related: Issue #202 (Two-Axis Environment Configuration)
"""

import os
from unittest.mock import patch

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
    require_app_environment,
    require_market_mode,
)


class TestAppEnvironment:
    """Tests for AppEnvironment enum."""

    def test_enum_values(self) -> None:
        """Verify all expected environment values exist."""
        assert AppEnvironment.DEVELOPMENT.value == "development"
        assert AppEnvironment.TEST.value == "test"
        assert AppEnvironment.STAGING.value == "staging"
        assert AppEnvironment.PRODUCTION.value == "production"

    @pytest.mark.parametrize(
        ("input_value", "expected"),
        [
            ("dev", AppEnvironment.DEVELOPMENT),
            ("development", AppEnvironment.DEVELOPMENT),
            ("DEVELOPMENT", AppEnvironment.DEVELOPMENT),
            ("test", AppEnvironment.TEST),
            ("testing", AppEnvironment.TEST),
            ("staging", AppEnvironment.STAGING),
            ("stage", AppEnvironment.STAGING),
            ("prod", AppEnvironment.PRODUCTION),
            ("production", AppEnvironment.PRODUCTION),
            ("PROD", AppEnvironment.PRODUCTION),
        ],
    )
    def test_from_string_valid(self, input_value: str, expected: AppEnvironment) -> None:
        """Test parsing various valid environment strings."""
        result = AppEnvironment.from_string(input_value)
        assert result == expected

    @pytest.mark.parametrize("invalid_value", ["invalid", "local", "demo", "live", "", "  "])
    def test_from_string_invalid(self, invalid_value: str) -> None:
        """Test that invalid strings raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AppEnvironment.from_string(invalid_value)
        assert "Invalid environment" in str(exc_info.value)

    def test_database_name_mapping(self) -> None:
        """Verify database names are derived correctly from environments."""
        assert AppEnvironment.DEVELOPMENT.database_name == "precog_dev"
        assert AppEnvironment.TEST.database_name == "precog_test"
        assert AppEnvironment.STAGING.database_name == "precog_staging"
        assert AppEnvironment.PRODUCTION.database_name == "precog_prod"

    def test_is_production_property(self) -> None:
        """Test the is_production convenience property."""
        assert not AppEnvironment.DEVELOPMENT.is_production
        assert not AppEnvironment.TEST.is_production
        assert not AppEnvironment.STAGING.is_production
        assert AppEnvironment.PRODUCTION.is_production

    def test_is_safe_for_testing_property(self) -> None:
        """Test the is_safe_for_testing convenience property."""
        assert AppEnvironment.DEVELOPMENT.is_safe_for_testing
        assert AppEnvironment.TEST.is_safe_for_testing
        assert not AppEnvironment.STAGING.is_safe_for_testing
        assert not AppEnvironment.PRODUCTION.is_safe_for_testing


class TestMarketMode:
    """Tests for MarketMode enum."""

    def test_enum_values(self) -> None:
        """Verify all expected mode values exist."""
        assert MarketMode.DEMO.value == "demo"
        assert MarketMode.LIVE.value == "live"

    @pytest.mark.parametrize(
        ("input_value", "expected"),
        [
            ("demo", MarketMode.DEMO),
            ("DEMO", MarketMode.DEMO),
            ("sandbox", MarketMode.DEMO),
            ("test", MarketMode.DEMO),
            ("live", MarketMode.LIVE),
            ("LIVE", MarketMode.LIVE),
            ("prod", MarketMode.LIVE),
            ("production", MarketMode.LIVE),
        ],
    )
    def test_from_string_valid(self, input_value: str, expected: MarketMode) -> None:
        """Test parsing various valid mode strings."""
        result = MarketMode.from_string(input_value)
        assert result == expected

    @pytest.mark.parametrize("invalid_value", ["invalid", "staging", "dev", "", "  "])
    def test_from_string_invalid(self, invalid_value: str) -> None:
        """Test that invalid strings raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            MarketMode.from_string(invalid_value)
        assert "Invalid market mode" in str(exc_info.value)

    def test_uses_real_money_property(self) -> None:
        """Test the uses_real_money convenience property."""
        assert not MarketMode.DEMO.uses_real_money
        assert MarketMode.LIVE.uses_real_money


class TestEnvironmentConfig:
    """Tests for EnvironmentConfig dataclass and safety validation."""

    def test_config_is_immutable(self) -> None:
        """Verify that EnvironmentConfig is frozen (immutable)."""
        config = EnvironmentConfig(
            app_env=AppEnvironment.DEVELOPMENT,
            kalshi_mode=MarketMode.DEMO,
            database_name="precog_dev",
        )
        with pytest.raises(AttributeError, match="cannot assign"):  # dataclass frozen attribute
            config.app_env = AppEnvironment.PRODUCTION  # type: ignore[misc]

    @pytest.mark.parametrize(
        ("app_env", "market_mode", "expected_safety"),
        [
            # Development combinations
            (AppEnvironment.DEVELOPMENT, MarketMode.DEMO, CombinationSafety.ALLOWED),
            (AppEnvironment.DEVELOPMENT, MarketMode.LIVE, CombinationSafety.WARNING),
            # Test combinations
            (AppEnvironment.TEST, MarketMode.DEMO, CombinationSafety.ALLOWED),
            (AppEnvironment.TEST, MarketMode.LIVE, CombinationSafety.BLOCKED),
            # Staging combinations
            (AppEnvironment.STAGING, MarketMode.DEMO, CombinationSafety.ALLOWED),
            (AppEnvironment.STAGING, MarketMode.LIVE, CombinationSafety.WARNING),
            # Production combinations
            (AppEnvironment.PRODUCTION, MarketMode.DEMO, CombinationSafety.BLOCKED),
            (AppEnvironment.PRODUCTION, MarketMode.LIVE, CombinationSafety.ALLOWED),
        ],
    )
    def test_combination_safety(
        self,
        app_env: AppEnvironment,
        market_mode: MarketMode,
        expected_safety: CombinationSafety,
    ) -> None:
        """Test all environment + market mode combinations return correct safety level."""
        config = EnvironmentConfig(
            app_env=app_env,
            kalshi_mode=market_mode,
            database_name=app_env.database_name,
        )
        assert config.get_combination_safety() == expected_safety

    def test_validate_blocked_test_live(self) -> None:
        """Test that test + live combination raises EnvironmentError."""
        config = EnvironmentConfig(
            app_env=AppEnvironment.TEST,
            kalshi_mode=MarketMode.LIVE,
            database_name="precog_test",
        )
        with pytest.raises(EnvironmentError) as exc_info:
            config.validate()
        assert "BLOCKED" in str(exc_info.value)
        assert "Test environment must NEVER use live API" in str(exc_info.value)

    def test_validate_blocked_production_demo(self) -> None:
        """Test that production + demo combination raises EnvironmentError."""
        config = EnvironmentConfig(
            app_env=AppEnvironment.PRODUCTION,
            kalshi_mode=MarketMode.DEMO,
            database_name="precog_prod",
        )
        with pytest.raises(EnvironmentError) as exc_info:
            config.validate()
        assert "BLOCKED" in str(exc_info.value)
        assert "Production environment must use live API" in str(exc_info.value)

    def test_validate_warning_dev_live(self) -> None:
        """Test that dev + live combination issues warning but doesn't block."""
        config = EnvironmentConfig(
            app_env=AppEnvironment.DEVELOPMENT,
            kalshi_mode=MarketMode.LIVE,
            database_name="precog_dev",
        )
        # Should not raise, just warn
        with pytest.warns(UserWarning, match="dangerous environment combination"):
            config.validate()

    def test_validate_warning_with_confirmation_required(self) -> None:
        """Test that warning combinations block when confirmation is required but not provided."""
        config = EnvironmentConfig(
            app_env=AppEnvironment.DEVELOPMENT,
            kalshi_mode=MarketMode.LIVE,
            database_name="precog_dev",
        )
        with patch.dict(os.environ, {"PRECOG_DANGEROUS_CONFIRMED": ""}):
            with pytest.raises(EnvironmentError) as exc_info:
                config.validate(require_confirmation=True)
            assert "PRECOG_DANGEROUS_CONFIRMED=yes" in str(exc_info.value)

    def test_validate_warning_with_confirmation_provided(self) -> None:
        """Test that warning combinations pass when confirmation is provided."""
        config = EnvironmentConfig(
            app_env=AppEnvironment.DEVELOPMENT,
            kalshi_mode=MarketMode.LIVE,
            database_name="precog_dev",
        )
        with patch.dict(os.environ, {"PRECOG_DANGEROUS_CONFIRMED": "yes"}):
            # Should issue warning but not raise
            with pytest.warns(UserWarning, match="dangerous environment combination"):
                config.validate(require_confirmation=True)

    def test_validate_allowed_passes_silently(self) -> None:
        """Test that allowed combinations pass without warnings."""
        config = EnvironmentConfig(
            app_env=AppEnvironment.TEST,
            kalshi_mode=MarketMode.DEMO,
            database_name="precog_test",
        )
        # Should not raise or warn
        config.validate()


class TestGetAppEnvironment:
    """Tests for get_app_environment() function."""

    def test_from_precog_env_variable(self) -> None:
        """Test that PRECOG_ENV takes highest priority."""
        with patch.dict(os.environ, {"PRECOG_ENV": "staging", "DB_NAME": "precog_test"}):
            result = get_app_environment()
            assert result == AppEnvironment.STAGING

    def test_inferred_from_db_name_test(self) -> None:
        """Test inference from DB_NAME containing 'test'."""
        with patch.dict(os.environ, {"DB_NAME": "precog_test"}, clear=False):
            # Clear PRECOG_ENV if set
            os.environ.pop("PRECOG_ENV", None)
            result = get_app_environment()
            assert result == AppEnvironment.TEST

    def test_inferred_from_db_name_staging(self) -> None:
        """Test inference from DB_NAME containing 'staging'."""
        with patch.dict(os.environ, {"DB_NAME": "precog_staging"}, clear=False):
            os.environ.pop("PRECOG_ENV", None)
            result = get_app_environment()
            assert result == AppEnvironment.STAGING

    def test_inferred_from_db_name_prod(self) -> None:
        """Test inference from DB_NAME containing 'prod'."""
        with patch.dict(os.environ, {"DB_NAME": "precog_prod"}, clear=False):
            os.environ.pop("PRECOG_ENV", None)
            result = get_app_environment()
            assert result == AppEnvironment.PRODUCTION

    def test_default_to_development(self) -> None:
        """Test default to DEVELOPMENT when no env vars set."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_app_environment()
            assert result == AppEnvironment.DEVELOPMENT

    def test_invalid_precog_env_falls_back(self) -> None:
        """Test that invalid PRECOG_ENV value falls back to inference."""
        with patch.dict(os.environ, {"PRECOG_ENV": "invalid", "DB_NAME": "precog_test"}):
            result = get_app_environment()
            assert result == AppEnvironment.TEST


class TestGetMarketMode:
    """Tests for get_market_mode() function."""

    def test_from_env_variable_demo(self) -> None:
        """Test reading KALSHI_MODE=demo from environment."""
        with patch.dict(os.environ, {"KALSHI_MODE": "demo"}):
            result = get_market_mode("kalshi")
            assert result == MarketMode.DEMO

    def test_from_env_variable_live(self) -> None:
        """Test reading KALSHI_MODE=live from environment."""
        with patch.dict(os.environ, {"KALSHI_MODE": "live"}):
            result = get_market_mode("kalshi")
            assert result == MarketMode.LIVE

    def test_default_to_demo(self) -> None:
        """Test default to DEMO when env var not set (safe default)."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_market_mode("kalshi")
            assert result == MarketMode.DEMO

    def test_invalid_value_defaults_to_demo(self) -> None:
        """Test that invalid values default to DEMO (safe default)."""
        with patch.dict(os.environ, {"KALSHI_MODE": "invalid"}):
            result = get_market_mode("kalshi")
            assert result == MarketMode.DEMO

    def test_other_market_env_var(self) -> None:
        """Test that other markets use their own env vars."""
        with patch.dict(os.environ, {"POLYMARKET_MODE": "live"}):
            result = get_market_mode("polymarket")
            assert result == MarketMode.LIVE


class TestGetDatabaseName:
    """Tests for get_database_name() function."""

    def test_explicit_db_name_override(self) -> None:
        """Test that explicit DB_NAME takes priority."""
        with patch.dict(os.environ, {"DB_NAME": "custom_db", "PRECOG_ENV": "staging"}):
            result = get_database_name()
            assert result == "custom_db"

    def test_derived_from_precog_env(self) -> None:
        """Test database name derived from PRECOG_ENV."""
        with patch.dict(os.environ, {"PRECOG_ENV": "staging"}, clear=False):
            os.environ.pop("DB_NAME", None)
            result = get_database_name()
            assert result == "precog_staging"

    def test_default_to_precog_dev(self) -> None:
        """Test default to precog_dev when no env vars set."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_database_name()
            assert result == "precog_dev"


class TestLoadEnvironmentConfig:
    """Tests for load_environment_config() function."""

    def test_load_complete_config(self) -> None:
        """Test loading a complete configuration."""
        with patch.dict(
            os.environ,
            {
                "PRECOG_ENV": "test",
                "KALSHI_MODE": "demo",
                "DB_HOST": "localhost",
                "DB_PORT": "5432",
                "DB_USER": "postgres",
            },
            clear=False,
        ):
            os.environ.pop("DB_NAME", None)
            config = load_environment_config(validate=False)
            assert config.app_env == AppEnvironment.TEST
            assert config.kalshi_mode == MarketMode.DEMO
            assert config.database_name == "precog_test"
            assert config.database_host == "localhost"
            assert config.database_port == 5432
            assert config.database_user == "postgres"

    def test_load_with_validation_blocking(self) -> None:
        """Test that validation blocks dangerous combinations."""
        with patch.dict(os.environ, {"PRECOG_ENV": "test", "KALSHI_MODE": "live"}):
            with pytest.raises(EnvironmentError):
                load_environment_config(validate=True)

    def test_load_without_validation(self) -> None:
        """Test that validation can be disabled."""
        with patch.dict(os.environ, {"PRECOG_ENV": "test", "KALSHI_MODE": "live"}):
            config = load_environment_config(validate=False)
            assert config.app_env == AppEnvironment.TEST
            assert config.kalshi_mode == MarketMode.LIVE


class TestRequireAppEnvironment:
    """Tests for require_app_environment() function."""

    def test_passes_when_environment_matches(self) -> None:
        """Test that no error when environment matches."""
        with patch.dict(os.environ, {"PRECOG_ENV": "test"}):
            # Should not raise
            require_app_environment(AppEnvironment.TEST)

    def test_raises_when_environment_mismatch(self) -> None:
        """Test that RuntimeError raised when environment doesn't match."""
        with patch.dict(os.environ, {"PRECOG_ENV": "dev"}):
            with pytest.raises(RuntimeError) as exc_info:
                require_app_environment(AppEnvironment.PRODUCTION)
            assert "requires production environment" in str(exc_info.value)
            assert "current environment is development" in str(exc_info.value)


class TestRequireMarketMode:
    """Tests for require_market_mode() function."""

    def test_passes_when_mode_matches(self) -> None:
        """Test that no error when mode matches."""
        with patch.dict(os.environ, {"KALSHI_MODE": "demo"}):
            # Should not raise
            require_market_mode("kalshi", MarketMode.DEMO)

    def test_raises_when_mode_mismatch(self) -> None:
        """Test that RuntimeError raised when mode doesn't match."""
        with patch.dict(os.environ, {"KALSHI_MODE": "demo"}):
            with pytest.raises(RuntimeError) as exc_info:
                require_market_mode("kalshi", MarketMode.LIVE)
            assert "requires kalshi in live mode" in str(exc_info.value)
            assert "current mode is demo" in str(exc_info.value)
