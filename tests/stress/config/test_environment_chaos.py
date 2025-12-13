"""
Chaos tests for environment configuration.

Tests failure scenarios and edge cases for environment configuration.

Reference: TESTING_STRATEGY_V3.2.md Section "Chaos Tests"
"""

import pytest

from precog.config.environment import (
    AppEnvironment,
    CombinationSafety,
    EnvironmentConfig,
    MarketMode,
    get_app_environment,
    get_market_mode,
)


@pytest.mark.chaos
class TestEnvironmentChaos:
    """Chaos tests for environment detection edge cases."""

    def test_missing_environment_vars_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test behavior when environment variables are missing."""
        # Remove all relevant env vars
        monkeypatch.delenv("PRECOG_ENV", raising=False)
        monkeypatch.delenv("DB_NAME", raising=False)

        # Should fall back to default (development)
        env = get_app_environment()
        assert env == AppEnvironment.DEVELOPMENT

    def test_missing_market_mode_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test behavior when market mode env var is missing."""
        monkeypatch.delenv("KALSHI_MODE", raising=False)

        # Should fall back to default (demo)
        mode = get_market_mode("kalshi")
        assert mode == MarketMode.DEMO

    def test_invalid_environment_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test behavior with invalid environment value."""
        monkeypatch.setenv("PRECOG_ENV", "invalid_env")

        with pytest.raises(ValueError):
            get_app_environment()

    def test_invalid_market_mode_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test behavior with invalid market mode value."""
        monkeypatch.setenv("KALSHI_MODE", "invalid_mode")

        with pytest.raises(ValueError):
            get_market_mode("kalshi")

    def test_empty_environment_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test behavior with empty environment value."""
        monkeypatch.setenv("PRECOG_ENV", "")
        monkeypatch.delenv("DB_NAME", raising=False)

        # Empty string should be treated as missing, fall back to default
        env = get_app_environment()
        assert env == AppEnvironment.DEVELOPMENT

    def test_whitespace_environment_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test behavior with whitespace-only environment value."""
        monkeypatch.setenv("PRECOG_ENV", "   ")
        monkeypatch.delenv("DB_NAME", raising=False)

        # Whitespace should be treated as missing
        env = get_app_environment()
        assert env == AppEnvironment.DEVELOPMENT


@pytest.mark.chaos
class TestEnvironmentConfigChaos:
    """Chaos tests for EnvironmentConfig edge cases."""

    def test_rapid_config_creation_destruction(self) -> None:
        """Test creating and destroying many configs rapidly."""
        configs = []
        for _ in range(1000):
            config = EnvironmentConfig(
                app_env=AppEnvironment.DEVELOPMENT,
                kalshi_mode=MarketMode.DEMO,
                database_name="precog_dev",
            )
            configs.append(config)

        # All should be valid
        for config in configs:
            assert config.get_combination_safety() == CombinationSafety.ALLOWED

        # Destroy all
        configs.clear()

    def test_all_environment_combinations(self) -> None:
        """Test all possible environment/mode combinations."""
        for env in AppEnvironment:
            for mode in MarketMode:
                config = EnvironmentConfig(
                    app_env=env,
                    kalshi_mode=mode,
                    database_name=env.database_name,
                )
                # Should always return a valid safety level
                safety = config.get_combination_safety()
                assert safety in list(CombinationSafety)

    def test_blocked_combination_validation_raises(self) -> None:
        """Test that blocked combinations raise on validation."""
        # TEST + LIVE is always blocked
        config = EnvironmentConfig(
            app_env=AppEnvironment.TEST,
            kalshi_mode=MarketMode.LIVE,
            database_name="precog_test",
        )

        assert config.get_combination_safety() == CombinationSafety.BLOCKED

        with pytest.raises(OSError):
            config.validate()

    def test_production_with_demo_blocked(self) -> None:
        """Test that PRODUCTION + DEMO is blocked."""
        config = EnvironmentConfig(
            app_env=AppEnvironment.PRODUCTION,
            kalshi_mode=MarketMode.DEMO,
            database_name="precog_prod",
        )

        assert config.get_combination_safety() == CombinationSafety.BLOCKED

        with pytest.raises(OSError):
            config.validate()

    def test_warning_combination_logs_warning(self) -> None:
        """Test that warning combinations log but don't raise."""
        config = EnvironmentConfig(
            app_env=AppEnvironment.DEVELOPMENT,
            kalshi_mode=MarketMode.LIVE,
            database_name="precog_dev",
        )

        assert config.get_combination_safety() == CombinationSafety.WARNING

        # Should warn but not raise
        with pytest.warns(UserWarning, match="WARNING"):
            config.validate(require_confirmation=False)


@pytest.mark.chaos
class TestAppEnvironmentChaos:
    """Chaos tests for AppEnvironment enum."""

    def test_case_insensitive_from_string(self) -> None:
        """Test that from_string is case-insensitive."""
        assert AppEnvironment.from_string("DEV") == AppEnvironment.DEVELOPMENT
        assert AppEnvironment.from_string("Dev") == AppEnvironment.DEVELOPMENT
        assert AppEnvironment.from_string("DEVELOPMENT") == AppEnvironment.DEVELOPMENT
        assert AppEnvironment.from_string("Development") == AppEnvironment.DEVELOPMENT

    def test_all_aliases_map_correctly(self) -> None:
        """Test all documented aliases map to correct environments."""
        alias_map = {
            "dev": AppEnvironment.DEVELOPMENT,
            "development": AppEnvironment.DEVELOPMENT,
            "test": AppEnvironment.TEST,
            "testing": AppEnvironment.TEST,
            "staging": AppEnvironment.STAGING,
            "stage": AppEnvironment.STAGING,
            "prod": AppEnvironment.PRODUCTION,
            "production": AppEnvironment.PRODUCTION,
        }

        for alias, expected in alias_map.items():
            result = AppEnvironment.from_string(alias)
            assert result == expected, f"Alias '{alias}' mapped to {result}, expected {expected}"

    def test_database_names_unique(self) -> None:
        """Test that all database names are unique."""
        names = [env.database_name for env in AppEnvironment]
        assert len(names) == len(set(names)), "Database names must be unique"

    def test_database_names_valid_format(self) -> None:
        """Test that database names have valid format."""
        for env in AppEnvironment:
            name = env.database_name
            assert name.startswith("precog_"), f"DB name {name} must start with precog_"
            assert name.islower() or name.replace("_", "").islower(), (
                f"DB name {name} should be lowercase"
            )


@pytest.mark.chaos
class TestMarketModeChaos:
    """Chaos tests for MarketMode enum."""

    def test_case_insensitive_from_string(self) -> None:
        """Test that from_string is case-insensitive."""
        assert MarketMode.from_string("DEMO") == MarketMode.DEMO
        assert MarketMode.from_string("Demo") == MarketMode.DEMO
        assert MarketMode.from_string("LIVE") == MarketMode.LIVE
        assert MarketMode.from_string("Live") == MarketMode.LIVE

    def test_all_aliases_map_correctly(self) -> None:
        """Test all documented aliases map to correct modes."""
        alias_map = {
            "demo": MarketMode.DEMO,
            "sandbox": MarketMode.DEMO,
            "test": MarketMode.DEMO,
            "live": MarketMode.LIVE,
            "prod": MarketMode.LIVE,
            "production": MarketMode.LIVE,
        }

        for alias, expected in alias_map.items():
            result = MarketMode.from_string(alias)
            assert result == expected, f"Alias '{alias}' mapped to {result}, expected {expected}"

    def test_only_live_uses_real_money(self) -> None:
        """Test that only LIVE mode uses real money."""
        for mode in MarketMode:
            if mode == MarketMode.LIVE:
                assert mode.uses_real_money is True
            else:
                assert mode.uses_real_money is False
