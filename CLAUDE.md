# Precog Project Context for Claude Code

**Version:** 2.0
**Last Updated:** 2026-03-04
**Previous Version:** V1.22 (archived to _archive/CLAUDE_V1.22.md)

---

## What Is Precog?

A modular Python application that identifies and executes positive expected value (EV+) trading opportunities on prediction markets.

**Pipeline:** Fetch market prices (Kalshi) -> Calculate true probabilities (ML models) -> Identify edges -> Execute trades -> Monitor positions -> Exit strategically.

**Current Focus:** Kalshi platform, NFL/NCAAF/NBA/NHL markets.
**Future:** Multiple sports, non-sports markets, multiple platforms.

### Tech Stack

- **Language:** Python 3.14 (3.12 kept for backward compat in CI)
- **Database:** PostgreSQL 15+ with `DECIMAL(10,4)` precision
- **ORM:** SQLAlchemy + psycopg2
- **Testing:** pytest (8 test types)
- **Configuration:** YAML files + `.env` for secrets
- **CLI:** Typer framework
- **APIs:** Kalshi (RSA-PSS auth), ESPN (public)
- **Layout:** `src/precog/` (PEP 517/518)

---

## Agent Team Structure

This project uses an agent team approach:

| Role | Description |
|------|-------------|
| **PM (main agent)** | Owns priorities, delegates, synthesizes results. You talk to PM. |
| **Backend Dev** | API connectors, database, trading logic, schedulers |
| **Frontend Dev** | Web GUI (FastAPI + modern frontend) |
| **Code Reviewer** | Reviews ALL changes before commit - catches shortcuts and misunderstandings |
| **Analyst** | On-demand: audits tests, docs, requirements when decisions impact them |

**Code Reviewer is mandatory** - the #1 pain point is bugs from shortcuts or misunderstandings.
**Analyst is on-demand** - called when changes impact documentation, not every session.

---

## Current State

**What works:** Kalshi API client, ESPN client, database CRUD, config system, market/game pollers, service supervisor.
**What's shaky:** Manager integration, scheduler stability for long runs, database environment drift.
**Not built yet:** Trade execution pipeline, model prediction pipeline, risk management enforcement, web GUI.

**MVP Roadmap:**
1. Data Collection MVP - Fix schedulers, 24hr soak test, verify data integrity
2. Manual Trade Placement MVP - Web form -> Kalshi API call
3. Web GUI Dashboard - Market browser, positions, manual trading

**Tests:** ~4,827 reported but ~3,000 effective (quality > quantity initiative underway).
**Docs:** ~86,000 lines of valuable docs (architecture, guides, schema). Process ceremony archived.

---

## Critical Patterns (NEVER Violate)

### 1. Decimal Precision - NEVER USE FLOAT
```python
# CORRECT
price = Decimal("0.4975")
# WRONG - NEVER DO THIS
price = 0.4975
```
All prices, probabilities, and money values use `Decimal`. Database uses `DECIMAL(10,4)`.

### 2. Credentials - NEVER HARDCODE
```python
# CORRECT
api_key = os.getenv('DEV_KALSHI_API_KEY')
# WRONG - NEVER DO THIS
api_key = "sk_live_abc123"
```

### 3. SCD Type 2 Versioning
Always filter by `row_current_ind = TRUE` when querying positions, markets, game states.

### 4. Environment Safety
Two-axis model: `PRECOG_ENV` (dev/test/staging/prod) + `MARKET_MODE` (demo/live).
Credential pattern: `{PRECOG_ENV}_KALSHI_API_KEY` (e.g., `DEV_KALSHI_API_KEY`).
Dangerous combos blocked: test+live, prod+demo.

### 5. Cross-Platform
ASCII output for console (Windows cp1252). Explicit UTF-8 for file I/O.

### 6. Immutable Versioning
Strategies and models are immutable once created. Create new version, don't modify existing.

### 7. External API Test Mocking — VCR OR live, NEVER hand-written

Tests that exercise code calling **Kalshi, ESPN, or any HTTP client** use one of two approaches — **never** hand-written `MagicMock` response dicts:

```python
# CORRECT — Pattern 22 VCR cassette (reproducible, catches shape regressions)
@pytest.mark.vcr  # Records to tests/cassettes/ on first run, replays after
def test_kalshi_market_fetch():
    markets = kalshi_client.get_markets(series="NFL")
    assert markets[0]["ticker"].startswith("KXNFLGAME-")

# CORRECT — Live contract test (catches API format drift)
@pytest.mark.live_api  # Runs only in nightly contract workflow, never in normal CI
def test_kalshi_api_responds_to_markets_endpoint():
    markets = kalshi_client.get_markets()
    assert "markets" in markets and all("ticker" in m for m in markets["markets"])

# WRONG — Hand-written mock (rots silently, cannot catch drift)
mock_kalshi.poll_once.return_value = {"items_fetched": 10, "items_updated": 8}
```

**Why:** Hand-written mocks freeze a guessed shape that diverges from the real API over time. VCR cassettes (`tests/cassettes/`) record real responses once and replay them — they catch regressions in our code AND surface format drift when the cassette is re-recorded. Live contract tests catch drift in real-time but are gated to nightly runs. See `tests/integration/api_connectors/test_kalshi_client_vcr.py` for the canonical Pattern 22 reference implementation.

**Umbrella issue #764** tracks the retrofit of 8 files that historically violated this rule and had been reporting fictional green CI for months. **Trigger S73** enforces this rule on new PRs; **Pattern 22** in `docs/guides/DEVELOPMENT_PATTERNS_V1.31.md` is the authoritative reference.

---

## Repository Structure

```
precog-repo/
├── src/precog/              # Main package
│   ├── api_connectors/      # Kalshi, ESPN clients + types
│   ├── config/              # YAML configs + environment logic
│   ├── database/            # Connection, CRUD, migrations (Alembic)
│   ├── trading/             # StrategyManager, PositionManager
│   ├── analytics/           # ModelManager, EloEngine
│   ├── schedulers/          # Pollers (Kalshi, ESPN), ServiceSupervisor
│   ├── matching/            # Event-game matching, ticker parsing
│   ├── runners/             # ServiceRunner (production wrapper)
│   ├── cli/                 # Typer CLI commands
│   └── tui/                 # Terminal UI (deprioritized)
├── tests/                   # 8 test types: unit, integration, e2e, property,
│                            #   stress, race, security, performance
├── scripts/                 # Utility scripts
├── docs/                    # Documentation
│   ├── foundation/          # Requirements, ADRs, phases, testing strategy
│   ├── guides/              # Implementation guides, patterns
│   ├── database/            # Schema docs
│   ├── api-integration/     # API docs, pricing cheat sheet
│   ├── supplementary/       # Detailed specs
│   └── utility/             # Process docs (being archived)
└── _archive/                # Archived/superseded docs
```

---

## Key Documents

**Architecture & Planning:**
- `docs/foundation/MASTER_REQUIREMENTS_V2.25.md` - All requirements
- `docs/foundation/ARCHITECTURE_DECISIONS_V2.35.md` - 114 ADRs
- `docs/foundation/DEVELOPMENT_PHASES_ERA2_V1.1.md` - Phase roadmap (Era 2: current)

**Implementation:**
- `docs/guides/DEVELOPMENT_PATTERNS_V1.31.md` - 64 development patterns with examples
- `docs/guides/CONFIGURATION_GUIDE_V3.1.md` - YAML config reference
- `docs/guides/KALSHI_CLIENT_USER_GUIDE_V1.0.md` - Kalshi API usage
- `docs/guides/STRATEGY_MANAGER_USER_GUIDE_V1.1.md`
- `docs/guides/MODEL_MANAGER_USER_GUIDE_V1.1.md`
- `docs/guides/POSITION_MANAGER_USER_GUIDE_V1.1.md`

**Database & API:**
- `docs/database/DATABASE_SCHEMA_SUMMARY_V1.16.md` - Complete schema
- `docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md`
- `docs/api-integration/KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md` - CRITICAL reference

**Testing:**
- `docs/foundation/TESTING_STRATEGY_V3.9.md` - 8-type testing strategy

---

## Security Essentials

**Before every commit:**
```bash
# Scan for hardcoded credentials
git grep -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]" -- '*.py' '*.yaml'

# Verify .env not staged
git diff --cached --name-only | grep "\.env$" && echo "STOP - .env staged!" || echo "OK"

# Run tests
python -m pytest tests/ -v
```

**Never commit:** `.env`, `_keys/*`, `*.pem`, `*.key`, database dumps.

---

## Quick Reference Commands

```bash
# Validation
./scripts/validate_quick.sh          # Fast validation (~3s)
./scripts/validate_all.sh            # Full validation (~60s)

# Testing (3 levels)
python -m pytest tests/unit/ -q --no-cov -n auto                       # Quick (~30s)
python -m pytest tests/unit/ tests/integration/ tests/e2e/ -q --no-cov # Medium (~60-90s, = pre-push)
python -m pytest tests/ -q --no-cov                                     # Full (~3-5 min, = CI)
python -m pytest tests/ --cov=src/precog --cov-report=term-missing      # Full + coverage

# Code quality
python -m ruff format .              # Format code
python -m ruff check .               # Lint
python -m mypy .                     # Type check

# Database
python scripts/test_db_connection.py # Test connection

# Services
python main.py scheduler start --supervised --foreground  # Start pollers
python main.py scheduler status                           # Check status
python main.py scheduler stop                             # Stop pollers
```

---

## Common Mistakes to Avoid

**NEVER:**
1. Use float for prices: `price = 0.4975`
2. Hardcode credentials: `password = "..."`
3. Query without `row_current_ind`: `query(Position).all()`
4. Use float in YAML configs: `min_edge: 0.05` (use string: `"0.05"`)
5. Skip tests: `git commit --no-verify`
6. Commit `.env` files

**ALWAYS:**
1. Use Decimal: `price = Decimal("0.4975")`
2. Use env vars: `os.getenv('PASSWORD')`
3. Filter by `row_current_ind == True`
4. Use strings in YAML: `min_edge: "0.05"`
5. Run tests before commit
6. Have Code Reviewer agent check changes before committing

---

## Branch & PR Workflow

```bash
# Feature branch workflow
git checkout -b feature/description
# ... make changes ...
git add <specific-files>
git commit -m "description"
git push origin feature/description
gh pr create --title "..." --body "..."
```

Branch protection on `main` (restored session 43, 2026-04-08): requires PR, must be up-to-date with main, and the **`CI Summary`** status check must pass before merge.

`CI Summary` is the umbrella job in `.github/workflows/ci.yml` that aggregates all the underlying jobs (`pre-commit-checks`, `security-scan`, `documentation-validation`, `test`, `integration-tests`, `test-type-coverage`). It is the **only** required status check, by design — most of those underlying jobs are gated on `needs.detect-changes.outputs.code == 'true'` and skip on docs-only PRs. Requiring them individually would block every docs-only PR forever waiting for skipped checks. `CI Summary` runs unconditionally (`if: always()`) and correctly treats skipped jobs as success while still failing on any actual job failure.

Admin override is enabled (`enforce_admins: false`) for emergency direct pushes. The Windows test job (`Tests (Python 3.14 on windows-latest, main only)`) is also deliberately not required because per #697 it only runs on main-branch pushes, not PR runs.

**History note (session 43):** The first attempt at restoration required 6 individual checks. The very first PR to test the rule (#701 — this doc) was a docs-only change, and all 6 checks were skipped via `paths-filter`, blocking the PR forever. The `CI Summary` umbrella was the correct gate from the start. **Lesson: when a workflow uses `paths-filter` or `if:` conditionals, gate on the umbrella job that's designed to handle skips, not on individual conditional jobs.**

---

## Version History

| Version | Date | Summary |
|---------|------|---------|
| 2.0 | 2026-03-04 | Major simplification: 1,893 -> ~500 lines. Archived process ceremony. Added agent team structure. |
| 1.22 | 2025-11-29 | Pre-planning test coverage checklist |
| 1.16 | 2025-11-13 | First size reduction (48.7%) |
| 1.0 | 2025-10-28 | Initial creation |

Full version history available in `_archive/CLAUDE_V1.22.md`.
