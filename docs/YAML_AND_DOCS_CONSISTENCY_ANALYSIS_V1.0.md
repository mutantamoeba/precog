# YAML and Documentation Consistency Analysis V1.0

**Created:** 2025-10-23
**Phase:** 1 (Foundation Completion)
**Purpose:** Comprehensive analysis of YAML files and documentation for consistency, gaps, and alerts/notification requirements

---

## Executive Summary

**Critical Findings:**
1. ✅ **Alerts section EXISTS** in trading.yaml (lines 367-391) but alerts table does NOT exist
2. ❌ **Email/SMS referenced** but not implemented anywhere
3. ❌ **Methods table** missing from YAMLs (correctly - it's Phase 4-5)
4. ⚠️ **Logging inconsistency** - multiple places reference different alert channels
5. ✅ **YAML versioning** well-implemented for models/strategies
6. ❌ **Notification channels** undefined (email, SMS, Slack, webhook)

---

## PART 1: Alerts & Notifications in YAML Files

### 1.1 trading.yaml - Alerts Section (Lines 367-391)

**CURRENT STATE:**
```yaml
alerts:
  # Alert on circuit breaker trips
  on_circuit_breaker: true

  # Alert on large losses
  on_loss_threshold:
    enabled: true
    threshold_dollars: 100.00

  # Alert on large gains
  on_gain_threshold:
    enabled: true
    threshold_dollars: 500.00

  # Alert on API issues
  on_api_failure: true

  # Alert on system errors
  on_system_error: true
```

**COMMENT (Line 369):**
> "When to send notifications (email, SMS, etc.)
> Configured later in system.yaml"

**ISSUES:**
- References system.yaml for configuration
- Mentions email, SMS but doesn't specify HOW
- No actual notification channel config in system.yaml
- No alerts table exists to LOG these alerts
- Boolean flags but no severity levels
- No acknowledgement tracking

**NEEDED:**
1. Alerts table to log all alerts
2. Notification channels config in system.yaml
3. Severity levels (critical, high, medium, low)
4. Channel routing rules (e.g., critical → email + SMS, medium → file only)

### 1.2 system.yaml - Logging Section (Lines 337-365)

**CURRENT STATE:**
```yaml
logging:
  level: INFO
  outputs:
    - console
    - file
  file:
    path: "logs/trading.log"
    rotation: daily
    retention_days: 30
  log_trades: true
  log_signals: true
  log_edges: true
  log_market_updates: false
  log_api_calls: false
```

**MISSING:**
- No email logging output
- No SMS logging output
- No Slack/webhook outputs
- No alert-specific logging
- No notification configuration

**NEEDED:**
```yaml
logging:
  # ... existing ...

  # Alert channels
  alert_outputs:
    console: true
    file: true
    email: true      # NEW
    sms: true        # NEW
    slack: false     # NEW
    webhook: false   # NEW

  # Notification settings
  notifications:
    email:
      enabled: true
      smtp_host_env: "SMTP_HOST"
      smtp_port_env: "SMTP_PORT"
      smtp_user_env: "SMTP_USER"
      smtp_password_env: "SMTP_PASSWORD"
      from_address_env: "ALERT_FROM_EMAIL"
      to_addresses_env: "ALERT_TO_EMAILS"  # Comma-separated

    sms:
      enabled: true
      provider: "twilio"  # or "aws_sns"
      twilio_account_sid_env: "TWILIO_ACCOUNT_SID"
      twilio_auth_token_env: "TWILIO_AUTH_TOKEN"
      twilio_from_number_env: "TWILIO_FROM_NUMBER"
      to_numbers_env: "ALERT_TO_PHONE_NUMBERS"  # Comma-separated

    slack:
      enabled: false
      webhook_url_env: "SLACK_WEBHOOK_URL"
      channel_env: "SLACK_ALERT_CHANNEL"

    webhook:
      enabled: false
      url_env: "CUSTOM_WEBHOOK_URL"
      method: "POST"
      headers_env: "CUSTOM_WEBHOOK_HEADERS"

  # Alert routing by severity
  alert_routing:
    critical:
      channels: ["console", "file", "email", "sms"]
      immediate: true
    high:
      channels: ["console", "file", "email"]
      immediate: true
    medium:
      channels: ["console", "file"]
      immediate: false
    low:
      channels: ["file"]
      immediate: false
```

### 1.3 position_management.yaml - Alerts (Line 514)

**CURRENT STATE:**
```yaml
correlation:
  actions:
    alert_on_portfolio_correlation:
      enabled: true
      threshold: 0.70  # Alert if avg correlation > 70%
```

**ISSUE:**
- Says "alert" but doesn't specify HOW
- No connection to alerts table
- No severity level
- No channel specification

### 1.4 data_sources.yaml - Monitoring Section (Lines 699-713)

**CURRENT STATE:**
```yaml
monitoring:
  health_checks:
    enabled: true
    interval_seconds: 60
    alert_on_failure: true  # ← HOW?

  usage_tracking:
    enabled: true
    track_by_source: true
    track_rate_limits: true
    alert_at_percent: 80  # ← HOW?
```

**ISSUE:**
- `alert_on_failure` and `alert_at_percent` but no alert mechanism defined
- No connection to alerts table
- No notification channels

### 1.5 probability_models.yaml - Monitoring (Lines 590-622)

**CURRENT STATE:**
```yaml
monitoring:
  degradation_alerts:
    enabled: true
    lookback_window_days: 30
    min_performance_pct: 0.85  # Alert if < 85% of historical
```

**ISSUE:**
- Alerts mentioned but no implementation
- No severity, channels, or table logging

---

## PART 2: Methods Table References

### 2.1 YAML Files

**SEARCHED FOR:** "method_id", "methods table", "method table", "trading method"

**FINDINGS:**
- ❌ **NO references** to methods table in any YAML file
- ✅ **CORRECT** - Methods are Phase 4-5, stored in database
- ✅ **CORRECT** - Methods created via API, not YAML config

**REASONING:**
Per ADR-021, methods combine:
- strategy_id (from strategies table)
- model_id (from probability_models table)
- position_mgmt_config (JSONB)
- risk_config (JSONB)
- execution_config (JSONB)
- sport_config (JSONB)

All of these have YAML equivalents:
- trade_strategies.yaml → strategies
- probability_models.yaml → models
- position_management.yaml → position mgmt
- trading.yaml → risk
- markets.yaml → execution/sport

But methods table BUNDLES these into versioned, immutable combinations stored in database.

**CONCLUSION:**
- No YAML updates needed for methods
- Methods created programmatically in Phase 4-5
- OPTIONAL: Could add method_templates.yaml for template definitions

### 2.2 Database Schema

**ADR-021 specifies methods table needs:**
- method_id column added to `trades` table
- method_id column added to `edges` table (if edges table exists)
- Both as NULLABLE FKs (backward compatible)

**CURRENT SCHEMA:**
- trades table: NO method_id column
- edges table: Check if exists, likely NO method_id column

**NEEDED:**
```sql
ALTER TABLE trades
ADD COLUMN method_id INT REFERENCES methods(method_id);

-- If edges table exists:
ALTER TABLE edges
ADD COLUMN method_id INT REFERENCES methods(method_id);
```

---

## PART 3: Documentation Consistency Gaps

### 3.1 Missing Tables in MASTER_REQUIREMENTS

**From earlier audit:**
1. platforms
2. settlements
3. account_balance
4. config_overrides
5. circuit_breaker_events
6. system_health
7. **methods** (placeholder needed)
8. **method_templates** (placeholder needed)
9. **alerts** (if we add it)

### 3.2 Missing from DATABASE_SCHEMA_SUMMARY

1. methods table (placeholder)
2. method_templates table (placeholder)
3. alerts table (if added)
4. method_id columns on trades/edges
5. matrix_name, description columns on probability_matrices

### 3.3 YAML → Documentation Gaps

**Issue:** YAMLs reference features that aren't documented

**Examples:**
1. trading.yaml mentions "email, SMS" → No email/SMS docs
2. data_sources.yaml has "alert_on_failure" → No alert system docs
3. position_management.yaml has alert routing → Not documented
4. All YAMLs have "enabled: false" features → No Phase tracking

**NEEDED:**
- NOTIFICATION_SYSTEM_GUIDE.md
- ALERTS_AND_MONITORING_GUIDE.md
- PHASE_FEATURE_MATRIX.md (which features in which phases)

---

## PART 4: Email & SMS Implementation Requirements

### 4.1 Email Support

**Libraries Needed:**
```python
# Python standard library
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
```

**Configuration (add to system.yaml):**
```yaml
notifications:
  email:
    enabled: true
    provider: "smtp"  # or "sendgrid", "mailgun"

    # SMTP settings (Gmail, Outlook, custom)
    smtp:
      host_env: "SMTP_HOST"          # smtp.gmail.com
      port_env: "SMTP_PORT"          # 587 (TLS) or 465 (SSL)
      use_tls: true
      username_env: "SMTP_USERNAME"
      password_env: "SMTP_PASSWORD"
      from_address_env: "ALERT_FROM_EMAIL"

    # Recipients
    recipients:
      critical_env: "CRITICAL_ALERT_EMAILS"
      high_env: "HIGH_ALERT_EMAILS"
      medium_env: "MEDIUM_ALERT_EMAILS"
      default_env: "DEFAULT_ALERT_EMAILS"

    # Email formatting
    subject_prefix: "[PRECOG ALERT]"
    include_html: true
    include_plaintext: true
```

**Implementation File:**
```python
# utils/notification_manager.py

def send_email_alert(
    severity: str,
    alert_type: str,
    message: str,
    details: Dict = None
):
    """Send email alert via SMTP."""
    pass
```

### 4.2 SMS Support

**Options:**
1. **Twilio** (recommended - $1/month + $0.0079/SMS)
2. **AWS SNS** (pay-per-use, ~$0.00645/SMS)
3. **Vonage** (formerly Nexmo)

**Configuration (add to system.yaml):**
```yaml
notifications:
  sms:
    enabled: true
    provider: "twilio"  # or "aws_sns"

    # Twilio settings
    twilio:
      account_sid_env: "TWILIO_ACCOUNT_SID"
      auth_token_env: "TWILIO_AUTH_TOKEN"
      from_number_env: "TWILIO_FROM_NUMBER"

    # Recipients by severity
    recipients:
      critical_env: "CRITICAL_ALERT_PHONE_NUMBERS"  # +15551234567
      high_env: "HIGH_ALERT_PHONE_NUMBERS"

    # Rate limiting (don't spam yourself!)
    rate_limit:
      max_per_hour: 5
      max_per_day: 20
      cooldown_between_sms_seconds: 300  # 5 min minimum between SMS
```

**Implementation:**
```python
# utils/notification_manager.py

from twilio.rest import Client

def send_sms_alert(
    severity: str,
    alert_type: str,
    message: str,
    phone_number: str
):
    """Send SMS alert via Twilio."""
    client = Client(account_sid, auth_token)
    client.messages.create(
        body=f"[{severity.upper()}] {alert_type}: {message}",
        from_=twilio_from_number,
        to=phone_number
    )
```

### 4.3 Slack Support (Bonus)

**Configuration:**
```yaml
notifications:
  slack:
    enabled: false
    webhook_url_env: "SLACK_WEBHOOK_URL"
    channel_env: "SLACK_ALERT_CHANNEL"  # #trading-alerts
    mention_on_critical: true
    user_to_mention_env: "SLACK_USER_ID"  # @username
```

---

## PART 5: Alerts Table Schema (Final Proposal)

```sql
CREATE TABLE alerts (
    -- Identity
    alert_id SERIAL PRIMARY KEY,
    alert_uuid UUID DEFAULT gen_random_uuid() UNIQUE,

    -- Classification
    alert_type VARCHAR NOT NULL,        -- 'circuit_breaker', 'api_failure', 'loss_threshold'
    severity VARCHAR NOT NULL,          -- 'critical', 'high', 'medium', 'low'
    category VARCHAR,                   -- 'risk', 'system', 'trading', 'data'
    component VARCHAR NOT NULL,         -- 'kalshi_api', 'edge_detector', 'position_manager'

    -- Message
    message TEXT NOT NULL,              -- Human-readable alert message
    details JSONB,                      -- Additional context (stack trace, metrics, etc.)

    -- Source tracking
    source_table VARCHAR,               -- 'trades', 'circuit_breaker_events', 'system_health'
    source_id INT,                      -- FK to source table record

    -- Timestamps
    triggered_at TIMESTAMP DEFAULT NOW() NOT NULL,
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP,

    -- Acknowledgement
    acknowledged_by VARCHAR,            -- Username or system
    acknowledged_notes TEXT,
    resolved_by VARCHAR,
    resolved_notes TEXT,
    resolution_action VARCHAR,          -- 'fixed', 'false_positive', 'ignored', 'escalated'

    -- Notification tracking
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_channels JSONB,        -- {'email': true, 'sms': true, 'slack': false}
    notification_sent_at TIMESTAMP,
    notification_attempts INT DEFAULT 0,
    notification_errors JSONB,          -- Track delivery failures

    -- Deduplication
    fingerprint VARCHAR(64),            -- MD5 hash for detecting duplicates
    suppressed BOOLEAN DEFAULT FALSE,   -- Rate-limited/suppressed duplicate

    -- Metadata
    environment VARCHAR,                -- 'demo', 'prod'
    tags JSONB,                         -- Flexible tagging

    -- Constraints
    CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    CHECK (resolution_action IS NULL OR resolution_action IN ('fixed', 'false_positive', 'ignored', 'escalated'))
);

-- Indexes
CREATE INDEX idx_alerts_type ON alerts(alert_type);
CREATE INDEX idx_alerts_severity ON alerts(severity);
CREATE INDEX idx_alerts_component ON alerts(component);
CREATE INDEX idx_alerts_triggered ON alerts(triggered_at DESC);
CREATE INDEX idx_alerts_unresolved ON alerts(resolved_at) WHERE resolved_at IS NULL;
CREATE INDEX idx_alerts_fingerprint ON alerts(fingerprint) WHERE fingerprint IS NOT NULL;
CREATE INDEX idx_alerts_environment ON alerts(environment);

-- Comments
COMMENT ON TABLE alerts IS 'Centralized alert/notification logging with acknowledgement tracking';
COMMENT ON COLUMN alerts.fingerprint IS 'MD5 hash of (alert_type + component + key details) for deduplication';
COMMENT ON COLUMN alerts.suppressed IS 'True if alert was suppressed due to rate limiting or deduplication';
COMMENT ON COLUMN alerts.notification_channels IS 'JSONB tracking which channels were notified: {email: true, sms: false}';
```

---

## PART 6: Required Code Updates

### 6.1 New Files Needed

1. **utils/notification_manager.py**
   - send_email_alert()
   - send_sms_alert()
   - send_slack_alert()
   - send_webhook_alert()
   - route_alert() - Routes to correct channels based on severity

2. **utils/alert_manager.py**
   - log_alert() - Log to alerts table + trigger notifications
   - acknowledge_alert()
   - resolve_alert()
   - get_unresolved_alerts()
   - suppress_duplicate_alerts()

3. **database/crud_operations.py** - Add alert operations
   - create_alert()
   - get_alert()
   - update_alert()
   - get_alerts_by_severity()
   - get_unacknowledged_alerts()

### 6.2 Existing Files to Update

1. **config/system.yaml**
   - Add notifications section (email, SMS, Slack, webhook)
   - Add alert_routing section (severity → channels)

2. **utils/logger.py**
   - Add alert logging helpers
   - Integrate with alert_manager

3. **Circuit breaker code** (when implemented)
   - Call log_alert() when breakers trip

4. **Position manager** (when implemented)
   - Call log_alert() for loss thresholds, profit targets

5. **API client** (when implemented)
   - Call log_alert() on API failures

---

## PART 7: Directory Structure Question - managers/ vs utils/

### Question: Why managers/method_manager.py and not utils/method_manager.py?

**Answer:**

**managers/** - Domain-specific business logic
- Orchestrates complex operations
- Coordinates multiple database tables
- Implements business rules
- Examples:
  - `method_manager.py` - Creates methods, validates configs, manages lifecycle
  - `position_manager.py` - Manages positions, executes exits, tracks P&L
  - `trade_manager.py` - Places trades, handles retries, tracks executions

**utils/** - General-purpose utilities
- Reusable across domains
- No business logic
- Helpers and tools
- Examples:
  - `logger.py` - Logging utilities
  - `alert_manager.py` - Alert utilities (simple logging)
  - `notification_manager.py` - Notification sending (just mechanics)
  - `decimal_utils.py` - Decimal conversion helpers

**Recommendation:**
```
managers/
├── method_manager.py        # Business logic: create/manage methods
├── position_manager.py       # Business logic: manage positions
├── trade_manager.py          # Business logic: execute trades
└── strategy_manager.py       # Business logic: select/execute strategies

utils/
├── logger.py                 # Utility: logging
├── alert_manager.py          # Utility: alert logging (simple wrapper)
├── notification_manager.py   # Utility: send emails/SMS (mechanics only)
└── config_helpers.py         # Utility: config parsing
```

**Why this matters:**
- managers/ has business logic → needs extensive testing
- utils/ is generic → can be reused across projects
- Separation makes code organization clearer

---

## PART 8: Simplified Directory Structure (No Numbering)

```
docs/
├── foundation/              # Core project docs
│   ├── PROJECT_OVERVIEW.md
│   ├── MASTER_REQUIREMENTS.md
│   ├── MASTER_INDEX.md
│   ├── ARCHITECTURE_DECISIONS.md
│   ├── DEVELOPMENT_PHASES.md
│   ├── GLOSSARY.md
│   ├── ADR_INDEX.md
│   └── REQUIREMENT_INDEX.md
│
├── database/                # Database design & schema
│   ├── DATABASE_SCHEMA_SUMMARY.md
│   ├── DATABASE_TABLES_REFERENCE.md
│   ├── VERSIONING_GUIDE.md
│   └── ODDS_RESEARCH_COMPREHENSIVE.md
│
├── configuration/           # YAML & config management
│   ├── CONFIGURATION_GUIDE.md
│   ├── USER_CUSTOMIZATION_STRATEGY.md
│   └── YAML_CONSISTENCY_AUDIT.md
│
├── api-integration/         # External API docs
│   ├── API_INTEGRATION_GUIDE.md
│   ├── KALSHI_API_REFERENCE.md
│   ├── KALSHI_DECIMAL_PRICING.md
│   └── KALSHI_API_STRUCTURE.md
│
├── trading/                 # Trading strategies & risk
│   ├── POSITION_MANAGEMENT_GUIDE.md
│   ├── TRAILING_STOP_GUIDE.md
│   └── NOTIFICATION_SYSTEM_GUIDE.md          # NEW
│
├── testing/                 # Testing strategy
│   └── TESTING_STRATEGY.md
│
├── adrs/                    # Architecture Decision Records
│   ├── ADR_020_DEFERRED_EXECUTION.md
│   ├── ADR_021_METHOD_ABSTRACTION.md
│   └── (future ADRs)
│
├── phase-specs/             # Phase-specific designs
│   ├── PHASE_1_TASK_PLAN.md
│   ├── PHASE_5_POSITION_MONITORING.md
│   ├── PHASE_5_EXIT_EVALUATION.md
│   ├── PHASE_5_EVENT_LOOP_ARCHITECTURE.md
│   └── PHASE_8_ADVANCED_EXECUTION.md
│
├── protocols/               # Development protocols
│   ├── SESSION_HANDOFF_TEMPLATE.md
│   ├── PHASE_COMPLETION_PROTOCOL.md
│   ├── TOKEN_MONITORING_PROTOCOL.md
│   ├── ENVIRONMENT_CHECKLIST.md
│   └── VERSION_HEADERS_GUIDE.md
│
├── archive/                 # Historical/completed docs
│   ├── phase-0/
│   ├── phase-0.5/
│   └── sessions/
│
├── MASTER_INDEX.md          # Root comprehensive index
├── POSTGRESQL_SETUP_GUIDE.md
└── README.md                # Navigation guide

phase05 updates/ → INTEGRATE INTO APPROPRIATE DIRECTORIES ABOVE
```

**Changes from current:**
- foundation/ (was 4 separate dirs: foundation, supplementary, utility, sessions)
- trading/ (was trading-risk)
- adrs/ (separated from phase05 updates)
- phase-specs/ (was phases-planning)
- protocols/ (consolidated from utility)
- archive/ (was phase-0-completion, phase-0.5-completion)
- **10 directories total** (vs 13+ currently)
- **NO NUMBERING** (cleaner, easier to reference)

---

## PART 9: Action Items for YAMLs

### 9.1 system.yaml Updates

**ADD:**
```yaml
# ============================================
# NOTIFICATIONS
# ============================================
notifications:
  email:
    enabled: false  # Enable in production
    provider: "smtp"
    smtp:
      host_env: "SMTP_HOST"
      port_env: "SMTP_PORT"
      use_tls: true
      username_env: "SMTP_USERNAME"
      password_env: "SMTP_PASSWORD"
      from_address_env: "ALERT_FROM_EMAIL"
    recipients:
      critical_env: "CRITICAL_ALERT_EMAILS"
      high_env: "HIGH_ALERT_EMAILS"
      medium_env: "MEDIUM_ALERT_EMAILS"
      default_env: "DEFAULT_ALERT_EMAILS"

  sms:
    enabled: false  # Enable in production
    provider: "twilio"
    twilio:
      account_sid_env: "TWILIO_ACCOUNT_SID"
      auth_token_env: "TWILIO_AUTH_TOKEN"
      from_number_env: "TWILIO_FROM_NUMBER"
    recipients:
      critical_env: "CRITICAL_ALERT_PHONE_NUMBERS"
      high_env: "HIGH_ALERT_PHONE_NUMBERS"
    rate_limit:
      max_per_hour: 5
      max_per_day: 20
      cooldown_seconds: 300

  slack:
    enabled: false
    webhook_url_env: "SLACK_WEBHOOK_URL"
    channel_env: "SLACK_ALERT_CHANNEL"

  webhook:
    enabled: false
    url_env: "CUSTOM_WEBHOOK_URL"
    method: "POST"

# Alert routing by severity
alert_routing:
  critical:
    channels: ["console", "file", "email", "sms", "database"]
    immediate: true
  high:
    channels: ["console", "file", "email", "database"]
    immediate: true
  medium:
    channels: ["console", "file", "database"]
    immediate: false
  low:
    channels: ["file", "database"]
    immediate: false
```

### 9.2 No Other YAML Updates Needed

- trading.yaml: Already has alerts section (OK as-is)
- position_management.yaml: References alerts (will use alert_manager)
- data_sources.yaml: References alerts (will use alert_manager)
- probability_models.yaml: References alerts (will use alert_manager)
- Others: No changes needed

---

## PART 10: Summary of Gaps & Fixes

| Gap | Current State | Fix Needed | Priority |
|-----|---------------|------------|----------|
| **Alerts table missing** | References in YAMLs but no table | Create alerts table | CRITICAL |
| **Email/SMS not implemented** | Referenced in YAMLs but no code | Add notification_manager.py + system.yaml updates | HIGH |
| **Methods table placeholder** | Missing from DB schema docs | Add placeholder to DATABASE_SCHEMA_SUMMARY | HIGH |
| **Missing 6 tables in MASTER_REQ** | Only 13/19 tables documented | Add platforms, settlements, account_balance, config_overrides, circuit_breaker_events, system_health | CRITICAL |
| **15 method requirements missing** | Not in MASTER_REQUIREMENTS | Add REQ-METH-001 through REQ-METH-015 | MEDIUM |
| **Directory structure** | 13+ directories, confusing | Simplify to 10 directories | MEDIUM |
| **phase05 updates limbo** | Separate directory | Integrate into main docs | HIGH |
| **method_id missing from trades** | No FK column | ALTER TABLE trades ADD method_id (Phase 4-5) | LOW (future) |
| **matrix_name/description missing** | Not in probability_matrices | ALTER TABLE (Plan A - do after testing) | MEDIUM |

---

**Next Steps:** Await user approval on:
1. Simplified directory structure
2. Alerts table implementation
3. Email/SMS in system.yaml
4. 2-session implementation plan

