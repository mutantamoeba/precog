# Documentation Refactoring Plan V1.0

**Created:** 2025-10-23
**Phase:** 1 (Foundation Completion)
**Purpose:** Address documentation gaps, inconsistencies, and structural issues before Phase 2

---

## Executive Summary

Comprehensive audit revealed:
- ❌ **5 missing tables** in MASTER_REQUIREMENTS (platforms, settlements, account_balance, config_overrides, circuit_breaker_events, system_health)
- ❌ **Methods table missing** from DATABASE_SCHEMA_SUMMARY (supposed to be placeholder per ADR-021)
- ❌ **15 requirements missing** (REQ-METH-001 through REQ-METH-015 from ADR-021)
- ❌ **Directory structure overcomplicated** (70+ docs across 10+ directories)
- ❌ **Version inconsistency** (phase05 updates/ not integrated into main docs)
- ❌ **Alerts table undefined** (system_health.alert_sent exists, but no dedicated alerts log)

---

## PART 1: Critical Gaps Found

### 1.1 Missing Tables in MASTER_REQUIREMENTS

**Current:** Table at line 345-360 lists only 13 tables
**Should Have:** All 18 tables from DATABASE_SCHEMA_SUMMARY_V1.5

**Missing Tables:**
1. **platforms** - CRITICAL (foundational table, FK parent for series/events/markets)
2. **settlements** - Market resolution and payouts
3. **account_balance** - Account balance tracking (versioned)
4. **config_overrides** - Runtime configuration overrides
5. **circuit_breaker_events** - Risk management event log
6. **system_health** - Component health monitoring (has alert_sent field)

**Impact:** HIGH - Incomplete database documentation, missing table awareness

### 1.2 Methods Table Missing from DATABASE_SCHEMA_SUMMARY

**Per ADR-021 (line 891):**
> "✅ Placeholder in DATABASE_SCHEMA_SUMMARY V1.5"

**Current:** NO methods table in DATABASE_SCHEMA_SUMMARY_V1.5.md
**Should Have:** Section noting "Methods table designed in Phase 0.5, implementation deferred to Phase 4-5"

**Additional Missing:**
- `method_templates` table
- `method_id` column on edges and trades tables
- Helper views: active_methods, method_performance, complete_trade_attribution

**Impact:** HIGH - Technical debt, ADR-021 deliverable incomplete

### 1.3 Missing Requirements in MASTER_REQUIREMENTS

**Per ADR-021 (lines 929-973):**
- REQ-METH-001 through REQ-METH-015 (15 requirements)

**Current:** NOT in MASTER_REQUIREMENTS_V2.6.md
**Should Have:** Section 4.x with all method requirements

**Impact:** MEDIUM - Requirements not indexed, harder to track

### 1.4 Alerts Table - Undefined

**Question:** Should we have a dedicated `alerts` table?

**Current State:**
- `system_health` table has `alert_sent` BOOLEAN field
- `circuit_breaker_events` table logs breaker triggers
- No dedicated alerts log table

**Proposed:**
```sql
CREATE TABLE alerts (
    alert_id SERIAL PRIMARY KEY,
    alert_type VARCHAR NOT NULL,          -- 'circuit_breaker', 'health_degraded', 'trade_failed', 'edge_detected'
    severity VARCHAR NOT NULL,            -- 'critical', 'high', 'medium', 'low'
    component VARCHAR NOT NULL,           -- 'kalshi_api', 'edge_detector', 'position_manager'
    message TEXT NOT NULL,
    details JSONB,                        -- Additional context
    triggered_at TIMESTAMP DEFAULT NOW(),
    acknowledged_at TIMESTAMP,
    acknowledged_by VARCHAR,
    resolved_at TIMESTAMP,
    resolved_by VARCHAR,
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_channels JSONB          -- {'email': true, 'slack': false}
);

CREATE INDEX idx_alerts_type ON alerts(alert_type);
CREATE INDEX idx_alerts_severity ON alerts(severity);
CREATE INDEX idx_alerts_triggered ON alerts(triggered_at);
CREATE INDEX idx_alerts_unresolved ON alerts(resolved_at) WHERE resolved_at IS NULL;
```

**Rationale:**
- Centralized alert/notification logging
- Separate from source tables (circuit_breaker_events, system_health)
- Acknowledgement tracking
- Multi-channel notification tracking
- Historical alert analysis

**Decision Needed:** Add alerts table or keep distributed approach?

---

## PART 2: Directory Structure Issues

### 2.1 Current Structure (Overcomplicated)

```
docs/
├── foundation/              # 11 files (core docs)
├── guides/                  # 3 files (implementation guides)
├── database/                # 3 files
├── configuration/           # 1 file
├── api-integration/         # 6 files
├── trading-risk/            # 1 file
├── supplementary/           # 1 file
├── utility/                 # 11 files (mixed purpose)
├── sessions/                # 1 file
├── phase-0-completion/      # 10 files (historical)
├── phase-0.5-completion/    # 2 files (historical)
├── phase05 updates/         # 13 files ❌ NOT INTEGRATED
└── phases-planning/         # 3 files
```

**Problems:**
- "phase05 updates/" separate from main docs (should be integrated)
- "utility/" mixed purpose (handoffs, protocols, planning, tech stack)
- Completion reports scattered across 3 directories
- Inconsistent naming (phase-0 vs phase05)
- 70+ markdown files hard to navigate

### 2.2 Proposed Refactored Structure

```
docs/
├── 01-foundation/           # Core architecture & requirements
│   ├── PROJECT_OVERVIEW.md
│   ├── MASTER_REQUIREMENTS.md
│   ├── ARCHITECTURE_DECISIONS.md
│   ├── DEVELOPMENT_PHASES.md
│   ├── GLOSSARY.md
│   ├── ADR_INDEX.md
│   └── REQUIREMENT_INDEX.md
│
├── 02-database/             # Database schema & design
│   ├── DATABASE_SCHEMA_SUMMARY.md
│   ├── DATABASE_TABLES_REFERENCE.md
│   ├── VERSIONING_GUIDE.md
│   └── research/
│       └── ODDS_RESEARCH_COMPREHENSIVE.md
│
├── 03-configuration/        # YAML configs & management
│   ├── CONFIGURATION_GUIDE.md
│   ├── USER_CUSTOMIZATION_STRATEGY.md
│   └── YAML_CONSISTENCY_AUDIT.md
│
├── 04-api-integration/      # External API integration
│   ├── API_INTEGRATION_GUIDE.md
│   ├── KALSHI_API_REFERENCE.md
│   ├── KALSHI_DECIMAL_PRICING.md
│   └── KALSHI_API_STRUCTURE.md
│
├── 05-trading/              # Trading strategies & risk
│   ├── POSITION_MANAGEMENT_GUIDE.md
│   ├── TRAILING_STOP_GUIDE.md
│   └── risk-research/
│       └── Sports_Win_Probabilities.md
│
├── 06-testing/              # Testing strategy & protocols
│   └── TESTING_STRATEGY.md
│
├── 07-adrs/                 # Architecture Decision Records
│   ├── ADR_020_DEFERRED_EXECUTION.md
│   ├── ADR_021_METHOD_ABSTRACTION.md
│   └── (future ADRs as separate files)
│
├── 08-phase-specs/          # Phase-specific specifications
│   ├── PHASE_5_POSITION_MONITORING.md
│   ├── PHASE_5_EXIT_EVALUATION.md
│   ├── PHASE_5_EVENT_LOOP_ARCHITECTURE.md
│   ├── PHASE_8_ADVANCED_EXECUTION.md
│   └── PHASE_1_TASK_PLAN.md
│
├── 09-protocols/            # Development protocols
│   ├── TESTING_STRATEGY.md
│   ├── SESSION_HANDOFF_TEMPLATE.md
│   ├── PHASE_COMPLETION_PROTOCOL.md
│   ├── TOKEN_MONITORING_PROTOCOL.md
│   ├── ENVIRONMENT_CHECKLIST.md
│   └── VERSION_HEADERS_GUIDE.md
│
├── 10-archive/              # Historical/completed phase docs
│   ├── phase-0/
│   ├── phase-0.5/
│   └── sessions/
│
├── MASTER_INDEX.md          # Root-level comprehensive index
├── POSTGRESQL_SETUP_GUIDE.md
└── README.md                # Docs navigation guide
```

**Benefits:**
- Numbered directories for logical progression
- Clear purpose for each directory
- ADRs separated (easy to find individual ADRs)
- Phase specs consolidated
- Historical docs archived
- No more "phase05 updates" limbo
- Easier navigation (< 10 top-level dirs vs 13+)

---

## PART 3: Actions Required

### 3.1 DATABASE_SCHEMA_SUMMARY Updates

**File:** `docs/database/DATABASE_SCHEMA_SUMMARY_V1.5.md` → V1.6

**Changes:**
1. Add missing platforms table (was skipped, but is in actual schema)
2. Add settlements table to main list
3. Add account_balance, config_overrides, circuit_breaker_events, system_health to comprehensive list
4. Add methods table placeholder section:
   ```markdown
   ### methods (PLACEHOLDER - Phase 4-5 Implementation)
   ```sql
   -- Designed in Phase 0.5 (ADR-021)
   -- Implementation deferred to Phase 4-5
   -- See ADR_021_METHOD_ABSTRACTION.md for complete specification

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
       -- ... see ADR-021 for full schema
       UNIQUE(method_name, method_version)
   );
   ```
   **Note:** Actual implementation will include:
   - method_templates table
   - method_id columns on edges and trades
   - Helper views (active_methods, method_performance, complete_trade_attribution)
   - Complete lifecycle and validation
   ```

5. Add section on method_id in trades/edges tables (nullable FK, backward compatible)
6. Update table count: "19 tables (18 implemented, 1 placeholder for Phase 4-5)"

### 3.2 MASTER_REQUIREMENTS Updates

**File:** `docs/foundation/MASTER_REQUIREMENTS_V2.6.md` → V2.7

**Changes:**

1. **Section 4.2 Core Tables** - Add missing tables to table:
   ```markdown
   | platforms | Platform definitions | platform_id, platform_type, base_url | N/A | None |
   | settlements | Market settlements | market_id, outcome, payout | payout (DECIMAL(10,4)) | None (append-only) |
   | account_balance | Account balance | platform_id, balance, currency | balance (DECIMAL(10,4)) | row_current_ind |
   | config_overrides | Runtime config | config_key, override_value | N/A | None |
   | circuit_breaker_events | Breaker triggers | breaker_type, triggered_at | N/A | None (append-only) |
   | system_health | Component health | component, status, last_check | N/A | None |
   ```

2. **New Section 4.7 Method Requirements (Phase 4-5)**
   ```markdown
   ## 4.7 Trading Methods (Phase 4-5)

   **REQ-METH-001: Method Creation**
   System SHALL support creating methods from templates with optional config overrides.

   **REQ-METH-002: Method Immutability**
   Method configs (position_mgmt, risk, execution, sport) SHALL be immutable once method is created.

   **REQ-METH-003: Method Versioning**
   Methods SHALL use semantic versioning (vX.Y format). Config changes require new version.

   ... (all 15 requirements from ADR-021)
   ```

3. **Section 4.8 Alerts & Monitoring** (if we add alerts table)
   ```markdown
   ## 4.8 Alerts & Monitoring

   **REQ-ALERT-001: Centralized Alert Logging**
   System SHALL log all alerts to centralized alerts table with severity, component, and acknowledgement tracking.

   **REQ-ALERT-002: Alert Severity Levels**
   Alerts SHALL have severity levels: critical, high, medium, low.

   **REQ-ALERT-003: Alert Acknowledgement**
   Critical and high severity alerts SHALL require acknowledgement before resolution.

   **REQ-ALERT-004: Multi-Channel Notifications**
   System SHALL support configurable notification channels (email, Slack, webhook) per alert type.
   ```

### 3.3 ADR_INDEX Updates

**File:** `docs/foundation/ADR_INDEX.md`

**Changes:**
1. Verify ADR-021 is correctly indexed (it should be)
2. Add note that ADRs 020-021 have dedicated files in `phase05 updates/` (will move to `07-adrs/` in refactor)
3. Update cross-references

### 3.4 MASTER_INDEX Updates

**File:** `docs/foundation/MASTER_INDEX_V2.4.md` → V2.5

**Changes:**
1. Update all file paths after directory refactoring
2. Add methods table documentation references
3. Add alerts table (if added)
4. Update version numbers for modified docs
5. Mark phase05 updates as integrated

### 3.5 Directory Refactoring

**Actions:**
1. Create new numbered directory structure
2. Move files to appropriate directories
3. Update all internal cross-references
4. Create README.md in docs/ with navigation guide
5. Archive phase-0, phase-0.5, sessions to 10-archive/
6. Integrate phase05 updates into appropriate directories

---

## PART 4: YAML File Updates

### 4.1 Current YAML Files

**Config Directory:**
```
config/
├── system.yaml
├── trading.yaml
├── position_management.yaml
└── probability_models.yaml
```

### 4.2 Updates Needed for ADR-021 (Methods)

**NO YAML CHANGES NEEDED NOW** - Methods implemented in Phase 4-5

**Rationale:**
- Methods table stores all config in database (JSONB fields)
- Templates seeded directly in database (INSERT statements)
- Methods created via Python API, not YAML
- Existing YAML files remain for non-method usage

**Future (Phase 4-5):**
- OPTIONAL: `config/method_templates.yaml` for template management
- But templates primarily in database for versioning

### 4.3 Matrix Enhancements (matrix_name, description)

**NO YAML CHANGES NEEDED**

**Rationale:**
- probability_matrices populated from code/API, not YAML
- matrix_name and description added via migration
- Updated via INSERT/UPDATE statements

---

## PART 5: Code Updates Required

### 5.1 For Methods Table (Phase 4-5 - NOT NOW)

**Future code updates when implementing:**
1. `models/method.py` - Method dataclass
2. `managers/method_manager.py` - CRUD operations
3. `database/crud_operations.py` - Add method operations
4. Trading execution - Link trades to method_id
5. Edge detection - Link edges to method_id

### 5.2 For Matrix Enhancements (NOW - after migration)

**No code changes needed**

Columns are optional (NULL allowed), existing code unaffected.

**Future enhancement (optional):**
```python
# In analytics/probability_calculator.py or similar
def create_probability_matrix(
    category: str,
    subcategory: str,
    matrix_name: str,  # NEW parameter
    description: str,  # NEW parameter
    ...
):
    """Create probability matrix with metadata."""
    pass
```

### 5.3 For Alerts Table (IF ADDED)

**New module:**
```python
# utils/alert_manager.py

def log_alert(
    alert_type: str,
    severity: str,
    component: str,
    message: str,
    details: Dict = None,
    send_notification: bool = True
):
    """
    Log alert to database and optionally send notifications.

    Args:
        alert_type: 'circuit_breaker', 'health_degraded', etc.
        severity: 'critical', 'high', 'medium', 'low'
        component: 'kalshi_api', 'edge_detector', etc.
        message: Human-readable alert message
        details: Additional context (JSONB)
        send_notification: Whether to trigger notifications
    """
    # Insert into alerts table
    # If send_notification: trigger email/Slack/webhook
    pass

def acknowledge_alert(alert_id: int, acknowledged_by: str):
    """Mark alert as acknowledged."""
    pass

def resolve_alert(alert_id: int, resolved_by: str):
    """Mark alert as resolved."""
    pass
```

**Integration points:**
- Circuit breaker triggers → log_alert()
- System health checks → log_alert()
- Trade failures → log_alert()
- Edge detector → log_alert() for high-value edges

---

## PART 6: Implementation Plan

### Phase 1A: Documentation Updates (This Session)

**Priority: CRITICAL**
**Time: 2-3 hours**

1. ✅ Create this refactoring plan
2. [ ] Update DATABASE_SCHEMA_SUMMARY V1.5 → V1.6
   - Add methods table placeholder
   - Add missing tables (platforms, settlements, etc.)
   - Update table count
3. [ ] Update MASTER_REQUIREMENTS V2.6 → V2.7
   - Add missing tables to section 4.2
   - Add REQ-METH-001 through REQ-METH-015
   - Add REQ-ALERT-* (if alerts table approved)
4. [ ] Update ADR_INDEX
5. [ ] Update REQUIREMENT_INDEX

### Phase 1B: Decide on Alerts Table

**Priority: HIGH**
**Decision Point: User input needed**

Questions:
1. Add dedicated alerts table? (RECOMMENDED: YES)
2. If yes, implement in Phase 1 or Phase 5?
3. What notification channels? (email, Slack, webhook, SMS?)

### Phase 1C: Directory Refactoring (Next Session)

**Priority: MEDIUM**
**Time: 3-4 hours**

1. [ ] Create new directory structure
2. [ ] Move files (with git mv for history preservation)
3. [ ] Update all cross-references
4. [ ] Update MASTER_INDEX V2.4 → V2.5
5. [ ] Create docs/README.md navigation guide
6. [ ] Test all links

### Phase 4-5: Methods Implementation

**Priority: DEFERRED**
**Per ADR-021 implementation timeline**

1. [ ] Create methods and method_templates tables
2. [ ] Implement Method class and MethodManager
3. [ ] Add method_id to edges and trades
4. [ ] Create helper views
5. [ ] Implement trade attribution

---

## PART 7: Documentation Debt Summary

### High Priority (Fix Now)
- ❌ Methods table placeholder missing from DATABASE_SCHEMA_SUMMARY
- ❌ 5 tables missing from MASTER_REQUIREMENTS table
- ❌ 15 REQ-METH requirements not documented
- ❌ Alerts table decision needed

### Medium Priority (Fix Next Session)
- ⚠️ Directory structure overcomplicated
- ⚠️ phase05 updates not integrated
- ⚠️ MASTER_INDEX needs updating

### Low Priority (Can Defer)
- ℹ️ Some outdated version headers
- ℹ️ Backup files (.bak) in foundation/

---

## PART 8: Success Criteria

**Documentation refactoring complete when:**
- [ ] All 18+ tables documented in MASTER_REQUIREMENTS
- [ ] Methods table placeholder in DATABASE_SCHEMA_SUMMARY
- [ ] All 15 method requirements added
- [ ] Alerts table decision made and documented
- [ ] Directory structure simplified to < 10 top-level directories
- [ ] All cross-references updated
- [ ] MASTER_INDEX reflects new structure
- [ ] No broken links in documentation

---

## Questions for User

1. **Alerts table:** Add dedicated alerts table now? Or keep distributed approach?
2. **Directory refactoring:** Approve proposed structure? Any changes?
3. **Phase05 updates:** Integrate now or keep separate?
4. **Priority:** Fix docs first, or resume testing first?

---

**Next Steps:** Awaiting user decisions on questions above, then proceed with Phase 1A documentation updates.
