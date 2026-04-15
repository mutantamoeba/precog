#!/usr/bin/env python
"""Verify that all CLI flags referenced in test files actually exist.

Walks tests/**/*.py AST looking for CliRunner.invoke(app, [...]) calls,
extracts flag strings (anything starting with '-'), and verifies each
flag exists in the current CLI --help output.

Pre-commit hook entry (see .pre-commit-config.yaml).
Session 50 identified 12+ tests using nonexistent flags (#764, #769).

Usage:
    python scripts/lint_cli_flag_references.py [--verbose]
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Subcommand groups in the CLI — each gets its own --help
_SUBCOMMANDS = [
    [],  # top-level
    ["kalshi"],
    ["kalshi", "balance"],
    ["kalshi", "markets"],
    ["kalshi", "positions"],
    ["kalshi", "fills"],
    ["kalshi", "settlements"],
    ["espn"],
    ["espn", "scores"],
    ["espn", "schedule"],
    ["espn", "games"],
    ["espn", "teams"],
    ["data"],
    ["data", "seed"],
    ["data", "verify"],
    ["db"],
    ["db", "init"],
    ["db", "upgrade"],
    ["db", "downgrade"],
    ["db", "status"],
    ["scheduler"],
    ["scheduler", "start"],
    ["scheduler", "stop"],
    ["scheduler", "status"],
    ["scheduler", "poll-once"],
    ["config"],
    ["config", "show"],
    ["config", "validate"],
    ["config", "env"],
    ["system"],
    ["system", "health"],
    ["system", "version"],
    ["system", "info"],
    ["circuit-breaker"],
    ["circuit-breaker", "list"],
    ["circuit-breaker", "trip"],
    ["circuit-breaker", "resolve"],
    ["backup"],
    ["backup", "create"],
    ["backup", "list"],
    ["backup", "restore"],
]

# Flags that are valid but don't appear in --help (e.g., pytest flags,
# or commands with allow_extra_args).  Add entries as needed.
_ALLOWLIST = {
    "--help",
    "-h",
    "--version",
    "-v",
}


def collect_known_flags() -> set[str]:
    """Use Typer CliRunner to get --help from every subcommand and extract flags."""
    import os

    os.environ.setdefault("PRECOG_ENV", "test")

    from typer.testing import CliRunner

    from precog.cli import app, register_commands

    register_commands()
    runner = CliRunner()
    known: set[str] = set(_ALLOWLIST)

    for subcmd in _SUBCOMMANDS:
        try:
            result = runner.invoke(app, subcmd + ["--help"])
            for line in result.output.split("\n"):
                for word in line.split():
                    # Strip Rich table borders and punctuation
                    cleaned = word.strip("│┃|,()[]{}?")
                    if cleaned.startswith("-") and not cleaned.startswith("---"):
                        flag = cleaned.rstrip(",;:.")
                        if flag:
                            known.add(flag)
        except Exception:
            continue
    return known


def _extract_invoke_flags(tree: ast.AST, filepath: Path) -> list[tuple[str, int]]:
    """Find runner.invoke(app, [...]) calls and extract flag strings."""
    flags: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Match: runner.invoke(app, [...]) or result = runner.invoke(...)
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "invoke" and len(node.args) >= 2:
            args_node = node.args[1]
            if isinstance(args_node, ast.List):
                for elt in args_node.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        val = elt.value
                        if val.startswith("-"):
                            flags.append((val, elt.lineno))
    return flags


def main() -> int:
    verbose = "--verbose" in sys.argv

    # Collect known flags from CLI help
    known = collect_known_flags()
    if verbose:
        print(f"Known flags: {len(known)}")
        for f in sorted(known):
            print(f"  {f}")

    # Scan test files
    unknown: list[tuple[Path, int, str]] = []
    test_dir = Path("tests")
    if not test_dir.exists():
        print("ERROR: tests/ directory not found")
        return 1

    for test_file in sorted(test_dir.rglob("*.py")):
        try:
            source = test_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(test_file))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for flag, lineno in _extract_invoke_flags(tree, test_file):
            if flag not in known:
                unknown.append((test_file, lineno, flag))

    if unknown:
        print(f"Found {len(unknown)} unknown CLI flag(s) in test files:\n")
        for filepath, lineno, flag in unknown:
            print(f"  {filepath}:{lineno}: unknown flag '{flag}'")
        print(f"\nKnown flags ({len(known)}) come from `precog --help` output.")
        print("If a flag is valid but not in --help, add it to _ALLOWLIST in this script.")
        return 1

    if verbose:
        print(f"All test CLI flags verified against {len(known)} known flags.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
