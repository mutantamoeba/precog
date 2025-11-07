# Precog Project Context for Claude Code

---
**Version:** 1.6
**Created:** 2025-10-28
**Last Updated:** 2025-11-05
**Purpose:** Main source of truth for project context, architecture, and development workflow
**Target Audience:** Claude Code AI assistant in all sessions
**Changes in V1.6:**
- Changed session archiving from `docs/sessions/` (committed) to `_sessions/` (local-only, excluded from git)
- Added `docs/sessions/` to .gitignore to prevent repository bloat from session archives
- Updated Section 3 "Ending a Session" Step 0 to use local `_sessions/` folder
- Historical session archives (2025-10-28 through 2025-11-05) remain in git history at `docs/sessions/`
- Rationale: Session archives are ephemeral documentation; git commit messages + foundation docs provide permanent context
**Changes in V1.5:**
- Created `docs/guides/` folder for implementation guides (addresses documentation discoverability issue)
- Moved 5 implementation guides from supplementary/ and configuration/ to docs/guides/
- Updated Section 6 "Implementation Guides" to list all 5 guides (added CONFIGURATION_GUIDE and POSTGRESQL_SETUP_GUIDE)
- Updated MASTER_INDEX V2.8 → V2.9 (5 location changes)
- Aligns documentation structure with Section 6 references (previously referenced non-existent folder)
**Changes in V1.4:**
- Added session history archiving workflow to Section 3 (Ending a Session - Step 0)
- Extracted 7 historical SESSION_HANDOFF.md versions from git history to docs/sessions/
- Preserves full session history with date-stamped archives before overwriting
**Changes in V1.3:**
- Updated all version references to reflect Phase 1 API best practices documentation (PART 0-1 updates)
- MASTER_REQUIREMENTS V2.8 → V2.10 (added REQ-API-007, REQ-OBSERV-001, REQ-SEC-009, REQ-VALIDATION-004)
- ARCHITECTURE_DECISIONS V2.7 → V2.9 (added ADR-047 through ADR-052 for API integration best practices)
- MASTER_INDEX V2.6 → V2.8 (added PHASE_1_TEST_PLAN and PHASE_0.7_DEFERRED_TASKS)
- Updated Quick Reference and Documentation Structure sections with current document versions
**Changes in V1.2:**
- Added Deferred Tasks Workflow to Phase Completion Protocol Step 6 (Section 9)
- Documents multi-location strategy for tracking non-blocking tasks deferred to future phases
- Added numbering convention (DEF-001, etc.), priority levels, and documentation locations
- Updated Current Status for Phase 0.7 completion
- Updated references to DEVELOPMENT_PHASES V1.4
**Changes in V1.1:**
- Added Rule 6: Planning Future Work (Section 5)
- Added Status Field Usage Standards (Section 5)
- Added validation commands to Quick Reference (Section 10)
- Updated Phase Completion Protocol with validate_all.sh (Section 9)
- Updated Current Status for Phase 0.6c completion
---

## 🎯 What This Document Does

This is **THE single source of truth** for working on Precog. Read this file at the start of every session along with `SESSION_HANDOFF.md` to get fully caught up in <5 minutes.

**This document contains:**
- Project architecture and current status
- Critical patterns (Decimal precision, versioning, security)
- **Document cohesion and consistency guidelines** (CRITICAL)
- Development workflow and handoff process
- Common tasks and troubleshooting
- Quick reference to all documentation

**What you need to read each session:**
1. **CLAUDE.md** (this file) - Comprehensive project context
2. **SESSION_HANDOFF.md** - What happened recently, what's next

That's it! No need to hunt through multiple status documents.

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Current Status](#current-status)
3. [Session Handoff Workflow](#session-handoff-workflow)
4. [Critical Patterns](#critical-patterns)
5. [Document Cohesion & Consistency](#document-cohesion--consistency) ⚠️ **CRITICAL**
6. [Documentation Structure](#documentation-structure)
7. [Common Tasks](#common-tasks)
8. [Security Guidelines](#security-guidelines)
9. [Phase Completion Protocol](#phase-completion-protocol)
10. [Quick Reference](#quick-reference)

---

## 📖 Project Overview

### What is Precog?

**Precog** is a modular Python application that identifies and executes positive expected value (EV+) trading opportunities on prediction markets.

**How it works:**
1. Fetches live market prices from APIs (Kalshi, eventually Polymarket)
2. Calculates true win probabilities using versioned ML models
3. Identifies edges where market price < true probability
4. Executes trades automatically with risk management
5. Monitors positions with dynamic trailing stops
6. Exits strategically based on 10-condition priority hierarchy

**Initial Focus:** Kalshi platform, NFL/NCAAF markets
**Future Expansion:** Multiple sports, non-sports markets, multiple platforms

### Tech Stack

- **Language:** Python 3.12
- **Database:** PostgreSQL 15+ with `DECIMAL(10,4)` precision (CRITICAL)
- **ORM:** SQLAlchemy + psycopg2
- **Testing:** pytest (>80% coverage required)
- **Configuration:** YAML files + `.env` for secrets
- **CLI:** Typer framework
- **APIs:** Kalshi (RSA-PSS auth), ESPN, Balldontlie

### Key Principles

1. **Safety First:** Multiple layers of risk management, decimal precision
2. **Version Everything:** Immutable strategy and model versions for A/B testing
3. **Test Everything:** 80%+ coverage, comprehensive test suite
4. **Document Everything:** Every decision has ADR, every change tracked
5. **Keep Documents in Sync:** When requirements change, cascade updates through all affected docs
6. **Secure Everything:** Zero credentials in code, comprehensive security reviews

---

## 🚦 Current Status

### Phase Progress

**Current Phase:** Phase 1 (Database & API Connectivity)
**Phase 1 Status:** 50% complete

**✅ Completed:**
- **Phase 0:** Foundation & Documentation (100%)
- **Phase 0.5:** Foundation Enhancement - Versioning, trailing stops (100%)
- **Phase 0.6:** Documentation Correction & Security Hardening (100%)
- **Phase 0.6c:** Validation & Testing Infrastructure (100%)
- **Phase 0.7:** CI/CD Integration & Advanced Testing (100%)
- **Phase 1 (Partial):** Database schema V1.7, migrations 001-010, 66/66 tests passing (87% coverage)

**🔵 In Progress:**
- **Phase 1 (Remaining):** Kalshi API client, CLI commands, config loader

**📋 Planned:**
- **Phase 1.5:** Strategy Manager, Model Manager, Position Manager
- **Phase 2+:** See `docs/foundation/DEVELOPMENT_PHASES_V1.4.md`

### What Works Right Now

```bash
# Database connection and CRUD operations
python scripts/test_db_connection.py  # ✅ Works

# All tests
python -m pytest tests/ -v  # ✅ 66/66 passing, 87% coverage

# Database migrations
python scripts/apply_migration_v1.5.py  # ✅ Works

# Validation & Testing (Phase 0.6c)
./scripts/validate_quick.sh  # ✅ Works (~3 sec - code quality + docs)
./scripts/validate_all.sh    # ✅ Works (~60 sec - full validation)
./scripts/test_fast.sh       # ✅ Works (~5 sec - unit tests only)
./scripts/test_full.sh       # ✅ Works (~30 sec - all tests + coverage)
python scripts/validate_docs.py  # ✅ Works (documentation validation)
python scripts/fix_docs.py       # ✅ Works (auto-fix doc issues)
```

### What Doesn't Work Yet

```bash
# API integration - Not implemented
python main.py fetch-balance  # ❌ Not implemented

# CLI commands - Not implemented
python main.py fetch-markets  # ❌ Not implemented

# Trading - Not implemented (Phase 5)
python main.py execute-trades  # ❌ Not implemented
```

### Repository Structure

```
precog-repo/
├── ✅ config/                    # 7 YAML configuration files
├── ✅ database/                  # Schema, migrations, CRUD, seeds
│   ├── connection.py            # ✅ Complete
│   ├── crud_operations.py       # ✅ Complete (87% coverage)
│   ├── migrations/              # ✅ Migrations 001-010
│   └── seeds/                   # ✅ NFL team Elo data
├── ✅ docs/                      # Comprehensive documentation
│   ├── foundation/              # Core requirements, architecture
│   ├── guides/                  # Implementation guides
│   ├── supplementary/           # Detailed specifications
│   ├── sessions/                # Session handoffs
│   └── utility/                 # Process documents
├── ✅ tests/                     # Test suite (66 tests passing)
├── ✅ utils/                     # Utilities (logger.py complete)
├── ✅ scripts/                   # Database utility scripts
├── 🔵 api_connectors/           # NOT YET CREATED
├── 🔵 analytics/                # NOT YET CREATED
├── 🔵 trading/                  # NOT YET CREATED
├── 🔵 main.py                   # NOT YET CREATED
├── ✅ CLAUDE.md                 # This file!
└── ✅ SESSION_HANDOFF.md        # Current session status
```

---

## 🔄 Session Handoff Workflow

### Starting a New Session (5 minutes)

**Step 1: Read These Two Files**
1. **CLAUDE.md** (this file) - Project context and patterns
2. **SESSION_HANDOFF.md** - Recent work and immediate next steps

**Step 2: Check Current Phase**
- Review phase objectives in `docs/foundation/DEVELOPMENT_PHASES_V1.4.md` if needed
- Understand what's blocking vs. nice-to-have

**Step 2a: Verify Phase Prerequisites (MANDATORY)**
- **⚠️ BEFORE CONTINUING ANY PHASE WORK:** Check DEVELOPMENT_PHASES for current phase's Dependencies section
- Verify ALL "Requires Phase X: 100% complete" dependencies are met
- Check that previous phase is marked ✅ Complete in DEVELOPMENT_PHASES
- If dependencies NOT met: STOP and complete prerequisite phase first
- **⚠️ IF STARTING NEW PHASE:** Complete "Before Starting This Phase - TEST PLANNING CHECKLIST" from DEVELOPMENT_PHASES before writing any production code

**Example - Phase 1:**
```bash
# Phase 1 Dependencies: Requires Phase 0.7: 100% complete
# Check: Is Phase 0.7 marked ✅ Complete in DEVELOPMENT_PHASES?
# If NO → Must complete Phase 0.7 before starting Phase 1
# If YES → Can proceed with Phase 1 test planning checklist
```

**Step 3: Create Todo List**
```python
# Use TodoWrite tool to track progress
TodoWrite([
    {"content": "Implement Kalshi API auth", "status": "in_progress"},
    {"content": "Add rate limiting", "status": "pending"},
    {"content": "Write API tests", "status": "pending"}
])
```

### During Development

**Track Progress:**
- Update todo status frequently (mark completed immediately)
- Keep only ONE task as `in_progress` at a time
- Break complex tasks into smaller todos

**Before Committing Code:**

```bash
# 1. Run tests
python -m pytest tests/ -v

# 2. Check coverage
python -m pytest tests/ --cov=. --cov-report=term-missing

# 3. Security scan (CRITICAL)
git grep -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]" -- '*.py' '*.yaml' '*.sql'

# 4. Verify no .env file staged
git diff --cached --name-only | grep "\.env$"
```

**If ANY of these fail, DO NOT COMMIT until fixed.**

### Ending a Session (10 minutes)

**Step 0: Archive Current SESSION_HANDOFF.md**

```bash
# Archive current session handoff before overwriting (local-only, not committed)
cp SESSION_HANDOFF.md "_sessions/SESSION_HANDOFF_$(date +%Y-%m-%d).md"

# Note: _sessions/ is in .gitignore (local archives, not committed to git)
# Historical archives (2025-10-28 through 2025-11-05) remain in docs/sessions/ git history
```

**Why:** Preserves session context locally during active development. Archives are local-only (excluded from git) to prevent repository bloat. Git commit messages and foundation documents provide permanent context.

**Step 1: Update SESSION_HANDOFF.md**

Use this structure:
```markdown
# Session Handoff

**Session Date:** 2025-10-XX
**Phase:** Phase 1 (50% → 65%)
**Duration:** X hours

## This Session Completed
- ✅ Implemented Kalshi API authentication
- ✅ Added rate limiting (100 req/min)
- ✅ Created 15 API client tests (all passing)

## Previous Session Completed
- ✅ Database schema V1.7
- ✅ All migrations applied
- ✅ Tests passing (66/66)

## Current Status
- **Tests:** 81/81 passing (89% coverage)
- **Blockers:** None
- **Phase Progress:** Phase 1 at 65%

## Next Session Priorities
1. Implement CLI commands with Typer
2. Add config loader (YAML + .env)
3. Write integration tests (live demo API)

## Files Modified
- Created: `api_connectors/kalshi_client.py`
- Created: `tests/test_kalshi_client.py`
- Updated: `requirements.txt` (added requests)

## Notes
- API auth uses RSA-PSS (not HMAC-SHA256)
- All prices parsed as Decimal from *_dollars fields
- Rate limiter working correctly
```

**Step 2: Commit Changes**

```bash
git add .
git commit -m "Implement Kalshi API client with RSA-PSS auth

- Add api_connectors/kalshi_client.py
- Implement authentication, rate limiting, error handling
- Parse all prices as Decimal from *_dollars fields
- Add 15 unit tests with mock responses (all passing)
- Coverage: 87% → 89%

Phase 1: 50% → 65% complete

Co-authored-by: Claude <noreply@anthropic.com>"
```

**Step 3: Push to Remote**

```bash
git push origin main
```

### Updating CLAUDE.md (Only When Needed)

**Update this file ONLY when:**
- Major architecture changes (new patterns, tech stack changes)
- Phase transitions (Phase 1 → Phase 2)
- Critical patterns change (e.g., new security requirements)
- Status section needs major updates (>20% phase progress)

**Don't update for:**
- Every session (that's what SESSION_HANDOFF is for)
- Minor code changes
- Bug fixes
- Test additions

**When you do update:**
1. Increment version in header (1.0 → 1.1)
2. Add "Changes in vX.Y" section
3. Update relevant sections
4. Keep history at bottom

---

## 🏗️ Critical Patterns

### Pattern 1: Decimal Precision (NEVER USE FLOAT)

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

---

### Pattern 2: Dual Versioning System

**Two Different Patterns for Different Needs:**

#### Pattern A: SCD Type 2 (Frequently-Changing Data)

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

#### Pattern B: Immutable Versions (Strategies & Models)

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

---

### Pattern 3: Trade Attribution

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

### Pattern 4: Security (NO CREDENTIALS IN CODE)

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

### Pattern 5: Cross-Platform Compatibility (Windows/Linux)

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
    """Replace emoji with ASCII equivalents for Windows console."""
    replacements = {
        "✅": "[COMPLETE]",
        "🔵": "[PLANNED]",
        "🟡": "[IN PROGRESS]",
        "❌": "[FAILED]",
        "⚠️": "[WARNING]",
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

**Where Emoji is OK:**
- **Markdown files (.md)**: ✅ Yes (GitHub/VS Code render correctly)
- **Script `print()` output**: ❌ No (use ASCII equivalents)
- **Error messages**: ❌ No (may be printed to console - sanitize first)

**Reference:** `docs/foundation/ARCHITECTURE_DECISIONS_V2.10.md` (ADR-053), `scripts/validate_docs.py` (lines 57-82 for sanitization example)

---

### Pattern 6: TypedDict for API Response Types (ALWAYS)

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

### Pattern 7: Educational Docstrings (ALWAYS)

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
        - Pattern 1 in CLAUDE.md: Decimal Precision
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

## 📑 Document Cohesion & Consistency

⚠️ **CRITICAL SECTION** - Read carefully. Document drift causes bugs, confusion, and wasted time.

### Why This Matters

**The Problem:**
When you add a requirement, make an architecture decision, or complete a task, **multiple documents need updating**. Miss one, and documentation becomes inconsistent, leading to:
- Requirements in MASTER_REQUIREMENTS but not in REQUIREMENT_INDEX
- ADRs in ARCHITECTURE_DECISIONS but not in ADR_INDEX
- Phase tasks in DEVELOPMENT_PHASES but not aligned with MASTER_REQUIREMENTS
- Supplementary specs not referenced in foundation documents
- MASTER_INDEX listing documents that don't exist or have wrong names

**The Solution:**
Follow the **Update Cascade Rules** below. When you change one document, you MUST update its downstream dependencies.

---

### Document Dependency Map

**Understanding Upstream → Downstream Flow:**

```
┌─────────────────────────────────────────────────────────────┐
│                    MASTER_INDEX (V2.6)                       │
│          Master inventory of ALL documents                   │
│          Updates when ANY document added/removed/renamed     │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
┌───────▼───────┐        ┌───────▼────────┐
│ MASTER_       │        │ ARCHITECTURE_  │
│ REQUIREMENTS  │        │ DECISIONS      │
│ (V2.8)        │        │ (V2.7)         │
└───┬───────┬───┘        └───┬────────┬───┘
    │       │                │        │
    │       │                │        │
┌───▼───┐ ┌─▼─────────┐  ┌──▼────┐ ┌─▼────────┐
│ REQ   │ │ DEV       │  │ ADR   │ │ Supp     │
│ INDEX │ │ PHASES    │  │ INDEX │ │ Specs    │
│       │ │ (V1.3)    │  │       │ │          │
└───────┘ └───────────┘  └───────┘ └──────────┘
```

**Key Relationships:**

1. **MASTER_INDEX** depends on everything (always update last)
2. **MASTER_REQUIREMENTS** feeds into REQUIREMENT_INDEX and DEVELOPMENT_PHASES
3. **ARCHITECTURE_DECISIONS** feeds into ADR_INDEX and Supplementary Specs
4. **DEVELOPMENT_PHASES** must align with MASTER_REQUIREMENTS
5. **Supplementary Specs** must be referenced in MASTER_REQUIREMENTS or ARCHITECTURE_DECISIONS

---

### Update Cascade Rules

#### Rule 1: Adding a New Requirement

**When you add REQ-XXX-NNN to MASTER_REQUIREMENTS, you MUST:**

1. ✅ **Add to MASTER_REQUIREMENTS** (primary source)
   ```markdown
   **REQ-CLI-006: Market Fetch Command**
   - Phase: 2
   - Priority: Critical
   - Status: 🔵 Planned
   - Description: Fetch markets from Kalshi API with DECIMAL precision
   ```

2. ✅ **Add to REQUIREMENT_INDEX** (for searchability)
   ```markdown
   | REQ-CLI-006 | Market Fetch Command | 2 | Critical | 🔵 Planned |
   ```

3. ✅ **Check DEVELOPMENT_PHASES alignment**
   - Is this requirement listed in the phase deliverables?
   - If not, add it to the phase's task list

4. ✅ **Update MASTER_REQUIREMENTS version** (V2.8 → V2.9)

5. ✅ **Update MASTER_INDEX** (if filename changes)
   ```markdown
   | MASTER_REQUIREMENTS_V2.9.md | ✅ | v2.9 | ... | UPDATED from V2.8 |
   ```

**Example Commit Message:**
```
Add REQ-CLI-006 for market fetch command

- Add to MASTER_REQUIREMENTS V2.8 → V2.9
- Add to REQUIREMENT_INDEX
- Verify alignment with DEVELOPMENT_PHASES Phase 2
- Update MASTER_INDEX
```

---

#### Rule 2: Adding an Architecture Decision

**When you add ADR-XXX to ARCHITECTURE_DECISIONS, you MUST:**

1. ✅ **Add to ARCHITECTURE_DECISIONS** (primary source)
   ```markdown
   ### ADR-038: CLI Framework Choice

   **Decision #38**
   **Phase:** 1
   **Status:** ✅ Complete

   **Decision:** Use Typer for CLI framework

   **Rationale:** Type hints, auto-help, modern Python
   ```

2. ✅ **Add to ADR_INDEX** (for searchability)
   ```markdown
   | ADR-038 | CLI Framework (Typer) | Phase 1 | ✅ Complete | 🔴 Critical |
   ```

3. ✅ **Reference in related requirements**
   - Find related REQ-CLI-* requirements
   - Add cross-reference: "See ADR-038 for framework choice"

4. ✅ **Update ARCHITECTURE_DECISIONS version** (V2.7 → V2.8)

5. ✅ **Update ADR_INDEX version** (V1.1 → V1.2)

6. ✅ **Update MASTER_INDEX** (if filenames change)

**Example Commit Message:**
```
Add ADR-038 for CLI framework decision (Typer)

- Add to ARCHITECTURE_DECISIONS V2.7 → V2.8
- Add to ADR_INDEX V1.1 → V1.2
- Cross-reference in MASTER_REQUIREMENTS (REQ-CLI-001)
- Update MASTER_INDEX
```

---

#### Rule 3: Creating Supplementary Specification

**When you create a new supplementary spec, you MUST:**

1. ✅ **Create the spec file**
   - Use consistent naming: `FEATURE_NAME_SPEC_V1.0.md`
   - Remove phase numbers from filename
   - Include version header

2. ✅ **Reference in MASTER_REQUIREMENTS**
   ```markdown
   **REQ-EXEC-008: Advanced Walking Algorithm**
   ...
   **Reference:** See `supplementary/ADVANCED_EXECUTION_SPEC_V1.0.md` for detailed walking algorithm
   ```

3. ✅ **Reference in ARCHITECTURE_DECISIONS** (if applicable)
   ```markdown
   ### ADR-037: Order Walking Strategy
   ...
   **Reference:** See `supplementary/ADVANCED_EXECUTION_SPEC_V1.0.md`
   ```

4. ✅ **Add to MASTER_INDEX**
   ```markdown
   | ADVANCED_EXECUTION_SPEC_V1.0.md | ✅ | v1.0 | `/docs/supplementary/` | 5 | Phase 5b | 🟡 High | Order walking algorithms |
   ```

5. ✅ **Update version numbers** on referencing documents

**Example Commit Message:**
```
Add Advanced Execution Spec V1.0

- Create supplementary/ADVANCED_EXECUTION_SPEC_V1.0.md
- Reference in MASTER_REQUIREMENTS (REQ-EXEC-008)
- Reference in ARCHITECTURE_DECISIONS (ADR-037)
- Add to MASTER_INDEX
- Update MASTER_REQUIREMENTS V2.8 → V2.9
```

---

#### Rule 4: Renaming or Moving Documents

**When you rename/move a document, you MUST:**

1. ✅ **Use `git mv` to preserve history**
   ```bash
   git mv old_name.md new_name.md
   ```

2. ✅ **Update MASTER_INDEX**
   ```markdown
   | NEW_NAME_V1.0.md | ✅ | v1.0 | `/new/location/` | ... | **RENAMED** from old_name |
   ```

3. ✅ **Update ALL references in other documents**
   ```bash
   # Find all references
   grep -r "old_name.md" docs/

   # Update each reference to new_name.md
   ```

4. ✅ **Add note in renamed file header**
   ```markdown
   **Filename Updated:** Renamed from old_name.md to NEW_NAME_V1.0.md on 2025-10-XX
   ```

5. ✅ **Validate no broken links**
   ```bash
   python scripts/validate_doc_references.py
   ```

**Example Commit Message:**
```
Rename PHASE_5_EXIT_SPEC to EXIT_EVALUATION_SPEC_V1.0

- Rename with git mv (preserves history)
- Update all 7 references in foundation docs
- Update MASTER_INDEX with "RENAMED" note
- Add filename update note to file header
- Validate no broken links
```

---

#### Rule 5: Completing a Phase Task

**When you complete a task from DEVELOPMENT_PHASES, you MUST:**

1. ✅ **Mark complete in DEVELOPMENT_PHASES**
   ```markdown
   - [✅] Kalshi API client implementation
   ```

2. ✅ **Update related requirements status**
   ```markdown
   **REQ-API-001: Kalshi API Integration**
   - Status: ✅ Complete  # Changed from 🔵 Planned
   ```

3. ✅ **Update REQUIREMENT_INDEX status**
   ```markdown
   | REQ-API-001 | Kalshi API Integration | 1 | Critical | ✅ Complete |
   ```

4. ✅ **Update CLAUDE.md Current Status** (if major milestone)
   ```markdown
   **Phase 1 Status:** 50% → 65% complete
   ```

5. ✅ **Update SESSION_HANDOFF.md**
   ```markdown
   ## This Session Completed
   - ✅ Kalshi API client (REQ-API-001 complete)
   ```

**Example Commit Message:**
```
Complete REQ-API-001: Kalshi API client

- Mark complete in DEVELOPMENT_PHASES
- Update REQ-API-001 status to Complete in MASTER_REQUIREMENTS
- Update REQUIREMENT_INDEX
- Update CLAUDE.md (Phase 1: 50% → 65%)
- Update SESSION_HANDOFF
```

---

#### Rule 6: Planning Future Work

**When you identify future enhancements during implementation, you MUST:**

1. ✅ **Add to DEVELOPMENT_PHASES**
   - Create new Phase section (e.g., Phase 0.7) if logical grouping
   - OR add to existing future phase section
   - Mark all tasks as `[ ]` (not started)
   ```markdown
   ### Phase 0.7: CI/CD Integration (Future)
   **Status:** 🔵 Planned
   - [ ] GitHub Actions workflow
   - [ ] Codecov integration
   ```

2. ✅ **Add to MASTER_REQUIREMENTS** (if formal requirements)
   ```markdown
   **REQ-CICD-001: GitHub Actions Integration**
   - Phase: 0.7 (Future)
   - Priority: High
   - Status: 🔵 Planned  # Not ✅ Complete or 🟡 In Progress
   - Description: ...
   ```

3. ✅ **Add to REQUIREMENT_INDEX** (if requirements added)
   ```markdown
   | REQ-CICD-001 | GitHub Actions | 0.7 | High | 🔵 Planned |
   ```

4. ✅ **Add to ARCHITECTURE_DECISIONS** (if design decisions needed)
   ```markdown
   ### ADR-052: CI/CD Pipeline Strategy (Planned)

   **Decision #52**
   **Phase:** 0.7 (Future)
   **Status:** 🔵 Planned

   **Decision:** Use GitHub Actions for CI/CD

   **Rationale:** (high-level, can be expanded when implementing)

   **Implementation:** (To be detailed in Phase 0.7)

   **Related Requirements:** REQ-CICD-001
   ```

5. ✅ **Add to ADR_INDEX** (if ADRs added)
   ```markdown
   | ADR-052 | CI/CD Pipeline (GitHub Actions) | 0.7 | 🔵 Planned | 🟡 High |
   ```

6. ✅ **Add "Future Enhancements" section** to technical docs
   - In TESTING_STRATEGY, VALIDATION_LINTING_ARCHITECTURE, etc.
   - Describes what's coming next
   - References related REQs and ADRs

7. ✅ **Update version numbers** on all modified docs

8. ✅ **Update MASTER_INDEX** (if filenames change)

**When to use this rule:**
- 🎯 During implementation, you discover logical next steps
- 🎯 User mentions future work they want documented
- 🎯 You create infrastructure that enables future capabilities
- 🎯 Phase completion reveals obvious next phase

**Example trigger:**
"We just built validation infrastructure. This enables CI/CD integration in the future. Should document CI/CD as planned work now."

**Example Commit Message:**
```
Implement Phase 0.6c validation suite + document Phase 0.7 CI/CD plans

Implementation (Phase 0.6c):
- Add validation suite (validate_docs.py, validate_all.sh)
- ... (current work)

Future Planning (Phase 0.7):
- Add REQ-CICD-001 to MASTER_REQUIREMENTS V2.8 → V2.9 (🔵 Planned)
- Add ADR-052 to ARCHITECTURE_DECISIONS V2.8 (🔵 Planned)
- Add Phase 0.7 to DEVELOPMENT_PHASES V1.3 → V1.4
- Add "Future Enhancements" sections to technical docs
- Update indexes (REQUIREMENT_INDEX, ADR_INDEX)

Phase 0.6c: ✅ Complete
Phase 0.7: 🔵 Planned and documented
```

---

### Status Field Usage Standards

Use consistent status indicators across all documentation:

#### Requirement & ADR Status

| Status | Meaning | When to Use |
|--------|---------|-------------|
| 🔵 Planned | Documented but not started | Future work, identified but not implemented |
| 🟡 In Progress | Currently being worked on | Active development this session |
| ✅ Complete | Implemented and tested | Done, tests passing, committed |
| ⏸️ Paused | Started but blocked/deferred | Waiting on dependency or decision |
| ❌ Rejected | Considered but decided against | Document why NOT doing something |
| 📦 Archived | Was complete, now superseded | Old versions, deprecated approaches |

#### Phase Status

| Status | Meaning |
|--------|---------|
| 🔵 Planned | Phase not yet started |
| 🟡 In Progress | Phase currently active (XX% complete) |
| ✅ Complete | Phase 100% complete, all deliverables done |

#### Document Status (MASTER_INDEX)

| Status | Meaning |
|--------|---------|
| ✅ Current | Latest version, actively maintained |
| 🔵 Planned | Document listed but not yet created |
| 📦 Archived | Old version, moved to _archive/ |
| 🚧 Draft | Exists but incomplete/in revision |

**Consistency Rules:**

1. **Same status across paired documents**
   - REQ-API-001 is 🔵 Planned in MASTER_REQUIREMENTS
   - REQ-API-001 is 🔵 Planned in REQUIREMENT_INDEX
   - (Never: 🔵 in one, ✅ in other)

2. **Phase determines status**
   - Phase 0.6c work = ✅ Complete (this session)
   - Phase 0.7 work = 🔵 Planned (future)
   - Phase 1 in-progress work = 🟡 In Progress

3. **Status transitions**
   - 🔵 Planned → 🟡 In Progress (when starting work)
   - 🟡 In Progress → ✅ Complete (when done + tested)
   - ✅ Complete → 📦 Archived (when superseded)

4. **Never skip statuses**
   - ❌ BAD: 🔵 Planned → ✅ Complete (skip 🟡 In Progress)
   - ✅ GOOD: 🔵 Planned → 🟡 In Progress → ✅ Complete

---

### Consistency Validation Checklist

**Run this checklist BEFORE committing any documentation changes:**

#### Level 1: Quick Checks (2 minutes)

- [ ] **Cross-references valid?**
  ```bash
  # Check all .md references in foundation docs
  grep -r "\.md" docs/foundation/*.md | grep -v "^#"
  # Verify each reference exists
  ```

- [ ] **Version numbers consistent?**
  - Header version matches filename? (e.g., V2.8 in MASTER_REQUIREMENTS_V2.8.md)
  - All references use correct version?

- [ ] **MASTER_INDEX accurate?**
  - Document exists at listed location?
  - Version matches?
  - Status correct (✅ exists, 🔵 planned)?

#### Level 2: Requirement Consistency (5 minutes)

- [ ] **Requirements in both places?**
  ```bash
  # Extract REQ IDs from MASTER_REQUIREMENTS
  grep -E "REQ-[A-Z]+-[0-9]+" docs/foundation/MASTER_REQUIREMENTS*.md | sort -u

  # Compare with REQUIREMENT_INDEX
  grep -E "REQ-[A-Z]+-[0-9]+" docs/foundation/REQUIREMENT_INDEX.md | sort -u

  # Should match exactly
  ```

- [ ] **Requirements align with phases?**
  - Each Phase 1 requirement in DEVELOPMENT_PHASES Phase 1 section?
  - Each Phase 2 requirement in DEVELOPMENT_PHASES Phase 2 section?

- [ ] **Requirement statuses consistent?**
  - Same status in MASTER_REQUIREMENTS and REQUIREMENT_INDEX?
  - Completed requirements marked in DEVELOPMENT_PHASES?

#### Level 3: ADR Consistency (5 minutes)

- [ ] **ADRs in both places?**
  ```bash
  # Extract ADR numbers from ARCHITECTURE_DECISIONS
  grep -E "ADR-[0-9]+" docs/foundation/ARCHITECTURE_DECISIONS*.md | sort -u

  # Compare with ADR_INDEX
  grep -E "ADR-[0-9]+" docs/foundation/ADR_INDEX.md | sort -u

  # Should match exactly
  ```

- [ ] **ADRs sequentially numbered?**
  - No gaps (ADR-001, ADR-002, ADR-003... no missing numbers)
  - No duplicates

- [ ] **ADRs referenced where needed?**
  - Critical ADRs referenced in MASTER_REQUIREMENTS?
  - Related ADRs cross-referenced?

#### Level 4: Supplementary Spec Consistency (5 minutes)

- [ ] **All supplementary specs referenced?**
  ```bash
  # List all supplementary specs
  ls docs/supplementary/*.md

  # Check each is referenced in MASTER_REQUIREMENTS or ARCHITECTURE_DECISIONS
  for file in docs/supplementary/*.md; do
      basename="$(basename $file)"
      grep -r "$basename" docs/foundation/
  done
  ```

- [ ] **Specs match naming convention?**
  - Format: `FEATURE_NAME_SPEC_V1.0.md`
  - No phase numbers in filename
  - Version in filename matches header

- [ ] **Specs in MASTER_INDEX?**
  - All supplementary specs listed?
  - Correct location, version, status?

---

### Common Update Patterns (Examples)

#### Pattern 1: Adding a Complete Feature

**Scenario:** Adding CLI market fetch command

**Documents to Update (in order):**

1. **MASTER_REQUIREMENTS** (add requirement)
   ```markdown
   **REQ-CLI-006: Market Fetch Command**
   - Phase: 2
   - Priority: Critical
   - Status: 🔵 Planned
   ```

2. **REQUIREMENT_INDEX** (add to table)
   ```markdown
   | REQ-CLI-006 | Market Fetch Command | 2 | Critical | 🔵 Planned |
   ```

3. **DEVELOPMENT_PHASES** (add to Phase 2 tasks)
   ```markdown
   #### Phase 2: Football Market Data (Weeks 3-4)
   ...
   - [ ] CLI command: `main.py fetch-markets`
   ```

4. **ARCHITECTURE_DECISIONS** (if needed, add ADR)
   ```markdown
   ### ADR-039: Market Fetch Strategy
   ...
   ```

5. **ADR_INDEX** (if ADR added)
   ```markdown
   | ADR-039 | Market Fetch Strategy | 2 | 🔵 Planned | 🟡 High |
   ```

6. **Version bump** all modified docs
   - MASTER_REQUIREMENTS V2.8 → V2.9
   - ARCHITECTURE_DECISIONS V2.7 → V2.8 (if ADR added)
   - ADR_INDEX V1.1 → V1.2 (if ADR added)

7. **MASTER_INDEX** (if filenames changed)
   ```markdown
   | MASTER_REQUIREMENTS_V2.9.md | ✅ | v2.9 | ... | UPDATED from V2.8 |
   ```

8. **SESSION_HANDOFF** (document the changes)

**Commit Message:**
```
Add REQ-CLI-006 for market fetch command

Foundation Updates:
- Add REQ-CLI-006 to MASTER_REQUIREMENTS V2.8 → V2.9
- Add REQ-CLI-006 to REQUIREMENT_INDEX
- Add to DEVELOPMENT_PHASES Phase 2 tasks
- Add ADR-039 for fetch strategy to ARCHITECTURE_DECISIONS V2.7 → V2.8
- Add ADR-039 to ADR_INDEX V1.1 → V1.2
- Update MASTER_INDEX

Validates:
- ✅ Requirements consistent across docs
- ✅ ADRs properly indexed
- ✅ Phase tasks aligned
- ✅ All versions bumped
```

---

#### Pattern 2: Implementing and Completing a Feature

**Scenario:** Just finished implementing Kalshi API client

**Documents to Update (in order):**

1. **MASTER_REQUIREMENTS** (update status)
   ```markdown
   **REQ-API-001: Kalshi API Integration**
   - Status: ✅ Complete  # Was 🔵 Planned
   ```

2. **REQUIREMENT_INDEX** (update status)
   ```markdown
   | REQ-API-001 | Kalshi API Integration | 1 | Critical | ✅ Complete |
   ```

3. **DEVELOPMENT_PHASES** (mark complete)
   ```markdown
   #### Phase 1: Core Foundation
   **Weeks 2-4: Kalshi API Integration**
   - [✅] RSA-PSS authentication implementation  # Was [ ]
   - [✅] REST endpoints: markets, events, series, balance, positions, orders
   - [✅] Error handling and exponential backoff retry logic
   ```

4. **CLAUDE.md** (update status if major milestone)
   ```markdown
   **Phase 1 Status:** 50% → 75% complete  # Significant progress
   ```

5. **SESSION_HANDOFF** (document completion)
   ```markdown
   ## This Session Completed
   - ✅ REQ-API-001: Kalshi API client fully implemented
   - ✅ 15 tests added (all passing)
   - ✅ Coverage increased 87% → 92%
   ```

6. **Version bump** modified docs
   - MASTER_REQUIREMENTS V2.8 → V2.9
   - DEVELOPMENT_PHASES V1.3 → V1.4 (if significant changes)

7. **MASTER_INDEX** (if filenames changed)

**Commit Message:**
```
Complete REQ-API-001: Kalshi API client implementation

Implementation:
- Add api_connectors/kalshi_client.py
- Add tests/test_kalshi_client.py (15 tests)
- All prices use Decimal precision
- RSA-PSS authentication working
- Rate limiting (100 req/min) implemented

Documentation Updates:
- Update REQ-API-001 status to Complete in MASTER_REQUIREMENTS V2.8 → V2.9
- Update REQUIREMENT_INDEX status
- Mark Phase 1 Kalshi tasks complete in DEVELOPMENT_PHASES
- Update CLAUDE.md (Phase 1: 50% → 75%)
- Update SESSION_HANDOFF

Tests: 66/66 → 81/81 passing (87% → 92% coverage)
Phase 1: 50% → 75% complete
```

---

#### Pattern 3: Reorganizing Documentation

**Scenario:** Moving guides from `/supplementary/` to `/guides/` and renaming

**Documents to Update (in order):**

1. **Move files with git mv**
   ```bash
   git mv docs/supplementary/VERSIONING_GUIDE.md docs/guides/VERSIONING_GUIDE_V1.0.md
   git mv docs/supplementary/TRAILING_STOP_GUIDE.md docs/guides/TRAILING_STOP_GUIDE_V1.0.md
   ```

2. **Update file headers** (add rename note)
   ```markdown
   **Filename Updated:** Moved from supplementary/ to guides/ on 2025-10-28
   ```

3. **Find and update ALL references**
   ```bash
   # Find all references
   grep -r "supplementary/VERSIONING_GUIDE" docs/

   # Update each to: guides/VERSIONING_GUIDE_V1.0.md
   ```

4. **Update MASTER_INDEX**
   ```markdown
   | VERSIONING_GUIDE_V1.0.md | ✅ | v1.0 | `/docs/guides/` | ... | **MOVED** from /supplementary/ |
   ```

5. **Update MASTER_REQUIREMENTS** (references)
   ```markdown
   **Reference:** See `guides/VERSIONING_GUIDE_V1.0.md` for versioning patterns
   ```

6. **Validate no broken links**
   ```bash
   python scripts/validate_doc_references.py
   ```

7. **Version bump** all docs with references updated
   - MASTER_REQUIREMENTS V2.8 → V2.9
   - MASTER_INDEX V2.5 → V2.6

8. **SESSION_HANDOFF** (document reorganization)

**Commit Message:**
```
Reorganize guides: Move from supplementary to guides folder

File Operations:
- Move VERSIONING_GUIDE to guides/VERSIONING_GUIDE_V1.0.md
- Move TRAILING_STOP_GUIDE to guides/TRAILING_STOP_GUIDE_V1.0.md
- Move POSITION_MANAGEMENT_GUIDE to guides/POSITION_MANAGEMENT_GUIDE_V1.0.md

Documentation Updates:
- Update 12 references in MASTER_REQUIREMENTS V2.8 → V2.9
- Update 8 references in ARCHITECTURE_DECISIONS
- Update MASTER_INDEX V2.5 → V2.6 with new locations
- Add "MOVED" notes to file headers
- Validate all references (zero broken links)

Rationale: Separate implementation guides from supplementary specs
```

---

### Validation Script Template

**Create:** `scripts/validate_doc_consistency.py`

```python
"""
Validate document consistency across foundation documents.

Checks:
1. Requirements in both MASTER_REQUIREMENTS and REQUIREMENT_INDEX
2. ADRs in both ARCHITECTURE_DECISIONS and ADR_INDEX
3. All supplementary specs referenced
4. MASTER_INDEX accuracy
5. No broken document references
"""
import re
from pathlib import Path

def validate_requirements():
    """Validate requirement IDs match across documents."""
    # Extract REQ IDs from MASTER_REQUIREMENTS
    master_reqs = set()
    master_req_file = Path("docs/foundation/MASTER_REQUIREMENTS_V2.8.md")
    content = master_req_file.read_text()
    master_reqs = set(re.findall(r'REQ-[A-Z]+-\d+', content))

    # Extract REQ IDs from REQUIREMENT_INDEX
    index_reqs = set()
    index_file = Path("docs/foundation/REQUIREMENT_INDEX.md")
    content = index_file.read_text()
    index_reqs = set(re.findall(r'REQ-[A-Z]+-\d+', content))

    # Compare
    missing_in_index = master_reqs - index_reqs
    missing_in_master = index_reqs - master_reqs

    if missing_in_index:
        print(f"❌ {len(missing_in_index)} requirements in MASTER_REQUIREMENTS but not in REQUIREMENT_INDEX:")
        for req in sorted(missing_in_index):
            print(f"   - {req}")

    if missing_in_master:
        print(f"❌ {len(missing_in_master)} requirements in REQUIREMENT_INDEX but not in MASTER_REQUIREMENTS:")
        for req in sorted(missing_in_master):
            print(f"   - {req}")

    if not missing_in_index and not missing_in_master:
        print(f"✅ All {len(master_reqs)} requirements consistent")

    return len(missing_in_index) + len(missing_in_master) == 0

def validate_adrs():
    """Validate ADR numbers match across documents."""
    # Similar to validate_requirements
    # Extract from ARCHITECTURE_DECISIONS and ADR_INDEX
    # Compare sets
    pass

def validate_references():
    """Validate all .md references point to existing files."""
    # Find all references in foundation docs
    # Check each file exists
    pass

if __name__ == "__main__":
    print("Validating document consistency...\n")

    req_ok = validate_requirements()
    adr_ok = validate_adrs()
    ref_ok = validate_references()

    if req_ok and adr_ok and ref_ok:
        print("\n✅ All validation checks passed")
        exit(0)
    else:
        print("\n❌ Validation failed - fix issues above")
        exit(1)
```

**Run before every major commit:**
```bash
python scripts/validate_doc_consistency.py
```

---

### Summary: Document Consistency Workflow

**When making any documentation change:**

1. **Identify impact**: Which documents reference this?
2. **Update cascade**: Follow Update Cascade Rules for your change type
3. **Validate consistency**: Run consistency checklist
4. **Version bump**: Increment versions on all modified docs
5. **Update MASTER_INDEX**: Reflect any filename changes
6. **Validate links**: Run validation script
7. **Update SESSION_HANDOFF**: Document what you changed
8. **Commit atomically**: All related changes in one commit

**Key Principle:** Documentation is code. Treat it with the same rigor as your Python code. Every change must maintain consistency across the entire documentation set.

---

## 📚 Documentation Structure

### Quick Navigation

**Need project context?**
- **START HERE:** `CLAUDE.md` (this file)

**Need recent updates?**
- `SESSION_HANDOFF.md`

**Need requirements?**
- `docs/foundation/MASTER_REQUIREMENTS_V2.10.md`
- `docs/foundation/REQUIREMENT_INDEX.md`

**Need architecture decisions?**
- `docs/foundation/ARCHITECTURE_DECISIONS_V2.9.md`
- `docs/foundation/ADR_INDEX.md`

**Need phase information?**
- `docs/foundation/DEVELOPMENT_PHASES_V1.4.md`

**Need implementation details?**
- Database: `docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md`
- API: `docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md`
- Versioning: `docs/guides/VERSIONING_GUIDE_V1.0.md`
- Trailing Stops: `docs/guides/TRAILING_STOP_GUIDE_V1.0.md`
- Position Management: `docs/guides/POSITION_MANAGEMENT_GUIDE_V1.0.md`

**Need to find any document?**
- `docs/foundation/MASTER_INDEX_V2.8.md`

### Foundation Documents (Authoritative)

**Location:** `docs/foundation/`

1. **MASTER_INDEX_V2.8.md** - Complete document inventory
2. **MASTER_REQUIREMENTS_V2.10.md** - All requirements with REQ IDs
3. **ARCHITECTURE_DECISIONS_V2.9.md** - All ADRs (001-052)
4. **PROJECT_OVERVIEW_V1.3.md** - System architecture
5. **DEVELOPMENT_PHASES_V1.4.md** - Roadmap and phases
6. **REQUIREMENT_INDEX.md** - Searchable requirement catalog
7. **ADR_INDEX.md** - Searchable ADR catalog
8. **GLOSSARY.md** - Terminology reference

### Implementation Guides

**Location:** `docs/guides/`

1. **CONFIGURATION_GUIDE_V3.1.md** - YAML configuration reference (START HERE)
2. **VERSIONING_GUIDE_V1.0.md** - Strategy/model versioning
3. **TRAILING_STOP_GUIDE_V1.0.md** - Trailing stop implementation
4. **POSITION_MANAGEMENT_GUIDE_V1.0.md** - Position lifecycle
5. **POSTGRESQL_SETUP_GUIDE.md** - Database setup (Windows/Linux/Mac)

### API & Integration

**Location:** `docs/api-integration/`

1. **API_INTEGRATION_GUIDE_V2.0.md** - Kalshi/ESPN/Balldontlie APIs
2. **KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md** ⚠️ **CRITICAL - PRINT THIS**

### Database

**Location:** `docs/database/`

1. **DATABASE_SCHEMA_SUMMARY_V1.7.md** - Complete schema (25 tables)
2. **DATABASE_TABLES_REFERENCE.md** - Quick lookup

### Process & Utility

**Location:** `docs/utility/`

1. **Handoff_Protocol_V1.1.md** - Phase completion (8-step assessment)
2. **SECURITY_REVIEW_CHECKLIST.md** - Pre-commit security checks
3. **VERSION_HEADERS_GUIDE_V2.1.md** - Document versioning

---

## 🔧 Common Tasks

### Task 1: Implement New Feature

**Example: Add Kalshi API client**

```python
"""
Kalshi API Client

Handles authentication, rate limiting, and API requests.
ALL prices parsed as Decimal from *_dollars fields.

Reference: docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md
Related ADR: ADR-005 (RSA-PSS Authentication)
Related REQ: REQ-API-001 (Kalshi API Integration)
"""
from decimal import Decimal
import os
from typing import Dict
import requests

class KalshiClient:
    """Kalshi API client with RSA-PSS authentication."""

    def __init__(self):
        # ✅ Load from environment
        self.api_key = os.getenv('KALSHI_API_KEY')
        self.api_secret = os.getenv('KALSHI_API_SECRET')
        self.base_url = os.getenv('KALSHI_BASE_URL')

        if not all([self.api_key, self.api_secret, self.base_url]):
            raise ValueError("Kalshi credentials not found")

    def get_balance(self) -> Decimal:
        """Fetch account balance.

        Returns:
            Account balance as Decimal

        Raises:
            requests.HTTPError: If API request fails
        """
        response = self._make_request('/portfolio/balance')
        # ✅ Parse as Decimal
        return Decimal(str(response['balance_dollars']))
```

**Create tests:**
```python
# tests/test_kalshi_client.py
import pytest
from decimal import Decimal
from api_connectors.kalshi_client import KalshiClient

def test_get_balance_returns_decimal(mock_kalshi_api):
    """Verify balance is Decimal, not float."""
    client = KalshiClient()
    balance = client.get_balance()

    assert isinstance(balance, Decimal)
    assert balance == Decimal("1234.5678")
```

**Update documentation:**
1. Mark REQ-API-001 as complete
2. Update REQUIREMENT_INDEX
3. Update DEVELOPMENT_PHASES tasks
4. Update SESSION_HANDOFF

**Run tests:**
```bash
python -m pytest tests/test_kalshi_client.py -v
python -m pytest tests/ --cov=api_connectors
```

---

### Task 6: Validate Implementation Against Requirements (MANDATORY)

**WHY:** Prevent "implementation complete but requirements not met" gaps. This validation should run BEFORE marking any feature complete.

**When to run:**
- Before marking any REQ as ✅ Complete
- Before marking any phase deliverable as done
- After implementing significant functionality (API client, database layer, trading logic)

**Step 1: Identify Relevant Requirements**

```bash
# Find all requirements for current phase
grep "Phase: 1" docs/foundation/MASTER_REQUIREMENTS*.md

# Find all ADRs for current phase
grep "Phase:** 1" docs/foundation/ARCHITECTURE_DECISIONS*.md
```

**Step 2: Validate Each Requirement**

For each REQ-XXX-NNN in scope:

```markdown
**Validation Checklist:**

- [ ] **Requirement exists in code?**
  - Find implementing function/class
  - Verify functionality matches requirement description

- [ ] **Tests exist for requirement?**
  - Search tests for requirement coverage
  - Verify all requirement scenarios tested

- [ ] **ADRs followed?**
  - Check implementation matches architectural decisions
  - Verify no deviations without documented reason

- [ ] **Documentation updated?**
  - Requirement marked complete in MASTER_REQUIREMENTS
  - REQUIREMENT_INDEX updated
  - DEVELOPMENT_PHASES task marked complete
```

**Step 3: Run Validation Commands**

```bash
# 1. Check requirement coverage
python scripts/validate_requirements_coverage.py  # Phase 0.8 future task

# 2. Verify all tests passing
python -m pytest tests/ -v

# 3. Check coverage threshold
python -m pytest tests/ --cov=api_connectors --cov-fail-under=80

# 4. Verify type safety
python -m mypy api_connectors/

# 5. Check code quality
python -m ruff check .
```

**Example: Validating REQ-API-001 (Kalshi API Integration)**

```markdown
**REQ-API-001 Validation:**

✅ **Implementation exists:**
- File: api_connectors/kalshi_client.py
- Class: KalshiClient
- Methods: get_markets(), get_positions(), get_balance(), etc.

✅ **Tests exist:**
- File: tests/unit/api_connectors/test_kalshi_client.py
- Coverage: 27/27 tests passing (87.24% coverage)
- Scenarios tested:
  - [x] RSA-PSS authentication
  - [x] Rate limiting (100 req/min)
  - [x] Exponential backoff
  - [x] Decimal price conversion
  - [x] Error handling (4xx, 5xx)
  - [x] TypedDict return types

✅ **ADRs followed:**
- ADR-002: Decimal precision ✅ (all prices use Decimal)
- ADR-047: RSA-PSS authentication ✅ (implemented in kalshi_auth.py)
- ADR-048: Rate limiting ✅ (100 req/min with token bucket)
- ADR-049: Exponential backoff ✅ (max 3 retries, 1s/2s/4s delays)
- ADR-050: TypedDict responses ✅ (17 TypedDict classes in types.py)

✅ **Documentation updated:**
- MASTER_REQUIREMENTS V2.10: REQ-API-001 status = ✅ Complete
- REQUIREMENT_INDEX: REQ-API-001 status = ✅ Complete
- DEVELOPMENT_PHASES V1.4: Phase 1 API tasks marked complete

**RESULT:** REQ-API-001 VALIDATED ✅
```

**Step 4: Identify Gaps**

If validation finds gaps:

```markdown
**Gap Identified:**
- **Requirement:** REQ-API-007 (Retry-After header handling)
- **Status:** Implemented but not tested
- **Gap:** No test for 429 error with Retry-After header
- **Action:** Add test_handle_429_with_retry_after() to test suite
- **Priority:** 🔴 Critical (must fix before marking complete)
```

**Step 5: Document Validation**

Add to SESSION_HANDOFF.md:

```markdown
## Implementation Validation

**Requirements Validated:**
- ✅ REQ-API-001: Kalshi API Integration
- ✅ REQ-API-002: RSA-PSS Authentication
- ✅ REQ-API-003: Rate Limiting
- ⚠️ REQ-API-007: Retry-After handling (test gap identified)

**Gaps Found:** 1 (REQ-API-007 test coverage)
**Gaps Resolved:** 1 (added test_handle_429_with_retry_after)

**Validation Status:** ✅ PASS (all requirements met)
```

**Reference:**
- MASTER_REQUIREMENTS_V2.10.md - All requirements
- ARCHITECTURE_DECISIONS_V2.10.md - All ADRs
- DEVELOPMENT_PHASES_V1.4.md - Phase deliverables
- Phase Completion Protocol (Section 9) - 8-step assessment

**Automation (Future - Phase 0.8):**

Create `scripts/validate_requirements_coverage.py` to automate validation:

```python
"""
Validate all requirements have implementation and tests.

Checks:
1. Each REQ-XXX-NNN in MASTER_REQUIREMENTS has:
   - Implementation (code file reference)
   - Tests (test file with coverage)
   - Documentation (marked complete when done)
"""
```

---

## 🔒 Security Guidelines

### Pre-Commit Security Scan (MANDATORY)

**Run BEFORE EVERY COMMIT:**

```bash
# 1. Search for hardcoded credentials
git grep -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]" -- '*.py' '*.yaml' '*.sql'

# 2. Check for connection strings with passwords
git grep -E "(postgres://|mysql://).*:.*@"

# 3. Verify .env not staged
git diff --cached --name-only | grep "\.env$"

# 4. Run tests
python -m pytest tests/ -v
```

**If ANY fail, DO NOT COMMIT until fixed.**

### What NEVER to Commit

**Files:**
- `.env` (only `.env.template` allowed)
- `_keys/*` (private keys, certificates)
- `*.pem`, `*.key`, `*.p12`, `*.pfx`
- `*.dump`, `*.sql.bak` (database backups with data)

**Patterns:**
```python
# ❌ NEVER
password = "mypassword"
api_key = "sk_live_abc123"
```

### Security Checklist Document

**Full checklist:** `docs/utility/SECURITY_REVIEW_CHECKLIST.md`

---

## 🎯 Phase Completion Protocol

**At the end of EVERY phase**, run this **8-Step Assessment** (~40 minutes total):

---

### Step 1: Deliverable Completeness (10 min)

- [ ] All planned documents for phase created?
- [ ] All planned code modules implemented?
- [ ] All documents have correct version headers?
- [ ] All documents have correct filenames (with versions)?
- [ ] All cross-references working?
- [ ] All code examples tested?
- [ ] All tests written and passing?

**Output:** List of deliverables with ✅/❌ status

---

### Step 2: Internal Consistency (5 min)

- [ ] Terminology consistent across all docs? (check GLOSSARY)
- [ ] Technical details match? (e.g., decimal pricing everywhere)
- [ ] Design decisions aligned?
- [ ] No contradictions between documents?
- [ ] Version numbers logical and sequential?
- [ ] Requirements and implementation match?

**Output:** List of any inconsistencies found + resolution plan

---

### Step 3: Dependency Verification (5 min)

- [ ] All document cross-references valid?
- [ ] All external dependencies identified and documented?
- [ ] Next phase blockers identified?
- [ ] API contracts documented?
- [ ] Data flow diagrams current?
- [ ] All imports in code resolve correctly?

**Output:** Dependency map with any missing items flagged

---

### Step 4: Quality Standards (5 min)

- [ ] Spell check completed on all docs?
- [ ] Grammar check completed?
- [ ] Format consistency (headers, bullets, tables)?
- [ ] Code syntax highlighting correct in docs?
- [ ] All links working (no 404s)?
- [ ] Code follows project style (type hints, docstrings)?

**Output:** Quality checklist with pass/fail

---

### Step 5: Testing & Validation (3 min)

- [ ] All tests passing? (`pytest tests/ -v`)
- [ ] Coverage meets threshold? (>80%)
- [ ] Sample data provided where relevant?
- [ ] Configuration examples included?
- [ ] Error handling documented and tested?
- [ ] Edge cases identified and tested?

**Output:** Test summary with coverage percentage

---

### Step 6: Gaps & Risks (2 min)

- [ ] Technical debt documented?
- [ ] Known issues logged with severity?
- [ ] Future improvements identified?
- [ ] Risk mitigation strategies noted?
- [ ] Performance concerns documented?
- [ ] **Deferred tasks documented?** (see Deferred Tasks Workflow below)

**Output:** Risk register with mitigation plans

#### Deferred Tasks Workflow

**When to create a deferred tasks document:**
- Phase identified tasks that are **important but not blocking** for next phase
- Tasks would take >2 hours total implementation time
- Tasks are infrastructure/tooling improvements (not core features)

**Multi-Location Documentation Strategy:**

1. **Create detailed document in utility/**
   - Filename: `PHASE_N.N_DEFERRED_TASKS_V1.0.md`
   - Include: Task IDs (DEF-001, etc.), rationale, implementation details, timeline, success metrics
   - Example: `docs/utility/PHASE_0.7_DEFERRED_TASKS_V1.0.md`

2. **Add summary to DEVELOPMENT_PHASES**
   - Add "Deferred Tasks" subsection at end of phase (before phase separator)
   - List high-priority vs. low-priority tasks
   - Include task IDs, time estimates, rationale
   - Reference detailed document: `📋 Detailed Documentation: docs/utility/PHASE_N.N_DEFERRED_TASKS_V1.0.md`

3. **Update MASTER_INDEX**
   - Add entry for deferred tasks document
   - Category: Utility document

4. **Optional: Promote critical tasks to requirements**
   - If task is critical infrastructure (pre-commit hooks, branch protection), consider adding REQ-TOOL-* IDs
   - Only do this if task will definitely be implemented in next 1-2 phases

**Deferred Task Numbering Convention:**
- `DEF-001`, `DEF-002`, etc. (sequential within phase)
- Phase-specific (Phase 0.7 deferred tasks: DEF-001 through DEF-007)

**Priority Levels:**
- 🟡 **High:** Should be implemented in next phase (Phase 0.8)
- 🟢 **Medium:** Implement within 2-3 phases
- 🔵 **Low:** Nice-to-have, implement as time allows

**Example Deferred Tasks:**
- Pre-commit hooks (prevents CI failures locally)
- Pre-push hooks (catches issues before CI)
- Branch protection rules (enforces PR workflow)
- Line ending edge cases (cosmetic CI issues)
- Additional security checks (non-blocking)

**When NOT to defer:**
- Blocking issues (prevents next phase from starting)
- Security vulnerabilities (must fix immediately)
- Data corruption risks (must fix immediately)
- Core feature requirements (belongs in phase, not deferred)

---

### Step 7: Archive & Version Management (5 min)

- [ ] Old document versions archived to `_archive/`?
- [ ] MASTER_INDEX updated with new versions?
- [ ] REQUIREMENT_INDEX updated (if requirements changed)?
- [ ] ADR_INDEX updated (if ADRs added)?
- [ ] DEVELOPMENT_PHASES updated (tasks marked complete)?
- [ ] All version numbers incremented correctly?

**Output:** Version audit report

---

### Step 8: Security Review (5 min) ⚠️ **CRITICAL**

**Hardcoded Credentials Check:**
```bash
# Search for hardcoded passwords, API keys, tokens
git grep -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]" -- '*.py' '*.yaml' '*.sql'

# Search for connection strings with embedded passwords
git grep -E "(postgres://|mysql://).*:.*@" -- '*'
```

**Expected Result:** No matches (or only `os.getenv()` lines)

**Manual Checklist:**
- [ ] No hardcoded passwords in source code?
- [ ] No API keys in configuration files?
- [ ] All credentials loaded from environment variables?
- [ ] `.env` file in `.gitignore` (not committed)?
- [ ] `_keys/` folder in `.gitignore`?
- [ ] No sensitive files in git history?
- [ ] All scripts use `os.getenv()` for credentials?

**If ANY security issues found:**
1. ⚠️ **STOP immediately** - Do NOT proceed to next phase
2. Fix all security issues
3. Rotate compromised credentials
4. Re-run security scan
5. Update `.gitignore` if needed

**Output:** Security scan report with ✅ PASS or ❌ FAIL + remediation

---

### Step 8a: Performance Profiling (Phase 5+ Only) ⚡ **OPTIONAL**

**When to profile:**
- **Phase 5+ ONLY:** Trading execution, order walking, position monitoring
- **NOT Phase 1-4:** Infrastructure, data processing, API integration

**Why defer optimization:**
- "Make it work, make it right, make it fast" - in that order
- Premature optimization wastes time on wrong bottlenecks
- Phase 1-4 focus: Correctness, type safety, test coverage
- Phase 5+ focus: Speed (when trading performance matters)

**Profiling Tools:**
```bash
# 1. Profile critical trading paths with cProfile
python -m cProfile -o profile.stats main.py execute-trades

# 2. Visualize with snakeviz (install: pip install snakeviz)
snakeviz profile.stats

# 3. Look for hotspots (functions taking >10% total time)
python -m pstats profile.stats
>>> sort time
>>> stats 20
```

**Only optimize if:**
- [ ] Bottleneck identified (single function >10% total execution time)
- [ ] Impacts trading performance (missed opportunities, slow exits)
- [ ] Simple optimization available (caching, vectorization, batch processing)
- [ ] Optimization doesn't sacrifice correctness or readability

**Common optimizations (Phase 5+):**
- **Caching:** Memoize expensive calculations (Elo ratings, model features)
- **Vectorization:** Use NumPy/Pandas for batch operations
- **Database:** Add indexes on frequently queried columns
- **API:** Batch requests instead of individual calls
- **WebSocket:** Use for live data instead of polling

**What NOT to optimize:**
- Database connection pooling (Phase 1-4: single connection is fine)
- API rate limiting (Phase 1-4: 100 req/min is sufficient)
- Code formatting/linting (zero performance impact)
- Test execution time (unless >5 minutes)

**Example Decision Matrix:**

| Scenario | Phase 1-4 | Phase 5+ | Optimize? |
|----------|-----------|----------|-----------|
| API request takes 200ms | ✅ OK | ✅ OK | ❌ No - network latency normal |
| Database query takes 50ms | ✅ OK | ✅ OK | ❌ No - reasonable for complex query |
| Model prediction takes 2s | ✅ OK | ⚠️ Slow | ✅ Yes - could miss trade opportunities |
| Order execution takes 500ms | N/A | ⚠️ Slow | ✅ Yes - price may move in 500ms |
| Position check takes 100ms | ✅ OK | ⚠️ Slow | ✅ Yes - runs every second in Phase 5 |

**Output:** Performance profile report with optimization recommendations (Phase 5+ only)

**Reference:**
- ADR-TBD (Performance Optimization Strategy) - Phase 5+
- "Premature optimization is the root of all evil" - Donald Knuth

---

### Assessment Output

**Create:** `docs/phase-completion/PHASE_N_COMPLETION_REPORT.md`

**Template:**
```markdown
# Phase N Completion Report

**Phase:** Phase N - [Name]
**Assessment Date:** YYYY-MM-DD
**Assessed By:** [Name/Claude]
**Status:** ✅ PASS / ⚠️ PASS WITH ISSUES / ❌ FAIL

---

## Assessment Summary

| Step | Status | Issues | Notes |
|------|--------|--------|-------|
| 1. Deliverable Completeness | ✅ | 0 | All deliverables complete |
| 2. Internal Consistency | ✅ | 0 | No contradictions found |
| 3. Dependency Verification | ✅ | 0 | All dependencies documented |
| 4. Quality Standards | ✅ | 0 | Quality checks passed |
| 5. Testing & Validation | ✅ | 0 | 66/66 tests passing, 87% coverage |
| 6. Gaps & Risks | ✅ | 2 | 2 minor risks documented |
| 7. Archive & Version Management | ✅ | 0 | All versions updated |
| 8. Security Review | ✅ | 0 | No credentials in code |

---

## Detailed Findings

### Step 1: Deliverable Completeness
[Details...]

### Step 2: Internal Consistency
[Details...]

[... continue for all 8 steps ...]

---

## Known Issues & Risks

1. **[Issue name]** (Severity: Low/Medium/High)
   - **Description:** [...]
   - **Impact:** [...]
   - **Mitigation:** [...]

---

## Recommendation

☐ **APPROVE** - Proceed to next phase
☐ **APPROVE WITH CONDITIONS** - Proceed with noted issues tracked
☐ **REJECT** - Address critical issues before proceeding

**Next Phase Prerequisites:**
- [List any prerequisites for starting next phase]

---

**Sign-off:** [Name] - [Date]
```

---

### Quick Completion Checklist

**Use this for rapid end-of-session validation (not full phase completion):**

- [ ] Tests passing?
- [ ] Security scan clean?
- [ ] SESSION_HANDOFF.md updated?
- [ ] CLAUDE.md updated (if major progress)?
- [ ] All new files committed?
- [ ] No hardcoded credentials?

**Time:** ~5 minutes

---

## 📎 Quick Reference

### Essential Reading Order

**Every Session:**
1. `CLAUDE.md` (this file)
2. `SESSION_HANDOFF.md`

**When Starting Phase:**
3. `docs/foundation/DEVELOPMENT_PHASES_V1.4.md`

**When Implementing:**
4. Relevant guides from `docs/guides/`
5. Relevant specs from `docs/supplementary/`

### Key Commands

```bash
# Validation & Testing (Phase 0.6c)
./scripts/validate_all.sh      # Complete validation (60s) - run before commits
./scripts/validate_quick.sh    # Fast validation (3s) - run during development
./scripts/test_full.sh         # All tests + coverage (30s)
./scripts/test_fast.sh         # Unit tests only (5s)

# Code Quality
ruff check .           # Linting
ruff check --fix .     # Linting with auto-fix
ruff format .          # Code formatting
mypy .                 # Type checking

# Documentation
python scripts/validate_docs.py  # Doc consistency validation
python scripts/fix_docs.py       # Auto-fix doc issues

# Testing (direct pytest)
pytest tests/ -v                              # All tests
pytest tests/unit/ -v                         # Unit tests only
pytest --cov=. --cov-report=html             # With coverage

# Database
python scripts/test_db_connection.py  # Test connection

# Security
git grep -E "password\s*=" -- '*.py'  # Scan for hardcoded credentials
```

### Critical References

**Decimal Precision:**
- `docs/api-integration/KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md`
- ADR-002 in ARCHITECTURE_DECISIONS

**Versioning:**
- `docs/guides/VERSIONING_GUIDE_V1.0.md`
- ADR-018, ADR-019, ADR-020 in ARCHITECTURE_DECISIONS

**Security:**
- `docs/utility/SECURITY_REVIEW_CHECKLIST.md`
- Pre-commit scan commands above

**Database:**
- `docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md`
- `docs/database/DATABASE_TABLES_REFERENCE.md`

**API Integration:**
- `docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md`

**Validation & Testing (Phase 0.6c):**
- `docs/foundation/TESTING_STRATEGY_V2.0.md` - Comprehensive testing infrastructure
- `docs/foundation/VALIDATION_LINTING_ARCHITECTURE_V1.0.md` - Code quality & doc validation
- `pyproject.toml` - Ruff, mypy, pytest configuration
- `scripts/validate_all.sh` - Complete validation suite

**Document Consistency:**
- Section 5 above: Document Cohesion & Consistency
- Rule 6: Planning Future Work
- Status Field Usage Standards
- Update Cascade Rules

---

## 🚨 Common Mistakes to Avoid

### ❌ NEVER Do These

1. **Use float for prices:** `price = 0.4975` ❌
2. **Modify immutable configs:** `strategy.config = {...}` ❌
3. **Query without row_current_ind:** `query(Position).all()` ❌
4. **Hardcode credentials:** `password = "..."` ❌
5. **Skip tests:** `git commit --no-verify` ❌
6. **Commit without security scan** ❌
7. **Update one doc without updating related docs** ❌
8. **Add requirement without updating REQUIREMENT_INDEX** ❌
9. **Add ADR without updating ADR_INDEX** ❌
10. **Rename file without updating all references** ❌

### ✅ ALWAYS Do These

1. **Use Decimal for prices:** `price = Decimal("0.4975")` ✅
2. **Create new version for config changes:** `v1.1 = Strategy(...)` ✅
3. **Filter by row_current_ind:** `filter(row_current_ind == True)` ✅
4. **Use environment variables:** `os.getenv('PASSWORD')` ✅
5. **Run tests before commit:** `pytest tests/ -v` ✅
6. **Run security scan before commit** ✅
7. **Follow Update Cascade Rules when changing docs** ✅
8. **Update REQUIREMENT_INDEX when adding REQ** ✅
9. **Update ADR_INDEX when adding ADR** ✅
10. **Update all references when renaming files** ✅

---

## 🔄 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.6 | 2025-11-05 | Changed session archiving from docs/sessions/ (committed) to _sessions/ (local-only); added docs/sessions/ to .gitignore; updated Section 3 Step 0 workflow; prevents repository bloat while preserving local context |
| 1.5 | 2025-11-05 | Created docs/guides/ folder and moved 5 implementation guides (CONFIGURATION, VERSIONING, TRAILING_STOP, POSITION_MANAGEMENT, POSTGRESQL_SETUP); updated Section 6 and MASTER_INDEX V2.8→V2.9; aligns docs structure with Section 6 references; addresses discoverability issue |
| 1.4 | 2025-11-05 | Added session history archiving workflow (Section 3 Step 0); extracted 7 historical SESSION_HANDOFF.md versions from git history to docs/sessions/; preserves full session history with date-stamped archives |
| 1.3 | 2025-11-04 | Updated all version references: MASTER_REQUIREMENTS V2.8→V2.10, ARCHITECTURE_DECISIONS V2.7→V2.9, MASTER_INDEX V2.6→V2.8; reflects Phase 1 API best practices documentation (ADR-047 through ADR-052, REQ-API-007, REQ-OBSERV-001, REQ-SEC-009, REQ-VALIDATION-004) |
| 1.2 | 2025-10-31 | Added Deferred Tasks Workflow to Phase Completion Protocol; multi-location documentation strategy; updated for Phase 0.7 completion; updated references to DEVELOPMENT_PHASES V1.4 |
| 1.1 | 2025-10-29 | Added Rule 6: Planning Future Work; Status Field Usage Standards; validation commands to Quick Reference; updated Phase Completion Protocol with validate_all.sh; Phase 0.6c completion updates |
| 1.0 | 2025-10-28 | Initial creation - Streamlined handoff workflow, added comprehensive Document Cohesion & Consistency section, removed PROJECT_STATUS and DOCUMENT_MAINTENANCE_LOG overhead, fixed API_INTEGRATION_GUIDE reference to V2.0 |

---

## 📋 Summary: Your Session Workflow

**Start Session (5 min):**
1. Read `CLAUDE.md` (this file)
2. Read `SESSION_HANDOFF.md`
3. Create TodoList

**During Session:**
1. Follow critical patterns (Decimal, Versioning, Security)
2. Follow Document Cohesion rules when updating docs
3. Write tests (>80% coverage)
4. Update todos frequently

**Before Commit:**
1. Run tests: `pytest tests/ -v`
2. Run security scan: `git grep "password\s*=" '*.py'`
3. **Run consistency validation if docs changed**
4. Check coverage: `pytest --cov`

**End Session (10 min):**
0. Archive `SESSION_HANDOFF.md` to `docs/sessions/` (preserves history)
1. Update `SESSION_HANDOFF.md`
2. Commit with descriptive message (list all doc updates)
3. Push to remote

**Phase Complete:**
1. Run 8-step assessment
2. Create completion report
3. Update `CLAUDE.md` status if major changes

---

**That's it! Two files to read, clear patterns to follow, strong document cohesion discipline, comprehensive security checks. You're ready to code.**

---

**END OF CLAUDE.md V1.6**
- always use descriptive variable names
- Always document deferred tasks appropriately in requirements, architural, and project development phases documentation