#!/usr/bin/env python
"""Verify that mock.patch string targets resolve to real attributes.

Walks tests/**/*.py AST looking for mock.patch / patch / @patch calls with
a string literal target, attempts to import the dotted path, and reports
targets that do not resolve to a real attribute.

Background: mock.patch('some.dotted.path') silently creates the target
attribute if it doesn't exist, so stale paths produce mocks that mock
nothing. This is the #764 decay-family this hook prevents. The S75 linter
(lint_cli_flag_references.py) caught CLI flag decay — this catches mock
target decay. See Phase A' exit criterion #1, hook 1.6.

Usage:
    python scripts/lint_mock_target_paths.py [--verbose]
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

_ALLOWLIST_FILE = Path("scripts/mock_path_allowlist.txt")


def load_allowlist() -> set[str]:
    """Read allowlist file; lines starting with # and blanks are ignored."""
    if not _ALLOWLIST_FILE.exists():
        return set()
    entries: set[str] = set()
    with _ALLOWLIST_FILE.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            entries.add(line)
    return entries


def _is_patch_call(node: ast.Call) -> bool:
    """True if the call is `patch(...)`, `mock.patch(...)`, or `<...>.patch(...)`."""
    func = node.func
    if isinstance(func, ast.Name) and func.id == "patch":
        return True
    # mock.patch(...) or unittest.mock.patch(...)
    return isinstance(func, ast.Attribute) and func.attr == "patch"


def _extract_patch_targets(tree: ast.AST) -> list[tuple[str, int]]:
    """Find string literal targets passed to patch()/@patch()/mock.patch().

    Handles:
      - patch("a.b.c")                 -> ("a.b.c", lineno)
      - @patch("a.b.c")                -> ("a.b.c", lineno)
      - mock.patch("a.b.c")            -> ("a.b.c", lineno)

    Skips (silently):
      - patch(some_var)                — dynamic target, can't resolve
      - patch.object(Cls, "method")    — first arg is a Name, not a string
      - patch.multiple(...)            — different shape, skipped
    """
    targets: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_patch_call(node):
            continue
        # Reject patch.object / patch.multiple / patch.dict subforms
        func = node.func
        # patch.object etc. look like Attribute(Attribute(..., "patch"), "object")
        # but ast.walk reaches the outer Call separately; our _is_patch_call only
        # matches when the terminal attr is "patch". Subforms like patch.object()
        # have terminal attr "object"/"multiple"/"dict" and are skipped here.
        _ = func  # silence linter; matched above
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            targets.append((first.value, first.lineno))
    return targets


def resolve_dotted_path(dotted: str) -> bool:
    """True if `dotted` resolves to a real attribute in the current source tree.

    Strategy: split on '.', try importing progressively longer module prefixes,
    then walk remaining components as attributes via getattr.
    """
    parts = dotted.split(".")
    # Try longest-to-shortest module prefix so `a.b.c.d` tries importing a.b.c.d,
    # then a.b.c (with d as attr), then a.b (with c.d as attrs), etc.
    for split in range(len(parts), 0, -1):
        mod_name = ".".join(parts[:split])
        attr_chain = parts[split:]
        try:
            mod = importlib.import_module(mod_name)
        except (ImportError, ValueError, TypeError):
            # ValueError: relative-name edge cases; TypeError: weird inputs
            continue
        obj: object = mod
        ok = True
        for attr in attr_chain:
            if not hasattr(obj, attr):
                ok = False
                break
            obj = getattr(obj, attr)
        if ok:
            return True
    return False


def main() -> int:
    verbose = "--verbose" in sys.argv
    allowlist = load_allowlist()

    test_dir = Path("tests")
    if not test_dir.exists():
        print("ERROR: tests/ directory not found")
        return 1

    # Ensure source imports work
    import os

    os.environ.setdefault("PRECOG_ENV", "test")

    unresolved: list[tuple[Path, int, str]] = []
    seen_targets = 0
    for test_file in sorted(test_dir.rglob("*.py")):
        try:
            source = test_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(test_file))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for target, lineno in _extract_patch_targets(tree):
            seen_targets += 1
            if target in allowlist:
                continue
            if not resolve_dotted_path(target):
                unresolved.append((test_file, lineno, target))

    if verbose:
        print(f"Scanned {seen_targets} mock.patch string targets")
        print(f"Allowlist: {len(allowlist)} entries")

    if unresolved:
        print(f"Found {len(unresolved)} unresolved mock.patch target(s):\n")
        for filepath, lineno, target in unresolved:
            print(f"  {filepath}:{lineno}: {target}")
        print("\nIf a path is intentionally external or dynamic, add it to")
        print(f"{_ALLOWLIST_FILE} (one dotted path per line).")
        return 1

    if verbose:
        print("All mock.patch targets resolved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
