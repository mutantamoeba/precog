#!/usr/bin/env python3
"""
Cleanup Frozen Processes - Manual recovery for frozen Claude Code sessions.

When Claude Code sessions freeze during pre-push hooks, orphaned processes are
left running because Windows doesn't propagate SIGTERM to child processes.

These orphaned processes:
  - Hold database connections (causing pool exhaustion)
  - Hold file locks (causing git operations to hang)
  - Consume memory (100MB+ per pytest process)

Usage:
    python scripts/cleanup_frozen_processes.py          # Kill all orphaned processes
    python scripts/cleanup_frozen_processes.py --check  # Just check, don't kill
    python scripts/cleanup_frozen_processes.py --force  # Kill without confirmation

Reference:
    - Issue #230: Pre-push hook freeze root cause analysis
    - CLAUDE.md: Session recovery workflow

Author: Claude Code (automated recovery tool)
Created: 2025-12-26
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def get_process_count(pattern: str) -> int:
    """Count processes matching a command line pattern."""
    try:
        result = subprocess.run(
            ["wmic", "process", "where", f"commandline like '%{pattern}%'", "get", "processid"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Count non-empty lines minus the header
        lines = [line.strip() for line in result.stdout.split("\n") if line.strip()]
        return max(0, len(lines) - 1)  # Subtract header line
    except Exception:
        return 0


def kill_processes(pattern: str, description: str) -> int:
    """Kill processes matching a command line pattern."""
    count = get_process_count(pattern)
    if count > 0:
        print(f"  Killing {count} {description}...")
        try:
            subprocess.run(
                ["wmic", "process", "where", f"commandline like '%{pattern}%'", "delete"],
                capture_output=True,
                timeout=30,
            )
            return count
        except Exception as e:
            print(f"  Error killing {description}: {e}")
            return 0
    return 0


def kill_by_name(process_name: str, description: str) -> int:
    """Kill processes by executable name."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Count matching lines (excluding header)
        count = sum(1 for line in result.stdout.split("\n") if process_name.lower() in line.lower())
        if count > 0:
            print(f"  Killing {count} {description}...")
            subprocess.run(
                ["taskkill", "/F", "/IM", process_name],
                capture_output=True,
                timeout=30,
            )
            return count
    except Exception as e:
        print(f"  Error killing {description}: {e}")
    return 0


def check_processes() -> dict[str, int]:
    """Check for orphaned processes and return counts."""
    return {
        "pytest": get_process_count("pytest"),
        "run_parallel_checks": get_process_count("run_parallel_checks"),
        "git-remote-https": get_process_count("git-remote-https"),
        "validate_": get_process_count("validate_"),  # Validation scripts
    }


def cleanup_all(force: bool = False) -> int:
    """Kill all orphaned processes."""
    print("=" * 60)
    print("Frozen Process Cleanup Tool")
    print("=" * 60)
    print()

    # Check current state
    print("Checking for orphaned processes...")
    counts = check_processes()
    total = sum(counts.values())

    if total == 0:
        print("  No orphaned processes found!")
        return 0

    print(f"  Found {total} orphaned process(es):")
    for name, count in counts.items():
        if count > 0:
            print(f"    - {name}: {count}")
    print()

    # Confirm unless forced
    if not force:
        response = input("Kill all orphaned processes? [y/N]: ").strip().lower()
        if response != "y":
            print("Aborted.")
            return 0

    # Kill processes
    print()
    print("Cleaning up...")
    killed = 0
    killed += kill_processes("pytest", "pytest processes")
    killed += kill_processes("run_parallel_checks", "parallel check processes")
    killed += kill_by_name("git-remote-https.exe", "git-remote-https processes")
    killed += kill_processes("validate_", "validation script processes")

    print()
    print("=" * 60)
    print(f"Cleanup complete! Killed {killed} process(es).")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Start a new Claude Code session")
    print("  2. Run: git status (verify clean state)")
    print("  3. Try your push again")
    print()

    return killed


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Cleanup orphaned processes from frozen Claude Code sessions"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Just check for orphaned processes, don't kill them",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Kill processes without confirmation",
    )
    args = parser.parse_args()

    if sys.platform != "win32":
        print("This script is designed for Windows. On Unix, orphaned processes")
        print("are typically cleaned up automatically when the parent exits.")
        print()
        print("If you're experiencing frozen processes on Unix, try:")
        print("  pkill -f pytest")
        print("  pkill -f run_parallel_checks")
        return 1

    if args.check:
        print("Checking for orphaned processes...")
        counts = check_processes()
        total = sum(counts.values())
        if total == 0:
            print("  No orphaned processes found!")
        else:
            print(f"  Found {total} orphaned process(es):")
            for name, count in counts.items():
                if count > 0:
                    print(f"    - {name}: {count}")
        return 0

    cleanup_all(force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
