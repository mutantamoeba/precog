# Claude Code Instructions - Errata and Corrections

**Date:** 2025-10-17
**File:** CLAUDE_CODE_INSTRUCTIONS.md
**Status:** Discrepancies noted for Phase 1 reference

---

## Purpose

This document notes discrepancies and outdated information in `CLAUDE_CODE_INSTRUCTIONS.md` that should be corrected before Phase 1. The instructions file was helpful for Phase 0 completion, but has some inconsistencies with the actual project configuration.

---

## Discrepancies Found

### 1. Environment Variable Names (CRITICAL)

**Location:** Section "Step 7.4: Create .env.template" (lines ~1288-1330)

**Issue:** Shows outdated/incorrect Kalshi authentication variable names

**CLAUDE_CODE_INSTRUCTIONS shows:**
```bash
KALSHI_DEMO_KEY_ID=your_demo_key_id_here
KALSHI_DEMO_KEYFILE=/path/to/demo_private_key.pem
KALSHI_PROD_KEY_ID=your_prod_key_id_here
KALSHI_PROD_KEYFILE=/path/to/prod_private_key.pem
```

**ACTUAL in config/env.template (CORRECT):**
```bash
KALSHI_API_KEY=your_kalshi_api_key_here
KALSHI_API_SECRET=your_kalshi_api_secret_here
KALSHI_BASE_URL=https://demo-api.kalshi.co  # Use demo for testing
# KALSHI_BASE_URL=https://trading-api.kalshi.com  # Production URL
```

**Impact:** High - Would cause authentication failures
**Status:** ✅ Fixed in all actual docs (Master Requirements v2.3, Configuration Guide v3.0, env.template)
**Action:** Use actual `config/env.template` as source of truth, ignore CLAUDE_CODE_INSTRUCTIONS version

---

### 2. env.template Completeness

**Location:** Section "Step 7.4: Create .env.template" (lines ~1288-1330)

**Issue:** CLAUDE_CODE_INSTRUCTIONS version is much more basic/incomplete

**CLAUDE_CODE_INSTRUCTIONS has:**
- Only ~6 environment variables
- Missing many Phase 2-10 API configurations
- Missing system configuration variables
- Missing optional data source variables

**ACTUAL config/env.template (CORRECT) has:**
- ~40+ environment variables
- All Phase 1-10 API configurations
- Complete system settings
- All data source options (ESPN, Balldontlie, Weather, etc.)
- Comprehensive comments and examples

**Impact:** High - Incomplete environment setup
**Status:** ✅ Actual env.template is comprehensive and correct
**Action:** Use actual `config/env.template` (already in repo), ignore CLAUDE_CODE_INSTRUCTIONS version

---

### 3. requirements.txt Versions and Completeness

**Location:** Section "Step 7.3: Create requirements.txt" (lines ~1254-1286)

**Issue:** Versions shown are outdated and package list is incomplete

**CLAUDE_CODE_INSTRUCTIONS shows:**
```
python-dotenv==1.0.0
pyyaml==6.0.1
psycopg2-binary==2.9.9
SQLAlchemy==2.0.23
requests==2.31.0
cryptography==41.0.7
# ... (12 packages total)
```

**ACTUAL requirements.txt (MORE COMPLETE) has:**
```
python-dotenv==1.1.1  # Newer version
pyyaml==6.0.3  # Newer version
psycopg2-binary==2.9.11  # Newer version
sqlalchemy==2.0.44  # Newer version
httpx==0.27.2  # MISSING in CLAUDE_CODE_INSTRUCTIONS
aiohttp==3.13.0  # MISSING in CLAUDE_CODE_INSTRUCTIONS
alembic==1.15.2  # MISSING in CLAUDE_CODE_INSTRUCTIONS
pydantic==2.12.0  # MISSING in CLAUDE_CODE_INSTRUCTIONS
# ... (~36 packages total with better versions)
```

**Impact:** High - Missing packages and outdated versions
**Status:** ✅ Actual requirements.txt is comprehensive with 2025 versions
**Action:** Use actual `requirements.txt` (already in repo), ignore CLAUDE_CODE_INSTRUCTIONS version

---

### 4. Task Order Issues

**Location:** Section "TASK 4: Create Developer Onboarding Guide" (line ~191)

**Issue:** Instructions reference using requirements.txt before creating it

**CLAUDE_CODE_INSTRUCTIONS sequence:**
- Section 2.3: "Install Python Dependencies" - Says run `pip install -r requirements.txt`
- Section 7.3: "Create requirements.txt" - Says to create the file

**Problem:** Can't install from a file that doesn't exist yet

**Correct sequence:**
1. Create requirements.txt FIRST
2. Create virtual environment
3. THEN install dependencies

**Impact:** Medium - Confusing task order
**Status:** ⚠️ Documentation issue in CLAUDE_CODE_INSTRUCTIONS
**Action:** Follow correct sequence: create requirements.txt → venv → pip install

---

### 5. Developer Onboarding - Not Created

**Location:** Section "TASK 4: Create Developer Onboarding Guide" (lines ~191-1080)

**Issue:** Task was marked for creation but template is very long (~900 lines)

**Status:** Not created during Phase 0
**Reason:**
- Template is extensive and detailed
- Phase 0 is documentation foundation, not developer onboarding
- Can create in Phase 1 when actually onboarding developers

**Impact:** Low - Not needed until Phase 1
**Action:** Create DEVELOPER_ONBOARDING_V1.0.md in Phase 1 when actually setting up environment

---

## What to Use for Phase 1

### ✅ Use These (CORRECT and CURRENT):

1. **config/env.template** - Complete, correct variable names
2. **requirements.txt** - Comprehensive, current versions (2025)
3. **All YAML config files** - Accurate and complete
4. **Master Requirements V2.3** - Correct environment variables
5. **Configuration Guide V3.0** - Matches actual YAML files
6. **API Integration Guide V2.0** - Correct RSA-PSS auth

### ❌ Ignore These Sections in CLAUDE_CODE_INSTRUCTIONS:

1. Section 7.3 - requirements.txt template (use actual file instead)
2. Section 7.4 - .env.template template (use actual file instead)
3. Section 2.3 - Environment Setup sequence (fix task order)
4. Task 4 - Developer Onboarding (create in Phase 1 if needed)

---

## Recommendations

### For Phase 1:

1. **Use actual config files** - Don't recreate from CLAUDE_CODE_INSTRUCTIONS
2. **Update CLAUDE_CODE_INSTRUCTIONS** - Fix discrepancies if it will be used again
3. **Create PHASE_1_CHECKLIST** - With correct task sequence and actual file references
4. **Verify environment** - Test that actual env.template variables work with Kalshi API

### For Future Sessions:

1. **Single source of truth** - Keep actual config files as authoritative
2. **Cross-reference validation** - Check instructions against actual files
3. **Version tracking** - Ensure instructions match current document versions

---

## Summary

**CLAUDE_CODE_INSTRUCTIONS.md was helpful for Phase 0 task organization, but has outdated/incorrect:**
- ❌ Environment variable names (critical)
- ❌ env.template content (incomplete)
- ❌ requirements.txt versions (outdated)
- ❌ Task sequence (out of order)

**Use the actual project files instead:**
- ✅ config/env.template (comprehensive and correct)
- ✅ requirements.txt (current versions)
- ✅ All configuration documentation (v2.3/v3.0)

**Impact on Phase 0:** None - Phase 0 used correct actual files
**Impact on Phase 1:** Medium - Need to use actual files, not instruction templates

---

**Document:** CLAUDE_CODE_INSTRUCTIONS_ERRATA.md
**Created:** 2025-10-17
**Purpose:** Document discrepancies for Phase 1 reference
**Status:** Informational - use actual project files as source of truth

---

**END OF CLAUDE_CODE_INSTRUCTIONS_ERRATA.md**
