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
- If the test DB is BEHIND (delta > 0): attempt `alembic upgrade head`
  automatically and exit 0 on success. Falls through to the existing
  BEHIND error message on failure or when auto-upgrade is unsafe (dirty
  alembic versions tree, --no-auto-upgrade flag).
- If the test DB is AHEAD (delta < 0): never auto-upgrade — the developer
  is on a branch with newer migrations than `main`. Falls through to the
  existing error reporting.
- Exits 1 with an actionable error message if behind/ahead and auto-upgrade
  did not resolve the gap.

Mirrors the UserPromptSubmit dev-DB hook (scripts/check_migration_parity_hook.py)
but (a) targets the test DB and (b) blocks instead of warning.

Issue: #867 (this hook)
Related: #792 (dev-DB UserPromptSubmit hook precedent), #1103 (auto-upgrade
on BEHIND), #1101 (AHEAD vs BEHIND disambiguated message)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

# SSOT (Pattern 73): single source for the alembic.ini path used in both
# the auto-upgrade subprocess invocation and the BEHIND remediation hint.
_ALEMBIC_INI = "src/precog/database/alembic.ini"
_ALEMBIC_VERSIONS_DIR = "src/precog/database/alembic/versions/"


def _alembic_versions_tree_dirty() -> bool:
    """Return True if the alembic versions directory has uncommitted changes.

    Auto-upgrade is unsafe when the developer has in-progress migration
    work (staged or unstaged edits under alembic/versions/), because
    upgrading would apply potentially-incomplete migration code. We detect
    this with `git diff --quiet` (unstaged) and `git diff --cached --quiet`
    (staged) — both return non-zero when there are changes.

    Returns True if either has changes (auto-upgrade should be skipped),
    False if the tree is clean. If git itself fails (not a repo, etc.),
    returns True conservatively to block auto-upgrade.
    """
    for cmd in (
        ["git", "diff", "--quiet", _ALEMBIC_VERSIONS_DIR],
        ["git", "diff", "--cached", "--quiet", _ALEMBIC_VERSIONS_DIR],
    ):
        try:
            # `git diff --quiet` should be near-instant; 10s is a generous bound
            # that still bounds a hung-git failure mode. TimeoutExpired is a
            # SubprocessError subclass and falls into the conservative-True path.
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            # git unavailable, hung, or some unexpected failure — block
            # auto-upgrade rather than silently proceeding with possibly-stale
            # code.
            return True
        if result.returncode != 0:
            return True
    return False


def _attempt_alembic_upgrade() -> tuple[bool, str, str]:
    """Run `alembic upgrade head` against the test DB.

    Returns (success, stdout, stderr). Forces PRECOG_ENV=test in the
    subprocess environment so the alembic invocation targets the same
    DB the parity check just inspected.
    """
    env = os.environ.copy()
    env["PRECOG_ENV"] = "test"
    try:
        # 5 min ceiling: a multi-migration upgrade can legitimately take
        # tens of seconds, but should never run for minutes. A hang here
        # blocks the developer's pre-push indefinitely. TimeoutExpired is a
        # SubprocessError subclass and is caught by the existing handler.
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", _ALEMBIC_INI, "upgrade", "head"],
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return False, "", f"subprocess invocation failed: {e}"
    return result.returncode == 0, result.stdout or "", result.stderr or ""


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify test DB is at alembic head; auto-upgrade if BEHIND."
    )
    parser.add_argument(
        "--no-auto-upgrade",
        action="store_true",
        help="Disable the automatic `alembic upgrade head` when the test DB is BEHIND. "
        "The hook will fall through to the standard error message instead. "
        "Has no effect when the test DB is AHEAD.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the parity check. Returns exit code (0 OK/skip, 1 block, 2 fatal).

    `argv`: list of CLI args. Defaults to `sys.argv[1:]` when invoked from
    the shell (`if __name__ == "__main__"` below passes it explicitly).
    Tests calling `main()` with no args get an empty list, so argparse
    does not accidentally pick up the test runner's own argv.
    """
    if argv is None:
        argv = []
    args = _parse_args(argv)

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

    # Mismatch detected. Determine direction and decide whether to auto-upgrade.
    # versions_behind: positive = BEHIND (DB < head), negative = AHEAD (DB > head),
    # None = unknown (non-numeric versions).
    delta = status.versions_behind

    if delta is not None and delta > 0:
        # BEHIND. Attempt auto-upgrade unless disabled or unsafe.
        if args.no_auto_upgrade:
            print("INFO: --no-auto-upgrade flag set; skipping automatic alembic upgrade.")
        elif _alembic_versions_tree_dirty():
            print("")
            print(
                "INFO: alembic versions tree has uncommitted changes; skipping automatic upgrade."
            )
            print(
                "      Auto-upgrade is unsafe when migration work is in progress "
                "(staged or unstaged"
            )
            print(
                f"      edits under {_ALEMBIC_VERSIONS_DIR}). Commit or stash before re-running, or"
            )
            print("      run the upgrade manually.")
        else:
            print("")
            print("=" * 72)
            print("AUTO-UPGRADE: test DB is BEHIND alembic head; running upgrade...")
            print(f"  Command: PRECOG_ENV=test python -m alembic -c {_ALEMBIC_INI} upgrade head")
            print("=" * 72)
            success, up_stdout, up_stderr = _attempt_alembic_upgrade()
            if up_stdout:
                print(up_stdout, end="" if up_stdout.endswith("\n") else "\n")
            if success:
                print("=" * 72)
                print("AUTO-UPGRADE: success — test DB now at alembic head.")
                print("=" * 72)
                return 0
            # Auto-upgrade attempted and failed. Surface the failure detail
            # to stderr, then fall through to the standard BEHIND error.
            print("", file=sys.stderr)
            print(
                "AUTO-UPGRADE FAILED: alembic upgrade head returned non-zero. "
                "Falling through to the original error message below.",
                file=sys.stderr,
            )
            if up_stderr:
                print("--- alembic stderr ---", file=sys.stderr)
                print(up_stderr, end="" if up_stderr.endswith("\n") else "\n", file=sys.stderr)
                print("--- end alembic stderr ---", file=sys.stderr)

    # Fall through: render the existing actionable error message. This block
    # currently formats as "behind" for both BEHIND and AHEAD; PR #1104
    # (#1101) introduces direction-aware branching here. Until that lands,
    # we keep the message body unchanged so this PR's diff stays scoped to
    # the auto-upgrade behavior.
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
    print(f"  PRECOG_ENV=test python -m alembic -c {_ALEMBIC_INI} upgrade head")
    print("")
    print("Reference: #867 (test DB migration parity hook), #792 (dev DB sibling)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
