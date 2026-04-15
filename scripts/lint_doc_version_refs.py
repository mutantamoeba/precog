#!/usr/bin/env python
"""Doc version drift linter (G1).

Blocks a commit that renames a versioned documentation file (pattern:
``_V<major>.<minor>.md``) while leaving references to the old filename
elsewhere in the repo. The common failure this prevents: promoting
``DEVELOPMENT_PATTERNS_V1.31.md`` to ``_V1.32.md`` while other guides,
CLAUDE.md, or cross-references still hardcode the old version suffix.

Exit codes:
    0 -- no staged renames matching the versioned-doc pattern, or renames
        present and all old-filename references updated (or absent).
    1 -- staged rename(s) found with stale references still pointing at
        the old filename; lists them for the developer.
    2 -- internal tool error (git unavailable, unexpected git output).
"""

from __future__ import annotations

import re
import subprocess
import sys

VERSION_PATTERN = re.compile(r"_V\d+\.\d+\.md$")
EXCLUDE_DIR_RE = re.compile(r"(^|/)_archive(/|$)")


def get_staged_versioned_renames() -> list[tuple[str, str]]:
    """Return [(old_path, new_path), ...] for staged renames whose
    source and destination both match the versioned-doc pattern.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-status", "--diff-filter=R"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"ERROR: git diff failed: {result.stderr}", file=sys.stderr)
        sys.exit(2)

    renames: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or not parts[0].startswith("R"):
            continue
        _, old, new = parts
        if VERSION_PATTERN.search(old) and VERSION_PATTERN.search(new):
            renames.append((old, new))
    return renames


def find_stale_references(old_path: str) -> list[tuple[str, int, str]]:
    """Return [(file, line_number, line_content), ...] for refs to the old
    filename in tracked files, excluding the old file itself and _archive/.
    """
    result = subprocess.run(
        ["git", "grep", "-nF", "--", old_path],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        print(f"ERROR: git grep failed: {result.stderr}", file=sys.stderr)
        sys.exit(2)

    hits: list[tuple[str, int, str]] = []
    for line in result.stdout.splitlines():
        match = re.match(r"^([^:]+):(\d+):(.*)$", line)
        if not match:
            continue
        fname, lno, content = match.group(1), int(match.group(2)), match.group(3)
        if fname == old_path:
            continue
        if EXCLUDE_DIR_RE.search(fname):
            continue
        hits.append((fname, lno, content))
    return hits


def main() -> int:
    renames = get_staged_versioned_renames()
    if not renames:
        print("No versioned-doc renames staged -- skipping doc drift check")
        return 0

    any_stale = False
    for old, new in renames:
        print(f"Checking references to {old} (renamed to {new})...")
        stale = find_stale_references(old)
        if stale:
            any_stale = True
            print(f"ERROR: {len(stale)} stale reference(s) to {old}:")
            for fname, lno, content in stale:
                print(f"  {fname}:{lno}: {content.rstrip()[:120]}")

    if any_stale:
        print()
        print("Fix: update the stale references to the new filename,")
        print("     OR move the old file to _archive/ (its refs are ignored).")
        print("Reference: G1 doc-drift hook")
        return 1

    print("Doc drift check passed (no stale refs for renamed versioned docs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
