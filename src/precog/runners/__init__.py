"""
Precog Runners - Production service entry points.

This module previously contained the DataCollectorService wrapper.
That code was removed as dead code — the actual production path uses
ServiceSupervisor directly via `cli/scheduler.py`:

    python main.py scheduler start --supervised --foreground

Reference:
    - ADR-100: Service Supervisor Pattern
    - Issue #324: Desktop Migration
"""

__all__: list[str] = []
