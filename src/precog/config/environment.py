"""
Two-Axis Environment Configuration System.

This module implements a two-axis environment model that independently controls:
1. **Application Environment (PRECOG_ENV)**: Controls database, logging, safety guards
2. **Market API Mode ({MARKET}_MODE)**: Controls API endpoints per prediction market

Why Two Axes?
-------------
Database environments and API environments serve different purposes:
- Database: Internal infrastructure (dev/test/staging/prod)
- API: External service connections (demo/live)

A developer might want to:
- Use staging database with demo API (safe pre-prod testing)
- Use dev database with live API (debugging production issues - dangerous!)
- Use test database with demo API (automated integration tests)

Separating these concerns provides flexibility while maintaining safety.

Safety Guardrails:
------------------
Not all combinations are safe:
- test + live API = BLOCKED (never test against live money)
- production + demo API = BLOCKED (production must use real APIs)
- dev + live API = WARNING (requires confirmation)

Architecture:
-------------
This module follows the "Environment Object" pattern:
1. Read configuration from environment variables
2. Validate combinations at startup
3. Provide typed accessors for environment values
4. Log active configuration for debugging

Reference: docs/guides/ENVIRONMENT_CONFIGURATION_GUIDE_V1.0.md
Related: Issue #202 (Two-Axis Environment Configuration)
Related Requirements: REQ-CONFIG-001 (Environment Configuration)
Related ADR: ADR-105 (Two-Axis Environment Model)
"""

import os
import warnings
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Literal, overload

from dotenv import load_dotenv

from precog.utils.logger import get_logger

# Load environment variables
load_dotenv()

logger = get_logger(__name__)


class AppEnvironment(str, Enum):
    """
    Application environment (Axis 1).

    Controls internal infrastructure: database, logging level, safety guards.

    Values:
        DEVELOPMENT: Local development with precog_dev database
        TEST: Automated testing with precog_test database
        STAGING: Pre-production validation with precog_staging database
        PRODUCTION: Live trading with precog_prod database

    Educational Note:
        Using Enum instead of raw strings provides:
        - Type safety (IDE autocomplete, type checking)
        - Exhaustive pattern matching
        - Clear documentation of valid values
        - Protection against typos ("devleopment" vs DEVELOPMENT)
    """

    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"

    @classmethod
    def from_string(cls, value: str) -> "AppEnvironment":
        """
        Parse string to AppEnvironment enum.

        Handles common aliases:
        - "dev" -> DEVELOPMENT
        - "prod" -> PRODUCTION

        Args:
            value: Environment string (case-insensitive)

        Returns:
            AppEnvironment enum value

        Raises:
            ValueError: If value is not a valid environment

        Example:
            >>> AppEnvironment.from_string("dev")
            AppEnvironment.DEVELOPMENT
            >>> AppEnvironment.from_string("PRODUCTION")
            AppEnvironment.PRODUCTION
        """
        value_lower = value.lower().strip()

        # Handle common aliases
        aliases = {
            "dev": cls.DEVELOPMENT,
            "development": cls.DEVELOPMENT,
            "test": cls.TEST,
            "testing": cls.TEST,
            "staging": cls.STAGING,
            "stage": cls.STAGING,
            "prod": cls.PRODUCTION,
            "production": cls.PRODUCTION,
        }

        if value_lower in aliases:
            return aliases[value_lower]

        valid = list(aliases.keys())
        msg = f"Invalid environment: '{value}'. Valid options: {valid}"
        raise ValueError(msg)

    @property
    def database_name(self) -> str:
        """
        Get default database name for this environment.

        Returns:
            Database name string (e.g., "precog_dev", "precog_test")

        Example:
            >>> AppEnvironment.DEVELOPMENT.database_name
            'precog_dev'
        """
        mapping = {
            self.DEVELOPMENT: "precog_dev",
            self.TEST: "precog_test",
            self.STAGING: "precog_staging",
            self.PRODUCTION: "precog_prod",
        }
        return mapping[self]

    @property
    def is_production(self) -> bool:
        """Check if this is a production environment."""
        return self == self.PRODUCTION

    @property
    def is_safe_for_testing(self) -> bool:
        """Check if this environment is safe for destructive testing operations."""
        return self in (self.DEVELOPMENT, self.TEST)


class MarketMode(str, Enum):
    """
    Market API mode (Axis 2).

    Controls external API endpoints for each prediction market.

    Values:
        DEMO: Use demo/sandbox API (fake money, safe for testing)
        LIVE: Use production API (real money, actual trades)

    Educational Note:
        Each prediction market (Kalshi, Polymarket, etc.) may have
        different API endpoints for demo vs live. This enum provides
        a unified abstraction across all markets.
    """

    DEMO = "demo"
    LIVE = "live"

    @classmethod
    def from_string(cls, value: str) -> "MarketMode":
        """
        Parse string to MarketMode enum.

        Args:
            value: Mode string (case-insensitive)

        Returns:
            MarketMode enum value

        Raises:
            ValueError: If value is not a valid mode

        Example:
            >>> MarketMode.from_string("demo")
            MarketMode.DEMO
            >>> MarketMode.from_string("LIVE")
            MarketMode.LIVE
        """
        value_lower = value.lower().strip()

        aliases = {
            "demo": cls.DEMO,
            "sandbox": cls.DEMO,
            "test": cls.DEMO,
            "live": cls.LIVE,
            "prod": cls.LIVE,
            "production": cls.LIVE,
        }

        if value_lower in aliases:
            return aliases[value_lower]

        valid = ["demo", "live"]
        msg = f"Invalid market mode: '{value}'. Valid options: {valid}"
        raise ValueError(msg)

    @property
    def uses_real_money(self) -> bool:
        """Check if this mode involves real money."""
        return self == self.LIVE


class CombinationSafety(str, Enum):
    """Safety level for environment + market mode combinations."""

    ALLOWED = "allowed"
    WARNING = "warning"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class EnvironmentConfig:
    """
    Immutable configuration for the two-axis environment model.

    This dataclass holds the resolved environment configuration,
    including the app environment, market modes, and database name.

    Attributes:
        app_env: Application environment (controls database)
        kalshi_mode: Kalshi API mode (demo/live)
        database_name: Resolved database name (may be overridden)
        database_host: Database host
        database_port: Database port
        database_user: Database user

    Educational Note:
        Using frozen=True makes this dataclass immutable (hashable).
        This prevents accidental modification after creation and
        enables use as dictionary keys or in sets.
    """

    app_env: AppEnvironment
    kalshi_mode: MarketMode
    database_name: str
    database_host: str = "localhost"
    database_port: int = 5432
    database_user: str = "postgres"

    # Combination safety rules
    # Key: (AppEnvironment, MarketMode) -> CombinationSafety
    SAFETY_RULES: ClassVar[dict[tuple[AppEnvironment, MarketMode], CombinationSafety]] = {
        # Development combinations
        (AppEnvironment.DEVELOPMENT, MarketMode.DEMO): CombinationSafety.ALLOWED,
        (AppEnvironment.DEVELOPMENT, MarketMode.LIVE): CombinationSafety.WARNING,
        # Test combinations
        (AppEnvironment.TEST, MarketMode.DEMO): CombinationSafety.ALLOWED,
        (AppEnvironment.TEST, MarketMode.LIVE): CombinationSafety.BLOCKED,
        # Staging combinations
        (AppEnvironment.STAGING, MarketMode.DEMO): CombinationSafety.ALLOWED,
        (AppEnvironment.STAGING, MarketMode.LIVE): CombinationSafety.WARNING,
        # Production combinations
        (AppEnvironment.PRODUCTION, MarketMode.DEMO): CombinationSafety.BLOCKED,
        (AppEnvironment.PRODUCTION, MarketMode.LIVE): CombinationSafety.ALLOWED,
    }

    def get_combination_safety(self) -> CombinationSafety:
        """
        Check safety level of current environment + market mode combination.

        Returns:
            CombinationSafety enum value

        Example:
            >>> config = EnvironmentConfig(
            ...     app_env=AppEnvironment.TEST,
            ...     kalshi_mode=MarketMode.LIVE,
            ...     database_name="precog_test"
            ... )
            >>> config.get_combination_safety()
            CombinationSafety.BLOCKED
        """
        key = (self.app_env, self.kalshi_mode)
        return self.SAFETY_RULES.get(key, CombinationSafety.WARNING)

    def validate(self, require_confirmation: bool = False) -> None:
        """
        Validate the environment configuration.

        Checks that the combination of app environment and market modes
        is safe. Raises exceptions for blocked combinations and warnings
        for dangerous-but-allowed combinations.

        Args:
            require_confirmation: If True, require PRECOG_DANGEROUS_CONFIRMED=yes
                                  for WARNING-level combinations

        Raises:
            EnvironmentError: If combination is BLOCKED
            UserWarning: If combination is WARNING (logged but not raised)

        Example:
            >>> config = EnvironmentConfig(
            ...     app_env=AppEnvironment.TEST,
            ...     kalshi_mode=MarketMode.LIVE,
            ...     database_name="precog_test"
            ... )
            >>> config.validate()  # Raises EnvironmentError
        """
        safety = self.get_combination_safety()

        if safety == CombinationSafety.BLOCKED:
            msg = (
                f"BLOCKED: Environment combination not allowed!\n"
                f"  App Environment: {self.app_env.value}\n"
                f"  Kalshi Mode: {self.kalshi_mode.value}\n"
                f"\n"
                f"Reason: "
            )

            if self.app_env == AppEnvironment.TEST and self.kalshi_mode == MarketMode.LIVE:
                msg += (
                    "Test environment must NEVER use live API (risk of using real money in tests)"
                )
            elif self.app_env == AppEnvironment.PRODUCTION and self.kalshi_mode == MarketMode.DEMO:
                msg += "Production environment must use live API (demo API has no real markets)"
            else:
                msg += "This combination is not supported"

            raise OSError(msg)

        if safety == CombinationSafety.WARNING:
            warning_msg = (
                f"WARNING: Potentially dangerous environment combination!\n"
                f"  App Environment: {self.app_env.value}\n"
                f"  Kalshi Mode: {self.kalshi_mode.value}\n"
            )

            if self.app_env == AppEnvironment.DEVELOPMENT and self.kalshi_mode == MarketMode.LIVE:
                warning_msg += "  Risk: Development database with LIVE API (real money!)\n"
            elif self.app_env == AppEnvironment.STAGING and self.kalshi_mode == MarketMode.LIVE:
                warning_msg += "  Risk: Staging database with LIVE API (real money!)\n"

            if require_confirmation:
                confirmed = os.getenv("PRECOG_DANGEROUS_CONFIRMED", "").lower() == "yes"
                if not confirmed:
                    warning_msg += (
                        "\n  To proceed, set PRECOG_DANGEROUS_CONFIRMED=yes in environment.\n"
                        "  This confirms you understand the risks."
                    )
                    raise OSError(warning_msg)

            # Log warning but don't block
            logger.warning(warning_msg)
            warnings.warn(warning_msg, UserWarning, stacklevel=2)

    def log_configuration(self) -> None:
        """
        Log the current environment configuration.

        Useful at startup to verify the active configuration.
        """
        logger.info(
            "environment_configuration",
            app_env=self.app_env.value,
            kalshi_mode=self.kalshi_mode.value,
            database_name=self.database_name,
            database_host=self.database_host,
            database_port=self.database_port,
            combination_safety=self.get_combination_safety().value,
        )


def get_app_environment() -> AppEnvironment:
    """
    Get current application environment.

    Resolution order:
    1. PRECOG_ENV environment variable (if set and valid)
    2. ENVIRONMENT environment variable (alias used in .env template)
    3. Default to DEVELOPMENT

    Returns:
        AppEnvironment enum value

    Example:
        >>> os.environ["PRECOG_ENV"] = "staging"
        >>> get_app_environment()
        AppEnvironment.STAGING
    """
    # Check explicit PRECOG_ENV first
    precog_env = os.getenv("PRECOG_ENV")
    if precog_env:
        try:
            return AppEnvironment.from_string(precog_env)
        except ValueError:
            logger.warning(f"Invalid PRECOG_ENV value: '{precog_env}', falling back")

    # Check ENVIRONMENT (alias used in .env template)
    environment = os.getenv("ENVIRONMENT")
    if environment:
        try:
            return AppEnvironment.from_string(environment)
        except ValueError:
            logger.warning(f"Invalid ENVIRONMENT value: '{environment}', falling back")

    # Default to development (safest)
    return AppEnvironment.DEVELOPMENT


def get_market_mode(market: str) -> MarketMode:
    """
    Get API mode for a specific market.

    Looks for {MARKET}_MODE environment variable (e.g., KALSHI_MODE).

    Args:
        market: Market name (e.g., "kalshi", "polymarket")

    Returns:
        MarketMode enum value (defaults to DEMO if not set)

    Example:
        >>> os.environ["KALSHI_MODE"] = "live"
        >>> get_market_mode("kalshi")
        MarketMode.LIVE

    Educational Note:
        Defaulting to DEMO is a safety measure. If someone forgets
        to set the mode, they won't accidentally trade real money.
    """
    env_var = f"{market.upper()}_MODE"
    mode_str = os.getenv(env_var, "demo")

    try:
        return MarketMode.from_string(mode_str)
    except ValueError:
        logger.warning(f"Invalid {env_var} value: '{mode_str}', defaulting to DEMO")
        return MarketMode.DEMO


def get_env_prefix() -> str:
    """
    Get the environment variable prefix for the current app environment.

    Maps AppEnvironment to the prefix used in .env for prefixed vars:
    - DEVELOPMENT -> "DEV"
    - TEST -> "TEST"
    - STAGING -> "STAGING"
    - PRODUCTION -> "PROD"

    Returns:
        Prefix string (e.g., "DEV", "PROD")

    Example:
        >>> os.environ["PRECOG_ENV"] = "staging"
        >>> get_env_prefix()
        'STAGING'

    Educational Note:
        This prefix maps to the naming convention in .env where each
        environment has its own set of variables (DEV_DB_NAME, STAGING_DB_HOST,
        PROD_KALSHI_API_KEY, etc.). Changing PRECOG_ENV switches all
        credentials and configuration at once.
    """
    app_env = get_app_environment()
    prefix_map = {
        AppEnvironment.DEVELOPMENT: "DEV",
        AppEnvironment.TEST: "TEST",
        AppEnvironment.STAGING: "STAGING",
        AppEnvironment.PRODUCTION: "PROD",
    }
    return prefix_map[app_env]


@overload
def get_prefixed_env(var_name: str, default: str) -> str: ...


@overload
def get_prefixed_env(var_name: str, default: None = None) -> str | None: ...


def get_prefixed_env(var_name: str, default: str | None = None) -> str | None:
    """
    Get an environment variable using the environment-aware prefix pattern.

    Resolution order:
    1. {PREFIX}_{var_name} (e.g., DEV_DB_NAME when PRECOG_ENV=dev)
    2. {var_name} (flat fallback for CI/overrides)
    3. default

    Args:
        var_name: The unprefixed variable name (e.g., "DB_NAME", "DB_HOST")
        default: Default value if neither prefixed nor flat var is found

    Returns:
        Resolved value or default

    Example:
        >>> os.environ["PRECOG_ENV"] = "dev"
        >>> os.environ["DEV_DB_NAME"] = "precog_dev"
        >>> get_prefixed_env("DB_NAME")
        'precog_dev'

    Educational Note:
        The resolution order (prefixed -> flat -> default) ensures:
        - Local dev: uses prefixed vars from .env (DEV_DB_NAME, etc.)
        - CI: uses flat vars set by GitHub Actions (DB_NAME, etc.)
        - Fallback: sensible defaults prevent crashes on missing vars
        Uses ``is not None`` (not truthiness) so empty strings are respected.
    """
    prefix = get_env_prefix()
    prefixed = os.getenv(f"{prefix}_{var_name}")
    if prefixed is not None:
        return prefixed
    flat = os.getenv(var_name)
    if flat is not None:
        return flat
    return default


def get_database_name() -> str:
    """
    Get database name based on environment configuration.

    Resolution order:
    1. {PREFIX}_DB_NAME (e.g., DEV_DB_NAME when PRECOG_ENV=dev)
    2. DB_NAME (flat fallback for CI/overrides)
    3. Derived from AppEnvironment (e.g., DEVELOPMENT -> precog_dev)

    Returns:
        Database name string

    Example:
        >>> os.environ["PRECOG_ENV"] = "staging"
        >>> os.environ["STAGING_DB_NAME"] = "precog_staging"
        >>> get_database_name()
        'precog_staging'
    """
    resolved = get_prefixed_env("DB_NAME")
    if resolved:
        return resolved

    # Derive from app environment
    app_env = get_app_environment()
    return app_env.database_name


def load_environment_config(
    validate: bool = True,
    require_confirmation: bool = False,
) -> EnvironmentConfig:
    """
    Load complete environment configuration from environment variables.

    This is the main entry point for getting the environment config.
    It reads all relevant environment variables and constructs an
    immutable EnvironmentConfig object.

    Args:
        validate: If True, validate the configuration (default: True)
        require_confirmation: If True, require confirmation for dangerous
                              combinations (default: False)

    Returns:
        EnvironmentConfig with all resolved values

    Raises:
        EnvironmentError: If configuration is invalid or blocked

    Example:
        >>> config = load_environment_config()
        >>> print(f"Database: {config.database_name}")
        >>> print(f"Kalshi Mode: {config.kalshi_mode.value}")

    Educational Note:
        This function follows the "Factory" pattern - it creates and
        configures a complex object (EnvironmentConfig) based on
        various inputs (environment variables).
    """
    app_env = get_app_environment()
    kalshi_mode = get_market_mode("kalshi")
    database_name = get_database_name()

    config = EnvironmentConfig(
        app_env=app_env,
        kalshi_mode=kalshi_mode,
        database_name=database_name,
        database_host=get_prefixed_env("DB_HOST", "localhost"),
        database_port=int(get_prefixed_env("DB_PORT", "5432")),
        database_user=get_prefixed_env("DB_USER", "postgres"),
    )

    if validate:
        config.validate(require_confirmation=require_confirmation)

    return config


def require_app_environment(required: AppEnvironment) -> None:
    """
    Ensure the application is running in the expected environment.

    Use this at the start of scripts that should only run in
    specific environments.

    Args:
        required: Expected AppEnvironment

    Raises:
        RuntimeError: If current environment doesn't match

    Example:
        >>> require_app_environment(AppEnvironment.DEVELOPMENT)
        >>> # Only runs if PRECOG_ENV=development
    """
    current = get_app_environment()
    if current != required:
        msg = (
            f"This operation requires {required.value} environment, "
            f"but current environment is {current.value}.\n"
            f"Set PRECOG_ENV={required.value} to proceed."
        )
        raise RuntimeError(msg)


def require_market_mode(market: str, required: MarketMode) -> None:
    """
    Ensure a market is configured with the expected mode.

    Args:
        market: Market name (e.g., "kalshi")
        required: Expected MarketMode

    Raises:
        RuntimeError: If current mode doesn't match

    Example:
        >>> require_market_mode("kalshi", MarketMode.DEMO)
        >>> # Only runs if KALSHI_MODE=demo
    """
    current = get_market_mode(market)
    if current != required:
        env_var = f"{market.upper()}_MODE"
        msg = (
            f"This operation requires {market} in {required.value} mode, "
            f"but current mode is {current.value}.\n"
            f"Set {env_var}={required.value} to proceed."
        )
        raise RuntimeError(msg)


def derive_execution_environment(
    app_env: AppEnvironment,
    market_mode: MarketMode,
) -> Literal["live", "paper", "backtest"]:
    """
    Translate the two-axis runtime environment to a single execution_environment value.

    This function is the SINGLE LINE OF TRUTH in the codebase for the runtime
    mapping from ``(PRECOG_ENV, MARKET_MODE)`` to the
    ``execution_environment`` value persisted on money-touching SCD tables
    (``positions``, ``trades``, ``account_balance``). Every CRUD caller that
    needs an ``execution_environment`` value MUST obtain it from this
    function — never construct the literal inline, never read it from
    YAML, never pass a constant.

    Why this function exists:
        Pre-2026, the codebase had FIVE unreconciled vocabularies for the
        same concept (``PRECOG_ENV``, ``MarketMode``, the
        ``execution_environment`` DB column, the dead ``trading.yaml
        environment:`` field, and ``KalshiClient.environment``). No
        translator existed; the mapping lived only in human memory. The
        result was the #662/#686/#622 cross-environment-contamination bug
        class. This function eliminates the implicit mapping by making it
        a single, testable, validated function.

    Mapping (after SAFETY_RULES validation):
        ``MarketMode.LIVE`` -> ``'live'``
        ``MarketMode.DEMO`` -> ``'paper'``
        ``'backtest'`` -> set explicitly by the backtest entry point only,
            NEVER derived here from runtime axes.

    Args:
        app_env: The application environment from ``get_app_environment()``.
        market_mode: The market API mode from ``get_market_mode("kalshi")``
            or equivalent for other markets.

    Returns:
        One of ``'live'`` or ``'paper'``. ``'backtest'`` is never returned
        from this function.

    Raises:
        ValueError: If the ``(app_env, market_mode)`` combination is BLOCKED
            by ``EnvironmentConfig.SAFETY_RULES`` (e.g., ``test+live``,
            ``prod+demo``). The error message includes the blocked
            combination. This guard converts a silent contamination risk
            into a loud, traceable failure at the application boundary,
            BEFORE any DB write happens.

    Example:
        >>> from precog.config.environment import (
        ...     derive_execution_environment,
        ...     get_app_environment,
        ...     get_market_mode,
        ... )
        >>> exec_env = derive_execution_environment(
        ...     get_app_environment(),
        ...     get_market_mode("kalshi"),
        ... )
        >>> # 'live' or 'paper' depending on env vars

        >>> # Backtest entry point sets the value explicitly:
        >>> # backtest_runner.py:
        >>> #     create_position(..., execution_environment='backtest')
        >>> # NEVER call derive_execution_environment() from a backtest path.

    Educational Note:
        Why this function does not handle ``'backtest'``:
        Backtest is not a runtime axis — it is a separate execution mode
        triggered by an explicit backtest entry point (e.g.,
        ``backtest_runner``). Mixing it into the runtime translator would
        force every CRUD caller to know about backtest semantics, which is
        the opposite of single-line-of-truth. The backtest entry point
        sets the literal ``'backtest'`` directly when calling CRUD
        functions; this translator handles only the live/paper runtime
        distinction.

    Related:
        - REQ-SAFE-005 (proposed): Mandatory translator function for
          execution environment derivation
        - findings_622_686_synthesis.md (Mulder + Holden design pass)
        - findings_622_686_mulder.md (5 unreconciled vocabularies analysis)
        - ADR-107: Single-Database Architecture with Execution Environments
        - ADR-105: Two-Axis Environment Model
        - Migration 0051: account_balance.execution_environment + the dead
          per-mode views drop
        - Issues #622, #662, #686 (the bug class this function prevents)
    """
    # Lookup the safety rule for this combination. EnvironmentConfig owns
    # the SAFETY_RULES dict (the canonical source of truth for which
    # combinations are allowed); this function only adds the additional
    # constraint that BLOCKED combinations cannot derive a value at all.
    safety = EnvironmentConfig.SAFETY_RULES.get((app_env, market_mode), CombinationSafety.WARNING)
    if safety == CombinationSafety.BLOCKED:
        msg = (
            f"BLOCKED combination: ({app_env.value}, {market_mode.value}). "
            f"This combination is not allowed by EnvironmentConfig.SAFETY_RULES "
            f"and cannot derive a valid execution_environment. Refusing to "
            f"return any value to prevent silent cross-environment "
            f"contamination on money-touching SCD tables. See ADR-105 and "
            f"the #622+#686 synthesis for the full rationale."
        )
        raise ValueError(msg)

    # WARNING combinations are allowed (e.g., dev + live API for production
    # debugging). The mapping is the same as ALLOWED combinations: the
    # safety warning is logged elsewhere via EnvironmentConfig.validate().
    if market_mode == MarketMode.LIVE:
        return "live"
    if market_mode == MarketMode.DEMO:
        return "paper"

    # Defensive: every MarketMode value is handled above. mypy correctly
    # infers this is unreachable today (MarketMode has exactly LIVE + DEMO),
    # but the guard exists to fail loudly if a future MarketMode value is
    # added without updating this function. The `type: ignore` suppresses
    # the unreachable warning at the cost of preserving runtime defense.
    msg = (  # type: ignore[unreachable]
        f"Unhandled MarketMode value in derive_execution_environment: "
        f"{market_mode!r}. This function must be updated when new "
        f"MarketMode values are added."
    )
    raise ValueError(msg)
