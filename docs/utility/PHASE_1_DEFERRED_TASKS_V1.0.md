# Phase 1 Deferred Tasks

**Version:** 1.0
**Created:** 2025-11-06
**Phase:** 1 (Database & API Connectivity)
**Status:** 🟡 In Progress - Deferred to Phase 1.5

---

## Overview

This document tracks tasks that were identified during Phase 1 (Database & API Connectivity) but deferred to Phase 1.5 or later phases due to time constraints, priority, or dependencies. These tasks are **important but not blocking** for Phase 1 completion or Phase 2 development to begin.

**Deferred from Session:** 2025-11-06 CI/CD Integration & Code Quality Sprint

---

## Deferred Tasks Summary

| ID | Task | Priority | Estimated Effort | Target Phase |
|----|------|----------|------------------|--------------|
| DEF-P1-001 | Extended Docstrings for All Modules | 🟡 High | 6-8 hours | 1.5 |
| DEF-P1-002 | Fix Documentation Cross-References (11 issues) | 🟡 High | 2 hours | 1.5 |
| DEF-P1-003 | Add 54 Documents to MASTER_INDEX | 🟡 High | 3 hours | 1.5 |
| DEF-P1-004 | Archive Superseded Documents (V2.3, etc.) | 🟢 Medium | 1 hour | 1.5 |
| DEF-P1-005 | Re-enable validate-docs Pre-Commit Hook | 🟢 Medium | 30 min | 1.5 |
| DEF-P1-006 | Enhance validate_docs.py (Exclude Ephemeral Files) | 🟢 Medium | 1 hour | 1.5 |
| DEF-P1-007 | Expand Security Scanning Patterns | 🔵 Low | 1 hour | 2+ |
| DEF-P1-008 | Database Query Optimization | 🔵 Low | 4-6 hours | 2+ |
| DEF-P1-009 | Comprehensive Integration Tests (Live API) | 🟡 High | 8-10 hours | 2 |

**Total Estimated Effort:** 26-33 hours (HIGH: 16-20h, MEDIUM: 5.5h, LOW: 5-7h)

---

## DEF-P1-001: Extended Docstrings for All Modules

### Description
Elevate all Python modules to the **"gold standard"** docstring format exemplified by `api_connectors/rate_limiter.py`. This means adding:
- Educational notes explaining WHY things work (not just what they do)
- Comprehensive examples with actual code
- Cross-references to documentation (REQ-*, ADR-*, guides)
- Thread safety notes where applicable
- Performance implications
- Security considerations

### Rationale
- **Developer onboarding:** New developers can learn the system faster with educational docstrings
- **Code maintainability:** Understanding the "why" prevents breaking important patterns
- **Self-documenting code:** Reduces need to constantly reference external docs
- **Best practices:** Matches industry standards for production-grade Python codebases

### Current Status
**✅ GOLD STANDARD (No changes needed):**
- `api_connectors/rate_limiter.py` - Comprehensive educational docstrings
- `api_connectors/kalshi_auth.py` - Good docstrings with security placeholders
- `api_connectors/kalshi_client.py` - Good API-focused docstrings

**🟡 NEEDS ENHANCEMENT (Basic docstrings exist):**
- `database/connection.py` - Missing educational notes about connection pooling
- `database/crud_operations.py` - Missing SCD Type 2 patterns, versioning examples
- `config/config_loader.py` - Missing YAML config structure explanations
- `main.py` - CLI commands need better usage examples, error handling docs
- `utils/logger.py` - Missing structured logging examples, log levels explanation

**🔴 MINIMAL OR MISSING:**
- `api_connectors/__init__.py` - No module-level docstring
- `database/__init__.py` - No module-level docstring
- `config/__init__.py` - No module-level docstring
- `tests/fixtures/factories.py` - No factory pattern explanation

### Implementation Plan

#### Phase 1.5A: Database Module Enhancements (4 hours)

**database/connection.py:**
```python
"""
Database connection management with connection pooling.

Connection Pooling Explained:
-----------------------------
Imagine a parking lot with 10 spots. Instead of building a new car (connection)
every time you want to drive (query), you borrow a car from the lot and return
it when done. This is MUCH faster than creating a new TCP connection to PostgreSQL
for every query.

Why This Matters:
- Creating a new connection: ~50-100ms overhead
- Reusing pooled connection: <1ms overhead
- For 1000 queries: 50 seconds vs 1 second

Thread Safety:
- psycopg2.pool.SimpleConnectionPool is thread-safe
- Multiple threads can call get_connection() simultaneously
- Pool ensures no two threads get the same connection

Performance Metrics:
- Min connections (minconn=2): Always 2 connections ready
- Max connections (maxconn=10): Pool grows up to 10 under load
- Idle timeout: Connections returned to pool immediately after use

Reference: docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md
Related Requirements: REQ-DB-002 (Connection Pooling)
Related ADR: ADR-008 (PostgreSQL Connection Strategy)
"""
# ... rest of module
```

**database/crud_operations.py:**
```python
"""
CRUD operations with SCD Type 2 versioning support.

SCD Type 2 (Slowly Changing Dimension) Explained:
--------------------------------------------------
Instead of UPDATE, we INSERT new rows and mark old ones as historical.
This preserves full history of changes for auditing and backtesting.

Example - Market price changes over time:
┌────────┬─────────┬─────────────────┬──────────────────┬─────────────────┐
│market_id│yes_price│inserted_datetime│updated_datetime  │row_current_ind  │
├────────┼─────────┼─────────────────┼──────────────────┼─────────────────┤
│  1     │ 0.5200  │ 2024-01-01 10:00│ 2024-01-01 11:00 │ FALSE (historical)│
│  1     │ 0.5350  │ 2024-01-01 11:00│ 2024-01-01 11:00 │ TRUE (current)   │
└────────┴─────────┴─────────────────┴──────────────────┴─────────────────┘

CRITICAL: Always query with row_current_ind = TRUE to get current data!

Why This Pattern?
- Backtesting: Can see exactly what price was at any point in time
- Auditing: Full history of all changes (who, when, what)
- Trade attribution: Know which price triggered which trade

Reference: docs/guides/VERSIONING_GUIDE_V1.0.md
Related Requirements: REQ-DB-003 (SCD Type 2 Tracking)
Related ADR: ADR-019 (SCD Type 2 for Markets/Positions)
"""
# ... rest of module
```

#### Phase 1.5B: Configuration & Logging (2 hours)

**config/config_loader.py:**
```python
"""
YAML configuration loader with environment variable overrides.

Configuration Hierarchy:
-----------------------
1. Base config files (config/*.yaml) - Defaults
2. Environment variables (.env) - Overrides for secrets
3. Command-line arguments - Highest priority

Example:
  config/system.yaml:    log_level: INFO
  .env:                  LOG_LEVEL=DEBUG   <- Overrides YAML
  CLI:                   --log-level=ERROR <- Overrides everything

Why This Pattern?
- Secrets never in YAML (version controlled)
- Easy to change settings without code changes
- Different settings for dev/test/prod environments

Security Note:
- NEVER put API keys, passwords, tokens in YAML files
- ALWAYS use environment variables for credentials
- See: docs/utility/SECURITY_REVIEW_CHECKLIST.md

Reference: docs/guides/CONFIGURATION_GUIDE_V3.1.md
Related Requirements: REQ-CONFIG-001 (YAML Configuration)
Related ADR: ADR-012 (Configuration Management Strategy)
"""
# ... rest of module
```

**utils/logger.py:**
```python
"""
Structured logging with JSON output for production observability.

Structured Logging Explained:
-----------------------------
Instead of plain text logs like:
  "User john logged in from 192.168.1.1"

We output JSON with structured fields:
  {"event": "user_login", "user_id": "john", "ip": "192.168.1.1", "timestamp": "..."}

Why This Matters:
- **Searchability:** Can query logs like a database (find all user_login events)
- **Alerting:** Easy to trigger alerts on specific field values
- **Analytics:** Aggregate metrics (count logins per hour)
- **Debugging:** Consistent fields make correlation easier

Log Levels (from most to least critical):
- CRITICAL: System is unusable (database down, API unreachable)
- ERROR: Feature failed but system continues (trade execution failed)
- WARNING: Unexpected but handled (rate limit hit, retrying)
- INFO: Normal operations (trade executed, market fetched)
- DEBUG: Detailed troubleshooting (SQL queries, API payloads)

Performance Note:
- Logging is expensive! Avoid DEBUG logs in tight loops
- JSON serialization adds ~5-10% overhead vs plain text
- Use `extra=` parameter for structured fields (see examples)

Reference: docs/guides/CONFIGURATION_GUIDE_V3.1.md (Logging section)
Related Requirements: REQ-OBSERV-001 (Structured Logging)
Related ADR: ADR-048 (Logging Strategy)
"""
# ... rest of module
```

#### Phase 1.5C: CLI & Test Fixtures (2-3 hours)

**main.py:**
- Add comprehensive CLI usage examples to each command docstring
- Document error handling patterns (when to exit vs retry)
- Add cross-references to API_INTEGRATION_GUIDE

**tests/fixtures/factories.py:**
- Explain factory pattern benefits (DRY test data creation)
- Document how to create realistic test data
- Add examples of using factories in tests

### Success Criteria
- [ ] All modules have educational docstrings matching rate_limiter.py standard
- [ ] All docstrings include cross-references to REQ-*/ADR-*/guides
- [ ] All docstrings have comprehensive examples
- [ ] Mypy compliance maintained (no type errors introduced)
- [ ] Ruff compliance maintained (no lint errors introduced)

### Dependencies
- None (can start immediately)

### Timeline
- **Phase 1.5A:** 4 hours (database modules)
- **Phase 1.5B:** 2 hours (config & logging)
- **Phase 1.5C:** 2-3 hours (CLI & tests)
- **TOTAL:** 8-9 hours

---

## DEF-P1-002: Fix Documentation Cross-References (11 issues)

### Description
Fix 11 broken cross-references detected by `validate_docs.py`:
- `MASTER_REQUIREMENTS_V2.10.md` references old versions (V2.9, V2.8)
- `TESTING_STRATEGY_V2.0.md` references `MASTER_REQUIREMENTS_V2.9.md` (should be V2.10)
- `VALIDATION_LINTING_ARCHITECTURE_V1.0.md` references old versions

### Rationale
- Broken links cause confusion ("which version is current?")
- Documentation credibility suffers
- Automated validation catches these before manual review

### Implementation
```bash
# 1. Find all broken references
python scripts/validate_docs.py

# 2. Update references in foundation documents
# MASTER_REQUIREMENTS_V2.10.md:
#   - Update self-references V2.9 → V2.10
#   - Update MASTER_INDEX V2.7 → V2.10
#   - Update ARCHITECTURE_DECISIONS V2.8 → V2.10
#   - Update ADR_INDEX V1.2 → V1.4

# TESTING_STRATEGY_V2.0.md:
#   - Update foundation/MASTER_REQUIREMENTS_V2.9.md → V2.10.md
#   - Update foundation/ARCHITECTURE_DECISIONS_V2.8.md → V2.10.md

# VALIDATION_LINTING_ARCHITECTURE_V1.0.md:
#   - Update MASTER_REQUIREMENTS_V2.9.md → V2.10.md

# 3. Run validation again
python scripts/validate_docs.py  # Should show 0 broken cross-references
```

### Success Criteria
- [ ] `validate_docs.py` reports 0 broken cross-references
- [ ] All version numbers in references match current versions
- [ ] MASTER_INDEX reflects all changes

### Dependencies
- None (can do immediately)

### Timeline
- 2 hours

---

## DEF-P1-003: Add 54 Documents to MASTER_INDEX

### Description
54 versioned documents exist but are not listed in `MASTER_INDEX_V2.10.md`. Add all permanent documents, exclude ephemeral ones (SESSION_HANDOFF_*).

### Rationale
- MASTER_INDEX is single source of truth for document inventory
- Missing documents appear "orphaned" and may be overlooked
- Automated validation enforces this standard

### Implementation

**Step 1: Categorize documents** (30 min)

**Permanent docs (should be in MASTER_INDEX):**
- ADR_INDEX_V1.4.md
- ADVANCED_EXECUTION_SPEC_V1.0.md
- API_INTEGRATION_GUIDE_V2.0.md
- ARCHITECTURE_DECISIONS_V2.10.md
- CONFIGURATION_GUIDE_V3.1.md
- DATABASE_SCHEMA_SUMMARY_V1.7.md
- DEVELOPMENT_PHASES_V1.4.md
- ENVIRONMENT_CHECKLIST_V1.0.md
- EVENT_LOOP_ARCHITECTURE_V1.0.md
- EXIT_EVALUATION_SPEC_V1.0.md
- [... 30 more permanent docs]

**Ephemeral docs (exclude from MASTER_INDEX):**
- SESSION_HANDOFF_* (temporary handoff docs, not permanent)
- CLAUDE_CODE_* (temporary planning docs)
- DOCUMENTATION_REFACTORING_PLAN_* (one-time planning)
- TWO_SESSION_IMPLEMENTATION_PLAN_* (one-time planning)
- FILENAME_VERSION_REPORT.md (audit artifact)
- [... other temporary docs]

**Step 2: Update MASTER_INDEX** (2 hours)

Add entries for all permanent documents following the table format:
```markdown
| DOCUMENT_NAME_VX.Y.md | Status | Version | Location | Page Count | Phase | Priority | Description |
```

**Step 3: Update validate_docs.py** (30 min)

Add exclusion patterns for ephemeral files:
```python
# Exclude ephemeral patterns from "missing from MASTER_INDEX" check
EPHEMERAL_PATTERNS = [
    r"SESSION_HANDOFF_.*\.md$",
    r"CLAUDE_CODE_.*\.md$",
    r".*_PLAN_.*\.md$",
    r"FILENAME_VERSION_REPORT\.md$",
]
```

### Success Criteria
- [ ] All 40+ permanent documents added to MASTER_INDEX
- [ ] Ephemeral patterns excluded from validation
- [ ] `validate_docs.py` reports 0 "missing from MASTER_INDEX" errors

### Dependencies
- None

### Timeline
- 3 hours total (30min categorize + 2h update index + 30min update validator)

---

## DEF-P1-004: Archive Superseded Documents

### Description
Move old document versions to `_archive/` folder to prevent confusion:
- MASTER_REQUIREMENTS_V2.3.md → _archive/
- DEVELOPMENT_PHASES_V1.1.md → _archive/
- TESTING_STRATEGY_V1.1.md → _archive/
- [... other superseded versions]

### Rationale
- Reduces clutter in main docs/ folder
- Prevents accidentally referencing old versions
- Preserves history (still accessible in _archive/)

### Implementation
```bash
# 1. Create _archive folder structure if needed
mkdir -p _archive/foundation
mkdir -p _archive/guides
mkdir -p _archive/utility

# 2. Move superseded versions
git mv docs/foundation/MASTER_REQUIREMENTS_V2.3.md _archive/foundation/
git mv docs/foundation/DEVELOPMENT_PHASES_V1.1.md _archive/foundation/
git mv docs/foundation/TESTING_STRATEGY_V1.1.md _archive/foundation/
# ... etc

# 3. Update MASTER_INDEX to mark as archived
# Change status from ✅ Current to 📦 Archived

# 4. Commit with clear message
git commit -m "Archive superseded document versions (V2.3, V1.1, etc.)"
```

### Success Criteria
- [ ] All superseded versions moved to _archive/
- [ ] MASTER_INDEX updated (status = 📦 Archived)
- [ ] No broken links introduced

### Dependencies
- Complete DEF-P1-002 first (fix cross-references to avoid breaking links)

### Timeline
- 1 hour

---

## DEF-P1-005: Re-enable validate-docs Pre-Commit Hook

### Description
Currently the `validate-docs` hook is temporarily disabled in `.pre-commit-config.yaml` (lines 13-22). Re-enable after fixing documentation issues.

### Rationale
- Prevents future documentation drift
- Catches broken cross-references before commit
- Enforces MASTER_INDEX consistency

### Implementation
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      # Uncomment these lines:
      - id: validate-docs
        name: Documentation Validation (9 checks)
        entry: python scripts/validate_docs.py
        language: system
        pass_filenames: false
        files: \.(md|yaml|yml)$
        description: "Validates documentation consistency, cross-references, versioning"
```

### Success Criteria
- [ ] Hook uncommented in `.pre-commit-config.yaml`
- [ ] `pre-commit run --all-files` passes without errors
- [ ] CI `pre-commit-checks` job passes

### Dependencies
- **MUST complete DEF-P1-002 (fix cross-references)**
- **MUST complete DEF-P1-003 (add docs to MASTER_INDEX)**
- **MUST complete DEF-P1-006 (enhance validate_docs.py)**

### Timeline
- 30 minutes (testing and verification)

---

## DEF-P1-006: Enhance validate_docs.py (Exclude Ephemeral Files)

### Description
Update `scripts/validate_docs.py` to exclude ephemeral files from "missing from MASTER_INDEX" validation. Currently flags SESSION_HANDOFF_* and other temporary files as errors.

### Rationale
- SESSION_HANDOFF_* files are temporary (deleted after archiving)
- Planning documents (CLAUDE_CODE_*, *_PLAN_*) are one-time artifacts
- Reduces false positive errors in validation output

### Implementation
```python
# scripts/validate_docs.py

# Add after imports:
EPHEMERAL_PATTERNS = [
    r"SESSION_HANDOFF_.*\.md$",           # Temporary session handoffs
    r"CLAUDE_CODE_.*\.md$",               # Claude planning docs
    r".*_PLAN_V.*\.md$",                  # One-time planning documents
    r"FILENAME_VERSION_REPORT\.md$",      # Audit artifact
    r"DOCUMENTATION_V2_REVIEW_GUIDE\.md$", # Review guide (temporary)
]

def is_ephemeral(filename: str) -> bool:
    """Check if file matches ephemeral patterns."""
    import re
    return any(re.search(pattern, filename) for pattern in EPHEMERAL_PATTERNS)

# In validate_master_index_completeness():
for doc_file in versioned_docs:
    if is_ephemeral(doc_file.name):
        continue  # Skip ephemeral files

    if doc_file.name not in master_index_docs:
        missing_docs.append(doc_file.name)
```

### Success Criteria
- [ ] Ephemeral patterns excluded from validation
- [ ] SESSION_HANDOFF_* no longer flagged as "missing from MASTER_INDEX"
- [ ] Planning documents excluded
- [ ] Permanent documents still validated

### Dependencies
- None

### Timeline
- 1 hour

---

## DEF-P1-007: Expand Security Scanning Patterns

### Description
Enhance security scanning to catch additional credential patterns:
- AWS keys (AKIA...)
- Google API keys (AIza...)
- JWT tokens
- Private keys (-----BEGIN PRIVATE KEY-----)

### Rationale
- Current scan only checks for generic `password=`, `api_key=` patterns
- Cloud provider keys have specific formats that can be detected
- Better prevention than remediation

### Implementation
```yaml
# .pre-commit-config.yaml - Enhanced security scan
- id: security-credentials
  name: Security Scan (Hardcoded Credentials)
  entry: bash
  args:
    - -c
    - |
      # Existing patterns
      if git grep -E '(password|secret|api_key|token)\s*=\s*['\''"][^'\''\"]{5,}['\''"]' -- '*.py' '*.yaml' '*.yml' '*.sql' ':(exclude)tests/**' | grep -v -E '(YOUR_|TEST_|EXAMPLE_|PLACEHOLDER|<[A-Z_]+>)'; then
        echo "ERROR: Found potential hardcoded credentials!"
        exit 1
      fi

      # NEW: AWS keys
      if git grep -E 'AKIA[0-9A-Z]{16}' -- '*.py' '*.yaml' '*.yml'; then
        echo "ERROR: Found potential AWS access key!"
        exit 1
      fi

      # NEW: Google API keys
      if git grep -E 'AIza[0-9A-Za-z\\-_]{35}' -- '*.py' '*.yaml' '*.yml'; then
        echo "ERROR: Found potential Google API key!"
        exit 1
      fi

      # NEW: Private keys
      if git grep -E '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' -- '*'; then
        echo "ERROR: Found private key in repository!"
        exit 1
      fi

      echo "No hardcoded credentials detected"
  language: system
  pass_filenames: false
```

### Success Criteria
- [ ] AWS key pattern detection working
- [ ] Google API key pattern detection working
- [ ] Private key detection working
- [ ] No false positives in tests or documentation

### Dependencies
- None

### Timeline
- 1 hour

---

## DEF-P1-008: Database Query Optimization

### Description
Optimize database queries for production performance:
- Add indexes on frequently queried columns
- Analyze query plans for slow queries
- Implement query result caching where appropriate
- Add database connection pooling monitoring

### Rationale
- Current implementation works but not optimized for scale
- As data volume grows, unoptimized queries become bottlenecks
- Better to optimize early than refactor under load

### Implementation Areas

**1. Index Optimization** (2 hours)
```sql
-- Add indexes on frequently queried columns
CREATE INDEX idx_markets_ticker_current
  ON markets(ticker)
  WHERE row_current_ind = TRUE;

CREATE INDEX idx_positions_status_current
  ON positions(status)
  WHERE row_current_ind = TRUE;

CREATE INDEX idx_trades_executed_at
  ON trades(executed_at);
```

**2. Query Plan Analysis** (2 hours)
```python
# Add EXPLAIN ANALYZE for slow queries
# Identify queries taking >100ms
# Optimize using indexes, query rewriting, or caching
```

**3. Connection Pool Monitoring** (1-2 hours)
```python
# Add metrics to track:
# - Pool utilization (current connections / max connections)
# - Average wait time for connection
# - Query execution time distribution
```

### Success Criteria
- [ ] All frequently queried columns indexed
- [ ] No queries taking >100ms under normal load
- [ ] Connection pool metrics exposed
- [ ] Documentation updated with query optimization guide

### Dependencies
- Complete Phase 1 (need production-like data volume to test)

### Timeline
- 5-6 hours

---

## DEF-P1-009: Comprehensive Integration Tests (Live API)

### Description
Create full end-to-end integration tests using Kalshi's **demo API** (not production):
- Market fetching workflow (series → events → markets)
- Order placement and fills
- Position monitoring and updates
- Account balance tracking
- Error handling (rate limits, API errors)

### Rationale
- Current tests use mocked responses (unit tests)
- Need to verify actual API integration works
- Demo API allows testing without real money
- Catches API changes before production

### Implementation

**Test Suite Structure:**
```python
# tests/integration/test_kalshi_demo_api.py

@pytest.mark.integration
@pytest.mark.skipif(not os.getenv('KALSHI_DEMO_API_KEY'), reason="Demo API key required")
class TestKalshiDemoAPI:
    """Integration tests using Kalshi demo API."""

    def test_fetch_markets_workflow(self):
        """Test full market fetching workflow."""
        # 1. Fetch NFL series
        # 2. Fetch events for series
        # 3. Fetch markets for event
        # 4. Verify decimal precision
        # 5. Verify data structure

    def test_order_lifecycle(self):
        """Test placing, monitoring, and cancelling orders."""
        # 1. Get account balance
        # 2. Place small test order
        # 3. Monitor order status
        # 4. Cancel order
        # 5. Verify balance unchanged

    def test_rate_limiting(self):
        """Test rate limiter handles 100 req/min correctly."""
        # 1. Make 101 requests rapidly
        # 2. Verify rate limiter blocks request 101
        # 3. Verify request succeeds after waiting

    def test_error_handling(self):
        """Test API error handling (429, 500, invalid ticker, etc.)."""
        # 1. Trigger 429 error (exceed rate limit)
        # 2. Verify exponential backoff
        # 3. Trigger 404 error (invalid ticker)
        # 4. Verify error logged and raised correctly
```

**CI Integration:**
```yaml
# .github/workflows/ci.yml
jobs:
  integration-tests:
    name: Integration Tests (Demo API)
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'  # Only on PRs
    steps:
      - name: Run integration tests
        env:
          KALSHI_DEMO_API_KEY: ${{ secrets.KALSHI_DEMO_API_KEY }}
        run: pytest tests/integration/ -v --maxfail=1
```

### Success Criteria
- [ ] All integration tests pass against demo API
- [ ] Tests run in CI on pull requests
- [ ] Tests complete in <5 minutes
- [ ] Demo API credentials stored as GitHub secrets

### Dependencies
- Complete Phase 1 API client implementation
- Obtain Kalshi demo API credentials

### Timeline
- 8-10 hours (test development + CI integration)

---

## Priority Recommendations

### Start in Phase 1.5 (High Priority)
1. **DEF-P1-001: Extended Docstrings** (8-9 hours)
   - Immediate developer productivity benefit
   - Required for professional codebase standards

2. **DEF-P1-002: Fix Cross-References** (2 hours)
   - Blocking DEF-P1-005 (re-enable validate-docs hook)
   - Quick win, high impact

3. **DEF-P1-003: Add Docs to MASTER_INDEX** (3 hours)
   - Blocking DEF-P1-005 (re-enable validate-docs hook)
   - Required for documentation consistency

### Start in Phase 2 (Medium Priority)
4. **DEF-P1-006: Enhance validate_docs.py** (1 hour)
   - Blocking DEF-P1-005 (re-enable validate-docs hook)

5. **DEF-P1-004: Archive Superseded Docs** (1 hour)
   - Depends on DEF-P1-002 (cross-references fixed first)

6. **DEF-P1-005: Re-enable validate-docs Hook** (30 min)
   - Depends on DEF-P1-002, DEF-P1-003, DEF-P1-006

7. **DEF-P1-009: Integration Tests** (8-10 hours)
   - Critical for Phase 2 confidence

### Start Later (Low Priority)
8. **DEF-P1-007: Expand Security Scanning** (1 hour)
   - Nice-to-have, not blocking

9. **DEF-P1-008: Database Optimization** (5-6 hours)
   - Wait until Phase 2 (more data to test with)

---

## Success Metrics

### Phase 1.5 Completion Criteria
- [ ] All HIGH priority tasks complete (DEF-P1-001, 002, 003)
- [ ] Documentation validation fully enabled and passing
- [ ] All modules have gold standard docstrings

### Phase 2 Readiness Criteria
- [ ] Integration tests passing against demo API
- [ ] No documentation validation errors
- [ ] Security scanning enhanced

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-06 | Claude | Initial creation - 9 deferred tasks identified |

---

**END OF PHASE_1_DEFERRED_TASKS_V1.0.md**
