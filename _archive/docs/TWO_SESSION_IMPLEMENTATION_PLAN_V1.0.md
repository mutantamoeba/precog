# Two-Session Implementation Plan V1.0

**Created:** 2025-10-23
**Phase:** 1 (Foundation Completion)
**Purpose:** Strategic plan to complete documentation refactoring, alerts table, and testing over this session + next session

---

## Session Breakdown

###

 **THIS SESSION (Session N)** - Documentation & Schema Design
**Next Session (Session N+1)** - Implementation & Testing

---

## SESSION N: Documentation & Schema (THIS SESSION)

**Goal:** Complete all documentation updates, finalize schemas, prepare for implementation
**Estimated Time:** Remaining ~2 hours of this session

### TASKS THIS SESSION

#### Task 1: Answer User Questions (DONE)
- ✅ Why managers/ vs utils/?
- ✅ Simplified directory structure (no numbering)
- ✅ YAML consistency analysis
- ✅ Email/SMS requirements
- ✅ Alerts table design

#### Task 2: Update DATABASE_SCHEMA_SUMMARY (30 min)
**File:** `docs/database/DATABASE_SCHEMA_SUMMARY_V1.5.md` → `V1.6`

**Changes:**
1. Add missing tables:
   - platforms (currently exists but not documented!)
   - settlements
   - account_balance
   - config_overrides
   - circuit_breaker_events
   - system_health

2. Add methods table (PLACEHOLDER - Phase 4-5):
   ```markdown
   ### methods (PLACEHOLDER - Implementation in Phase 4-5)

   **Purpose:** Trading methods bundle strategy + model + position management + risk config

   **Status:** Designed in Phase 0.5 (ADR-021), implementation deferred to Phase 4-5

   **Schema Preview:**
   ```sql
   CREATE TABLE methods (
       method_id SERIAL PRIMARY KEY,
       method_name VARCHAR NOT NULL,
       method_version VARCHAR NOT NULL,
       strategy_id INT REFERENCES strategies(strategy_id),
       model_id INT REFERENCES probability_models(model_id),
       position_mgmt_config JSONB NOT NULL,
       risk_config JSONB NOT NULL,
       execution_config JSONB NOT NULL,
       sport_config JSONB NOT NULL,
       config_hash VARCHAR(64) NOT NULL,
       status VARCHAR(20) DEFAULT 'draft',
       -- ... (see ADR-021 for complete spec)
       UNIQUE(method_name, method_version)
   );
   ```

   **Related Tables:**
   - method_templates (template definitions)
   - trades.method_id (nullable FK - backward compatible)
   - edges.method_id (nullable FK - backward compatible)

   **Helper Views:**
   - active_methods
   - method_performance
   - complete_trade_attribution

   **Documentation:** See ADR_021_METHOD_ABSTRACTION.md
   ```

3. Add alerts table:
   ```markdown
   ### alerts

   **Purpose:** Centralized alert/notification logging with acknowledgement tracking

   **Status:** Implemented in Phase 1

   **Schema:** (full schema from analysis document)

   **Integration:**
   - Circuit breaker events → log_alert()
   - System health checks → log_alert()
   - Trade failures → log_alert()
   - Model degradation → log_alert()

   **Notification Channels:**
   - Console
   - File logging
   - Email (SMTP)
   - SMS (Twilio)
   - Slack (webhook)
   - Custom webhook
   ```

4. Update table count: "21 tables (18 operational, 1 alerts, 2 placeholders for Phase 4-5)"

**Deliverable:** DATABASE_SCHEMA_SUMMARY_V1.6.md

#### Task 3: Update MASTER_REQUIREMENTS (45 min)
**File:** `docs/foundation/MASTER_REQUIREMENTS_V2.6.md` → `V2.7`

**Changes:**

1. **Section 4.2 Core Tables** - Add table entries:
   ```markdown
   | platforms | Platform definitions | platform_id, platform_type, base_url | N/A | None |
   | settlements | Market settlement outcomes | market_id, outcome, payout | payout (DECIMAL(10,4)) | None (append-only) |
   | account_balance | Account balance tracking | platform_id, balance | balance (DECIMAL(10,4)) | row_current_ind (SCD Type 2) |
   | config_overrides | Runtime config overrides | config_key, override_value | N/A | None |
   | circuit_breaker_events | Circuit breaker triggers | breaker_type, triggered_at | N/A | None (append-only) |
   | system_health | Component health monitoring | component, status, last_check | N/A | None |
   | alerts | Alert logging and acknowledgement | alert_id, severity, message | N/A | None (append-only) |
   | methods | Trading method versions (Phase 4-5) | method_id, method_name, method_version | N/A | Immutable versioning |
   | method_templates | Method templates (Phase 4-5) | template_id, template_name | N/A | Immutable versioning |
   ```

2. **New Section 4.7 - Trading Methods (Phase 4-5)**
   ```markdown
   ## 4.7 Trading Methods (Phase 4-5 Implementation)

   **REQ-METH-001: Method Creation**
   System SHALL support creating methods from templates with optional config overrides.

   **REQ-METH-002: Method Immutability**
   Method configurations (position_mgmt, risk, execution, sport) SHALL be immutable once method is activated.

   **REQ-METH-003: Method Versioning**
   Methods SHALL use semantic versioning (vX.Y format). Configuration changes require new version.

   **REQ-METH-004: Configuration Hashing**
   System SHALL generate MD5 hash of method configuration for quick comparison and deduplication.

   **REQ-METH-005: Method Templates**
   System SHALL provide method templates (conservative, moderate, aggressive) as starting points.

   **REQ-METH-006: Lifecycle Management**
   Methods SHALL have lifecycle states: draft, testing, active, deprecated.

   **REQ-METH-007: Activation Criteria**
   Methods SHALL meet activation criteria (min 10 paper trades, positive ROI) before ACTIVE status.

   **REQ-METH-008: Trade Attribution**
   Every trade SHALL link to exact method_id used for complete attribution.

   **REQ-METH-009: Edge Attribution**
   Every edge detection SHALL link to method_id for performance tracking.

   **REQ-METH-010: A/B Testing**
   System SHALL support running multiple method versions side-by-side for comparison.

   **REQ-METH-011: Performance Views**
   System SHALL provide helper views (active_methods, method_performance, complete_trade_attribution).

   **REQ-METH-012: Method Export/Import**
   System SHALL support exporting methods as JSONB and importing for backup/sharing.

   **REQ-METH-013: Deprecation**
   System SHALL auto-deprecate old method versions when new version activated (configurable).

   **REQ-METH-014: Historical Retention**
   System SHALL retain deprecated methods for minimum 5 years for audit trail.

   **REQ-METH-015: Backward Compatibility**
   method_id SHALL be nullable FK on trades/edges for backward compatibility with pre-method data.

   **Note:** See ADR_021_METHOD_ABSTRACTION.md for complete specification.
   ```

3. **New Section 4.8 - Alerts & Monitoring**
   ```markdown
   ## 4.8 Alerts & Monitoring

   **REQ-ALERT-001: Centralized Logging**
   System SHALL log all alerts to centralized alerts table with severity, component, message, and details.

   **REQ-ALERT-002: Severity Levels**
   Alerts SHALL have severity levels: critical, high, medium, low.

   **REQ-ALERT-003: Alert Acknowledgement**
   Critical and high severity alerts SHALL support acknowledgement tracking (acknowledged_by, acknowledged_at, acknowledged_notes).

   **REQ-ALERT-004: Alert Resolution**
   Alerts SHALL support resolution tracking (resolved_by, resolved_at, resolved_notes, resolution_action).

   **REQ-ALERT-005: Multi-Channel Notifications**
   System SHALL support configurable notification channels: console, file, email, SMS, Slack, webhook.

   **REQ-ALERT-006: Severity-Based Routing**
   System SHALL route alerts to appropriate channels based on severity (critical → all channels, low → file only).

   **REQ-ALERT-007: Deduplication**
   System SHALL deduplicate alerts using fingerprint (MD5 hash of type + component + key details).

   **REQ-ALERT-008: Rate Limiting**
   System SHALL rate-limit duplicate alerts to prevent notification spam.

   **REQ-ALERT-009: Email Notifications**
   System SHALL support email alerts via SMTP with configurable recipients by severity.

   **REQ-ALERT-010: SMS Notifications**
   System SHALL support SMS alerts via Twilio with rate limiting (max 5/hour, 20/day).

   **REQ-ALERT-011: Notification Tracking**
   System SHALL track notification attempts, channels used, and delivery failures in alerts table.

   **REQ-ALERT-012: Alert Sources**
   Alerts SHALL link to source table/record (source_table, source_id) when applicable.

   **REQ-ALERT-013: Environment Tagging**
   Alerts SHALL be tagged with environment (demo, prod) to separate test vs production alerts.

   **REQ-ALERT-014: Flexible Metadata**
   Alerts SHALL support JSONB details field for alert-specific context (stack traces, metrics, etc.).

   **REQ-ALERT-015: Query Performance**
   System SHALL index alerts by type, severity, component, triggered_at, and resolved_at for fast queries.
   ```

**Deliverable:** MASTER_REQUIREMENTS_V2.7.md

#### Task 4: Update system.yaml (15 min)
**File:** `config/system.yaml`

**Add notifications section** (from analysis document)

**Deliverable:** Updated system.yaml with notifications + alert_routing

#### Task 5: Create Alerts Table Migration SQL (15 min)
**File:** `database/migrations/002_add_alerts_table.sql`

**Content:** Complete CREATE TABLE alerts statement from analysis document

**Deliverable:** Migration SQL file (ready to execute next session)

#### Task 6: Update MASTER_INDEX (20 min)
**File:** `docs/foundation/MASTER_INDEX_V2.4.md` → `V2.5`

**Changes:**
1. Update all document version numbers
2. Add alerts table references
3. Add methods/method_templates placeholders
4. Update cross-references

**Deliverable:** MASTER_INDEX_V2.5.md

#### Task 7: Create Session Handoff Document (30 min)
**File:** `docs/sessions/SESSION_N_HANDOFF_DOCUMENTATION_REFACTORING.md`

**Content:**
- Summary of work completed this session
- List of files created/modified
- Schema changes designed (not yet executed)
- Next session tasks
- Testing requirements
- Outstanding questions

**Deliverable:** Comprehensive handoff doc

### SESSION N DELIVERABLES

**Documentation:**
- [x] DATABASE_SCHEMA_SUMMARY_V1.6.md
- [x] MASTER_REQUIREMENTS_V2.7.md
- [x] MASTER_INDEX_V2.5.md
- [x] system.yaml (updated)
- [x] YAML_AND_DOCS_CONSISTENCY_ANALYSIS_V1.0.md
- [x] TWO_SESSION_IMPLEMENTATION_PLAN_V1.0.md (this file)
- [x] SESSION_N_HANDOFF_DOCUMENTATION_REFACTORING.md

**Migrations (designed, not executed):**
- [x] 002_add_alerts_table.sql

**Code (NOT in this session):**
- None (code implementation is next session)

---

## SESSION N+1: Implementation & Testing (NEXT SESSION)

**Goal:** Execute migrations, implement alert/notification code, fix remaining tests, achieve 80% coverage
**Estimated Time:** Full session (~3-4 hours)

### TASKS NEXT SESSION

#### Task 1: Execute Database Migrations (10 min)

**Run migrations:**
```bash
# Add alerts table
psql -U postgres -d precog_dev -f database/migrations/002_add_alerts_table.sql

# Verify
psql -U postgres -d precog_dev -c "\d alerts"
```

**Validation:**
- Alerts table exists
- All indexes created
- Constraints working

**Deliverable:** Alerts table operational

#### Task 2: Implement notification_manager.py (60 min)

**File:** `utils/notification_manager.py`

**Functions:**
```python
def send_email_alert(severity: str, alert_type: str, message: str, details: Dict = None)
def send_sms_alert(severity: str, alert_type: str, message: str, phone_number: str)
def send_slack_alert(severity: str, alert_type: str, message: str, details: Dict = None)
def send_webhook_alert(severity: str, alert_type: str, message: str, details: Dict = None)
def route_alert(severity: str, alert_type: str, message: str, details: Dict = None)
```

**Dependencies:**
```bash
pip install twilio  # For SMS
# email via stdlib (smtplib)
# requests for webhook (already have)
```

**Testing:**
- Unit tests for each function
- Mock SMTP/Twilio in tests
- Test routing logic

**Deliverable:** notification_manager.py + tests

#### Task 3: Implement alert_manager.py (45 min)

**File:** `utils/alert_manager.py`

**Functions:**
```python
def log_alert(alert_type: str, severity: str, component: str, message: str, details: Dict = None, send_notification: bool = True) -> int
def acknowledge_alert(alert_id: int, acknowledged_by: str, notes: str = None)
def resolve_alert(alert_id: int, resolved_by: str, resolution_action: str, notes: str = None)
def get_unresolved_alerts(severity: str = None, component: str = None) -> List[Dict]
def suppress_duplicate_alerts(fingerprint: str, window_minutes: int = 60) -> bool
def calculate_fingerprint(alert_type: str, component: str, key_details: Dict) -> str
```

**Integration:**
- Calls notification_manager.route_alert()
- Inserts into alerts table
- Implements deduplication
- Rate limiting for SMS

**Testing:**
- Test alert creation
- Test deduplication
- Test rate limiting
- Test notification integration

**Deliverable:** alert_manager.py + tests

#### Task 4: Update CRUD Operations (30 min)

**File:** `database/crud_operations.py`

**Add alert operations:**
```python
def create_alert(alert_type, severity, component, message, details=None, ...):
def get_alert(alert_id):
def update_alert(alert_id, **kwargs):
def get_alerts_by_severity(severity, limit=100):
def get_unacknowledged_alerts(severity=None):
def acknowledge_alert_db(alert_id, acknowledged_by, notes=None):
def resolve_alert_db(alert_id, resolved_by, resolution_action, notes=None):
```

**Deliverable:** Updated crud_operations.py

#### Task 5: Update logger.py Integration (20 min)

**File:** `utils/logger.py`

**Add:**
```python
def log_alert_helper(alert_type, severity, component, message, details=None):
    """Helper to log structured alert."""
    from utils.alert_manager import log_alert
    log_alert(alert_type, severity, component, message, details)
```

**Deliverable:** Updated logger.py

#### Task 6: Write Tests for Alert System (45 min)

**File:** `tests/test_alert_manager.py`

**Tests:**
```python
@pytest.mark.integration
def test_create_alert(db_cursor):
    """Test creating alert in database."""

@pytest.mark.unit
def test_fingerprint_calculation():
    """Test fingerprint deduplication."""

@pytest.mark.integration
def test_suppress_duplicate_alerts(db_cursor):
    """Test duplicate suppression."""

@pytest.mark.unit
def test_alert_routing():
    """Test severity-based channel routing."""

@pytest.mark.integration
def test_email_notification(mocker):
    """Test email sending (mocked SMTP)."""

@pytest.mark.integration
def test_sms_notification(mocker):
    """Test SMS sending (mocked Twilio)."""
```

**Deliverable:** test_alert_manager.py

#### Task 7: Fix Remaining 20 Test Failures (60 min)

**Current Issue:** Tests failing due to missing parent records (strategies, models, platforms, events)

**Fix:**
Update `tests/conftest.py`:
```python
@pytest.fixture(scope="function")
def clean_test_data(db_cursor):
    """Enhanced fixture with strategies and models."""

    # ... existing cleanup ...

    # Create test strategy
    db_cursor.execute("""
        INSERT INTO strategies (
            strategy_id, strategy_name, strategy_version,
            sport, config, status
        )
        VALUES (
            1, 'test_strategy', 'v1.0',
            'nfl', '{}', 'active'
        )
        ON CONFLICT (strategy_id) DO NOTHING
    """)

    # Create test model
    db_cursor.execute("""
        INSERT INTO probability_models (
            model_id, model_name, model_version,
            category, config, status
        )
        VALUES (
            1, 'test_model', 'v1.0',
            'sports', '{}', 'active'
        )
        ON CONFLICT (model_id) DO NOTHING
    """)

    db_cursor.connection.commit()

    yield

    # ... existing cleanup ...
```

**Run tests:**
```bash
pytest -v --cov=database --cov=config --cov=utils --cov-report=term-missing --cov-fail-under=80
```

**Goal:** All tests passing, 80%+ coverage

**Deliverable:** Fixed tests, passing test suite

#### Task 8: Documentation for Alerts (30 min)

**File:** `docs/trading/NOTIFICATION_SYSTEM_GUIDE.md`

**Content:**
- Overview of alert system
- Severity levels and routing
- Email configuration (SMTP)
- SMS configuration (Twilio)
- Testing notifications
- Troubleshooting guide
- Cost estimates (Twilio pricing)

**Deliverable:** NOTIFICATION_SYSTEM_GUIDE.md

#### Task 9: Update .env.example (10 min)

**File:** `.env.example`

**Add:**
```bash
# Email Notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
ALERT_FROM_EMAIL=alerts@precog.local
CRITICAL_ALERT_EMAILS=you@example.com
HIGH_ALERT_EMAILS=you@example.com
MEDIUM_ALERT_EMAILS=you@example.com
DEFAULT_ALERT_EMAILS=you@example.com

# SMS Notifications (Twilio)
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+15551234567
CRITICAL_ALERT_PHONE_NUMBERS=+15551234567
HIGH_ALERT_PHONE_NUMBERS=+15551234567

# Slack Notifications (Optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_ALERT_CHANNEL=#trading-alerts

# Custom Webhook (Optional)
CUSTOM_WEBHOOK_URL=https://your-webhook.com/alerts
```

**Deliverable:** Updated .env.example

#### Task 10: Final Session Handoff (20 min)

**File:** `docs/sessions/SESSION_N_PLUS_1_HANDOFF_ALERTS_IMPLEMENTATION.md`

**Content:**
- Summary of implementations
- Test results (coverage %)
- Migration status
- Outstanding items for Phase 2
- Known issues/limitations

**Deliverable:** Session handoff document

### SESSION N+1 DELIVERABLES

**Code:**
- [x] utils/notification_manager.py
- [x] utils/alert_manager.py
- [x] database/crud_operations.py (updated)
- [x] utils/logger.py (updated)

**Tests:**
- [x] tests/test_alert_manager.py
- [x] tests/test_notification_manager.py
- [x] tests/conftest.py (enhanced fixtures)
- [x] All 66+ tests passing
- [x] 80%+ coverage achieved

**Database:**
- [x] alerts table created
- [x] Indexes created
- [x] Migration executed successfully

**Documentation:**
- [x] NOTIFICATION_SYSTEM_GUIDE.md
- [x] .env.example (updated)
- [x] SESSION_N_PLUS_1_HANDOFF_ALERTS_IMPLEMENTATION.md

---

## Success Criteria

### End of Session N (THIS SESSION)
- [ ] All documentation updated (DATABASE_SCHEMA_SUMMARY, MASTER_REQUIREMENTS, MASTER_INDEX)
- [ ] system.yaml has notifications section
- [ ] Alerts table migration SQL file created
- [ ] Handoff document created
- [ ] No code implementations (just design)

### End of Session N+1 (NEXT SESSION)
- [ ] Alerts table exists in database
- [ ] notification_manager.py implemented and tested
- [ ] alert_manager.py implemented and tested
- [ ] All 66+ tests passing
- [ ] 80%+ code coverage achieved
- [ ] NOTIFICATION_SYSTEM_GUIDE.md created
- [ ] Phase 1 foundation complete

---

## Risk Mitigation

### Potential Issues

**Issue 1: SMTP Configuration Complexity**
- **Risk:** Email sending might fail due to SMTP config
- **Mitigation:** Provide Gmail + Outlook examples in docs, mock in tests
- **Fallback:** Skip email in Phase 1, implement in Phase 2

**Issue 2: Twilio Account Required**
- **Risk:** User might not want to set up Twilio immediately
- **Mitigation:** Make SMS optional, test with mocks
- **Fallback:** Console + file + email only in Phase 1

**Issue 3: Test Coverage Might Not Reach 80%**
- **Risk:** Complex code paths hard to test
- **Mitigation:** Focus on critical paths, use mocks extensively
- **Fallback:** Target 75% if 80% proves difficult, document gaps

**Issue 4: Time Constraints**
- **Risk:** Session N+1 might run long
- **Mitigation:** Prioritize core functionality, defer nice-to-haves
- **Fallback:** Split into Session N+1 and N+2 if needed

---

## Phase 1 Completion Checklist

After Session N+1, Phase 1 should be complete:

### Foundation Components
- [x] Database connection pooling (psycopg2)
- [x] CRUD operations (raw SQL)
- [x] Configuration loader (YAML with Decimal)
- [x] Structured logging (JSON with Decimal serialization)
- [x] Alert system (database + notifications)
- [x] Testing infrastructure (pytest, 80% coverage)

### Documentation
- [x] DATABASE_SCHEMA_SUMMARY (all tables documented)
- [x] MASTER_REQUIREMENTS (all requirements listed)
- [x] TESTING_STRATEGY (standard for all phases)
- [x] DATABASE_TABLES_REFERENCE (quick lookup)
- [x] NOTIFICATION_SYSTEM_GUIDE (alert configuration)
- [x] MASTER_INDEX (updated)

### Database
- [x] All 18 core tables operational
- [x] alerts table created
- [x] methods/method_templates placeholders documented (Phase 4-5)
- [x] Test fixtures working

### Configuration
- [x] system.yaml (with notifications)
- [x] trading.yaml
- [x] position_management.yaml
- [x] probability_models.yaml
- [x] markets.yaml
- [x] data_sources.yaml
- [x] trade_strategies.yaml

### Ready for Phase 2
- [ ] Edge detection
- [ ] Position sizing (Kelly Criterion)
- [ ] Basic trading strategies

---

**Total Estimated Time:**
- Session N (THIS): ~2 hours remaining
- Session N+1 (NEXT): ~3-4 hours

**Grand Total:** ~5-6 hours across 2 sessions
