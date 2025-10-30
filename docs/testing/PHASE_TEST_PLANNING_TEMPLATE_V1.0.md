# Phase Test Planning Template V1.0

**Document Type:** Testing Template
**Status:** ✅ Active
**Version:** 1.0
**Created:** 2025-10-29
**Owner:** Development Team
**Purpose:** Reusable checklist template for planning phase-specific tests BEFORE starting each development phase

---

## When to Use This Template

**MANDATORY: Run this checklist at the START of every development phase, BEFORE writing any production code.**

**Triggers:**
1. **Phase Completion:** During Phase N completion, use this to plan Phase N+1 tests
2. **Session Start:** When starting first session of new phase, verify this checklist was completed
3. **Before First Commit:** If somehow skipped, run this before committing any Phase N code

**Output:** Either update existing test plan or create `docs/testing/PHASE_N_TEST_PLAN_V1.0.md`

---

## Checklist Structure

This template provides 8 sections to ensure comprehensive test coverage for each phase:

1. **Requirements Analysis** - What needs testing?
2. **Test Categories Needed** - Unit/Integration/E2E breakdown
3. **Test Infrastructure Updates** - Factories, fixtures, mocks
4. **Critical Test Scenarios** - Must-pass scenarios from user requirements
5. **Performance Baselines** - Speed/latency targets
6. **Security Test Scenarios** - Vulnerability testing
7. **Edge Cases to Test** - Boundary conditions
8. **Success Criteria** - How to know testing is complete

---

## Phase Test Planning Checklist Template

Copy this template for each phase and customize with phase-specific details.

---

### 1. Requirements Analysis

**Goal:** Identify what functionality needs testing

#### Review Phase Requirements
- [ ] List all REQ-* identifiers for this phase (from MASTER_REQUIREMENTS)
- [ ] Identify critical vs. nice-to-have requirements
- [ ] Map requirements to modules/files that will implement them
- [ ] List all new database tables/columns (if applicable)
- [ ] List all new API endpoints/clients (if applicable)
- [ ] List all new CLI commands (if applicable)

#### Identify Critical Paths
- [ ] What are the 3-5 most critical user workflows for this phase?
- [ ] What are the highest-risk components (security, money, data integrity)?
- [ ] What functionality is a prerequisite for future phases?
- [ ] What existing functionality could this phase break?

#### List New Modules
- [ ] `module1.py` - Brief description
- [ ] `module2.py` - Brief description
- [ ] (Continue for all new files)

---

### 2. Test Categories Needed

**Goal:** Plan test types and coverage

#### Unit Tests
- [ ] What pure functions need unit testing?
- [ ] What utility functions need testing?
- [ ] What data transformations need testing?
- [ ] Target coverage for unit tests: ____%

**Example:**
```python
# tests/unit/test_phase_N_utils.py
- test_decimal_conversion()
- test_validation_logic()
- test_config_parsing()
```

#### Integration Tests
- [ ] What components interact with database?
- [ ] What components make external API calls?
- [ ] What components read/write files?
- [ ] What end-to-end workflows need testing?
- [ ] Target coverage for integration tests: ____%

**Example:**
```python
# tests/integration/test_phase_N_workflow.py
- test_full_pipeline_database_to_output()
- test_api_client_with_real_responses()
- test_config_file_loading()
```

#### End-to-End Tests (if applicable)
- [ ] What complete user workflows need E2E testing?
- [ ] What cross-module interactions are critical?
- [ ] Do we need performance/load tests?

#### Mocking Strategy
- [ ] What external dependencies need mocking? (APIs, database, file system)
- [ ] What test data do we need to generate?
- [ ] What edge cases need specific mock responses?

---

### 3. Test Infrastructure Updates

**Goal:** Prepare test support code before writing tests

#### Test Fixtures (conftest.py)
- [ ] New fixtures needed:
  - [ ] `fixture_name_1` - Description
  - [ ] `fixture_name_2` - Description

#### Test Factories (tests/fixtures/factories.py)
- [ ] New factories needed:
  - [ ] `PhaseNDataFactory` - Generate test data for X
  - [ ] `PhaseNConfigFactory` - Generate config variations
  - [ ] (List all factories)

#### Mock Data Files
- [ ] Create `tests/fixtures/phase_N_responses.py` (API responses)
- [ ] Create `tests/fixtures/phase_N_sample_data.json` (if needed)
- [ ] Create `tests/fixtures/phase_N_configs/` (sample configs)

#### Test Utilities
- [ ] Create `tests/utils/phase_N_helpers.py` (if complex setup needed)
- [ ] Add helper functions to existing utilities

---

### 4. Critical Test Scenarios

**Goal:** Ensure user-specified requirements are testable

**Source:** From user requirements, MASTER_REQUIREMENTS, or project stakeholders

List all critical scenarios that MUST pass:

#### Scenario 1: [Scenario Name]
- **Requirement:** REQ-XXX-NNN
- **Description:** What functionality must work
- **Test:** Specific test to write
- **Success Criteria:** What proves it works
- **Priority:** Critical / High / Medium

**Example:**
#### Scenario 1: API Client Error Handling
- **Requirement:** REQ-API-006
- **Description:** API client must handle 4xx/5xx errors gracefully with retry logic
- **Test:** `test_api_client_retries_on_500_error()`
- **Success Criteria:**
  - Retries 3 times with exponential backoff
  - Logs each retry attempt
  - Returns clear error after max retries
- **Priority:** Critical

#### Scenario 2: [Next Scenario]
...

---

### 5. Performance Baselines

**Goal:** Establish speed/latency targets for this phase

**Note:** Performance testing detailed in Phase 0.7 (pytest-benchmark)

#### Operation Targets

| Operation | Target Time | Justification |
|-----------|-------------|---------------|
| Module initialization | <100ms | Fast startup |
| Single database query | <10ms | Acceptable latency |
| API client request | <100ms | Excluding network |
| Config file loading | <50ms | Fast startup |
| [Custom operation] | <Xms | [Why] |

#### Load Targets (if applicable)

| Scenario | Target | Justification |
|----------|--------|---------------|
| Concurrent database connections | 100+ | Connection pool size |
| Requests per second | X rps | Expected load |
| Memory usage under load | <Xmb | Resource limits |

#### Baseline Measurement Plan
- [ ] Identify operations to benchmark
- [ ] Create benchmark tests with pytest-benchmark (Phase 0.7)
- [ ] Document baseline performance in test plan
- [ ] Set regression thresholds (+10% warning, +20% fail)

---

### 6. Security Test Scenarios

**Goal:** Identify security vulnerabilities to test

**Note:** Automated security testing in Phase 0.7 (Bandit, Safety)

#### Authentication/Authorization
- [ ] API keys loaded from environment (not hardcoded)
- [ ] Credentials not logged or exposed
- [ ] Authentication failures handled securely
- [ ] Rate limiting enforced

#### Input Validation
- [ ] User input sanitized (SQL injection prevention)
- [ ] File paths validated (path traversal prevention)
- [ ] Config values validated (type checking, range checking)
- [ ] API responses validated (schema checking)

#### Data Protection
- [ ] Sensitive data encrypted at rest (if applicable)
- [ ] Secure communication (HTTPS for APIs)
- [ ] No sensitive data in logs
- [ ] Database credentials secured

#### Dependency Security
- [ ] Run `safety check` on new dependencies
- [ ] Review licenses for new packages
- [ ] No known vulnerabilities in dependencies

#### Phase-Specific Security Scenarios
- [ ] (List phase-specific security concerns)
- [ ] (E.g., "Phase 5: Circuit breaker can't be bypassed")

---

### 7. Edge Cases to Test

**Goal:** Identify boundary conditions and error paths

**Principle:** Test not just happy paths, but all the ways things can go wrong

#### Data Edge Cases
- [ ] Empty inputs (empty string, empty list, null)
- [ ] Minimum values (0, 0.0001, smallest Decimal)
- [ ] Maximum values (max int, 0.9999, largest Decimal)
- [ ] Special characters in strings (" ' ; -- \\n \\r)
- [ ] Unicode characters (if applicable)
- [ ] Very long inputs (>1000 chars, >10k items)

#### Decimal Precision Edge Cases (CRITICAL for Precog)
- [ ] Sub-penny prices (0.4275, 0.4976)
- [ ] Minimum price (0.0001)
- [ ] Maximum price (0.9999)
- [ ] Decimal arithmetic (addition, subtraction, multiplication)
- [ ] Decimal to string conversion (no float contamination)
- [ ] Decimal from API response parsing

#### System Edge Cases
- [ ] Database connection lost mid-transaction
- [ ] API returns malformed JSON
- [ ] API rate limit exceeded (429 response)
- [ ] Network timeout
- [ ] Disk full (if writing files)
- [ ] Permission denied (if file I/O)
- [ ] Configuration file missing
- [ ] Configuration file malformed (invalid YAML syntax)
- [ ] Environment variable not set

#### Business Logic Edge Cases
- [ ] Divide by zero scenarios
- [ ] Negative values where not allowed
- [ ] Concurrent modifications (race conditions)
- [ ] State transitions (can state X transition to state Y?)
- [ ] Resource exhaustion (connection pool, memory)

#### Phase-Specific Edge Cases
- [ ] (List phase-specific edge cases)
- [ ] (E.g., "Phase 1: API returns prices as integers instead of dollars")

---

### 8. Success Criteria

**Goal:** Define "done" for this phase's testing

#### Coverage Targets
- [ ] Overall code coverage: ≥80% (MANDATORY - enforced by pyproject.toml)
- [ ] Critical modules coverage: ≥85%
- [ ] New modules coverage: ≥80%

**Critical Modules for This Phase:**
1. `module1.py` - Target: 90%
2. `module2.py` - Target: 85%
3. (List critical modules)

#### Test Count Targets
- [ ] Minimum unit tests: ___ tests
- [ ] Minimum integration tests: ___ tests
- [ ] Minimum critical tests: ___ tests

#### All Critical Scenarios Tested
- [ ] Every scenario from Section 4 has passing test
- [ ] Every REQ-* from Section 1 has test coverage
- [ ] All user-specified requirements tested

#### Test Performance
- [ ] Full test suite runs in <30 seconds (local)
- [ ] Full test suite runs in <60 seconds (CI/CD)
- [ ] Unit tests run in <5 seconds
- [ ] No test marked @pytest.mark.slow unless justified

#### Quality Gates
- [ ] All tests passing (0 failures)
- [ ] No security vulnerabilities detected (Bandit clean)
- [ ] No dependency vulnerabilities (Safety clean)
- [ ] All critical tests marked with @pytest.mark.critical
- [ ] Test documentation complete (every test has docstring)

#### Documentation
- [ ] Test categories documented (which tests cover which requirements)
- [ ] Edge cases documented (why each edge case matters)
- [ ] Performance baselines documented
- [ ] Known test limitations documented (if any)

---

## After Completing Checklist

### Immediate Actions
- [ ] Update SESSION_HANDOFF.md: "Phase N test planning complete"
- [ ] (Optional) Create detailed test plan: `docs/testing/PHASE_N_TEST_PLAN_V1.0.md`
- [ ] Add test planning completion to phase deliverables checklist

### Before First Code Commit
- [ ] Verify test infrastructure ready (fixtures, factories, mocks)
- [ ] Create placeholder test files with TODOs
- [ ] Run `pytest` (should pass with 0 tests initially)

### During Development
- [ ] Reference this checklist when writing tests
- [ ] Mark checklist items complete as tests are written
- [ ] Run `./scripts/validate_all.sh` before every commit

### At Phase Completion
- [ ] Verify all checklist items marked complete
- [ ] Verify coverage meets targets
- [ ] Verify all critical scenarios tested
- [ ] Include test summary in phase completion report

---

## Example Usage

### Phase 1 Test Planning

```markdown
# Phase 1 Test Plan V1.0

Based on PHASE_TEST_PLANNING_TEMPLATE_V1.0.md

## 1. Requirements Analysis

### Phase Requirements
- REQ-API-001: Kalshi API Integration
- REQ-API-002: RSA-PSS Authentication
- REQ-API-003: ESPN API Integration
- REQ-API-004: Balldontlie API Integration
- REQ-API-005: API Rate Limit Management
- REQ-API-006: API Error Handling
- REQ-CLI-001: Typer CLI Framework
- REQ-CLI-002: Config Loader Command
- REQ-CLI-003: Market Fetch Command
- REQ-CLI-004: Balance Check Command
- REQ-CLI-005: Help and Version Commands

### Critical Paths
1. Kalshi authentication (blocks all API access)
2. Decimal price parsing from API (blocks trading accuracy)
3. Rate limiting (blocks API compliance)

### New Modules
- `api_connectors/kalshi_client.py` - Kalshi API wrapper
- `api_connectors/espn_client.py` - ESPN API wrapper
- `api_connectors/balldontlie_client.py` - NBA stats API
- `main.py` - Typer CLI entry point
- `utils/config_loader.py` - YAML config loading

## 2. Test Categories Needed

### Unit Tests (Target: 85%)
- `test_decimal_parsing.py` - Decimal conversion utilities
- `test_rate_limiter.py` - Rate limiting logic
- `test_config_loader.py` - YAML parsing and validation
- `test_cli_commands.py` - CLI argument parsing

### Integration Tests (Target: 80%)
- `test_kalshi_client.py` - API client with mocked responses
- `test_espn_client.py` - ESPN API with mocked responses
- `test_cli_integration.py` - Full CLI workflow
- `test_config_override.py` - Config precedence

### Mocking Strategy
- Mock all HTTP requests (responses library or pytest-httpx)
- Mock database connections for CLI tests
- Mock file system for config tests

... (continue with remaining sections)
```

---

## Integration with Workflow

This template integrates with the Precog workflow at multiple points:

### 1. Phase Completion (Proactive)
**Location:** `docs/utility/PHASE_COMPLETION_ASSESSMENT_PROTOCOL_V1.0.md` Step 8

When finishing Phase N:
- Review Phase N+1 deliverables
- Use this template to plan Phase N+1 tests
- Document in SESSION_HANDOFF.md

### 2. DEVELOPMENT_PHASES (Reference)
**Location:** `docs/foundation/DEVELOPMENT_PHASES_V1.4.md`

Each phase includes:
```markdown
### Before Starting This Phase - TEST PLANNING CHECKLIST ⚠️

**MANDATORY: Complete this checklist BEFORE writing Phase N code**

Reference: `docs/testing/PHASE_TEST_PLANNING_TEMPLATE_V1.0.md`

... (phase-specific customized checklist)
```

### 3. Session Start (Reminder)
**Location:** `CLAUDE.md` Section 3 "Starting a New Session"

Step 2: Check Current Phase
- **IF STARTING NEW PHASE:** Run "Before Starting Phase N" test planning checklist from DEVELOPMENT_PHASES

### 4. Validation Script (Future - Phase 0.7)
**Location:** `scripts/validate_phase_readiness.py`

Automated check that test planning was completed:
- Coverage baselines documented
- Critical scenarios identified
- Test infrastructure ready

---

## Template Maintenance

### When to Update This Template

- **After completing any phase:** Add lessons learned
- **After discovering new edge case category:** Add to Section 7
- **After implementing new test infrastructure:** Add to Section 3
- **When test requirements evolve:** Update sections to match current best practices

### Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-29 | Initial template based on Phase 0.6c testing infrastructure |

---

## References

- **Test Framework:** `docs/foundation/TESTING_STRATEGY_V2.0.md`
- **Validation Infrastructure:** `docs/foundation/VALIDATION_LINTING_ARCHITECTURE_V1.0.md`
- **Requirements:** `docs/foundation/MASTER_REQUIREMENTS_V2.9.md`
- **Phase Roadmap:** `docs/foundation/DEVELOPMENT_PHASES_V1.4.md`
- **Phase Completion:** `docs/utility/PHASE_COMPLETION_ASSESSMENT_PROTOCOL_V1.0.md`

---

**END OF PHASE_TEST_PLANNING_TEMPLATE_V1.0.md**
