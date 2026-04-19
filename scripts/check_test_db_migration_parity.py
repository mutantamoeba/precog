#!/usr/bin/env python
"""Pre-push hook: verify test DB is at alembic head.

S61 root-caused a class of silent-CI failures where the local test DB was
several migrations behind the head (0056 vs 0063), silently masking three
real test bugs for multiple sessions. This is a sibling of umbrella #764:
test-infrastructure state drifting from production reality lets bugs pile
up unseen. Mechanical enforcement at pre-push is the fix class.

Behavior:
- Forces PRECOG_ENV=test so the precog DB helpers connect to the test DB.
- Reads current alembic_version and compares to the alembic head.
- Exits 0 if in parity, or if the test DB is unreachable / unconfigured
  (graceful SKIP so developers without a test DB are not blocked).
- Exits 1 with an actionable error message if behind.

Mirrors the UserPromptSubmit dev-DB hook (scripts/check_migration_parity_hook.py)
but (a) targets the test DB and (b) blocks instead of warning.

Issue: #867
Related: #792 (dev-DB UserPromptSubmit hook precedent)
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    """Run the parity check. Returns exit code (0 OK/skip, 1 block)."""
    # Force test DB — this hook only ever checks the test DB. The dev DB is
    # covered by the UserPromptSubmit warning hook from #792.
    os.environ["PRECOG_ENV"] = "test"

    try:
        from precog.database.migration_check import check_migration_parity
    except Exception as e:
        # Import failure = developer environment not set up. Skip (do not block).
        print(f"SKIP: could not import migration_check ({e}); test DB parity not verified")
        return 0

    try:
        status = check_migration_parity()
    except Exception as e:
        # Any unexpected exception escaping the helper — skip rather than block.
        print(f"SKIP: test DB parity check raised unexpectedly ({e})")
        return 0

    if status.error:
        # Typical cause: test DB unreachable, credentials unset, alembic dir
        # missing. Warn-and-skip so contributors without a test DB can push.
        print(f"SKIP: test DB parity check not conclusive ({status.error})")
        return 0

    if status.is_current:
        print(f"OK: test DB at migration {status.db_version} (matches head)")
        return 0

    # Behind — block the push with an actionable message.
    db_ver = status.db_version or "<empty>"
    head_ver = status.head_version or "<unknown>"
    behind = status.versions_behind
    gap = f" ({behind} behind)" if behind else ""

    print("")
    print("ERROR: Test DB is behind alembic head.")
    print(f"  Test DB version: {db_ver}")
    print(f"  Alembic head:    {head_ver}{gap}")
    print("")
    print("A stale test DB can silently mask real test failures (S61 root cause).")
    print("Upgrade the test DB before pushing:")
    print("")
    print("  PRECOG_ENV=test python -m alembic -c src/precog/database/alembic.ini upgrade head")
    print("")
    print("Reference: #867 (test DB migration parity hook), #792 (dev DB sibling)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
