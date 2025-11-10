# Phase 4 Deferred Tasks - Strategic Research Priorities

---
**Version:** 1.0
**Created:** November 9, 2025
**Status:** ✅ Current
**Purpose:** Document 11 critical research tasks deferred from Phase 4 to dedicated Phase 4.5 research period
**Target Phase:** Phase 4.5 (Ensemble Architecture & Dynamic Weights Research, 6-8 weeks)
---

## Overview

**Context:** During Phase 0.7c completion and strategic planning (November 2025), we identified **open architectural questions** that require **deep research** before committing to implementation. Rather than guess at solutions now, we will:

1. **Implement Phase 1-4** with STATIC configs (simple, proven patterns)
2. **Gather real-world data** from Phase 1-4 usage (6-9 months of development experience)
3. **Conduct focused research** in Phase 4.5 (6-8 weeks dedicated research)
4. **Make informed architectural decisions** based on data, not speculation
5. **Implement optimal solutions** in Phase 5+ with confidence

**Total Tasks:** 11 research tasks (74-92 hours total)
**Priority Distribution:**
- 🔴 **Critical Priority:** 2 tasks (18-22 hours) - Strategy research (DEF-013, DEF-014)
- 🟡 **High Priority:** 6 tasks (42-59 hours) - Strategy + Model research (DEF-009, DEF-010, DEF-015, DEF-016, DEF-011, DEF-012)
- 🟢 **Medium Priority:** 3 tasks (10-13 hours) - Edge detection quick wins (DEF-017, DEF-018, DEF-019)

---

## 🚨 Section 1: STRATEGY RESEARCH (HIGHEST PRIORITY) 🔴

**ADR Reference:** ADR-077 (Strategy vs Method Separation) in ARCHITECTURE_DECISIONS_V2.13.md

**Problem Statement:**
Current architecture separates **strategies** (Phase 1-3 entry/exit logic) from **methods** (Phase 4+ complete trading system bundles), but boundaries are **ambiguous**. Strategy configs already contain position management logic (e.g., `hedge_strategy.profit_lock_percentage: "0.70"`). Where does "strategy logic" END and "position management" BEGIN?

**Why This Matters:**
This is the **foundation of our trading system**. Getting this wrong means:
- Confusing config taxonomy (users don't know where to put settings)
- A/B testing breaks (can't isolate strategy vs position management performance)
- Version explosion (Strategy v1.0 × Model v2.0 × Position v1.5 × Risk v1.0 × Execution v1.0 = combinatorial nightmare)
- User frustration (unclear customization patterns)

**Decision Timeline:** Research in Phase 4.5 (after Phase 1-3 usage data available), decide before Phase 5 Methods Implementation

---

### DEF-013: Strategy Config Taxonomy (8-10 hours, 🔴 Critical Priority)

**Task ID:** DEF-013
**Priority:** 🔴 Critical (HIGHEST PRIORITY)
**Estimated Effort:** 8-10 hours
**Target Phase:** Phase 4.5 (Week 1-2)
**Dependencies:** 6-9 months of Phase 1-3 usage data (config complexity observations, user feedback)
**Blocking:** Phase 5 Methods Implementation (can't start until boundaries clear)

#### Problem
Current config taxonomy has **ambiguous boundaries**:

**Example from `trade_strategies.yaml`:**
```yaml
hedge_strategy:
  entry_logic: halftime_or_inplay  # Clearly "strategy"
  exit_conditions: [stop_loss, profit_target, hedge_complete]  # Clearly "strategy"
  hedge_sizing_method: partial_lock  # Is this "strategy" or "position management"?
  partial_lock:
    profit_lock_percentage: "0.70"  # Is this "strategy parameter" or "position management parameter"?
```

**Ambiguity:** If a user wants to test different profit lock percentages (60%, 70%, 80%), do they:
- **Option A:** Create `hedge_strategy_v1.1`, `hedge_strategy_v1.2`, `hedge_strategy_v1.3` (strategy versioning)
- **Option B:** Create `position_config_v1.1`, `position_config_v1.2`, `position_config_v1.3` (position management versioning)
- **Option C:** Create `method_v1.1`, `method_v1.2`, `method_v1.3` (bundled method versioning)

**Current problem:** Users don't know which approach to use, and A/B testing attribution is unclear.

#### Research Objectives

1. **Define Clear Boundaries:**
   - Create decision tree: "Should this setting be a strategy parameter or position management parameter?"
   - Document 5-10 example scenarios with rationale

2. **Boundary Criteria:**
   - **Strategy parameters:** Control WHEN to enter/exit (timing, conditions, triggers)
   - **Position management parameters:** Control HOW MUCH to size/adjust (Kelly fraction, profit lock percentage, trailing stop width)
   - **Risk management parameters:** Control exposure limits (max position, max correlated positions, circuit breakers)
   - **Execution parameters:** Control HOW to execute (price walking, slippage tolerance, order types)

3. **Gray Areas to Resolve:**
   - `profit_lock_percentage` - Strategy or position management?
   - `hedge_sizing_method` - Strategy or position management?
   - `trailing_stop_width` - Position management or risk management?
   - `circuit_breaker_threshold` - Risk management or execution?

4. **Propose Updated Config Structure:**
   - If current structure works → Document decision criteria only
   - If structure needs changes → Propose reorganization (e.g., move `profit_lock_percentage` to `position_management.yaml`)

#### Research Tasks

**Task 1: Analyze Current Configs (2-3 hours)**
- Review all 7 YAML configs (`trade_strategies.yaml`, `position_management.yaml`, `trading.yaml`, etc.)
- Extract ALL parameters (estimate: 50-100 parameters total)
- Classify each as: strategy, position, risk, execution, or AMBIGUOUS
- Create spreadsheet: Parameter Name | Current Location | Classification | Confidence (High/Medium/Low)

**Task 2: User Mental Model Research (2-3 hours)**
- Interview 3-5 target users (or simulate user scenarios)
- Question: "If you want to test different profit lock percentages, where do you expect to change the setting?"
- Question: "If you want to compare two strategies (halftime entry vs. pre-game entry), what configs would you duplicate?"
- Question: "If you want to test tighter trailing stops, is that a 'strategy change' or 'position management change'?"
- Document user expectations vs. current taxonomy

**Task 3: Create Decision Tree (2-3 hours)**
- Create flowchart: "Where does this parameter belong?"
- Example criteria:
  - Does it control TIMING? → Strategy
  - Does it control SIZING? → Position Management
  - Does it control RISK EXPOSURE? → Risk Management
  - Does it control EXECUTION MECHANICS? → Execution
- Validate decision tree against 20 sample parameters

**Task 4: Propose Taxonomy & Migration Plan (2-3 hours)**
- Document clear boundaries with examples
- If reorganization needed, propose migration plan:
  - Which parameters move from `trade_strategies.yaml` to `position_management.yaml`?
  - How to migrate existing strategy versions (v1.0 configs need updating?)
  - Backward compatibility considerations

#### Deliverable

**Document:** `STRATEGY_CONFIG_TAXONOMY_V1.0.md` (~200 lines)

**Contents:**
- Problem statement with current ambiguity examples
- Clear boundary definitions (strategy vs position vs risk vs execution)
- Decision tree flowchart (where does parameter X belong?)
- 10 example scenarios with rationale
- Proposed config structure (current or reorganized)
- Migration plan if reorganization needed
- A/B testing implications (can we isolate strategy changes from position changes?)

#### Success Criteria
- [ ] Clear decision criteria documented (developers know where to put new parameters)
- [ ] All ambiguous parameters classified with rationale
- [ ] User mental model validated (taxonomy matches user expectations)
- [ ] A/B testing workflows unblocked (can attribute performance to specific config changes)
- [ ] Phase 5 Methods Implementation can proceed with confidence

---

### DEF-014: A/B Testing Workflows Validation (10-12 hours, 🔴 Critical Priority)

**Task ID:** DEF-014
**Priority:** 🔴 Critical
**Estimated Effort:** 10-12 hours
**Target Phase:** Phase 4.5 (Week 1-2)
**Dependencies:** DEF-013 (Strategy Config Taxonomy must be complete first)
**Blocking:** Phase 5 Methods Implementation, Phase 6 Analytics/Reporting

#### Problem
Current versioning system (ADR-019: Immutable Versions) creates **A/B testing attribution challenges**:

**Scenario 1: Test Strategy Change Only**
- User wants to test: "Does halftime entry outperform pre-game entry?"
- **Current approach:** Create `strategy_v1.0` (halftime) and `strategy_v1.1` (pre-game), both use `model_v2.0`, `position_v1.0`, `risk_v1.0`, `execution_v1.0`
- **Question:** Can we confidently say "Strategy v1.1 increased Sharpe by 0.15" if other components also changed?

**Scenario 2: Test Position Management Change Only**
- User wants to test: "Does 70% profit lock outperform 60% profit lock?"
- **Current approach:** Is this `strategy_v1.1` or `position_v1.1`? (Depends on DEF-013 taxonomy)
- **Question:** Can we isolate position management performance from strategy performance?

**Scenario 3: Test Combined Change**
- User wants to test: "Halftime entry + 70% profit lock vs. Pre-game entry + 60% profit lock"
- **Current approach:** Create `method_v1.0` bundling all configs?
- **Question:** If performance improves, was it the strategy change or position change? (Can't tell!)

**Critical Issue:** If A/B testing attribution is unclear, we can't learn from backtests or live trading.

#### Research Objectives

1. **Design A/B Testing Workflows:**
   - Workflow 1: Strategy-only A/B test (hold position/risk/execution constant)
   - Workflow 2: Position-only A/B test (hold strategy/risk/execution constant)
   - Workflow 3: Combined A/B test (change multiple components, document which)

2. **Validate Statistical Attribution:**
   - Can we confidently say "Strategy v1.1 increased Sharpe by 0.15 ± 0.05 (95% CI)"?
   - What if strategy and position changes interact (non-additive effects)?
   - How to handle confounding variables?

3. **Identify Versioning Conflicts:**
   - Does current versioning system (immutable configs) support A/B testing?
   - Do we need "experiment groups" table to track A/B test configs?
   - How to prevent version proliferation (every A/B test creates 2+ versions)?

4. **Propose Solutions:**
   - Keep current separation (strategy/position/risk/execution as separate configs)?
   - Adopt "Methods" architecture (bundle all configs into methods)?
   - Hybrid approach (separate configs + experiment tracking table)?

#### Research Tasks

**Task 1: Design A/B Testing Workflows (3-4 hours)**
- Create 3 workflow diagrams:
  - Workflow 1: Strategy-only test (halftime vs. pre-game entry)
  - Workflow 2: Position-only test (60% vs. 70% profit lock)
  - Workflow 3: Combined test (halftime + 70% vs. pre-game + 60%)
- For each workflow, document:
  - Which configs change? (strategy? position? both?)
  - How to track in database? (trades table has `strategy_id`, `model_id` - add `position_config_id`?)
  - How to query results? (SELECT Sharpe FROM trades WHERE strategy_id = X)

**Task 2: Statistical Attribution Validation (3-4 hours)**
- Simulate backtest scenarios:
  - Scenario A: Strategy v1.0 + Position v1.0 → Sharpe 1.2
  - Scenario B: Strategy v1.1 + Position v1.0 → Sharpe 1.35 (can we attribute +0.15 to strategy?)
  - Scenario C: Strategy v1.1 + Position v1.1 → Sharpe 1.50 (interaction effect? +0.30 total, but how much from each?)
- Calculate statistical power: How many trades needed to detect Sharpe improvement of 0.10 with 95% confidence?
- Identify confounding variables: Market conditions, time period, opponent strength

**Task 3: Identify Versioning Conflicts (2-3 hours)**
- Map current versioning system to A/B testing needs:
  - `strategies` table (immutable configs) → Works for strategy A/B tests?
  - `probability_models` table (immutable configs) → Works for model A/B tests?
  - MISSING: `position_configs` table? `risk_configs` table? `execution_configs` table?
- Identify gaps:
  - How to A/B test position management if no `position_configs` table?
  - How to A/B test risk parameters if all in `trading.yaml` (global, not versioned)?
  - How to prevent version explosion (every A/B test creates 2+ strategy versions)?

**Task 4: Propose Experiment Tracking Solution (2-3 hours)**
- **Option A:** Separate config versioning (current plan)
  - Create `position_configs`, `risk_configs`, `execution_configs` tables (like `strategies` table)
  - Trades link to: `strategy_id`, `model_id`, `position_config_id`, `risk_config_id`, `execution_config_id`
  - **Pro:** Fine-grained A/B testing (can isolate each component)
  - **Con:** Version explosion (5 config types × 10 versions = 100,000 combinations?)

- **Option B:** "Methods" architecture (bundled configs)
  - Create `methods` table containing: strategy_id, model_id, position_config JSONB, risk_config JSONB, execution_config JSONB
  - Trades link to single `method_id`
  - **Pro:** Simpler user experience, manageable versions
  - **Con:** Coarse-grained A/B testing (can't isolate strategy vs. position performance)

- **Option C:** Hybrid (separate configs + experiment groups)
  - Keep current separate config tables
  - Add `experiment_groups` table tracking A/B test metadata
  - Trades link to `experiment_group_id` (maps to strategy/model/position/risk/execution combo)
  - **Pro:** Fine-grained A/B testing + manageable version tracking
  - **Con:** Added complexity (experiment groups table + queries)

- **Recommendation:** Based on DEF-013 taxonomy and DEF-016 combinatorics analysis

#### Deliverable

**Document:** `A_B_TESTING_WORKFLOWS_V1.0.md` (~300 lines)

**Contents:**
- Problem statement with A/B testing attribution challenges
- 3 workflow diagrams (strategy-only, position-only, combined)
- Statistical attribution validation (power analysis, confidence intervals)
- Versioning conflicts identified (gaps in current system)
- 3 proposed solutions (separate configs, methods, hybrid) with pros/cons/recommendations
- Database schema changes needed (if any)
- Example SQL queries for A/B test analysis
- Integration with existing versioning system (ADR-019)

#### Success Criteria
- [ ] Clear A/B testing workflows documented (developers know how to set up tests)
- [ ] Statistical attribution validated (can confidently measure strategy performance)
- [ ] Versioning conflicts resolved (know how to track position/risk/execution configs)
- [ ] Database schema updated (if needed) to support A/B testing
- [ ] Phase 5 Methods Implementation can proceed with validated A/B testing approach

---

### DEF-015: User Customization Patterns Research (6-8 hours, 🟡 High Priority)

**Task ID:** DEF-015
**Priority:** 🟡 High
**Estimated Effort:** 6-8 hours
**Target Phase:** Phase 4.5 (Week 3-4)
**Dependencies:** DEF-013 (Strategy Config Taxonomy), DEF-014 (A/B Testing Workflows)

#### Problem
We don't know how users will customize strategies in practice:

**User Story 1: Novice User**
- "I want to try a tighter trailing stop. Where do I change that?"
- **Separate configs:** "Edit `position_management.yaml`, create `position_v1.1`" (confusing?)
- **Bundled methods:** "Edit `method_v1.yaml`, change trailing_stop_width" (simpler?)

**User Story 2: Advanced User**
- "I want to A/B test 5 different entry strategies, all with the same position management."
- **Separate configs:** "Create `strategy_v1.0` through `strategy_v1.4`, reuse `position_v1.0`" (efficient)
- **Bundled methods:** "Create `method_v1.0` through `method_v1.4`, duplicate position config 5 times" (redundant?)

**Critical Question:** Do users prefer **separate configs** (more flexible, steeper learning curve) or **bundled methods** (simpler, less flexible)?

#### Research Objectives

1. **User Interview Study:**
   - Interview 3-5 target users (algorithmic traders, quant researchers, sports bettors)
   - Ask: "If you want to test a new exit rule, do you expect to create a new strategy version or a new position management version?"
   - Ask: "Would you prefer editing 4 separate config files (strategy/position/risk/execution) or 1 bundled config?"

2. **Industry Pattern Research:**
   - How do TradingView Pine Script, QuantConnect, Zipline, Backtrader handle this?
   - Do they use separate configs or bundled "strategies"?
   - What are pros/cons of each approach?

3. **Usability Trade-off Analysis:**
   - **Separate configs:**
     - **Pro:** Flexible (mix/match any strategy with any position config)
     - **Pro:** Fine-grained A/B testing
     - **Con:** Steep learning curve (users must understand 4 config types)
     - **Con:** Complex UI (4 dropdowns: strategy, model, position, risk, execution)
   - **Bundled methods:**
     - **Pro:** Simple (one "method" contains everything)
     - **Pro:** Easy UI (1 dropdown: method)
     - **Con:** Redundant configs (changing one parameter requires duplicating entire method)
     - **Con:** Coarse-grained A/B testing

4. **Propose Customization Patterns:**
   - **Beginner-friendly pattern:** Bundled methods with templates (e.g., "Conservative method", "Aggressive method")
   - **Advanced user pattern:** Separate configs with inheritance (e.g., "strategy_v1.1 inherits from strategy_v1.0")
   - **Hybrid pattern:** Default methods for novices, separate configs for advanced users

#### Research Tasks

**Task 1: User Interview Study (2-3 hours)**
- Recruit 3-5 target users:
  - 1-2 novice users (no algo trading experience)
  - 2-3 advanced users (have used QuantConnect, TradingView, or similar)
- Create interview script with 10 questions:
  - "How do you currently manage trading strategies?"
  - "If you want to test a new stop loss rule, what's your expected workflow?"
  - "Would you prefer editing 4 separate config files or 1 bundled config? Why?"
  - "How important is A/B testing to you?"
- Conduct 30-minute interviews (remote or in-person)
- Document feedback with direct quotes

**Task 2: Industry Pattern Research (2-3 hours)**
- Research 5 platforms:
  - **TradingView Pine Script:** How do strategies work? Separate configs or bundled?
  - **QuantConnect:** How do algorithms work? Class-based or config-based?
  - **Zipline (Quantopian):** How do strategies work? Separate modules or bundled?
  - **Backtrader:** How do strategies work? Modular or monolithic?
  - **MetaTrader:** How do EAs work? Bundled with parameters?
- Extract patterns:
  - Do they separate strategy logic from position sizing? Yes/No?
  - Do they allow A/B testing? How?
  - Do they use inheritance/composition? How?
- Create comparison table

**Task 3: Usability Trade-off Analysis (1-2 hours)**
- Create decision matrix:
  - Rows: Separate configs, Bundled methods, Hybrid
  - Columns: Flexibility, Learning curve, A/B testing, UI complexity, Config redundancy
  - Score each (1-5 scale)
- Identify winner for novice users vs. advanced users
- Document trade-offs with examples

**Task 4: Propose Customization Patterns (1-2 hours)**
- Design 3 user personas:
  - **Novice:** Wants simple, doesn't care about A/B testing
  - **Intermediate:** Wants to test a few variations, basic A/B testing
  - **Advanced:** Wants full control, extensive A/B testing
- For each persona, propose optimal config pattern
- Document migration path: Novice → Intermediate → Advanced

#### Deliverable

**Document:** `USER_CUSTOMIZATION_PATTERNS_V1.0.md` (~250 lines)

**Contents:**
- Problem statement with user stories
- User interview findings (3-5 interviews with direct quotes)
- Industry pattern research (TradingView, QuantConnect, Zipline, Backtrader, MetaTrader comparison)
- Usability trade-off analysis (decision matrix with scores)
- 3 user personas with recommended config patterns
- Migration path from novice to advanced user
- Recommendation for Precog architecture (separate configs, bundled methods, or hybrid)
- Integration with DEF-013 taxonomy and DEF-014 A/B testing workflows

#### Success Criteria
- [ ] 3-5 user interviews completed with documented feedback
- [ ] Industry patterns researched (5 platforms compared)
- [ ] Usability trade-offs quantified (decision matrix with scores)
- [ ] Clear recommendation for Precog architecture based on user needs
- [ ] Phase 5 UI design can proceed with validated customization patterns

---

### DEF-016: Version Combinatorics Modeling (4-6 hours, 🟡 High Priority)

**Task ID:** DEF-016
**Priority:** 🟡 High
**Estimated Effort:** 4-6 hours
**Target Phase:** Phase 4.5 (Week 3-4)
**Dependencies:** DEF-013 (Strategy Config Taxonomy), DEF-014 (A/B Testing Workflows)

#### Problem
If we adopt **separate config versioning** (Option A from DEF-014), how many version combinations will we realistically have?

**Theoretical worst case:**
- 100 strategies × 20 models × 50 position configs × 10 risk configs × 10 execution configs = **100,000,000 combinations** (combinatorial explosion!)

**But is this realistic?** Or will users actually use 5-10 strategies with 2-3 position configs = **10-30 combinations**?

**Critical Question:** Is version explosion a **real problem** (manage complexity now) or **theoretical concern** (solve if it happens)?

#### Research Objectives

1. **Model 3 Usage Scenarios:**
   - **Conservative:** 10 strategies, 5 models, 5 position configs, 3 risk configs, 2 execution configs
   - **Moderate:** 30 strategies, 10 models, 10 position configs, 5 risk configs, 3 execution configs
   - **Aggressive:** 100 strategies, 20 models, 50 position configs, 10 risk configs, 10 execution configs

2. **Calculate Implications for Each Scenario:**
   - Database storage (JSONB config size × versions)
   - Query performance (JOIN across 5 tables to get trade attribution)
   - UI complexity (5 dropdowns vs. 1 dropdown)
   - Version management overhead (tracking 5 version numbers vs. 1)

3. **Determine Acceptable Threshold:**
   - If <1000 combinations → Separate configs acceptable
   - If 1000-10,000 combinations → Consider hybrid (experiment groups)
   - If >10,000 combinations → Bundled methods required (simplify)

4. **Propose Version Management Strategy:**
   - If version explosion is real → Limit config proliferation (e.g., max 20 active strategies)
   - If version explosion is theoretical → No changes needed (proceed with separate configs)

#### Research Tasks

**Task 1: Model 3 Usage Scenarios (1-2 hours)**
- **Conservative Scenario:**
  - 10 strategies (e.g., halftime_entry, pre_game_entry, fourth_quarter_entry, etc.)
  - 5 models (e.g., ensemble_v1.0, elo_only_v1.0, regression_only_v1.0, ml_only_v1.0, historical_only_v1.0)
  - 5 position configs (e.g., kelly_25pct_v1.0, kelly_50pct_v1.0, fixed_size_v1.0, etc.)
  - 3 risk configs (e.g., max_5_positions_v1.0, max_10_positions_v1.0, max_20_positions_v1.0)
  - 2 execution configs (e.g., market_orders_v1.0, limit_orders_v1.0)
  - **Total combinations:** 10 × 5 × 5 × 3 × 2 = **1,500 combinations**

- **Moderate Scenario:**
  - 30 strategies (user tests many variations)
  - 10 models (multiple ensemble versions)
  - 10 position configs (varied Kelly fractions, profit locks, trailing stops)
  - 5 risk configs (varied position limits, correlation limits)
  - 3 execution configs (market, limit, limit with walking)
  - **Total combinations:** 30 × 10 × 10 × 5 × 3 = **45,000 combinations**

- **Aggressive Scenario:**
  - 100 strategies (extensive strategy research)
  - 20 models (many ensemble variations)
  - 50 position configs (fine-grained position management testing)
  - 10 risk configs (varied risk parameters)
  - 10 execution configs (advanced walking algorithms)
  - **Total combinations:** 100 × 20 × 50 × 10 × 10 = **100,000,000 combinations** (combinatorial explosion)

**Task 2: Calculate Storage Implications (1-2 hours)**
- Assume average JSONB config size:
  - Strategy config: ~500 bytes (entry/exit logic)
  - Model config: ~300 bytes (weights, thresholds)
  - Position config: ~400 bytes (Kelly fraction, profit locks, trailing stops)
  - Risk config: ~200 bytes (position limits, correlation limits)
  - Execution config: ~300 bytes (order types, slippage tolerance)
  - **Total per combination:** ~1700 bytes = 1.7 KB

- **Storage requirements:**
  - Conservative (1,500 combinations): 1,500 × 1.7 KB = **2.55 MB** (negligible)
  - Moderate (45,000 combinations): 45,000 × 1.7 KB = **76.5 MB** (acceptable)
  - Aggressive (100M combinations): 100M × 1.7 KB = **170 GB** (problematic!)

**Task 3: Calculate Query Performance Implications (1-2 hours)**
- Query to get trade attribution:
```sql
SELECT
  t.trade_id,
  s.strategy_name, s.strategy_version,
  m.model_name, m.model_version,
  p.position_config_name, p.version,
  r.risk_config_name, r.version,
  e.execution_config_name, e.version,
  t.pnl
FROM trades t
JOIN strategies s ON t.strategy_id = s.strategy_id
JOIN probability_models m ON t.model_id = m.model_id
JOIN position_configs p ON t.position_config_id = p.position_config_id
JOIN risk_configs r ON t.risk_config_id = r.risk_config_id
JOIN execution_configs e ON t.execution_config_id = e.execution_config_id
WHERE t.timestamp > '2026-01-01'
```

- Measure query performance:
  - With 1,500 combinations: <10ms (fast)
  - With 45,000 combinations: <50ms (acceptable)
  - With 100M combinations: >1000ms (slow!)

- Identify bottlenecks (5-way JOIN across tables)

**Task 4: Propose Version Management Strategy (1-2 hours)**
- If Conservative scenario is realistic:
  - **Recommendation:** Separate configs acceptable, no changes needed
  - **Rationale:** 1,500 combinations manageable, storage negligible, query performance fast

- If Moderate scenario is realistic:
  - **Recommendation:** Separate configs + experiment groups table
  - **Rationale:** 45,000 combinations borderline, add experiment groups to track active combinations only
  - **Implementation:** `experiment_groups` table with `(strategy_id, model_id, position_config_id, risk_config_id, execution_config_id)` combos used in live trading

- If Aggressive scenario is realistic:
  - **Recommendation:** Bundled methods required
  - **Rationale:** 100M combinations unmanageable, storage problematic (170GB), query performance slow (>1s)
  - **Implementation:** `methods` table with single JSONB config containing all components

#### Deliverable

**Document:** `VERSION_COMBINATORICS_ANALYSIS_V1.0.md` (~200 lines)

**Contents:**
- Problem statement with combinatorial explosion risk
- 3 usage scenarios modeled (conservative, moderate, aggressive)
- Storage implications calculated (MB/GB per scenario)
- Query performance implications measured (ms per scenario)
- UI complexity implications documented (5 dropdowns vs. 1 dropdown)
- Acceptable threshold determined (<1000, 1000-10,000, >10,000)
- Recommendation for Precog architecture (separate configs, hybrid, or bundled methods)
- Version management strategy proposed (limits, experiment groups, or simplification)

#### Success Criteria
- [ ] 3 usage scenarios modeled with realistic parameters
- [ ] Storage implications quantified (MB/GB)
- [ ] Query performance measured (ms)
- [ ] Clear threshold determined (when does version explosion become a problem?)
- [ ] Recommendation aligned with DEF-013 taxonomy and DEF-014 A/B testing workflows
- [ ] Phase 5 implementation can proceed with validated version management strategy

---

## Section 2: MODEL RESEARCH (4 tasks, 36-51 hours) 🟡

**ADR Reference:** ADR-076 (Dynamic Ensemble Weights Architecture) in ARCHITECTURE_DECISIONS_V2.13.md

**Problem Statement:**
Current ensemble configuration uses **STATIC weights** hardcoded in `probability_models.yaml` (elo: 0.40, regression: 0.35, ml: 0.25). This creates a **fundamental architectural tension**:
1. **Versioning System Requires Immutability** - Model configs MUST NOT change (ADR-019: Immutable Versions)
2. **Performance Requires Dynamic Weights** - Best weights change over time as models improve/degrade

**Why This Matters:**
Suboptimal weights mean **leaving money on the table**. If Elo is performing better than ML, but we're stuck with static weights, we're not maximizing edge.

**Decision Timeline:** Research in Phase 4.5, decide based on backtest data

---

### DEF-009: Backtest Static vs Dynamic Performance (15-20 hours, 🟡 High Priority)

**Task ID:** DEF-009
**Priority:** 🟡 High
**Estimated Effort:** 15-20 hours
**Target Phase:** Phase 4.5 (Week 3-6)
**Dependencies:** Phase 2 historical data loaded, Phase 4 ensemble model implemented

#### Problem
We don't know if dynamic ensemble weights actually improve performance enough to justify the added complexity.

**Static weights (current):**
- elo: 0.40, regression: 0.35, ml: 0.25 (never change)
- **Pro:** Simple, immutable (ADR-019 compliance)
- **Con:** Suboptimal if one model performs better/worse over time

**Dynamic weights (proposed):**
- Update weights weekly/monthly based on recent model performance
- **Pro:** Optimal (weights reflect current model quality)
- **Con:** Complex (separate mutable weights table), violates ADR-019 immutability

**Critical Question:** Does dynamic weighting improve Sharpe ratio by >5%? If not, complexity isn't worth it.

#### Research Objectives

1. **Implement 4 Weighting Strategies:**
   - **Baseline:** Static weights (elo: 0.40, regression: 0.35, ml: 0.25)
   - **Sharpe-weighted:** Weight by trailing 30-day Sharpe ratio of each model
   - **Performance-weighted:** Weight by trailing 30-day accuracy (Brier score) of each model
   - **Kelly-weighted:** Weight by Kelly criterion (edge / variance)

2. **Backtest on 2019-2024 NFL Data:**
   - 1000+ games (5 seasons)
   - Walk-forward validation (train on 2019-2021, test on 2022-2024)
   - Calculate metrics for each weighting strategy:
     - Sharpe ratio
     - Max drawdown
     - Calmar ratio (Sharpe / max drawdown)
     - Win rate
     - Average edge per trade

3. **Quantify Performance Gains:**
   - "Dynamic weights improve Sharpe by X% vs. static baseline"
   - "Dynamic weights reduce max drawdown by Y%"
   - "Dynamic weights require Z additional complexity (separate table, weight calculation logic)"

4. **Determine Decision Criteria:**
   - If dynamic weights improve Sharpe <5% → Keep static weights (not worth complexity)
   - If dynamic weights improve Sharpe 5-15% → Consider hybrid periodic rebalancing (monthly updates)
   - If dynamic weights improve Sharpe >15% → Implement full dynamic weights system

#### Research Tasks

**Task 1: Implement 4 Weighting Strategies (4-5 hours)**
- Create `analytics/weight_calculator.py` module
- Implement 4 methods:
  ```python
  def calculate_sharpe_weights(models: List[Model], lookback_days: int = 30) -> Dict[str, Decimal]:
      """Weight by trailing Sharpe ratio."""
      # Calculate Sharpe for each model over lookback period
      # Normalize weights to sum to 1.0
      pass

  def calculate_performance_weights(models: List[Model], lookback_days: int = 30) -> Dict[str, Decimal]:
      """Weight by trailing Brier score (accuracy)."""
      pass

  def calculate_kelly_weights(models: List[Model], lookback_days: int = 30) -> Dict[str, Decimal]:
      """Weight by Kelly criterion (edge / variance)."""
      pass

  def calculate_static_weights() -> Dict[str, Decimal]:
      """Baseline: Static weights from config."""
      return {"elo": Decimal("0.40"), "regression": Decimal("0.35"), "ml": Decimal("0.25")}
  ```

**Task 2: Create Backtesting Framework (3-4 hours)**
- Extend existing backtesting module (`analytics/backtesting.py`)
- Add walk-forward validation:
  ```python
  def walk_forward_backtest(
      games: List[Game],
      weight_strategy: str,  # "static", "sharpe", "performance", "kelly"
      train_window_days: int = 365,
      test_window_days: int = 90,
      rebalance_freq_days: int = 30
  ) -> BacktestResults:
      """Walk-forward backtest with dynamic weights."""
      # For each test window:
      #   1. Train weights on previous train_window_days
      #   2. Test on next test_window_days
      #   3. Rebalance weights every rebalance_freq_days
      #   4. Calculate Sharpe, drawdown, Calmar for test period
      pass
  ```

**Task 3: Run Backtests on 2019-2024 Data (5-7 hours)**
- Load 1000+ NFL games from `historical_games` table
- Run 4 backtests (static, sharpe, performance, kelly)
- For each strategy:
  - Calculate Sharpe ratio, max drawdown, Calmar ratio, win rate, avg edge
  - Track weight evolution over time (plot weights vs. date)
  - Measure implementation complexity (lines of code, database queries per day)
- Generate comparison table

**Task 4: Analyze Results & Make Recommendation (3-4 hours)**
- Compare 4 strategies side-by-side
- Calculate performance improvements:
  - "Sharpe-weighted improves Sharpe by 12% vs. static baseline (1.20 → 1.34)"
  - "Performance-weighted reduces max drawdown by 8% (15% → 13.8%)"
  - "Kelly-weighted increases Calmar ratio by 10% (0.80 → 0.88)"
- Estimate complexity cost:
  - Static weights: 0 additional code, 0 database queries
  - Dynamic weights: +200 lines of code, +30 database queries/day (weight calculation)
- Make recommendation based on cost/benefit ratio

#### Deliverable

**Document:** `DYNAMIC_WEIGHTS_BACKTEST_REPORT_V1.0.md` (~400 lines)

**Contents:**
- Problem statement with static vs. dynamic trade-off
- 4 weighting strategies implemented (Sharpe, performance, Kelly, static)
- Backtest methodology (walk-forward validation, 2019-2024 NFL data)
- Performance comparison table (Sharpe, max drawdown, Calmar, win rate per strategy)
- Weight evolution charts (4 charts showing weight changes over time)
- Complexity cost analysis (lines of code, database queries per strategy)
- Decision criteria applied (5%, 5-15%, >15% Sharpe improvement)
- Recommendation for Precog architecture (static, hybrid, or full dynamic)
- Integration with ADR-019 (Immutable Versions) - How to reconcile?

#### Success Criteria
- [ ] 4 weighting strategies implemented and tested
- [ ] Backtest on 1000+ games completed (2019-2024 NFL data)
- [ ] Performance gains quantified (Sharpe improvement %)
- [ ] Complexity cost quantified (lines of code, database queries)
- [ ] Clear recommendation based on data (not speculation)
- [ ] ADR-076 can be resolved (static, hybrid, or dynamic weights)

---

### DEF-010: Weight Calculation Methods Comparison (10-15 hours, 🟡 High Priority)

**Task ID:** DEF-010
**Priority:** 🟡 High
**Estimated Effort:** 10-15 hours
**Target Phase:** Phase 4.5 (Week 5-6)
**Dependencies:** DEF-009 (Backtest Static vs Dynamic Performance)

#### Problem
If DEF-009 shows dynamic weights improve performance >5%, we need to choose the **best weight calculation method**.

**5 Candidate Methods:**
1. **Sharpe-weighted:** Weight by trailing Sharpe ratio (risk-adjusted returns)
2. **Performance-weighted:** Weight by trailing Brier score (accuracy)
3. **Kelly-weighted:** Weight by Kelly criterion (edge / variance)
4. **Bayesian updating:** Bayesian posterior probabilities of model quality
5. **Exponential moving average (EMA):** Smooth recent performance

**Evaluation Criteria:**
- **Performance:** Backtest Sharpe, max drawdown, Calmar ratio
- **Stability:** How often do weights change? (daily? weekly? monthly?)
- **Complexity:** Implementation time (hours), lines of code, database queries
- **Robustness:** Performance degrades gracefully with limited data?

#### Research Objectives

1. **Implement 5 Weight Calculation Methods:**
   - Extend `analytics/weight_calculator.py` with 5 methods
   - Each method takes model performance history → outputs weights

2. **Backtest Each Method on 2019-2024 NFL Data:**
   - Use walk-forward validation framework from DEF-009
   - Calculate Sharpe, max drawdown, Calmar, win rate for each method
   - Track weight stability (standard deviation of weights over time)

3. **Evaluate Complexity:**
   - Lines of code per method
   - Database queries per day (how often weights recalculate?)
   - Dependencies (external libraries? statistical models?)

4. **Rank Methods by Cost/Benefit Ratio:**
   - Score each method: Performance (0-10) / Complexity (0-10) = Cost/benefit ratio
   - Recommend method with best ratio

#### Research Tasks

**Task 1: Implement 5 Weight Calculation Methods (4-6 hours)**
- Extend `analytics/weight_calculator.py`:
  ```python
  def calculate_sharpe_weights(models: List[Model], lookback_days: int = 30) -> Dict[str, Decimal]:
      """Weight by trailing Sharpe ratio."""
      pass

  def calculate_performance_weights(models: List[Model], lookback_days: int = 30) -> Dict[str, Decimal]:
      """Weight by trailing Brier score (accuracy)."""
      pass

  def calculate_kelly_weights(models: List[Model], lookback_days: int = 30) -> Dict[str, Decimal]:
      """Weight by Kelly criterion (edge / variance)."""
      pass

  def calculate_bayesian_weights(models: List[Model], prior_weights: Dict[str, Decimal]) -> Dict[str, Decimal]:
      """Bayesian updating with performance priors."""
      # Use Beta distribution for Bayesian posterior
      pass

  def calculate_ema_weights(models: List[Model], alpha: Decimal = Decimal("0.05")) -> Dict[str, Decimal]:
      """Exponential moving average of recent performance."""
      # EMA smoothing: new_weight = alpha * new_performance + (1 - alpha) * old_weight
      pass
  ```

**Task 2: Backtest Each Method (3-5 hours)**
- Use walk-forward validation framework from DEF-009
- Run 5 backtests (1 per method) on 2019-2024 NFL data
- For each method:
  - Calculate Sharpe ratio, max drawdown, Calmar ratio, win rate
  - Track weight stability (std dev of weights over time)
  - Measure rebalancing frequency (how often weights change by >5%?)

**Task 3: Evaluate Complexity (2-3 hours)**
- For each method, document:
  - **Lines of code:** Count Python LOC for implementation
  - **Database queries per day:** How many queries to calculate weights?
  - **Dependencies:** Does it need scipy? statsmodels? TensorFlow?
  - **Implementation time:** How long did it take to implement? (hours)
- Create complexity scoring table (0-10 scale)

**Task 4: Rank Methods & Recommend (1-2 hours)**
- Create cost/benefit matrix:
  - Rows: 5 methods
  - Columns: Sharpe ratio, Max drawdown, Calmar ratio, Complexity score
  - Score: Performance (0-10) / Complexity (0-10) = Cost/benefit ratio
- Rank methods by ratio (highest = best)
- Recommend top method for Precog implementation

#### Deliverable

**Document:** `WEIGHT_CALCULATION_METHODS_V1.0.md` (~300 lines)

**Contents:**
- Problem statement with 5 candidate methods
- Implementation details for each method (code snippets)
- Backtest results table (Sharpe, max drawdown, Calmar, win rate per method)
- Weight stability analysis (std dev over time, rebalancing frequency)
- Complexity evaluation (lines of code, database queries, dependencies)
- Cost/benefit matrix (performance / complexity ratio)
- Ranking of methods (1st, 2nd, 3rd, 4th, 5th)
- Recommendation for Precog implementation with rationale
- Integration plan with DEF-012 (Ensemble Versioning Strategy)

#### Success Criteria
- [ ] 5 weight calculation methods implemented and tested
- [ ] Backtest on 1000+ games completed for each method
- [ ] Complexity evaluated (lines of code, database queries, dependencies)
- [ ] Methods ranked by cost/benefit ratio
- [ ] Clear recommendation with rationale
- [ ] DEF-012 can proceed with recommended method

---

### DEF-011: Version Explosion Analysis (5-8 hours, 🟢 Medium Priority)

**Task ID:** DEF-011
**Priority:** 🟢 Medium
**Estimated Effort:** 5-8 hours
**Target Phase:** Phase 4.5 (Week 6-7)
**Dependencies:** DEF-010 (Weight Calculation Methods Comparison)

#### Problem
If we adopt **dynamic weights** (from DEF-009/DEF-010), how many ensemble versions will be created?

**Scenario 1: Daily weight updates**
- 365 ensemble versions per year (1 per day)
- **Storage:** 365 × 300 bytes = ~109 KB/year (negligible)
- **Query complexity:** Need to query correct version for each trade date

**Scenario 2: Weekly weight updates**
- 52 ensemble versions per year (1 per week)
- **Storage:** 52 × 300 bytes = ~16 KB/year (negligible)

**Scenario 3: Monthly weight updates**
- 12 ensemble versions per year (1 per month)
- **Storage:** 12 × 300 bytes = ~3.6 KB/year (negligible)

**Critical Question:** How frequently should weights update? Daily (optimal performance, high version count) vs. monthly (simpler, lower version count)?

#### Research Objectives

1. **Model Version Creation Frequency:**
   - If daily updates: 365 versions/year
   - If weekly updates: 52 versions/year
   - If monthly updates: 12 versions/year

2. **Calculate Storage Implications:**
   - Database storage (JSONB config size × versions)
   - Over 5 years, 10 years

3. **Measure Query Performance Impact:**
   - Query to get correct ensemble version for trade date
   - Join performance with 365 versions vs. 12 versions

4. **Determine Acceptable Update Frequency:**
   - If performance plateaus after monthly updates → Use monthly (simpler)
   - If performance improves with weekly updates → Use weekly (balance)
   - If performance requires daily updates → Use daily (accept higher version count)

#### Research Tasks

**Task 1: Model Version Creation Frequency (1-2 hours)**
- Create version projection table:
  - Daily updates: 365/year × 5 years = 1,825 versions
  - Weekly updates: 52/year × 5 years = 260 versions
  - Monthly updates: 12/year × 5 years = 60 versions

**Task 2: Calculate Storage Implications (1-2 hours)**
- Assume ensemble config size: ~300 bytes (weights + metadata)
- Calculate storage:
  - Daily (1,825 versions): 1,825 × 300 bytes = 547.5 KB (negligible)
  - Weekly (260 versions): 260 × 300 bytes = 78 KB (negligible)
  - Monthly (60 versions): 60 × 300 bytes = 18 KB (negligible)
- **Conclusion:** Storage is NOT a concern (all scenarios <1 MB)

**Task 3: Measure Query Performance Impact (2-3 hours)**
- Query to get correct ensemble version for trade:
```sql
SELECT
  t.trade_id,
  m.model_name,
  m.model_version,
  m.config ->> 'weights' AS weights
FROM trades t
JOIN probability_models m ON t.model_id = m.model_id
WHERE t.trade_id = 12345
```
- Measure query time:
  - With 60 versions (monthly): <5ms
  - With 260 versions (weekly): <10ms
  - With 1,825 versions (daily): <50ms
- **Conclusion:** Query performance is acceptable for all scenarios

**Task 4: Determine Acceptable Update Frequency (1-2 hours)**
- From DEF-009 backtest, extract performance vs. rebalance frequency:
  - Daily rebalance: Sharpe 1.35
  - Weekly rebalance: Sharpe 1.33 (98% of daily performance)
  - Monthly rebalance: Sharpe 1.28 (95% of daily performance)
- Calculate performance loss vs. version count trade-off
- Recommend frequency balancing performance and simplicity

#### Deliverable

**Document:** `ENSEMBLE_VERSION_EXPLOSION_ANALYSIS_V1.0.md` (~150 lines)

**Contents:**
- Problem statement with version creation frequency scenarios
- Version projection table (daily, weekly, monthly over 5/10 years)
- Storage implications (KB/MB per scenario)
- Query performance measurements (ms per scenario)
- Performance vs. frequency trade-off analysis (Sharpe ratio vs. version count)
- Recommendation for rebalancing frequency (daily, weekly, or monthly)
- Integration with DEF-012 (Ensemble Versioning Strategy)

#### Success Criteria
- [ ] Version projection modeled for 3 scenarios (daily, weekly, monthly)
- [ ] Storage implications quantified (KB/MB)
- [ ] Query performance measured (ms)
- [ ] Performance vs. frequency trade-off analyzed
- [ ] Clear recommendation for rebalancing frequency
- [ ] DEF-012 can proceed with recommended frequency

---

### DEF-012: Ensemble Versioning Strategy Documentation (6-8 hours, 🟢 Medium Priority)

**Task ID:** DEF-012
**Priority:** 🟢 Medium
**Estimated Effort:** 6-8 hours
**Target Phase:** Phase 4.5 (Week 6-7)
**Dependencies:** DEF-009 (Backtest), DEF-010 (Weight Methods), DEF-011 (Version Explosion)

#### Problem
If we adopt dynamic weights, how do we reconcile with ADR-019 (Immutable Versions)?

**Option 1: Static Weights (current)**
- Model configs immutable, weights never change
- **Pro:** Simple, ADR-019 compliant
- **Con:** Suboptimal performance (DEF-009 shows 5-15% Sharpe loss)

**Option 2: Dynamic Weights + Separate Mutable Table**
- Model configs immutable, weights stored in separate `ensemble_weights` table (mutable)
- **Pro:** Optimal performance, ADR-019 compliant (configs unchanged)
- **Con:** Complex (2 tables: `probability_models` + `ensemble_weights`)

**Option 3: Hybrid Periodic Rebalancing**
- Create new ensemble version monthly/quarterly with updated weights
- **Pro:** Balance simplicity and performance
- **Con:** Still creates versions, but fewer than daily updates

**Critical Question:** Which option best balances performance, simplicity, and ADR-019 compliance?

#### Research Objectives

1. **Document 3 Versioning Options:**
   - Option 1: Static weights (current)
   - Option 2: Dynamic weights + separate mutable table
   - Option 3: Hybrid periodic rebalancing (monthly/quarterly new versions)

2. **Evaluate Each Option:**
   - Performance (Sharpe ratio from DEF-009 backtest)
   - Complexity (lines of code, database tables, queries)
   - ADR-019 compliance (immutability preserved?)
   - Implementation time (hours to implement)

3. **Create Implementation Plan:**
   - Database schema changes needed
   - Code changes needed (ensemble model, backtesting, trade attribution)
   - Migration plan (how to transition from current static weights?)

4. **Make Recommendation:**
   - Based on DEF-009/DEF-010/DEF-011 data, recommend best option
   - Document rationale, pros/cons, implementation roadmap

#### Research Tasks

**Task 1: Document 3 Versioning Options (2-3 hours)**
- **Option 1: Static Weights (current)**
  - **Database:** `probability_models` table with static weights in JSONB config
  - **Query:** `SELECT config ->> 'weights' FROM probability_models WHERE model_id = X`
  - **Pros:** Simple, ADR-019 compliant, zero implementation time
  - **Cons:** Suboptimal performance (DEF-009 shows 5-15% Sharpe loss)
  - **Performance:** Sharpe 1.20 (baseline from DEF-009)

- **Option 2: Dynamic Weights + Separate Mutable Table**
  - **Database:** `probability_models` table (immutable configs) + `ensemble_weights` table (mutable weights)
  - **Schema:**
    ```sql
    CREATE TABLE ensemble_weights (
      weight_id SERIAL PRIMARY KEY,
      ensemble_model_id INTEGER REFERENCES probability_models(model_id),
      weights JSONB NOT NULL,  -- {"elo": 0.42, "regression": 0.33, "ml": 0.25}
      valid_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      valid_to TIMESTAMP,  -- NULL = currently active
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    ```
  - **Query:** `SELECT weights FROM ensemble_weights WHERE ensemble_model_id = X AND valid_to IS NULL`
  - **Pros:** Optimal performance (Sharpe 1.35 from DEF-009), ADR-019 compliant (configs unchanged)
  - **Cons:** Complex (2 tables, more queries), implementation time ~8-10 hours
  - **Performance:** Sharpe 1.35 (+12.5% vs. static)

- **Option 3: Hybrid Periodic Rebalancing**
  - **Database:** `probability_models` table (create new version monthly with updated weights)
  - **Process:** Every month, calculate new weights → create `ensemble_v1.1`, `ensemble_v1.2`, etc.
  - **Query:** `SELECT config ->> 'weights' FROM probability_models WHERE model_id = X` (same as Option 1)
  - **Pros:** Balance simplicity and performance, ADR-019 compliant (new versions, not mutations)
  - **Cons:** Creates versions (12/year), migration complexity (which version for which trades?)
  - **Performance:** Sharpe 1.28 (DEF-009 monthly rebalance, +6.7% vs. static)

**Task 2: Evaluate Each Option (2-3 hours)**
- Create comparison matrix:
  - Rows: Option 1 (static), Option 2 (dynamic), Option 3 (hybrid)
  - Columns: Performance (Sharpe), Complexity (LOC), ADR-019 Compliance, Implementation Time, Version Count
  - Score each (0-10 scale where applicable)

**Task 3: Create Implementation Plan (1-2 hours)**
- For recommended option, document:
  - Database schema changes (SQL DDL)
  - Code changes needed:
    - `models/ensemble.py` - Update to query dynamic weights (if Option 2)
    - `analytics/backtesting.py` - Handle time-varying weights (if Option 2 or 3)
    - `database/crud_operations.py` - Add ensemble_weights CRUD operations (if Option 2)
  - Migration plan:
    - Phase 5a: Implement weight calculation logic
    - Phase 5b: Integrate with ensemble model
    - Phase 5c: Backtest with historical data to validate
  - Effort estimate (hours)

**Task 4: Make Recommendation (1-2 hours)**
- Based on DEF-009/DEF-010/DEF-011 data:
  - If dynamic weights improve Sharpe <5% → Recommend Option 1 (static)
  - If dynamic weights improve Sharpe 5-15% → Recommend Option 3 (hybrid monthly)
  - If dynamic weights improve Sharpe >15% → Recommend Option 2 (dynamic + separate table)
- Document rationale with data support
- Create implementation roadmap for recommended option

#### Deliverable

**Document:** `ENSEMBLE_VERSIONING_STRATEGY_V1.0.md` (~250 lines)

**Contents:**
- Problem statement with immutability vs. performance tension
- 3 versioning options documented (static, dynamic + table, hybrid)
- Comparison matrix (performance, complexity, ADR-019 compliance, implementation time)
- Implementation plan for recommended option (database schema, code changes, migration plan)
- Recommendation with rationale based on DEF-009/DEF-010/DEF-011 data
- Integration with ADR-019 (Immutable Versions) - How does recommendation preserve immutability?
- Roadmap for Phase 5+ implementation

#### Success Criteria
- [ ] 3 versioning options fully documented with pros/cons
- [ ] Comparison matrix created with data from DEF-009/DEF-010/DEF-011
- [ ] Implementation plan created for recommended option
- [ ] Clear recommendation with data-driven rationale
- [ ] ADR-076 can be resolved with recommended approach
- [ ] Phase 5 ensemble implementation can proceed with validated versioning strategy

---

## Section 3: EDGE DETECTION RESEARCH (3 tasks, 10-13 hours) 🟢

**Quick Wins - Lower Priority**

These are shorter research tasks that can be completed quickly and provide incremental improvements to edge detection. Lower priority than strategies and models research.

---

### DEF-017: Fee Impact Sensitivity Analysis (3-4 hours, 🟢 Medium Priority)

**Task ID:** DEF-017
**Priority:** 🟢 Medium
**Estimated Effort:** 3-4 hours
**Target Phase:** Phase 4.5 (Week 7)
**Dependencies:** Phase 4 edge detection implemented

#### Problem
Current `min_edge` threshold is 5% (hardcoded in `markets.yaml`). But is this optimal given Kalshi's 7% taker fees?

**Example:**
- Market price: 0.6000 (60%)
- True probability: 0.6500 (65%)
- Edge: 5.00% (meets threshold)
- **After fees:** Net edge = 5.00% - 7% × winnings = ?% (may be negative!)

**Critical Question:** What's the optimal `min_edge` threshold that accounts for fees and maximizes Sharpe ratio?

#### Research Objectives

1. **Backtest `min_edge` Thresholds from 3% to 10%:**
   - Test 8 values: 3%, 4%, 5%, 6%, 7%, 8%, 9%, 10%
   - For each threshold, calculate trade frequency, Sharpe ratio, max drawdown

2. **Find Optimal Threshold:**
   - Threshold that maximizes Sharpe ratio
   - Balance edge size vs. trade frequency (higher threshold = fewer trades but higher edge)

3. **Recommend Updated Threshold:**
   - If 5% is optimal → Keep current setting
   - If different threshold (e.g., 6%) improves Sharpe >10% → Update `markets.yaml`

#### Research Tasks

**Task 1: Implement Fee Impact Calculation (1 hour)**
- Update edge detection to account for fees:
```python
def calculate_net_edge(
    true_prob: Decimal,
    market_price: Decimal,
    taker_fee_pct: Decimal = Decimal("0.07")
) -> Decimal:
    """Calculate edge after accounting for fees."""
    gross_edge = true_prob - market_price
    # Kalshi fees are 7% of *winnings*, not stake
    expected_winnings = true_prob * (Decimal("1.0") - market_price)
    fee_cost = expected_winnings * taker_fee_pct
    net_edge = gross_edge - (fee_cost / market_price)  # Normalize to market price
    return net_edge
```

**Task 2: Backtest 8 Thresholds (1-2 hours)**
- Run backtest on 2019-2024 NFL data
- For each threshold (3%, 4%, ..., 10%):
  - Filter trades where net_edge >= threshold
  - Calculate Sharpe ratio, max drawdown, trade frequency, win rate
- Create comparison table

**Task 3: Analyze Results & Recommend (1 hour)**
- Plot Sharpe ratio vs. threshold
- Identify optimal threshold (max Sharpe)
- Recommend updated setting for `markets.yaml`

#### Deliverable

**Document:** `FEE_IMPACT_ANALYSIS_V1.0.md` (~100 lines)

**Contents:**
- Problem statement with fee impact on edge
- Fee calculation formula (net_edge = gross_edge - fee_cost)
- Backtest results table (8 thresholds × Sharpe/drawdown/frequency)
- Optimal threshold identified (e.g., 6% maximizes Sharpe)
- Recommendation for `markets.yaml` update

#### Success Criteria
- [ ] Fee impact calculation implemented
- [ ] 8 thresholds backtested on 2019-2024 data
- [ ] Optimal threshold identified
- [ ] Recommendation made for config update

---

### DEF-018: Confidence Interval Methods Research (4-5 hours, 🟢 Medium Priority)

**Task ID:** DEF-018
**Priority:** 🟢 Medium
**Estimated Effort:** 4-5 hours
**Target Phase:** Phase 4.5 (Week 7)
**Dependencies:** Phase 4 edge detection implemented

#### Problem
Current edge detection uses **fixed thresholds** (min_edge = 5%, no uncertainty quantification).

**Example:**
- Model predicts: 65% ± ??? (no confidence interval!)
- Market price: 60%
- Edge: 5.00% ± ??? (is this reliable?)

**Question:** Should we skip trades where confidence interval is wide (high uncertainty)?

#### Research Objectives

1. **Research 4 Confidence Interval Methods:**
   - Bootstrap (resample model predictions)
   - Bayesian credible intervals (posterior distribution)
   - Ensemble agreement (std dev of model predictions)
   - Monte Carlo simulation (perturb inputs, measure output variance)

2. **Implement Proof-of-Concept:**
   - For each method, calculate confidence interval for 100 sample predictions
   - Measure: Width of interval, computation time, implementation complexity

3. **Evaluate Utility:**
   - Does filtering trades with wide confidence intervals improve Sharpe ratio?
   - Complexity vs. utility trade-off

4. **Recommend:**
   - If confidence intervals improve Sharpe <5% → Skip implementation (not worth complexity)
   - If confidence intervals improve Sharpe >5% → Implement in Phase 5

#### Research Tasks

**Task 1: Research 4 Methods (1-2 hours)**
- Literature review: Bootstrap, Bayesian, ensemble agreement, Monte Carlo
- Document pros/cons of each method

**Task 2: Implement Proof-of-Concept (2-3 hours)**
- Implement 4 methods in `analytics/confidence_intervals.py`
- Test on 100 sample games
- Measure: Interval width, computation time, implementation time

**Task 3: Evaluate Utility (1 hour)**
- Backtest: Filter trades where confidence interval width >10%
- Compare Sharpe ratio with vs. without filtering
- Calculate utility gain vs. complexity cost

#### Deliverable

**Document:** `CONFIDENCE_INTERVAL_METHODS_V1.0.md` (~150 lines)

**Contents:**
- Problem statement with uncertainty quantification need
- 4 methods researched (bootstrap, Bayesian, ensemble agreement, Monte Carlo)
- Proof-of-concept results (interval width, computation time per method)
- Utility evaluation (Sharpe improvement with filtering)
- Recommendation (implement or skip based on utility vs. complexity)

#### Success Criteria
- [ ] 4 confidence interval methods researched
- [ ] Proof-of-concept implemented and tested
- [ ] Utility evaluated (Sharpe improvement with filtering)
- [ ] Recommendation made (implement or skip)

---

### DEF-019: Market Correlation Analysis (3-4 hours, 🟢 Medium Priority)

**Task ID:** DEF-019
**Priority:** 🟢 Medium
**Estimated Effort:** 3-4 hours
**Target Phase:** Phase 4.5 (Week 7)
**Dependencies:** Phase 2 historical data loaded

#### Problem
Same-game markets are **correlated** (spread, total points, halftime winner).

**Example: Buccaneers vs. Lions**
- Buccaneers spread: -3.5 (correlated with total points and halftime winner)
- Total points: 50.5 (correlated with spread and halftime winner)
- Buccaneers halftime winner: Yes (correlated with spread and total)

**Risk:** Trading all 3 markets exposes portfolio to correlated outcomes (if Buccaneers underperform, lose all 3 trades).

**Question:** Should we filter correlated markets? E.g., "Don't trade >2 markets from same game if correlation >0.70"?

#### Research Objectives

1. **Quantify Correlation:**
   - Calculate correlation matrix for 10 sample games
   - Correlation between: spread, total points, halftime winner, player props

2. **Propose Filtering Strategy:**
   - "Don't trade >2 markets from same game if correlation >0.70"
   - Or: "Weight correlated markets less in portfolio (Kelly fraction × correlation factor)"

3. **Backtest Filtering:**
   - Compare Sharpe ratio with vs. without correlation filtering
   - Measure trade frequency reduction

4. **Recommend:**
   - If correlation filtering improves Sharpe >5% → Implement in Phase 5
   - If correlation filtering reduces trade frequency too much (>50%) → Skip

#### Research Tasks

**Task 1: Calculate Correlation Matrix (1-2 hours)**
- Extract 10 sample games from historical data
- For each game, calculate correlation between:
  - Spread vs. total points
  - Spread vs. halftime winner
  - Total points vs. halftime winner
  - Spread vs. player props (if available)
- Create average correlation matrix

**Task 2: Propose Filtering Strategy (1 hour)**
- If correlation >0.70 → Only trade 1-2 markets from same game
- Document filtering rules

**Task 3: Backtest Filtering (1 hour)**
- Simulate backtest: Apply correlation filter, measure Sharpe ratio and trade frequency
- Compare with unfiltered baseline

#### Deliverable

**Document:** `MARKET_CORRELATION_ANALYSIS_V1.0.md` (~100 lines)

**Contents:**
- Problem statement with correlated market risk
- Correlation matrix for 10 sample games
- Proposed filtering strategy (correlation threshold, max markets per game)
- Backtest results (Sharpe ratio with vs. without filtering)
- Recommendation (implement or skip based on Sharpe improvement)

#### Success Criteria
- [ ] Correlation matrix calculated for 10 sample games
- [ ] Filtering strategy proposed (correlation threshold, max markets per game)
- [ ] Backtest completed (Sharpe ratio with vs. without filtering)
- [ ] Recommendation made (implement or skip)

---

## Summary

**Total Deferred Tasks:** 11
**Total Effort:** 74-92 hours (6-8 weeks @ 12 hours/week)

**Priority Breakdown:**
- 🔴 **Critical Priority:** 2 tasks (18-22 hours) - Strategy research (DEF-013, DEF-014)
- 🟡 **High Priority:** 6 tasks (42-59 hours) - Strategy + Model research (DEF-009, DEF-010, DEF-015, DEF-016, DEF-011, DEF-012)
- 🟢 **Medium Priority:** 3 tasks (10-13 hours) - Edge detection quick wins (DEF-017, DEF-018, DEF-019)

**Deliverables:** 11 research reports + 2 ADR resolutions + 2 planning document updates

**Decision Timeline:**
- Week 1-2: Strategy research (DEF-013, DEF-014) → Resolve ADR-077
- Week 3-6: Strategy + Model research (DEF-015, DEF-016, DEF-009, DEF-010) → Continue ADR-077, Start ADR-076
- Week 6-7: Model research (DEF-011, DEF-012) → Resolve ADR-076
- Week 7-8: Edge detection research (DEF-017, DEF-018, DEF-019) + Documentation

**After Phase 4.5:**
- ADR-076 resolved (static, hybrid, or dynamic ensemble weights)
- ADR-077 resolved (separate configs or bundled methods)
- Phase 5+ implementation can proceed with validated architecture

**See Also:**
- `docs/foundation/DEVELOPMENT_PHASES_V1.7.md` - Phase 4.5 detailed phase description
- `docs/utility/STRATEGIC_WORK_ROADMAP_V1.0.md` - 25 strategic tasks organized by category
- `docs/foundation/ARCHITECTURE_DECISIONS_V2.13.md` - ADR-076 and ADR-077 (full analysis)

---

**END OF PHASE_4_DEFERRED_TASKS_V1.0.md**
