"""
Structured logging for Precog trading system with dual output formats.

Output Formats:
--------------
**Console (stdout):** Human-readable text with structured fields
  [info     ] trade_entry user=john price=0.5200 ticker=NFL-KC-YES [main]

**File (logs/):** JSON for machine parsing and observability tools
  {"event": "trade_entry", "user": "john", "price": "0.5200", "ticker": "NFL-KC-YES", "timestamp": "..."}

Structured Logging Explained:
-----------------------------
Instead of plain text logs like:
  "User john executed trade at 0.52 for NFL-KC-YES"

We capture structured fields that enable querying, alerting, and analytics.

Why This Matters for Trading:
- **Searchability:** Query logs like a database ("find all trade_entry events where price > 0.50")
- **Alerting:** Trigger alerts on specific field values ("notify if unrealized_pnl < -100")
- **Analytics:** Aggregate metrics ("count trades per hour", "average execution price")
- **Debugging:** Correlation across distributed systems (request_id links logs)
- **Compliance:** Audit trail for regulatory requirements (immutable JSON logs)

Log Levels (from most to least critical):
-----------------------------------------
**CRITICAL** - System is unusable, manual intervention required
  - Examples: Database down, API authentication failed, trading halted
  - Action: Page on-call engineer immediately
  - Frequency: Should be RARE (< 1 per month)

**ERROR** - Feature failed but system continues
  - Examples: Trade execution failed, position update failed, market fetch error
  - Action: Investigate within hours, may require code fix
  - Frequency: Acceptable but should trend down (< 10 per day)

**WARNING** - Unexpected but handled situation
  - Examples: Rate limit hit (retrying), stale data (using cache), API degraded
  - Action: Monitor trends, may need capacity planning
  - Frequency: Common during normal operations (10-100 per hour)

**INFO** - Normal operations (business events)
  - Examples: Trade executed, position opened, edge detected, market fetched
  - Action: No action needed, business metrics
  - Frequency: Most common level (100-1000 per hour)

**DEBUG** - Detailed troubleshooting information
  - Examples: SQL queries, API request/response payloads, calculation steps
  - Action: Used during development or production debugging
  - Frequency: Disabled in production (too verbose)

Performance Implications:
------------------------
JSON serialization adds overhead compared to plain text:
- **Plain text:** ~10-20 microseconds per log line
- **JSON structured:** ~30-50 microseconds per log line
- **Overhead:** ~2-3x slower but WORTH IT for observability

When to avoid logging:
- Inside tight loops (< 1ms iteration time)
- High-frequency operations (> 1000 calls/sec)
- Hot path code (latency-critical trading decisions)

Example - Avoid logging in hot loops:
  ```python
  # ❌ BAD - Logs 1000 times in tight loop
  for market in markets:  # 1000 markets
      logger.debug("processing_market", ticker=market.ticker)
      process_market(market)

  # ✅ GOOD - Log once with batch info
  logger.info("processing_markets", count=len(markets))
  for market in markets:
      process_market(market)
  logger.info("markets_processed", count=len(markets))
  ```

Decimal Precision in Logs:
--------------------------
Custom decimal_serializer preserves financial precision in JSON:
- Decimal("0.5200") → "0.5200" (NOT 0.52 or 0.5199999)
- Critical for price reconstruction from logs
- Enables exact trade replication for backtesting

Daily Log Files:
---------------
Logs automatically rotate daily:
- Format: logs/precog_2025-11-06.log
- Retention: Not automated (implement in Phase 2+)
- Size: Typically 10-50 MB per day (INFO level)
- Compression: Recommend gzip for archival (90% reduction)

Context Binding (Request Tracking):
-----------------------------------
LogContext binds fields to ALL logs within a scope:
```python
# Without context:
logger.info("step1")  # {"event": "step1"}
logger.info("step2")  # {"event": "step2"}

# With context:
with LogContext(request_id="abc-123", strategy_id=1):
    logger.info("step1")  # {"event": "step1", "request_id": "abc-123", "strategy_id": 1}
    logger.info("step2")  # {"event": "step2", "request_id": "abc-123", "strategy_id": 1}
```

Use cases:
- HTTP request tracking (request_id)
- Trading session tracking (session_id)
- Strategy execution tracking (strategy_id, model_id)

Observability Stack (Future):
-----------------------------
This structured logging enables future integrations:
- **Elasticsearch:** Full-text search, aggregations, dashboards
- **Datadog/New Relic:** APM metrics, alerts, anomaly detection
- **Grafana Loki:** Log aggregation, correlation with metrics
- **CloudWatch Logs:** AWS-native log management

Credential Masking (REQ-SEC-009):
---------------------------------
This module automatically masks sensitive data in logs:
- API keys, passwords, tokens → masked as "abc***xyz"
- Connection strings → postgres://user:****@host:5432/db
- Error messages → credentials in exception text sanitized

Sensitive field names detected: api_key, api_secret, password, token,
jwt_token, access_token, refresh_token, secret, private_key, auth_token,
authorization, bearer_token, connection_string.

Reference: docs/guides/CONFIGURATION_GUIDE_V3.1.md (Logging section)
Related Requirements: REQ-OBSERV-001 (Structured Logging), REQ-SEC-009 (Credential Masking)
Related ADR: ADR-048 (Logging Strategy)
"""

import logging
import re
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import structlog

# =============================================================================
# CREDENTIAL MASKING (REQ-SEC-009)
# =============================================================================

# Sensitive field names that MUST be masked
SENSITIVE_FIELD_NAMES = frozenset(
    {
        "api_key",
        "api_secret",
        "password",
        "token",
        "jwt_token",
        "access_token",
        "refresh_token",
        "secret",
        "private_key",
        "auth_token",
        "authorization",
        "bearer_token",
        "connection_string",
    }
)

# Patterns that indicate sensitive content (case-insensitive)
SENSITIVE_PATTERNS = [
    # Connection strings with embedded passwords
    re.compile(r"(postgres://[^:]+:)([^@]+)(@.+)", re.IGNORECASE),
    re.compile(r"(mysql://[^:]+:)([^@]+)(@.+)", re.IGNORECASE),
    re.compile(r"(mongodb://[^:]+:)([^@]+)(@.+)", re.IGNORECASE),
    # Credentials in error messages - detects various assignment formats
    re.compile(r"(password\s*[=:]\s*['\"]?)([^'\"]+)(['\"]?)", re.IGNORECASE),
    re.compile(r"(password\s+['\"])([^'\"]+)(['\"])", re.IGNORECASE),
]


def mask_credential(value: str | None, show_chars: int = 3) -> str:
    """
    Mask a credential showing only first and last N characters.

    Args:
        value: The credential value to mask
        show_chars: Number of characters to show at start and end (default: 3)

    Returns:
        Masked string in format "abc***xyz"

    Example:
        >>> mask_credential("abc123-secret-456def")
        "abc***def"
        >>> mask_credential("short")
        "***"
    """
    if value is None:
        return "None"
    value_str = str(value)
    if len(value_str) <= show_chars * 2:
        return "***"
    return f"{value_str[:show_chars]}***{value_str[-show_chars:]}"


def sanitize_connection_string(conn_str: str) -> str:
    """
    Sanitize database connection strings by masking the password.

    Args:
        conn_str: Connection string like postgres://user:password@host:port/db

    Returns:
        Sanitized string with password replaced by ****

    Example:
        >>> sanitize_connection_string("postgres://user:MySecret@localhost:5432/db")
        "postgres://user:****@localhost:5432/db"
    """
    for pattern in SENSITIVE_PATTERNS[:3]:  # Connection string patterns
        match = pattern.match(conn_str)
        if match:
            return f"{match.group(1)}****{match.group(3)}"
    return conn_str


def sanitize_error_message(message: str) -> str:
    """
    Sanitize error messages by masking any embedded credentials.

    Args:
        message: Error message that may contain credentials

    Returns:
        Sanitized message with credentials replaced by ****

    Example:
        >>> sanitize_error_message("Auth failed: password 'MySecret123' is invalid")
        "Auth failed: password '****' is invalid"
    """
    result = message

    # Apply all sensitive patterns to sanitize credentials
    for pattern in SENSITIVE_PATTERNS:
        result = pattern.sub(r"\g<1>****\g<3>", result)

    return result


def mask_sensitive_data(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """
    Structlog processor that masks sensitive data in log events.

    This processor runs BEFORE log output and automatically:
    - Masks values for sensitive field names (api_key, password, etc.)
    - Sanitizes connection strings
    - Cleans error messages of embedded credentials

    Args:
        logger: The logger instance (unused, required by structlog)
        method_name: The log method name (info, error, etc.)
        event_dict: The log event dictionary

    Returns:
        Modified event dictionary with sensitive data masked

    Reference:
        REQ-SEC-009: Sensitive Data Masking in Logs
        Pattern 4: Security - NO CREDENTIALS IN CODE
    """
    for key, value in list(event_dict.items()):
        if value is None:
            continue

        # Check if field name is sensitive
        key_lower = key.lower()

        # Special handling for connection strings - sanitize password portion
        if key_lower == "connection_string" or (
            isinstance(value, str) and "://" in value and "@" in value
        ):
            event_dict[key] = sanitize_connection_string(str(value))
            continue

        # Mask other sensitive field names completely
        if key_lower in SENSITIVE_FIELD_NAMES or any(
            sensitive in key_lower for sensitive in ["key", "secret", "password", "token"]
        ):
            event_dict[key] = mask_credential(str(value))
            continue

        # Check for exception messages that may contain credentials
        if key_lower in (
            "exception_message",
            "error_message",
            "message",
            "exception",
        ) and isinstance(value, str):
            event_dict[key] = sanitize_error_message(value)

    return event_dict


def decimal_serializer(obj: Any, **kwargs) -> Any:
    """
    Custom serializer for Decimal and other non-JSON types.

    Args:
        obj: Object to serialize
        **kwargs: Additional keyword arguments (ignored, for compatibility)

    Returns:
        JSON-serializable representation

    Example:
        >>> decimal_serializer(Decimal("0.5200"))
        "0.5200"
    """
    if isinstance(obj, Decimal):
        # Convert Decimal to string to preserve precision
        return str(obj)
    if isinstance(obj, datetime):
        # Convert datetime to ISO format
        return obj.isoformat()
    if isinstance(obj, dict | list | str | int | float | bool | type(None)):
        # Already JSON-serializable
        return obj
    # Unknown type - convert to string as fallback
    return str(obj)


def setup_logging(
    log_level: str = "INFO", log_to_file: bool = True, log_dir: str = "logs"
) -> structlog.BoundLogger:
    """
    Configure structured logging for the application.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to write logs to daily files
        log_dir: Directory for log files (default: 'logs')

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logging(log_level="DEBUG")
        >>> logger.info("trade_executed", ticker="NFL-KC-YES", price=Decimal("0.5200"))
    """
    # Create logs directory if needed
    if log_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)

        # Daily log file name: precog_2025-10-23.log
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_path / f"precog_{today}.log"
    else:
        log_file = None

    # Configure standard library logging (required for structlog)
    # Explicitly close existing FileHandler objects to prevent ResourceWarnings
    # when setup_logging() is called multiple times (e.g., in tests)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:  # [:] creates a copy to safely modify during iteration
        if isinstance(handler, logging.FileHandler):
            handler.close()
            root_logger.removeHandler(handler)

    # force=True: Clear remaining handlers before adding new ones
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(message)s",
        handlers=[
            # Console handler (always enabled)
            logging.StreamHandler(sys.stdout),
            # File handler (if enabled)
            *([logging.FileHandler(log_file, mode="a", encoding="utf-8")] if log_file else []),
        ],
        force=True,  # Clear old handlers before adding new ones
    )

    # Configure structlog processors
    shared_processors = [
        # Add log level
        structlog.stdlib.add_log_level,
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Add timestamp in ISO format
        structlog.processors.TimeStamper(fmt="iso"),
        # CRITICAL: Mask sensitive data BEFORE logging (REQ-SEC-009)
        mask_sensitive_data,
        # Add stack info for exceptions
        structlog.processors.StackInfoRenderer(),
        # Format exception info
        structlog.processors.format_exc_info,
    ]

    # Configure structlog
    structlog.configure(
        processors=shared_processors  # type: ignore[arg-type]
        + [
            # Use ProcessorFormatter for final rendering
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure formatters for different outputs
    # Console formatter (human-readable with color)
    console_formatter = structlog.stdlib.ProcessorFormatter(
        # Foreign log messages (from stdlib logging)
        foreign_pre_chain=shared_processors,  # type: ignore[arg-type]
        # Structlog messages
        processors=[
            # Remove internal _record and _from_structlog keys
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            # Render as human-readable console output (returns string)
            structlog.dev.ConsoleRenderer(colors=False),
        ],
    )

    # File formatter (JSON for machine parsing)
    file_formatter = structlog.stdlib.ProcessorFormatter(
        # Foreign log messages (from stdlib logging)
        foreign_pre_chain=shared_processors,  # type: ignore[arg-type]
        # Structlog messages
        processors=[
            # Remove internal _record and _from_structlog keys
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            # Render as JSON (use default= instead of serializer=, returns string)
            structlog.processors.JSONRenderer(default=decimal_serializer),
        ],
    )

    # Apply appropriate formatter to each handler
    for handler in logging.root.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            # Console handler gets human-readable format
            handler.setFormatter(console_formatter)
        else:
            # File handler gets JSON format
            handler.setFormatter(file_formatter)

    # Get logger instance
    logger = structlog.get_logger()

    # Log startup message
    logger.info(
        "logging_initialized",
        log_level=log_level,
        log_file=str(log_file) if log_file else None,
    )

    return logger  # type: ignore[no-any-return]


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Get a logger instance with optional name binding.

    Args:
        name: Logger name (typically module name)

    Returns:
        Logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("module_started")
    """
    return structlog.get_logger(name)  # type: ignore[no-any-return]


# Context manager for request tracking
class LogContext:
    """
    Context manager for binding persistent context to logs.

    Example:
        >>> logger = get_logger()
        >>> with LogContext(request_id="abc-123", user_id=42):
        ...     logger.info("processing_request")
        ...     # All logs within this context will include request_id and user_id
    """

    def __init__(self, **context):
        """
        Initialize log context.

        Args:
            **context: Key-value pairs to bind to all logs
        """
        self.context = context
        self.logger = None

    def __enter__(self):
        """Bind context when entering."""
        self.logger = structlog.get_logger().bind(**self.context)
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clear context when exiting."""
        if self.logger:
            self.logger.unbind(*self.context.keys())
        return False


# Initialize default logger on module import
try:
    logger = setup_logging()
except Exception as e:
    # Fallback to basic logging if setup fails (e.g., during testing)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = structlog.get_logger()
    # Don't log the warning if we're in test environment (pytest sets PYTEST_CURRENT_TEST)
    import os

    if "PYTEST_CURRENT_TEST" not in os.environ:
        # Use logging.warning instead of print (since basicConfig already set up)
        logging.warning(f"Logging setup failed: {e}")


# Helper functions for common log patterns
def log_trade(
    action: str,
    ticker: str,
    side: str,
    quantity: int,
    price: Decimal,
    strategy_id: int,
    model_id: int,
    **extra,
):
    """
    Log a trade event with standardized format.

    Args:
        action: 'entry' or 'exit'
        ticker: Market ticker
        side: 'YES' or 'NO'
        quantity: Number of contracts
        price: Execution price
        strategy_id: Strategy version ID
        model_id: Model version ID
        **extra: Additional context

    Example:
        >>> log_trade(
        ...     action='entry',
        ...     ticker='NFL-KC-YES',
        ...     side='YES',
        ...     quantity=100,
        ...     price=Decimal("0.5200"),
        ...     strategy_id=1,
        ...     model_id=2
        ... )
    """
    logger.info(
        f"trade_{action}",
        ticker=ticker,
        side=side,
        quantity=quantity,
        price=price,
        strategy_id=strategy_id,
        model_id=model_id,
        **extra,
    )


def log_position_update(
    position_id: int,
    ticker: str,
    current_price: Decimal,
    unrealized_pnl: Decimal,
    status: str,
    **extra,
):
    """
    Log a position monitoring update.

    Args:
        position_id: Position ID
        ticker: Market ticker
        current_price: Current market price
        unrealized_pnl: Unrealized P&L
        status: Position status
        **extra: Additional context

    Example:
        >>> log_position_update(
        ...     position_id=42,
        ...     ticker='NFL-KC-YES',
        ...     current_price=Decimal("0.5800"),
        ...     unrealized_pnl=Decimal("6.00"),
        ...     status='open'
        ... )
    """
    logger.info(
        "position_update",
        position_id=position_id,
        ticker=ticker,
        current_price=current_price,
        unrealized_pnl=unrealized_pnl,
        status=status,
        **extra,
    )


def log_edge_detected(
    ticker: str,
    expected_value: Decimal,
    market_price: Decimal,
    model_probability: Decimal,
    strategy_name: str,
    **extra,
):
    """
    Log an EV+ edge detection.

    Args:
        ticker: Market ticker
        expected_value: Expected value (EV)
        market_price: Current market price
        model_probability: Model's probability estimate
        strategy_name: Strategy that detected edge
        **extra: Additional context

    Example:
        >>> log_edge_detected(
        ...     ticker='NFL-KC-YES',
        ...     expected_value=Decimal("0.0500"),
        ...     market_price=Decimal("0.5200"),
        ...     model_probability=Decimal("0.5700"),
        ...     strategy_name='halftime_entry'
        ... )
    """
    logger.info(
        "edge_detected",
        ticker=ticker,
        expected_value=expected_value,
        market_price=market_price,
        model_probability=model_probability,
        strategy_name=strategy_name,
        **extra,
    )


def log_error(error_type: str, message: str, exception: Exception | None = None, **extra):
    """
    Log an error with standardized format.

    Args:
        error_type: Category of error (e.g., 'api_error', 'database_error')
        message: Error description
        exception: Exception object (if available)
        **extra: Additional context

    Example:
        >>> try:
        ...     risky_operation()
        ... except Exception as e:
        ...     log_error('api_error', 'Failed to fetch market data', exception=e)
    """
    logger.error(
        error_type,
        message=message,
        exception_type=type(exception).__name__ if exception else None,
        exception_message=str(exception) if exception else None,
        **extra,
    )
