"""Unit tests for scripts/check_test_db_migration_parity.py (#867).

The hook itself is a thin adapter over precog.database.migration_check.
These tests verify the adapter's exit-code + stdout contract at each
branch: parity match, drift (behind), and graceful skip when the test
DB is unreachable or the module is unavailable.

Boundary choice:
- We mock check_migration_parity() at its module-level binding inside
  precog.database.migration_check. This mirrors tests/unit/database/
  test_migration_check.py (the canonical project pattern) and keeps the
  test independent of any actual DB connection. The hook's only
  external collaborator is check_migration_parity(); mocking it lets
  us drive every exit-code branch deterministically.

Reference:
- scripts/check_test_db_migration_parity.py
- precog.database.migration_check.MigrationStatus
- Issue #867 (this hook), Issue #792 (dev-DB sibling)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from precog.database.migration_check import MigrationStatus

# Add scripts/ to path so we can import the hook module.
_SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import check_test_db_migration_parity as hook_mod  # type: ignore[import-not-found]  # noqa: E402


class TestMainExitCodes:
    """Exit-code contract: 0 for OK/skip, 1 for drift."""

    @patch("precog.database.migration_check.check_migration_parity")
    def test_match_returns_zero(self, mock_check, capsys):
        mock_check.return_value = MigrationStatus(
            is_current=True,
            db_version="0063",
            head_version="0063",
        )

        rc = hook_mod.main()

        assert rc == 0
        out = capsys.readouterr().out
        assert "OK" in out
        assert "0063" in out

    @patch("precog.database.migration_check.check_migration_parity")
    def test_behind_returns_one_with_actionable_message(self, mock_check, capsys):
        mock_check.return_value = MigrationStatus(
            is_current=False,
            db_version="0056",
            head_version="0063",
        )

        rc = hook_mod.main()

        assert rc == 1
        out = capsys.readouterr().out
        # Must flag the drift clearly
        assert "ERROR" in out
        assert "behind" in out.lower()
        # Must mention both versions and the gap (7 behind)
        assert "0056" in out
        assert "0063" in out
        assert "7" in out  # versions_behind
        # Must include the exact remediation command
        assert "alembic" in out
        assert "upgrade head" in out
        assert "PRECOG_ENV=test" in out
        # Must cross-reference the issue for traceability
        assert "#867" in out

    @patch("precog.database.migration_check.check_migration_parity")
    def test_unreachable_db_skips_with_warning(self, mock_check, capsys):
        mock_check.return_value = MigrationStatus(
            is_current=False,
            db_version=None,
            head_version="0063",
            error="Could not read database version: connection refused",
        )

        rc = hook_mod.main()

        assert rc == 0  # Graceful skip — do not block developer without test DB
        out = capsys.readouterr().out
        assert "SKIP" in out
        # Surface the underlying reason so the developer knows why
        assert "connection refused" in out

    @patch("precog.database.migration_check.check_migration_parity")
    def test_unexpected_exception_exits_two_loudly(self, mock_check, capsys):
        """An unexpected exception in check_migration_parity is a bug in the
        helper, not a skippable condition. Exit 2 = loud failure so the
        developer sees the real error. Glokta S62 review: swallowing this
        reintroduces the silent-CI pattern #867 exists to prevent.
        """
        mock_check.side_effect = RuntimeError("unexpected failure")

        rc = hook_mod.main()

        assert rc == 2
        err = capsys.readouterr().err  # FATAL messages go to stderr
        assert "FATAL" in err
        assert "unexpected failure" in err

    @patch("precog.database.migration_check.check_migration_parity")
    def test_multi_head_alembic_chain_blocks_not_skips(self, mock_check, capsys):
        """Multi-head alembic chain is a schema-hygiene problem, not a skip.
        Glokta S62: silent skip reintroduces #867's target failure mode.
        """
        mock_check.return_value = MigrationStatus(
            is_current=False,
            db_version=None,
            head_version=None,
            error="Multiple alembic heads detected: ['0063', '0064_sibling']. Run `alembic merge heads` before pushing.",
            fatal=True,
        )

        rc = hook_mod.main()

        assert rc == 1  # Block, not skip
        out = capsys.readouterr().out
        assert "ERROR" in out
        assert "Multiple alembic heads" in out
        assert "alembic merge heads" in out

    @patch("precog.database.migration_check.check_migration_parity")
    def test_forces_precog_env_to_test(self, mock_check, monkeypatch):
        """The hook must always check the test DB, never whatever env happens to be set."""
        monkeypatch.setenv("PRECOG_ENV", "dev")
        mock_check.return_value = MigrationStatus(
            is_current=True, db_version="0063", head_version="0063"
        )

        hook_mod.main()

        import os

        assert os.environ["PRECOG_ENV"] == "test"


class TestAutoUpgradeOnBehind:
    """#1103: when the test DB is BEHIND, attempt `alembic upgrade head` automatically.

    These tests pin the auto-upgrade behavior at every branch:
    - BEHIND + clean tree + flag absent -> attempt + success -> exit 0
    - BEHIND + clean tree + flag absent -> attempt + failure -> fall through
    - BEHIND + dirty tree -> skip attempt -> fall through with INFO
    - BEHIND + --no-auto-upgrade -> skip attempt -> fall through with INFO
    - AHEAD -> never attempt -> existing error path
    """

    @patch("check_test_db_migration_parity._alembic_versions_tree_dirty", return_value=False)
    @patch("check_test_db_migration_parity._attempt_alembic_upgrade")
    @patch("precog.database.migration_check.check_migration_parity")
    def test_behind_triggers_auto_upgrade_by_default(
        self, mock_check, mock_upgrade, mock_dirty, capsys
    ):
        mock_check.return_value = MigrationStatus(
            is_current=False, db_version="0056", head_version="0063"
        )
        mock_upgrade.return_value = (True, "alembic upgrade ok\n", "")

        rc = hook_mod.main([])

        assert rc == 0
        assert mock_upgrade.called
        out = capsys.readouterr().out
        assert "AUTO-UPGRADE" in out
        assert "success" in out.lower()

    @patch("check_test_db_migration_parity._alembic_versions_tree_dirty", return_value=False)
    @patch("check_test_db_migration_parity._attempt_alembic_upgrade")
    @patch("precog.database.migration_check.check_migration_parity")
    def test_behind_with_no_auto_upgrade_flag_skips_attempt(
        self, mock_check, mock_upgrade, mock_dirty, capsys
    ):
        mock_check.return_value = MigrationStatus(
            is_current=False, db_version="0056", head_version="0063"
        )

        rc = hook_mod.main(["--no-auto-upgrade"])

        assert rc == 1  # falls through to standard BEHIND error
        assert not mock_upgrade.called
        captured = capsys.readouterr()
        # Standard BEHIND remediation must still appear
        assert "ERROR" in captured.out
        assert "alembic" in captured.out
        # And the INFO about the flag
        assert "--no-auto-upgrade" in captured.out

    @patch("check_test_db_migration_parity._alembic_versions_tree_dirty", return_value=True)
    @patch("check_test_db_migration_parity._attempt_alembic_upgrade")
    @patch("precog.database.migration_check.check_migration_parity")
    def test_behind_with_dirty_alembic_tree_skips_attempt(
        self, mock_check, mock_upgrade, mock_dirty, capsys
    ):
        mock_check.return_value = MigrationStatus(
            is_current=False, db_version="0056", head_version="0063"
        )

        rc = hook_mod.main([])

        assert rc == 1  # falls through to standard BEHIND error
        assert not mock_upgrade.called
        out = capsys.readouterr().out
        # INFO about the dirty-tree skip
        assert "uncommitted changes" in out
        # Original BEHIND error still rendered
        assert "ERROR" in out
        assert "behind" in out.lower()

    @patch("check_test_db_migration_parity._alembic_versions_tree_dirty", return_value=False)
    @patch("check_test_db_migration_parity._attempt_alembic_upgrade")
    @patch("precog.database.migration_check.check_migration_parity")
    def test_ahead_does_not_attempt_upgrade(self, mock_check, mock_upgrade, mock_dirty, capsys):
        # AHEAD: db_version > head_version -> versions_behind is negative.
        mock_check.return_value = MigrationStatus(
            is_current=False, db_version="0063", head_version="0056"
        )

        rc = hook_mod.main([])

        assert rc == 1
        assert not mock_upgrade.called  # Never auto-upgrade on AHEAD

    @patch("check_test_db_migration_parity._alembic_versions_tree_dirty", return_value=False)
    @patch("check_test_db_migration_parity._attempt_alembic_upgrade")
    @patch("precog.database.migration_check.check_migration_parity")
    def test_failed_auto_upgrade_falls_through_with_both_messages(
        self, mock_check, mock_upgrade, mock_dirty, capsys
    ):
        mock_check.return_value = MigrationStatus(
            is_current=False, db_version="0056", head_version="0063"
        )
        mock_upgrade.return_value = (
            False,
            "running migrations...\n",
            "alembic.util.exc.CommandError: boom\n",
        )

        rc = hook_mod.main([])

        assert rc == 1
        assert mock_upgrade.called
        captured = capsys.readouterr()
        # Failure detail on stderr
        assert "AUTO-UPGRADE FAILED" in captured.err
        assert "boom" in captured.err
        # Original BEHIND error on stdout
        assert "ERROR" in captured.out
        assert "behind" in captured.out.lower()
        assert "0056" in captured.out
        assert "0063" in captured.out


class TestAlembicVersionsTreeDirty:
    """Cover the helper directly so the integration tests can mock it."""

    @patch("subprocess.run")
    def test_clean_tree_returns_false(self, mock_run):
        # Both `git diff --quiet` invocations return 0 -> clean.
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        assert hook_mod._alembic_versions_tree_dirty() is False
        # Two calls: unstaged + cached
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_unstaged_changes_return_true(self, mock_run):
        # First call (unstaged) returns 1 -> dirty; short-circuits.
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1)
        assert hook_mod._alembic_versions_tree_dirty() is True

    @patch("subprocess.run")
    def test_staged_changes_return_true(self, mock_run):
        # Unstaged clean, staged dirty.
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0),
            subprocess.CompletedProcess(args=[], returncode=1),
        ]
        assert hook_mod._alembic_versions_tree_dirty() is True

    @patch("subprocess.run", side_effect=OSError("git not found"))
    def test_git_failure_blocks_auto_upgrade(self, mock_run):
        # Conservative: if git itself fails, treat as dirty (block auto-upgrade).
        assert hook_mod._alembic_versions_tree_dirty() is True


class TestScriptInvocation:
    """End-to-end: run the script as a subprocess and verify exit code."""

    def test_script_is_executable_as_module(self, tmp_path, monkeypatch):
        """Smoke test: the script can be invoked and returns an integer exit code.

        We don't assert the specific exit code here because it depends on the
        developer's local test DB state. We only verify the script runs to
        completion without crashing (the branches' behavior is covered above).
        """
        repo_root = Path(__file__).parent.parent.parent.parent
        script = repo_root / "scripts" / "check_test_db_migration_parity.py"
        assert script.exists()

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(repo_root),
        )

        # Must exit with 0 or 1 — never crash (2+) or hang.
        assert result.returncode in (0, 1), (
            f"Script crashed: rc={result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        # Must print something actionable on stdout
        assert result.stdout.strip(), "Script should always print a status line"


class TestPrePushValidationWiring:
    """Verify the hook is actually invoked by the real push path.

    Glokta S62: without this test, the hook could be dead code — registered
    in .pre-commit-config.yaml but never fired because scripts/pre-push-
    validation.sh (the live push entry point) doesn't call the pre-commit
    framework. This test is the anti-regression guard on the wiring itself.
    """

    def test_pre_push_validation_invokes_parity_check(self):
        """scripts/pre-push-validation.sh must invoke the parity script."""
        repo_root = Path(__file__).parent.parent.parent.parent
        validation_script = repo_root / "scripts" / "pre-push-validation.sh"
        assert validation_script.exists(), (
            "pre-push-validation.sh is the live push entry point; missing means "
            "the entire pre-push validation layer is gone."
        )
        content = validation_script.read_text(encoding="utf-8")
        assert "check_test_db_migration_parity.py" in content, (
            "pre-push-validation.sh does not invoke the #867 parity check. "
            "Without this wiring, the hook is dead code and #867's silent-CI "
            "failure class is reintroduced. Add a call to "
            "`python scripts/check_test_db_migration_parity.py` near the top "
            "of the script (see STEP 0.2)."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
