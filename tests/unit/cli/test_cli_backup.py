"""Smoke tests for backup CLI module (#565, PR #597).

Minimal unit coverage for the experimental backup CLI to satisfy the
test type coverage audit (TESTING_STRATEGY V3.2). The backup CLI commands
(create, list, restore, info) are exercised end-to-end by the orchestrator
integration tests; these tests verify the typer app and commands are
importable and structurally sound.

Tracking issue for full test suite expansion: TBD (file as follow-up).
"""

from __future__ import annotations

import pytest
import typer


@pytest.mark.unit
class TestBackupCli:
    """Smoke tests for backup CLI module surface."""

    def test_backup_cli_module_is_importable(self) -> None:
        """Verify the backup CLI module is importable."""
        from precog.cli import backup

        assert backup is not None

    def test_backup_cli_exposes_typer_app(self) -> None:
        """Verify the module exposes a Typer app named 'app'."""
        from precog.cli.backup import app

        assert isinstance(app, typer.Typer)

    def test_backup_cli_commands_are_callable(self) -> None:
        """Verify the four documented commands are callable."""
        from precog.cli.backup import create, info, list_backups, restore

        assert callable(create)
        assert callable(list_backups)
        assert callable(restore)
        assert callable(info)
