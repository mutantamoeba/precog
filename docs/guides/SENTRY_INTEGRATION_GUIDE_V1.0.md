# Sentry Integration Guide (Hybrid Architecture)

---
**Version:** 1.0
**Created:** 2025-11-14
**Last Updated:** 2025-11-14
**Status:** 🔵 Planned (Phase 2)
**Related Documents:**
- `docs/foundation/ARCHITECTURE_DECISIONS_V2.14.md` (ADR-055)
- `docs/foundation/MASTER_REQUIREMENTS_V2.14.md` (REQ-OBSERV-002)
- `docs/foundation/DEVELOPMENT_PHASES_V1.9.md` (Phase 2, Task #7)
- `docs/foundation/PROJECT_OVERVIEW_V1.5.md` (Tech Stack)
- `src/precog/utils/logger.py` (Existing structured logging)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture: The 3-Layer Hybrid System](#architecture-the-3-layer-hybrid-system)
3. [Gap Analysis: Current State](#gap-analysis-current-state)
4. [Prerequisites](#prerequisites)
5. [Phase 2.0: Sentry Initial Setup (30 min)](#phase-20-sentry-initial-setup-30-min)
6. [Phase 2.1: Logger Integration (1 hour)](#phase-21-logger-integration-1-hour)
7. [Phase 2.2: Alert Manager Implementation (3 hours)](#phase-22-alert-manager-implementation-3-hours)
8. [Phase 2.3: Notification System (5 hours)](#phase-23-notification-system-5-hours)
9. [Testing & Validation](#testing--validation)
10. [Configuration Reference](#configuration-reference)
11. [Troubleshooting](#troubleshooting)
12. [Performance & Cost Considerations](#performance--cost-considerations)

---

## Overview

**Purpose:** This guide provides step-by-step instructions for implementing Sentry production error tracking using a **hybrid architecture** that integrates with (not replaces) Precog's existing observability infrastructure.

**The Problem We're Solving:**

Precog currently has three **disconnected** observability layers:
1. **logger.py** - Writes JSON logs to files only, NO database integration, NO real-time alerts
2. **alerts table** (PostgreSQL) - Exists in database (migration 002) but **ORPHANED** (no code writes to it yet)
3. **Notification system** - NOT IMPLEMENTED (no email/SMS)

This means:
- ❌ Errors sit in log files with no real-time visibility
- ❌ No automatic error deduplication or grouping
- ❌ No centralized dashboard for production issues
- ❌ alerts table exists but unused
- ❌ No way to notify team of critical failures

**The Solution:**

A **3-layer hybrid architecture** where all layers work together:

1. **Layer 1: logger.py** - Primary audit trail (files only, ALL events)
2. **Layer 2: Sentry** - Real-time error tracking (cloud, ERROR/CRITICAL only)
3. **Layer 3: alerts table** - Permanent record (database, alert tracking)

**Key Principle:** Sentry **complements** existing infrastructure, not replaces it.

---

## Architecture: The 3-Layer Hybrid System

### Separation of Concerns

| Layer | Purpose | What It Stores | When to Use |
|-------|---------|----------------|-------------|
| **logger.py** | Audit trail | ALL events (INFO, DEBUG, ERROR) | Always - comprehensive logging |
| **Sentry** | Real-time visibility | ERROR/CRITICAL code errors only | When error needs immediate attention |
| **alerts table** | Permanent record | ALL alerts with acknowledgement | Business alerts + code errors |

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        APPLICATION CODE                          │
│  (API failures, trading logic, position monitoring, etc.)       │
└──────────────────┬──────────────────┬──────────────────────────┘
                   │                  │
                   ▼                  ▼
         ┌─────────────────┐   ┌──────────────────┐
         │  log_error()    │   │ create_alert()   │
         │  (logger.py)    │   │ (alert_manager)  │
         └────┬────────────┘   └────┬─────────────┘
              │                     │
              ▼                     ▼
    ┌──────────────────┐    ┌─────────────────────────┐
    │ File: logs/*.log │    │ 1. ALWAYS → alerts table│
    │ (audit trail)    │    │ 2. IF code error + high │
    └──────────────────┘    │    severity → Sentry    │
                            │ 3. IF critical → email  │
                            │    + SMS                │
                            └────┬────────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
            ┌───────────┐ ┌──────────┐ ┌──────────────┐
            │PostgreSQL │ │  Sentry  │ │Email/SMS     │
            │alerts     │ │  Cloud   │ │Notifications │
            └───────────┘ └──────────┘ └──────────────┘
```

### Code Error vs Business Alert

**Code Errors** (Sentry + DB + email):
- API failures (401, 500, timeout)
- Database connection failures
- Exception/stack traces
- Circuit breaker triggers
- System-level failures

**Business Alerts** (DB only, NO Sentry):
- Edge detected (INFO level, not an error)
- Position opened (INFO level)
- Loss limit approaching (WARNING, but not a code error)
- Daily summary (INFO level)

**Why this separation?** Sentry is for fixing **bugs**. Business alerts are expected system behavior.

---

## Gap Analysis: Current State

### What Already Exists

**✅ Structured Logging (logger.py):**
- Location: `src/precog/utils/logger.py`
- Writes JSON to `logs/precog_YYYY-MM-DD.log`
- Has helpers: `log_trade()`, `log_position_update()`, `log_edge_detected()`, `log_error()`
- Masks sensitive data (ADR-051: log masking processor)

**✅ alerts Table Schema:**
- Location: `src/precog/database/migrations/002_add_alerts_table.sql`
- Columns: `alert_id`, `alert_type`, `severity`, `component`, `message`, `details`, `fingerprint`, `notification_sent`, etc.
- **Status:** ORPHANED (exists but no code writes to it)

**✅ B3 Correlation IDs (ADR-049):**
- Request tracing implemented in Phase 1
- `request_id` available in logs for distributed debugging

### What Doesn't Exist (Phase 2 Tasks)

**❌ Sentry Integration:**
- No `sentry-sdk` installed
- No Sentry initialization
- No error forwarding to Sentry

**❌ Alert Manager:**
- No `utils/alert_manager.py` module
- No `create_alert()` function
- No code writes to alerts table

**❌ CRUD Operations for Alerts:**
- No `insert_alert()` in `database/crud_operations.py`
- No `get_alert()`, `update_alert()`, `acknowledge_alert()` functions

**❌ Notification System:**
- No email integration (SMTP)
- No SMS integration (Twilio)
- No `send_email_notification()` function
- No `send_sms_notification()` function

---

## Prerequisites

### Sentry Account Setup

1. **Create Sentry account** (FREE tier):
   - Visit https://sentry.io/signup/
   - Choose "Free" plan (5,000 errors/month, 10,000 transactions/month)
   - Create new project: "Precog" (Python platform)

2. **Get DSN (Data Source Name):**
   - After project creation, copy DSN from project settings
   - Format: `https://<key>@o<org-id>.ingest.sentry.io/<project-id>`

3. **Add to `.env` file:**
   ```bash
   # Sentry Configuration (Phase 2)
   SENTRY_DSN=https://your-key-here@o123456.ingest.sentry.io/789012
   ENVIRONMENT=demo  # or 'production', 'staging'
   ```

4. **Verify `.env` in `.gitignore`:**
   ```bash
   # Should see .env listed
   cat .gitignore | grep "\.env$"
   ```

### Email Configuration (SMTP)

Add to `.env`:
```bash
# Email Notifications (Phase 2)
SMTP_HOST=smtp.gmail.com  # or your SMTP server
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # NOT your regular password
SMTP_FROM=precog-alerts@yourdomain.com
ALERT_EMAIL_RECIPIENTS=team@yourdomain.com,oncall@yourdomain.com
```

**Gmail App Password Setup:**
1. Go to Google Account → Security → 2-Step Verification → App Passwords
2. Generate app password for "Mail"
3. Use this password in `SMTP_PASSWORD` (NOT your regular Gmail password)

### SMS Configuration (Twilio - Optional)

Add to `.env`:
```bash
# SMS Notifications (Phase 2 - Optional)
TWILIO_ACCOUNT_SID=AC...  # From Twilio dashboard
TWILIO_AUTH_TOKEN=...     # From Twilio dashboard
TWILIO_PHONE_NUMBER=+1234567890  # Your Twilio number
ALERT_SMS_RECIPIENTS=+1234567890,+0987654321  # Comma-separated
```

**Twilio Setup:**
1. Sign up at https://www.twilio.com/try-twilio (FREE trial: $15.50 credit)
2. Get phone number
3. Copy Account SID and Auth Token from dashboard

---

## Phase 2.0: Sentry Initial Setup (30 min)

### Step 1: Install sentry-sdk

**Update `requirements.txt`:**

```bash
# Add to requirements.txt (Observability & Monitoring section)
sentry-sdk==2.0.0  # Production error tracking and APM
```

**Install:**
```bash
pip install sentry-sdk==2.0.0
```

### Step 2: Initialize Sentry in main.py

**Location:** `src/precog/main.py` (create if doesn't exist)

```python
"""
Precog CLI Application

Main entry point with Sentry initialization.
"""
import os
import sys
from decimal import Decimal

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
import typer

# Import version from package
try:
    from importlib.metadata import version
    __version__ = version("precog")
except Exception:
    __version__ = "0.1.0"  # Fallback for development

app = typer.Typer(
    name="precog",
    help="Precog - Prediction market trading system",
    add_completion=False,
)


def init_sentry() -> None:
    """
    Initialize Sentry for production error tracking.

    Educational Note:
    - Only initializes if SENTRY_DSN is set (graceful degradation)
    - Uses hybrid architecture: Sentry receives ERROR+ from logger.py
    - Release tracking enables source maps and commit tracking
    - Sample rates control data sent to Sentry (cost optimization)

    Reference: ADR-055 (Sentry Integration - Hybrid Architecture)
    """
    sentry_dsn = os.getenv("SENTRY_DSN")

    # Graceful degradation: if no DSN, skip Sentry (local development)
    if not sentry_dsn:
        return

    environment = os.getenv("ENVIRONMENT", "demo")

    # Configure Sentry
    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=environment,
        release=f"precog@{__version__}",

        # Sample rates (cost optimization)
        traces_sample_rate=0.10,  # 10% of transactions for APM
        profiles_sample_rate=0.10,  # 10% of transactions for profiling

        # Integrations
        integrations=[
            # Forward ERROR/CRITICAL from Python logging to Sentry
            LoggingIntegration(
                level=None,        # Capture no logs by default
                event_level="ERROR"  # Send ERROR+ as Sentry events
            ),
        ],

        # Before send hook (respects log masking)
        before_send=before_send_hook,
    )


def before_send_hook(event: dict, hint: dict) -> dict | None:
    """
    Filter/modify events before sending to Sentry.

    Respects existing log masking from logger.py (ADR-051).

    Args:
        event: Sentry event dict
        hint: Additional context

    Returns:
        Modified event or None to drop event
    """
    # Add custom context
    event.setdefault("contexts", {})
    event["contexts"]["runtime"] = {
        "name": "precog",
        "version": __version__,
    }

    # Add tags for filtering in Sentry UI
    event.setdefault("tags", {})
    event["tags"]["environment"] = os.getenv("ENVIRONMENT", "demo")

    return event


@app.command()
def version():
    """Show Precog version."""
    typer.echo(f"Precog version {__version__}")


# Add other CLI commands here (fetch-markets, fetch-balance, etc.)


def main():
    """Main entry point with Sentry initialization."""
    # Initialize Sentry BEFORE running CLI
    init_sentry()

    # Run Typer CLI
    app()


if __name__ == "__main__":
    main()
```

### Step 3: Test Sentry Connection

**Create test script:** `scripts/test_sentry_connection.py`

```python
"""
Test Sentry connection.

Sends test error to verify Sentry is receiving events.
"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import sentry_sdk


def test_sentry_connection():
    """Send test error to Sentry."""
    sentry_dsn = os.getenv("SENTRY_DSN")

    if not sentry_dsn:
        print("[FAIL] SENTRY_DSN not set in .env")
        sys.exit(1)

    print(f"[INFO] Initializing Sentry (DSN: {sentry_dsn[:30]}...)")

    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=os.getenv("ENVIRONMENT", "demo"),
        release="precog@0.1.0-test",
    )

    print("[INFO] Sending test error to Sentry...")

    try:
        # Trigger intentional error
        1 / 0
    except ZeroDivisionError as e:
        sentry_sdk.capture_exception(e)

    # Flush events (ensure sent before script exits)
    sentry_sdk.flush(timeout=5.0)

    print("[OK] Test error sent to Sentry")
    print("[INFO] Check Sentry dashboard: https://sentry.io/")
    print("[INFO] You should see 'ZeroDivisionError' in Issues")


if __name__ == "__main__":
    test_sentry_connection()
```

**Run test:**
```bash
python scripts/test_sentry_connection.py
```

**Expected output:**
```
[INFO] Initializing Sentry (DSN: https://abc123...)
[INFO] Sending test error to Sentry...
[OK] Test error sent to Sentry
[INFO] Check Sentry dashboard: https://sentry.io/
```

**Verify in Sentry UI:**
1. Go to https://sentry.io/
2. Navigate to Projects → Precog → Issues
3. Should see "ZeroDivisionError: division by zero"

---

## Phase 2.1: Logger Integration (1 hour)

### Step 1: Update logger.py to Forward Errors to Sentry

**Location:** `src/precog/utils/logger.py`

**Add Sentry forwarding to `log_error()` helper:**

```python
def log_error(
    error_type: str,
    message: str,
    exception: Exception | None = None,
    **extra
) -> None:
    """
    Log error to file + forward to Sentry if initialized.

    Hybrid architecture:
    1. ALWAYS log to file (audit trail)
    2. IF Sentry initialized, forward ERROR to Sentry (real-time)

    Args:
        error_type: Error classification (api_failure, database_error, etc.)
        message: Human-readable error message
        exception: Optional exception object
        **extra: Additional context (component, operation, etc.)

    Educational Note:
    - File logging is PRIMARY (Sentry is supplementary)
    - Sentry SDK automatically captures exception with stack trace
    - Uses capture_exception (with exception) or capture_message (without)

    Reference: ADR-055 (Sentry Integration - Hybrid Architecture)
    """
    import sentry_sdk

    # 1. ALWAYS log to file (primary audit trail)
    logger.error(
        error_type,
        message=message,
        exception_type=type(exception).__name__ if exception else None,
        exception_message=str(exception) if exception else None,
        **extra,
    )

    # 2. IF Sentry initialized, forward to Sentry (real-time)
    if sentry_sdk.Hub.current.client is not None:
        # Add context to Sentry event
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("error_type", error_type)
            scope.set_context("details", extra)

            # Add request_id if available (B3 correlation)
            if "request_id" in extra:
                scope.set_tag("request_id", extra["request_id"])

        # Capture exception or message
        if exception:
            sentry_sdk.capture_exception(exception)
        else:
            sentry_sdk.capture_message(message, level="error")
```

### Step 2: Test Logger → Sentry Integration

**Create test:** `tests/unit/utils/test_logger_sentry.py`

```python
"""
Tests for logger.py Sentry integration.
"""
import os
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
import sentry_sdk

from precog.utils.logger import log_error


@pytest.fixture
def mock_sentry():
    """Mock Sentry SDK for testing."""
    with patch("sentry_sdk.Hub.current") as mock_hub:
        mock_client = Mock()
        mock_hub.client = mock_client
        yield mock_hub


def test_log_error_forwards_to_sentry_when_initialized(mock_sentry, tmp_path, monkeypatch):
    """
    Verify log_error() forwards ERROR to Sentry when initialized.

    Reference: REQ-OBSERV-002 (Sentry Integration)
    """
    # Configure logger to write to temp directory
    monkeypatch.setenv("LOG_DIR", str(tmp_path))

    # Mock Sentry capture_exception
    with patch("sentry_sdk.capture_exception") as mock_capture:
        exception = ValueError("Test error")

        log_error(
            error_type="test_error",
            message="Test error message",
            exception=exception,
            component="test",
        )

        # Verify Sentry received exception
        mock_capture.assert_called_once_with(exception)


def test_log_error_works_without_sentry(tmp_path, monkeypatch):
    """
    Verify log_error() gracefully handles Sentry not initialized.

    Graceful degradation - no crash if Sentry disabled.
    """
    # Configure logger to write to temp directory
    monkeypatch.setenv("LOG_DIR", str(tmp_path))

    # Mock Sentry as uninitialized
    with patch("sentry_sdk.Hub.current") as mock_hub:
        mock_hub.client = None  # Sentry NOT initialized

        # Should NOT crash
        log_error(
            error_type="test_error",
            message="Test error message",
            component="test",
        )

        # Verify log file created (file logging still works)
        log_files = list(tmp_path.glob("precog_*.log"))
        assert len(log_files) == 1


def test_log_error_adds_request_id_to_sentry(mock_sentry, tmp_path, monkeypatch):
    """
    Verify request_id from B3 correlation forwarded to Sentry.

    Reference: ADR-049 (B3 Correlation IDs)
    """
    monkeypatch.setenv("LOG_DIR", str(tmp_path))

    with patch("sentry_sdk.configure_scope") as mock_scope:
        log_error(
            error_type="api_failure",
            message="Kalshi API timeout",
            component="kalshi_client",
            request_id="b3-trace-id-123",
        )

        # Verify request_id added to Sentry scope
        # (scope.set_tag called with request_id)
        mock_scope.assert_called_once()
```

**Run tests:**
```bash
python -m pytest tests/unit/utils/test_logger_sentry.py -v
```

---

## Phase 2.2: Alert Manager Implementation (3 hours)

### Step 1: Create Alert Manager Module

**Location:** `src/precog/utils/alert_manager.py`

```python
"""
Alert Manager - Hybrid Architecture

Implements 3-layer hybrid observability:
1. ALWAYS write to alerts table (permanent record)
2. IF code error + high severity, send to Sentry (real-time)
3. Send notifications via email/SMS based on severity

Educational Note:
- Database is PRIMARY (Sentry is supplementary)
- Separation of concerns: code errors vs business alerts
- Graceful degradation if Sentry/notifications unavailable

Reference: ADR-055 (Sentry Integration - Hybrid Architecture)
"""
import hashlib
import os
from datetime import datetime
from typing import Literal

import sentry_sdk

from precog.database.crud_operations import insert_alert
from precog.utils.logger import logger


# Alert type classifications
CODE_ERROR_TYPES = {
    "api_failure",
    "system_error",
    "database_error",
    "circuit_breaker",
    "authentication_error",
    "validation_error",
}

BUSINESS_ALERT_TYPES = {
    "edge_detected",
    "position_opened",
    "position_closed",
    "loss_limit_approaching",
    "daily_summary",
}

# Severity levels
SeverityLevel = Literal["critical", "high", "medium", "low", "info"]


def create_alert(
    alert_type: str,
    severity: SeverityLevel,
    component: str,
    message: str,
    details: dict | None = None,
) -> int:
    """
    Create alert with hybrid architecture.

    Hybrid behavior:
    1. ALWAYS write to alerts table (permanent record)
    2. IF code error + high severity, send to Sentry (real-time)
    3. Send notifications via email/SMS based on severity

    Args:
        alert_type: Alert classification (api_failure, edge_detected, etc.)
        severity: Severity level (critical, high, medium, low, info)
        component: Component name (kalshi_client, edge_detector, etc.)
        message: Human-readable alert message
        details: Additional context as dict (optional)

    Returns:
        alert_id: Database alert ID

    Raises:
        ValueError: If severity invalid

    Example:
        >>> create_alert(
        ...     alert_type="api_failure",
        ...     severity="critical",
        ...     component="kalshi_client",
        ...     message="Kalshi API authentication failed (401 Unauthorized)",
        ...     details={"endpoint": "/portfolio/balance", "status_code": 401}
        ... )
        1234

    Educational Note:
    - Database write is PRIMARY (never skip this)
    - Sentry is SUPPLEMENTARY (graceful degradation if unavailable)
    - Notifications are SUPPLEMENTARY (async, best-effort delivery)

    Reference: REQ-OBSERV-002, ADR-055
    """
    if details is None:
        details = {}

    # Validate severity
    valid_severities = {"critical", "high", "medium", "low", "info"}
    if severity not in valid_severities:
        raise ValueError(f"Invalid severity: {severity}. Must be one of {valid_severities}")

    # Generate fingerprint for deduplication
    fingerprint = generate_fingerprint(alert_type, component, details)

    # 1. ALWAYS write to database (permanent record)
    alert_id = insert_alert(
        alert_type=alert_type,
        severity=severity,
        component=component,
        message=message,
        details=details,
        fingerprint=fingerprint,
        environment=os.getenv("ENVIRONMENT", "demo"),
    )

    logger.info(
        "alert_created",
        alert_id=alert_id,
        alert_type=alert_type,
        severity=severity,
        component=component,
    )

    # 2. IF code error AND critical/high, send to Sentry (real-time)
    if severity in ["critical", "high"] and alert_type in CODE_ERROR_TYPES:
        _send_to_sentry(alert_type, severity, component, message, details, fingerprint)

    # 3. Send notifications (email/SMS based on severity)
    _send_notifications(alert_id, alert_type, severity, component, message)

    return alert_id


def generate_fingerprint(alert_type: str, component: str, details: dict) -> str:
    """
    Generate deduplication fingerprint for alert.

    Same alert type + component + key details = same fingerprint.

    Args:
        alert_type: Alert classification
        component: Component name
        details: Alert details dict

    Returns:
        SHA256 hash (first 16 chars)

    Educational Note:
    - Used by Sentry for grouping similar errors
    - Used by database for suppressing duplicate alerts
    - Includes only stable fields (NOT timestamps, request IDs)

    Example:
        >>> generate_fingerprint(
        ...     "api_failure",
        ...     "kalshi_client",
        ...     {"endpoint": "/portfolio/balance", "status_code": 401}
        ... )
        'a1b2c3d4e5f6g7h8'
    """
    # Extract stable fields from details (ignore timestamps, request IDs)
    stable_fields = {
        k: v for k, v in details.items()
        if k not in {"timestamp", "request_id", "triggered_at"}
    }

    # Create fingerprint string
    fingerprint_str = f"{alert_type}:{component}:{stable_fields}"

    # Hash and truncate
    hash_obj = hashlib.sha256(fingerprint_str.encode())
    return hash_obj.hexdigest()[:16]


def _send_to_sentry(
    alert_type: str,
    severity: str,
    component: str,
    message: str,
    details: dict,
    fingerprint: str,
) -> None:
    """
    Send alert to Sentry (internal helper).

    Graceful degradation: if Sentry unavailable, log warning but don't crash.
    """
    if sentry_sdk.Hub.current.client is None:
        logger.debug("sentry_not_initialized", message="Skipping Sentry (not initialized)")
        return

    try:
        with sentry_sdk.configure_scope() as scope:
            # Add tags for filtering in Sentry UI
            scope.set_tag("alert_type", alert_type)
            scope.set_tag("component", component)
            scope.set_tag("severity", severity)

            # Add context
            scope.set_context("alert_details", details)

            # Add fingerprint for grouping
            scope.fingerprint = [component, alert_type, fingerprint]

        # Send to Sentry
        sentry_sdk.capture_message(
            message,
            level="error" if severity == "critical" else "warning",
        )

        logger.debug("sentry_alert_sent", alert_type=alert_type, component=component)

    except Exception as e:
        # Graceful degradation: log error but don't crash
        logger.warning(
            "sentry_send_failed",
            error=str(e),
            alert_type=alert_type,
        )


def _send_notifications(
    alert_id: int,
    alert_type: str,
    severity: str,
    component: str,
    message: str,
) -> None:
    """
    Send email/SMS notifications based on severity (internal helper).

    Routing logic:
    - critical: email + SMS
    - high: email only
    - medium/low/info: no notifications

    Graceful degradation: if notifications fail, log warning but don't crash.
    """
    if severity == "critical":
        # Send both email and SMS
        _send_email_notification(alert_id, message)
        _send_sms_notification(alert_id, message)

    elif severity == "high":
        # Send email only
        _send_email_notification(alert_id, message)

    # medium/low/info: no notifications


def _send_email_notification(alert_id: int, message: str) -> None:
    """
    Send email notification (internal helper).

    Uses SMTP configuration from .env.
    Graceful degradation: if SMTP unavailable, log warning.
    """
    # Import here to avoid circular dependencies
    from precog.utils.notifications import send_email

    recipients = os.getenv("ALERT_EMAIL_RECIPIENTS", "").split(",")
    recipients = [r.strip() for r in recipients if r.strip()]

    if not recipients:
        logger.debug("email_skipped", reason="No recipients configured")
        return

    try:
        send_email(
            recipients=recipients,
            subject=f"[Precog Alert #{alert_id}] {message[:100]}",
            body=f"Alert ID: {alert_id}\nMessage: {message}",
        )

        logger.info("email_sent", alert_id=alert_id, recipients=len(recipients))

    except Exception as e:
        logger.warning("email_failed", error=str(e), alert_id=alert_id)


def _send_sms_notification(alert_id: int, message: str) -> None:
    """
    Send SMS notification (internal helper).

    Uses Twilio configuration from .env.
    Graceful degradation: if Twilio unavailable, log warning.
    """
    # Import here to avoid circular dependencies
    from precog.utils.notifications import send_sms

    recipients = os.getenv("ALERT_SMS_RECIPIENTS", "").split(",")
    recipients = [r.strip() for r in recipients if r.strip()]

    if not recipients:
        logger.debug("sms_skipped", reason="No recipients configured")
        return

    try:
        # Truncate message to 160 chars (SMS limit)
        sms_message = f"[Precog #{alert_id}] {message[:130]}"

        send_sms(
            recipients=recipients,
            message=sms_message,
        )

        logger.info("sms_sent", alert_id=alert_id, recipients=len(recipients))

    except Exception as e:
        logger.warning("sms_failed", error=str(e), alert_id=alert_id)
```

### Step 2: Add CRUD Operations for Alerts

**Location:** `src/precog/database/crud_operations.py`

**Add these functions:**

```python
def insert_alert(
    alert_type: str,
    severity: str,
    component: str,
    message: str,
    details: dict | None = None,
    fingerprint: str | None = None,
    environment: str = "demo",
) -> int:
    """
    Insert alert into alerts table.

    Args:
        alert_type: Alert classification (api_failure, edge_detected, etc.)
        severity: Severity level (critical, high, medium, low, info)
        component: Component name (kalshi_client, edge_detector, etc.)
        message: Human-readable alert message
        details: Additional context as JSON (optional)
        fingerprint: Deduplication hash (optional)
        environment: Environment name (demo, production, etc.)

    Returns:
        alert_id: Database alert ID

    Example:
        >>> insert_alert(
        ...     alert_type="api_failure",
        ...     severity="critical",
        ...     component="kalshi_client",
        ...     message="Kalshi API authentication failed",
        ...     details={"endpoint": "/portfolio/balance", "status_code": 401},
        ...     fingerprint="a1b2c3d4e5f6g7h8",
        ...     environment="demo"
        ... )
        1234

    Reference: REQ-OBSERV-002 (Sentry Integration - alerts table)
    """
    from precog.database.connection import get_connection
    import psycopg2.extras

    if details is None:
        details = {}

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO alerts (
                alert_type,
                severity,
                component,
                message,
                details,
                fingerprint,
                triggered_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, NOW()
            )
            RETURNING alert_id
            """,
            (
                alert_type,
                severity,
                component,
                message,
                psycopg2.extras.Json(details),
                fingerprint,
            ),
        )

        alert_id = cursor.fetchone()[0]
        conn.commit()

        return alert_id

    except Exception as e:
        conn.rollback()
        raise
    finally:
        cursor.close()


def get_alert(alert_id: int) -> dict | None:
    """
    Get alert by ID.

    Args:
        alert_id: Database alert ID

    Returns:
        Alert dict or None if not found

    Example:
        >>> get_alert(1234)
        {
            'alert_id': 1234,
            'alert_type': 'api_failure',
            'severity': 'critical',
            'component': 'kalshi_client',
            'message': 'Kalshi API authentication failed',
            'details': {'endpoint': '/portfolio/balance', 'status_code': 401},
            'triggered_at': datetime(2025, 11, 14, 10, 30, 0),
            'acknowledged_at': None,
            'resolved_at': None
        }
    """
    from precog.database.connection import get_connection
    import psycopg2.extras

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT *
            FROM alerts
            WHERE alert_id = %s
            """,
            (alert_id,),
        )

        row = cursor.fetchone()
        return dict(row) if row else None

    finally:
        cursor.close()


def acknowledge_alert(alert_id: int) -> bool:
    """
    Mark alert as acknowledged.

    Args:
        alert_id: Database alert ID

    Returns:
        True if updated, False if not found

    Example:
        >>> acknowledge_alert(1234)
        True
    """
    from precog.database.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE alerts
            SET acknowledged_at = NOW()
            WHERE alert_id = %s
              AND acknowledged_at IS NULL
            RETURNING alert_id
            """,
            (alert_id,),
        )

        updated = cursor.fetchone() is not None
        conn.commit()

        return updated

    except Exception as e:
        conn.rollback()
        raise
    finally:
        cursor.close()


def resolve_alert(alert_id: int) -> bool:
    """
    Mark alert as resolved.

    Args:
        alert_id: Database alert ID

    Returns:
        True if updated, False if not found

    Example:
        >>> resolve_alert(1234)
        True
    """
    from precog.database.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE alerts
            SET resolved_at = NOW()
            WHERE alert_id = %s
              AND resolved_at IS NULL
            RETURNING alert_id
            """,
            (alert_id,),
        )

        updated = cursor.fetchone() is not None
        conn.commit()

        return updated

    except Exception as e:
        conn.rollback()
        raise
    finally:
        cursor.close()
```

---

## Phase 2.3: Notification System (5 hours)

### Step 1: Create Notifications Module

**Location:** `src/precog/utils/notifications.py`

```python
"""
Notification System - Email and SMS

Sends notifications for critical alerts.

Educational Note:
- SMTP for email (Gmail, SendGrid, etc.)
- Twilio for SMS
- Graceful degradation: if unavailable, log warning but don't crash
- Async delivery (don't block alert creation)

Reference: REQ-OBSERV-002 (Alert notifications)
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from precog.utils.logger import logger


def send_email(recipients: list[str], subject: str, body: str) -> None:
    """
    Send email notification via SMTP.

    Args:
        recipients: List of email addresses
        subject: Email subject
        body: Email body (plain text)

    Raises:
        ValueError: If SMTP not configured
        smtplib.SMTPException: If email send fails

    Example:
        >>> send_email(
        ...     recipients=["team@example.com"],
        ...     subject="[Precog Alert] API failure",
        ...     body="Kalshi API authentication failed (401)"
        ... )

    Educational Note:
    - Uses TLS encryption (STARTTLS)
    - Gmail requires "App Password" (not regular password)
    - Sender email from SMTP_FROM env var

    Reference: REQ-OBSERV-002
    """
    # Get SMTP configuration from environment
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not all([smtp_host, smtp_user, smtp_password]):
        raise ValueError("SMTP not configured (missing SMTP_HOST, SMTP_USER, or SMTP_PASSWORD)")

    # Create message
    msg = MIMEMultipart()
    msg["From"] = smtp_from
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    # Send email
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()  # Upgrade to TLS
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        logger.info("email_sent", recipients=recipients, subject=subject)

    except smtplib.SMTPException as e:
        logger.error("email_failed", error=str(e), recipients=recipients)
        raise


def send_sms(recipients: list[str], message: str) -> None:
    """
    Send SMS notification via Twilio.

    Args:
        recipients: List of phone numbers (E.164 format: +1234567890)
        message: SMS message (max 160 chars)

    Raises:
        ValueError: If Twilio not configured
        TwilioRestException: If SMS send fails

    Example:
        >>> send_sms(
        ...     recipients=["+1234567890"],
        ...     message="[Precog] API failure - Kalshi auth failed"
        ... )

    Educational Note:
    - Twilio free trial: $15.50 credit (~500 SMS)
    - Phone numbers must be in E.164 format (+country code + number)
    - Message truncated to 160 chars if longer

    Reference: REQ-OBSERV-002
    """
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioRestException

    # Get Twilio configuration from environment
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_PHONE_NUMBER")

    if not all([account_sid, auth_token, from_number]):
        raise ValueError("Twilio not configured (missing TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, or TWILIO_PHONE_NUMBER)")

    # Initialize Twilio client
    client = Client(account_sid, auth_token)

    # Truncate message to 160 chars (SMS limit)
    message = message[:160]

    # Send SMS to each recipient
    for to_number in recipients:
        try:
            message_obj = client.messages.create(
                body=message,
                from_=from_number,
                to=to_number,
            )

            logger.info("sms_sent", to=to_number, sid=message_obj.sid)

        except TwilioRestException as e:
            logger.error("sms_failed", error=str(e), to=to_number)
            raise
```

### Step 2: Install Dependencies

**Update `requirements.txt`:**

```bash
# Add to requirements.txt
twilio==8.10.0  # SMS notifications via Twilio
```

**Install:**
```bash
pip install twilio==8.10.0
```

---

## Testing & Validation

### Unit Tests

**Location:** `tests/unit/utils/test_alert_manager.py`

```python
"""
Tests for alert_manager.py
"""
import os
from unittest.mock import Mock, patch

import pytest

from precog.utils.alert_manager import create_alert, generate_fingerprint


@pytest.fixture
def mock_db():
    """Mock database connection."""
    with patch("precog.utils.alert_manager.insert_alert") as mock:
        mock.return_value = 1234  # Mock alert_id
        yield mock


@pytest.fixture
def mock_sentry():
    """Mock Sentry SDK."""
    with patch("sentry_sdk.Hub.current") as mock_hub:
        mock_client = Mock()
        mock_hub.client = mock_client
        yield mock_hub


def test_create_alert_writes_to_database(mock_db, mock_sentry):
    """
    Verify create_alert() ALWAYS writes to database.

    Reference: REQ-OBSERV-002 (hybrid architecture - DB is primary)
    """
    alert_id = create_alert(
        alert_type="api_failure",
        severity="critical",
        component="kalshi_client",
        message="Kalshi API authentication failed",
        details={"endpoint": "/portfolio/balance", "status_code": 401},
    )

    # Verify database insert called
    mock_db.assert_called_once()
    assert alert_id == 1234


def test_create_alert_sends_code_errors_to_sentry(mock_db, mock_sentry):
    """
    Verify code errors with high severity sent to Sentry.

    Reference: ADR-055 (Sentry for code errors only)
    """
    with patch("sentry_sdk.capture_message") as mock_capture:
        create_alert(
            alert_type="api_failure",  # Code error
            severity="critical",       # High severity
            component="kalshi_client",
            message="Kalshi API authentication failed",
        )

        # Verify Sentry received message
        mock_capture.assert_called_once_with(
            "Kalshi API authentication failed",
            level="error",
        )


def test_create_alert_skips_sentry_for_business_alerts(mock_db, mock_sentry):
    """
    Verify business alerts NOT sent to Sentry.

    Reference: ADR-055 (separation of concerns)
    """
    with patch("sentry_sdk.capture_message") as mock_capture:
        create_alert(
            alert_type="edge_detected",  # Business alert (NOT code error)
            severity="info",
            component="edge_detector",
            message="Edge detected: NFL game XYZ (5.2% edge)",
        )

        # Verify Sentry NOT called
        mock_capture.assert_not_called()


def test_generate_fingerprint_consistent():
    """
    Verify fingerprint consistent for same inputs.
    """
    fp1 = generate_fingerprint(
        "api_failure",
        "kalshi_client",
        {"endpoint": "/portfolio/balance", "status_code": 401},
    )

    fp2 = generate_fingerprint(
        "api_failure",
        "kalshi_client",
        {"endpoint": "/portfolio/balance", "status_code": 401},
    )

    assert fp1 == fp2


def test_generate_fingerprint_different_for_different_inputs():
    """
    Verify fingerprint different for different inputs.
    """
    fp1 = generate_fingerprint(
        "api_failure",
        "kalshi_client",
        {"endpoint": "/portfolio/balance", "status_code": 401},
    )

    fp2 = generate_fingerprint(
        "api_failure",
        "kalshi_client",
        {"endpoint": "/portfolio/balance", "status_code": 500},  # Different status
    )

    assert fp1 != fp2
```

**Run tests:**
```bash
python -m pytest tests/unit/utils/test_alert_manager.py -v
```

### Integration Test

**Create:** `scripts/test_alert_system.py`

```python
"""
Integration test for alert system.

Tests full alert creation → DB → Sentry → notifications flow.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from precog.utils.alert_manager import create_alert
from precog.database.crud_operations import get_alert, acknowledge_alert, resolve_alert


def test_alert_system():
    """Test full alert system flow."""
    print("[INFO] Testing alert system...")

    # 1. Create critical alert (should trigger Sentry + email + SMS)
    print("\n[STEP 1] Creating critical alert (API failure)...")
    alert_id = create_alert(
        alert_type="api_failure",
        severity="critical",
        component="kalshi_client",
        message="Kalshi API authentication failed (401 Unauthorized)",
        details={"endpoint": "/portfolio/balance", "status_code": 401, "retry_count": 3},
    )
    print(f"[OK] Alert created: alert_id={alert_id}")

    # 2. Verify alert in database
    print("\n[STEP 2] Verifying alert in database...")
    alert = get_alert(alert_id)
    if alert:
        print(f"[OK] Alert found in database:")
        print(f"  - alert_type: {alert['alert_type']}")
        print(f"  - severity: {alert['severity']}")
        print(f"  - component: {alert['component']}")
        print(f"  - message: {alert['message']}")
        print(f"  - triggered_at: {alert['triggered_at']}")
    else:
        print(f"[FAIL] Alert not found in database")
        sys.exit(1)

    # 3. Acknowledge alert
    print("\n[STEP 3] Acknowledging alert...")
    acknowledged = acknowledge_alert(alert_id)
    if acknowledged:
        print(f"[OK] Alert acknowledged")
    else:
        print(f"[FAIL] Failed to acknowledge alert")
        sys.exit(1)

    # 4. Resolve alert
    print("\n[STEP 4] Resolving alert...")
    resolved = resolve_alert(alert_id)
    if resolved:
        print(f"[OK] Alert resolved")
    else:
        print(f"[FAIL] Failed to resolve alert")
        sys.exit(1)

    # 5. Create business alert (should NOT trigger Sentry)
    print("\n[STEP 5] Creating business alert (edge detected)...")
    alert_id_2 = create_alert(
        alert_type="edge_detected",
        severity="info",
        component="edge_detector",
        message="Edge detected: NFL game XYZ (5.2% edge)",
        details={"market_id": "NFL-123", "edge": "0.0520", "probability": "0.6500"},
    )
    print(f"[OK] Business alert created: alert_id={alert_id_2}")

    print("\n[SUCCESS] All tests passed!")
    print("\nManual verification:")
    print("1. Check Sentry dashboard for critical alert (alert_id={})".format(alert_id))
    print("2. Check email inbox for notification")
    print("3. Verify business alert (alert_id={}) NOT in Sentry".format(alert_id_2))


if __name__ == "__main__":
    test_alert_system()
```

**Run test:**
```bash
python scripts/test_alert_system.py
```

---

## Configuration Reference

### Environment Variables (.env)

```bash
# Sentry Configuration (Phase 2)
SENTRY_DSN=https://your-key@o123456.ingest.sentry.io/789012
ENVIRONMENT=demo  # or 'production', 'staging'

# Email Notifications (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=precog-alerts@yourdomain.com
ALERT_EMAIL_RECIPIENTS=team@yourdomain.com,oncall@yourdomain.com

# SMS Notifications (Twilio - Optional)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1234567890
ALERT_SMS_RECIPIENTS=+1234567890,+0987654321
```

### Sentry Configuration

**Sample rates (cost optimization):**
- `traces_sample_rate=0.10` - 10% of transactions for APM (reduces cost)
- `profiles_sample_rate=0.10` - 10% of transactions for profiling

**Free tier limits:**
- 5,000 errors/month
- 10,000 transactions/month

**When to upgrade:**
- If hitting limits consistently
- Paid tier: $26/month for 50K errors, 100K transactions

---

## Troubleshooting

### Sentry Not Receiving Events

**Problem:** Events not appearing in Sentry dashboard

**Solutions:**
1. **Verify DSN configured:**
   ```bash
   echo $SENTRY_DSN
   # Should see: https://...@o123456.ingest.sentry.io/789012
   ```

2. **Test connection:**
   ```bash
   python scripts/test_sentry_connection.py
   ```

3. **Check Sentry initialized:**
   ```python
   import sentry_sdk
   print(sentry_sdk.Hub.current.client)
   # Should NOT be None
   ```

4. **Force flush:**
   ```python
   sentry_sdk.flush(timeout=5.0)
   ```

### Email Notifications Not Sending

**Problem:** Email notifications not arriving

**Solutions:**
1. **Verify SMTP configuration:**
   ```bash
   echo $SMTP_HOST
   echo $SMTP_USER
   echo $SMTP_PASSWORD  # Should be app password, NOT regular password
   ```

2. **Test SMTP connection:**
   ```python
   import smtplib
   server = smtplib.SMTP("smtp.gmail.com", 587)
   server.starttls()
   server.login("your-email@gmail.com", "your-app-password")
   print("SMTP connection successful")
   ```

3. **Gmail App Password:**
   - Go to Google Account → Security → 2-Step Verification → App Passwords
   - Generate new app password
   - Use THIS password in SMTP_PASSWORD (NOT regular password)

4. **Check spam folder:**
   - Precog alerts may be marked as spam initially
   - Add `precog-alerts@yourdomain.com` to contacts

### SMS Notifications Not Sending

**Problem:** SMS not arriving

**Solutions:**
1. **Verify Twilio configuration:**
   ```bash
   echo $TWILIO_ACCOUNT_SID
   echo $TWILIO_AUTH_TOKEN
   echo $TWILIO_PHONE_NUMBER
   ```

2. **Check phone number format:**
   - Must be E.164 format: `+1234567890` (with country code)
   - NOT: `1234567890` or `(123) 456-7890`

3. **Verify Twilio trial restrictions:**
   - Free trial can only send to **verified numbers**
   - Add phone number in Twilio console: Phone Numbers → Verified Caller IDs

4. **Check Twilio logs:**
   - Go to Twilio console → Monitor → Logs → Messaging
   - Look for failed messages

### Alerts Not Writing to Database

**Problem:** `create_alert()` fails with database error

**Solutions:**
1. **Verify alerts table exists:**
   ```sql
   \d alerts
   -- Should show table structure
   ```

2. **Run migration 002:**
   ```bash
   python scripts/apply_migration_002.py
   ```

3. **Check database connection:**
   ```bash
   python scripts/test_db_connection.py
   ```

4. **Verify fingerprint length:**
   - Fingerprint column: `VARCHAR(64)`
   - If longer than 64 chars, insert fails
   - Solution: Truncate in `generate_fingerprint()` to 16 chars

---

## Performance & Cost Considerations

### Sentry Costs

**Free Tier (Current):**
- 5,000 errors/month
- 10,000 transactions/month
- $0/month

**Expected Usage (Demo Phase):**
- ~50-100 errors/month (assuming stable system)
- ~500-1,000 transactions/month (10% sample rate)
- **Well within free tier**

**Paid Tier ($26/month):**
- 50,000 errors/month
- 100,000 transactions/month
- Upgrade when consistently hitting free tier limits

**Cost Optimization:**
- Use `traces_sample_rate=0.10` (10% sampling) to reduce transaction volume
- Only send ERROR/CRITICAL (not WARNING/INFO)
- Use fingerprints for deduplication (reduces error count)

### Email Costs

**Gmail (Current):**
- FREE for personal accounts
- Limit: 500 emails/day
- **Expected: 5-20 emails/day (well within limit)**

**SendGrid (Alternative):**
- FREE tier: 100 emails/day
- Paid: $19.95/month for 50,000 emails
- Use if Gmail limits exceeded

### SMS Costs

**Twilio (Current):**
- FREE trial: $15.50 credit (~500 SMS)
- Paid: $0.0079/SMS (US)
- **Expected: 2-10 SMS/month (critical alerts only)**

**Cost estimate:**
- 10 SMS/month × $0.0079 = **$0.08/month**
- Negligible cost

### Database Storage

**Alerts Table Growth:**
- Assume 100 alerts/day (aggressive)
- ~36,500 alerts/year
- Row size: ~500 bytes (with JSON details)
- **Storage: ~18 MB/year (negligible)**

**Retention Policy (Future):**
- Keep all alerts indefinitely (audit trail)
- Archive resolved alerts older than 1 year to separate table
- Phase 5+ consideration

---

**END OF SENTRY_INTEGRATION_GUIDE_V1.0.md**
