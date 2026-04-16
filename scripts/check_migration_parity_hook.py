#!/usr/bin/env python
"""Claude Code UserPromptSubmit hook: check migration parity.

Outputs a warning if the dev DB is behind alembic head.
Fails silently on any error (no DB, no credentials, etc.)
so it never blocks the conversation.

Wired via .claude/projects/.../settings.json UserPromptSubmit hook.
Issue: #792
"""

from __future__ import annotations

import os


def main() -> None:
    # Only check against dev DB, not test
    os.environ.setdefault("PRECOG_ENV", "dev")

    try:
        from precog.database.migration_check import check_migration_parity

        status = check_migration_parity()

        if status.error:
            # Silently skip — DB might not be reachable
            return

        if not status.is_current:
            behind = status.versions_behind
            gap = f" ({behind} behind)" if behind else ""
            print(
                f"WARNING: Dev DB at migration {status.db_version}, "
                f"head is {status.head_version}{gap}. "
                f"Run: cd src/precog/database && python -m alembic upgrade head"
            )
    except Exception:
        # Never block the conversation on hook failure
        pass


if __name__ == "__main__":
    main()
