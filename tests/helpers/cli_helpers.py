"""
CLI Test Helpers.

Provides shared utilities for CLI testing across all test types.
Consolidates common patterns to eliminate duplication.

Usage:
    from tests.helpers.cli_helpers import (
        strip_ansi,
        assert_cli_success,
        assert_cli_output_contains,
        assert_cli_exit_code_in,
    )

Related:
    - Issue #258: Create shared CLI test fixtures
    - REQ-CLI-001: CLI Framework (Typer)
    - tests/conftest.py: Shared CLI fixtures (cli_runner, cli_app)

Educational Note:
    These helpers abstract common CLI testing patterns:
    - strip_ansi(): Rich/Typer output contains ANSI codes for colors
    - assert_cli_success(): Validates exit code 0
    - assert_cli_output_contains(): Pattern matching in output
    - assert_cli_exit_code_in(): For commands with multiple valid exit codes
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typer.testing import Result as CliResult


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text for reliable string matching.

    Rich and Typer add ANSI escape codes for colors and formatting.
    These codes can interfere with string matching in tests.

    Args:
        text: Text potentially containing ANSI escape codes

    Returns:
        Text with all ANSI escape codes removed

    Example:
        >>> output = "\\x1b[32mSuccess\\x1b[0m"  # Green "Success"
        >>> strip_ansi(output)
        'Success'

    Educational Note:
        ANSI escape codes follow the pattern: ESC[<params>m
        where ESC is \\x1b (hex 1B) and params are semicolon-separated numbers.
        Common codes: 32m=green, 31m=red, 1m=bold, 0m=reset
    """
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def assert_cli_success(result: CliResult, msg: str | None = None) -> None:
    """Assert that a CLI command succeeded (exit code 0).

    Args:
        result: The CliRunner.invoke() result
        msg: Optional custom error message

    Raises:
        AssertionError: If exit code is not 0

    Example:
        >>> result = runner.invoke(app, ["system", "version"])
        >>> assert_cli_success(result)

    Educational Note:
        Exit code 0 is the Unix convention for success.
        Non-zero exit codes indicate various failure modes:
        - 1: General error
        - 2: Command line usage error
        - 3+: Application-specific errors
    """
    if result.exit_code != 0:
        output = strip_ansi(result.stdout) if result.stdout else "(no output)"
        error_msg = msg or f"CLI command failed with exit code {result.exit_code}"
        raise AssertionError(f"{error_msg}\nOutput:\n{output}")


def assert_cli_output_contains(
    result: CliResult,
    *patterns: str,
    case_sensitive: bool = False,
) -> None:
    """Assert that CLI output contains all specified patterns.

    Args:
        result: The CliRunner.invoke() result
        *patterns: One or more strings that must appear in output
        case_sensitive: If False (default), comparison is case-insensitive

    Raises:
        AssertionError: If any pattern is not found in output

    Example:
        >>> result = runner.invoke(app, ["db", "--help"])
        >>> assert_cli_output_contains(result, "init", "status", "migrate")

    Educational Note:
        Case-insensitive matching (default) is more robust for CLI testing
        because command help text formatting may change (e.g., "Init" vs "init").
    """
    output = strip_ansi(result.stdout) if result.stdout else ""
    compare_output = output if case_sensitive else output.lower()

    missing = []
    for pattern in patterns:
        compare_pattern = pattern if case_sensitive else pattern.lower()
        if compare_pattern not in compare_output:
            missing.append(pattern)

    if missing:
        raise AssertionError(
            f"CLI output missing expected patterns: {missing}\nActual output:\n{output}"
        )


def assert_cli_exit_code_in(
    result: CliResult,
    valid_codes: list[int] | tuple[int, ...],
    msg: str | None = None,
) -> None:
    """Assert that CLI exit code is one of the valid codes.

    Some CLI commands may have multiple valid exit codes depending on
    environment or state. This assertion allows for flexible validation.

    Args:
        result: The CliRunner.invoke() result
        valid_codes: List/tuple of acceptable exit codes
        msg: Optional custom error message

    Raises:
        AssertionError: If exit code is not in valid_codes

    Example:
        >>> result = runner.invoke(app, ["db", "init"])
        >>> # Init may succeed (0) or partially succeed (1-5)
        >>> assert_cli_exit_code_in(result, [0, 1, 2, 3, 4, 5])

    Educational Note:
        Database commands often have nuanced exit codes:
        - 0: Full success
        - 1: Partial success (some migrations already applied)
        - 2: Connection issues but handled gracefully
        - 3+: Various application-specific states

        This helper supports the common pattern in our CLI tests where
        we accept a range of exit codes for commands that depend on
        external state (database, API availability, etc.).
    """
    if result.exit_code not in valid_codes:
        output = strip_ansi(result.stdout) if result.stdout else "(no output)"
        error_msg = msg or (f"CLI exit code {result.exit_code} not in valid codes {valid_codes}")
        raise AssertionError(f"{error_msg}\nOutput:\n{output}")


def get_cli_output_lower(result: CliResult) -> str:
    """Get CLI output as lowercase with ANSI codes stripped.

    Convenience function for common pattern of checking output content.

    Args:
        result: The CliRunner.invoke() result

    Returns:
        Lowercase output string with ANSI codes removed

    Example:
        >>> result = runner.invoke(app, ["system", "health"])
        >>> output = get_cli_output_lower(result)
        >>> assert "database" in output
    """
    return strip_ansi(result.stdout).lower() if result.stdout else ""
