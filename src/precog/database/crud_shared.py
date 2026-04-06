"""
Shared constants, helpers, and type aliases used across CRUD domain modules.

Extracted from crud_operations.py during Phase 1a domain split to avoid
circular imports and provide a single source of truth for cross-cutting
definitions.

Contents:
    - ExecutionEnvironment: Literal type alias for order execution contexts
    - SystemHealthComponent: Literal type alias for system health monitoring
    - VALID_SYSTEM_HEALTH_COMPONENTS: Runtime frozenset for O(1) validation
    - DecimalEncoder: JSON encoder that preserves Decimal precision
    - _convert_config_strings_to_decimal(): Config restoration helper
    - validate_decimal(): Runtime Decimal type enforcement
    - retry_on_scd_unique_conflict(): SCD first-insert race retry helper
"""

import json
import logging
from collections.abc import Callable
from decimal import Decimal
from typing import Any, Literal

import psycopg2.errors

# Type alias for execution environment - matches database ENUM (Migration 0008)
# - 'live': Production trading with Kalshi Production API (real money)
# - 'paper': Integration testing with Kalshi Demo/Sandbox API (no real money)
# - 'backtest': Historical data simulation (no API calls)
ExecutionEnvironment = Literal["live", "paper", "backtest"]

# App-layer allowlist for system_health.component (ADR-114, Migration 0043).
# The PostgreSQL CHECK constraint was dropped in migration 0043 so new data
# sources can be added here without a schema migration. Add new components
# to this Literal and to VALID_SYSTEM_HEALTH_COMPONENTS below.
#
# Tier A components (active data sources):
#   - 'kalshi_api':      Kalshi prediction market API
#   - 'espn_api':        ESPN sports data API
#   - 'database':        PostgreSQL database connection
# Operational components:
#   - 'backup':          Database backup system
# Infrastructure components:
#   - 'edge_detector':   Edge detection engine
#   - 'trading_engine':  Trade execution engine
#   - 'websocket':       WebSocket connections
# Planned Tier A components (not yet active):
#   - 'polymarket_api':  Polymarket prediction market API
SystemHealthComponent = Literal[
    "kalshi_api",
    "polymarket_api",
    "espn_api",
    "database",
    "backup",
    "edge_detector",
    "trading_engine",
    "websocket",
]

# Runtime set for O(1) validation in upsert_system_health.
# Must stay in sync with the SystemHealthComponent Literal above.
VALID_SYSTEM_HEALTH_COMPONENTS: frozenset[str] = frozenset(
    SystemHealthComponent.__args__  # type: ignore[attr-defined]
)


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder that converts Decimal to string.

    This encoder is required because Python's json module doesn't natively
    support Decimal serialization. We convert Decimal to string to preserve
    precision (Pattern 1: NEVER USE FLOAT).

    Educational Note:
        Why not convert to float? Because float introduces rounding errors!
        Example:
            Decimal("0.4975") -> float -> 0.49750000000000005 ❌ WRONG
            Decimal("0.4975") -> str -> "0.4975" ✅ CORRECT

    Example:
        >>> config = {"max_edge": Decimal("0.05"), "kelly_fraction": Decimal("0.10")}
        >>> json.dumps(config, cls=DecimalEncoder)
        '{"max_edge": "0.05", "kelly_fraction": "0.10"}'

    Reference:
        - Pattern 1 (Decimal Precision): docs/guides/DEVELOPMENT_PATTERNS_V1.2.md
        - ADR-002: Decimal precision for all financial calculations
    """

    def default(self, obj: Any) -> Any:
        """Convert Decimal to string, otherwise use default encoding.

        Args:
            obj: Object to encode

        Returns:
            String representation for Decimal, default encoding for others
        """
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


def _convert_config_strings_to_decimal(config: dict[str, Any]) -> dict[str, Any]:
    """Convert string values to Decimal for known financial fields.

    When configs are stored as JSON in the database, Decimal values are
    serialized as strings. This helper converts them back to Decimal objects
    for fields that should use Decimal precision (Pattern 1).

    Educational Note:
        We only convert specific known fields (max_edge, kelly_fraction, etc.)
        rather than converting all numeric-looking strings, because some
        fields like 'min_lead' should remain as integers.

    Args:
        config: Strategy config dict (may have string Decimal values)

    Returns:
        Config dict with Decimal values restored

    Example:
        >>> config = {"max_edge": "0.05", "kelly_fraction": "0.10", "min_lead": 5}
        >>> _convert_config_strings_to_decimal(config)
        {"max_edge": Decimal("0.05"), "kelly_fraction": Decimal("0.10"), "min_lead": 5}

    Reference:
        - Pattern 1 (Decimal Precision): docs/guides/DEVELOPMENT_PATTERNS_V1.2.md
        - ADR-002: Decimal precision for all financial calculations
    """
    # Fields that should be Decimal (financial calculations)
    decimal_fields = {
        "max_edge",
        "min_edge",
        "kelly_fraction",
        "max_position_size",
        "max_exposure",
        "stop_loss_threshold",
        "profit_target",
        "trailing_stop_activation",
        "trailing_stop_distance",
    }

    result = config.copy()
    for field in decimal_fields:
        if field in result and isinstance(result[field], str):
            result[field] = Decimal(result[field])

    return result


# =============================================================================
# TYPE VALIDATION HELPERS
# =============================================================================


def validate_decimal(value: Any, param_name: str) -> Decimal:
    """
    Validate that value is a Decimal type (runtime type enforcement).

    Args:
        value: Value to validate
        param_name: Parameter name for error message

    Returns:
        The value if it's a Decimal

    Raises:
        TypeError: If value is not a Decimal

    Educational Note:
        Python type hints (e.g., `price: Decimal`) are annotations only.
        They provide IDE autocomplete and mypy static analysis, but do NOT
        enforce types at runtime.

        Without runtime validation:
        >>> create_market(yes_ask_price=0.5)  # Executes (float contamination!)

        With runtime validation:
        >>> create_market(yes_ask_price=0.5)  # TypeError: yes_ask_price must be Decimal

        Why this matters:
        - Prevents float contamination (0.5 != Decimal("0.5"))
        - Ensures sub-penny precision preserved (0.4975 stored exactly)
        - Catches type errors early (at function call, not database INSERT)

    Example:
        >>> price = validate_decimal(Decimal("0.5200"), "yes_ask_price")
        >>> # Returns Decimal("0.5200")

        >>> price = validate_decimal(0.5200, "yes_ask_price")
        >>> # TypeError: yes_ask_price must be Decimal, got float
        >>> #    Use Decimal("0.5200"), not 0.5200
    """
    if not isinstance(value, Decimal):
        raise TypeError(
            f"{param_name} must be Decimal, got {type(value).__name__}. "
            f"Use Decimal('{value}'), not {value} ({type(value).__name__}). "
            f"See Pattern 1 in CLAUDE.md for Decimal precision guidance."
        )
    return value


# =============================================================================
# SCD RACE-PREVENTION RETRY HELPER
# =============================================================================

# Module-level logger for the retry helper. Callers may pass a logger_override
# to route warnings/errors to a domain-specific logger.
_scd_retry_logger = logging.getLogger(__name__)


def retry_on_scd_unique_conflict[T](
    operation: Callable[[], T],
    constraint_name: str,
    *,
    business_key: dict[str, Any] | None = None,
    logger_override: logging.Logger | None = None,
) -> T:
    """
    Run an SCD close+insert operation with one retry on a targeted partial-
    unique-index conflict.

    SCD Type 2 close+insert sequences (close current row -> insert new current
    row) can race when two callers concurrently create the FIRST current row
    for a business key -- neither sees a row to lock with FOR UPDATE, so both
    proceed to INSERT and the second caller hits the partial unique index that
    enforces "at most one current row per key".

    Migration 0049 added one such index, ``idx_balance_unique_current``, on
    ``account_balance(platform_id) WHERE row_current_ind = TRUE``. Sibling SCD
    tables (``game_states``, ``game_odds``, ``positions``, ``market_snapshots``,
    etc.) carry equivalent partial-unique indexes from earlier migrations.

    This helper is the "suspenders" complementing the index "belt": when the
    targeted constraint fires, the caller's transaction is rolled back (by
    ``get_cursor``'s exception handler) and ``operation`` is invoked one more
    time, opening a fresh ``with get_cursor(commit=True)`` block. The fresh
    transaction's MVCC snapshot sees the sibling caller's now-committed row,
    so the second attempt's ``FOR UPDATE`` lock query finds the row and the
    normal close+insert path proceeds.

    Holden's seven conditions (issue #613) implemented here:
        1. Exception discrimination -- only retry on
           ``psycopg2.errors.UniqueViolation`` whose ``e.diag.constraint_name``
           matches ``constraint_name``. CHECK violations, FK violations, NOT
           NULL violations, and any unrelated UniqueViolation re-raise
           immediately without retry.
        2. New transaction for retry -- ``operation`` is a callable that
           opens its OWN ``with get_cursor(commit=True)`` block on each
           invocation. We never re-enter a failed block; each call starts a
           fresh transaction with a fresh MVCC snapshot.
        3. NOW() must be re-captured on retry -- because ``operation`` runs
           top-to-bottom on retry, its ``SELECT NOW() AS ts`` runs again
           inside the fresh transaction. Pattern 49's "single NOW() for
           temporal continuity" still holds within each individual attempt.
        4. Max one retry -- on second matching failure attempt 2's exception
           is re-raised with attempt 1's exception explicitly chained via
           ``__cause__`` (PEP 3134 chaining). Both tracebacks remain
           accessible for postmortem analysis.
        5. Structured logging -- WARNING between attempts, ERROR on retry
           exhaustion OR on any attempt-2 failure path. Attempt 1 failures on
           non-matching constraints or non-UniqueViolation exceptions
           propagate silently (no log), because the retry cycle never
           started. Attempt 2 failures ALWAYS emit an ERROR describing the
           asymmetric transition so operators can correlate the earlier
           retry WARNING with the final failure.
        6/7. Tested via ``tests/unit/database/test_crud_shared_retry.py`` and
           ``tests/race/test_account_balance_concurrent_first_insert.py``.

    Args:
        operation: A zero-arg callable that performs ONE attempt of the SCD
            close+insert sequence. It MUST open its own ``with
            get_cursor(commit=True)`` block (NOT receive a cursor from
            outside) so the retry attempt gets a fresh transaction. The
            callable's return value is forwarded back to the helper's caller.
        constraint_name: Exact name of the partial unique index to discriminate
            on (e.g., ``"idx_balance_unique_current"``). Any UniqueViolation
            with a different constraint_name re-raises without retry.
        business_key: Optional dict of business identifiers (e.g.,
            ``{"platform_id": "kalshi"}``) included in WARNING/ERROR logs to
            aid postmortems. Do NOT pass balance amounts, auth material, or
            other sensitive values -- keys only.
        logger_override: Optional logger to use instead of the module logger.
            Useful for routing retry events into a caller-specific logger.

    Returns:
        Whatever ``operation`` returned on its successful (first or second)
        attempt.

    Raises:
        ValueError: If ``constraint_name`` is not a non-empty string. This
            guard prevents a ``None`` constraint_name from spuriously matching
            a libpq edge case where ``diag.constraint_name`` is ``None``, which
            would otherwise trigger an unwanted retry.
        psycopg2.errors.UniqueViolation: If the targeted constraint conflict
            persists after one retry attempt. The re-raised exception is
            attempt 2's exception; attempt 1's exception is explicitly chained
            via ``__cause__`` (PEP 3134), so both tracebacks remain accessible
            (e.g. ``exc.__cause__`` points to attempt 1). May also be raised
            if attempt 2 fails with a DIFFERENT UniqueViolation constraint;
            in that case attempt 1 is still chained via ``__cause__`` and an
            ERROR log explains the transition.
        Exception: Any other exception from inside ``operation`` is re-raised
            immediately without retry on attempt 1. If such an exception
            surfaces on attempt 2 (after attempt 1 triggered the matching
            retry), it is re-raised with attempt 1's matching UniqueViolation
            explicitly chained via ``__cause__`` and an ERROR log explaining
            the asymmetric failure.

    Usage:
        Define the SCD close+insert sequence as a local closure that opens
        its own ``get_cursor(commit=True)`` block, then pass it to this
        helper. The closure captures the parameters from the outer function;
        the helper handles the retry decision.

        >>> from precog.database.connection import get_cursor
        >>> from precog.database.crud_shared import retry_on_scd_unique_conflict
        >>>
        >>> def upsert_balance(platform_id: str, balance: Decimal) -> int:
        ...     def attempt() -> int:
        ...         with get_cursor(commit=True) as cur:
        ...             cur.execute("SELECT NOW() AS ts")
        ...             now = cur.fetchone()["ts"]
        ...             cur.execute(LOCK_QUERY, (platform_id,))
        ...             cur.execute(CLOSE_QUERY, (now, platform_id))
        ...             cur.execute(INSERT_QUERY, (platform_id, balance, now))
        ...             return cur.fetchone()["id"]
        ...
        ...     return retry_on_scd_unique_conflict(
        ...         attempt,
        ...         "idx_balance_unique_current",
        ...         business_key={"platform_id": platform_id},
        ...     )

    Design notes:
        Why a callable and not a context manager?
            A ``@contextmanager`` ``yield``s exactly once -- it cannot re-run
            the caller's body. The retry strictly requires running the
            ``with get_cursor(commit=True)`` block a second time in a fresh
            transaction, so the caller's body must be re-invokable. A
            zero-arg callable is the minimal shape that satisfies this
            constraint while keeping the helper generic across SCD CRUD
            sites. Two sequential ``with`` blocks must NOT live inside the
            same function body (that would couple the helper to the caller's
            local variables); instead the callable closes over them.

        Why max one retry?
            For a constraint-collision race, attempt 2 either succeeds
            (sibling committed, retry sees the row, normal FOR UPDATE path
            works) or the system is in a state further retries cannot fix.
            Exponential backoff is inappropriate -- this is mutual exclusion
            resolution, not rate limiting.

        Why constraint_name discrimination?
            ``account_balance`` alone has five distinct IntegrityError sources:
            unique index, CHECK on negative balance, FK to ``platforms``, NOT
            NULL on ``balance``, and any future constraint. A bare catch on
            ``IntegrityError`` would mask CHECK violations from buggy API
            responses, retry pathologically, and emit confusing "tried twice,
            both failed" logs for what are actually validation bugs.

    Related:
        - Issue #613: SCD first-insert race in crud_account
        - Migration 0049: account_balance partial unique index
        - Pattern 49 (DEVELOPMENT_PATTERNS_V1.30.md): SCD Race Prevention with
          FOR UPDATE -- this helper covers the gap Pattern 49 leaves when
          there is no current row to lock.
        - crud_teams.py:341: precedent for catching ``UniqueViolation`` in
          CRUD code (without constraint_name discrimination -- this helper
          tightens that pattern).
    """
    # Input validation (FIX 3 / Marvin Scenario 12): reject empty/None/non-str
    # constraint names up front. Without this, a libpq edge case where
    # diag.constraint_name is None would match `constraint_name=None` and
    # trigger a spurious retry on an unrelated failure.
    if not constraint_name or not isinstance(constraint_name, str):
        raise ValueError(
            f"constraint_name must be a non-empty string, got {constraint_name!r} "
            f"({type(constraint_name).__name__}). Pass the exact name of the "
            f"partial unique index to discriminate retries on."
        )

    log = logger_override if logger_override is not None else _scd_retry_logger
    safe_key = business_key if business_key is not None else {}

    # Capture attempt 1's exception in a local so we can explicitly chain it
    # via `raise ... from first_exc` inside attempt 2's handlers. Python's
    # automatic __context__ chain is severed because attempt 1's `except`
    # clause exits cleanly before attempt 2 runs, so we must thread the
    # reference through ourselves.
    first_exc: psycopg2.errors.UniqueViolation | None = None

    # Attempt 1: invoke the caller's operation. Its `with get_cursor(commit=True)`
    # block defines the entire first transaction.
    try:
        return operation()
    except psycopg2.errors.UniqueViolation as exc:
        # Discriminate on constraint_name. The `diag` attribute is populated
        # by libpq for any constraint violation; defensive `getattr` guards
        # against future psycopg2 API drift.
        diag = getattr(exc, "diag", None)
        observed_constraint = getattr(diag, "constraint_name", None) if diag else None

        if observed_constraint != constraint_name:
            # Different constraint -- not the race we're guarding against.
            # Re-raise immediately, do NOT retry, do NOT log a warning.
            raise

        log.warning(
            "SCD partial-unique-index conflict on %s (business_key=%s); "
            "retrying once in a new transaction. This indicates a concurrent "
            "first-insert race that the migration 0049-style partial index "
            "correctly blocked at the DB layer.",
            constraint_name,
            safe_key,
        )
        # Persist attempt 1's exception across the except-clause exit so
        # attempt 2's handlers can chain it via PEP 3134's `raise ... from`.
        first_exc = exc

    # Attempt 2: invoke the caller's operation again. The callable opens a
    # fresh `with get_cursor(commit=True)` block, giving us a new transaction
    # with a new MVCC snapshot that sees the sibling caller's committed row.
    try:
        return operation()
    except psycopg2.errors.UniqueViolation as exc2:
        diag2 = getattr(exc2, "diag", None)
        observed_constraint2 = getattr(diag2, "constraint_name", None) if diag2 else None

        if observed_constraint2 == constraint_name:
            # Retry exhaustion -- same targeted race fired twice.
            log.error(
                "SCD partial-unique-index conflict on %s persisted after one "
                "retry (business_key=%s). Re-raising with attempt 1 chained "
                "via __cause__.",
                constraint_name,
                safe_key,
            )
            raise exc2 from first_exc

        # Attempt 2 raised UniqueViolation on a DIFFERENT constraint. This
        # is NOT retry exhaustion; the retry transaction hit an unrelated
        # constraint. Operators must see the transition so they can
        # correlate the earlier WARNING with this ERROR.
        log.error(
            "SCD retry attempt 2 raised UniqueViolation on a DIFFERENT "
            "constraint %r (expected %r, business_key=%s). This is NOT "
            "retry exhaustion -- an unrelated constraint violation "
            "occurred during the retry transaction. Re-raising.",
            observed_constraint2,
            constraint_name,
            safe_key,
        )
        raise exc2 from first_exc
    except Exception as other_exc2:
        # Attempt 2 raised a non-UniqueViolation exception (OperationalError,
        # CheckViolation, arbitrary code bug, etc.). The original race was
        # the trigger but the retry path failed for unrelated reasons.
        # Surface the transition in logs before re-raising with chain.
        log.error(
            "SCD retry attempt 2 raised a non-UniqueViolation exception (%s) "
            "after attempt 1's matching UniqueViolation on %s "
            "(business_key=%s). The original race was the trigger but the "
            "retry path hit an unrelated failure. Re-raising.",
            type(other_exc2).__name__,
            constraint_name,
            safe_key,
        )
        raise other_exc2 from first_exc
