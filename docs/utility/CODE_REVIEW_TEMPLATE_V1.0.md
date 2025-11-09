# Universal Code Review Template

**Version:** 1.0
**Created:** 2025-11-09
**Purpose:** Standardized checklist for all code reviews (PRs, feature implementations, phase completions)
**Source:** Consolidated from CLAUDE.md, Phase Completion Protocol, and Perplexity recommendations
**Applies To:** All phases (Phase 1-10)

---

## How to Use This Template

**For Pull Requests:**
- Reviewer copies relevant sections below
- Checks each box while reviewing code
- Documents findings in PR comments
- All boxes must be checked before approval

**For Feature Implementation:**
- Developer uses as self-review before creating PR
- Ensures all requirements met before submitting
- Reduces review cycles and CI failures

**For Phase Completion:**
- Part of Phase Completion Protocol (CLAUDE.md Section 9)
- Comprehensive review of all phase deliverables
- Documents completion evidence for each category

---

## 1. Requirements Traceability

**Purpose:** Ensure all work implements documented requirements and aligns with architecture decisions.

### Requirements Coverage
- [ ] **All REQ-XXX-NNN IDs linked in code comments**
  - Each function/class references relevant requirement IDs
  - Example: `# Implements REQ-API-001: Kalshi API Integration`
- [ ] **All requirements fully implemented**
  - Verify implementation matches requirement description in MASTER_REQUIREMENTS
  - No partial implementations without documented deferral
- [ ] **Test coverage for each requirement**
  - At least one test per requirement
  - Tests validate requirement acceptance criteria
- [ ] **ADR alignment verified**
  - Implementation follows relevant architecture decisions
  - No deviations without documented justification (new ADR)

### Traceability Validation
- [ ] **MASTER_REQUIREMENTS status updated**
  - Status changed from 🔵 Planned → 🟡 In Progress → ✅ Complete
- [ ] **REQUIREMENT_INDEX synchronized**
  - Same status as MASTER_REQUIREMENTS
- [ ] **DEVELOPMENT_PHASES tasks marked complete**
  - Checkboxes updated for completed deliverables
- [ ] **Cross-references working**
  - All doc references point to existing files
  - All version numbers current

**Evidence Required:**
- List of REQ IDs implemented: `REQ-___-___, REQ-___-___, ...`
- List of ADRs followed: `ADR-___, ADR-___, ...`

---

## 2. Test Coverage

**Purpose:** Ensure comprehensive testing meets project standards (≥80% coverage minimum).

### Coverage Metrics
- [ ] **Overall coverage ≥80%**
  - Run: `pytest tests/ --cov=. --cov-report=term-missing`
  - Check coverage percentage in output
- [ ] **Module-specific targets met**
  - API connectors: ≥90% coverage (critical path)
  - Business logic: ≥85% coverage (trading, positions, strategies)
  - Infrastructure: ≥80% coverage (config, logging, database)
- [ ] **All functions covered**
  - No critical functions with 0% coverage
  - Acceptable exceptions: `if __name__ == "__main__"` blocks

### Test Types
- [ ] **Unit tests passing**
  - Tests for individual functions/classes
  - Mocked external dependencies (API calls, database)
  - Fast execution (<5 seconds total)
- [ ] **Integration tests passing** (if applicable)
  - Tests for component interactions
  - Database integration, API integration
  - Moderate execution (<30 seconds total)
- [ ] **Property-based tests** (for trading logic)
  - Hypothesis tests for mathematical invariants
  - Examples: Position ≤ bankroll, bid < ask, probability ∈ [0,1]
  - See Pattern 10 in CLAUDE.md
- [ ] **Edge cases tested**
  - Boundary conditions (0, 1, max values)
  - Error conditions (network failures, invalid inputs)
  - Race conditions (concurrent updates)

### Test Quality
- [ ] **All tests passing**
  - Run: `pytest tests/ -v`
  - 100% pass rate (no skipped tests except documented)
- [ ] **Tests are deterministic**
  - No flaky tests (random failures)
  - Reproducible failures
- [ ] **Tests have clear assertions**
  - Each test validates specific behavior
  - Assertion messages explain what's being tested
- [ ] **Tests follow naming convention**
  - `test_<function_name>_<scenario>` (e.g., `test_calculate_kelly_size_negative_edge`)

**Evidence Required:**
- Coverage percentage: `____%`
- Test count: `___ passing, ___ skipped`
- Module coverage details:
  ```
  module_name.py: ___%
  another_module.py: ___%
  ```

---

## 3. Code Quality

**Purpose:** Ensure code follows project standards, is maintainable, and uses correct patterns.

### Linting & Type Checking
- [ ] **Ruff lint passing (no errors)**
  - Run: `ruff check .`
  - All errors fixed (warnings acceptable if documented)
- [ ] **Ruff format applied**
  - Run: `ruff format .`
  - Consistent code formatting
- [ ] **Mypy type checking passing**
  - Run: `mypy .`
  - All type hints correct
  - No `type: ignore` without justification

### Critical Patterns (CLAUDE.md)
- [ ] **Pattern 1: Decimal Precision** ✅
  - **NO FLOAT for prices** - All prices use `Decimal("0.4975")`
  - All database columns: `DECIMAL(10,4)` not `FLOAT`
  - All config files: String format `"0.05"` not float `0.05`
- [ ] **Pattern 2: Dual Versioning** ✅
  - SCD Type 2: Query with `WHERE row_current_ind = TRUE`
  - Immutable versions: Create new version, never modify `config` JSONB
- [ ] **Pattern 3: Trade Attribution** ✅
  - Every trade links to exact `strategy_id` and `model_id`
  - Full version details queryable
- [ ] **Pattern 4: Security** ✅
  - NO hardcoded credentials (`os.getenv()` only)
  - All secrets in environment variables
  - `.env` in `.gitignore`
- [ ] **Pattern 6: TypedDict for API Responses** ✅
  - All API responses typed with TypedDict classes
  - No untyped `Dict` returns

### Code Structure
- [ ] **Functions are focused**
  - Single Responsibility Principle
  - Functions ≤50 lines (complex logic may exceed)
- [ ] **No code duplication**
  - Extract common logic to shared functions
  - DRY (Don't Repeat Yourself) principle
- [ ] **Meaningful variable names**
  - Descriptive names (not `x`, `tmp`, `data`)
  - Follow Python naming conventions (snake_case)
- [ ] **No commented-out code**
  - Remove dead code (use git history for recovery)
- [ ] **No debug artifacts**
  - No `print()` statements (use logger)
  - No `breakpoint()` or `pdb.set_trace()`

**Evidence Required:**
- Ruff output: `All checks passed!` or list of warnings with justification
- Mypy output: `Success: no issues found` or list of errors with justification

---

## 4. Security

**Purpose:** Ensure no security vulnerabilities, hardcoded credentials, or sensitive data exposure.

### Credential Management
- [ ] **No hardcoded credentials**
  - Run: `git grep -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]" -- '*.py' '*.yaml' '*.sql'`
  - Expected: No matches (or only `os.getenv()` lines)
- [ ] **All credentials from environment variables**
  - `os.getenv('KALSHI_API_KEY')` pattern used
  - Validation raises error if missing
- [ ] **Secrets management documented**
  - `.env.template` updated with new variables
  - README documents required secrets
- [ ] **.env file NOT committed**
  - Check: `git diff --cached --name-only | grep "\.env$"`
  - Expected: No output (or "✅ No .env")

### SQL Injection Prevention
- [ ] **All queries use parameterized statements**
  - No string concatenation: ❌ `f"SELECT * FROM users WHERE id = {user_id}"`
  - Use placeholders: ✅ `cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))`
- [ ] **No raw SQL from user input**
  - All user inputs sanitized
  - ORM or parameterized queries only

### API Security
- [ ] **API authentication implemented**
  - Kalshi: RSA-PSS signature authentication (ADR-047)
  - ESPN/Balldontlie: API key in headers
- [ ] **Rate limiting implemented**
  - Kalshi: 100 req/min token bucket
  - Prevents API abuse
- [ ] **Sensitive data not logged**
  - No API keys in logs
  - No passwords in error messages
  - Mask PII in logs (ADR-072: Privacy-Preserving Logging)

### Data Protection
- [ ] **Decimal precision for financial data** (Pattern 1)
  - All prices stored as `DECIMAL(10,4)`
  - No float contamination in YAML configs
- [ ] **No sensitive data in version control**
  - Check: `git log --all --full-history -- '*secret*' '*key*' '*.env'`
  - Expected: No matches (or only `.env.template`)

**Evidence Required:**
- Security scan output: `No hardcoded credentials found`
- List of environment variables used: `KALSHI_API_KEY, DB_PASSWORD, ...`

---

## 5. Documentation

**Purpose:** Ensure all documentation updated, version numbers incremented, cross-references valid.

### Code Documentation
- [ ] **Docstrings educational** (Pattern 7)
  - Clear description of what function does
  - Args/Returns documented with types
  - Educational Note explaining WHY pattern matters
  - Examples showing correct AND incorrect usage
  - Related references (ADRs, REQs, docs)
- [ ] **Type hints present**
  - All function signatures typed
  - Return types specified
  - Complex types use TypedDict (Pattern 6)
- [ ] **Comments explain WHY, not WHAT**
  - Code is self-documenting (what)
  - Comments explain rationale (why)

### Foundation Documents
- [ ] **MASTER_REQUIREMENTS updated** (if requirements changed)
  - New REQs added with proper format
  - Existing REQs status updated (🔵 → 🟡 → ✅)
  - Version number incremented (V2.11 → V2.12)
- [ ] **REQUIREMENT_INDEX synchronized**
  - All REQs in MASTER_REQUIREMENTS also in REQUIREMENT_INDEX
  - Status matches exactly
- [ ] **ARCHITECTURE_DECISIONS updated** (if ADRs added)
  - New ADRs follow sequential numbering
  - Cross-references to related REQs
  - Version number incremented (V2.12 → V2.13)
- [ ] **ADR_INDEX synchronized**
  - All ADRs in ARCHITECTURE_DECISIONS also in ADR_INDEX
- [ ] **DEVELOPMENT_PHASES updated**
  - Tasks marked complete
  - Phase progress percentage updated
  - Version number incremented (V1.5 → V1.6) if major changes
- [ ] **PROJECT_OVERVIEW updated** (if architecture changed)
  - System architecture diagram current
  - Tech stack list current
- [ ] **MASTER_INDEX updated** (if filenames changed)
  - All new documents listed
  - All renamed documents noted
  - Version numbers correct

### Document Cohesion (CLAUDE.md Section 5)
- [ ] **Update Cascade Rules followed**
  - All downstream documents updated when upstream changes
  - Example: New REQ → REQUIREMENT_INDEX + DEVELOPMENT_PHASES
- [ ] **Cross-references valid**
  - Run: `grep -r "\.md" docs/foundation/*.md`
  - All references point to existing files
- [ ] **Version numbers consistent**
  - Header version matches filename
  - All references use correct version

### Session Documentation
- [ ] **SESSION_HANDOFF.md updated**
  - This session completed section
  - Files modified list
  - Next session priorities
- [ ] **CLAUDE.md updated** (if major milestone)
  - Current status section
  - Phase progress updated

**Evidence Required:**
- List of documents updated: `MASTER_REQUIREMENTS V2.11→V2.12, DEVELOPMENT_PHASES V1.5→V1.6, ...`
- Validation: `All cross-references valid, zero broken links`

---

## 6. Performance

**Purpose:** Ensure no obvious performance regressions, optimizations justified.

### Database Performance
- [ ] **Queries optimized**
  - Indexes exist on frequently queried columns
  - No N+1 query patterns
  - `EXPLAIN ANALYZE` run on complex queries
- [ ] **Connection pooling configured**
  - SQLAlchemy pool size appropriate
  - No connection leaks
- [ ] **Batch operations used**
  - Bulk inserts instead of individual inserts
  - Example: `session.bulk_insert_mappings()`

### API Performance
- [ ] **Rate limits respected**
  - Kalshi: 100 req/min token bucket
  - No API rate limit violations
- [ ] **Caching implemented** (if applicable)
  - Frequently accessed data cached
  - Cache invalidation strategy documented
- [ ] **Timeouts configured**
  - All API requests have timeouts
  - Prevents hanging on slow responses

### Code Performance
- [ ] **No obvious inefficiencies**
  - No unnecessary loops
  - No repeated calculations (memoize if needed)
  - No blocking I/O in async code
- [ ] **Algorithm complexity acceptable**
  - Time complexity O(n) or better for hot paths
  - Space complexity reasonable

### Performance Baselines (Phase 5+ Only)
- [ ] **Profiling completed** (if performance-critical)
  - Run: `python -m cProfile -o profile.stats main.py`
  - Hotspots identified (functions >10% total time)
- [ ] **Latency targets met** (Phase 5 trading execution)
  - CRITICAL exits: <10 seconds
  - HIGH exits: <30 seconds
  - MEDIUM exits: <60 seconds
  - Model inference: <200ms
  - Feature extraction: <500ms
  - End-to-end: <2 seconds

**Note:** Phase 1-4 do NOT require performance optimization (see CLAUDE.md Section 9 Step 8a). Focus on correctness, not speed.

**Evidence Required:**
- Performance validation: `No obvious inefficiencies found` or `Profiling shows acceptable performance`
- If Phase 5+: `Latency targets: CRITICAL <10s ✅, HIGH <30s ✅, MEDIUM <60s ✅`

---

## 7. Error Handling

**Purpose:** Ensure graceful degradation, comprehensive logging, user-friendly error messages.

### Exception Handling
- [ ] **All exceptions caught**
  - No bare `except:` clauses (catch specific exceptions)
  - No uncaught exceptions in critical paths
- [ ] **Exceptions logged**
  - Use `logger.exception()` for stack traces
  - Log context (inputs, state) for debugging
- [ ] **Graceful degradation**
  - System continues operating after non-critical errors
  - Example: Skip bad market data, log error, continue processing
- [ ] **User-friendly error messages**
  - CLI errors explain what went wrong and how to fix
  - API errors return structured error responses

### Logging
- [ ] **Appropriate log levels**
  - DEBUG: Detailed diagnostic info
  - INFO: General informational messages
  - WARNING: Potential issues, degraded functionality
  - ERROR: Errors that need attention
  - CRITICAL: System failures
- [ ] **No sensitive data in logs**
  - No API keys, passwords, or PII
  - Mask sensitive fields (Pattern 4)
- [ ] **Structured logging used**
  - Use structlog for consistent formatting
  - Include context: `logger.info("event", user_id=123, market_id="ABC")`

### Retry Logic
- [ ] **Transient failures retried**
  - API requests: 3 retries with exponential backoff
  - Database operations: Retry on connection loss
  - Critical operations: 10 retries (ADR-051)
- [ ] **Retry limits enforced**
  - Max retries configured (prevent infinite loops)
  - Backoff strategy documented

### Circuit Breakers (Phase 3+)
- [ ] **Circuit breakers implemented** (if applicable)
  - 3 consecutive failures → 60 second cooldown
  - Prevents cascading failures
  - Alert on circuit break

**Evidence Required:**
- Error handling validation: `All critical paths have exception handling`
- Logging validation: `No sensitive data logged, appropriate levels used`
- Retry validation: `3 retries with exponential backoff (1s, 2s, 4s)`

---

## Review Completion Checklist

### Final Validation
- [ ] **All 7 categories checked**
  - Requirements Traceability ✅
  - Test Coverage ✅
  - Code Quality ✅
  - Security ✅
  - Documentation ✅
  - Performance ✅
  - Error Handling ✅
- [ ] **All evidence documented**
  - Coverage percentages recorded
  - Test counts recorded
  - Security scan outputs recorded
- [ ] **Findings communicated**
  - PR comments added
  - Issues created for deferred items
  - Session handoff updated

### Approval Criteria
- [ ] **Zero critical issues**
  - No security vulnerabilities
  - No test failures
  - No hardcoded credentials
- [ ] **Minor issues documented**
  - Issues created for non-blocking items
  - Target phase assigned
- [ ] **Documentation complete**
  - All foundation documents updated
  - All cross-references valid
  - All version numbers incremented

---

## Related Documentation

**Foundation Documents:**
- **DEVELOPMENT_PHILOSOPHY_V1.1.md** - Core development principles
  - Section 1: Test-Driven Development (80%+ coverage required)
  - Section 2: Defense in Depth (multiple validation layers)
  - Section 3: Documentation-Driven Development (requirements before code)
  - Section 6: Explicit Over Clever (code clarity over brevity)
  - Section 9: Security by Default (no hardcoded credentials)
  - Section 10: Anti-Patterns to Avoid (detection checklist)
  - Section 11: Test Coverage Accountability (explicit coverage targets)
- CLAUDE.md - Critical patterns and workflow
- MASTER_REQUIREMENTS - Requirement definitions
- ARCHITECTURE_DECISIONS - ADR definitions
- DEVELOPMENT_PHASES - Phase deliverables and test planning checklists

**Utility Documents:**
- SECURITY_REVIEW_CHECKLIST.md - Detailed security review
- INFRASTRUCTURE_REVIEW_TEMPLATE_V1.0.md - Infrastructure review
- Handoff_Protocol_V1.1.md - Phase completion protocol

**Guides:**
- VERSIONING_GUIDE_V1.0.md - Strategy/model versioning
- CONFIGURATION_GUIDE_V3.1.md - YAML configuration

---

**Template Version:** 1.0
**Last Updated:** 2025-11-09
**Maintained By:** Development Team
**Review Cycle:** Update template when new patterns added to CLAUDE.md

---

**END OF CODE_REVIEW_TEMPLATE_V1.0.md**
