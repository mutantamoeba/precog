# Python 3.14 Compatibility Note

**Date:** 2025-10-17
**Issue:** Some packages in requirements.txt don't support Python 3.14 yet
**Status:** Temporary workaround in place for Phase 1

---

## Issue

Python 3.14.0 is very new (just released). Some packages we planned to use don't have Python 3.14 compatible wheels yet:

### Packages Not Compatible with Python 3.14 (Resolved):
- `python-dateutil==2.9.1` - Version doesn't exist (latest is 2.9.0.post0) ✅ **FIXED**: Updated to 2.9.0.post0
- `spacy==3.8.7` - Max Python version is 3.13 ✅ **RESOLVED**: Replaced with transformers 4.47.0 (better fit for our use case + Python 3.14 compatible)

---

## Temporary Solution for Phase 1

Created `requirements-phase1.txt` with only the packages needed for Phase 1 (Core Infrastructure):

**What's Included:**
- ✅ Database: psycopg2-binary, sqlalchemy, alembic
- ✅ API Clients: requests, httpx, websockets, aiohttp
- ✅ Config: python-dotenv, pyyaml, pydantic
- ✅ Auth: cryptography (for Kalshi RSA-PSS)
- ✅ CLI: click
- ✅ Testing: pytest, pytest-asyncio, pytest-cov
- ✅ Code Quality: black, flake8, mypy
- ✅ Logging: structlog

**What's Excluded (not needed for Phase 1 anyway):**
- ❌ pandas, numpy (Phase 3-4: Data processing)
- ❌ apscheduler (Phase 2: Scheduling)
- ❌ transformers, torch (Phase 3-4: NLP/Sentiment - replaced spacy with transformers for better sentiment analysis)

---

## Long-Term Solutions

### Option 1: Wait for Package Updates (Recommended)
- By the time we reach Phase 2-4, packages will likely have Python 3.14 support
- Monitor PyPI for updated versions
- Update requirements.txt when available

### Option 2: Downgrade to Python 3.13
- Only if we absolutely need packages before they support 3.14
- Python 3.13 is the latest stable with full ecosystem support
- Would require recreating virtual environment

### Option 3: Use Compatible Versions
- Find newer/older versions that support Python 3.14
- May lose some features or get untested versions

---

## Recommendation

**Proceed with Phase 1 using `requirements-phase1.txt`**

Reasons:
1. Phase 1 only needs core infrastructure packages (database, API, config, logging, CLI)
2. All Phase 1 packages ARE compatible with Python 3.14
3. By Phase 2-4, the ecosystem will likely have caught up to Python 3.14
4. If not, we can switch to Python 3.13 later (one-time venv rebuild)

---

## Installation Commands

### For Phase 1 (Current):
```bash
pip install -r requirements-phase1.txt
```

### For Full Project (Phase 2+):
```bash
# Try full requirements
pip install -r requirements.txt

# If it fails due to Python 3.14:
# Option A: Wait for package updates
# Option B: Recreate venv with Python 3.13
python3.13 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

---

## Package Version Fixes Applied

**python-dateutil:**
- ❌ Original: `python-dateutil==2.9.1` (doesn't exist)
- ✅ Fixed: `python-dateutil==2.9.0.post0` (latest available)

**pytest-asyncio:**
- ❌ Original: `pytest-asyncio==0.24.1` (doesn't exist)
- ✅ Fixed: `pytest-asyncio==0.24.0` (latest stable)

**pytest-cov:**
- ❌ Original: `pytest-cov==5.1.1` (doesn't exist)
- ✅ Fixed: `pytest-cov==7.0.0` (latest stable)

**flake8:**
- ❌ Original: `flake8==8.0.1` (doesn't exist)
- ✅ Fixed: `flake8==7.3.0` (latest stable)

---

## Status

**Phase 1:** ✅ Can proceed with `requirements-phase1.txt`
**Phase 2-4:** ⚠️ May need to address pandas/numpy compatibility (transformers ✅ compatible)
**Phase 3-4 (NLP):** ✅ **RESOLVED** - Using transformers instead of spacy (better sentiment analysis + Python 3.14 compatible)

---

## Next Steps

1. ✅ Install Phase 1 requirements using `requirements-phase1.txt`
2. ✅ Complete Phase 1 implementation
3. 🔄 Monitor PyPI for Python 3.14 wheels:
   - pandas (currently max 3.13)
   - numpy (currently max 3.13)
   - ~~spacy~~ ✅ **RESOLVED** - Replaced with transformers 4.47.0 (Python 3.14 compatible)
4. 🔄 Update requirements.txt when pandas/numpy support Python 3.14
5. 🔄 If stuck before packages update, consider Python 3.13 venv

---

**Document:** PYTHON_3.14_COMPATIBILITY_NOTE.md
**Created:** 2025-10-17
**Purpose:** Track Python 3.14 compatibility issues and workarounds
**Status:** Temporary workaround in place

---

**END OF PYTHON_3.14_COMPATIBILITY_NOTE.md**
