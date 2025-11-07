# Development Philosophy

---
**Version:** 1.0
**Created:** 2025-11-07
**Last Updated:** 2025-11-07
**Purpose:** Core principles guiding Precog development
**Target Audience:** All developers working on Precog
**Status:** ✅ Active - Follow in ALL development work
---

## Overview

This document defines the foundational development principles for Precog. These principles guide **every decision** from architecture to implementation to documentation.

**Why This Document Matters:**
- **Consistency:** All developers follow the same patterns
- **Quality:** Principles prevent common mistakes
- **Onboarding:** New developers understand "the Precog way"
- **Decision-Making:** When in doubt, refer to these principles

**How to Use:**
1. **Before implementation:** Review relevant principles
2. **During code review:** Check adherence to principles
3. **Before phase completion:** Validate all principles followed
4. **When making decisions:** Consult philosophy for guidance

---

## Table of Contents

1. [Test-Driven Development (TDD)](#1-test-driven-development-tdd)
2. [Defense in Depth (DID)](#2-defense-in-depth-did) ⚠️ **CORE PRINCIPLE**
3. [Documentation-Driven Development (DDD)](#3-documentation-driven-development-ddd)
4. [Data-Driven Design](#4-data-driven-design)
5. [Fail-Safe Defaults](#5-fail-safe-defaults)
6. [Explicit Over Clever](#6-explicit-over-clever)
7. [Cross-Document Consistency](#7-cross-document-consistency)
8. [Maintenance Visibility](#8-maintenance-visibility)
9. [Security by Default](#9-security-by-default)
10. [Summary Checklist](#summary-philosophy-checklist)

---

## 1. Test-Driven Development (TDD)

### The Red-Green-Refactor Cycle

**Philosophy:** Write tests BEFORE implementation. Tests are specifications.

**The Cycle:**
1. **🔴 RED** - Write failing test that describes desired behavior
2. **🟢 GREEN** - Write minimal code to make test pass
3. **🔵 REFACTOR** - Improve code quality without changing behavior

**Why This Matters:**
- **Tests document intent** - Show what SHOULD happen
- **Catches regressions immediately** - Know when you break something
- **Forces modular design** - Testable code is better code
- **80%+ coverage required** - Not negotiable

**Example Workflow:**

```python
# 🔴 RED: Write test first (describes what we want)
def test_kalshi_balance_returns_decimal():
    """Balance must be Decimal for sub-penny precision."""
    client = KalshiClient()
    balance = client.get_balance()

    assert isinstance(balance, Decimal)  # FAILS - not implemented yet
    assert balance == Decimal("1234.5678")

# 🟢 GREEN: Implement minimal solution
def get_balance(self) -> Decimal:
    """Fetch account balance from Kalshi API."""
    response = self._make_request('/portfolio/balance')
    return Decimal(str(response['balance_dollars']))  # PASSES

# 🔵 REFACTOR: Improve (error handling, logging, caching)
def get_balance(self) -> Decimal:
    """
    Fetch account balance from Kalshi API.

    Returns:
        Decimal: Account balance in dollars (e.g., Decimal("1234.5678"))

    Raises:
        RequestException: If API request fails

    Example:
        >>> client = KalshiClient()
        >>> balance = client.get_balance()
        >>> print(f"Balance: ${balance}")
        Balance: $1234.5678
    """
    try:
        response = self._make_request('/portfolio/balance')
        balance = Decimal(str(response['balance_dollars']))
        logger.info(f"Account balance fetched: ${balance}")
        return balance
    except RequestException as e:
        logger.error(f"Failed to fetch balance: {e}")
        raise
```

**Coverage Requirements:**
- **≥80% overall coverage** (measured by pytest-cov)
- **100% for critical paths** (financial calculations, trading logic)
- **100% for security code** (authentication, credential handling)

**Related Documents:**
- `docs/foundation/TESTING_STRATEGY_V2.0.md`
- `CLAUDE.md` Section 7 (Common Tasks - Task 1)

---

## 2. Defense in Depth (DID)

### Multiple Independent Validation Layers

**Philosophy:** Never rely on a single layer of validation. Multiple independent checks at different stages catch different error types.

⚠️ **CORE PRINCIPLE:** This is foundational to Precog's quality and security architecture.

**Why Defense in Depth:**
- **No single point of failure** - If one layer misses an issue, others catch it
- **Different layers catch different issues** - Syntax errors vs logic errors vs security issues
- **Early layers are fast** - Instant feedback for common issues
- **Later layers are thorough** - Comprehensive checks before deployment
- **Cost-effective** - Catch issues early (seconds) vs late (hours/days)

---

### Layer Architecture

**The 4-Layer Validation Strategy:**

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Pre-Commit Hooks (~2-5 seconds)                    │
│ - 12 automated checks on every commit                       │
│ - Auto-fixes: formatting, whitespace, line endings          │
│ - Blocks: linting errors, type errors, credentials          │
│ - Catches: 60-70% of issues                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Pre-Push Hooks (~30-60 seconds)                    │
│ - 5 comprehensive validation steps before push              │
│ - Includes: Unit tests, full type checking, security scan   │
│ - Blocks: Test failures, type errors, security issues       │
│ - Catches: 80-90% of issues (first time tests run locally)  │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: CI/CD Pipeline (~2-5 minutes)                      │
│ - Full test matrix (Python 3.12/3.13/3.14, Ubuntu/Windows)  │
│ - 6 required status checks for PR merge                     │
│ - Blocks: PR merge until all checks pass                    │
│ - Catches: 99%+ of issues (comprehensive multi-platform)    │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Branch Protection (~instant gate)                  │
│ - Enforces PR workflow, no direct commits to main           │
│ - Requires all CI checks passing before merge               │
│ - Requires conversation resolution                          │
│ - Final enforcement gate (cannot be bypassed)               │
└─────────────────────────────────────────────────────────────┘
```

---

### Defense in Depth Examples

#### Example 1: Decimal Precision (4 Layers)

**Why 4 layers:** Float precision loss would cause financial calculation errors.

```python
# Layer 1: Type hints (caught by mypy in pre-commit)
def calculate_profit(entry_price: Decimal, exit_price: Decimal) -> Decimal:
    return exit_price - entry_price  # mypy ensures Decimal types

# Layer 2: Database schema (DECIMAL(10,4) enforced)
CREATE TABLE trades (
    entry_price DECIMAL(10, 4) NOT NULL,  -- PostgreSQL type check
    exit_price DECIMAL(10, 4) NOT NULL
);

# Layer 3: Validation script (schema consistency check)
price_columns = {
    'trades': ['entry_price', 'exit_price']  # Script validates DECIMAL(10,4)
}

# Layer 4: Runtime validation (TypedDict + assertions)
class Trade(TypedDict):
    entry_price: Decimal  # TypedDict enforces type
    exit_price: Decimal

def record_trade(trade: Trade):
    assert isinstance(trade['entry_price'], Decimal), "Price must be Decimal"
```

**Result:** Float values caught at FOUR different points before causing errors.

---

#### Example 2: Security (3 Layers)

**Why 3 layers:** Hardcoded credentials would leak sensitive data.

```bash
# Layer 1: Pre-commit security scan (instant, blocks commit)
git add config.py  # Contains: password = "mypass123"
git commit
# → Hook blocks commit: "ERROR: Found hardcoded credentials!"

# Layer 2: Pre-push security scan (comprehensive, blocks push)
git push
# → Step 4: Security Scan runs Bandit
# → Bandit detects hardcoded password
# → Push blocked

# Layer 3: CI/CD security scan (recorded proof)
# → GitHub Actions runs security-scan job
# → Fails with detailed report
# → PR cannot be merged (branch protection enforces)
```

**Result:** No way to merge hardcoded credentials into main branch.

---

#### Example 3: Documentation Consistency (3 Layers)

**Why 3 layers:** Documentation drift causes confusion and implementation errors.

```bash
# Layer 1: Manual review (phase completion protocol Step 3)
# Developer checks: "Does code match docs?"

# Layer 2: Automated validation (validate_docs.py)
python scripts/validate_docs.py
# → Checks: Cross-references, version consistency, missing docs
# → Runs in pre-push hooks

# Layer 3: Update cascade rules (CLAUDE.md Section 5)
# → When adding REQ-XXX-NNN:
#    1. Add to MASTER_REQUIREMENTS
#    2. Add to REQUIREMENT_INDEX
#    3. Add to DEVELOPMENT_PHASES
#    4. Update MASTER_INDEX
# → Multiple documents prevent single-doc drift
```

**Result:** Documentation stays synchronized across all foundation docs.

---

### When to Apply Defense in Depth

**Always apply multiple layers for:**
- ✅ **Financial calculations** (Decimal precision, trade attribution)
- ✅ **Security-critical code** (credentials, authentication, SQL injection)
- ✅ **Data integrity** (database schema, SCD Type 2, foreign keys)
- ✅ **Configuration validation** (YAML syntax, required fields, type checking)
- ✅ **Documentation consistency** (cross-references, versioning, requirements)

**Single layer acceptable for:**
- ❌ **Trivial utilities** (string formatting, date parsing)
- ❌ **Internal tools** (scripts for manual use only)
- ❌ **Temporary debugging** (console logging, test fixtures)

---

### Cost-Benefit Analysis

| Layer | Time | What It Catches | When It Runs | Bypassable? |
|-------|------|-----------------|--------------|-------------|
| **Pre-Commit** | 2-5s | Syntax, formatting, basic security | Every commit | Yes (`--no-verify`) |
| **Pre-Push** | 30-60s | Tests, types, comprehensive security | Every push | Yes (`--no-verify`) |
| **CI/CD** | 2-5min | Multi-platform, integration, coverage | Every push (GitHub) | No (recorded) |
| **Branch Protection** | 0s | PR workflow, CI pass requirement | PR merge | No (enforced) |

**Key Insight:**
- **Layer 1+2 are bypassable** (local developer control) but provide instant feedback
- **Layer 3+4 are NOT bypassable** (final enforcement) but slower
- **Together:** Fast feedback + guaranteed enforcement = best of both worlds

---

### Defense in Depth Checklist

Before marking any feature complete, verify defense in depth:

- [ ] **Multiple validation layers implemented?**
  - [ ] Early layer (pre-commit/pre-push) for fast feedback?
  - [ ] Late layer (CI/CD) for comprehensive enforcement?
  - [ ] Runtime layer (assertions, type checks) as last resort?

- [ ] **Each layer checks different aspects?**
  - [ ] Syntax/formatting in pre-commit?
  - [ ] Tests/types in pre-push?
  - [ ] Multi-platform/integration in CI?

- [ ] **No single point of failure?**
  - [ ] If one layer disabled, do others still catch issues?
  - [ ] If local checks bypassed, does CI catch it?

- [ ] **Appropriate for criticality?**
  - [ ] Financial code has 4+ layers?
  - [ ] Security code has 3+ layers?
  - [ ] Non-critical code has 2+ layers?

**Related Documents:**
- `CLAUDE.md` Section 3.1-3.3 (Pre-commit, Pre-push, Branch protection workflows)
- `.pre-commit-config.yaml` - Layer 1 configuration
- `.git/hooks/pre-push` - Layer 2 configuration
- `.github/workflows/ci.yml` - Layer 3 configuration
- `docs/utility/GITHUB_BRANCH_PROTECTION_CONFIG.md` - Layer 4 configuration

---

## 3. Documentation-Driven Development (DDD)

### Document Before Implementing

**Philosophy:** Requirements and architecture decisions PRECEDE code. No code without docs.

**The Workflow:**
1. **REQUIREMENTS** - Add REQ-XXX-NNN to MASTER_REQUIREMENTS
2. **ARCHITECTURE** - Add ADR-XXX to ARCHITECTURE_DECISIONS
3. **SPECIFICATION** - Create supplementary spec (if complex)
4. **IMPLEMENTATION** - Write code that fulfills documented requirements
5. **UPDATE** - Mark REQ/ADR as complete, update indexes

**Why This Matters:**
- **Prevents "we built the wrong thing"** - Requirements clear upfront
- **Makes requirements traceable** - Every line of code → REQ-XXX-NNN
- **Enables accurate impact analysis** - Know what depends on what
- **Prevents documentation drift** - Docs lead, code follows

**Example: Adding New API Client**

```markdown
## STEP 1: Add Requirement (MASTER_REQUIREMENTS)

**REQ-API-008: Polymarket API Integration**
- **Phase:** 3
- **Priority:** 🟡 High
- **Status:** 🔵 Planned
- **Description:** Integrate Polymarket API for market data fetching
  - REST endpoints: /markets, /events, /positions
  - WebSocket for live updates
  - Rate limiting: 60 req/min
  - Authentication: API key
- **Related:** ADR-055 (Polymarket Auth Strategy)

## STEP 2: Add Architecture Decision (ARCHITECTURE_DECISIONS)

### ADR-055: Polymarket Authentication Strategy

**Decision #55**
**Phase:** 3
**Status:** 🔵 Planned

**Decision:** Use API key authentication for Polymarket (not OAuth)

**Rationale:**
- Polymarket API uses simple API key auth
- Simpler than OAuth (no token refresh needed)
- Consistent with Kalshi pattern (API key in headers)

**Implementation:**
- API key in .env: `POLYMARKET_API_KEY`
- Header: `Authorization: Bearer {api_key}`

**Related Requirements:** REQ-API-008

## STEP 3: Update Indexes

Add to REQUIREMENT_INDEX:
| REQ-API-008 | Polymarket API Integration | 3 | High | 🔵 Planned |

Add to ADR_INDEX:
| ADR-055 | Polymarket Authentication | 3 | 🔵 Planned | 🟡 High |

## STEP 4: NOW Write Code

```python
# polymarket_client.py - Implementation follows documented requirements
class PolymarketClient:
    """
    Polymarket API client.

    Implements REQ-API-008: Polymarket API Integration
    Uses ADR-055: API key authentication strategy
    """
    def __init__(self):
        self.api_key = os.getenv('POLYMARKET_API_KEY')
        # ... implementation
```

## STEP 5: Mark Complete

Update MASTER_REQUIREMENTS:
- REQ-API-008 status: 🔵 Planned → ✅ Complete

Update REQUIREMENT_INDEX:
| REQ-API-008 | Polymarket API Integration | 3 | High | ✅ Complete |

Update DEVELOPMENT_PHASES:
- [✅] Polymarket API client implementation
```

**Related Documents:**
- `CLAUDE.md` Section 5 (Document Cohesion & Consistency)
- `CLAUDE.md` Section 7 (Common Tasks - Update Cascade Rules)

---

## 4. Data-Driven Design

### Configuration Over Code

**Philosophy:** Make data structures explicit, visible, and maintainable. Prefer dicts/lists over hard-coded logic.

**Why This Matters:**
- **Easy to update** - Change data, not code
- **Maintenance time visible** - "5 minutes per table" documented
- **Junior developers can contribute** - Update list, not rewrite logic
- **Self-documenting** - Structure shows intent

**Good Example (Data-Driven):**

```python
# ✅ Configuration explicit and maintainable
price_columns = {
    'markets': ['yes_bid', 'yes_ask', 'no_bid', 'no_ask'],
    'positions': ['entry_price', 'exit_price', 'current_price'],
    'trades': ['price', 'fill_price'],
    'edges': ['edge_probability'],
    # Future tables: Add here when implementing new price-related tables
    # Example:
    # 'portfolio': ['total_value', 'cash_balance'],  # Phase 5
}

def validate_decimal_precision(table_name: str) -> bool:
    """Validate price columns are DECIMAL(10,4)."""
    if table_name not in price_columns:
        return True  # Skip validation for non-price tables (fail-safe)

    columns_to_check = price_columns[table_name]

    for col_name in columns_to_check:
        # ... validation logic (SAME for all tables)
        column_type = get_column_type(table_name, col_name)
        if column_type != "DECIMAL(10,4)":
            errors.append(f"{table_name}.{col_name}: Expected DECIMAL(10,4), got {column_type}")

    return len(errors) == 0
```

**Bad Example (Logic-Driven):**

```python
# ❌ Hard-coded logic requires code changes for every table
def validate_decimal_precision(table_name: str) -> bool:
    """Validate price columns are DECIMAL(10,4)."""
    if table_name == 'markets':
        columns_to_check = ['yes_bid', 'yes_ask', 'no_bid', 'no_ask']
        for col_name in columns_to_check:
            # ... validation logic (DUPLICATED per table)
    elif table_name == 'positions':
        columns_to_check = ['entry_price', 'exit_price', 'current_price']
        for col_name in columns_to_check:
            # ... validation logic (DUPLICATED again)
    elif table_name == 'trades':
        columns_to_check = ['price', 'fill_price']
        for col_name in columns_to_check:
            # ... validation logic (DUPLICATED yet again)
    # ... repeat for EVERY table (unmaintainable!)
```

**When to Use Data-Driven Design:**
- ✅ **Validation rules** (lists of columns, tables, required fields)
- ✅ **Configuration mappings** (API endpoints, error codes)
- ✅ **Feature flags** (enable/disable functionality)
- ✅ **Test fixtures** (sample data, mock responses)
- ✅ **Database schemas** (table lists, column lists)

**When NOT to Use:**
- ❌ **Complex business logic** (multi-step calculations)
- ❌ **Stateful algorithms** (trading strategies, exit conditions)
- ❌ **Dynamic behavior** (behavior changes based on runtime data)

**Reference:** `scripts/validate_schema_consistency.py` (lines 247-409) - Excellent example of data-driven validation

---

## 5. Fail-Safe Defaults

### Graceful Degradation Over Crashes

**Philosophy:** Validation scripts should skip gracefully, not crash. Better to warn than to block.

**Why This Matters:**
- **Development continues** - Incomplete validation doesn't block work
- **Clear errors explain HOW to fix** - Not just "failed"
- **Manual maintenance doesn't break automation** - Can update incrementally
- **Progressive enhancement** - Add checks over time

**Example (Fail-Safe Validation):**

```python
def validate_price_columns(table_name: str) -> tuple[bool, list[str]]:
    """
    Validate price columns are DECIMAL(10,4).

    Fail-safe design:
    - Skip if table not in price_columns dict (maybe not a price table)
    - Skip if table doesn't exist in database (maybe not created yet)
    - Only fail if table EXISTS and has WRONG precision (actual error)
    """
    # Fail-safe #1: Skip if not a known price table
    if table_name not in price_columns:
        logger.debug(f"Skipping {table_name} - not in price_columns dict")
        return True, []  # Success (skipped)

    # Fail-safe #2: Skip if table doesn't exist yet
    columns = get_table_columns(table_name)
    if not columns:
        logger.warning(f"Table {table_name} not found - skipping validation")
        return True, []  # Success (skipped)

    # Only fail if table EXISTS and column type is WRONG
    errors = []
    for col_name in price_columns[table_name]:
        col_info = get_column_info(table_name, col_name)

        # Fail-safe #3: Skip if column doesn't exist (maybe not added yet)
        if not col_info:
            logger.warning(f"{table_name}.{col_name} not found - skipping")
            continue

        # NOW check precision (only fail if wrong type)
        if col_info['data_type'] != 'numeric' or col_info['precision'] != 10:
            errors.append(f"{table_name}.{col_name}: Expected DECIMAL(10,4), got {col_info['data_type']}")

    if errors:
        for error in errors:
            logger.error(error)
        return False, errors
    else:
        logger.info(f"{table_name}: All price columns are DECIMAL(10,4) ✓")
        return True, []
```

**Result:**
- ✅ Validation runs even if schema incomplete
- ✅ Skips gracefully when data missing
- ✅ Only fails when actual type mismatch found
- ✅ Clear logs explain what was checked and why

**Related:** All validation scripts (`validate_schema_consistency.py`, `validate_docs.py`)

---

## 6. Explicit Over Clever

### Code Clarity Trumps Brevity

**Philosophy:** Write code that's obvious, not code that's short. Favor verbose clarity over terse cleverness.

**Why This Matters:**
- **Onboarding time reduced** - New developers understand immediately
- **Bugs easier to spot** - Logic is visible
- **Maintenance easier** - No "what does this do?" moments
- **Performance rarely matters** - For business logic (not hot loops)

**Good Example (Explicit):**

```python
def is_market_tradeable(market: Market) -> bool:
    """
    Check if market can be traded.

    A market is tradeable if ALL conditions met:
    1. Status is "open"
    2. Close time is in the future
    3. Volume is ≥100 contracts

    Returns:
        True if tradeable, False otherwise (with logged reason)
    """
    if market.status != "open":
        logger.info(f"Market {market.ticker} not tradeable - status is {market.status} (expected 'open')")
        return False

    if market.close_time < datetime.now():
        logger.info(f"Market {market.ticker} not tradeable - already closed at {market.close_time}")
        return False

    if market.volume < 100:
        logger.info(f"Market {market.ticker} not tradeable - low volume ({market.volume} contracts, need ≥100)")
        return False

    logger.info(f"Market {market.ticker} is tradeable ✓")
    return True
```

**Bad Example (Clever):**

```python
def is_market_tradeable(m):
    """Check if market can be traded."""
    return m.status == "open" and m.close_time > datetime.now() and m.volume >= 100
    # Which condition failed? No idea! No logging. Impossible to debug.
```

**When Verbosity Matters:**
- ✅ **Validation logic** - Explicit checks with clear error messages
- ✅ **Error handling** - Detailed try/except blocks
- ✅ **Financial calculations** - Every step visible and commented
- ✅ **Security-critical code** - No magic, no cleverness

**When Brevity Okay:**
- ✅ **Simple getters/setters** - `def get_price(self): return self.price`
- ✅ **List comprehensions** (if readable) - `[x for x in items if x.active]`
- ✅ **Standard library idioms** - `with open(...) as f:`

---

## 7. Cross-Document Consistency

### Single Source of Truth for Everything

**Philosophy:** Every piece of information has ONE canonical location. Updates cascade to dependent docs.

**Why This Matters:**
- **No contradictions** - Avoids "which doc is correct?"
- **Changes propagate systematically** - Update cascade rules prevent drift
- **Makes onboarding reliable** - Docs don't contradict each other
- **Enables automation** - Consistency checks can be automated

**The Workflow (Adding Requirement):**

```markdown
1. **Canonical:** MASTER_REQUIREMENTS_V2.10.md
   Add REQ-XXX-NNN here FIRST

2. **Cascade to:**
   - REQUIREMENT_INDEX.md (add to table)
   - DEVELOPMENT_PHASES_V1.4.md (add to phase tasks)
   - MASTER_INDEX_V2.11.md (update version if renamed)
   - SESSION_HANDOFF.md (document change)

3. **Validate:**
   python scripts/validate_docs.py  # Checks consistency

4. **DO NOT skip any step!**
```

**Example (Adding REQ-CLI-007):**

```markdown
Step 1: Add to MASTER_REQUIREMENTS V2.10 → V2.11
**REQ-CLI-007: Market Filtering Command**
- Phase: 2
- Priority: High
- Description: CLI command to filter markets by criteria

Step 2: Add to REQUIREMENT_INDEX
| REQ-CLI-007 | Market Filtering Command | 2 | High | 🔵 Planned |

Step 3: Add to DEVELOPMENT_PHASES Phase 2 tasks
- [ ] CLI command: `main.py filter-markets --sport NFL --min-volume 1000`

Step 4: Update MASTER_INDEX
| MASTER_REQUIREMENTS_V2.11.md | ✅ | v2.11 | ... | UPDATED from V2.10 |

Step 5: Update SESSION_HANDOFF
## This Session Completed
- ✅ Added REQ-CLI-007 for market filtering (Phase 2 planning)
```

**Related Documents:**
- `CLAUDE.md` Section 5 (Document Cohesion & Consistency)
- `CLAUDE.md` Section 5 (Update Cascade Rules)

---

## 8. Maintenance Visibility

### Document Maintenance Burden Explicitly

**Philosophy:** Every manual update should have time estimate and clear instructions. No "figure it out" maintenance.

**Why This Matters:**
- **Realistic effort estimation** - Know how long updates take
- **Junior developers can contribute** - Clear instructions provided
- **Prevents "I forgot to update X"** - Explicit reminders
- **Makes automation decisions data-driven** - "5 min manual" vs "2 hours to automate"

**Example: Validation Script Maintenance Guide**

```python
"""
MAINTENANCE GUIDE:
==================
When adding NEW tables with price/probability columns:
1. Add table_name to price_columns dict below
2. List all price/probability column names for that table
3. Tag with phase number for tracking (e.g., # Phase 3)
4. Run validation: python scripts/validate_schema_consistency.py

Maintenance time: ~5 minutes per new price table

Example:
    price_columns = {
        'markets': ['yes_bid', 'yes_ask', ...],  # Phase 1
        'odds_history': ['historical_odds'],      # Phase 3
        'portfolio': ['total_value'],             # Phase 5
    }

When to update:
- Adding new table with DECIMAL columns
- Adding price/probability column to existing table
- Implementing Phase 3, 4, or 5 financial features

How to test:
    python scripts/validate_schema_consistency.py
    # Expected: All price tables pass DECIMAL(10,4) check
"""

# CONFIGURATION: Price/probability columns by table
price_columns = {
    'markets': ['yes_bid', 'yes_ask', 'no_bid', 'no_ask'],
    'positions': ['entry_price', 'exit_price', 'current_price'],
    'trades': ['price', 'fill_price'],
    # Future tables: Add here (5 min per table)
}
```

**Where to Add Maintenance Guides:**
- ✅ **Validation scripts** - Which lists/dicts to update
- ✅ **Configuration files** - Which sections need updates
- ✅ **Database migrations** - Which validations to run
- ✅ **Documentation templates** - Which sections to customize

**Related:** All validation scripts have comprehensive maintenance guides

---

## 9. Security by Default

### No Credentials in Code, Ever

**Philosophy:** Zero tolerance for hardcoded secrets. Environment variables for all credentials.

**Why This Matters:**
- **Prevents accidental credential leaks** - Git history doesn't expose secrets
- **Enables per-environment configuration** - Dev/staging/prod use different creds
- **Makes credential rotation safe** - Update .env, don't touch code
- **Meets security compliance requirements** - SOC2, PCI-DSS, etc.

**Always Use Environment Variables:**

```python
# ✅ CORRECT: Environment variables
import os
from dotenv import load_dotenv

load_dotenv()

db_password = os.getenv('DB_PASSWORD')
api_key = os.environ['KALSHI_API_KEY']  # Raises KeyError if missing (fail-fast)

# Validate credentials exist
if not db_password:
    raise ValueError("DB_PASSWORD environment variable not set")

# Use in connection string
db_url = f"postgresql://user:{db_password}@localhost:5432/dbname"
```

**Never Hardcode:**

```python
# ❌ NEVER: Hardcoded credentials
password = "mypassword123"
api_key = "sk_live_abc123xyz"
db_url = "postgresql://user:password123@localhost/db"
```

**Pre-Commit Security Scan (Mandatory):**

```bash
# Runs automatically on every commit (pre-commit hook)
git add config.py
git commit -m "Update config"

# Hook runs security scan:
git grep -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]" -- '*.py'

# If matches found:
# ❌ ERROR: Found potential hardcoded credentials!
# Commit blocked.

# Expected result:
# ✅ No hardcoded credentials detected
# Commit allowed.
```

**Defense in Depth (3 Layers):**
1. **Pre-commit hook** - Blocks commit with hardcoded credentials
2. **Pre-push hook** - Bandit security scan (comprehensive)
3. **CI/CD** - Security scan job (recorded proof)

**Related Documents:**
- `docs/utility/SECURITY_REVIEW_CHECKLIST.md`
- `CLAUDE.md` Section 8 (Security Guidelines)
- `CLAUDE.md` Section 4 - Pattern 4 (Security)

---

## Summary: Philosophy Checklist

Before marking any feature complete, validate ALL principles followed:

- [ ] **TDD:** Tests written before implementation? (80%+ coverage)
- [ ] **DID:** Multiple validation layers implemented? (pre-commit + pre-push + CI)
- [ ] **DDD:** Requirements/ADRs documented before code? (REQ-XXX-NNN, ADR-XXX)
- [ ] **Data-Driven:** Configuration externalized (not hard-coded)?
- [ ] **Fail-Safe:** Validation scripts skip gracefully (don't crash)?
- [ ] **Explicit:** Code clarity prioritized over brevity?
- [ ] **Consistent:** All dependent docs updated? (follow cascade rules)
- [ ] **Maintainable:** Maintenance guides written? (time estimates provided)
- [ ] **Secure:** No hardcoded credentials? (all in .env)

**If ANY box unchecked → Feature NOT complete.**

---

## Related Documentation

**Testing & Validation:**
- `docs/foundation/TESTING_STRATEGY_V2.0.md` - Testing infrastructure
- `docs/foundation/VALIDATION_LINTING_ARCHITECTURE_V1.0.md` - Code quality

**Process & Workflow:**
- `CLAUDE.md` Section 3 (Session Handoff Workflow)
- `CLAUDE.md` Section 4 (Critical Patterns)
- `CLAUDE.md` Section 5 (Document Cohesion & Consistency)
- `CLAUDE.md` Section 8 (Security Guidelines)
- `CLAUDE.md` Section 9 (Phase Completion Protocol)

**Validation Configuration:**
- `.pre-commit-config.yaml` - Pre-commit hooks (Layer 1)
- `.git/hooks/pre-push` - Pre-push hooks (Layer 2)
- `.github/workflows/ci.yml` - CI/CD pipeline (Layer 3)
- `docs/utility/GITHUB_BRANCH_PROTECTION_CONFIG.md` - Branch protection (Layer 4)

**Security:**
- `docs/utility/SECURITY_REVIEW_CHECKLIST.md` - Pre-commit security checklist

---

**END OF DOCUMENT**
