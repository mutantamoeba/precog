"""
Precog Runners - Production service entry points.

This module contains production-grade service runners that wrap core components
with proper signal handling, PID management, and startup validation.

Modules:
    service_runner: Data collection service runner (ESPN, Kalshi polling)

Why This Module Exists:
    Separates "production concerns" (signal handling, PID files, logging setup)
    from "core logic" (ServiceSupervisor, pollers). This allows:
    1. Core logic to be unit tested without production infrastructure
    2. Production runners to be integration tested
    3. CLI commands to be thin wrappers around testable code

Reference:
    - Issue #193: Phase 2.5 Live Data Collection Service
    - ADR-100: Service Supervisor Pattern
"""

from precog.runners.service_runner import DataCollectorService

__all__ = ["DataCollectorService"]
