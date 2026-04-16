#!/usr/bin/env python
"""Verify that all CLI flags referenced in test files actually exist.

Walks tests/**/*.py AST looking for CliRunner.invoke(app, [...]) calls,
extracts flag strings (anything starting with '-'), and verifies each
flag exists in the --help output of the SPECIFIC subcommand being invoked.

Pre-commit hook entry (see .pre-commit-config.yaml).

Session 50 identified 12+ tests using nonexistent flags (#764, #769).
Session 55 (#799, Ghanima audit) identified two fidelity bugs in the
earlier single-global-set implementation:

  1. Shared flag names (--force, --dry-run, --verbose) passed on ANY
     subcommand because they existed on at least one — `db init --force`
     and `db migrate --dry-run` both escaped detection.
  2. Missing _SUBCOMMANDS entries for actively-registered subcommands
     (`db migrate`, `db tables`, `trade *`).

Both fixed here: per-subcommand known sets + full subcommand enumeration.

Usage:
    python scripts/lint_cli_flag_references.py [--verbose]
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Subcommand groups in the CLI — each gets its own --help call.
# Top-level flags inherit down to subcommands via Typer, so the linter
# treats subcommand flag sets as: own flags plus all ancestor flags.
_SUBCOMMANDS: list[list[str]] = [
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
    ["db", "status"],
    ["db", "migrate"],
    ["db", "tables"],
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
    ["trade"],
    ["trade", "execute"],
    ["trade", "cancel"],
    ["trade", "history"],
    ["trade", "edges"],
]

# Flags that are valid but don't appear in --help (e.g., pytest flags,
# or commands with allow_extra_args). Add entries as needed.
_UNIVERSAL_ALLOWLIST = {
    "--help",
    "-h",
    "--version",
}


def _extract_flags_from_help(output: str) -> set[str]:
    """Parse --help output for flag strings."""
    flags: set[str] = set()
    for line in output.split("\n"):
        for word in line.split():
            # Strip Rich table borders and punctuation
            cleaned = word.strip("│┃|,()[]{}?")
            if cleaned.startswith("-") and not cleaned.startswith("---"):
                flag = cleaned.rstrip(",;:.")
                if flag:
                    flags.add(flag)
    return flags


def collect_known_flags() -> dict[tuple[str, ...], set[str]]:
    """Collect known flags per subcommand path.

    Returns a dict keyed by subcommand path tuple. Each value includes the
    subcommand's own flags PLUS all ancestor flags (Typer inheritance).
    """
    import os

    os.environ.setdefault("PRECOG_ENV", "test")

    from typer.testing import CliRunner

    from precog.cli import app, register_commands

    register_commands()
    runner = CliRunner()

    # First pass: collect own flags per subcommand (without inheritance)
    own_flags: dict[tuple[str, ...], set[str]] = {}
    for subcmd in _SUBCOMMANDS:
        try:
            result = runner.invoke(app, subcmd + ["--help"])
            own_flags[tuple(subcmd)] = _extract_flags_from_help(result.output)
        except Exception:
            # Any subcommand-help failure (missing subcmd, registration error,
            # etc.) should skip this entry rather than crash the whole linter.
            own_flags[tuple(subcmd)] = set()

    # Second pass: propagate ancestor flags down.
    # E.g., `db init` inherits from `db` which inherits from top-level.
    resolved: dict[tuple[str, ...], set[str]] = {}
    for subcmd_tuple, flags in own_flags.items():
        merged = set(_UNIVERSAL_ALLOWLIST) | flags
        # Merge in all strict ancestors
        for i in range(len(subcmd_tuple)):
            ancestor = subcmd_tuple[:i]
            merged |= own_flags.get(ancestor, set())
        resolved[subcmd_tuple] = merged
    return resolved


def _extract_invoke_flags(
    tree: ast.AST,
) -> list[tuple[tuple[str, ...] | None, str, int]]:
    """Find runner.invoke(app, [...]) calls; return (subcmd_path_or_None, flag, lineno).

    Walks the args list of each invoke call:
      - Leading string constants (no leading '-') form the subcommand path.
      - First string starting with '-' terminates the path and is recorded as a flag.
      - Subsequent flags share the same subcommand context.
      - Non-constant args (variables, f-strings) mid-path make the path
        undeterminable; we return None for those invocations so the linter
        falls back to a permissive union check.
    """
    results: list[tuple[tuple[str, ...] | None, str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "invoke" and len(node.args) >= 2):
            continue
        args_node = node.args[1]
        if not isinstance(args_node, ast.List):
            continue

        subcmd_path: list[str] = []
        flags_in_call: list[tuple[str, int]] = []
        path_dynamic = False
        seen_flag = False
        for elt in args_node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                val = elt.value
                if val.startswith("-"):
                    seen_flag = True
                    flags_in_call.append((val, elt.lineno))
                elif not seen_flag:
                    subcmd_path.append(val)
                # positional value after a flag (e.g. --component "database")
                # is treated as the flag's argument; skip.
            elif not seen_flag:
                # Dynamic arg in positional position — subcommand path is
                # unknown. Mark so we fall back to permissive check.
                path_dynamic = True

        final_path = None if path_dynamic else tuple(subcmd_path)
        for flag, lineno in flags_in_call:
            results.append((final_path, flag, lineno))
    return results


def main() -> int:
    verbose = "--verbose" in sys.argv

    known_by_subcmd = collect_known_flags()
    all_known_union: set[str] = set().union(*known_by_subcmd.values())

    if verbose:
        total_distinct = len(all_known_union)
        print(f"Subcommand paths indexed: {len(known_by_subcmd)}")
        print(f"Distinct flags across all subcommands: {total_distinct}")

    unknown: list[tuple[Path, int, str, str]] = []  # (file, line, flag, ctx_label)
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

        for subcmd_path, flag, lineno in _extract_invoke_flags(tree):
            if subcmd_path is None:
                # Dynamic path — permissive union check
                if flag not in all_known_union:
                    unknown.append((test_file, lineno, flag, "<dynamic>"))
            elif subcmd_path in known_by_subcmd:
                if flag not in known_by_subcmd[subcmd_path]:
                    ctx = " ".join(subcmd_path) if subcmd_path else "<top-level>"
                    unknown.append((test_file, lineno, flag, ctx))
            else:
                # Unknown subcommand path — probably a typo or unregistered subcmd.
                # Fall back to union check (permissive) but surface the oddity
                # in verbose mode. This is a linter-limitation note, not a test
                # bug, because _SUBCOMMANDS may not cover every invocation.
                if flag not in all_known_union:
                    ctx = " ".join(subcmd_path) if subcmd_path else "<top-level>"
                    unknown.append((test_file, lineno, flag, f"{ctx} (path unrecognized)"))

    if unknown:
        print(f"Found {len(unknown)} unknown CLI flag(s) in test files:\n")
        for filepath, lineno, flag, ctx in unknown:
            print(f"  {filepath.as_posix()}:{lineno}: '{flag}' not valid for [{ctx}]")
        print(
            "\nIf a flag is valid but missing from a subcommand's --help, either"
            "\nadd the subcommand path to _SUBCOMMANDS or add the flag to"
            "\n_UNIVERSAL_ALLOWLIST in this script."
        )
        return 1

    if verbose:
        print("All test CLI flags verified against their subcommand contexts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
