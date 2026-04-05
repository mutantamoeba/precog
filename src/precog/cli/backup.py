"""
Backup CLI Commands.

Provides commands for database backup creation, listing, restoration,
and storage backend status.

Commands:
    create  - Create a manual database backup
    list    - List available backups
    restore - Restore database from a backup
    info    - Show storage backend information

Usage:
    precog backup create                    # Create manual backup
    precog backup create --type daily       # Create daily backup
    precog backup list                      # List all backups
    precog backup list --limit 5            # List 5 most recent
    precog backup restore <backup-id>       # Restore from backup
    precog backup restore <id> --force      # Force cross-env restore
    precog backup info                      # Show backend info

Related:
    - Issue #565: Automated backup system
    - system.yaml backup section
"""

from __future__ import annotations

import typer
from rich.table import Table

from precog.cli._common import (
    ExitCode,
    cli_error,
    console,
    echo_success,
)

app = typer.Typer(
    name="backup",
    help="Database backup and restore operations",
    no_args_is_help=True,
)


@app.command()
def create(
    backup_type: str = typer.Option(
        "manual",
        "--type",
        "-t",
        help="Backup type: manual, daily, weekly, monthly",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output including row counts",
    ),
) -> None:
    """Create a database backup.

    Runs pg_dump, verifies the backup, stores it via the configured
    storage backend, and enforces retention policy.

    Example:
        precog backup create                  # Manual backup
        precog backup create --type daily     # Tagged as daily
        precog backup create -v               # Verbose output
    """
    from precog.backup import BackupOrchestrator, BackupType
    from precog.backup._types import BackupError

    # Validate backup type
    try:
        bt = BackupType(backup_type)
    except ValueError:
        valid = ", ".join(t.value for t in BackupType)
        cli_error(
            f"Invalid backup type: '{backup_type}'",
            ExitCode.USAGE_ERROR,
            hint=f"Valid types: {valid}",
        )

    try:
        console.print(f"\n[bold]Creating {bt.value} backup...[/bold]")
        orchestrator = BackupOrchestrator()

        # Show backend info
        info = orchestrator.backend.get_storage_info()
        console.print(f"  Storage: {info.get('type', 'unknown')}")
        if "directory" in info:
            console.print(f"  Directory: {info['directory']}")
        console.print()

        metadata = orchestrator.create_backup(backup_type=bt)

        # Display results
        console.print("[green]Backup completed successfully![/green]\n")

        results_table = Table(show_header=False, box=None, padding=(0, 2))
        results_table.add_column("Field", style="dim")
        results_table.add_column("Value", style="bold")

        results_table.add_row("Backup ID", metadata.backup_id)
        results_table.add_row("Database", metadata.database_name)
        results_table.add_row("Environment", metadata.environment)
        results_table.add_row("Status", metadata.status.value)
        results_table.add_row("Size", _format_bytes(metadata.size_bytes))
        results_table.add_row("Verified", str(metadata.verified))
        results_table.add_row("Checksum", metadata.checksum_sha256[:16] + "...")
        if metadata.migration_head:
            results_table.add_row("Migration", metadata.migration_head)

        console.print(results_table)

        if verbose and metadata.row_counts:
            console.print("\n[bold]Row Counts:[/bold]")
            counts_table = Table(box=None, padding=(0, 2))
            counts_table.add_column("Table", style="dim")
            counts_table.add_column("Rows", justify="right")
            for table, count in sorted(metadata.row_counts.items()):
                counts_table.add_row(
                    table,
                    f"{count:,}" if count >= 0 else "[red]N/A[/red]",
                )
            console.print(counts_table)

        echo_success(f"Backup saved: {metadata.backup_id} ({_format_bytes(metadata.size_bytes)})")

    except BackupError as e:
        cli_error(str(e), ExitCode.ERROR)
    except Exception as e:
        cli_error(
            f"Unexpected backup error: {e}",
            ExitCode.ERROR,
            hint="Check database connection and pg_dump availability",
        )


@app.command("list")
def list_backups(
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        help="Maximum number of backups to show",
    ),
    all_backups: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Show all backups (no limit)",
    ),
) -> None:
    """List available database backups.

    Shows backups from the active storage backend, sorted newest first.

    Example:
        precog backup list              # Show 20 most recent
        precog backup list --limit 5    # Show 5 most recent
        precog backup list --all        # Show all backups
    """
    from precog.backup import BackupOrchestrator
    from precog.backup._types import BackupError

    try:
        orchestrator = BackupOrchestrator()
        all_backup_list = orchestrator.list_backups()

        if not all_backup_list:
            console.print("\n[yellow]No backups found.[/yellow]")
            console.print("[dim]Run 'precog backup create' to create one.[/dim]")
            return

        # Slice for display, keep total count from single call
        total = len(all_backup_list)
        backups = all_backup_list if all_backups else all_backup_list[:limit]

        # Show backend info
        info = orchestrator.backend.get_storage_info()
        console.print(f"\n[bold]Backups[/bold] [dim]({info.get('type', 'unknown')})[/dim]\n")

        table = Table()
        table.add_column("Backup ID", style="bold")
        table.add_column("Type")
        table.add_column("Status")
        table.add_column("Size", justify="right")
        table.add_column("Date")
        table.add_column("Env")
        table.add_column("Verified")

        for b in backups:
            status_style = {
                "verified": "green",
                "completed": "blue",
                "failed": "red",
                "in_progress": "yellow",
            }.get(b.status.value, "")

            table.add_row(
                b.backup_id,
                b.backup_type.value,
                f"[{status_style}]{b.status.value}[/{status_style}]",
                _format_bytes(b.size_bytes),
                b.created_at.strftime("%Y-%m-%d %H:%M"),
                b.environment,
                "[green]yes[/green]" if b.verified else "[dim]no[/dim]",
            )

        console.print(table)

        if not all_backups and total > limit:
            console.print(f"\n[dim]Showing {limit} of {total}. Use --all to see all.[/dim]")

    except BackupError as e:
        cli_error(str(e), ExitCode.ERROR)
    except Exception as e:
        cli_error(
            f"Failed to list backups: {e}",
            ExitCode.ERROR,
        )


@app.command()
def restore(
    backup_id: str = typer.Argument(
        help="Backup ID to restore (from 'precog backup list')",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force cross-environment restore (e.g., dev backup into staging)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be restored without actually restoring",
    ),
) -> None:
    """Restore database from a backup.

    Downloads the backup from storage, verifies checksum integrity,
    and runs pg_restore. Includes safety checks for cross-environment
    restores.

    WARNING: This will overwrite the current database contents!

    Example:
        precog backup restore precog_dev_20260405_030000_manual.dump
        precog backup restore <id> --force    # Cross-env restore
        precog backup restore <id> --dry-run  # Preview only
    """
    from precog.backup import BackupOrchestrator
    from precog.backup._types import BackupError

    try:
        orchestrator = BackupOrchestrator()

        # Find backup metadata for display
        backups = orchestrator.list_backups()
        metadata = None
        for b in backups:
            if b.backup_id == backup_id:
                metadata = b
                break

        if metadata is None:
            cli_error(
                f"Backup '{backup_id}' not found.",
                ExitCode.ERROR,
                hint="Run 'precog backup list' to see available backups.",
            )

        # Show what we're about to restore
        console.print("\n[bold]Restore Preview:[/bold]")
        console.print(f"  Backup: {metadata.backup_id}")
        console.print(f"  Database: {metadata.database_name}")
        console.print(f"  Environment: {metadata.environment}")
        console.print(f"  Size: {_format_bytes(metadata.size_bytes)}")
        console.print(f"  Created: {metadata.created_at}")
        console.print(f"  Verified: {metadata.verified}")
        if metadata.checksum_sha256:
            console.print(f"  Checksum: {metadata.checksum_sha256[:16]}...")

        if dry_run:
            console.print("\n[yellow]Dry run — no changes made.[/yellow]")
            return

        # Confirmation
        console.print("\n[red bold]WARNING: This will overwrite the current database![/red bold]")
        confirm = typer.confirm("Proceed with restore?")
        if not confirm:
            console.print("[dim]Restore cancelled.[/dim]")
            raise typer.Exit

        console.print("\n[bold]Restoring...[/bold]")
        orchestrator.restore_backup(backup_id, force=force)
        echo_success(f"Database restored from: {backup_id}")

    except BackupError as e:
        cli_error(str(e), ExitCode.ERROR)
    except typer.Exit:
        raise
    except Exception as e:
        cli_error(
            f"Restore failed: {e}",
            ExitCode.ERROR,
            hint="Check pg_restore availability and database connectivity",
        )


@app.command()
def info() -> None:
    """Show storage backend information.

    Displays the active storage backend type, location, and
    available space.

    Example:
        precog backup info
    """
    from precog.backup import BackupOrchestrator
    from precog.backup._types import BackupError

    try:
        orchestrator = BackupOrchestrator()
        info_data = orchestrator.backend.get_storage_info()

        console.print("\n[bold]Backup Storage Info[/bold]\n")

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="dim")
        table.add_column("Value", style="bold")

        for key, value in info_data.items():
            table.add_row(key.replace("_", " ").title(), str(value))

        # Also show backup count
        backups = orchestrator.list_backups()
        table.add_row("Total Backups", str(len(backups)))
        if backups:
            total_size = sum(b.size_bytes for b in backups)
            table.add_row("Total Size", _format_bytes(total_size))
            table.add_row("Latest", backups[0].backup_id)

        console.print(table)

    except BackupError as e:
        cli_error(str(e), ExitCode.ERROR)
    except Exception as e:
        cli_error(
            f"Failed to get backup info: {e}",
            ExitCode.ERROR,
        )


def _format_bytes(size: int) -> str:
    """Format bytes to human-readable string."""
    if size == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size_f = float(size)
    while size_f >= 1024 and i < len(units) - 1:
        size_f /= 1024
        i += 1
    return f"{size_f:.1f} {units[i]}"
