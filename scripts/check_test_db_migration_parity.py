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
- Exits 1 with a direction-aware actionable error message if out of sync.
  BEHIND (test DB < branch head): recover via `alembic upgrade head`.
  AHEAD (test DB > branch head): branch lacks the migration files needed
  to downgrade in place — recover via the branch-switch dance documented
  in memory file feedback_test_db_branch_drift.md.

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
        # Unexpected exception from the helper itself = bug in migration_check,
        # not a legitimate skip. Fail loudly (exit 2) — Glokta S62 review:
        # swallowing this reintroduces the silent-CI pattern #867 exists to
        # prevent. The developer sees the real error and fixes the helper.
        print(f"FATAL: check_migration_parity raised unexpectedly ({e})", file=sys.stderr)
        print(
            "       This is a bug in migration_check.py, not a skippable condition.",
            file=sys.stderr,
        )
        return 2

    if status.error:
        if status.fatal:
            # Multi-head alembic chain, etc. — block, do not skip.
            print(f"ERROR: {status.error}")
            return 1
        # Skippable: test DB unreachable, credentials unset, alembic dir missing.
        # Do not block contributors without a test DB.
        print(f"SKIP: test DB parity check not conclusive ({status.error})")
        return 0

    if status.is_current:
        print(f"OK: test DB at migration {status.db_version} (matches head)")
        return 0

    # Out of sync — block the push with a direction-aware actionable message.
    # versions_behind: positive = BEHIND, negative = AHEAD, None = unknown direction.
    db_ver = status.db_version or "<empty>"
    head_ver = status.head_version or "<unknown>"
    delta = status.versions_behind

    if delta is not None and delta < 0:
        # AHEAD: test DB carries migrations the branch doesn't ship. Branch lacks
        # the files needed to downgrade in place, so the recovery path differs from
        # BEHIND. See feedback_test_db_branch_drift.md.
        ahead = -delta
        print("")
        print(f"ERROR: Test DB AHEAD of branch head by {ahead}.")
        print(f"  Test DB version: {db_ver}")
        print(f"  Alembic head:    {head_ver}")
        print("")
        print("Branch lacks the migration files needed to downgrade in place.")
        print("Recovery: switch to a branch with higher head, run alembic downgrade")
        print(f"          to {head_ver}, switch back, push.")
        print("See memory file feedback_test_db_branch_drift.md for the full dance.")
        print("")
        print("Reference: #867 (test DB migration parity hook), #1101 (directional message)")
        return 1

    # BEHIND (or unknown direction) — original behavior.
    gap = f" ({delta} behind)" if delta else ""
    print("")
    print("ERROR: Test DB BEHIND alembic head.")
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
