#!/usr/bin/env python
"""ADR-drift linter (G7, Option B criterion 7).

Warns when staged changes touch file paths referenced by the ADR
document without the ADR document itself being staged alongside. The
goal is to keep architecture decisions synchronized with the code they
describe. This hook is intentionally a WARNING, not a blocker -- ADRs
should not be required on every code change, only considered.

The check is lightweight: it parses backtick-quoted paths from the ADR
file (e.g. ``src/precog/database/crud_positions.py``) and matches them
against the list of staged files. Files matching an ADR-referenced
path trigger a reminder; the ADR file being staged suppresses the
warning entirely (author is already updating ADRs).

Exit codes:
    0 -- always (hook never blocks; warnings are informational).
    2 -- internal tool error (git unavailable, unexpected git output).

Scope boundary:
    * Does not parse ADR section structure -- treats the monolithic
      ADR file as a single unit. When any referenced path is touched
      and the ADR file is unstaged, we warn without claiming to know
      which specific ADR applies.
    * Does not semantic-match code concepts to ADRs -- only file paths.
      ADRs describing a concept without naming files will not trigger.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ADR_FILE = "docs/foundation/ARCHITECTURE_DECISIONS_V2.39.md"
EXCLUDE_DIR_RE = re.compile(r"(^|/)_archive(/|$)")

# Backtick-quoted paths containing a slash, optionally with a recognized
# file extension. Covers source, config, docs, and shell scripts.
PATH_PATTERN = re.compile(
    r"`([A-Za-z0-9_\-./]+/[A-Za-z0-9_\-.]+"
    r"(?:\.(?:py|yml|yaml|json|md|sh|sql|toml|cfg|ini|txt))?)`"
)


def get_staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"ERROR: git diff failed: {result.stderr}", file=sys.stderr)
        sys.exit(2)
    return [f for f in result.stdout.splitlines() if f]


def extract_adr_path_references(adr_path: Path) -> set[str]:
    """Parse backtick-quoted paths from the ADR file."""
    if not adr_path.exists():
        return set()
    text = adr_path.read_text(encoding="utf-8")
    paths: set[str] = set()
    for match in PATH_PATTERN.finditer(text):
        candidate = match.group(1)
        if "/" not in candidate:
            continue
        if EXCLUDE_DIR_RE.search(candidate):
            continue
        paths.add(candidate)
    return paths


def find_matches(staged: list[str], adr_paths: set[str]) -> list[tuple[str, str]]:
    """Return [(staged_file, matched_adr_reference), ...]."""
    hits: list[tuple[str, str]] = []
    for staged_file in staged:
        for adr_ref in adr_paths:
            if staged_file == adr_ref:
                hits.append((staged_file, adr_ref))
                break
            if adr_ref.endswith("/") and staged_file.startswith(adr_ref):
                hits.append((staged_file, adr_ref))
                break
    return hits


def main() -> int:
    staged = get_staged_files()
    if not staged:
        return 0
    if ADR_FILE in staged:
        return 0

    adr_paths = extract_adr_path_references(Path(ADR_FILE))
    if not adr_paths:
        return 0

    matches = find_matches(staged, adr_paths)
    if not matches:
        return 0

    print("WARNING: Staged changes touch paths referenced by the ADR document.")
    print(f"  ADR file: {ADR_FILE}")
    print("  The ADR file is NOT staged. Consider whether an ADR needs an update.")
    print()
    print("  Files matching ADR-referenced paths:")
    for staged_file, adr_ref in matches:
        print(f"    - {staged_file} (ADR ref: `{adr_ref}`)")
    print()
    print("  This is a REMINDER, not a block. Commit proceeds.")
    print("  If an ADR update is warranted, stage it and re-commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
