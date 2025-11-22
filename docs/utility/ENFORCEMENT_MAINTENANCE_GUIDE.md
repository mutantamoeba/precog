# Workflow Enforcement Maintenance Guide

---
**Version:** 1.0
**Created:** 2025-11-22
**Purpose:** Documentation for maintaining and updating workflow enforcement validators
**Audience:** Developers extending validation infrastructure
**Related:** DEVELOPMENT_PATTERNS_V1.5.md, DOCUMENTATION_WORKFLOW_GUIDE_V1.0.md
---

## Table of Contents

1. [Overview](#overview)
2. [When to Update Validators](#when-to-update-validators)
3. [Adding New Validation Rules](#adding-new-validation-rules)
4. [Common Update Patterns](#common-update-patterns)
5. [Testing New Validators](#testing-new-validators)
6. [Integration with Hooks/CI](#integration-with-hooksci)
7. [Maintenance Sustainability](#maintenance-sustainability)
8. [Configuration Management](#configuration-management)
9. [Troubleshooting](#troubleshooting)

---

## Overview

### Enforcement Architecture

**4-Layer Defense in Depth:**

```
Layer 1: Pre-Commit Hooks (~2-5s, fast feedback)
  ├─ Check #1-10: Documentation validation
  ├─ Decimal precision check
  ├─ Code review basics (REQ traceability)
  └─ Formatting/linting (Ruff, Mypy)

Layer 2: Pre-Push Hooks (~60-90s, comprehensive local validation)
  ├─ Step 1-5: Quick validation + tests + type checking + security
  ├─ Step 6: Code quality (tier-specific coverage)
  ├─ Step 7: Security patterns (API auth, secrets)
  └─ Step 8-10: SCD queries + property tests + test fixtures

Layer 3: CI/CD (~2-5min, multi-platform validation)
  ├─ pytest (all tests + coverage reports)
  ├─ Ruff + Mypy (full codebase)
  └─ Codecov integration

Layer 4: Branch Protection (merge gate)
  └─ 6 required CI checks must pass before merge
```

### Validator Inventory

**Current Validators (12 total):**

| Validator | Pattern | Layer | Exit Code | Purpose |
|-----------|---------|-------|-----------|---------|
| `validate_docs.py` | Docs | Pre-commit | 0/1 | 10 documentation checks |
| `validate_code_quality.py` | P13 | Pre-push | 0/1 | Tier-specific coverage |
| `validate_security_patterns.py` | P4 | Pre-push | 0/1/2 | API auth + secrets |
| `validate_scd_queries.py` | P2 | Pre-push | 0/1/2 | SCD Type 2 queries |
| `validate_property_tests.py` | P10 | Pre-push | 0/1/2 | Property test coverage |
| `validate_test_fixtures.py` | P13 | Pre-push | 0/1/2 | Real fixtures validation |
| `validate_phase_start.py` | - | Manual | 0/1/2 | Phase Start Protocol |
| `validate_phase_completion.py` | - | Manual | 0/1/2 | Phase Completion Protocol |
| `check_warning_debt.py` | P9 | Pre-push | 0/1 | Multi-source warning governance |
| `fix_docs.py` | - | Manual | 0/1 | Auto-fix doc issues |
| `validate_quick.sh` | - | Manual | 0/1 | Fast validation wrapper |
| `validate_all.sh` | - | Manual | 0/1 | Full validation wrapper |

**Pattern References:**
- P2: Dual Versioning (SCD Type 2)
- P4: Security (No Credentials in Code)
- P9: Multi-Source Warning Governance
- P10: Property-Based Testing (Hypothesis)
- P13: Coverage Quality (Tier-Specific Targets)

---

## When to Update Validators

### Trigger Events

**Update validators when:**

1. **New Critical Pattern Added** (e.g., Pattern 11)
   - Create new validator script
   - Add to validation_config.yaml
   - Integrate into pre-commit or pre-push hooks

2. **Pattern Definition Changes** (e.g., Pattern 13 tier thresholds change from 80/85/90 to 85/90/95)
   - Update validation_config.yaml thresholds
   - NO code changes needed (YAML-driven)

3. **New Module Type Added** (e.g., new "async_processing" tier)
   - Add tier definition to validation_config.yaml
   - Add tier_pattern entries
   - Existing validators auto-discover new modules

4. **New Test Type Required** (e.g., chaos tests in Phase 5)
   - Add test type to validation_config.yaml
   - Update validate_test_fixtures.py to check for new fixture requirements

5. **Schema Changes** (e.g., new SCD Type 2 table)
   - NO updates needed - validate_scd_queries.py auto-discovers from database schema

6. **Phase Deliverables Change** (e.g., Phase 2 adds ESPN integration)
   - Add phase section to validation_config.yaml
   - List deliverables with coverage targets

### Update Frequency

**Expected Update Cadence:**

| Validator | Update Frequency | Reason |
|-----------|-----------------|--------|
| `validation_config.yaml` | ~2-4 weeks | New phases, modules, patterns |
| `validate_docs.py` | ~1-2 months | New document types, validation rules |
| `validate_code_quality.py` | ~3-6 months | New tier classifications, coverage rules |
| `validate_scd_queries.py` | Rarely (6+ months) | Pattern stable, auto-discovers tables |
| `validate_property_tests.py` | Rarely (6+ months) | Auto-discovers modules, config-driven |
| `validate_test_fixtures.py` | Rarely (6+ months) | Fixture requirements stable |
| Phase validators | Rarely (6+ months) | Protocol changes infrequent |

---

## Adding New Validation Rules

### Step-by-Step Process

#### Step 1: Identify Pattern to Enforce (5 min)

**Question Checklist:**
- [ ] Is this a CRITICAL pattern? (financial correctness, security, data integrity)
- [ ] Can violations cause production bugs?
- [ ] Is manual enforcement error-prone?
- [ ] Can pattern be detected programmatically?
- [ ] Is pattern stable? (won't change every 2 weeks)

**If YES to all 5 → Proceed with automation**

**Example:**

```markdown
**Pattern to Enforce:** Pattern 14 - API Rate Limiting

**Why Critical:**
- Exceeding rate limits blocks trading operations (financial impact)
- Manual code review misses subtle violations (error-prone)
- Pattern stable (Kalshi 100 req/min, ESPN 1000 req/day)

**Detection Method:**
- Scan API client files for requests.get/post calls
- Verify rate limiter decorator present
- Check rate limiter config matches API limits

**Decision:** ✅ Automate
```

#### Step 2: Design Validator (15 min)

**Template Structure:**

```python
#!/usr/bin/env python3
"""
<Pattern Name> Validation - Pattern <N> Enforcement

Validates that <specific rule enforced>.

Pattern <N> (<Pattern Title>): <Brief description of pattern requirement>

Enforcement:
1. <Discovery method> (e.g., "Scan all Python files in src/precog/")
2. <Validation check> (e.g., "Verify rate limiter decorator present")
3. <Error detection> (e.g., "Flag missing decorators")
4. <Exception handling> (e.g., "Allow exceptions with explicit comments")
5. <Actionable reporting> (e.g., "Report violations with file/line + fix suggestion")

Reference: docs/guides/DEVELOPMENT_PATTERNS_V<X>.<Y>.md Pattern <N>
Reference: scripts/validation_config.yaml (<config section>)
Related: ADR-<XXX> (<Related ADR title>)

Exit codes:
  0 = All checks passed
  1 = Critical violations found
  2 = Configuration error (WARNING only, non-blocking)

Example usage:
  python scripts/validate_<name>.py          # Run validation
  python scripts/validate_<name>.py --verbose # Detailed output
"""

import re
import sys
from pathlib import Path

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


def load_validation_config() -> dict:
    """
    Load validation configuration from validation_config.yaml.

    Returns:
        dict with validation rules, or defaults if file not found
    """
    validation_config_path = PROJECT_ROOT / "scripts" / "validation_config.yaml"

    default_config = {
        # Define default configuration here
    }

    if not validation_config_path.exists() or not YAML_AVAILABLE:
        return default_config

    try:
        with open(validation_config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config.get("<config_section>", default_config)
    except Exception:
        return default_config


def discover_targets(verbose: bool = False) -> list:
    """
    Auto-discover targets to validate.

    Args:
        verbose: If True, show detailed discovery process

    Returns:
        List of targets (files, modules, tables, etc.)
    """
    # Implementation here
    pass


def validate_pattern(verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Validate all targets follow pattern.

    Args:
        verbose: If True, show detailed validation process

    Returns:
        (passed, violations) tuple
    """
    violations = []

    # Discover targets
    targets = discover_targets(verbose)

    # Validate each target
    for target in targets:
        # Check pattern compliance
        # Add violations if found
        pass

    return len(violations) == 0, violations


def main():
    """Run validation."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print("=" * 60)
    print("<Pattern Name> Validation (Pattern <N>)")
    print("=" * 60)
    print("Reference: docs/guides/DEVELOPMENT_PATTERNS_V<X>.<Y>.md")
    print("Related: ADR-<XXX> (<Related ADR title>)")
    print("")

    # Check dependencies
    if not YAML_AVAILABLE:
        print("[WARN] PyYAML not available - using default configuration")
        print("")

    # Run validation
    print("[1/1] Checking <pattern description>...")

    try:
        passed, violations = validate_pattern(verbose)

        if not passed:
            print(f"[FAIL] {len(violations)} violations found:")
            for v in violations:
                print(f"  {v}")
            print("")
            print("Fix: <Actionable fix suggestion>")
            print("Reference: DEVELOPMENT_PATTERNS Pattern <N>")
            print("")
            print("=" * 60)
            print("[FAIL] Validation failed")
            print("=" * 60)
            return 1

        print("[PASS] All checks passed")

    except Exception as e:
        print(f"[WARN] Validation failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        print("")
        print("Skipping validation (non-blocking)")
        print("")
        print("=" * 60)
        print("[WARN] Validation skipped")
        print("=" * 60)
        return 2

    print("")
    print("=" * 60)
    print("[PASS] Validation passed")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Design Decisions:**

1. **Exit Code 0/1/2 Strategy:**
   - 0 = PASS (all checks passed)
   - 1 = FAIL (violations found, block commit/push)
   - 2 = WARN (config error, skip validation, non-blocking)

2. **Graceful Degradation:**
   - If PyYAML not available → use default config
   - If database unavailable → use fallback list
   - If file not readable → log warning, continue

3. **Auto-Discovery Over Hardcoding:**
   - Query database schema
   - Glob filesystem patterns
   - Parse existing configs
   - Read from authoritative sources

4. **YAML-Driven Configuration:**
   - Validation rules in validation_config.yaml
   - Code only implements validation logic
   - Config changes don't require code changes

#### Step 3: Add Configuration (10 min)

**Update validation_config.yaml:**

```yaml
# Pattern <N>: <Pattern Name>
<config_section>:
  description: "<Brief description of what this validates>"

  # Discovery method
  discovery_method: "<How targets are discovered>"

  # Required patterns (what MUST be present)
  required_patterns:
    - "<Regex pattern 1>"
    - "<Regex pattern 2>"

  # Forbidden patterns (what MUST NOT be present)
  forbidden_patterns:
    - "<Regex pattern 1>"
    - "<Regex pattern 2>"

  # Exception comments (allow violations with explicit comment)
  allowed_exceptions:
    - "<Exception comment 1>"
    - "<Exception comment 2>"

  # Targets to validate
  targets:
    - name: "<Target 1 name>"
      file: "<File path or pattern>"
      rules:
        - "<Rule 1>"
        - "<Rule 2>"
```

**Example (API Rate Limiting):**

```yaml
# Pattern 14: API Rate Limiting
api_rate_limiting:
  description: "All API clients must implement rate limiting to prevent API bans"

  discovery_method: "Scan src/precog/api_connectors/ for *_client.py files"

  required_patterns:
    - "@rate_limiter"  # Decorator present
    - "RateLimiter\\("  # RateLimiter instantiated

  forbidden_patterns:
    - "requests\\.(get|post)\\([^)]*\\)(?!.*rate_limiter)"  # Direct requests without rate limiter

  allowed_exceptions:
    - "Test client - no rate limiting needed"
    - "Mock API client"

  targets:
    - name: "Kalshi API Client"
      file: "src/precog/api_connectors/kalshi_client.py"
      rate_limit: 100  # requests per minute
    - name: "ESPN API Client"
      file: "src/precog/api_connectors/espn_client.py"
      rate_limit: 1000  # requests per day
```

#### Step 4: Write Tests (20 min)

**Create tests/unit/scripts/test_validate_<name>.py:**

```python
"""
Tests for validate_<name>.py validator.

Tests validation logic, not the pattern itself.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
import sys

# Add scripts/ to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from validate_<name> import (
    load_validation_config,
    discover_targets,
    validate_pattern,
)


def test_load_validation_config_with_yaml():
    """Test loading config from YAML file."""
    # Test config loading
    config = load_validation_config()
    assert isinstance(config, dict)
    assert "<config_section>" in config or config  # Has config or defaults


def test_discover_targets_finds_modules():
    """Test auto-discovery finds all target modules."""
    targets = discover_targets(verbose=False)
    assert isinstance(targets, list)
    # Add specific assertions based on expected targets


def test_validate_pattern_passes_with_compliant_code():
    """Test validation passes when pattern followed."""
    with patch("validate_<name>.discover_targets") as mock_discover:
        mock_discover.return_value = []  # No violations

        passed, violations = validate_pattern(verbose=False)

        assert passed is True
        assert len(violations) == 0


def test_validate_pattern_fails_with_violations():
    """Test validation fails when pattern violated."""
    with patch("validate_<name>.discover_targets") as mock_discover:
        # Mock a violation
        mock_discover.return_value = ["/path/to/violating_file.py"]

        passed, violations = validate_pattern(verbose=False)

        assert passed is False
        assert len(violations) > 0


def test_validate_pattern_allows_exceptions():
    """Test validation allows exceptions with explicit comments."""
    # Test exception handling logic
    pass


def test_exit_codes():
    """Test validator returns correct exit codes."""
    # 0 = PASS
    # 1 = FAIL
    # 2 = WARN (config error)
    pass
```

**Run tests:**

```bash
python -m pytest tests/unit/scripts/test_validate_<name>.py -v
```

#### Step 5: Document Validator (10 min)

**Update this guide (ENFORCEMENT_MAINTENANCE_GUIDE.md):**

1. Add validator to "Validator Inventory" table
2. Add entry to "Update Frequency" table
3. Add examples to "Common Update Patterns" section

**Update DEVELOPMENT_PATTERNS_V<X>.<Y>.md:**

1. Add Pattern <N> section with full description
2. Add code examples (✅ CORRECT vs ❌ WRONG)
3. Add cross-references to ADRs, REQs
4. Add "Automated Enforcement" note referencing validator

**Update .pre-commit-config.yaml or .git/hooks/pre-push:**

```yaml
# Pre-commit example
- repo: local
  hooks:
    - id: <pattern-name>-check
      name: <Pattern Name> Validation (Pattern <N>)
      entry: python scripts/validate_<name>.py
      language: system
      types: [python]
      pass_filenames: false
      verbose: true
```

**Or pre-push hook:**

```bash
# Step <N>: <Pattern Name> Validation
echo "[<N>/<TOTAL>] <Pattern Name> validation..."
if ! python scripts/validate_<name>.py; then
    echo "❌ <Pattern Name> validation failed!"
    echo "Fix: <Actionable fix suggestion>"
    exit 1
fi
echo "✅ <Pattern Name> validation passed"
echo ""
```

#### Step 6: Test End-to-End (15 min)

**Run full validation suite:**

```bash
# 1. Test validator directly
python scripts/validate_<name>.py --verbose

# 2. Test in pre-commit (if added)
git add .
git commit -m "test: Verify <pattern name> validator"
# Should run validator automatically

# 3. Test in pre-push (if added)
git push origin feature/<branch-name>
# Should run validator in Step <N>

# 4. Verify on current codebase
python scripts/validate_<name>.py
# Should report violations or PASS
```

**Verify Expected Behavior:**

- [ ] Finds all targets (modules, files, tables)
- [ ] Detects violations correctly
- [ ] Provides actionable error messages
- [ ] Respects exception comments
- [ ] Returns correct exit codes (0/1/2)
- [ ] Runs within acceptable time (<10s for pre-commit, <60s for pre-push)

#### Step 7: Commit with Comprehensive Message (5 min)

```bash
git add scripts/validate_<name>.py
git add scripts/validation_config.yaml
git add tests/unit/scripts/test_validate_<name>.py
git add docs/utility/ENFORCEMENT_MAINTENANCE_GUIDE.md
git add docs/guides/DEVELOPMENT_PATTERNS_V<X>.<Y>.md
git add .pre-commit-config.yaml  # If updated
git add .git/hooks/pre-push      # If updated

git commit -m "feat: Add <Pattern Name> validator (Pattern <N> enforcement)

## New Files

**scripts/validate_<name>.py** (XXX lines)
- Enforces Pattern <N>: <Brief description>
- Auto-discovers targets: <Discovery method>
- Validates: <What it checks>
- Exit codes: 0 (pass), 1 (fail), 2 (warn)

**validation_config.yaml** (updated)
- Added <config_section> with required/forbidden patterns
- <N> targets defined with validation rules

**tests/unit/scripts/test_validate_<name>.py** (XXX lines)
- Tests config loading, discovery, validation logic
- Tests exit codes (0/1/2)
- Tests exception handling

## Modified Files

**ENFORCEMENT_MAINTENANCE_GUIDE.md** (updated)
- Added validator to inventory table
- Added update frequency guidance
- Added example to Common Update Patterns

**DEVELOPMENT_PATTERNS_V<X>.<Y>.md** (updated)
- Added Pattern <N> section with full description
- Added code examples (✅ CORRECT vs ❌ WRONG)
- Added \"Automated Enforcement\" note

**.<pre-commit-config.yaml | .git/hooks/pre-push>** (updated)
- Integrated validator into <pre-commit | pre-push> workflow
- Step <N>: <Pattern Name> validation

## Testing Results

**Validator Test Results:**
- XX/XX tests passing
- Found <N> violations on current codebase
- All violations legitimate

**Integration Test Results:**
- Pre-commit hook: ✅ Works (~Xs)
- Pre-push hook: ✅ Works (~XXs)
- Exit codes correct (0/1/2)

## Pattern Enforcement

**Pattern <N>: <Pattern Name>**
- **Why:** <Why this pattern is critical>
- **Violation Impact:** <What happens if pattern violated>
- **Detection:** <How validator detects violations>
- **Fix:** <How to fix violations>

## Cross-References

- Pattern <N>: docs/guides/DEVELOPMENT_PATTERNS_V<X>.<Y>.md
- Related ADR: docs/foundation/ARCHITECTURE_DECISIONS_V<X>.<Y>.md (ADR-<XXX>)
- Related REQ: docs/foundation/MASTER_REQUIREMENTS_V<X>.<Y>.md (REQ-<XXX>-<NNN>)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Common Update Patterns

### Pattern 1: Update Tier Thresholds

**Scenario:** Pattern 13 coverage tiers change from 80/85/90 to 85/90/95.

**Files to Update:**
1. `scripts/validation_config.yaml` - Update coverage_tiers section

**Changes:**

```yaml
# OLD
coverage_tiers:
  infrastructure: 80
  business_logic: 85
  critical_path: 90

# NEW
coverage_tiers:
  infrastructure: 85
  business_logic: 90
  critical_path: 95
```

**Test:**

```bash
python scripts/validate_code_quality.py --verbose
# Should report new violations (modules below new thresholds)
```

**Time:** 5 minutes
**Code Changes:** 0 (YAML-only)

---

### Pattern 2: Add New Module to Tier

**Scenario:** New `src/precog/analytics/ensemble.py` module needs critical_path tier (90% coverage).

**Files to Update:**
1. `scripts/validation_config.yaml` - Add to tier_patterns.critical_path

**Changes:**

```yaml
coverage_tiers:
  tier_patterns:
    critical_path:
      - "src/precog/api_connectors/kalshi_client.py"
      - "src/precog/database/migrations/*.py"
      - "src/precog/analytics/ensemble.py"  # NEW
```

**Test:**

```bash
python scripts/validate_code_quality.py --verbose
# Should classify ensemble.py as critical_path (90% target)
```

**Time:** 2 minutes
**Code Changes:** 0 (YAML-only)

---

### Pattern 3: Add New Phase Deliverables

**Scenario:** Starting Phase 2, need to define deliverables and coverage targets.

**Files to Update:**
1. `scripts/validation_config.yaml` - Add phase_deliverables."2" section

**Changes:**

```yaml
phase_deliverables:
  "1.5":
    name: "Manager Layer Implementation"
    deliverables: [...]

  "2":  # NEW
    name: "Live Data Integration"
    deliverables:
      - name: "ESPN Integration"
        file: "src/precog/api_connectors/espn_client.py"
        coverage_target: 90
        test_types: ["unit", "integration", "property"]

      - name: "WebSocket Handler"
        file: "src/precog/realtime/websocket_handler.py"
        coverage_target: 85
        test_types: ["unit", "integration", "stress"]

      - name: "Event Loop Manager"
        file: "src/precog/realtime/event_loop.py"
        coverage_target: 90
        test_types: ["unit", "race_condition"]
```

**Test:**

```bash
python scripts/validate_phase_start.py --phase 2 --verbose
# Should validate Phase 2 deliverables exist and have coverage targets

python scripts/validate_phase_completion.py --phase 2 --verbose
# Should check Phase 2 deliverable coverage against targets
```

**Time:** 10 minutes
**Code Changes:** 0 (YAML-only)

---

### Pattern 4: Add New Test Type

**Scenario:** Phase 2 requires stress tests, need to validate integration tests use stress fixtures.

**Files to Update:**
1. `scripts/validation_config.yaml` - Add stress_tests section to test_fixture_requirements
2. `scripts/validate_test_fixtures.py` - NO CHANGES (auto-discovers from config)

**Changes:**

```yaml
test_fixture_requirements:
  integration_tests:
    description: "Tests requiring real database/API infrastructure"
    required_fixtures:
      - "db_pool"
      - "db_cursor"
      - "clean_test_data"

  stress_tests:  # NEW
    description: "Tests validating system behavior under heavy load"
    required_fixtures:
      - "load_generator"
      - "performance_monitor"
      - "resource_cleanup"
    forbidden_patterns:
      - "mock_load_generator"
      - "time.sleep\\(\\d+\\)"  # Don't fake delays, use real load
    allowed_exceptions:
      - "Unit test - mock OK"
```

**Test:**

```bash
python scripts/validate_test_fixtures.py --verbose
# Should validate stress tests use load_generator fixture
```

**Time:** 15 minutes
**Code Changes:** 0 (YAML-only, validator auto-adapts)

---

### Pattern 5: Add New Property Test Module

**Scenario:** New `src/precog/analytics/ensemble.py` module needs property tests.

**Files to Update:**
1. `scripts/validation_config.yaml` - Add to property_test_requirements
2. `scripts/validate_property_tests.py` - NO CHANGES (auto-discovers)

**Changes:**

```yaml
property_test_requirements:
  trading_logic:
    modules:
      - "analytics/kelly.py"
      - "analytics/probability.py"
      - "analytics/ensemble.py"  # NEW
    required_properties:
      - "Kelly fraction in [0, 1] for all inputs"
      - "Edge detection is monotonic"
      - "Probabilities sum to 1.0"
      - "Ensemble weights sum to 1.0"  # NEW
```

**Test:**

```bash
python scripts/validate_property_tests.py --verbose
# Should check for tests/property/analytics/test_ensemble_properties.py
```

**Time:** 5 minutes
**Code Changes:** 0 (YAML-only)

---

### Pattern 6: Update Validator Logic

**Scenario:** validate_scd_queries.py needs to support Raw SQL queries (currently only SQLAlchemy).

**Files to Update:**
1. `scripts/validate_scd_queries.py` - Add raw SQL detection logic

**Changes:**

```python
# ADD NEW DETECTION PATTERN
def check_scd_queries(verbose: bool = False) -> tuple[bool, List[str]]:
    """..."""

    for python_file in python_files:
        content = python_file.read_text(encoding="utf-8")
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            for table in scd_tables:
                # EXISTING: SQLAlchemy patterns
                sqlalchemy_patterns = [
                    rf"\.query\({table.capitalize()}\)",
                    rf"from_\({table}\)",
                ]

                # NEW: Raw SQL patterns
                raw_sql_patterns = [
                    rf"SELECT .* FROM {table}",
                    rf"select .* from {table}",
                ]

                if any(re.search(p, line, re.IGNORECASE) for p in (sqlalchemy_patterns + raw_sql_patterns)):
                    # Check for row_current_ind filter
                    # ... (existing logic)
```

**Test:**

```bash
# 1. Update tests
# tests/unit/scripts/test_validate_scd_queries.py

def test_detects_raw_sql_violations():
    """Test detection of raw SQL queries without row_current_ind filter."""
    test_code = '''
def get_markets():
    cursor.execute("SELECT * FROM markets WHERE status = 'open'")
    '''

    # Should detect violation (no row_current_ind filter)
    passed, violations = validate_scd_queries()
    assert not passed
    assert "markets" in violations[0]

# 2. Run tests
python -m pytest tests/unit/scripts/test_validate_scd_queries.py -v

# 3. Run on codebase
python scripts/validate_scd_queries.py --verbose
```

**Time:** 30 minutes
**Code Changes:** ~50 lines (add raw SQL detection)

---

## Testing New Validators

### Local Testing Checklist

**Before committing new validator:**

- [ ] **Step 1: Unit Tests** (5 min)
  ```bash
  python -m pytest tests/unit/scripts/test_validate_<name>.py -v
  ```
  - All tests passing?
  - Edge cases covered?

- [ ] **Step 2: Run on Current Codebase** (2 min)
  ```bash
  python scripts/validate_<name>.py --verbose
  ```
  - Finds expected targets?
  - Violations legitimate or false positives?
  - Error messages actionable?

- [ ] **Step 3: Test with Violations** (5 min)
  - Create temporary violation in code
  - Run validator
  - Verify detection works
  - Verify fix suggestion helpful
  - Remove temporary violation

- [ ] **Step 4: Test Exception Handling** (3 min)
  - Add exception comment to violation
  - Run validator
  - Verify exception honored
  - Remove exception comment

- [ ] **Step 5: Test Exit Codes** (2 min)
  ```bash
  python scripts/validate_<name>.py
  echo $?  # Should be 0 (pass), 1 (fail), or 2 (warn)
  ```

- [ ] **Step 6: Test Performance** (1 min)
  ```bash
  time python scripts/validate_<name>.py
  ```
  - Pre-commit validators: <10s
  - Pre-push validators: <60s

- [ ] **Step 7: Test Graceful Degradation** (3 min)
  - Rename validation_config.yaml temporarily
  - Run validator
  - Verify falls back to defaults (exit code 2, warning message)
  - Restore validation_config.yaml

---

## Integration with Hooks/CI

### Pre-Commit Hook Integration

**For fast validators (<10s):**

```yaml
# .pre-commit-config.yaml

- repo: local
  hooks:
    - id: <pattern-name>-check
      name: <Pattern Name> Validation (Pattern <N>)
      entry: python scripts/validate_<name>.py
      language: system
      types: [python]
      pass_filenames: false
      verbose: true
```

**Test integration:**

```bash
# 1. Install pre-commit
pip install pre-commit
pre-commit install

# 2. Test hook
git add scripts/validate_<name>.py
git commit -m "test: Verify pre-commit hook"

# 3. Should run validator automatically
# Output: [PASS] or [FAIL]
```

### Pre-Push Hook Integration

**For thorough validators (10-60s):**

```bash
# .git/hooks/pre-push

#!/bin/bash
# Pre-push validation hook

# ... (existing steps 1-7)

# Step 8: <Pattern Name> Validation
echo "[8/10] <Pattern Name> validation..."
if ! python scripts/validate_<name>.py; then
    echo "❌ <Pattern Name> validation failed!"
    echo "Fix: <Actionable fix suggestion>"
    echo "Reference: DEVELOPMENT_PATTERNS Pattern <N>"
    exit 1
fi
echo "✅ <Pattern Name> validation passed"
echo ""
```

**Test integration:**

```bash
# 1. Create feature branch
git checkout -b test/<pattern-name>-validator

# 2. Make changes
git add .
git commit -m "test: Verify pre-push hook"

# 3. Push (triggers pre-push hook)
git push origin test/<pattern-name>-validator

# 4. Should run Step 8 automatically
# Output: [8/10] <Pattern Name> validation...
#         ✅ <Pattern Name> validation passed
```

### CI/CD Integration

**For comprehensive validation (2-5 min):**

```yaml
# .github/workflows/test.yml

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run <Pattern Name> Validation
        run: |
          python scripts/validate_<name>.py --verbose

      # ... (other CI steps)
```

**Test integration:**

```bash
# 1. Push to feature branch
git push origin feature/<branch-name>

# 2. Check GitHub Actions
gh run list --branch feature/<branch-name>

# 3. View run details
gh run view <run-id>

# 4. Verify validator ran successfully
# Output: Run <Pattern Name> Validation
#         [PASS] Validation passed
```

---

## Maintenance Sustainability

### Zero-Maintenance Design Principles

**1. Auto-Discovery Over Hardcoding**

❌ **HIGH MAINTENANCE (Hardcoded list):**

```python
SCD_TABLES = [
    "markets",
    "positions",
    "strategies",
    "models",
]
# PROBLEM: Requires code change every time new SCD table added
```

✅ **ZERO MAINTENANCE (Auto-discovery):**

```python
def discover_scd_tables() -> Set[str]:
    """
    Query database schema for tables with row_current_ind column.
    New SCD Type 2 tables automatically detected.
    """
    cursor.execute("""
        SELECT DISTINCT table_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name = 'row_current_ind'
    """)
    return {row[0] for row in cursor.fetchall()}
```

**2. YAML-Driven Configuration**

❌ **HIGH MAINTENANCE (Thresholds in code):**

```python
if coverage < 80:  # Infrastructure
    violations.append(...)
elif coverage < 85:  # Business logic
    violations.append(...)
elif coverage < 90:  # Critical path
    violations.append(...)
# PROBLEM: Requires code change to update thresholds
```

✅ **ZERO MAINTENANCE (YAML config):**

```python
def load_coverage_tiers() -> dict:
    config = yaml.safe_load(f)
    return config["coverage_tiers"]  # Read from YAML

tiers = load_coverage_tiers()
# Threshold changes = YAML edit only, no code changes
```

**3. Convention Over Configuration**

❌ **HIGH MAINTENANCE (Explicit mapping):**

```python
TEST_FILE_MAP = {
    "src/precog/analytics/kelly.py": "tests/property/test_kelly_properties.py",
    "src/precog/analytics/probability.py": "tests/property/test_probability_properties.py",
    # ... 50 more mappings
}
# PROBLEM: Requires manual entry for every new module
```

✅ **ZERO MAINTENANCE (Convention-based discovery):**

```python
def find_test_file(module_path: str) -> Path | None:
    """
    Convention: src/precog/<dir>/<name>.py → tests/property/<dir>/test_<name>_properties.py
    New modules automatically discovered via convention.
    """
    parts = Path(module_path).parts
    module_name = Path(module_path).stem

    # Try nested: tests/property/analytics/test_kelly_properties.py
    if len(parts) > 1:
        test_file = PROJECT_ROOT / "tests" / "property" / parts[0] / f"test_{module_name}_properties.py"
        if test_file.exists():
            return test_file

    # Try flat: tests/property/test_kelly_properties.py
    test_file = PROJECT_ROOT / "tests" / "property" / f"test_{module_name}_properties.py"
    if test_file.exists():
        return test_file

    return None
```

**4. Graceful Degradation**

❌ **FRAGILE (Hard failure on missing dependency):**

```python
import yaml
config = yaml.safe_load(f)  # Fails if PyYAML not installed
```

✅ **ROBUST (Fallback to defaults):**

```python
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

def load_config():
    if not YAML_AVAILABLE:
        return DEFAULT_CONFIG  # Use defaults

    try:
        return yaml.safe_load(f)
    except Exception:
        return DEFAULT_CONFIG  # Fallback on any error
```

**5. Single Source of Truth**

❌ **HIGH MAINTENANCE (Duplicate data):**

```python
# In validator
SCD_TABLES = ["markets", "positions", ...]

# In documentation
# DEVELOPMENT_PHASES: "SCD Type 2 tables: markets, positions, ..."

# In database schema
# schema.sql: CREATE TABLE markets (..., row_current_ind BOOLEAN)

# PROBLEM: 3 places to update when adding SCD table
```

✅ **ZERO MAINTENANCE (Query authoritative source):**

```python
def discover_scd_tables():
    """
    Query database schema (SINGLE SOURCE OF TRUTH).
    Documentation references this validator.
    Schema changes automatically detected.
    """
    cursor.execute("SELECT ... FROM information_schema.columns WHERE column_name = 'row_current_ind'")
    return {row[0] for row in cursor.fetchall()}
```

---

## Configuration Management

### validation_config.yaml Structure

**Complete Template:**

```yaml
# ===================================================================
# Workflow Enforcement Configuration
# ===================================================================
# Version: 1.0
# Purpose: Centralized configuration for all validation scripts
# Reference: docs/utility/ENFORCEMENT_MAINTENANCE_GUIDE.md
# ===================================================================

# Pattern 8: Configuration Synchronization (4-Layer Validation)
config_layers:
  tool_configs:
    description: "Build tool and linter configurations"
    patterns:
      - "pyproject.toml"
      - "ruff.toml"
      - ".pre-commit-config.yaml"
      - ".git/hooks/*"

  application_configs:
    description: "Application runtime configurations"
    patterns:
      - "src/precog/config/*.yaml"
      - "config/*.yaml"

  documentation:
    description: "Configuration documentation and guides"
    patterns:
      - "docs/guides/CONFIGURATION_GUIDE*.md"
      - "docs/guides/DEVELOPMENT_PATTERNS*.md"

  infrastructure:
    description: "Infrastructure-as-code configurations (Phase 5+)"
    patterns:
      - "terraform/*.tf"
      - "docker-compose*.yml"

# Pattern 13: Coverage Target Validation (Tier-Specific)
coverage_tiers:
  infrastructure: 80
  business_logic: 85
  critical_path: 90

  tier_patterns:
    infrastructure:
      - "src/precog/database/connection.py"
      - "src/precog/utils/logger.py"
      - "src/precog/config/config_loader.py"

    business_logic:
      - "src/precog/database/crud_operations.py"
      - "src/precog/analytics/strategy_manager.py"
      - "src/precog/analytics/model_manager.py"
      - "src/precog/trading/position_manager.py"

    critical_path:
      - "src/precog/api_connectors/kalshi_client.py"
      - "src/precog/api_connectors/kalshi_auth.py"
      - "src/precog/database/migrations/*.py"

# Pattern 10: Property-Based Testing Requirements
property_test_requirements:
  trading_logic:
    description: "Financial calculations requiring mathematical invariants"
    modules:
      - "analytics/kelly.py"
      - "analytics/probability.py"
      - "trading/edge_detector.py"
    required_properties:
      - "Kelly fraction in [0, 1] for all inputs"
      - "Edge detection is monotonic"
      - "Probabilities sum to 1.0"

  decimal_operations:
    description: "Currency and probability operations (Pattern 1)"
    modules:
      - "utils/decimal_ops.py"
    required_properties:
      - "Decimal precision maintained across operations"
      - "No float contamination"
      - "Rounding behavior consistent"

# Pattern 2: SCD Type 2 Query Validation
scd_type2_validation:
  description: "Slowly Changing Dimension Type 2 tables (immutable history)"
  discovery_method: "Query information_schema for tables with row_current_ind column"
  required_pattern: |
    .filter(table.c.row_current_ind == True)
  forbidden_patterns:
    - ".all()"  # Missing filter (gets ALL versions)
  exceptions:
    - "Historical audit query"
    - "Backfill script"

# Pattern 13: Test Fixture Requirements
test_fixture_requirements:
  integration_tests:
    description: "Tests requiring real database/API infrastructure"
    required_fixtures:
      - "db_pool"
      - "db_cursor"
      - "clean_test_data"
    forbidden_patterns:
      - "unittest\\.mock\\.patch\\(['\"]psycopg2\\.pool['\"]"
      - "mock_connection\\s*=\\s*Mock\\("
    allowed_exceptions:
      - "Unit test - mock OK"

# Phase Deliverables (Phase Start/Completion Validation)
phase_deliverables:
  "1.5":
    name: "Manager Layer Implementation"
    deliverables:
      - name: "Strategy Manager"
        file: "src/precog/analytics/strategy_manager.py"
        coverage_target: 85
        test_types: ["unit", "integration"]

      - name: "Model Manager"
        file: "src/precog/analytics/model_manager.py"
        coverage_target: 85
        test_types: ["unit", "integration"]

      - name: "Position Manager"
        file: "src/precog/trading/position_manager.py"
        coverage_target: 85
        test_types: ["unit", "integration"]

  "2":
    name: "Live Data Integration"
    deliverables:
      - name: "ESPN Integration"
        file: "src/precog/api_connectors/espn_client.py"
        coverage_target: 90
        test_types: ["unit", "integration", "property"]

      - name: "WebSocket Handler"
        file: "src/precog/realtime/websocket_handler.py"
        coverage_target: 85
        test_types: ["unit", "integration", "stress"]
```

### Updating Configuration

**When to update validation_config.yaml:**

1. **New Phase Starting** → Add phase_deliverables section
2. **New Module Created** → Add to appropriate tier_patterns
3. **New Pattern Adopted** → Add pattern validation section
4. **Tier Thresholds Change** → Update coverage_tiers values
5. **New Test Type Required** → Add to test_fixture_requirements

**Validation after updates:**

```bash
# 1. Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('scripts/validation_config.yaml'))"

# 2. Test validators with new config
python scripts/validate_code_quality.py --verbose
python scripts/validate_property_tests.py --verbose
python scripts/validate_test_fixtures.py --verbose
python scripts/validate_phase_start.py --phase <N> --verbose

# 3. Check for regressions
./scripts/validate_all.sh
```

---

## Troubleshooting

### Common Issues

#### Issue 1: Validator reports false positives

**Symptom:**
```bash
$ python scripts/validate_scd_queries.py
[FAIL] 10 queries missing row_current_ind filter:
  src/precog/utils/helpers.py:42 - Query on 'markets' table missing row_current_ind filter
```

**But the code is correct:**
```python
# helpers.py:42
def get_current_markets():
    """Historical audit query - intentionally queries all versions."""
    return session.query(Markets).all()
```

**Root Cause:** Exception comment not detected (too far from violation).

**Fix:**

```python
# Move exception comment closer (within 3 lines)
def get_current_markets():
    # Historical audit query
    return session.query(Markets).all()
```

**Or update validator:** Increase context window in `check_scd_queries()`:

```python
# OLD: 3 lines before
comment_lines = lines[max(0, line_num - 3) : line_num]

# NEW: 5 lines before (capture docstrings)
comment_lines = lines[max(0, line_num - 5) : line_num]
```

---

#### Issue 2: Validator times out on large codebase

**Symptom:**
```bash
$ python scripts/validate_property_tests.py
[WARN] Validation failed: Timeout after 120 seconds
```

**Root Cause:** Validator scans too many files or runs pytest for every module.

**Fix 1: Increase timeout** (quick fix):

```python
# In validator main()
result = subprocess.run([...], timeout=300)  # 120 → 300 seconds
```

**Fix 2: Optimize discovery** (better fix):

```python
# OLD: Scan ALL Python files
python_files = list((PROJECT_ROOT / "src").rglob("*.py"))

# NEW: Scan only files matching tier patterns
tier_config = load_coverage_tiers()
tier_patterns = tier_config["tier_patterns"]

python_files = []
for tier, patterns in tier_patterns.items():
    for pattern in patterns:
        python_files.extend(PROJECT_ROOT.glob(pattern))
```

---

#### Issue 3: Validator fails with exit code 2 (WARN)

**Symptom:**
```bash
$ python scripts/validate_code_quality.py
[WARN] PyYAML not available - using default configuration
[WARN] Validation skipped
$ echo $?
2
```

**Root Cause:** Missing dependency (PyYAML).

**Fix:**

```bash
# Install missing dependency
pip install pyyaml

# Verify installation
python -c "import yaml; print('PyYAML OK')"

# Re-run validator
python scripts/validate_code_quality.py
# Should now return exit code 0 or 1
```

---

#### Issue 4: Pre-commit hook doesn't run validator

**Symptom:**
```bash
$ git commit -m "test"
# No validator output shown
```

**Root Cause:** Validator not added to `.pre-commit-config.yaml`, or pre-commit not installed.

**Fix:**

```bash
# 1. Check if pre-commit installed
pre-commit --version

# 2. If not installed
pip install pre-commit
pre-commit install

# 3. Check .pre-commit-config.yaml
grep "validate_<name>" .pre-commit-config.yaml

# 4. If missing, add hook:
# (See "Integration with Hooks/CI" section above)

# 5. Test hook manually
pre-commit run --all-files
```

---

#### Issue 5: Validator doesn't detect new modules

**Symptom:**
```bash
$ python scripts/validate_property_tests.py
[PASS] All required modules have comprehensive property tests

# But new module src/precog/analytics/ensemble.py has NO property tests!
```

**Root Cause:** Module not added to validation_config.yaml.

**Fix:**

```yaml
# validation_config.yaml

property_test_requirements:
  trading_logic:
    modules:
      - "analytics/kelly.py"
      - "analytics/probability.py"
      - "analytics/ensemble.py"  # ADD THIS
```

```bash
# Re-run validator
python scripts/validate_property_tests.py
# Should now report violation for ensemble.py
```

---

### Getting Help

**If issue persists after troubleshooting:**

1. **Check validator verbose output:**
   ```bash
   python scripts/validate_<name>.py --verbose
   ```

2. **Check validation_config.yaml syntax:**
   ```bash
   python -c "import yaml; print(yaml.safe_load(open('scripts/validation_config.yaml')))"
   ```

3. **Check validator tests:**
   ```bash
   python -m pytest tests/unit/scripts/test_validate_<name>.py -v
   ```

4. **Review recent changes:**
   ```bash
   git log --oneline --since="1 week ago" -- scripts/validate_<name>.py scripts/validation_config.yaml
   ```

5. **Create GitHub issue:**
   - Title: `[Validator] <Brief description of issue>`
   - Include: validator name, command run, full error output, expected vs. actual behavior
   - Label: `validation`, `bug`

---

## Summary

### Key Takeaways

1. **Validators enforce critical patterns** - Automate what manual review misses
2. **YAML-driven configuration** - Update rules without code changes
3. **Auto-discovery design** - Zero maintenance for new modules/tables
4. **Graceful degradation** - Fallback to defaults on errors
5. **Defense in depth** - 4 layers (pre-commit → pre-push → CI/CD → branch protection)

### Maintenance Checklist

**Monthly Review (15 min):**
- [ ] Review validation_config.yaml for outdated patterns
- [ ] Check validator test coverage (>80%)
- [ ] Review false positive reports (GitHub issues)
- [ ] Update tier thresholds if needed
- [ ] Add new phase deliverables if phase started

**Quarterly Review (1 hour):**
- [ ] Review all 12 validators for optimization opportunities
- [ ] Update ENFORCEMENT_MAINTENANCE_GUIDE with new examples
- [ ] Run full validation suite on codebase
- [ ] Update DEVELOPMENT_PATTERNS with new patterns
- [ ] Review validator execution times (optimize slow validators)

---

**END OF ENFORCEMENT_MAINTENANCE_GUIDE.md V1.0**
