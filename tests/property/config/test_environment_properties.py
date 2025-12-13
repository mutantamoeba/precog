"""
Property-based tests for environment configuration.

Tests mathematical properties and invariants of environment configuration.

Reference: TESTING_STRATEGY_V3.2.md Section "Property Tests"
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from precog.config.environment import (
    AppEnvironment,
    CombinationSafety,
    EnvironmentConfig,
    MarketMode,
)


@pytest.mark.property
class TestAppEnvironmentProperties:
    """Property tests for AppEnvironment enum."""

    @given(
        st.sampled_from(
            ["dev", "development", "test", "testing", "staging", "stage", "prod", "production"]
        )
    )
    def test_from_string_always_returns_valid_enum(self, value: str) -> None:
        """All valid aliases should return a valid AppEnvironment."""
        result = AppEnvironment.from_string(value)
        assert isinstance(result, AppEnvironment)

    @given(
        st.text(min_size=1, max_size=20).filter(
            lambda x: x.lower()
            not in [
                "dev",
                "development",
                "test",
                "testing",
                "staging",
                "stage",
                "prod",
                "production",
            ]
        )
    )
    @settings(max_examples=50)
    def test_from_string_invalid_raises_value_error(self, value: str) -> None:
        """Invalid values should raise ValueError."""
        with pytest.raises(ValueError):
            AppEnvironment.from_string(value)

    @given(st.sampled_from(list(AppEnvironment)))
    def test_database_name_always_prefixed_with_precog(self, env: AppEnvironment) -> None:
        """Database name should always start with 'precog_'."""
        assert env.database_name.startswith("precog_")

    @given(st.sampled_from(list(AppEnvironment)))
    def test_is_production_only_true_for_production(self, env: AppEnvironment) -> None:
        """is_production should only be True for PRODUCTION."""
        if env == AppEnvironment.PRODUCTION:
            assert env.is_production is True
        else:
            assert env.is_production is False


@pytest.mark.property
class TestMarketModeProperties:
    """Property tests for MarketMode enum."""

    @given(st.sampled_from(["demo", "sandbox", "test", "live", "prod", "production"]))
    def test_from_string_always_returns_valid_enum(self, value: str) -> None:
        """All valid aliases should return a valid MarketMode."""
        result = MarketMode.from_string(value)
        assert isinstance(result, MarketMode)

    @given(st.sampled_from(list(MarketMode)))
    def test_uses_real_money_only_true_for_live(self, mode: MarketMode) -> None:
        """uses_real_money should only be True for LIVE."""
        if mode == MarketMode.LIVE:
            assert mode.uses_real_money is True
        else:
            assert mode.uses_real_money is False


@pytest.mark.property
class TestEnvironmentConfigProperties:
    """Property tests for EnvironmentConfig."""

    @given(st.sampled_from(list(AppEnvironment)), st.sampled_from(list(MarketMode)))
    def test_all_combinations_have_defined_safety(
        self, app_env: AppEnvironment, market_mode: MarketMode
    ) -> None:
        """Every combination should have a defined safety level."""
        config = EnvironmentConfig(
            app_env=app_env,
            kalshi_mode=market_mode,
            database_name=f"precog_{app_env.value}",
        )
        safety = config.get_combination_safety()
        assert safety in list(CombinationSafety)

    @given(st.sampled_from(list(AppEnvironment)))
    def test_test_with_live_always_blocked(self, app_env: AppEnvironment) -> None:
        """TEST environment with LIVE mode should always be BLOCKED."""
        if app_env == AppEnvironment.TEST:
            config = EnvironmentConfig(
                app_env=app_env,
                kalshi_mode=MarketMode.LIVE,
                database_name="precog_test",
            )
            assert config.get_combination_safety() == CombinationSafety.BLOCKED

    @given(st.sampled_from(list(AppEnvironment)))
    def test_production_with_demo_always_blocked(self, app_env: AppEnvironment) -> None:
        """PRODUCTION environment with DEMO mode should always be BLOCKED."""
        if app_env == AppEnvironment.PRODUCTION:
            config = EnvironmentConfig(
                app_env=app_env,
                kalshi_mode=MarketMode.DEMO,
                database_name="precog_prod",
            )
            assert config.get_combination_safety() == CombinationSafety.BLOCKED

    @given(
        st.sampled_from([AppEnvironment.DEVELOPMENT, AppEnvironment.TEST, AppEnvironment.STAGING]),
        st.sampled_from([MarketMode.DEMO]),
    )
    def test_non_prod_with_demo_always_allowed(
        self, app_env: AppEnvironment, mode: MarketMode
    ) -> None:
        """Non-production with DEMO should be ALLOWED."""
        config = EnvironmentConfig(
            app_env=app_env,
            kalshi_mode=mode,
            database_name=app_env.database_name,
        )
        assert config.get_combination_safety() == CombinationSafety.ALLOWED
