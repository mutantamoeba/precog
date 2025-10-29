"""
Utility functions and modules for Precog trading system.

Includes:
- Structured logging with JSON output
- Helper functions for common operations
"""

from .logger import (
    setup_logging,
    get_logger,
    LogContext,
    log_trade,
    log_position_update,
    log_edge_detected,
    log_error,
    logger,
)

__all__ = [
    'setup_logging',
    'get_logger',
    'LogContext',
    'log_trade',
    'log_position_update',
    'log_edge_detected',
    'log_error',
    'logger',
]
