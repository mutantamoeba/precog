# Precog Development Patterns Guide

---
**Version:** 1.2
**Created:** 2025-11-13
**Last Updated:** 2025-11-14
**Purpose:** Comprehensive reference for critical development patterns used throughout the Precog project
**Target Audience:** Developers and AI assistants working on any phase of the project
**Extracted From:** CLAUDE.md V1.15 (Section: Critical Patterns, Lines 930-2027)
**Status:** ✅ Current
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
13. [Pattern Quick Reference](#pattern-quick-reference)
14. [Related Documentation](#related-documentation)

---

## Introduction

This guide contains **11 critical development patterns** that must be followed throughout the Precog project. These patterns address:

- **Financial Precision:** Decimal-only arithmetic for sub-penny pricing
- **Data Versioning:** Dual versioning system for mutable vs. immutable data
- **Security:** Zero-tolerance for hardcoded credentials
- **Cross-Platform:** Windows/Linux compatibility
- **Type Safety:** TypedDict for compile-time validation
- **Testing:** Property-based testing for trading logic + robust test mocking
- **Configuration:** Multi-layer config synchronization
- **Quality:** Multi-source warning governance

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

**END OF DEVELOPMENT_PATTERNS_V1.0.md**

★ Insight ─────────────────────────────────────
This extraction serves two critical purposes:
1. **Context Optimization:** Reduces CLAUDE.md from 3,723 lines to ~1,800 lines (50% reduction), freeing up ~22,500 tokens (~11% of context budget)
2. **Improved Usability:** Patterns are now in a dedicated, searchable reference guide rather than buried in a 3,700-line master document

The preservation of all cross-references (ADRs, REQs, file paths) ensures developers can navigate from patterns to detailed implementation guides without information loss.
─────────────────────────────────────────────────
