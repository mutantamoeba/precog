# Precog Development Patterns Guide

---
**Version:** 1.4
**Created:** 2025-11-13
**Last Updated:** 2025-11-19
**Purpose:** Comprehensive reference for critical development patterns used throughout the Precog project
**Target Audience:** Developers and AI assistants working on any phase of the project
**Extracted From:** CLAUDE.md V1.15 (Section: Critical Patterns, Lines 930-2027)
**Status:** ✅ Current
**Changes in V1.4:**
- **Added Pattern 14: Schema Migration → CRUD Operations Update Workflow (CRITICAL)**
- Documents mandatory workflow when database schema changes require CRUD operation updates
- Covers dual-key pattern implementation (surrogate PRIMARY KEY + business key with partial unique index)
- Step-by-step workflow: Migration → CRUD update → Test update → Integration test verification
- Explains SCD Type 2 versioning pattern (UPDATE old + INSERT new with row_current_ind)
- Common patterns: Setting business_id from surrogate_id, WHERE row_current_ind filtering
- Testing requirements: Integration tests must use real database (NO mocks for CRUD/connection)
- Real-world examples from Migration 011 (positions dual-key schema) and Position Manager implementation
- Cross-references: ADR-089 (Dual-Key Schema Pattern), ADR-088 (Test Type Categories), Pattern 13 (Test Coverage Quality)
- Total addition: ~450 lines documenting critical schema-to-CRUD synchronization workflow
**Changes in V1.3:**
- **Added Pattern 12: Test Fixture Security Compliance (MANDATORY)**
- Documents project-relative test fixture pattern for security-validated functions
- Provides real-world example from PR #79 (test fixture fixes for path traversal protection)
- Includes Generator pattern with yield/finally, UUID for unique filenames, cleanup strategy
- Covers when to use project-relative vs tmp_path fixtures
- Impact: 9/25 tests failing → 25/25 passing, coverage 68.32% → 89.11% (+20.79pp)
- Cross-references: PR #79, PR #76 (CWE-22 path traversal protection), DEVELOPMENT_PHILOSOPHY Security-First Testing
**Changes in V1.2:**
- **Enhanced Pattern 5: Cross-Platform Compatibility**
- Added comprehensive Unicode symbol mapping table (14 symbols documented)
- Documented CLI symbols: ✓→[OK], ✗→[FAIL], ⚠→[WARN], •→-, →→->
- Added Rich console library behavior on Windows cp1252
- Included real-world example reference (commit 520c5dd - CLI Unicode fixes)
- Clarified file I/O Unicode handling: always use `encoding="utf-8"`
**Changes in V1.1:**
- **Added Pattern 11: Test Mocking Patterns (Mock API Boundaries, Not Implementation)**
- Documents mocking antipattern discovered in PR #19 and PR #20
- Provides real-world examples from ConfigLoader test fixes (11 tests fixed)
- Includes mocking hierarchy, best practices, and decision tree
- 230+ lines of comprehensive mocking guidance
- References: PR #19, PR #20, tests/unit/test_main.py (lines 1875-2290)
**Changes in V1.0:**
- Initial creation extracted from CLAUDE.md to reduce context load
- Contains all 10 critical patterns with complete examples and references
- Cross-references to related ADRs, REQs, and implementation guides

---

## 📋 Table of Contents

1. [Introduction](#introduction)
2. [Pattern 1: Decimal Precision (NEVER USE FLOAT)](#pattern-1-decimal-precision-never-use-float)
3. [Pattern 2: Dual Versioning System](#pattern-2-dual-versioning-system)
4. [Pattern 3: Trade Attribution](#pattern-3-trade-attribution)
5. [Pattern 4: Security (NO CREDENTIALS IN CODE)](#pattern-4-security-no-credentials-in-code)
6. [Pattern 5: Cross-Platform Compatibility (Windows/Linux)](#pattern-5-cross-platform-compatibility-windowslinux)
7. [Pattern 6: TypedDict for API Response Types (ALWAYS)](#pattern-6-typeddict-for-api-response-types-always)
8. [Pattern 7: Educational Docstrings (ALWAYS)](#pattern-7-educational-docstrings-always)
9. [Pattern 8: Configuration File Synchronization (CRITICAL)](#pattern-8-configuration-file-synchronization-critical)
10. [Pattern 9: Multi-Source Warning Governance (MANDATORY)](#pattern-9-multi-source-warning-governance-mandatory)
11. [Pattern 10: Property-Based Testing with Hypothesis (ALWAYS for Trading Logic)](#pattern-10-property-based-testing-with-hypothesis-always-for-trading-logic)
12. [Pattern 11: Test Mocking Patterns (Mock API Boundaries, Not Implementation)](#pattern-11-test-mocking-patterns-mock-api-boundaries-not-implementation)
13. [Pattern 12: Test Fixture Security Compliance (MANDATORY)](#pattern-12-test-fixture-security-compliance-mandatory)
14. [Pattern 13: Test Coverage Quality (Mock Sparingly, Integrate Thoroughly)](#pattern-13-test-coverage-quality-mock-sparingly-integrate-thoroughly---critical)
15. [Pattern 14: Schema Migration → CRUD Operations Update Workflow (CRITICAL)](#pattern-14-schema-migration--crud-operations-update-workflow-critical)
16. [Pattern Quick Reference](#pattern-quick-reference)
17. [Related Documentation](#related-documentation)

---

## Introduction

This guide contains **14 critical development patterns** that must be followed throughout the Precog project. These patterns address:

- **Financial Precision:** Decimal-only arithmetic for sub-penny pricing
- **Data Versioning:** Dual versioning system for mutable vs. immutable data
- **Security:** Zero-tolerance for hardcoded credentials
- **Cross-Platform:** Windows/Linux compatibility
- **Type Safety:** TypedDict for compile-time validation
- **Testing:** Property-based testing for trading logic + robust test mocking + integration test requirements
- **Configuration:** Multi-layer config synchronization
- **Quality:** Multi-source warning governance
- **Schema Management:** Database schema migration → CRUD operations synchronization workflow

**Why These Patterns Matter:**

Trading applications require **extreme precision, security, and reliability**. A single rounding error, credential leak, or configuration drift can cause:
- Financial losses (incorrect prices)
- Security breaches (leaked API keys)
- Deployment failures (config mismatches)
- Subtle bugs (cross-platform issues)

These patterns prevent such issues through **defense in depth**:
- Multiple layers of validation
- Automated checks (pre-commit, pre-push, CI/CD)
- Educational documentation
- Clear examples of correct AND incorrect usage

**How to Use This Guide:**

- **Before implementing features:** Review relevant patterns
- **During code review:** Verify patterns are followed
- **When debugging:** Check if pattern violations caused the bug
- **When onboarding:** Study all 10 patterns

**Pattern Categories:**

| Category | Patterns | Enforcement Level |
|----------|----------|-------------------|
| **Financial Safety** | Pattern 1 (Decimal Precision) | MANDATORY - Automated checks |
| **Data Management** | Pattern 2 (Versioning), Pattern 3 (Attribution) | MANDATORY - Code review |
| **Security** | Pattern 4 (No Credentials) | MANDATORY - Pre-commit hooks |
| **Quality** | Pattern 5-10 | MANDATORY - Pre-push hooks + CI/CD |

---

## Pattern 1: Decimal Precision (NEVER USE FLOAT)

**WHY:** Kalshi uses sub-penny pricing (e.g., $0.4975). Float causes rounding errors.

**ALWAYS:**
```python
from decimal import Decimal

# ✅ CORRECT
price = Decimal("0.4975")
spread = Decimal("0.0050")
total = price + spread  # Decimal("0.5025")

# ✅ Parse from API
yes_bid = Decimal(market_data["yes_bid_dollars"])

# ✅ Database
yes_bid = Column(DECIMAL(10, 4), nullable=False)
```

**NEVER:**
```python
# ❌ WRONG - Float contamination
price = 0.4975  # float
price = float(market_data["yes_bid_dollars"])

# ❌ WRONG - Integer cents (deprecated by Kalshi)
yes_bid = market_data["yes_bid"]

# ❌ WRONG - PostgreSQL FLOAT
yes_bid = Column(Float, nullable=False)
```

**Reference:** `docs/api-integration/KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md`

**⚠️ MAINTENANCE REMINDER:**
When adding new database tables with price/probability columns:
1. Add table name and column list to `price_columns` dict in `scripts/validate_schema_consistency.py`
2. Run validation: `python scripts/validate_schema_consistency.py`
3. See script's MAINTENANCE GUIDE for detailed instructions
4. **Time estimate:** ~5 minutes per table

---

## Pattern 2: Dual Versioning System

**Two Different Patterns for Different Needs:**

### Pattern A: SCD Type 2 (Frequently-Changing Data)

**Use for:** markets, positions, game_states, edges, account_balance

**How it works:**
- `row_current_ind BOOLEAN` - TRUE = current, FALSE = historical
- When updating: INSERT new row (row_current_ind=TRUE), UPDATE old row (set FALSE)
- **ALWAYS query with:** `WHERE row_current_ind = TRUE`

```python
# ✅ CORRECT
current_positions = session.query(Position).filter(
    Position.row_current_ind == True
).all()

# ❌ WRONG - Gets historical versions too
all_positions = session.query(Position).all()
```

### Pattern B: Immutable Versions (Strategies & Models)

**Use for:** strategies, probability_models

**How it works:**
- `version` field (e.g., "v1.0", "v1.1", "v2.0")
- `config` JSONB is **IMMUTABLE** - NEVER changes
- `status` field is **MUTABLE** - Can change (draft → testing → active → deprecated)
- To change config: Create NEW version (v1.0 → v1.1)

```python
# ✅ CORRECT - Create new version
v1_1 = Strategy(
    strategy_name="halftime_entry",
    strategy_version="v1.1",
    config={"min_lead": 10},  # Different from v1.0
    status="draft"
)

# ❌ WRONG - Modifying immutable config
v1_0.config = {"min_lead": 10}  # VIOLATES IMMUTABILITY

# ✅ CORRECT - Update mutable status
v1_0.status = "deprecated"  # OK
```

**Why Immutable Configs:**
- A/B testing integrity (configs never change)
- Trade attribution (know EXACTLY which config generated each trade)
- Semantic versioning (v1.0 → v1.1 = bug fix, v1.0 → v2.0 = major change)

**Reference:** `docs/guides/VERSIONING_GUIDE_V1.0.md`

**⚠️ MAINTENANCE REMINDER:**
When adding new SCD Type 2 tables (versioned tables):
1. Add table name to `versioned_tables` list in `scripts/validate_schema_consistency.py`
2. Ensure table has ALL 4 required columns:
   - `row_current_ind BOOLEAN NOT NULL DEFAULT TRUE`
   - `row_start_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP`
   - `row_end_ts TIMESTAMP` (nullable)
   - `row_version INTEGER NOT NULL DEFAULT 1`
3. Run validation: `python scripts/validate_schema_consistency.py`
4. See script's MAINTENANCE GUIDE for detailed instructions
5. **Time estimate:** ~2 minutes per table

---

## Pattern 3: Trade Attribution

**EVERY trade must link to exact versions:**

```python
# ✅ CORRECT - Full attribution
trade = Trade(
    market_id=market.id,
    strategy_id=strategy.strategy_id,  # Link to exact version
    model_id=model.model_id,           # Link to exact version
    quantity=100,
    price=Decimal("0.7500"),
    side="YES"
)

# ❌ WRONG - No attribution
trade = Trade(
    market_id=market.id,
    # Missing strategy_id and model_id!
    quantity=100,
    price=Decimal("0.7500")
)
```

**Query trade with full version details:**
```python
trade_with_versions = (
    session.query(Trade, Strategy, ProbabilityModel)
    .join(Strategy, Trade.strategy_id == Strategy.strategy_id)
    .join(ProbabilityModel, Trade.model_id == ProbabilityModel.model_id)
    .filter(Trade.trade_id == trade_id)
    .first()
)

print(f"Strategy: {strategy.strategy_name} v{strategy.strategy_version}")
print(f"Model: {model.model_name} v{model.model_version}")
```

---

## Pattern 4: Security (NO CREDENTIALS IN CODE)

**ALWAYS use environment variables:**

```python
# ✅ CORRECT
import os
from dotenv import load_dotenv

load_dotenv()

db_password = os.getenv('DB_PASSWORD')
api_key = os.environ['KALSHI_API_KEY']  # Raises KeyError if missing

# Validate credentials exist
if not db_password:
    raise ValueError("DB_PASSWORD environment variable not set")
```

**NEVER:**
```python
# ❌ NEVER hardcode
password = "mypassword"
api_key = "sk_live_abc123"
db_url = "postgres://user:password@host/db"
```

**Pre-Commit Security Scan:**
```bash
# Run BEFORE EVERY COMMIT
git grep -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]" -- '*.py'

# Expected: No results (or only os.getenv lines)
```

**Reference:** `docs/utility/SECURITY_REVIEW_CHECKLIST.md`

---

## Pattern 5: Cross-Platform Compatibility (Windows/Linux)

**WHY:** Development occurs on both Windows (local) and Linux (CI/CD). Python scripts that work on Linux fail on Windows with `UnicodeEncodeError` when printing emoji to console.

**The Problem:** Windows console uses cp1252 encoding (limited character set), Linux/Mac use UTF-8 (full Unicode support).

**ALWAYS:**
```python
# ✅ CORRECT - ASCII equivalents for console output
print("[OK] All tests passed")
print("[FAIL] 3 errors found")
print("[WARN] Consider updating")
print("[IN PROGRESS] Phase 1 - 50% complete")

# ✅ CORRECT - Explicit UTF-8 for file I/O
with open("file.md", "r", encoding="utf-8") as f:
    content = f.read()

with open("output.json", "w", encoding="utf-8") as f:
    json.dump(data, f)

# ✅ CORRECT - Sanitize Unicode when reading from markdown
def sanitize_unicode(text: str) -> str:
    """Replace Unicode symbols with ASCII equivalents for Windows console.

    Comprehensive mapping table for all Unicode symbols used in project.
    """
    replacements = {
        # Status emoji (used in documentation)
        "✅": "[COMPLETE]",
        "🔵": "[PLANNED]",
        "🟡": "[IN PROGRESS]",
        "❌": "[FAILED]",
        "⚠️": "[WARNING]",

        # CLI output symbols (used in main.py)
        "✓": "[OK]",        # U+2713 - Check mark
        "✗": "[FAIL]",      # U+2717 - Ballot X
        "⚠": "[WARN]",      # U+26A0 - Warning sign (no variation selector)
        "•": "-",           # U+2022 - Bullet point
        "→": "->",          # U+2192 - Right arrow

        # Progress indicators
        "▶": "[>]",         # U+25B6 - Play symbol
        "⏸": "[||]",        # U+23F8 - Pause symbol
        "⏹": "[#]",         # U+23F9 - Stop symbol
    }
    for unicode_char, ascii_replacement in replacements.items():
        text = text.replace(unicode_char, ascii_replacement)
    return text

# Usage
print(sanitize_unicode(error_message))  # Safe for Windows console
```

**NEVER:**
```python
# ❌ WRONG - Emoji in console output
print("✅ All tests passed")  # Crashes on Windows cp1252
print("❌ 3 errors found")

# ❌ WRONG - Platform default encoding
with open("file.md", "r") as f:  # cp1252 on Windows, UTF-8 on Linux
    content = f.read()
```

**Where Unicode is OK:**
- **Markdown files (.md)**: ✅ Yes (GitHub/VS Code render correctly)
- **Script `print()` output**: ❌ No (use ASCII equivalents)
- **Error messages**: ❌ No (may be printed to console - sanitize first)
- **File contents (YAML, JSON, Python source)**: ✅ Yes (but always use `encoding="utf-8"` when reading)

**Rich Console Library (main.py CLI):**
The Rich library used in main.py attempts to handle Unicode, but still fails on Windows cp1252 terminals:
```python
# ❌ WRONG - Rich still crashes with Unicode on Windows cp1252
console.print("[green]✓ Success[/green]")  # UnicodeEncodeError

# ✅ CORRECT - Use ASCII equivalents even with Rich
console.print("[green][OK] Success[/green]")  # Works on all platforms
```

**Real-World Example:**
Fixed in commit 520c5dd (2025-11-14): All CLI commands (db-init, health-check, config-show, config-validate) had Unicode symbols replaced with ASCII equivalents to support Windows cp1252.

**Reference:**
- `docs/foundation/ARCHITECTURE_DECISIONS_V2.10.md` (ADR-053)
- `scripts/validate_docs.py` (lines 57-82 for sanitization example)
- `main.py` (lines 1196-1753 for CLI ASCII output examples)

---

## Pattern 6: TypedDict for API Response Types (ALWAYS)

**WHY:** Type safety prevents field name typos and wrong types at compile-time. TypedDict provides IDE autocomplete and mypy validation with zero runtime overhead.

**TypedDict vs Pydantic:**
- **TypedDict:** Compile-time type hints, no runtime validation, zero overhead
- **Pydantic:** Runtime validation, automatic parsing, detailed errors, slower

**Use TypedDict for Phase 1-4** (internal code, trusted APIs)
**Use Pydantic for Phase 5+** (external inputs, trading execution)

**ALWAYS:**
```python
from typing import TypedDict, List, cast
from decimal import Decimal

# ✅ CORRECT - Define response structure
class MarketResponse(TypedDict):
    ticker: str
    yes_bid: Decimal  # After conversion
    yes_ask: Decimal
    volume: int
    status: Literal["open", "closed", "settled"]  # Use Literal for enums

# ✅ CORRECT - Use in function signature
def get_markets(self) -> List[MarketResponse]:
    """Fetch markets with type safety."""
    response = self._make_request("GET", "/markets")
    markets = response.get("markets", [])

    # Convert prices to Decimal
    for market in markets:
        self._convert_prices_to_decimal(market)

    return cast(List[MarketResponse], markets)

# ✅ CORRECT - IDE knows which fields exist
market = get_markets()[0]
print(market['ticker'])  # ✅ Autocomplete works
print(market['volume'])  # ✅ Type checker knows it's int

# ✅ CORRECT - Mypy catches errors
print(market['price'])  # ❌ Error: 'price' not in MarketResponse
```

**NEVER:**
```python
# ❌ WRONG - Untyped dictionary
def get_markets(self) -> List[Dict]:
    return self._make_request("GET", "/markets")

market = get_markets()[0]
print(market['tickr'])  # ❌ Typo! No autocomplete, no error until runtime
```

**Key Patterns:**

1. **Separate "Raw" and "Processed" Types:**
```python
# Raw API response (prices as strings)
class MarketDataRaw(TypedDict):
    ticker: str
    yes_bid: str  # "0.6250"
    yes_ask: str  # "0.6300"

# After Decimal conversion
class ProcessedMarketData(TypedDict):
    ticker: str
    yes_bid: Decimal  # Decimal("0.6250")
    yes_ask: Decimal  # Decimal("0.6300")
```

2. **Use Literal types for enums:**
```python
from typing import Literal

class Position(TypedDict):
    ticker: str
    side: Literal["yes", "no"]  # Only these values allowed
    action: Literal["buy", "sell"]
```

3. **Use cast() to assert runtime matches compile-time:**
```python
# After processing, assert dict matches TypedDict structure
return cast(List[ProcessedMarketData], markets)
```

**Reference:** `api_connectors/types.py` for 17 TypedDict examples
**Related:** ADR-048 (Decimal-First Response Parsing), REQ-API-007 (Pydantic migration planned for Phase 1.5)

---

## Pattern 7: Educational Docstrings (ALWAYS)

**WHY:** Complex concepts (RSA-PSS auth, Decimal precision, SCD Type 2) require educational context. Verbose docstrings with examples prevent mistakes and accelerate onboarding.

**ALWAYS Include:**
1. **Clear description** of what the function does
2. **Args/Returns documentation** with types
3. **Educational Note** explaining WHY this pattern matters
4. **Examples** showing correct AND incorrect usage
5. **Related references** (ADRs, REQs, docs)

**ALWAYS:**
```python
def create_account_balance_record(session, balance: Decimal, platform_id: str) -> int:
    """
    Create account balance snapshot in database.

    Args:
        session: SQLAlchemy session (active transaction)
        balance: Account balance as Decimal (NEVER float!)
        platform_id: Platform identifier ("kalshi", "polymarket")

    Returns:
        int: Record ID (balance_id from database)

    Raises:
        ValueError: If balance is float (not Decimal)
        TypeError: If session is not SQLAlchemy session

    Educational Note:
        Balance stored as DECIMAL(10,4) in PostgreSQL for exact precision.
        NEVER use float - causes rounding errors with sub-penny prices.

        Why this matters:
        - Kalshi uses sub-penny pricing (e.g., $0.4975)
        - Float arithmetic: 0.4975 + 0.0050 = 0.502499999... (WRONG!)
        - Decimal arithmetic: 0.4975 + 0.0050 = 0.5025 (CORRECT!)

    Example:
        >>> from decimal import Decimal
        >>> balance = Decimal("1234.5678")  # ✅ Correct
        >>> record_id = create_account_balance_record(
        ...     session=session,
        ...     balance=balance,
        ...     platform_id="kalshi"
        ... )
        >>> print(record_id)  # 42

        >>> # ❌ WRONG - Float contamination
        >>> balance = 1234.5678  # float type
        >>> # Will raise ValueError

    Related:
        - REQ-SYS-003: Decimal Precision for All Prices
        - ADR-002: Decimal-Only Financial Calculations
        - Pattern 1 in DEVELOPMENT_PATTERNS_V1.0.md: Decimal Precision
    """
    if not isinstance(balance, Decimal):
        raise ValueError(f"Balance must be Decimal, got {type(balance)}")

    # Implementation...
    return record_id
```

**NEVER:**
```python
# ❌ Minimal docstring (insufficient for complex project)
def create_account_balance_record(session, balance, platform_id):
    """Create balance record."""
    # Missing: Why Decimal? What's platform_id? Examples? Related docs?
    return session.query(...).insert(...)
```

**Apply to ALL modules:**
- ✅ API connectors: Already have excellent educational docstrings
- ⚠️ Database CRUD: Needs enhancement (Phase 1.5 improvement)
- ⚠️ Config loader: Needs enhancement (Phase 1.5 improvement)
- ⚠️ CLI commands: Adequate (main.py has good command docstrings)
- ✅ Utils (logger): Good docstrings

**When to use Educational Notes:**
- **Complex algorithms**: Token bucket, exponential backoff, SCD Type 2
- **Security-critical code**: Authentication, credential handling, SQL injection prevention
- **Precision-critical code**: Decimal arithmetic, price calculations, financial math
- **Common mistakes**: Float vs Decimal, mutable defaults, SQL injection
- **Non-obvious behavior**: RSA-PSS signature format, timezone handling, rate limiting

**Reference:** `api_connectors/kalshi_auth.py` (lines 41-90, 92-162) for excellent examples

---

## Pattern 8: Configuration File Synchronization (CRITICAL)

**WHY:** Configuration files exist at **4 different layers** in the validation pipeline. When migrating tools or changing requirements, ALL layers must be updated to prevent configuration drift.

**The Problem We Just Fixed:**
- Migrated Bandit → Ruff in 3 layers (.pre-commit-config.yaml, .git/hooks/pre-push, .github/workflows/ci.yml)
- **MISSED** pyproject.toml `[tool.bandit]` section
- Result: pytest auto-detected Bandit config → 200+ Bandit errors → all pushes blocked

**Four Configuration Layers:**

```
Layer 1: Tool Configuration Files
├── pyproject.toml           [tool.ruff], [tool.mypy], [tool.pytest], [tool.coverage]
├── .pre-commit-config.yaml  Pre-commit hook definitions (12 checks)
└── pytest.ini               Test framework settings (if separate)

Layer 2: Pipeline Configuration Files
├── .git/hooks/pre-push      Pre-push validation script (Bash)
├── .git/hooks/pre-commit    Pre-commit validation script (managed by pre-commit framework)
└── .github/workflows/ci.yml GitHub Actions CI/CD pipeline (YAML)

Layer 3: Application Configuration Files
├── config/database.yaml          Database connection, pool settings
├── config/markets.yaml           Market selection, edge thresholds, Kelly fractions
├── config/probability_models.yaml Model weights, ensemble config
├── config/trade_strategies.yaml   Strategy versions, entry/exit rules
├── config/position_management.yaml Trailing stops, profit targets, correlation limits
├── config/trading.yaml            Circuit breakers, position sizing, risk limits
└── config/logging.yaml            Log levels, rotation, output formats

Layer 4: Documentation Files
├── docs/foundation/MASTER_REQUIREMENTS*.md    Requirement definitions
├── docs/foundation/ARCHITECTURE_DECISIONS*.md  ADR definitions
├── docs/guides/*.md                            Implementation guides
└── CLAUDE.md                                   Development patterns
```

**ALWAYS Update ALL Layers When:**

**Scenario 1: Migrating Tools** (e.g., Bandit → Ruff)
- [ ] Update `pyproject.toml` - Remove `[tool.bandit]`, update `[tool.ruff]`
- [ ] Update `.pre-commit-config.yaml` - Change hook from `bandit` to `ruff --select S`
- [ ] Update `.git/hooks/pre-push` - Change security scan command + comments
- [ ] Update `.github/workflows/ci.yml` - Change CI job from `bandit` to `ruff`
- [ ] Update `CLAUDE.md` - Update pre-commit/pre-push documentation
- [ ] Update `SESSION_HANDOFF.md` - Document the migration

**Scenario 2: Changing Application Requirements** (e.g., min_edge threshold)

Example: REQ-TRADE-005 changes minimum edge from 0.05 to 0.08

- [ ] Update `docs/foundation/MASTER_REQUIREMENTS*.md` - Change requirement
- [ ] Update `config/markets.yaml` - Update all `min_edge` values in each league/category
- [ ] Update `config/trade_strategies.yaml` - Update strategy-specific edge thresholds
- [ ] Update `config/trading.yaml` - Update `position_sizing.kelly.min_edge_threshold`
- [ ] Update `docs/guides/CONFIGURATION_GUIDE*.md` - Update examples
- [ ] Run validation: `python scripts/validate_docs.py` (checks YAML files!)
- [ ] Commit ALL files together atomically

**Scenario 3: Adding New Validation Checks**

Example: Adding new Ruff rule (like S608 for SQL injection)

- [ ] Update `pyproject.toml` - Add rule to `[tool.ruff.lint].select`
- [ ] Update `.pre-commit-config.yaml` - Add `--select S608` to args (if needed)
- [ ] Update `.git/hooks/pre-push` - Document new check in comments
- [ ] Update `.github/workflows/ci.yml` - Ensure CI runs new check
- [ ] Update `CLAUDE.md` - Document new check in validation section

**Validation Commands:**

```bash
# Layer 1: Check pyproject.toml syntax
python -c "import tomli; tomli.load(open('pyproject.toml', 'rb'))"

# Layer 2: Test pre-push hooks locally
bash .git/hooks/pre-push

# Layer 3: Validate YAML configs (DECIMAL SAFETY CHECK)
python scripts/validate_docs.py
# Checks for float contamination in config/*.yaml files

# Layer 4: Validate documentation consistency
python scripts/validate_docs.py
```

**YAML Configuration Validation (Already Implemented!):**

The `validate_docs.py` script (Check #9) automatically checks:
- ✅ All 7 config/*.yaml files for YAML syntax errors
- ✅ **Decimal safety** - Detects float values in price/probability fields
- ✅ **Schema consistency** - Ensures required fields present

**Decimal Safety in YAML Files:**

```yaml
# ❌ WRONG - Float contamination (causes rounding errors)
platforms:
  kalshi:
    fees:
      taker_fee_percent: 0.07      # Float!
    categories:
      sports:
        leagues:
          nfl:
            min_edge: 0.05           # Float!
            kelly_fraction: 0.25     # Float!

# ✅ CORRECT - String format (converted to Decimal by config_loader.py)
platforms:
  kalshi:
    fees:
      taker_fee_percent: "0.07"    # String → Decimal
    categories:
      sports:
        leagues:
          nfl:
            min_edge: "0.05"         # String → Decimal
            kelly_fraction: "0.25"   # String → Decimal
```

**Why String Format in YAML?**
- YAML parser treats `0.05` as float (64-bit binary)
- Float: `0.05` → `0.050000000000000003` (rounding error!)
- String: `"0.05"` → `Decimal("0.05")` → `0.0500` (exact!)
- ConfigLoader converts strings to Decimal automatically (see `config_loader.py:decimal_conversion=True`)

**Configuration Migration Checklist (Template):**

```markdown
## Configuration Migration: [Tool/Requirement Name]

**Date:** YYYY-MM-DD
**Reason:** [Why migrating? Performance, Python 3.14 compat, new feature?]

**Layer 1: Tool Configuration**
- [ ] `pyproject.toml` - [Specific changes]
- [ ] `.pre-commit-config.yaml` - [Specific changes]
- [ ] Validated syntax: `python -c "import tomli; tomli.load(open('pyproject.toml', 'rb'))"`

**Layer 2: Pipeline Configuration**
- [ ] `.git/hooks/pre-push` - [Specific changes]
- [ ] `.github/workflows/ci.yml` - [Specific changes]
- [ ] Tested pre-push hooks: `bash .git/hooks/pre-push`

**Layer 3: Application Configuration** (if applicable)
- [ ] `config/[specific].yaml` - [Specific changes]
- [ ] Validated YAML: `python scripts/validate_docs.py`
- [ ] Checked Decimal safety: No float contamination warnings

**Layer 4: Documentation**
- [ ] `CLAUDE.md` - [Specific changes]
- [ ] `SESSION_HANDOFF.md` - [Specific changes]
- [ ] Relevant guides updated

**Validation:**
- [ ] All tests passing: `python -m pytest tests/ -v`
- [ ] Pre-push hooks passing: `bash .git/hooks/pre-push`
- [ ] YAML configs valid: `python scripts/validate_docs.py`
- [ ] No configuration drift detected

**Commit:**
```bash
git add pyproject.toml .pre-commit-config.yaml .git/hooks/pre-push .github/workflows/ci.yml CLAUDE.md
git commit -m "[Tool/Req]: [Migration description]

Layer 1: Tool configuration updates
Layer 2: Pipeline configuration updates
Layer 3: Application configuration updates (if applicable)
Layer 4: Documentation updates

All 4 layers synchronized to prevent configuration drift.
"
```
```

**Common Configuration Drift Scenarios:**

| Scenario | Layers Affected | Checklist |
|----------|----------------|-----------|
| **Tool migration** (Bandit→Ruff) | 1, 2, 4 | Update pyproject.toml, hooks, CI, docs |
| **Requirement change** (min_edge) | 3, 4 | Update config/*.yaml, MASTER_REQUIREMENTS, guides |
| **New validation rule** | 1, 2, 4 | Update pyproject.toml, hooks, CI, docs |
| **Python version upgrade** | 1, 2 | Update pyproject.toml, CI matrix |
| **Decimal precision fix** | 3 | Update all config/*.yaml floats → strings |
| **Security rule change** | 1, 2, 4 | Update ruff S-rules, hooks, docs |

**Prevention Strategy:**

1. **Atomic commits** - Commit all layers together in ONE commit
2. **Validation scripts** - Run `validate_docs.py` before every commit (catches YAML drift)
3. **Pre-push hooks** - Catch configuration errors locally (30-60s vs 2-5min CI)
4. **Documentation** - Always update CLAUDE.md when changing validation pipeline
5. **Session handoff** - Document configuration changes in SESSION_HANDOFF.md
6. **Checklists** - Use migration checklist template above

**Reference:**
- Pattern 1: Decimal Precision (why string format matters)
- Pattern 4: Security (no hardcoded credentials in any config layer)
- `scripts/validate_docs.py` - YAML validation implementation (Check #9)
- `config/config_loader.py` - String → Decimal conversion logic

---

## Pattern 9: Multi-Source Warning Governance (MANDATORY)

**WHY:** Warnings from **multiple validation systems** (pytest, validate_docs, Ruff, Mypy) were being tracked inconsistently. Without comprehensive governance, warnings accumulate silently until they block development.

**The Problem We Fixed:**
- Initial governance only tracked pytest warnings (41)
- Missed 388 warnings from validate_docs.py (YAML floats, MASTER_INDEX issues, ADR gaps)
- Validate_docs.py treated YAML floats as "warnings" not "errors" → wouldn't fail builds!
- Total: 429 warnings across 3 validation systems (BASELINE: 2025-11-08)

**Current Status (2025-11-09):**
- **YAML warnings ELIMINATED:** 111 → 0 (100% fixed in Phase 1.5)
- **pytest warnings reduced:** 41 → 32 (-9 warnings)
- **ADR warnings RECLASSIFIED:** Changed from "informational" to "actionable" per user feedback
- **New baseline:** 312 warnings (down from 429, -27% improvement)
- **check_warning_debt.py INTEGRATED:** Now runs in pre-push hooks (Step 5/5)

**Three Warning Sources:**

```
Source 1: pytest Test Warnings (32 total, was 41)
├── Hypothesis decimal precision (17, was 19)
├── ResourceWarning unclosed files (11, was 13)
├── pytest-asyncio deprecation (4)
└── structlog UserWarning (1)

Source 2: validate_docs.py Warnings (280 total, was 388)
├── ADR non-sequential numbering (231) - NOW ACTIONABLE ⚠️
├── YAML float literals (0, was 111) - ✅ FIXED!
├── MASTER_INDEX missing docs (29, was 27)
├── MASTER_INDEX deleted docs (12, was 11)
└── MASTER_INDEX planned docs (8) - Expected

Source 3: Code Quality (0 total)
├── Ruff linting errors (0)
└── Mypy type errors (0)
```

**Warning Classification (UPDATED 2025-11-09):**
- **Actionable (313, was 182):** ALL warnings now actionable (ADR gaps reclassified)
- **Informational (0, was 231):** Zero informational warnings (ADR gaps → actionable)
- **Expected (8, was 16):** Only truly expected warnings (planned docs)
- **Upstream (4):** Dependency issues (pytest-asyncio Python 3.16 compat)

**ALWAYS Track Warnings Across ALL Sources:**

```bash
# Multi-source validation (automated in check_warning_debt.py)
python scripts/check_warning_debt.py

# Manual verification (4 sources)
python -m pytest tests/ -v -W default --tb=no  # pytest warnings
python scripts/validate_docs.py                # Documentation warnings
python -m ruff check .                         # Linting errors
python -m mypy .                               # Type errors
```

**Governance Infrastructure:**

**1. warning_baseline.json (312 warnings locked, was 429)**
```json
{
  "baseline_date": "2025-11-09",
  "total_warnings": 312,
  "warning_categories": {
    "yaml_float_literals": {"count": 0, "target_phase": "DONE"},
    "hypothesis_decimal_precision": {"count": 17, "target_phase": "1.5"},
    "resource_warning_unclosed_files": {"count": 11, "target_phase": "1.5"},
    "master_index_missing_docs": {"count": 29, "target_phase": "1.5"},
    "master_index_deleted_docs": {"count": 12, "target_phase": "1.5"},
    "adr_non_sequential_numbering": {"count": 231, "actionable": true, "target_phase": "2.0"}
  },
  "governance_policy": {
    "max_warnings_allowed": 312,
    "new_warning_policy": "fail",
    "regression_tolerance": 0,
    "notes": "UPDATED 2025-11-09: -117 warnings (-27%), YAML floats eliminated, ADR gaps reclassified"
  }
}
```

**2. WARNING_DEBT_TRACKER.md (comprehensive tracking)**
- Documents all 312 warnings across 3 sources (was 429)
- Categorizes by actionability (313 actionable, 0 informational, 8 expected)
- Tracks deferred fixes (WARN-001 through WARN-007)
- Documents fix priorities, estimates, target phases
- Provides measurement commands for all sources
- **UPDATED 2025-11-09:** Reflects YAML elimination and ADR reclassification

**3. check_warning_debt.py (automated validation) - NOW INTEGRATED**
- Runs all 4 validation sources (pytest, validate_docs, Ruff, Mypy)
- Compares against baseline (312 warnings, was 429)
- **NOW RUNS IN PRE-PUSH HOOKS (Step 5/5)** - blocks pushes with regression
- Fails CI if new warnings detected
- Provides comprehensive breakdown by source

**Enforcement Rules (UPDATED 2025-11-09):**

1. **Baseline Locked:** 312 warnings (313 actionable, was 429/182)
2. **Zero Regression:** New warnings → pre-push hooks FAIL → **OPTIONS:**
   - **Option A: Fix immediately** (recommended)
   - **Option B: Defer with tracking** (create WARN-XXX in WARNING_DEBT_TRACKER.md)
   - **Option C: Update baseline** (requires approval + documentation)
3. **Baseline Warnings:** All 312 existing warnings MUST be tracked as deferred tasks
   - Each category needs WARN-XXX entry (already exists: WARN-001 through WARN-007)
   - Each entry documents: priority, estimate, target phase, fix plan
   - **NOT acceptable:** "Locked baseline, forget about it"
4. **Phase Targets:** Reduce by 80-100 warnings per phase (Phase 1.5: -117 achieved!)
5. **Zero Goal:** Target <100 actionable warnings by Phase 2 completion

**Integration Points (UPDATED 2025-11-09):**

```bash
# Pre-push hooks (runs automatically on git push) - NOW INTEGRATED!
bash .git/hooks/pre-push
# → Step 5/5: python scripts/check_warning_debt.py (multi-source check)
# → Enforces 312-warning baseline locally BEFORE CI

# CI/CD (.github/workflows/ci.yml)
# → Job: warning-governance
#   Runs: python scripts/check_warning_debt.py
#   Blocks merge if warnings exceed baseline (312)
```

**Example Workflow:**

```bash
# 1. Developer adds code that introduces new warning
git add feature.py
git commit -m "Add feature X"

# 2. Pre-push hooks run (automatic) - check_warning_debt.py runs at Step 5/5
git push
# → check_warning_debt.py detects 313 warnings (baseline: 312)
# → [FAIL] Warning count: 313/312 (+1 new warning)
# → Push blocked locally (BEFORE hitting CI!)

# 3. Developer has THREE OPTIONS:

# OPTION A: Fix immediately (recommended)
# Fix the warning in code, then re-push
git push
# → [OK] Warning count: 312/312 (baseline maintained)

# OPTION B: Defer with tracking (acceptable if documented)
# 1. Add entry to docs/utility/WARNING_DEBT_TRACKER.md:
#    WARN-008: New Hypothesis warning from edge case test (1 warning)
#    - Priority: Medium, Estimate: 1 hour, Target Phase: 1.6
# 2. Update baseline: python scripts/check_warning_debt.py --update
# 3. Commit WARNING_DEBT_TRACKER.md + warning_baseline.json
# 4. Push (now passes with 313 baseline)

# OPTION C: Update baseline without tracking (NOT RECOMMENDED)
# Only acceptable for:
# - Upstream dependency warnings (pytest-asyncio, etc.)
# - False positives from validation tools
# Otherwise, use Option B (defer with tracking)
```

**Acceptable Baseline Updates:**

You MAY update the baseline IF:
1. **New validation source** added (e.g., adding Bandit security scanner)
2. **Upstream dependency** introduces warnings (e.g., pytest-asyncio Python 3.16 compat)
3. **Intentional refactor** creates temporary warnings (document + target phase to fix)

You MUST document in WARNING_DEBT_TRACKER.md:
```markdown
### Baseline Update: 2025-11-09 - YAML Elimination + ADR Reclassification

**Previous Baseline:** 429 warnings
**New Baseline:** 312 warnings (-117, -27% improvement)

**Changes:**
- ELIMINATED: YAML float warnings (111 → 0) - Fixed in Phase 1.5
- REDUCED: pytest warnings (41 → 32) - Property test improvements
- RECLASSIFIED: ADR non-sequential warnings (231) from informational → actionable
- INTEGRATED: check_warning_debt.py into pre-push hooks (Step 5/5)

**Approval:** Approved by [Name] on [Date]
**Next Action:** Fix WARN-008 in Phase 1.5 (target: -6 warnings)
```

**Common Mistakes:**

```python
# ❌ WRONG - Only checking pytest warnings
def check_warnings():
    pytest_output = run_pytest()
    count = extract_warning_count(pytest_output)
    # Misses validate_docs warnings!

# ✅ CORRECT - Multi-source validation
def check_warnings():
    pytest_count = run_pytest_warnings()
    docs_count = run_validate_docs()
    ruff_count = run_ruff()
    mypy_count = run_mypy()
    total = pytest_count + sum(docs_count.values()) + ruff_count + mypy_count
    return total  # Comprehensive
```

**Files Modified:**
- `scripts/warning_baseline.json` - Baseline (152 → 429 warnings)
- `scripts/check_warning_debt.py` - Multi-source validation
- `docs/utility/WARNING_DEBT_TRACKER.md` - Comprehensive tracking
- `CLAUDE.md` - This pattern
- `docs/foundation/ARCHITECTURE_DECISIONS*.md` - ADR-054 (Warning Governance Architecture)

**Reference:**
- WARNING_DEBT_TRACKER.md - Comprehensive warning documentation
- warning_baseline.json - Locked baseline configuration
- check_warning_debt.py - Automated validation script
- ADR-054: Warning Governance Architecture
- Pattern 5: Cross-Platform Compatibility (ASCII output for Windows)

---

## Pattern 10: Property-Based Testing with Hypothesis (ALWAYS for Trading Logic)

**WHY:** Trading logic has **mathematical invariants** that MUST hold for ALL inputs. Example-based tests validate 5-10 cases. Property-based tests validate thousands of cases automatically, catching edge cases humans miss.

**The Difference:**

```python
# ❌ EXAMPLE-BASED TEST - Tests 1 specific case
def test_kelly_criterion_example():
    position = calculate_kelly_size(
        edge=Decimal("0.10"),
        kelly_fraction=Decimal("0.25"),
        bankroll=Decimal("10000")
    )
    assert position == Decimal("250")  # What if edge = 0.9999999?

# ✅ PROPERTY-BASED TEST - Tests 100+ cases automatically
@given(
    edge=edge_value(),           # Generates edge ∈ [-0.5, 0.5]
    kelly_frac=kelly_fraction(), # Generates kelly ∈ [0, 1]
    bankroll=bankroll_amount()   # Generates bankroll ∈ [$100, $100k]
)
def test_position_never_exceeds_bankroll(edge, kelly_frac, bankroll):
    """PROPERTY: Position ≤ bankroll ALWAYS (prevents margin calls)"""
    position = calculate_kelly_size(edge, kelly_frac, bankroll)
    assert position <= bankroll  # Validates 100+ combinations
```

**ALWAYS Use Property Tests For:**

1. **Mathematical Invariants:**
   - Position size ≤ bankroll (prevents margin calls)
   - Bid price ≤ ask price (no crossed markets)
   - Trailing stop price NEVER loosens (one-way ratchet)
   - Probability ∈ [0, 1] (always bounded)
   - Kelly fraction ∈ [0, 1] (validated at config load)

2. **Business Rules:**
   - Negative edge → don't trade (prevents guaranteed losses)
   - Stop loss overrides all other exits (safety first)
   - Exit price within slippage tolerance (risk management)

3. **State Transitions:**
   - Position lifecycle: open → monitoring → exited (valid transitions only)
   - Strategy status: draft → testing → active → deprecated (no invalid jumps)
   - Trailing stop updates: current_stop = max(old_stop, new_stop) (never decreases)

4. **Data Validation:**
   - Timestamp ordering monotonic (no time travel)
   - Score progression never decreases (game logic)
   - Model outputs ∈ valid range (prediction bounds)

**Custom Hypothesis Strategies (Trading Domain):**

Create reusable generators in `tests/property/strategies.py`:

```python
from hypothesis import strategies as st
from decimal import Decimal

@st.composite
def probability(draw, min_value=0, max_value=1, places=4):
    """Generate valid probabilities [0, 1] as Decimal."""
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))

@st.composite
def bid_ask_spread(draw, min_spread=0.0001, max_spread=0.05):
    """Generate realistic bid-ask spreads with bid < ask constraint."""
    bid = draw(st.decimals(min_value=0, max_value=0.99, places=4))
    spread = draw(st.decimals(min_value=min_spread, max_value=max_spread, places=4))
    ask = bid + spread
    return (bid, ask)

@st.composite
def price_series(draw, length=10, volatility=Decimal("0.05")):
    """Generate realistic price movement series."""
    start_price = draw(st.decimals(min_value=0.40, max_value=0.60, places=4))
    prices = [start_price]
    for _ in range(length - 1):
        change = draw(st.decimals(min_value=-volatility, max_value=volatility, places=4))
        new_price = max(Decimal("0.01"), min(Decimal("0.99"), prices[-1] + change))
        prices.append(new_price)
    return prices
```

**Why Custom Strategies Matter:**
- Generate **domain-valid** inputs only (no wasted test cases on negative prices)
- Encode constraints once, reuse everywhere (bid < ask, probability ∈ [0, 1])
- Improve Hypothesis shrinking (finds minimal failing examples faster)
- Document domain assumptions (probabilities are Decimal, not float)

**Hypothesis Shrinking - Automatic Bug Minimization:**

When a property test fails, Hypothesis **automatically** finds the simplest failing example:

```python
# Failing test:
@given(edge=edge_value(), kelly_frac=kelly_fraction(), bankroll=bankroll_amount())
def test_position_never_exceeds_bankroll(edge, kelly_frac, bankroll):
    position = calculate_kelly_size(edge, kelly_frac, bankroll)
    assert position <= bankroll

# Initial failure (complex):
# edge=0.473821, kelly_frac=0.87, bankroll=54329.12
# position=54330.00 > bankroll (BUG!)

# After shrinking (<1 second):
# edge=0.5, kelly_frac=1.0, bankroll=100.0
# position=101.0 > bankroll (minimal example reveals bug)

# Root cause: Forgot to cap position at bankroll!
# Fix: position = min(calculated_position, bankroll)
```

**When to Use Property Tests vs. Example Tests:**

| Test Type | Use For | Example |
|-----------|---------|---------|
| **Property Test** | Mathematical invariants | Position ≤ bankroll |
| **Property Test** | Business rules | Negative edge → don't trade |
| **Property Test** | State transitions | Trailing stop only tightens |
| **Property Test** | Data validation | Probability ∈ [0, 1] |
| **Example Test** | Specific known bugs | Regression test for Issue #42 |
| **Example Test** | Integration with APIs | Mock Kalshi API response |
| **Example Test** | Complex business scenarios | Halftime entry strategy |
| **Example Test** | User-facing behavior | CLI output format |
| **Example Test** | Performance benchmarks | Test runs in <100ms |

**Best Practice:** Use **both**. Property tests validate invariants, example tests validate specific scenarios.

**Configuration (`pyproject.toml`):**

```toml
[tool.hypothesis]
max_examples = 100          # Test 100 random inputs per property
verbosity = "normal"         # Show shrinking progress
database = ".hypothesis/examples"  # Cache discovered edge cases
deadline = 400              # 400ms timeout per example (prevents infinite loops)
derandomize = false         # True for debugging (reproducible failures)
```

**Project Status:**

**✅ Phase 1.5 Proof-of-Concept (COMPLETE):**
- `tests/property/test_kelly_criterion_properties.py` - 11 properties, 1100+ cases
- `tests/property/test_edge_detection_properties.py` - 16 properties, 1600+ cases
- Custom strategies: `probability()`, `market_price()`, `edge_value()`, `kelly_fraction()`, `bankroll_amount()`
- **Critical invariants validated:**
  - Position ≤ bankroll (prevents margin calls)
  - Negative edge → don't trade (prevents losses)
  - Trailing stop only tightens (never loosens)
  - Edge accounts for fees and spread (realistic P&L)

**🔵 Full Implementation Roadmap (Phases 1.5-5):**
- Phase 1.5: Config validation, position sizing (40+ properties)
- Phase 2: Historical data, model validation, strategy versioning (35+ properties)
- Phase 3: Order book, entry optimization (25+ properties)
- Phase 4: Ensemble models, backtesting (30+ properties)
- Phase 5: Position lifecycle, exit optimization, reporting (45+ properties)
- **Total: 165 properties, 16,500+ test cases**

**Writing Property Tests - Quick Start:**

```python
# 1. Import Hypothesis
from hypothesis import given
from hypothesis import strategies as st
from decimal import Decimal

# 2. Define custom strategy (if needed)
@st.composite
def edge_value(draw):
    return draw(st.decimals(min_value=-0.5, max_value=0.5, places=4))

# 3. Write property test with @given decorator
@given(edge=edge_value(), kelly_frac=kelly_fraction(), bankroll=bankroll_amount())
def test_position_never_exceeds_bankroll(edge, kelly_frac, bankroll):
    """PROPERTY: Position ≤ bankroll (prevents margin calls)"""
    position = calculate_kelly_size(edge, kelly_frac, bankroll)
    assert position <= bankroll, f"Position {position} > bankroll {bankroll}!"

# 4. Run with pytest
# pytest tests/property/test_kelly_criterion_properties.py -v
```

**Common Pitfalls:**

```python
# ❌ WRONG - Testing implementation details
@given(edge=edge_value())
def test_kelly_formula_calculation(edge):
    # Don't test "how" calculation is done, test "what" properties hold
    assert calculate_kelly_size(edge, ...) == edge * kelly_frac * bankroll

# ✅ CORRECT - Testing invariants
@given(edge=edge_value())
def test_negative_edge_means_no_trade(edge):
    if edge < 0:
        position = calculate_kelly_size(edge, kelly_frac, bankroll)
        assert position == Decimal("0")  # Property: negative edge → don't trade
```

```python
# ❌ WRONG - Unconstrained inputs waste test cases
@given(price=st.floats())  # Generates NaN, inf, negative prices
def test_bid_less_than_ask(price):
    # Most generated prices are invalid (negative, >1, NaN)
    # Hypothesis spends 90% of time on invalid inputs

# ✅ CORRECT - Constrained inputs focus on valid domain
@given(bid=st.decimals(min_value=0, max_value=0.99, places=4))
def test_bid_less_than_ask(bid):
    ask = bid + Decimal("0.01")  # Valid constraint
    # All generated bids are valid, tests are efficient
```

**Performance:**
- Property tests are slower (100 examples vs. 1 example)
- Phase 1.5: 26 properties = 2600 cases in 3.32s (acceptable)
- Full implementation: 165 properties = 16,500 cases in ~30-40s (acceptable)
- CI/CD impact: +30-40 seconds (total ~90-120 seconds)
- Mitigation: Run in parallel, use `max_examples=20` in CI

**Documentation:**
- **Requirements:** REQ-TEST-008 (complete), REQ-TEST-009 through REQ-TEST-011 (planned)
- **Architecture:** ADR-074 (Property-Based Testing Strategy)
- **Implementation Plan:** `docs/testing/HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md` (comprehensive roadmap)
- **Proof-of-Concept:** `tests/property/test_kelly_criterion_properties.py`, `tests/property/test_edge_detection_properties.py`

**Reference:**
- Pattern 1: Decimal Precision (use Decimal in custom strategies, never float)
- Pattern 7: Educational Docstrings (explain WHY properties matter in docstrings)
- ADR-074: Full rationale for property-based testing adoption
- REQ-TEST-008: Proof-of-concept completion details

---

## Pattern 11: Test Mocking Patterns (Mock API Boundaries, Not Implementation)

**WHY:** Tests that mock **internal implementation details** instead of **public APIs** are fragile. When internal implementation changes (even if public API stays the same), tests break unnecessarily. This creates false negatives and erodes confidence in the test suite.

**The Antipattern:**

Mocking internal implementation details that are **not part of the public contract**:

```python
# ❌ WRONG - Mocking internal implementation (.load method)
@patch("config.config_loader.ConfigLoader")
def test_config_show_bad(mock_config_loader, runner):
    """FRAGILE: Breaks if ConfigLoader refactors .load() internally."""
    mock_config_loader.return_value.load.return_value = {
        "kelly_criterion": {"max_bet_size": "0.05"}
    }

    # CLI uses .get() method, but we mocked .load()!
    result = runner.invoke(app, ["config-show", "trading.yaml"])

    # Test fails even though public API (.get()) works fine
    assert result.exit_code == 0  # ❌ FAILS - .get() was never mocked!
```

**Why This Fails:**
1. **Implementation Detail:** `.load()` is an internal method used by ConfigLoader
2. **Public API:** `.get(file, key_path)` is what CLI commands actually call
3. **Coupling:** Test is coupled to implementation, not behavior
4. **False Negative:** Test fails when internal refactoring happens, even if public API unchanged

**The Correct Pattern:**

Mock the **public API** that your code actually uses:

```python
# ✅ CORRECT - Mocking public API (.get method)
@patch("config.config_loader.ConfigLoader")
def test_config_show_good(mock_config_loader, runner):
    """ROBUST: Tests actual public API contract."""
    # Mock the .get() method that CLI actually calls
    mock_config_loader.return_value.get.return_value = {
        "kelly_criterion": {"max_bet_size": "0.05"}
    }

    # CLI calls .get(), we mocked .get() ✅
    result = runner.invoke(app, ["config-show", "trading.yaml"])

    assert result.exit_code == 0  # ✅ PASSES
    assert "max_bet_size" in result.stdout
```

**Real-World Examples from Precog:**

### Example 1: ConfigLoader Mocking (PR #19 and PR #20)

**Problem:** TestConfigValidate and TestConfigShow were both mocking `.load()` but CLI commands use `.get()`.

**Files Affected:**
- `tests/unit/test_main.py` (lines 1875-2037: TestConfigValidate)
- `tests/unit/test_main.py` (lines 2128-2290: TestConfigShow)

**Fix Pattern:**

```python
# ❌ WRONG (old code)
mock_config_loader.return_value.load.return_value = {...}

# ✅ CORRECT (fixed code)
mock_config_loader.return_value.get.return_value = {...}
```

**ConfigLoader Public API:**
```python
class ConfigLoader:
    def get(self, config_file: str, key_path: str | None = None) -> Any:
        """Public API - Use this in CLI commands."""
        # Returns entire config dict if key_path is None
        # Returns nested value if key_path provided (e.g., "kelly_criterion.max_bet_size")

    def load(self, filename: str) -> dict:
        """Internal implementation - DO NOT mock this in tests!"""
        # Used internally by .get(), may change in future refactoring
```

**Correct Mocking Patterns:**

```python
# Pattern 1: Mock .get() for entire config file
@patch("config.config_loader.ConfigLoader")
def test_show_entire_file(mock_config_loader, runner):
    mock_config_loader.return_value.get.return_value = {
        "kelly_criterion": {"max_bet_size": "0.05"},
        "enabled": True
    }
    result = runner.invoke(app, ["config-show", "trading.yaml"])
    assert "kelly_criterion" in result.stdout

# Pattern 2: Mock .get() for nested key path
@patch("config.config_loader.ConfigLoader")
def test_show_specific_key(mock_config_loader, runner):
    # .get(file, key_path) returns direct value for nested keys
    mock_config_loader.return_value.get.return_value = "0.05"
    result = runner.invoke(app, ["config-show", "trading.yaml", "--key", "kelly_criterion.max_bet_size"])
    assert "0.05" in result.stdout

# Pattern 3: Mock .get() with side_effect for errors
@patch("config.config_loader.ConfigLoader")
def test_show_missing_file(mock_config_loader, runner):
    mock_config_loader.return_value.get.side_effect = FileNotFoundError("Config not found")
    result = runner.invoke(app, ["config-show", "missing.yaml"])
    assert result.exit_code == 1

# Pattern 4: Mock .get() with side_effect list (multiple calls)
@patch("config.config_loader.ConfigLoader")
def test_show_invalid_key(mock_config_loader, runner):
    # First call: .get(file, bad_key) raises KeyError
    # Second call: .get(file) returns full config to show available keys
    mock_config_loader.return_value.get.side_effect = [
        KeyError("invalid.key"),
        {"kelly_criterion": {"max_bet_size": "0.05"}}
    ]
    result = runner.invoke(app, ["config-show", "trading.yaml", "--key", "invalid.key"])
    assert result.exit_code == 1
    assert "kelly_criterion" in result.stdout  # Shows available keys
```

**Mocking Hierarchy (Most Fragile → Most Robust):**

| Level | What to Mock | Fragility | Example |
|-------|--------------|-----------|---------|
| **1. Internal Details** | Private methods, internal state | 🔴 VERY FRAGILE | `.load()`, `._cache`, `._http_client` |
| **2. External Dependencies** | HTTP clients, file I/O | 🟡 MODERATELY FRAGILE | `requests.Session`, `open()` |
| **3. Public API Boundary** | Public methods, interfaces | 🟢 ROBUST | `.get()`, `.fetch_markets()`, `.calculate_kelly()` |
| **4. Integration Tests** | Real dependencies (test mode) | 🟢 MOST ROBUST | Live test database, demo API |

**Best Practices:**

1. **Mock at API Boundaries:**
   - ✅ Mock: `.get()`, `.fetch_markets()`, `.calculate_position()`
   - ❌ Don't Mock: `.load()`, `._parse_yaml()`, `._validate()`

2. **Test Public Contracts:**
   - Mock the methods **your code actually calls**
   - Don't mock methods **your code doesn't call**

3. **Use side_effect for Multiple Calls:**
   ```python
   # If function calls .get() multiple times with different behaviors:
   mock.get.side_effect = [
       first_return_value,
       second_return_value,
       KeyError("third call fails")
   ]
   ```

4. **Match Return Types:**
   ```python
   # If .get() returns dict, mock should return dict
   mock.get.return_value = {"key": "value"}

   # If .get() returns Decimal, mock should return Decimal
   mock.get.return_value = Decimal("0.52")

   # If .get() raises exception, use side_effect
   mock.get.side_effect = FileNotFoundError("Not found")
   ```

5. **Validate Mock Was Called Correctly:**
   ```python
   # Verify your code called the mocked method with correct args
   result = client.get("trading.yaml", "kelly_criterion.max_bet_size")
   mock.get.assert_called_once_with("trading.yaml", "kelly_criterion.max_bet_size")
   ```

**When Mocking is NOT the Answer:**

Sometimes integration tests are better than mocked unit tests:

```python
# ❌ Over-mocking obscures real behavior
@patch("config.config_loader.ConfigLoader.get")
@patch("api_connectors.kalshi_client.KalshiClient.fetch_markets")
@patch("trading.position_manager.PositionManager.open_position")
def test_entire_trading_flow_with_mocks(mock1, mock2, mock3):
    """TOO MANY MOCKS - Not testing real integration!"""
    # This test doesn't validate actual interactions

# ✅ Integration test with real components (test mode)
def test_entire_trading_flow_integration(test_db, demo_api):
    """Tests real interactions with test fixtures."""
    config = ConfigLoader().get("trading.yaml")  # Real config loading
    client = KalshiClient(mode="demo")  # Real API (demo endpoint)
    manager = PositionManager(db=test_db)  # Real database (test instance)
    # Validates actual end-to-end behavior
```

**Lessons from PR #19 and PR #20:**

1. **Same Mistake Twice:** Both TestConfigValidate and TestConfigShow made the same mocking error
2. **Root Cause:** Tests were written by copy-paste without understanding public API
3. **Prevention:** Document public API contracts clearly in docstrings
4. **Fix Pattern:** Search for `.return_value.load` and replace with `.return_value.get`

**Quick Decision Tree:**

```
Q: Should I mock this method?
├─ Is it called by my code?
│  ├─ YES → Continue
│  └─ NO → Don't mock it (not part of test)
├─ Is it part of the public API?
│  ├─ YES → Safe to mock ✅
│  └─ NO (private/internal) → Don't mock (fragile) ❌
└─ Can I use a real instance instead (integration test)?
   ├─ YES → Prefer real instance 🟢
   └─ NO (too slow/complex) → Mock the public API ✅
```

**Impact on Test Maintenance:**

- **Before (Fragile Tests):** 11 tests broke when ConfigLoader refactored `.load()` implementation
- **After (Robust Tests):** 0 tests break when internal implementation changes (as long as `.get()` API unchanged)
- **Maintenance Cost:** Reduced test maintenance by 90% for ConfigLoader tests

**Reference:**
- PR #19: Fixed 5 TestConfigValidate tests (`.load()` → `.get()` pattern)
- PR #20: Fixed 5 TestConfigShow tests + 1 property test
- `config/config_loader.py` (lines 142-193): ConfigLoader public API documentation
- `tests/unit/test_main.py` (lines 1875-2290): Corrected mocking examples

---

## Pattern 12: Test Fixture Security Compliance (MANDATORY)

**When to Use:** When writing test fixtures for functions that include security validations (path traversal protection, file extension validation, etc.)

**The Problem:**
When production code adds security validations, existing test fixtures using `tmp_path` (system temp) can break because they create files outside the project directory.

**Example from PR #79:**
- PR #76 added path traversal protection to `apply_schema()` and `apply_migrations()`
- Security validation rejects files outside project: `is_relative_to(project_root)`
- Tests using `tmp_path` failed: files created in `C:\Users\...\AppData\Local\Temp\...`
- Error: `'Security: Schema file must be within project directory'`

### ✅ CORRECT Pattern: Project-Relative Test Files

```python
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def temp_schema_file() -> Generator[str, None, None]:
    """Create temporary schema file within project for testing.

    Returns:
        Path to temporary schema file (project-relative for security validation)

    Educational Note:
        We create temp files WITHIN the project directory to pass security
        validation that prevents path traversal attacks. The file is cleaned
        up after the test via yield/finally pattern.
    """
    # Create project-relative temp directory
    project_root = Path.cwd()
    temp_dir = project_root / "tests" / ".tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Create unique schema file
    unique_id = uuid.uuid4().hex[:8]
    schema_file = temp_dir / f"test_schema_{unique_id}.sql"
    schema_file.write_text("CREATE TABLE test_table (id SERIAL PRIMARY KEY);")

    try:
        yield str(schema_file)
    finally:
        # Cleanup
        if schema_file.exists():
            schema_file.unlink()
        # Clean up temp_dir if empty
        try:
            temp_dir.rmdir()
        except OSError:
            pass  # Directory not empty or doesn't exist
```

### ❌ WRONG Pattern: Using tmp_path with Security-Validated Functions

```python
@pytest.fixture
def temp_schema_file(tmp_path: Path) -> str:
    """Creates file in system temp - FAILS security validation!"""
    schema_file = tmp_path / "test_schema.sql"  # Outside project!
    schema_file.write_text("CREATE TABLE test_table (id SERIAL PRIMARY KEY);")
    return str(schema_file)
    # Security validation fails: file not within project directory
```

### Key Implementation Details

**1. Use Generator Pattern with yield/finally**
- Type: `Generator[str, None, None]` (not `str`)
- `yield` provides fixture value to test
- `finally` ensures cleanup even if test fails

**2. UUID for Unique Filenames**
- `uuid.uuid4().hex[:8]` creates short unique IDs
- Prevents file collisions when tests run in parallel
- Example: `test_schema_a3f2b8c1.sql`

**3. Project-Relative Paths**
- Use `Path.cwd()` to get project root
- Create files in `tests/.tmp/` subdirectory
- Passes `is_relative_to(project_root)` security check

**4. Cleanup Strategy**
- Delete created files in `finally` block
- Try to remove temp_dir (may fail if other tests using it - that's OK)
- Graceful handling with `try/except OSError`

### When to Use This Pattern

**✅ Use project-relative fixtures when:**
- Function validates file paths (path traversal protection)
- Function checks file extensions (.sql, .yaml, etc.)
- Function uses `Path.resolve()` and `is_relative_to()`
- Function executes external commands with file paths (subprocess)

**❌ Use tmp_path when:**
- Testing file I/O operations (read/write/parse)
- No security validations on file location
- Function doesn't care where file is located
- Testing path manipulation itself

### Real-World Impact (PR #79)

**Before (using tmp_path):**
- 9/25 tests failing
- Coverage: 68.32%
- Error: "Security: Schema file must be within project directory"

**After (using project-relative):**
- 25/25 tests passing
- Coverage: 89.11% (+20.79pp)
- Security validation works correctly

### Common Mistakes

**Mistake 1: Forgetting to import Generator**
```python
# ❌ WRONG
def temp_schema_file() -> str:  # Missing Generator type

# ✅ CORRECT
from collections.abc import Generator

def temp_schema_file() -> Generator[str, None, None]:
```

**Mistake 2: Not using uuid (file collisions)**
```python
# ❌ WRONG (parallel tests collide)
schema_file = temp_dir / "test_schema.sql"

# ✅ CORRECT (unique per test)
unique_id = uuid.uuid4().hex[:8]
schema_file = temp_dir / f"test_schema_{unique_id}.sql"
```

**Mistake 3: Cleanup without error handling**
```python
# ❌ WRONG (fails if directory not empty)
temp_dir.rmdir()

# ✅ CORRECT (graceful handling)
try:
    temp_dir.rmdir()
except OSError:
    pass  # Directory not empty or doesn't exist
```

### Cross-References
- **PR #79:** Test initialization fixture fixes for security validation compatibility
- **PR #76:** Added path traversal protection (CWE-22) to `apply_schema()` and `apply_migrations()`
- **DEVELOPMENT_PHILOSOPHY_V1.2.md:** Security-First Testing principle
- **Pattern 4:** Security (NO CREDENTIALS IN CODE) - Related security best practices

---

## Pattern 13: Test Coverage Quality (Mock Sparingly, Integrate Thoroughly) - CRITICAL

**WHY:** Tests can pass with 100% test pass rate yet miss critical bugs. Phase 1.5 discovery: Strategy Manager had 17/17 tests passing with mocks, but 13/17 tests failed (77% failure rate) when refactored to use real database fixtures. Connection pool exhaustion bugs went completely undetected.

**The Critical Lesson:** "Tests passing" ≠ "Tests sufficient" ≠ "Code works correctly"

### The Problem: Over-Reliance on Mocks

**What went wrong:**

```python
# ❌ WRONG - Strategy Manager tests (17/17 passing, but implementation broken)
@patch("precog.trading.strategy_manager.get_connection")
def test_create_strategy(self, mock_get_connection, mock_connection, mock_cursor):
    """Test creates strategy - BUT DOESN'T TEST CONNECTION POOL!"""
    mock_get_connection.return_value = mock_connection
    mock_cursor.fetchone.return_value = (1, "strategy_v1", "1.0", ...)  # Fake response

    manager = StrategyManager()
    result = manager.create_strategy(...)  # Calls mock, not real DB

    assert result["strategy_id"] == 1  # ✅ Test passes!
    # But implementation has connection pool leak - not caught!
```

**Why this is catastrophic:**
- Mocks test "did we call the right function?" NOT "does the system work?"
- Mocks bypass integration bugs (connection pool exhaustion, transaction handling, constraint violations)
- Mocks provide false confidence - green tests, broken code
- In production: System crashes after 5 creates (connection pool exhausted)

### ✅ CORRECT Pattern: Real Infrastructure with Test Fixtures

```python
# ✅ CORRECT - Use real database with conftest.py fixtures
def test_create_strategy(clean_test_data, manager, strategy_factory):
    """Test creates strategy - TESTS REAL DATABASE!"""
    result = manager.create_strategy(**strategy_factory)  # Calls REAL database

    assert result["strategy_id"] is not None  # ✅ Test passes
    # If connection pool leak exists → test fails with pool exhausted error
    # If SQL syntax wrong → test fails with database error
    # If constraints violated → test fails with constraint error
```

### When to Use Mocks vs. Real Infrastructure

**✅ Mocks are APPROPRIATE for:**
- **External APIs** (Kalshi, ESPN, Polymarket) - expensive, rate-limited, flaky
- **Time-dependent code** (`datetime.now()`, `time.sleep()`)
- **Random number generation** (`random.random()`, `uuid.uuid4()`)
- **File I/O** (in some cases - when testing file handling logic, not content)
- **Network requests** (HTTP, WebSocket) - unreliable, slow

**❌ Mocks are NOT APPROPRIATE for:**
- **Database** (use test database with `clean_test_data` fixture)
- **Internal application logic** (strategy manager, model manager, position manager)
- **Configuration loading** (use test configs, not mocks)
- **Logging** (use test logger, capture output)
- **Connection pooling** (use `db_pool` fixture with real pool)

### ALWAYS Use Test Fixtures from conftest.py

**MANDATORY fixtures for database tests:**

```python
# conftest.py provides these fixtures - ALWAYS USE THEM
@pytest.fixture
def clean_test_data(db_pool):
    """Cleans database before/after each test. ALWAYS USE THIS."""
    # Deletes all test data before test runs
    # Ensures clean state
    # Automatically rolls back after test

@pytest.fixture
def db_pool():
    """Provides real connection pool. Use for pool-related tests."""
    # Real SimpleConnectionPool with minconn=2, maxconn=5
    # Tests pool exhaustion scenarios
    # Automatically cleans up connections

@pytest.fixture
def db_cursor(db_pool):
    """Provides real database cursor. Use for SQL execution tests."""
    # Real psycopg2 cursor
    # Automatically commits/rolls back
    # Cleans up cursor after test
```

**Example usage:**

```python
# ✅ CORRECT - All manager tests use clean_test_data
def test_create_strategy(clean_test_data, manager, strategy_factory):
    """Uses real database, real connection pool, real SQL."""
    result = manager.create_strategy(**strategy_factory)
    assert result["strategy_id"] is not None
    # Database automatically cleaned up after test

def test_connection_pool_exhaustion(clean_test_data, db_pool):
    """Tests connection pool limits with REAL pool."""
    manager = StrategyManager()

    # Create 6 strategies (pool maxconn=5)
    for i in range(6):
        result = manager.create_strategy(
            strategy_name=f"test_strategy_{i}",
            strategy_version="1.0",
            approach="value",
            config={"test": True},
        )
        assert result["strategy_id"] is not None

    # If connection pool leak exists → test fails here
```

### 8 Required Test Types (Not Just Unit Tests)

**CRITICAL:** Trading applications need multiple test types, not just unit tests.

| Test Type | Purpose | When Required | Example |
|-----------|---------|---------------|---------|
| **Unit** | Isolated function logic | ✅ ALWAYS | `test_calculate_kelly_fraction()` |
| **Property** | Mathematical invariants | ✅ CRITICAL PATH | `test_decimal_precision_preserved()` |
| **Integration** | Components together | ✅ MANAGER LAYER | `test_strategy_manager_database()` |
| **End-to-End** | Complete workflows | ⚠️ PHASE 2+ | `test_trading_lifecycle()` |
| **Stress** | Infrastructure limits | ✅ CRITICAL | `test_connection_pool_exhaustion()` |
| **Race Condition** | Concurrent operations | ⚠️ PHASE 3+ | `test_concurrent_position_updates()` |
| **Performance** | Latency/throughput | ⏸️ PHASE 5+ | `test_order_execution_latency()` |
| **Chaos** | Failure recovery | ⏸️ PHASE 5+ | `test_database_failure_recovery()` |

**Phase 1.5 Requirements:**
- ✅ Unit tests (isolated logic)
- ✅ Property tests (Hypothesis for Kelly criterion, edge detection)
- ✅ Integration tests (manager layer + database)
- ✅ Stress tests (connection pool exhaustion)

### Coverage Standards: Percentage ≠ Quality

**The Aggregate Coverage Trap:**

```
Overall Coverage: 86.25% ✅ (looks good!)

But module breakdown reveals gaps:
├── Model Manager: 25.75% ❌ (target: ≥85%, gap: -59.25%)
├── Strategy Manager: 19.96% ❌ (target: ≥85%, gap: -65.04%)
├── Position Manager: 0% ❌ (not implemented yet)
├── Database Layer: 86.32% ✅ (target: ≥80%)
└── API Clients: 93.19% ✅ (target: ≥80%)
```

**Module-Level Coverage Targets:**
- **Critical Path** (trading execution, position monitoring): ≥90%
- **Manager Layer** (strategy, model, position managers): ≥85%
- **Infrastructure** (database, logging, config): ≥80%
- **API Clients** (Kalshi, ESPN): ≥80%
- **Utilities** (helpers, formatters): ≥75%

### Test Review Checklist (MANDATORY Before Marking Work Complete)

Run this checklist before marking any feature complete:

```markdown
## Test Quality Checklist

- [ ] **Tests use real infrastructure (database, not mocks)?**
  - ✅ Uses `clean_test_data` fixture
  - ✅ Uses `db_pool` fixture for pool tests
  - ❌ NO `@patch("get_connection")` mocks

- [ ] **Tests use fixtures from conftest.py?**
  - ✅ ALL database tests use `clean_test_data`
  - ✅ NO manual `mock_connection` or `mock_cursor` fixtures
  - ✅ Fixtures handle cleanup automatically

- [ ] **Tests cover happy path AND edge cases?**
  - ✅ Happy path (normal create/update/delete)
  - ✅ Edge cases (null values, empty strings, boundary conditions)
  - ✅ Failure modes (database errors, connection pool exhausted)

- [ ] **Tests cover failure modes?**
  - ✅ What happens when database fails?
  - ✅ What happens when connection pool exhausted?
  - ✅ What happens when invalid data provided?

- [ ] **Coverage percentage ≥ target for this module?**
  - ✅ Manager modules: ≥85%
  - ✅ Infrastructure modules: ≥80%
  - ✅ Critical path: ≥90%

- [ ] **Tests written BEFORE implementation (TDD)?**
  - ✅ Test written first (red)
  - ✅ Implementation written second (green)
  - ✅ Refactored (clean)

- [ ] **Multiple test types present?**
  - ✅ Unit tests (isolated logic)
  - ✅ Integration tests (database + application)
  - ✅ Property tests (if mathematical invariants)
  - ✅ Stress tests (if touches infrastructure limits)
```

### Real-World Impact: Strategy Manager Example

**Before (using mocks):**
- Tests: 17/17 passing (100% pass rate) ✅
- Coverage: 19.96% ❌
- Bugs found: 0 ✅
- **Production behavior:** System crashes after 5 creates (connection pool exhausted)

**After (using real infrastructure):**
- Tests: 13/17 failing (77% failure rate) ❌
- Coverage: TBD (to be increased to ≥85%)
- Bugs found: 1 critical (connection pool leak) ✅
- **Production behavior:** Would have been caught before deployment

**Key Learning:** 77% of Strategy Manager tests were providing false confidence. They passed because they never touched real infrastructure.

### Prevention: Multi-Layer Test Strategy

```python
# Layer 1: Unit tests (fast, isolated)
def test_calculate_edge_unit():
    """Tests edge calculation math (no database)."""
    from precog.trading.strategy_manager import calculate_edge

    true_prob = Decimal("0.6")
    market_price = Decimal("0.5")
    edge = calculate_edge(true_prob, market_price)

    assert edge == Decimal("0.1")  # 60% - 50% = 10% edge

# Layer 2: Integration tests (real database)
def test_create_strategy_integration(clean_test_data, manager, strategy_factory):
    """Tests strategy creation with REAL database."""
    result = manager.create_strategy(**strategy_factory)

    assert result["strategy_id"] is not None
    # Verifies:
    # - SQL syntax correct
    # - Connection pool works
    # - Transactions commit
    # - Constraints enforced

# Layer 3: Stress tests (infrastructure limits)
def test_connection_pool_stress(clean_test_data):
    """Tests connection pool exhaustion with 10 concurrent creates."""
    import concurrent.futures

    def create_strategy(i):
        manager = StrategyManager()
        return manager.create_strategy(
            strategy_name=f"stress_test_{i}",
            strategy_version="1.0",
            approach="value",
            config={"test": True},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(create_strategy, i) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 10  # All creates succeeded
    # If connection pool leak → this fails with pool exhausted error

# Layer 4: Property tests (mathematical invariants)
from hypothesis import given
from hypothesis import strategies as st

@given(
    true_prob=st.decimals(min_value="0.01", max_value="0.99", places=4),
    market_price=st.decimals(min_value="0.01", max_value="0.99", places=4),
)
def test_edge_always_decimal(true_prob, market_price):
    """Edge calculation NEVER produces float (test with 100+ cases)."""
    edge = calculate_edge(true_prob, market_price)

    assert isinstance(edge, Decimal)  # NEVER float
    # Hypothesis generates 100+ test cases automatically
```

### Common Mistakes to Avoid

**Mistake 1: Mocking internal infrastructure**
```python
# ❌ WRONG
@patch("precog.database.connection.get_connection")
def test_create_strategy(mock_get_connection):
    # Don't mock internal infrastructure!

# ✅ CORRECT
def test_create_strategy(clean_test_data, manager, strategy_factory):
    # Use real database with fixtures
```

**Mistake 2: Not using conftest.py fixtures**
```python
# ❌ WRONG
def test_create_strategy():
    conn = psycopg2.connect(...)  # Manual connection
    cursor = conn.cursor()
    # Manual cleanup required

# ✅ CORRECT
def test_create_strategy(clean_test_data, db_cursor):
    # Fixtures handle connection + cleanup
```

**Mistake 3: Aggregate coverage hiding gaps**
```python
# ❌ WRONG
# "Overall coverage: 86% ✅ - ship it!"

# ✅ CORRECT
# "Model Manager: 25% ❌ - below 85% target, not ready"
```

**Mistake 4: Only unit tests, no integration/stress tests**
```python
# ❌ WRONG
# 30 unit tests, 0 integration tests, 0 stress tests

# ✅ CORRECT
# 30 unit tests + 15 integration tests + 5 stress tests
```

### Cross-References
- **TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md:** Post-mortem documenting Strategy Manager test failure
- **TEST_REQUIREMENTS_COMPREHENSIVE_V1.0.md:** REQ-TEST-012 through REQ-TEST-019 (8 test types, coverage standards, mock restrictions)
- **TESTING_GAPS_ANALYSIS.md:** Current coverage gaps and remediation plan
- **DEVELOPMENT_PHILOSOPHY_V1.3.md:** Section 1 - Test Quality: When Tests Pass But Aren't Sufficient
- **Pattern 11:** Test Mocking Patterns (HOW to mock public APIs vs implementation)
- **Pattern 12:** Test Fixture Security Compliance (project-relative test fixtures)
- **tests/conftest.py:** Test fixture infrastructure (`clean_test_data`, `db_pool`, `db_cursor`)

---

## Pattern 14: Schema Migration → CRUD Operations Update Workflow (CRITICAL)

**WHY:** When database schema changes (especially for SCD Type 2 tables with dual-key pattern), CRUD operations MUST be updated to match. Forgetting to update CRUD operations causes:
- Insert failures (missing required columns)
- Query failures (column doesn't exist)
- Business logic bugs (expecting field that doesn't exist)
- SCD Type 2 violations (forgetting row_current_ind filter)

**The Problem:** Database schema and CRUD operations can drift out of sync across multiple locations.

**Phase 1.5 Example:**
- Migration 011 added dual-key schema to positions table (surrogate `id` + business `position_id`)
- Required updates to 4 CRUD functions: `open_position()`, `update_position()`, `close_position()`, `get_current_positions()`
- Missed update in `close_position()` → missing `current_price` column → test assertion failure

### When This Pattern Applies

**✅ ALWAYS use this workflow when:**
- Adding new columns to SCD Type 2 tables (positions, markets, edges, balances)
- Changing column types (VARCHAR → DECIMAL, INTEGER → BIGINT)
- Adding/changing constraints (UNIQUE, FOREIGN KEY, CHECK)
- Implementing dual-key schema pattern (surrogate + business key)
- Changing SCD Type 2 metadata columns (row_current_ind, row_effective_date)

**Tables Using SCD Type 2 + Dual-Key Pattern:**
- ✅ `positions` (Migration 011 - IMPLEMENTED)
- ✅ `markets` (Migration 004 - IMPLEMENTED)
- 📋 `trades` (Planned - Phase 2)
- 📋 `account_balance` (Planned - Phase 2)
- 📋 `edges` (Planned - Phase 4)

### 5-Step Mandatory Workflow

#### Step 1: Create Database Migration (10-30 min)

```sql
-- Migration 011: Add dual-key schema to positions table
-- File: src/precog/database/migrations/011_add_positions_dual_key.sql

-- 1. Add position_id business key column (nullable initially)
ALTER TABLE positions ADD COLUMN position_id VARCHAR(50);

-- 2. Populate position_id from id (surrogate key)
UPDATE positions SET position_id = 'POS-' || id::TEXT WHERE position_id IS NULL;

-- 3. Make position_id NOT NULL
ALTER TABLE positions ALTER COLUMN position_id SET NOT NULL;

-- 4. Create partial UNIQUE index (one current version per position_id)
CREATE UNIQUE INDEX positions_position_id_current_unique
ON positions (position_id)
WHERE row_current_ind = TRUE;

-- 5. Add comment documenting dual-key pattern
COMMENT ON COLUMN positions.position_id IS 'Business key (repeats across versions), format: POS-{id}';
COMMENT ON COLUMN positions.id IS 'Surrogate PRIMARY KEY (unique across all versions, used for FK references)';
```

**Migration Checklist:**
- [ ] Added new column with correct type
- [ ] Populated existing rows if NOT NULL
- [ ] Created indexes if needed (partial unique for SCD Type 2)
- [ ] Added comments documenting pattern
- [ ] Tested migration on local database
- [ ] Verified rollback script (if applicable)

#### Step 2: Update CRUD Operations (30-60 min)

**CRITICAL: Update ALL functions that touch the modified table.**

**Example: positions table has 4 CRUD functions to update:**

**2a. open_position() - Set business_id from surrogate_id**

```python
# src/precog/database/crud_operations.py

def open_position(
    market_id: str,
    strategy_id: int,
    model_id: int,
    side: str,
    quantity: int,
    entry_price: Decimal,
    target_price: Decimal | None = None,
    stop_loss_price: Decimal | None = None,
    trailing_stop_config: dict[str, Any] | None = None,
    position_metadata: dict[str, Any] | None = None,
) -> str:
    """Open new position with dual-key pattern.

    Returns:
        position_id (business key, format: 'POS-{id}')

    Educational Note:
        Dual-key pattern: surrogate PRIMARY KEY (id) + business key (position_id).
        Business key is set from surrogate key after INSERT to guarantee uniqueness.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Step 1: INSERT without business_id (generates surrogate id)
            cur.execute("""
                INSERT INTO positions (
                    market_id, strategy_id, model_id, side,
                    quantity, entry_price, current_price,
                    target_price, stop_loss_price,
                    trailing_stop_state, position_metadata,
                    status, row_current_ind
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open', TRUE)
                RETURNING id
            """, (
                market_id, strategy_id, model_id, side,
                quantity, entry_price, entry_price,
                target_price, stop_loss_price,
                Json(trailing_stop_config) if trailing_stop_config else None,
                Json(position_metadata) if position_metadata else None,
            ))

            surrogate_id = cur.fetchone()['id']

            # Step 2: UPDATE to set business_id from surrogate_id
            cur.execute("""
                UPDATE positions
                SET position_id = %s
                WHERE id = %s
                RETURNING position_id
            """, (f'POS-{surrogate_id}', surrogate_id))

            position_id = cur.fetchone()['position_id']
            conn.commit()
            return position_id
    finally:
        release_connection(conn)
```

**2b. update_position() - SCD Type 2 versioning**

```python
def update_position(
    position_id: int,  # Surrogate key (NOT business key!)
    current_price: Decimal,
) -> int:
    """Update position - creates new SCD Type 2 version.

    Args:
        position_id: Surrogate key (id column, unique across all versions)
        current_price: New market price

    Returns:
        New surrogate id for updated version

    Educational Note:
        SCD Type 2 pattern: UPDATE old row (set row_current_ind=FALSE),
        then INSERT new row (same position_id, new surrogate id).
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Step 1: Get current version (must filter by row_current_ind!)
            cur.execute("""
                SELECT * FROM positions
                WHERE id = %s AND row_current_ind = TRUE
            """, (position_id,))

            current = cur.fetchone()
            if not current:
                raise ValueError(f"Position {position_id} not found or not current")

            # Step 2: Expire current version
            cur.execute("""
                UPDATE positions
                SET row_current_ind = FALSE, row_expiration_date = NOW()
                WHERE id = %s
            """, (position_id,))

            # Step 3: Insert new version (REUSE same position_id business key)
            cur.execute("""
                INSERT INTO positions (
                    position_id, market_id, strategy_id, model_id, side,
                    quantity, entry_price, current_price,
                    target_price, stop_loss_price,
                    trailing_stop_state, position_metadata,
                    status, entry_time, row_current_ind
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id
            """, (
                current['position_id'],  # Reuse business key!
                current['market_id'], current['strategy_id'], current['model_id'],
                current['side'], current['quantity'], current['entry_price'],
                current_price,  # Updated field
                current['target_price'], current['stop_loss_price'],
                current['trailing_stop_state'], current['position_metadata'],
                current['status'], current['entry_time'],
            ))

            new_id = cur.fetchone()['id']
            conn.commit()
            return new_id
    finally:
        release_connection(conn)
```

**2c. close_position() - Final SCD Type 2 version**

```python
def close_position(
    position_id: int,
    exit_price: Decimal,
    exit_reason: str,
    realized_pnl: Decimal,
) -> int:
    """Close position - creates final SCD Type 2 version with status='closed'.

    CRITICAL: Must set current_price to exit_price for closed positions.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get current version
            cur.execute("""
                SELECT * FROM positions
                WHERE id = %s AND row_current_ind = TRUE
            """, (position_id,))

            current = cur.fetchone()
            if not current:
                raise ValueError(f"Position {position_id} not found")

            # Expire current version
            cur.execute("""
                UPDATE positions
                SET row_current_ind = FALSE, row_expiration_date = NOW()
                WHERE id = %s
            """, (position_id,))

            # Insert closed version (MUST include ALL columns!)
            cur.execute("""
                INSERT INTO positions (
                    position_id, market_id, strategy_id, model_id, side,
                    quantity, entry_price, exit_price, current_price,
                    realized_pnl,
                    target_price, stop_loss_price,
                    trailing_stop_state, position_metadata,
                    status, entry_time, exit_time, row_current_ind
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'closed', %s, NOW(), TRUE)
                RETURNING id
            """, (
                current['position_id'], current['market_id'], current['strategy_id'],
                current['model_id'], current['side'], current['quantity'],
                current['entry_price'], exit_price,
                exit_price,  # ⚠️ CRITICAL: Set current_price to exit_price!
                realized_pnl,
                current['target_price'], current['stop_loss_price'],
                current['trailing_stop_state'], current['position_metadata'],
                current['entry_time'],
            ))

            final_id = cur.fetchone()['id']
            conn.commit()
            return final_id
    finally:
        release_connection(conn)
```

**2d. get_current_positions() - ALWAYS filter by row_current_ind**

```python
def get_current_positions(status: str | None = None, market_id: str | None = None) -> list[dict]:
    """Get current positions (filters by row_current_ind = TRUE).

    Educational Note:
        CRITICAL: ALWAYS filter SCD Type 2 tables by row_current_ind = TRUE
        to get only current versions, not historical versions.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT
                    p.*,
                    m.ticker, m.yes_price, m.no_price, m.market_type
                FROM positions p
                JOIN markets m ON p.market_id = m.market_id AND m.row_current_ind = TRUE
                WHERE p.row_current_ind = TRUE  -- ⚠️ CRITICAL: Filter current versions
            """
            params = []

            if status:
                query += " AND p.status = %s"
                params.append(status)

            if market_id:
                query += " AND p.market_id = %s"
                params.append(market_id)

            query += " ORDER BY p.entry_time DESC"

            cur.execute(query, params)
            return cur.fetchall()
    finally:
        release_connection(conn)
```

**CRUD Update Checklist:**
- [ ] Updated ALL INSERT statements to include new columns
- [ ] Updated ALL UPDATE statements to handle new columns
- [ ] Updated ALL SELECT statements to include new columns (if needed)
- [ ] Set business_id from surrogate_id on initial INSERT (dual-key pattern)
- [ ] ALWAYS filter by `row_current_ind = TRUE` in queries (SCD Type 2)
- [ ] Reuse business key when creating new SCD Type 2 versions
- [ ] Include ALL columns when inserting new versions (don't forget new columns!)

#### Step 3: Update Tests (30-60 min)

**CRITICAL: Tests must use REAL database, not mocks (Pattern 13).**

```python
# tests/unit/trading/test_position_manager.py

def test_open_position_sets_business_id(clean_test_data, manager, position_params):
    """Verify open_position sets position_id from surrogate id."""
    result = manager.open_position(**position_params)

    # Verify business_id format
    assert result['position_id'].startswith('POS-')
    assert result['id'] is not None  # Surrogate key

    # Verify business_id matches surrogate_id
    expected_position_id = f"POS-{result['id']}"
    assert result['position_id'] == expected_position_id


def test_update_position_creates_new_version_with_same_business_id(
    clean_test_data, manager, position_params
):
    """Verify SCD Type 2: new version reuses same position_id."""
    # Open position
    position = manager.open_position(**position_params)
    original_id = position['id']
    original_position_id = position['position_id']

    # Update position (creates new SCD Type 2 version)
    updated = manager.update_position(
        position_id=original_id,
        current_price=Decimal("0.6000"),
    )

    # Verify new version has DIFFERENT surrogate id
    assert updated['id'] != original_id

    # Verify new version has SAME business key
    assert updated['position_id'] == original_position_id

    # Verify old version is expired
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT row_current_ind FROM positions WHERE id = %s
            """, (original_id,))
            old_version = cur.fetchone()
            assert old_version['row_current_ind'] is False  # Expired
    finally:
        release_connection(conn)


def test_close_position_sets_current_price(clean_test_data, manager, position_params):
    """Verify close_position sets current_price to exit_price."""
    # Open position
    position = manager.open_position(**position_params)

    # Close position
    closed = manager.close_position(
        position_id=position['id'],
        exit_price=Decimal("0.7500"),
        exit_reason="profit_target",
    )

    # Verify current_price equals exit_price
    assert closed['current_price'] == Decimal("0.7500")
    assert closed['exit_price'] == Decimal("0.7500")
    assert closed['status'] == 'closed'


def test_get_current_positions_filters_by_row_current_ind(
    clean_test_data, manager, position_params
):
    """Verify get_current_positions only returns row_current_ind=TRUE."""
    # Open position
    position = manager.open_position(**position_params)
    original_id = position['id']

    # Update twice (creates 2 new versions, expires 2 old versions)
    manager.update_position(original_id, Decimal("0.5500"))
    manager.update_position(original_id, Decimal("0.6000"))

    # Should return 1 position (only current version)
    current_positions = manager.get_open_positions()
    assert len(current_positions) == 1

    # Verify returned position is the latest version
    assert current_positions[0]['current_price'] == Decimal("0.6000")

    # Verify database has 3 versions total (1 current + 2 expired)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM positions WHERE position_id = %s
            """, (position['position_id'],))
            total_versions = cur.fetchone()[0]
            assert total_versions == 3
    finally:
        release_connection(conn)
```

**Test Update Checklist:**
- [ ] Tests use `clean_test_data` fixture (real database)
- [ ] Tests verify business_id set correctly on INSERT
- [ ] Tests verify SCD Type 2 versioning (UPDATE + INSERT pattern)
- [ ] Tests verify row_current_ind filtering works
- [ ] Tests verify ALL new columns populated correctly
- [ ] Tests verify old versions expired (row_current_ind=FALSE)
- [ ] NO mocks for `get_connection()`, `ConfigLoader`, or internal CRUD

#### Step 4: Run Integration Tests (5-10 min)

```bash
# Run position manager tests
python -m pytest tests/unit/trading/test_position_manager.py -v

# Expected: All tests passing
# 23/23 tests passing (from Phase 1.5 example)

# Run full test suite
python -m pytest tests/ -v

# Check coverage
python -m pytest tests/ --cov=precog.database.crud_operations --cov-report=term-missing
```

**Integration Test Checklist:**
- [ ] All position manager tests passing
- [ ] All CRUD operation tests passing
- [ ] No SQL syntax errors
- [ ] No missing column errors
- [ ] Coverage ≥85% for CRUD operations
- [ ] Coverage ≥87% for position manager

#### Step 5: Update Documentation (10-20 min)

**Update 3 locations:**

**5a. DATABASE_SCHEMA_SUMMARY_V*.md**
```markdown
### positions Table (Dual-Key SCD Type 2)

**Purpose:** Track position lifecycle with historical versioning

**Dual-Key Pattern:**
- `id SERIAL PRIMARY KEY` - Surrogate key (unique across all versions, used for FK references)
- `position_id VARCHAR(50) NOT NULL` - Business key (repeats across versions, format: 'POS-{id}')
- Partial UNIQUE index: `CREATE UNIQUE INDEX ... ON positions (position_id) WHERE row_current_ind = TRUE`

**Key Columns:**
- `id` - Surrogate PRIMARY KEY
- `position_id` - Business key (user-facing, stable across versions)
- `market_id` - FK to markets (business key)
- `strategy_id` - FK to strategies
- `model_id` - FK to probability_models
- `entry_price DECIMAL(10,4)` - Original entry price
- `current_price DECIMAL(10,4)` - Latest market price
- `exit_price DECIMAL(10,4)` - Exit price (NULL until closed)
- `row_current_ind BOOLEAN` - TRUE = current version, FALSE = historical
- `row_effective_date TIMESTAMP` - Version start time
- `row_expiration_date TIMESTAMP` - Version end time (NULL for current)

**SCD Type 2 Behavior:**
- Updates create new row with same position_id, new surrogate id
- Old row: row_current_ind → FALSE, row_expiration_date → NOW()
- New row: row_current_ind → TRUE, row_effective_date → NOW()

**Migration:** Migration 011 (2025-11-19) - Added dual-key pattern
```

**5b. ADR-089 Cross-Reference**

Add positions table to "Tables Using This Pattern" section in ADR-089.

**5c. Pattern 14 (this document)**

You're reading it! 😊

**Documentation Update Checklist:**
- [ ] Updated DATABASE_SCHEMA_SUMMARY with dual-key columns
- [ ] Updated ADR-089 table list
- [ ] Updated MASTER_INDEX if new docs created
- [ ] Added migration number to documentation

### Common Mistakes to Avoid

**Mistake 1: Forgetting to set business_id from surrogate_id**

```python
# ❌ WRONG - business_id remains NULL
cur.execute("""
    INSERT INTO positions (market_id, strategy_id, ..., row_current_ind)
    VALUES (%s, %s, ..., TRUE)
    RETURNING id
""", (...))
# Missing UPDATE to set position_id!

# ✅ CORRECT - Set business_id after INSERT
surrogate_id = cur.fetchone()['id']
cur.execute("""
    UPDATE positions SET position_id = %s WHERE id = %s
""", (f'POS-{surrogate_id}', surrogate_id))
```

**Mistake 2: Forgetting row_current_ind filter in queries**

```python
# ❌ WRONG - Returns ALL versions (current + historical)
cur.execute("SELECT * FROM positions WHERE market_id = %s", (market_id,))

# ✅ CORRECT - Returns only current versions
cur.execute("""
    SELECT * FROM positions
    WHERE market_id = %s AND row_current_ind = TRUE
""", (market_id,))
```

**Mistake 3: Not reusing business key when creating new version**

```python
# ❌ WRONG - Generates NEW position_id (violates SCD Type 2)
cur.execute("""
    INSERT INTO positions (position_id, market_id, ...)
    VALUES ('POS-NEW-ID', %s, ...)  -- Wrong!
""", (...))

# ✅ CORRECT - Reuse same position_id from old version
cur.execute("""
    INSERT INTO positions (position_id, market_id, ...)
    VALUES (%s, %s, ...)  -- Reuse current['position_id']
""", (current['position_id'], ...))
```

**Mistake 4: Forgetting new columns in INSERT**

```python
# ❌ WRONG - Missing current_price in close_position INSERT
cur.execute("""
    INSERT INTO positions (
        position_id, market_id, ..., exit_price, status
    )
    VALUES (%s, %s, ..., %s, 'closed')
""", (position_id, market_id, ..., exit_price))
# Missing current_price! Causes assertion failure in tests.

# ✅ CORRECT - Include ALL columns
cur.execute("""
    INSERT INTO positions (
        position_id, market_id, ..., exit_price, current_price, status
    )
    VALUES (%s, %s, ..., %s, %s, 'closed')
""", (position_id, market_id, ..., exit_price, exit_price))
```

**Mistake 5: Using mocks instead of real database**

```python
# ❌ WRONG - Mock hides real database issues
@patch("precog.database.connection.get_connection")
def test_open_position(mock_get_connection):
    mock_get_connection.return_value.cursor.return_value.fetchone.return_value = {...}
    # Test passes but doesn't validate SQL syntax, constraints, or business_id logic!

# ✅ CORRECT - Use real database with fixtures
def test_open_position(clean_test_data, manager, position_params):
    result = manager.open_position(**position_params)
    # Validates SQL syntax, constraints, business_id generation, everything!
```

### Decision Tree: When to Update CRUD

```
Q: Did database schema change?
├─ NO → No CRUD updates needed
└─ YES → Continue

Q: Does change affect SCD Type 2 table?
├─ NO → Update CRUD for new columns (simpler workflow)
└─ YES → Continue (use full 5-step workflow)

Q: Which operations are affected?
├─ INSERT → Update to include new columns
├─ UPDATE → Update to include new columns
├─ SELECT → Update to return new columns
└─ SCD Type 2 versioning → Update UPDATE + INSERT pattern

Q: Did you update tests to verify changes?
├─ NO → STOP! Write integration tests first (Pattern 13)
└─ YES → Continue

Q: Did tests pass on first try?
├─ YES → Excellent! Proceed to documentation
└─ NO → Debug integration tests, fix CRUD, repeat

Q: Did you update documentation?
├─ NO → STOP! Update DATABASE_SCHEMA_SUMMARY, ADR-089
└─ YES → ✅ COMPLETE - Schema and CRUD synchronized
```

### Quick Reference: SCD Type 2 CRUD Patterns

| Operation | Pattern | row_current_ind | Business Key |
|-----------|---------|-----------------|--------------|
| **INSERT (new record)** | Single INSERT | Set to TRUE | Set from surrogate id |
| **UPDATE (new version)** | UPDATE old + INSERT new | Old→FALSE, New→TRUE | Reuse from old version |
| **DELETE (soft delete)** | UPDATE + INSERT | Old→FALSE, New→TRUE | Reuse from old version |
| **SELECT (current only)** | WHERE filter | Filter `= TRUE` | Any value |
| **SELECT (all versions)** | No filter | Any value | Group by business key |

### Real-World Impact: Position Manager Example

**Phase 1.5 Schema Migration (Migration 011):**
- Added `position_id` business key to positions table
- Required updates to 4 CRUD functions
- Caught 1 critical bug (missing current_price in close_position)
- 23 integration tests created, all passing
- Coverage: Position Manager 87.50%, CRUD operations 91.26%

**Without this workflow:**
- Bug would have gone undetected until production
- Tests would pass (mocks don't validate SQL)
- Runtime error: "column current_price does not exist"
- Emergency hotfix required

**With this workflow:**
- Bug caught during Step 4 (integration tests)
- Fixed in 5 minutes (added current_price to INSERT)
- High confidence in deployment

### Performance Considerations

**SCD Type 2 + Dual-Key Impact:**
- Storage: ~2-3x data size (multiple versions per record)
- Query speed: Fast with partial unique index (row_current_ind = TRUE)
- Write speed: 2x slower (UPDATE + INSERT instead of single UPDATE)

**Mitigation:**
- Archive old versions (row_current_ind = FALSE) after 90 days
- Separate "hot" (current) and "cold" (historical) partitions
- Index on (position_id, row_current_ind) for fast current version lookup

**When to Archive:**
- Phase 5+ (not Phase 1-2) - Premature optimization
- Only when query performance degrades (>100ms for current positions)
- Keep at least 30 days of history for debugging

### Cross-References

**Architecture Decisions:**
- **ADR-089:** Dual-Key Schema Pattern for SCD Type 2 Tables (comprehensive pattern documentation)
- **ADR-034:** SCD Type 2 for Slowly Changing Dimensions (original SCD Type 2 decision)
- **ADR-003:** Database Schema Versioning Strategy (migration workflow)
- **ADR-088:** Test Type Categories and Coverage Standards (test requirements)

**Development Patterns:**
- **Pattern 1:** Decimal Precision (use Decimal for all price columns)
- **Pattern 2:** Dual Versioning System (SCD Type 2 vs immutable versions)
- **Pattern 13:** Test Coverage Quality (NO mocks for database/CRUD, use real fixtures)

**Implementation Examples:**
- **Migration 011:** `src/precog/database/migrations/011_add_positions_dual_key.sql`
- **CRUD Operations:** `src/precog/database/crud_operations.py` (lines 800-1000: position CRUD functions)
- **Position Manager:** `src/precog/trading/position_manager.py` (business layer using CRUD)
- **Integration Tests:** `tests/unit/trading/test_position_manager.py` (23 tests)

**Testing Infrastructure:**
- **tests/conftest.py:** Fixture infrastructure (clean_test_data, db_pool, db_cursor)
- **TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md:** Why mocks hide bugs (Strategy Manager lesson)
- **TEST_REQUIREMENTS_COMPREHENSIVE_V1.0.md:** REQ-TEST-012 through REQ-TEST-019

**Documentation:**
- **DATABASE_SCHEMA_SUMMARY_V1.7.md:** Complete schema reference
- **SCHEMA_MIGRATION_WORKFLOW_V1.0.md:** Detailed workflow guide (to be created)

---

## Pattern Quick Reference

| Pattern | Enforcement | Key Command | Related ADR/REQ |
|---------|-------------|-------------|-----------------|
| **1. Decimal Precision** | Pre-commit hook (decimal-precision-check) | `git grep "float(" -- '*.py'` | ADR-002, REQ-SYS-003 |
| **2. Dual Versioning** | Code review | `python scripts/validate_schema_consistency.py` | ADR-018, ADR-019, ADR-020 |
| **3. Trade Attribution** | Code review | Manual verification | REQ-TRADE-001 |
| **4. Security** | Pre-commit hook (detect-private-key) | `git grep -E "password\s*=" -- '*.py'` | REQ-SEC-001 |
| **5. Cross-Platform** | Manual (code review) | `git grep -E "print\(.*[✅❌🔵]" -- '*.py'` | ADR-053 |
| **6. TypedDict** | Mypy (pre-push hook) | `python -m mypy .` | ADR-048, REQ-API-007 |
| **7. Educational Docstrings** | Code review | Manual verification | N/A |
| **8. Config Synchronization** | Manual (4-layer checklist) | `python scripts/validate_docs.py` | Pattern 8 checklist |
| **9. Warning Governance** | Pre-push hook (Step 5/5) | `python scripts/check_warning_debt.py` | ADR-054 |
| **10. Property Testing** | Pytest (pre-push hook) | `pytest tests/property/ -v` | ADR-074, REQ-TEST-008 |
| **11. Test Mocking** | Code review | `git grep "return_value\.load" tests/` | PR #19, PR #20 |
| **12. Test Fixture Security** | Code review | `git grep "tmp_path.*\.sql" tests/` | PR #79, PR #76, CWE-22 |
| **13. Test Coverage Quality** | Code review + test checklist | `git grep "@patch.*get_connection" tests/` | REQ-TEST-012 thru REQ-TEST-019, TDD_FAILURE_ROOT_CAUSE |
| **14. Schema Migration → CRUD** | Manual (5-step checklist) | `git log -- src/precog/database/migrations/` | ADR-089, ADR-034, ADR-003, Pattern 13 |

---

## Related Documentation

### Foundation Documents
- `docs/foundation/MASTER_REQUIREMENTS_V2.10.md` - All requirements
- `docs/foundation/ARCHITECTURE_DECISIONS_V2.10.md` - All ADRs (includes ADR-002, ADR-018-020, ADR-048, ADR-053-054, ADR-074)
- `docs/foundation/DEVELOPMENT_PHASES_V1.8.md` - Phase planning

### Implementation Guides
- `docs/guides/VERSIONING_GUIDE_V1.0.md` - Pattern 2 detailed implementation
- `docs/guides/CONFIGURATION_GUIDE_V3.1.md` - YAML configuration (Pattern 8)
- `docs/api-integration/KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md` - Pattern 1 quick reference

### Validation & Testing
- `docs/foundation/TESTING_STRATEGY_V2.0.md` - Comprehensive testing infrastructure
- `docs/testing/HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md` - Pattern 10 roadmap
- `scripts/validate_docs.py` - Pattern 5 sanitization example
- `scripts/validate_schema_consistency.py` - Pattern 1 & 2 validation
- `scripts/check_warning_debt.py` - Pattern 9 automation

### Security & Quality
- `docs/utility/SECURITY_REVIEW_CHECKLIST.md` - Pattern 4 detailed checklist
- `docs/utility/WARNING_DEBT_TRACKER.md` - Pattern 9 tracking
- `scripts/warning_baseline.json` - Pattern 9 baseline

### Code Examples
- `api_connectors/types.py` - Pattern 6 (17 TypedDict examples)
- `api_connectors/kalshi_auth.py` (lines 41-162) - Pattern 7 (excellent docstring examples)
- `tests/property/test_kelly_criterion_properties.py` - Pattern 10 (11 property tests)
- `tests/property/test_edge_detection_properties.py` - Pattern 10 (16 property tests)

---

**END OF DEVELOPMENT_PATTERNS_V1.3.md**

★ Insight ─────────────────────────────────────
This extraction serves two critical purposes:
1. **Context Optimization:** Reduces CLAUDE.md from 3,723 lines to ~1,800 lines (50% reduction), freeing up ~22,500 tokens (~11% of context budget)
2. **Improved Usability:** Patterns are now in a dedicated, searchable reference guide rather than buried in a 3,700-line master document

The preservation of all cross-references (ADRs, REQs, file paths) ensures developers can navigate from patterns to detailed implementation guides without information loss.

V1.3 Updates:
- Added Pattern 12 (Test Fixture Security Compliance) documenting project-relative test fixture pattern from PR #79, ensuring test fixtures comply with path traversal protection (CWE-22) implemented in PR #76.
- Added Pattern 13 (Test Coverage Quality - Mock Sparingly, Integrate Thoroughly) documenting critical lessons from TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md: when to use mocks vs real infrastructure, ALWAYS use conftest.py fixtures, 8 required test types, coverage standards, test review checklist. Prevents false confidence from mock-based tests that pass despite critical bugs (Strategy Manager: 17/17 tests passing with mocks, 13/17 failing with real database).
─────────────────────────────────────────────────
