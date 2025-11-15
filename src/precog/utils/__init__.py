"""
Utility functions and modules for Precog trading system.

Includes:
- Structured logging with JSON output
- Helper functions for common operations
"""

from .logger import (
    LogContext,
    get_logger,
    log_edge_detected,
    log_error,
    log_position_update,
    log_trade,
    logger,
    setup_logging,
)

__all__ = [
    "LogContext",
    "get_logger",
    "log_edge_detected",
    "log_error",
    "log_position_update",
    "log_trade",
    "logger",
    "setup_logging",
]
