# Development Phases & Roadmap

---
**Version:** 1.4
**Last Updated:** 2025-10-29
**Status:** ✅ Current
**Changes in v1.4:**
- **PHASE 0.6B COMPLETION**: Added Phase 0.6b (Documentation Correction & Security) - Documentation standardization complete
- **PHASE 0.6C COMPLETION**: Added Phase 0.6c (Validation & Testing Infrastructure) - Automated validation and testing infrastructure complete
- **PHASE 0.7 PLANNING**: Added Phase 0.7 (CI/CD Integration & Advanced Testing) - GitHub Actions, Codecov, mutation testing, property-based testing
- Added 8 new ADRs (ADR-038 through ADR-045) for validation, testing, and CI/CD
- Added 11 new requirements (REQ-TEST-005-008, REQ-VALIDATION-001-003, REQ-CICD-001-003)
- Created TESTING_STRATEGY V2.0, VALIDATION_LINTING_ARCHITECTURE V1.0
- Updated all foundation documents (ARCHITECTURE_DECISIONS V2.8, MASTER_REQUIREMENTS V2.9, ADR_INDEX V1.2, REQUIREMENT_INDEX V1.2)
- Current status: Phase 0.6c complete, Phase 0.7 planned, Phase 1 awaits Phase 0.7 completion
**Changes in v1.3:**
- **MAJOR**: Split Phase 5 into Phase 5a (Monitoring & Evaluation, Weeks 10-12) and Phase 5b (Execution & Walking, Weeks 13-14)
- Updated Phase 0.5 to 100% complete (Days 1-10 finished)
- Added comprehensive Phase 5a requirements (REQ-MON-*, REQ-EXIT-*)
- Added Phase 5b requirements (REQ-EXEC-* with price walking algorithm)
- Updated database schema to V1.5 (position_exits, exit_attempts tables)
- Added 10 exit conditions with priority hierarchy
- Created VERSIONING_GUIDE, TRAILING_STOP_GUIDE, POSITION_MANAGEMENT_GUIDE
- Updated timeline: Phase 5 total now 4 weeks (was 6 weeks)

**Changes in v1.2:** Added Phase 0.5 (Foundation Enhancement) and Phase 1.5 (Foundation Validation); updated to reflect database schema V1.4 with versioning system; updated timeline to include new phases
**Changes in v1.1:** Clarified Phase 2 (live data), Phase 3 (processing only, no edges), Phase 4 (odds/edges/historical loader); added new deliverables (GLOSSARY Phase 0, DEVELOPER_ONBOARDING Phase 0, DEPLOYMENT_GUIDE Phase 1, MODEL_VALIDATION/BACKTESTING_PROTOCOL Phase 4, USER_GUIDE Phase 5); updated Phase 0 to 100% complete.
---

## Timeline Overview (Realistic Part-Time Estimate)

**Total to Phase 10:** ~1.5-2 years (82 weeks @ 12 hours/week)
**MVP Trading (Phase 5):** ~8 months from Phase 0 start (includes Phase 0.5, 0.6b, 0.6c, 0.7, and 1.5)
**Current Status:** Phase 0.6c ✅ **100% COMPLETE** (Validation & testing infrastructure ready; Phase 0.7 planned; ready for Phase 1)

---

## Phase Structure

Each phase has codenames from sci-fi references for fun tracking. Phases are sequential with clear dependencies (see Phase Dependencies Table in PROJECT_OVERVIEW_V1.2.md).

---

## Phase 0: Foundation (Codename: "Genesis")

**Duration:** 8 weeks  
**Status:** ✅ **100% COMPLETE** (Session 7)  
**Goal:** Create comprehensive documentation, configuration system, and project foundation

### Deliverables

#### Core Documentation
- [✅] MASTER_REQUIREMENTS_V2.1.md (complete system requirements)
- [✅] PROJECT_OVERVIEW_V1.2.md (architecture, tech stack, data flow)
- [✅] MASTER_INDEX_V2.1.md (document inventory with locations and phase ties)
- [✅] ARCHITECTURE_DECISIONS_V2.1.md (ADRs 1-15+)
- [✅] DATABASE_SCHEMA_SUMMARY_V1.1.md (complete schema with SCD Type 2)
- [✅] CONFIGURATION_GUIDE_V2.1.md (YAML patterns, DECIMAL format)
- [✅] GLOSSARY_V1.0.md (terminology: EV, Kelly, edge, Elo, etc.)

#### API & Integration
- [✅] API_INTEGRATION_GUIDE_V1.0.md (Kalshi/ESPN/Balldontlie, RSA-PSS auth)
- [✅] KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md (critical reference)
- [✅] ODDS_RESEARCH_COMPREHENSIVE.md (historical odds methodology)

#### Configuration Files
- [✅] system.yaml (DB, logging, API settings)
- [✅] trading.yaml (Kelly fractions, DECIMAL examples)
- [✅] odds_models.yaml (Elo, regression, ML, historical_lookup ensemble)
- [✅] position_management.yaml (position sizing, CI adjustments)
- [✅] trade_strategies.yaml (entry/exit strategies, halftime_entry)
- [✅] markets.yaml (market filtering, research_gap_flag)
- [✅] data_sources.yaml (API endpoints, nflfastR config)
- [✅] .env.template (all Phase 1-10 API keys placeholders)

#### Process & Utility
- [✅] DEVELOPMENT_PHASES_V1.1.md (this file - roadmap)
- [✅] ENVIRONMENT_CHECKLIST_V1.1.md (Windows 11 setup, Parts 1-7)
- [✅] REQUIREMENTS_AND_DEPENDENCIES_V1.0.md (comprehensive vs. sample reqs.txt)
- [✅] VERSION_HEADERS_GUIDE_V2.1.md (version control standards)
- [✅] Handoff_Protocol_V1.0.md (session management, token budget, phase assessment)
- [✅] PROJECT_STATUS.md (living status tracker)
- [✅] DOCUMENT_MAINTENANCE_LOG.md (change tracking with impacts)
- [✅] DEVELOPER_ONBOARDING_V1.0.md (merged with ENVIRONMENT_CHECKLIST, onboarding steps)

### Tasks Completed
1. ✅ Created comprehensive system architecture
2. ✅ Designed database schema with SCD Type 2
3. ✅ Documented all API integrations
4. ✅ Created 7 YAML configuration files
5. ✅ Established version control and handoff systems
6. ✅ Streamlined documentation (73% reduction, 11 docs → 4)
7. ✅ Integrated historical model into configs
8. ✅ Set up developer onboarding process

### Success Criteria
- [✅] Complete documentation for all foundational systems
- [✅] Clear architecture patterns established
- [✅] Risk mitigation strategies defined
- [✅] All configuration files created and validated
- [✅] Handoff system tested and working (3-upload, <10 min)
- [✅] Phase dependencies mapped and documented

**Phase 0 Assessment:** ✅ PASSED (see SESSION_7_HANDOFF.md)

---

## Phase 0.5: Foundation Enhancement (Codename: "Upgrade")

**Duration:** 3 weeks
**Target:** October 2025
**Status:** ✅ **100% COMPLETE**
**Goal:** Enhance foundation with versioning system and trailing stops before Phase 1 implementation

### Dependencies
- Requires Phase 0: 100% complete ✅

### Tasks

#### Database Schema V1.5 (Days 1-2) ✅
- [✅] Create `strategies` table (immutable versions)
- [✅] Create `probability_models` table (immutable versions)
- [✅] Add `trailing_stop_state` JSONB to positions
- [✅] Add `strategy_id`, `model_id` FKs to edges and trades
- [✅] Create helper views (active_strategies, active_models, trade_attribution)
- [✅] Apply migration to precog_dev database
- [✅] Verify migration success

#### Documentation Updates (Days 1-10) ✅
- [✅] Day 1: DATABASE_SCHEMA_SUMMARY V1.4
- [✅] Day 2: MASTER_REQUIREMENTS V2.4, ARCHITECTURE_DECISIONS V2.4 (ADRs 18-23)
- [✅] Day 3: PROJECT_OVERVIEW V1.4, DEVELOPMENT_PHASES V1.2
- [✅] Day 4: position_management.yaml V2.0, probability_models.yaml V2.0, trade_strategies.yaml V2.0
- [✅] Day 5: MASTER_REQUIREMENTS V2.5, DATABASE_SCHEMA_SUMMARY V1.5
- [✅] Day 6: CONFIGURATION_GUIDE V3.1 (comprehensive)
- [✅] Day 7: VERSIONING_GUIDE_V1.0.md, TRAILING_STOP_GUIDE_V1.0.md
- [✅] Day 8: POSITION_MANAGEMENT_GUIDE_V1.0.md, DEVELOPMENT_PHASES V1.3
- [✅] Day 9: Database schema V1.5 applied, MASTER_INDEX V2.3
- [✅] Day 10: Validation tools, final review

### Deliverables
- [✅] Database schema V1.5 applied and verified
- [✅] position_exits table (tracks exit events)
- [✅] exit_attempts table (tracks price walking attempts)
- [✅] Updated foundational documentation (MASTER_REQUIREMENTS V2.5, ARCHITECTURE_DECISIONS V2.4)
- [✅] Updated planning documentation (PROJECT_OVERVIEW V1.4, DEVELOPMENT_PHASES V1.3)
- [✅] VERSIONING_GUIDE_V1.0.md (immutable versions, A/B testing)
- [✅] TRAILING_STOP_GUIDE_V1.0.md (progressive tightening, JSONB state)
- [✅] POSITION_MANAGEMENT_GUIDE_V1.0.md (10 exit conditions, complete lifecycle)
- [✅] Updated CONFIGURATION_GUIDE V3.1 with all Phase 5 enhancements
- [✅] All 3 YAML files updated to V2.0 (versioning + monitoring + exits)
- [✅] Updated MASTER_INDEX to V2.3

### Success Criteria
- [✅] Schema V1.5 deployed to precog_dev
- [✅] All new tables and columns created successfully
- [✅] All documentation updated to reflect versioning system
- [✅] Implementation guides available for Phase 1.5/4/5
- [✅] Architecture decisions documented (ADR-018 through ADR-023)
- [✅] 10 exit conditions documented with priority hierarchy
- [✅] Phase 5 requirements fully specified (REQ-MON-*, REQ-EXIT-*, REQ-EXEC-*)

**Architectural Decision:** Immutable Versions (ADR-019)
- Strategy and model configs are IMMUTABLE once created
- To change config: Create new version (v1.0 → v1.1)
- Enables A/B testing integrity and precise trade attribution
- NO row_current_ind in versioned tables (versions don't supersede each other)

---

## Phase 0.6b: Documentation Correction & Security (Codename: "Rectify")

**Duration:** 1 week
**Target:** October 2025
**Status:** ✅ **100% COMPLETE**
**Goal:** Standardize documentation filenames and enhance security practices

### Dependencies
- Requires Phase 0.5: 100% complete ✅

### Tasks
- [✅] Remove PHASE_ prefixes from supplementary document filenames
- [✅] Standardize all supplementary docs to V1.0 format
- [✅] Update all cross-references to use new standardized names
- [✅] Create comprehensive security review checklist
- [✅] Enhance .gitignore for sensitive files
- [✅] Document security scanning procedures
- [✅] Update MASTER_INDEX with new document names

### Deliverables
- [✅] Standardized supplementary documentation filenames
- [✅] SECURITY_REVIEW_CHECKLIST.md
- [✅] Enhanced .gitignore
- [✅] Updated MASTER_REQUIREMENTS V2.8
- [✅] Updated ARCHITECTURE_DECISIONS V2.7
- [✅] Updated ADR_INDEX V1.1

### Success Criteria
- [✅] All supplementary docs use consistent naming (FEATURE_NAME_SPEC_V1.0.md)
- [✅] Zero broken cross-references
- [✅] Security checklist covers all critical areas
- [✅] All references updated in foundation documents

**ADRs:** ADR-030 through ADR-034 (Database architecture refinements)

---

## Phase 0.6c: Validation & Testing Infrastructure (Codename: "Sentinel")

**Duration:** 1 week
**Target:** October 2025
**Status:** ✅ **100% COMPLETE**
**Goal:** Implement automated validation and testing infrastructure for code quality and documentation consistency

### Dependencies
- Requires Phase 0.6b: 100% complete ✅

### Tasks

#### Code Quality Automation
- [✅] Adopt Ruff for unified linting and formatting (10-100x faster than black+flake8)
- [✅] Configure comprehensive pyproject.toml (50+ rule categories)
- [✅] Create validation scripts (validate_quick.sh, validate_all.sh)
- [✅] Implement cross-platform compatibility (python -m module pattern)
- [✅] Replace Unicode emoji with ASCII for Windows compatibility

#### Documentation Validation
- [✅] Create validate_docs.py for automated consistency checks
- [✅] Create fix_docs.py for auto-fixing simple issues
- [✅] Validate ADR_INDEX ↔ ARCHITECTURE_DECISIONS consistency
- [✅] Validate REQUIREMENT_INDEX ↔ MASTER_REQUIREMENTS consistency
- [✅] Validate MASTER_INDEX accuracy (filenames, versions, locations)
- [✅] Check version header format and filename alignment

#### Testing Infrastructure
- [✅] Configure pytest with comprehensive plugins (pytest-cov, pytest-html, pytest-asyncio, pytest-mock, pytest-xdist)
- [✅] Create test_fast.sh for rapid unit testing (~0.3s)
- [✅] Create test_full.sh for comprehensive testing with coverage (~30s)
- [✅] Implement timestamped HTML test reports
- [✅] Add factory-boy and faker for test data generation

#### Security Scanning
- [✅] Integrate credential scanning into validation pipeline
- [✅] Exclude tests/ from security scans (test credentials acceptable)
- [✅] Include scripts/ in security scans (production code)
- [✅] Check for .env files staged for commit

#### Layered Validation Architecture
- [✅] Fast validation layer (~3 seconds): Ruff lint, Ruff format, Mypy, Doc validation
- [✅] Comprehensive validation layer (~60 seconds): Fast validations + full tests + security scans
- [✅] Clear usage guidance (fast for development, comprehensive for commits)

### Deliverables
- [✅] scripts/validate_quick.sh - Fast 3-second validation
- [✅] scripts/validate_all.sh - Comprehensive 60-second validation
- [✅] scripts/test_fast.sh - Rapid unit tests
- [✅] scripts/test_full.sh - Full test suite with coverage
- [✅] scripts/validate_docs.py - Documentation consistency validation
- [✅] scripts/fix_docs.py - Auto-fix documentation issues
- [✅] pyproject.toml - Unified tool configuration
- [✅] Updated TESTING_STRATEGY V2.0.md
- [✅] Created VALIDATION_LINTING_ARCHITECTURE_V1.0.md
- [✅] Updated ARCHITECTURE_DECISIONS V2.8 (ADR-038 through ADR-041)
- [✅] Updated ADR_INDEX V1.2
- [✅] Updated MASTER_REQUIREMENTS V2.9 (REQ-TEST-005, REQ-VALIDATION-001-003)
- [✅] Updated REQUIREMENT_INDEX V1.2

### Success Criteria
- [✅] validate_quick.sh runs in <5 seconds
- [✅] validate_all.sh completes in <90 seconds
- [✅] All validation scripts work cross-platform (Windows/Linux/Mac)
- [✅] Documentation validation catches inconsistencies
- [✅] Test infrastructure supports HTML reports and coverage tracking
- [✅] Security scans detect hardcoded credentials

**ADRs:**
- ADR-038: Ruff for Code Quality Automation (10-100x faster)
- ADR-039: Test Result Persistence Strategy (timestamped HTML reports)
- ADR-040: Documentation Validation Automation (prevent drift)
- ADR-041: Layered Validation Architecture (fast 3s + comprehensive 60s)

**Requirements:** REQ-TEST-005, REQ-VALIDATION-001, REQ-VALIDATION-002, REQ-VALIDATION-003

---

## Phase 0.7: CI/CD Integration & Advanced Testing (Codename: "Pipeline")

**Duration:** 1 week
**Target:** November 2025
**Status:** ✅ **COMPLETE** (Completed: 2025-10-30)
**Goal:** Integrate GitHub Actions CI/CD and advanced testing strategies (mutation, property-based, security)

### Dependencies
- Requires Phase 0.6c: 100% complete ✅

### Tasks

#### GitHub Actions CI/CD
- [x] Create .github/workflows/ci.yml workflow
- [x] Configure matrix testing (Python 3.12, 3.13 on ubuntu-latest, windows-latest)
- [x] Integrate Ruff lint + format check
- [x] Integrate Mypy type checking
- [x] Integrate documentation validation
- [x] Integrate full test suite with coverage
- [x] Integrate security scanning (Bandit, Safety, secret detection)
- [x] Add status badges to README.md

#### Codecov Integration
- [x] Create codecov.yml configuration
- [x] Upload coverage.xml from pytest-cov
- [x] Configure project and patch coverage thresholds (80% minimum)
- [x] Enable PR comments with coverage diff
- [x] Set up coverage dashboard

#### Branch Protection
- [ ] Configure branch protection rules for main branch (requires GitHub admin access)
- [ ] Require all CI checks to pass before merge
- [ ] Require 1 approving review (if collaborators)
- [ ] Enforce linear history (no merge commits)
- [ ] Disable force push and branch deletion
**Note:** Branch protection requires GitHub repository admin access - can be configured later

#### Advanced Testing
- [x] Integrate Bandit for security static analysis
- [x] Integrate Safety for dependency vulnerability scanning
- [x] Configure mutmut for mutation testing (60%+ mutation score target)
- [x] Integrate Hypothesis for property-based testing (Decimal arithmetic, edge detection)
- [x] Create mutation testing baseline for critical modules

### Deliverables
- [x] .github/workflows/ci.yml - GitHub Actions workflow
- [x] codecov.yml - Codecov configuration
- [ ] Branch protection rules configured (requires admin access)
- [x] mutmut configuration in pyproject.toml
- [x] Hypothesis test examples for critical logic (12 property tests)
- [x] Updated ARCHITECTURE_DECISIONS V2.8 (ADR-042 through ADR-045 already documented)
- [x] Updated MASTER_REQUIREMENTS V2.9 (REQ-TEST-006-008, REQ-CICD-001-003 already documented)

### Success Criteria
- [x] GitHub Actions workflow runs successfully on push and PR
- [x] All tests pass on both Ubuntu and Windows runners
- [x] Codecov reports are generated and uploaded
- [ ] Branch protection prevents merges with failing checks (requires admin access)
- [x] Mutation testing provides quality metrics for critical modules
- [x] Property-based tests catch edge cases in Decimal arithmetic

**ADRs:**
- ADR-042: CI/CD Integration with GitHub Actions
- ADR-043: Security Testing Integration (Bandit, Safety, SAST)
- ADR-044: Mutation Testing Strategy (mutmut, 60%+ score)
- ADR-045: Property-Based Testing with Hypothesis

**Requirements:** REQ-TEST-006, REQ-TEST-007, REQ-TEST-008, REQ-CICD-001, REQ-CICD-002, REQ-CICD-003

### Deferred Tasks

The following tasks were identified during Phase 0.7 but deferred to Phase 0.8 or later phases. These tasks are **important but not blocking** for Phase 1 development to begin.

**📋 Detailed Documentation:** `docs/utility/PHASE_0.7_DEFERRED_TASKS_V1.0.md`

#### High Priority (Phase 0.8 - 4-5 hours total)

**DEF-001: Pre-Commit Hooks Setup (2 hours)**
- Install pre-commit framework with Ruff, line ending normalization, security checks
- Auto-fix formatting issues before commit (prevents CI failures)
- Expected impact: 50% reduction in CI failures, <5 second execution time
- **Rationale:** Prevents "would reformat" errors, catches issues immediately

**DEF-002: Pre-Push Hooks Setup (1 hour)**
- Run validation suite (Ruff, Mypy, tests, security scan) before push
- Catches 70% of issues before CI runs
- Expected: <60 second execution time
- **Rationale:** Faster feedback than waiting for CI, saves CI time

**DEF-003: GitHub Branch Protection Rules (30 min)**
- Enforce PR workflow (no direct pushes to main)
- Require CI to pass before merge
- Require 1 approving review (if collaborators)
- **Rationale:** Enforces code review, prevents accidental commits

**DEF-004: Line Ending Edge Case Fix (1 hour)**
- Re-commit `test_crud_operations.py` and `test_decimal_properties.py` with LF endings
- Fixes persistent "would reformat" CI error
- ✅ `.gitattributes` already created (prevents future issues)
- **Note:** Will be automatically fixed once DEF-001 (pre-commit hooks) is implemented

#### Low Priority (Phase 1+)

**DEF-005: Pre-Commit Hook - No print() in Production (30 min)**
- Block commits with print() in production code (only logger.info() allowed)
- Exceptions: scripts/, tests/, commented-out debug statements

**DEF-006: Pre-Commit Hook - Check for Merge Conflicts (15 min)**
- Already included in DEF-001 configuration
- Prevents committing files with `<<<<<<<` markers

**DEF-007: Pre-Push Hook - Branch Name Convention (30 min)**
- Enforce naming: `feature/`, `bugfix/`, `refactor/`, `docs/`, `test/`
- Example: `feature/kalshi-api-client`, `bugfix/fix-decimal-precision`

#### Implementation Timeline

**Phase 0.8 (Week 1-2)**
1. DEF-001: Pre-commit hooks setup
2. DEF-004: Line ending fix (validate hooks catch future issues)
3. DEF-002: Pre-push hooks setup
4. DEF-003: Branch protection rules

**Phase 1+ (As Needed)**
5. DEF-005: No print() hook
6. DEF-007: Branch name convention

#### Success Metrics

- ✅ 0 "would reformat" errors in CI after DEF-001
- ✅ 50% reduction in CI failures (pre-commit)
- ✅ 70% reduction in CI failures overall (pre-commit + pre-push)
- ✅ 0 direct pushes to main (branch protection)
- ✅ All files use LF endings (DEF-004)

#### Why Deferred?

1. **Not blocking Phase 1:** Database and API work can proceed without these
2. **CI already functional:** Current CI catches all issues (just slower)
3. **Time constraints:** Phase 0.7 focus was getting CI working, not perfecting it
4. **Learning opportunity:** Better to implement hooks after seeing real CI failures

**Note:** Pre-commit hooks will be especially valuable once multiple developers join the project (Phase 2+).

---

## Phase 1: Core Infrastructure (Codename: "Bootstrap")

**Duration:** 6 weeks
**Target:** December 2025 - January 2026
**Status:** 🔵 Planned (Ready to Start - Phase 0.7 complete ✅)
**Goal:** Build core infrastructure and Kalshi API integration

### Dependencies
- Requires Phase 0.7: 100% complete ✅

### Before Starting This Phase - TEST PLANNING CHECKLIST ⚠️

**MANDATORY: Complete this checklist BEFORE writing any Phase 1 code**

**Reference:** `docs/testing/PHASE_TEST_PLANNING_TEMPLATE_V1.0.md`

**Output:** ✅ **Phase 1 test planning COMPLETE** - Comprehensive test plan documented in `docs/testing/PHASE_1_TEST_PLAN_V1.0.md`

#### 1. Requirements Analysis
- [ ] Review REQ-API-001 through REQ-API-006 (Kalshi/ESPN/Balldontlie API requirements)
- [ ] Review REQ-CLI-001 through REQ-CLI-005 (CLI command requirements with Typer framework)
- [ ] Review REQ-SYS-001 through REQ-SYS-006 (System requirements: DB, config, logging)
- [ ] Critical paths: RSA-PSS authentication, decimal price parsing, rate limiting, config precedence
- [ ] New modules: `api_connectors/kalshi_client.py`, `main.py`, `utils/config_loader.py`

#### 2. Test Categories Needed
- [ ] **Unit tests**: API client methods, CLI argument parsing, config loading, decimal conversion utilities
- [ ] **Integration tests**: API clients with mocked responses, database CRUD, CLI workflow, config override precedence
- [ ] **Critical tests**: Decimal precision (NO float), RSA-PSS auth signature, rate limit enforcement, SQL injection prevention
- [ ] **Mocking**: Mock all HTTP requests, mock database connections for CLI tests, mock file system for config tests

#### 3. Test Infrastructure Updates
- [ ] Create `tests/fixtures/api_responses.py` - Sample Kalshi/ESPN/Balldontlie JSON responses
- [ ] Add `KalshiAPIFactory` to `tests/fixtures/factories.py`
- [ ] Add `ESPNAPIFactory` to test factories
- [ ] Add `CLICommandFactory` for CLI testing
- [ ] Create `tests/fixtures/sample_configs/` - Valid and invalid YAML config files
- [ ] Update `tests/conftest.py` with API client fixtures and temp config directory fixtures

#### 4. Critical Test Scenarios (from user requirements)
- [ ] **API clients fully implemented** with versioned interfaces (REQ-API-001 through REQ-API-005)
- [ ] **CLI commands implemented** validating REQ-CLI-001 through REQ-CLI-005 using Typer framework
- [ ] **Unit tests cover ≥80%** of API client code, including error paths and retry logic
- [ ] **YAML config loader** validates schema; overrides work with expected precedence (DB > YAML > defaults)
- [ ] **Verify all numerical values use Decimal** and NOT float (CRITICAL)
- [ ] **Documentation** for API usage and CLI commands reviewed and published

#### 5. Performance Baselines
- [ ] API client request processing: <100ms (excluding network)
- [ ] CLI startup time: <500ms
- [ ] Config file loading: <50ms
- [ ] Database query (single record): <10ms
- [ ] Rate limiter overhead: <1ms per request

#### 6. Security Test Scenarios
- [ ] API keys loaded from environment variables (NOT hardcoded)
- [ ] RSA-PSS authentication signature validation working correctly
- [ ] Rate limit enforcement prevents API abuse
- [ ] SQL injection prevented (parameterized queries only)
- [ ] Input sanitization for CLI arguments
- [ ] No credentials in logs or error messages

#### 7. Edge Cases to Test
- [ ] API returns 4xx/5xx errors → retry logic with exponential backoff
- [ ] API rate limit exceeded (429 response) → appropriate handling
- [ ] Sub-penny Decimal prices (0.4275, 0.4976) → preserved precision
- [ ] Missing/malformed YAML config files → clear error messages
- [ ] Network timeouts → graceful degradation
- [ ] Expired API credentials → clear error and refresh attempt
- [ ] Config value precedence: DB override > YAML > default
- [ ] Concurrent API requests → rate limiter thread-safe

#### 8. Success Criteria
- [ ] Overall coverage: ≥80% (MANDATORY - enforced by pyproject.toml)
- [ ] Critical module coverage:
  - `api_connectors/kalshi_client.py`: ≥90%
  - `main.py` (CLI): ≥85%
  - `utils/config_loader.py`: ≥85%
  - `database/crud_operations.py`: ≥87% (existing baseline)
- [ ] All critical scenarios from Section 4 tested and passing
- [ ] All edge cases from Section 7 have test coverage
- [ ] Test suite runs in <30 seconds locally
- [ ] All tests marked with appropriate markers (@pytest.mark.unit, @pytest.mark.integration, @pytest.mark.critical)
- [ ] Zero security vulnerabilities (Bandit clean, Safety clean)

**After completion:** Update SESSION_HANDOFF.md: "✅ Phase 1 test planning complete"

---

### Tasks

#### 1. Environment Setup (Week 1)
- Python 3.12+ virtual environment
- PostgreSQL 15+ database installation
- Git repository initialization
- IDE configuration (VSCode recommended)
- Install dependencies from requirements.txt
- Verify Spacy model: `spacy download en_core_web_sm`

#### 2. Database Implementation (Weeks 1-2)
- Create all tables with proper indexes (from DATABASE_SCHEMA_SUMMARY_V1.1.md)
- Implement SCD Type 2 versioning logic (`row_current_ind`, `row_effective_date`, `row_expiration_date`)
- Write Alembic migration scripts
- Create CRUD operations in `database/crud_operations.py` (e.g., `get_active_edges()`)
- Implement `database/connection.py` with psycopg2 pool (pool_size: 5)
- Test with sample data

#### 3. Kalshi API Integration (Weeks 2-4)
- Implement RSA-PSS authentication (`cryptography` library, **not** HMAC-SHA256)
- Token refresh logic (30-minute cycle)
- REST endpoints: markets, events, series, balance, positions, orders
- WebSocket connection for real-time updates (Phase 2+)
- Error handling and exponential backoff retry logic
- Rate limiting (100 req/min, throttle if approaching)
- Parse `*_dollars` fields as DECIMAL (never int cents)

#### 4. Configuration System (Week 4)
- YAML loader with validation (`pyyaml`)
- Database override mechanism (config_overrides table)
- Config priority resolution (DB > YAML > defaults)
- CLI commands: `config-show`, `config-validate`, `config-set`
- DECIMAL range validation (e.g., Kelly 0.10-0.50)

#### 5. Logging Infrastructure (Week 5)
- File-based logging with rotation (`utils/logger.py`)
- Database logging for critical events (trades, errors, edge detections)
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Performance metrics collection (latency, API call counts)
- Structured logging (JSON format for analysis)

#### 6. CLI Framework (Week 6)
- Click 8.1+ CLI framework (`main.py`)
- Commands: `db-init`, `health-check`, `config-show`, `config-validate`
- Example stubs for future commands (Phase 5: `edges-list`, `trade-execute`)
- Help documentation for all commands

### Deliverables
- Working Kalshi API client (`api_connectors/kalshi_client.py` with RSA-PSS)
- Complete database schema (all tables created and tested)
- Configuration system operational (YAML + DB overrides)
- Logging infrastructure (file + database)
- CLI framework (Click commands)
- DEPLOYMENT_GUIDE_V1.0.md (local setup + AWS stubs for Phase 7+)
- Test suite with >80% coverage
- Requirements traceability matrix (REQ-001 through REQ-050 mapped to code)

### Success Criteria
- [  ] Can authenticate with Kalshi demo environment
- [  ] Can fetch and store market data with DECIMAL precision
- [  ] Database stores versioned market updates (SCD Type 2 working)
- [  ] Config system loads YAML and applies DB overrides correctly
- [  ] Logging captures all API calls and errors
- [  ] CLI commands work and provide helpful output
- [  ] Test coverage >80%
- [  ] No float types used for prices (all DECIMAL)

---

## Phase 1.5: Foundation Validation (Codename: "Verify")

**Duration:** 2 weeks
**Target:** December 2025
**Status:** 🔵 Planned (awaits Phase 1 completion)
**Goal:** Validate versioning system and trailing stop infrastructure before Phase 2 complexity

### Dependencies
- Requires Phase 1: 100% complete

### Tasks

#### 1. Strategy Manager Implementation (Week 1)
- [  ] Create `trading/strategy_manager.py`
  - CRUD operations for strategies table
  - Version validation (enforce immutability)
  - Status lifecycle management (draft → testing → active → deprecated)
  - Active strategy lookup
- [  ] Unit tests for strategy versioning
  - Test immutability enforcement
  - Test version creation (v1.0 → v1.1)
  - Test status transitions
  - Test unique constraint validation

#### 2. Model Manager Implementation (Week 1)
- [  ] Create `analytics/model_manager.py`
  - CRUD operations for probability_models table
  - Version validation (enforce immutability)
  - Status lifecycle management (draft → training → validating → active → deprecated)
  - Active model lookup
- [  ] Unit tests for model versioning
  - Test immutability enforcement
  - Test version creation (v1.0 → v1.1)
  - Test validation metrics updates
  - Test unique constraint validation

#### 3. Position Manager Enhancements (Week 2)
- [  ] Update `trading/position_manager.py`
  - Trailing stop state initialization
  - Trailing stop update logic
  - Stop trigger detection
  - JSONB state validation
- [  ] Unit tests for trailing stops
  - Test state initialization
  - Test stop updates on price movement
  - Test trigger detection
  - Test JSONB schema validation

#### 4. Configuration System Enhancement (Week 2)
- [  ] Update `utils/config.py`
  - YAML file loading for all 7 config files
  - Version resolution (get active version for strategy/model)
  - Trailing stop config retrieval
  - Override handling
- [  ] Unit tests for configuration
  - Test YAML loading
  - Test version resolution
  - Test trailing stop config retrieval
  - Test override priority

### Deliverables
- [  ] strategy_manager.py with full CRUD and validation
- [  ] model_manager.py with full CRUD and validation
- [  ] Enhanced position_manager.py with trailing stops
- [  ] Enhanced config.py with version resolution
- [  ] Comprehensive unit tests (>80% coverage for new code)
- [  ] Integration tests for versioning system
- [  ] PHASE_1.5_PLAN.md (detailed acceptance criteria)

### Success Criteria
- [  ] Can create strategy versions and enforce immutability
- [  ] Can create model versions and enforce immutability
- [  ] Trailing stop state initializes correctly on position creation
- [  ] Trailing stops update correctly on price movement
- [  ] Configuration system loads all YAML files correctly
- [  ] Version resolution returns correct active versions
- [  ] All unit tests pass (>80% coverage)
- [  ] Integration tests validate versioning workflow end-to-end

**Why Phase 1.5?**
- Validates versioning system BEFORE Phase 2 complexity
- Tests manager classes before they're used in production
- Ensures trailing stops work before live trading
- Prevents cascading errors in later phases

---

## Phase 2: Live Data Integration (Codename: "Observer")

**Duration:** 4 weeks
**Target:** January 2026
**Status:** 🔵 Planned (awaits Phase 1.5 completion)
**Goal:** Implement live game data collection for NFL/NCAAF via ESPN API

### Dependencies
- Requires Phase 1.5: Versioning system validated

### Before Starting This Phase - TEST PLANNING CHECKLIST ⚠️

**MANDATORY: Complete this checklist BEFORE writing any Phase 2 code**

**Reference:** `docs/testing/PHASE_TEST_PLANNING_TEMPLATE_V1.0.md`

**Output:** Update SESSION_HANDOFF.md with "Phase 2 test planning complete" (detailed test plan to be created when Phase 2 starts)

#### 1. Requirements Analysis
- [ ] Review all Phase 2 data ingestion requirements (ESPN API, game states, task scheduling)
- [ ] Review APScheduler integration and cron job specifications
- [ ] Critical paths: ESPN API reliability, data freshness validation, historical backfill integrity
- [ ] New modules: `api_connectors/espn_client.py`, `schedulers/market_updater.py`, backfill scripts

#### 2. Test Categories Needed
- [ ] **Unit tests**: ESPN API parsing, timestamp validation, data quality checks, APScheduler job logic
- [ ] **Integration tests**: Live feed ingestion with mocked ESPN streams, end-to-end pipeline from API to database
- [ ] **Async tests**: pytest-asyncio for concurrent polling, event loop stress tests, concurrency handling
- [ ] **Mocking**: Mock ESPN API responses (live games, completed games, pre-game), mock APScheduler jobs

#### 3. Test Infrastructure Updates
- [ ] Create `tests/fixtures/espn_responses.py` - Sample ESPN scoreboard JSON (NFL, NCAAF, various game states)
- [ ] Add `ESPNGameFactory` to `tests/fixtures/factories.py` for generating game state test data
- [ ] Create `tests/fixtures/mock_scheduler.py` - Mock APScheduler for testing job execution
- [ ] Update `tests/conftest.py` with async fixtures for event loop testing

#### 4. Critical Test Scenarios (from user requirements)
- [ ] **Live feed ingestion with mocked ESPN streams** - Verify data flows from API → game_states table
- [ ] **Async event loop stress/concurrency tests** - Handle 50+ concurrent game updates without lag
- [ ] **Failover/retry for REST endpoints** - Handle ESPN API errors with exponential backoff
- [ ] **SCD Type-2 validation** - Verify row_current_ind logic for game state updates
- [ ] **End-to-end pipeline tests** - Complete flow: ESPN API → parsing → validation → database storage

#### 5. Performance Baselines
- [ ] ESPN API response parsing: <50ms per game
- [ ] Database insert for game state: <10ms
- [ ] APScheduler job execution overhead: <100ms
- [ ] Concurrent game processing (50 games): <2 seconds total
- [ ] Historical backfill (5 years): <10 minutes total

#### 6. Security Test Scenarios
- [ ] ESPN API calls don't expose credentials (public API, but verify no leaks)
- [ ] Input sanitization for game state data (prevent injection attacks)
- [ ] Timestamp validation prevents time-based attacks
- [ ] Rate limiting prevents API abuse (500 req/hour limit)

#### 7. Edge Cases to Test
- [ ] ESPN API returns stale data (>60 seconds old) → reject and log warning
- [ ] ESPN API returns malformed JSON → graceful error handling
- [ ] ESPN API rate limit exceeded → backoff and retry
- [ ] Network timeout during API call → retry with exponential backoff
- [ ] APScheduler job overlaps (previous job still running) → skip or queue
- [ ] Game state transitions (pre-game → live → completed) → SCD Type-2 properly tracks history
- [ ] Missing data fields in ESPN response → use defaults or skip record with warning
- [ ] Historical backfill finds duplicate data → handle gracefully (upsert logic)

#### 8. Success Criteria
- [ ] Overall coverage: ≥80% (enforced by pyproject.toml)
- [ ] Critical module coverage:
  - `api_connectors/espn_client.py`: ≥85%
  - `schedulers/market_updater.py`: ≥85%
  - Historical backfill scripts: ≥75%
- [ ] All critical scenarios from Section 4 tested and passing
- [ ] Async tests validate concurrency handling (pytest-asyncio)
- [ ] SCD Type-2 logic tested (row_current_ind updates correctly)
- [ ] Test suite runs in <30 seconds locally
- [ ] Zero data loss in stress tests (1000+ updates)

**After completion:** Update SESSION_HANDOFF.md: "✅ Phase 2 test planning complete"

---

### Tasks

#### 1. ESPN API Integration (Weeks 1-2)
- **NFL scoreboard endpoint:** `https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard`
- **NCAAF scoreboard endpoint:** `https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard`
- Parse game state data: scores, period, time remaining, game status
- Store in `game_states` table
- Handle API errors (retries, fallback to cached data)
- Rate limiting (ESPN allows ~500 req/hour)

#### 2. Task Scheduling (Week 2)
- APScheduler 3.10+ implementation (`schedulers/market_updater.py`)
- Cron-like job: Fetch ESPN data every 15 seconds during active games
- Conditional polling: Only poll if games are live (don't waste API calls)
- Job monitoring: Log job execution times, detect failures

#### 3. Data Quality & Validation (Week 3)
- Timestamp validation: Reject stale data (>60 seconds old)
- Data consistency checks: Scores monotonic, period transitions logical
- Missing data handling: Graceful degradation, use last known state
- Alert on anomalies: Email/log if data quality issues detected

#### 4. Historical Data Backfill (Week 4)
- Scrape nflfastR data (2019-2024 seasons for NFL)
- Populate `odds_matrices` table with historical game outcomes
- Map game situations (e.g., "14-7 halftime") to win probabilities
- Validate data quality: Check for completeness, outliers
- **This historical data will be leveraged in Phase 4 for odds calculation**

### Deliverables
- ESPN API client (`api_connectors/espn_client.py`)
- APScheduler task scheduler (`schedulers/market_updater.py`)
- Data quality validation module
- Historical data backfill script (nflfastR)
- Updated test suite
- LIVE_DATA_INTEGRATION_GUIDE_V1.0.md

### Success Criteria
- [  ] Can fetch live NFL game data every 15 seconds
- [  ] Game states stored correctly in database
- [  ] Data quality checks catch anomalies
- [  ] Historical data (2019-2024) loaded into `odds_matrices`
- [  ] No data loss during extended polling sessions
- [  ] APScheduler jobs run reliably

---

## Phase 3: Data Processing (Codename: "Pipeline")

**Duration:** 4 weeks  
**Target:** January-February 2026  
**Status:** 🔵 Planned  
**Goal:** Implement asynchronous data processing and WebSocket handlers (**NO odds calculation or edge detection in this phase**)

### Dependencies
- Requires Phase 2: Live data integration operational

### Before Starting This Phase - TEST PLANNING CHECKLIST ⚠️

**MANDATORY: Complete this checklist BEFORE writing any Phase 3 code**

**Reference:** `docs/testing/PHASE_TEST_PLANNING_TEMPLATE_V1.0.md`

**Output:** Update SESSION_HANDOFF.md with "Phase 3 test planning complete" (detailed test plan to be created when Phase 3 starts)

#### 1. Requirements Analysis
- [ ] Review async processing framework requirements (asyncio, aiohttp, queue systems)
- [ ] Review WebSocket integration requirements (Kalshi, ESPN)
- [ ] Critical paths: WebSocket stability (24+ hours), queue backpressure handling, message routing
- [ ] New modules: Async processing pipeline, WebSocket handlers, data normalization module

#### 2. Test Categories Needed
- [ ] **Async unit tests**: pytest-asyncio for queue operations, message routing, data normalization
- [ ] **Integration tests**: WebSocket connection lifecycle, reconnection on disconnect, end-to-end message flow
- [ ] **Stress tests**: 50+ concurrent game updates, queue backpressure simulation, high-volume periods
- [ ] **Mocking**: Mock WebSocket connections, mock asyncio.Queue, mock concurrent game updates

#### 3. Test Infrastructure Updates
- [ ] Create `tests/fixtures/websocket_messages.py` - Sample Kalshi/ESPN WebSocket messages
- [ ] Add `WebSocketMockFactory` for simulating WebSocket message streams
- [ ] Create `tests/utils/async_helpers.py` - Utilities for async testing (event loop fixtures)
- [ ] Update `tests/conftest.py` with WebSocket client fixtures and async queue fixtures

#### 4. Critical Test Scenarios (from user requirements)
- [ ] **Async event loop stress tests** - Process 50+ concurrent updates without lag or data loss
- [ ] **Concurrency tests** - Validate thread safety and race condition handling
- [ ] **WebSocket failover/retry** - Handle disconnections with automatic reconnection and message replay
- [ ] **REST failover/retry** - Fallback to REST if WebSocket fails, with exponential backoff
- [ ] **End-to-end pipeline tests** - WebSocket → queue → processing → normalization → database

#### 5. Performance Baselines
- [ ] Message processing latency: <2 seconds (95th percentile)
- [ ] Queue throughput: >100 messages/second
- [ ] WebSocket reconnection time: <5 seconds
- [ ] Concurrent game processing (50 games): <2 seconds
- [ ] Memory usage under load: <500MB

#### 6. Security Test Scenarios
- [ ] WebSocket authentication tokens refreshed securely
- [ ] No credentials in WebSocket message logs
- [ ] Message validation prevents injection attacks
- [ ] Rate limiting on incoming WebSocket messages
- [ ] SSL/TLS for all WebSocket connections

#### 7. Edge Cases to Test
- [ ] WebSocket disconnects mid-message → reconnect and resume
- [ ] WebSocket receives malformed JSON → skip message and log error
- [ ] Queue fills up (backpressure) → throttle incoming messages gracefully
- [ ] Multiple WebSocket reconnections in quick succession → handle without crashes
- [ ] Network timeout during WebSocket handshake → retry with exponential backoff
- [ ] Concurrent writes to same game state → last-write-wins or merge logic
- [ ] Message ordering (out-of-order WebSocket messages) → handle with timestamps
- [ ] Long-running connections (24+ hours) → no memory leaks or degradation

#### 8. Success Criteria
- [ ] Overall coverage: ≥80% (enforced by pyproject.toml)
- [ ] Critical module coverage:
  - Async processing framework: ≥85%
  - WebSocket handlers: ≥85%
  - Data normalization: ≥80%
- [ ] All critical scenarios from Section 4 tested and passing
- [ ] WebSocket stability test (24-hour mock connection) passes
- [ ] Processing latency <2 seconds in stress tests
- [ ] Zero data loss in high-volume tests (1000+ messages)
- [ ] Test suite runs in <45 seconds locally (async tests are slower)

**After completion:** Update SESSION_HANDOFF.md: "✅ Phase 3 test planning complete"

---

### Tasks

#### 1. Async Processing Framework (Weeks 1-2)
- Implement asyncio-based processing pipeline
- Queue system for incoming data (aiohttp, asyncio.Queue)
- Concurrent processing of multiple games
- Backpressure handling: Throttle if queue fills up
- **Focus: Data ingestion and storage, NOT business logic**

#### 2. WebSocket Handlers (Week 2)
- Kalshi WebSocket integration for real-time market updates
- ESPN WebSocket (if available) for game updates
- Automatic reconnection on disconnect
- Message parsing and routing to appropriate handlers
- **Focus: Real-time data ingestion, NOT edge detection**

#### 3. Data Normalization (Week 3)
- Normalize game state data (scores, time, period)
- Normalize market data (prices, liquidity, metadata)
- Handle different data formats (REST vs. WebSocket)
- Ensure consistent DECIMAL precision across sources

#### 4. Processing Monitoring (Week 4)
- Processing latency tracking
- Queue depth monitoring
- Data throughput metrics
- Alert on processing delays (>5 seconds)
- Dashboard metrics (Phase 7 will visualize these)

### Deliverables
- Async processing framework (asyncio, aiohttp)
- WebSocket handlers (Kalshi, ESPN)
- Data normalization module
- Processing monitoring and metrics
- Updated test suite (async tests with pytest-asyncio)
- DATA_PROCESSING_ARCHITECTURE_V1.0.md

### Success Criteria
- [  ] Can process 50+ concurrent game updates without lag
- [  ] WebSocket connections stable for 24+ hours
- [  ] Data normalized consistently across sources
- [  ] Processing latency <2 seconds (95th percentile)
- [  ] No data loss during high-volume periods
- [  ] **NO edge detection or odds calculation implemented yet**

**Critical Note:** Phase 3 is pure data processing/ingestion. Odds models, edge detection, and trade signals are Phase 4+.

---

## Phase 4: Odds Calculation & Edge Detection (Codename: "Oracle")

**Duration:** 8 weeks  
**Target:** February-April 2026  
**Status:** 🔵 Planned  
**Goal:** Implement odds models, historical lookup, ensemble, and edge detection

### Dependencies
- Requires Phase 2: Historical data loaded (nflfastR)
- Requires Phase 3: Data processing pipeline operational

### Before Starting This Phase - TEST PLANNING CHECKLIST ⚠️

**MANDATORY: Complete this checklist BEFORE writing any Phase 4 code**

**Reference:** `docs/testing/PHASE_TEST_PLANNING_TEMPLATE_V1.0.md`

**Output:** Update SESSION_HANDOFF.md with "Phase 4 test planning complete" (detailed test plan to be created when Phase 4 starts)

#### 1. Requirements Analysis
- [ ] Review all Phase 4 model requirements (historical lookup, Elo, regression, ensemble)
- [ ] Review edge detection requirements (threshold filtering, confidence scoring)
- [ ] Review backtesting requirements (walk-forward validation, Brier score, log loss)
- [ ] Critical paths: Model versioning immutability, ensemble accuracy, backtesting integrity
- [ ] New modules: `models/historical_lookup.py`, `models/elo.py`, `models/regression.py`, `models/ensemble.py`, `analytics/edge_detection.py`, `analytics/backtesting.py`

#### 2. Test Categories Needed
- [ ] **Unit tests**: Individual model outputs (Elo, regression, historical lookup), ensemble weighting logic, edge calculation
- [ ] **Integration tests**: EV+ edge detection end-to-end, model versioning immutability enforcement, backtesting engine
- [ ] **Property-based tests**: Hypothesis for ensemble probabilities (always 0.0-1.0), edge calculation properties
- [ ] **Performance tests**: Model prediction latency (<100ms), backtesting speed (5 years in <30 minutes)

#### 3. Test Infrastructure Updates
- [ ] Create `tests/fixtures/historical_game_data.py` - Sample nflfastR data for testing
- [ ] Add `OddsMatrixFactory` to generate test historical odds matrices
- [ ] Add `GameSituationFactory` for various game situations (halftime, 4th quarter, etc.)
- [ ] Create `tests/fixtures/model_configs.py` - Sample strategy and model version configs
- [ ] Update `tests/conftest.py` with model fixtures and backtesting fixtures

#### 4. Critical Test Scenarios (from user requirements)
- [ ] **Ensemble feature extraction** - Verify all 4 models (Elo, regression, ML, historical) provide valid probabilities
- [ ] **Backtesting engine with reports** - Walk-forward validation produces Brier score, log loss, P&L reports
- [ ] **Model versioning immutability** - Verify config immutability (cannot modify v1.0 config after creation)
- [ ] **EV+ edge detection integration tests** - End-to-end: game state → models → ensemble → edge → trade signal
- [ ] **Model performance documentation** - Automated reports comparing ensemble vs. individual models

#### 5. Performance Baselines
- [ ] Historical lookup query: <10ms per situation
- [ ] Elo calculation: <5ms per team pair
- [ ] Regression prediction: <20ms
- [ ] Ensemble prediction (all 4 models): <100ms total
- [ ] Edge detection scan (100 markets): <5 seconds
- [ ] Backtesting (5 years, 1000 games): <30 minutes

#### 6. Security Test Scenarios
- [ ] Model configs stored securely (no secrets in JSONB)
- [ ] Backtesting doesn't expose sensitive market data
- [ ] Edge detection doesn't log proprietary signals
- [ ] Model version creation validates permissions

#### 7. Edge Cases to Test
- [ ] Historical lookup with no matching data → fallback to Elo/regression only
- [ ] Ensemble with missing model (e.g., ML not ready) → use available models and adjust weights
- [ ] Edge detection with very low confidence (<0.50) → skip signal
- [ ] Backtesting with missing historical data → skip games gracefully
- [ ] Model version conflict (attempt to create duplicate v1.0) → reject with clear error
- [ ] Probability bounds (ensemble returns >1.0 or <0.0) → clamp to [0.0, 1.0]
- [ ] Division by zero in edge calculation → handle gracefully
- [ ] Negative edge (market price > true probability) → correctly identify as no-trade

#### 8. Success Criteria
- [ ] Overall coverage: ≥80% (enforced by pyproject.toml)
- [ ] Critical module coverage:
  - `models/ensemble.py`: ≥90% (CRITICAL)
  - `models/historical_lookup.py`: ≥85%
  - `analytics/edge_detection.py`: ≥90% (CRITICAL)
  - `analytics/backtesting.py`: ≥85%
- [ ] All critical scenarios from Section 4 tested and passing
- [ ] Backtesting shows ensemble outperforms individual models by ≥5% (validation test)
- [ ] Property-based tests (Hypothesis) validate probability bounds and edge calculation
- [ ] Model immutability tests prevent config modifications
- [ ] Test suite runs in <60 seconds locally

**After completion:** Update SESSION_HANDOFF.md: "✅ Phase 4 test planning complete"

---

### Tasks

#### 1. Historical Lookup Model (Weeks 1-2)
- **Implement `models/historical_lookup.py`:**
  - Load historical odds matrices from `odds_matrices` table (populated in Phase 2)
  - Interpolation methods: linear, nearest-neighbor
  - Confidence scoring: Higher confidence for more data points
  - Era adjustment: Weight recent seasons more heavily (2022-2024 > 2019-2021)
- Map current game situations to historical outcomes
- Handle edge cases: No historical data for rare situations
- **Sample Task: "4.1 Historical Loader: Scrape 2019-2024 (nflfastR); populate odds_matrices (ref MODEL_VALIDATION for benchmarks)."**

#### 2. Elo Rating System (Week 2)
- Implement team Elo ratings (`models/elo.py`)
- Home advantage adjustments (post-2020 values: nfl:30, nba:40, mlb:20, nhl:30, soccer:25, tennis:20)
- K-factor tuning (nfl:28, nba:32, etc.)
- Elo-based win probability calculation

#### 3. Regression Model (Week 3)
- Logistic regression on team stats (`models/regression.py`)
- Feature engineering: Offensive/defensive ratings, recent form, injuries
- Coefficients tuned on historical data
- Probability output (0.0-1.0)

#### 4. Ensemble Model (Week 4)
- **Implement `models/ensemble.py`:**
  - Combine Elo (weight 0.40) + Regression (0.35) + ML (0.25) + Historical (0.30)
  - Weighted average with normalization
  - Confidence scoring based on model agreement
- Test ensemble vs. individual models (see MODEL_VALIDATION_V1.0.md for benchmarks)

#### 5. Edge Detection (Weeks 5-6)
- Calculate edge: `ensemble_probability - market_price`
- Threshold filtering: Only signal if edge > 0.0500 (5.00%)
- Confidence threshold: Only signal if ensemble confidence > 0.70
- Efficiency adjustment: Account for home advantage decline post-2020

#### 6. Backtesting & Validation (Weeks 7-8)
- Walk-forward validation on 2019-2024 data (see BACKTESTING_PROTOCOL_V1.0.md)
- Calculate hypothetical P&L
- Measure model accuracy (Brier score, log loss)
- Compare ensemble vs. individual models
- Validate edge detection thresholds

### Deliverables
- Historical lookup model (`models/historical_lookup.py`)
- Elo rating system (`models/elo.py`)
- Regression model (`models/regression.py`)
- Ensemble model (`models/ensemble.py`)
- Edge detection module
- Backtesting framework
- MODEL_VALIDATION_V1.0.md (Elo vs. research, benchmark comparisons)
- BACKTESTING_PROTOCOL_V1.0.md (walk-forward steps, train/test splits)
- Updated test suite

### Success Criteria
- [  ] Historical lookup model achieves >60% accuracy on unseen data
- [  ] Ensemble outperforms individual models by >5%
- [  ] Edge detection generates >10 profitable signals per week (backtest)
- [  ] Backtesting shows positive expectancy (Sharpe >1.0)
- [  ] Models handle rare situations gracefully (no crashes)
- [  ] **Ready to feed trade signals to Phase 5 trading engine**

---

## Phase 5: Position Monitoring & Exit Management (Codename: "Executor")

**Duration:** 4 weeks (split into 5a and 5b)
**Target:** April-May 2026
**Status:** 🔵 Planned
**Goal:** Implement comprehensive position monitoring, exit evaluation, and order execution with price walking

### Dependencies
- Requires Phase 1: Core infrastructure
- Requires Phase 4: Edge detection operational

### Sub-Phases

**Phase 5 Split:**
- **Phase 5a (Weeks 10-12):** Position monitoring, exit evaluation, priority hierarchy
- **Phase 5b (Weeks 13-14):** Order execution, price walking algorithm, exit attempt logging

---

## Phase 5a: Position Monitoring & Exit Evaluation (Codename: "Observer")

**Duration:** 3 weeks (Weeks 10-12)
**Target:** April 2026
**Status:** 🔵 Planned
**Goal:** Implement dynamic position monitoring, exit condition evaluation, and priority hierarchy

### Dependencies
- Requires Phase 1: Core infrastructure
- Requires Phase 4: Edge detection operational

### Before Starting This Phase - TEST PLANNING CHECKLIST ⚠️

**MANDATORY: Complete this checklist BEFORE writing any Phase 5a code**

**Reference:** `docs/testing/PHASE_TEST_PLANNING_TEMPLATE_V1.0.md`

**Output:** Update SESSION_HANDOFF.md with "Phase 5a test planning complete" (detailed test plan to be created when Phase 5a starts)

#### 1. Requirements Analysis
- [ ] Review REQ-MON-001 through REQ-MON-003 (dynamic monitoring, position state tracking, health checks)
- [ ] Review REQ-EXIT-001 through REQ-EXIT-003 (exit priority hierarchy, 10 exit conditions, partial exit staging)
- [ ] Critical paths: Monitoring loop stability (24+ hours), priority hierarchy resolution, trailing stop accuracy
- [ ] New modules: `trading/position_monitor.py`, `trading/exit_evaluator.py`, `trading/priority_resolver.py`

#### 2. Test Categories Needed
- [ ] **Unit tests**: Each of 10 exit conditions, priority hierarchy logic, trailing stop state updates, partial exit calculations
- [ ] **Integration tests**: Full monitoring loop with database, exit condition evaluation end-to-end, position lifecycle events
- [ ] **Performance tests**: Monitoring latency, API rate limit compliance (<60 calls/min), memory usage during 24-hour run
- [ ] **Mocking**: Mock position updates, mock API price fetches, mock database queries

#### 3. Test Infrastructure Updates
- [ ] Create `tests/fixtures/position_scenarios.py` - Sample positions at various profit/loss states
- [ ] Add `PositionFactory` with realistic profit/loss scenarios
- [ ] Create `tests/fixtures/exit_conditions.py` - Pre-configured exit condition test cases
- [ ] Add `MonitoringLoopFactory` for simulating monitoring cycles
- [ ] Update `tests/conftest.py` with position monitoring fixtures

#### 4. Critical Test Scenarios (from user requirements)
- [ ] **Exit conditions with priorities** - Verify all 10 conditions trigger correctly and highest priority wins
- [ ] **Order walking validation** - Not in this phase (Phase 5b), but prepare test infrastructure
- [ ] **Position lifecycle event logs** - Verify position_exits table records all exit events
- [ ] **Priority conflict resolution** - Multiple conditions trigger simultaneously → highest priority executes
- [ ] **Trailing stop progressive tightening** - Verify stop price tightens as profit increases

#### 5. Performance Baselines
- [ ] Position monitoring cycle (1 position): <100ms
- [ ] Exit condition evaluation (all 10 conditions): <50ms
- [ ] Priority resolution: <10ms
- [ ] Trailing stop update: <20ms
- [ ] API rate limit: ≤60 calls/minute (strict enforcement)
- [ ] 24-hour monitoring run: No memory leaks, stable performance

#### 6. Security Test Scenarios
- [ ] Position data access controls (no unauthorized reads)
- [ ] Exit condition logs don't expose proprietary strategies
- [ ] API calls use secure credentials
- [ ] Circuit breaker can't be bypassed maliciously

#### 7. Edge Cases to Test
- [ ] Position within 2% of multiple thresholds → urgent monitoring (5s) activates
- [ ] Multiple exit conditions trigger simultaneously → priority hierarchy resolves correctly
- [ ] Trailing stop hits exactly at profit target → priority determines action
- [ ] API rate limit approaching (58/60 calls) → throttle to stay under limit
- [ ] Position update fails (API timeout) → retry logic with backoff
- [ ] Trailing stop state corrupted in database → reinitialize from position data
- [ ] Partial exit quantity calculation (50% of odd number) → round correctly
- [ ] Circuit breaker triggers → all monitoring halts immediately

#### 8. Success Criteria
- [ ] Overall coverage: ≥80% (enforced by pyproject.toml)
- [ ] Critical module coverage:
  - `trading/position_monitor.py`: ≥90% (CRITICAL)
  - `trading/exit_evaluator.py`: ≥90% (CRITICAL)
  - `trading/priority_resolver.py`: ≥85%
- [ ] All 10 exit conditions have passing unit tests
- [ ] Priority hierarchy resolves conflicts correctly (all test cases pass)
- [ ] 24-hour stability test passes (no crashes, memory stable)
- [ ] API rate limits never exceeded in stress tests
- [ ] Paper trading validation shows correct exit logic (2-week test)
- [ ] Test suite runs in <60 seconds locally

**After completion:** Update SESSION_HANDOFF.md: "✅ Phase 5a test planning complete"

---

### Tasks

#### 1. Dynamic Monitoring System (Week 1)
- Implement normal frequency monitoring (30 seconds)
- Implement urgent frequency monitoring (5 seconds)
- Urgent condition detection (within 2% of thresholds)
- Price caching (10-second TTL)
- API rate management (60 calls/min maximum)
- Monitor loop with async processing

#### 2. Position State Tracking (Week 1)
- Update `current_price` on every check
- Calculate `unrealized_pnl` and `unrealized_pnl_pct`
- Update `last_update` timestamp
- Maintain `trailing_stop_state` JSONB
- Track peak price and trailing stop price
- Health check monitoring

#### 3. Exit Condition Evaluation (Week 2)
- Implement 10 exit conditions:
  1. **stop_loss** (CRITICAL): Price hits stop loss threshold
  2. **circuit_breaker** (CRITICAL): System protection triggers
  3. **trailing_stop** (HIGH): Price hits trailing stop
  4. **time_based_urgent** (HIGH): <10 min to event, losing position
  5. **liquidity_dried_up** (HIGH): Spread >3¢ or volume <50
  6. **profit_target** (MEDIUM): Price hits profit target
  7. **partial_exit_target** (MEDIUM): 50% @ +15%, 25% @ +25%
  8. **early_exit** (LOW): Edge drops below 2%
  9. **edge_disappeared** (LOW): Edge turns negative
  10. **rebalance** (LOW): Portfolio rebalancing needed
- Per-condition trigger logic
- Confidence-adjusted thresholds

#### 4. Exit Priority Hierarchy (Week 2)
- Implement 4-level priority system:
  - CRITICAL: stop_loss, circuit_breaker
  - HIGH: trailing_stop, time_based_urgent, liquidity_dried_up
  - MEDIUM: profit_target, partial_exit_target
  - LOW: early_exit, edge_disappeared, rebalance
- Conflict resolution (highest priority wins)
- Log all triggered conditions

#### 5. Partial Exit Staging (Week 3)
- Stage 1: Exit 50% at +15% profit
- Stage 2: Exit 25% at +25% profit
- Remaining 25%: Rides with trailing stop
- Track partial exit history in `position_exits` table

#### 6. Testing & Validation (Week 3)
- Unit tests for each exit condition
- Unit tests for priority resolution
- Integration tests for monitoring loop
- Paper trading mode validation
- Performance metrics collection

### Deliverables (Phase 5a)
- Dynamic monitoring system (`trading/position_monitor.py`)
- Exit condition evaluators (10 conditions)
- Priority hierarchy resolver
- Partial exit staging logic
- Database updates (`position_exits` table usage)
- Test suite (>80% coverage)
- MONITORING_IMPLEMENTATION_GUIDE_V1.0.md

### Success Criteria (Phase 5a)
- [  ] Normal monitoring working (30s checks)
- [  ] Urgent monitoring activates correctly (5s when needed)
- [  ] All 10 exit conditions evaluate correctly
- [  ] Priority hierarchy resolves conflicts properly
- [  ] Partial exits execute at correct thresholds
- [  ] Paper trading shows exit logic working correctly
- [  ] API rate limits respected (<60 calls/min)

**Requirements Implemented:**
- REQ-MON-001: Dynamic monitoring frequencies ✓
- REQ-MON-002: Position state tracking ✓
- REQ-EXIT-001: Exit priority hierarchy ✓
- REQ-EXIT-002: 10 exit conditions ✓
- REQ-EXIT-003: Partial exit staging ✓

---

## Phase 5b: Exit Execution & Order Walking (Codename: "Walker")

**Duration:** 2 weeks (Weeks 13-14)
**Target:** May 2026
**Status:** 🔵 Planned
**Goal:** Implement urgency-based execution strategies, price walking algorithm, and exit attempt logging

### Dependencies
- Requires Phase 5a: Exit evaluation system operational

### Before Starting This Phase - TEST PLANNING CHECKLIST ⚠️

**MANDATORY: Complete this checklist BEFORE writing any Phase 5b code**

**Reference:** `docs/testing/PHASE_TEST_PLANNING_TEMPLATE_V1.0.md`

**Output:** Update SESSION_HANDOFF.md with "Phase 5b test planning complete" (detailed test plan to be created when Phase 5b starts)

#### 1. Requirements Analysis
- [ ] Review REQ-EXEC-001 through REQ-EXEC-003 (urgency-based execution, price walking, exit attempt logging)
- [ ] Review requirements for circuit breaker tests and position lifecycle logging
- [ ] Critical paths: Price walking algorithm accuracy, exit attempt logging completeness, circuit breaker reliability
- [ ] New modules: `trading/exit_executor.py`, `trading/price_walker.py`, `trading/circuit_breaker.py`

#### 2. Test Categories Needed
- [ ] **Unit tests**: Price walking algorithm, urgency-based execution strategies, timeout handling, circuit breaker logic
- [ ] **Integration tests**: Full exit execution with mock Kalshi API, order placement and fill confirmation, exit attempt logging
- [ ] **Load/latency tests**: Fill rates by priority level, slippage analysis, execution under high concurrency
- [ ] **Circuit breaker tests**: System halt on trigger, trade blocking, emergency stop functionality

#### 3. Test Infrastructure Updates
- [ ] Create `tests/fixtures/order_responses.py` - Sample Kalshi order placement responses (filled, partial, rejected)
- [ ] Add `OrderFactory` for generating test orders at various states
- [ ] Create `tests/fixtures/market_depth.py` - Sample order book data for price walking tests
- [ ] Add `CircuitBreakerScenarioFactory` for testing system halt conditions
- [ ] Update `tests/conftest.py` with order execution fixtures and circuit breaker fixtures

#### 4. Critical Test Scenarios (from user requirements)
- [ ] **Circuit breaker tests halting trading** - Verify circuit breaker stops all trading immediately
- [ ] **Position lifecycle event logs** - Verify exit_attempts table records every order attempt
- [ ] **Load/latency tests for execution** - Measure fill rates, slippage, and execution speed under stress
- [ ] **Price walking effectiveness** - Verify walking improves fill prices by 1-2% vs. market orders
- [ ] **Urgency-based execution strategies** - CRITICAL uses market orders, HIGH/MEDIUM/LOW use progressive limit orders

#### 5. Performance Baselines
- [ ] CRITICAL priority fill time: <10 seconds (market orders)
- [ ] HIGH priority fill time: <30 seconds (95th percentile)
- [ ] MEDIUM priority average slippage: <2%
- [ ] LOW priority average slippage: <1%
- [ ] Price walking improvement vs. market: 1-2%
- [ ] Circuit breaker activation time: <1 second
- [ ] Exit attempt logging latency: <50ms per record

#### 6. Security Test Scenarios
- [ ] Order execution uses secure API credentials
- [ ] Exit attempt logs don't expose sensitive strategy details
- [ ] Circuit breaker can't be bypassed via API manipulation
- [ ] Order placement validates all parameters before submission
- [ ] No credentials in order execution logs

#### 7. Edge Cases to Test
- [ ] Price walking reaches max walks without fill → escalate to market order (HIGH priority)
- [ ] Partial fill on limit order → update position quantity, continue walking for remainder
- [ ] Order rejected by API (insufficient funds, invalid params) → log error, alert user
- [ ] Circuit breaker triggers mid-execution → halt immediately, log all in-flight orders
- [ ] Network timeout during order placement → retry with exponential backoff
- [ ] Order fills at worse price than limit (slippage) → log actual fill price
- [ ] Multiple exits triggered simultaneously → queue and execute serially
- [ ] Price walks beyond best ask (limit > market price) → cap at market + $0.01

#### 8. Success Criteria
- [ ] Overall coverage: ≥80% (enforced by pyproject.toml)
- [ ] Critical module coverage:
  - `trading/exit_executor.py`: ≥90% (CRITICAL)
  - `trading/price_walker.py`: ≥90% (CRITICAL)
  - `trading/circuit_breaker.py`: ≥95% (CRITICAL - safety feature)
- [ ] All critical scenarios from Section 4 tested and passing
- [ ] Circuit breaker tests prove system halts reliably
- [ ] Load tests show acceptable fill rates (≥90% for CRITICAL, ≥80% for HIGH)
- [ ] Price walking tests prove slippage reduction
- [ ] Paper trading validation (2 weeks) shows proper execution
- [ ] Test suite runs in <60 seconds locally

**After completion:** Update SESSION_HANDOFF.md: "✅ Phase 5b test planning complete"

---

### Tasks

#### 1. Urgency-Based Execution Strategies (Week 1)
- **CRITICAL Priority:**
  - Market orders only
  - 5-second timeout
  - Immediate retry on failure
- **HIGH Priority:**
  - Aggressive limit orders (best_bid + $0.01)
  - 10-second timeout
  - Walk price 2x, then market order
- **MEDIUM Priority:**
  - Fair limit orders (best_bid)
  - 30-second timeout
  - Walk price up to 5x
- **LOW Priority:**
  - Conservative limit orders (best_bid - $0.01)
  - 60-second timeout
  - Walk price up to 10x

#### 2. Price Walking Algorithm (Week 1)
- Start with limit order at initial price
- Wait for timeout
- If not filled, walk price by $0.01 toward market
- Repeat up to max_walks
- HIGH priority: Escalate to market after max walks
- Track all attempts in `exit_attempts` table

#### 3. Exit Attempt Logging (Week 2)
- Create `exit_attempts` table records
- Log every order attempt:
  - Order type (limit/market)
  - Limit price (if applicable)
  - Fill price (if filled)
  - Attempt number
  - Timeout duration
  - Success/failure
- Enable "Why didn't my exit fill?" analysis

#### 4. Order Execution Integration (Week 2)
- Integrate with Kalshi API order placement
- Handle partial fills
- Update position quantity on fills
- Create `position_exits` record on completion
- Error handling and retries

#### 5. Testing & Validation (Week 2)
- Unit tests for each execution strategy
- Unit tests for price walking logic
- Integration tests with mock Kalshi API
- Paper trading validation (2 weeks)
- Performance metrics (fill rates, slippage)

#### 6. Reporting & Analytics (Week 2)
- Exit attempt analysis dashboard
- Fill rate by priority level
- Average slippage by strategy
- Price walking effectiveness metrics
- Performance by exit condition

### Deliverables (Phase 5b)
- Urgency-based execution engine (`trading/exit_executor.py`)
- Price walking algorithm
- Exit attempt logger
- Order execution integration
- Test suite (>80% coverage)
- EXIT_EXECUTION_GUIDE_V1.0.md
- PRICE_WALKING_ANALYSIS_V1.0.md

### Success Criteria (Phase 5b)
- [  ] CRITICAL exits fill within 10 seconds (market orders)
- [  ] HIGH exits fill within 30 seconds (95th percentile)
- [  ] MEDIUM exits achieve <2% slippage average
- [  ] LOW exits achieve <1% slippage average
- [  ] Price walking improves fill prices by 1-2% vs. market
- [  ] Exit attempt logging captures all details
- [  ] Paper trading shows proper exit execution

**Requirements Implemented:**
- REQ-EXEC-001: Urgency-based execution ✓
- REQ-EXEC-002: Price walking algorithm ✓
- REQ-EXEC-003: Exit attempt logging ✓

**MILESTONE: Ready for Small Live Trading ($50-100 positions)**

---

## Phase 6: Multi-Sport Expansion (Codename: "Constellation")

**Duration:** 6 weeks  
**Target:** May-June 2026  
**Status:** 🔵 Planned  
**Goal:** Add NBA, MLB, Tennis, and UFC support

### Dependencies
- Requires Phase 5: Trading engine operational and profitable on NFL/NCAAF

### Tasks

#### 1. NBA Integration (Weeks 1-2)
- Balldontlie API integration (`api_connectors/balldontlie_client.py`)
- Research NBA odds models (pace adjustments, back-to-back penalties)
- Create `nba_odds_matrices` table
- Test with 2024-2025 season data
- Validate profitability (backtest + paper trade 1 week)

#### 2. MLB Integration (Week 2-3)
- ESPN MLB API integration
- Starting pitcher analysis
- Create `mlb_odds_matrices` table
- Test on 2025 season data

#### 3. Tennis Integration (Week 3-4)
- ATP/WTA data sources (TBD - research Phase 6)
- Surface-specific odds (hard, clay, grass)
- Create `tennis_odds_matrices` table
- Test on active tournaments

#### 4. UFC Integration (Weeks 4-5 - Stretch)
- ESPN UFC API: `https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard`
- Fight-specific matrices (round_3_lead, etc.)
- Create `ufc_odds_matrices` table in `odds_matrices` with subcategory: ufc
- Minimal stubs, no deep implementation

#### 5. System Scaling (Week 6)
- Handle 100+ concurrent markets across all sports
- Multi-sport edge detection (run all models in parallel)
- Sport-specific trade strategies (different Kelly fractions: nfl:0.25, nba:0.22, tennis:0.18)
- Unified position tracking across sports

### Deliverables
- NBA trading operational
- MLB trading operational
- Tennis trading operational (if data source found)
- UFC placeholders/stubs (Phase 6+)
- Multi-sport test suite
- SPORT_EXPANSION_GUIDE_V1.0.md

### Success Criteria
- [  ] All new sports profitable in paper trading (2-week validation)
- [  ] System uptime >99% with multi-sport load
- [  ] Edge detection <5 seconds across all markets
- [  ] No cross-sport interference (NBA doesn't break NFL)

---

## Phase 7: Web Dashboard (Codename: "Augment")

**Duration:** 8 weeks  
**Target:** June-August 2026  
**Status:** 🔵 Planned  
**Goal:** Create web dashboard for monitoring and manual control

### Dependencies
- Requires Phase 5: Trading engine operational

### Tasks

#### 1. Backend API (Weeks 1-2)
- FastAPI 0.104+ backend (`/api/*` endpoints)
- Endpoints: `/positions`, `/trades`, `/pnl`, `/edges`, `/health`
- WebSocket for real-time updates
- Authentication (JWT tokens)

#### 2. Frontend Development (Weeks 3-6)
- React + Next.js frontend
- Real-time position monitoring (WebSocket updates)
- P&L charts and visualizations (Recharts or Plotly)
- System health indicators (API status, data freshness)
- Manual trade execution interface (override automation)
- Historical performance dashboard

#### 3. Deployment (Week 7)
- Vercel for frontend (free tier)
- AWS EC2 for backend (or Railway.app)
- SSL certificates (Let's Encrypt)
- Domain setup

#### 4. Advanced Analytics (Week 8)
- Integrate DVOA, EPA, SP+ ratings (NFL)
- Net Rating, pace adjustments (NBA)
- A/B test baseline vs. enhanced odds
- Feature importance visualization

### Deliverables
- Working web dashboard
- FastAPI backend
- React frontend
- Deployment scripts
- GUI_DESIGN_V1.0.md
- ADVANCED_METRICS_GUIDE_V1.0.md

### Success Criteria
- [  ] Can view all positions in real-time
- [  ] Can execute trades via GUI
- [  ] Dashboard loads in <2 seconds
- [  ] Advanced metrics improve edge detection accuracy by 5%+

---

## Phase 8: Non-Sports Markets (Codename: "Multiverse")

**Duration:** 12 weeks  
**Target:** August-November 2026  
**Status:** 🔵 Planned  
**Goal:** Expand to politics, entertainment, and other non-sports categories

### Dependencies
- Requires Phase 5: Trading engine operational

### Tasks

#### 1. Political Markets (Weeks 1-6)
- RealClearPolling API integration
- FiveThirtyEight data integration
- Election outcome probabilities
- Polling-based odds models
- Validate on 2026 midterms

#### 2. Entertainment Markets (Weeks 7-10)
- Box office predictions (BoxOfficeMojo API)
- Award show outcomes (Oscars, Grammys)
- Cultural event markets
- Custom odds matrices for entertainment

#### 3. NLP Sentiment Analysis (Weeks 9-12)
- Spacy 3.7+ sentiment analysis (`utils/text_parser.py`)
- Twitter/news sentiment for political markets
- Integrate sentiment into odds models (Phase 8-9 blend)

#### 4. Generalized Infrastructure (Week 11-12)
- Category-agnostic edge detection
- Custom strategy per category
- Unified reporting across all categories

### Deliverables
- Political market trading
- Entertainment market trading
- NLP sentiment integration
- Generalized odds framework
- NON_SPORTS_MARKETS_GUIDE_V1.0.md

### Success Criteria
- [  ] Profitable trading in at least 2 non-sports categories
- [  ] Sentiment analysis improves political market accuracy by 10%+
- [  ] System handles diverse market types without errors

---

## Phase 9: Machine Learning Enhancement (Codename: "Singularity")

**Duration:** 16 weeks  
**Target:** November 2026 - March 2027  
**Status:** 🔵 Planned  
**Goal:** Integrate advanced ML models for enhanced predictions

### Dependencies
- Requires Phase 4: Baseline odds models operational
- Requires Phase 8: Large dataset for training

### Tasks

#### 1. Feature Engineering (Weeks 1-4)
- Historical game data features (team stats, player stats, situational factors)
- Market sentiment indicators
- Time-series features (momentum, streaks)
- Feature selection and importance analysis

#### 2. Model Development (Weeks 5-10)
- XGBoost 2.0+ gradient boosting (`analytics/ml/train.py`)
- TensorFlow 2.15+ or PyTorch 2.1+ LSTM for time-series
- Ensemble methods (stacking, blending)
- Hyperparameter tuning (grid search, Bayesian optimization)
- Cross-validation on historical data

#### 3. Model Integration (Weeks 11-14)
- Blend ML predictions with statistical odds (Phase 4 ensemble)
- A/B testing framework (baseline vs. ML-enhanced)
- Continuous learning pipeline (retrain monthly)
- Feature drift detection

#### 4. Performance Tracking (Weeks 15-16)
- Model drift detection (alert if accuracy drops >5%)
- Automatic retraining triggers (monthly or on drift)
- Feature importance visualization
- Backtesting on new data

### Deliverables
- XGBoost/LSTM models for NFL, NBA
- Model blending framework
- Continuous learning pipeline
- A/B testing results
- ML_MODELS_GUIDE_V1.0.md
- FEATURE_ENGINEERING_SPEC_V1.0.md

### Success Criteria
- [  ] ML models outperform baseline by 5%+
- [  ] Models retrain automatically monthly
- [  ] Drift detection catches degradation before losses
- [  ] A/B test shows statistical significance (p<0.05)

---

## Phase 10: Multi-Platform & Advanced Features (Codename: "Nexus Prime")

**Duration:** 12 weeks  
**Target:** March-June 2027  
**Status:** 🔵 Planned  
**Goal:** Add Polymarket integration and cross-platform arbitrage

### Dependencies
- Requires all previous phases operational

### Tasks

#### 1. Polymarket Integration (Weeks 1-4)
- Metamask/Web3 authentication
- CLOB API integration
- Adapt data ingestion for different market structure
- Test on Polymarket sandbox

#### 2. Cross-Platform Features (Weeks 5-8)
- Arbitrage detection (Kalshi vs. Polymarket price discrepancies)
- Unified position tracking across platforms
- Optimal platform selection (liquidity, fees, edge)

#### 3. Advanced Risk Management (Weeks 9-10)
- Portfolio optimization (maximize Sharpe ratio)
- Correlation analysis (avoid concentrated risk)
- Dynamic position sizing based on volatility

#### 4. Production Hardening (Weeks 11-12)
- High availability (failover, redundancy)
- Performance optimization (database tuning, caching)
- Security audit (penetration testing, code review)
- Compliance documentation (CFTC regulations)

### Deliverables
- Polymarket integration
- Arbitrage detection system
- Cross-platform position tracking
- Portfolio optimization module
- Production-grade infrastructure
- POLYMARKET_INTEGRATION_GUIDE_V1.0.md
- CROSS_PLATFORM_ARBITRAGE_V1.0.md

### Success Criteria
- [  ] Can trade on both Kalshi and Polymarket seamlessly
- [  ] Arbitrage opportunities detected and exploited (>$100/week)
- [  ] System handles multi-platform load without errors
- [  ] Production ready for continuous operation (99.9% uptime)

---

## Summary of New Deliverables

**Phase 0:**
- ✅ GLOSSARY_V1.0.md (terms like EV, Kelly, edge, Elo, etc.)
- ✅ DEVELOPER_ONBOARDING_V1.0.md (merged with ENVIRONMENT_CHECKLIST, onboarding steps: "Follow Checklist Parts 1-6, then code stubs")

**Phase 1:**
- DEPLOYMENT_GUIDE_V1.0.md (local setup instructions + AWS deployment stubs for Phase 7+)

**Phase 4:**
- MODEL_VALIDATION_V1.0.md (Elo vs. research benchmarks, ensemble comparisons)
- BACKTESTING_PROTOCOL_V1.0.md (walk-forward validation steps, train/test splits)

**Phase 5:**
- USER_GUIDE_V1.0.md (CLI command examples: `edges-list`, `trade-execute --paper`, `positions-view`)

---

## Phase Dependencies Summary

See PROJECT_OVERVIEW_V1.2.md for complete Phase Dependencies Table. Key dependencies:

- Phase 1 → Phase 0 (foundation complete)
- Phase 2 → Phase 1 (API client operational)
- Phase 3 → Phase 2 (live data available)
- Phase 4 → Phases 2-3 (live data + processing + historical data from Phase 2)
- Phase 5 → Phases 1, 4 (infrastructure + edge detection)
- Phase 6+ → Phase 5 (trading engine profitable)

**Critical:** Phase 4 depends on Phase 2 historical data (nflfastR backfill) for historical_lookup model.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | 2025-10-12 | Clarified Phase 2 (ESP), 3 (processing only), 4 (odds/edges/historical); added new deliverables; Phase 0 marked 100% |
| 1.0 | Earlier | Initial roadmap with all 10 phases |

---

**Maintained By:** Project lead  
**Review Frequency:** Update after each phase completion  
**Next Review:** Phase 1 kickoff (after Phase 0 complete)

---

**END OF DEVELOPMENT_PHASES**
