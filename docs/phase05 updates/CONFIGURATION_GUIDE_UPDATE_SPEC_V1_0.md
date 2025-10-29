# Configuration Guide Update Specification V1.0

**Version:** 1.0  
**Created:** 2025-10-21  
**Purpose:** Define required updates to CONFIGURATION_GUIDE_V3.0 → V3.1  
**Status:** ✅ Specification Complete

---

## Executive Summary

**Current State:** CONFIGURATION_GUIDE_V3.0 exists but is missing:
- Session 7 position monitoring enhancements
- Exit priority hierarchy and execution strategies
- User customization strategy (Phase 1, 1.5, 4-5)
- ADR-021 Method abstraction integration
- YAML consistency audit findings

**Target State:** CONFIGURATION_GUIDE_V3.1 with comprehensive coverage of all configuration aspects

**Estimated Effort:** 4-6 hours

---

## Required Updates to CONFIGURATION_GUIDE_V3.0

### 1. Add New Section: Position Monitoring Configuration

**Location:** After "Position Management Configuration" section

**Content:**

```markdown
## Position Monitoring Configuration

### Overview

The position monitoring system tracks all open positions and evaluates exit conditions dynamically. Configuration controls monitoring frequency, urgency detection, and API usage.

### Configuration File: position_management.yaml

#### Monitoring Frequency

```yaml
monitoring:
  normal_frequency: 30      # Check every 30 seconds under normal conditions
  urgent_frequency: 5       # Check every 5 seconds when urgent conditions detected
```

**Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `normal_frequency` | int | 30 | 10-120 | Seconds between checks (normal) |
| `urgent_frequency` | int | 5 | 3-15 | Seconds between checks (urgent) |

**When Urgent Mode Activates:**

```yaml
  urgent_conditions:
    near_stop_loss_pct: 0.02      # Within 2% of stop loss
    near_profit_target_pct: 0.02  # Within 2% of profit target  
    near_trailing_stop_pct: 0.02  # Within 2% of trailing stop
```

**Example:**
- Position at +13% profit, profit target at +15%
- Within 2% of target → Switch to urgent mode (5s checks)
- Ensures timely exit when target hit

#### API Rate Management

```yaml
  price_cache_ttl_seconds: 10        # Cache prices for 10 seconds
  max_api_calls_per_minute: 60      # Safety limit
```

**Calculation:**
- Normal: 20 positions × (60s / 30s) = 40 calls/min ✓
- Urgent: 5 positions × (60s / 5s) = 60 calls/min ✓
- Cache reduces load by ~66%

**Safety Constraints:**
- `max_api_calls_per_minute` is NOT user-customizable (safety)
- System auto-throttles if approaching limit
- Urgent checks prioritized over normal checks

#### Best Practices

✅ **DO:**
- Use 30s for normal (balances responsiveness and API usage)
- Use 5s for urgent (timely exits without hammering API)
- Keep cache at 10s (acceptable staleness)

❌ **DON'T:**
- Set normal_frequency < 10s (API abuse)
- Set urgent_frequency < 3s (excessive API load)
- Disable caching (will hit rate limits)

### Monitoring in Action

**Scenario: Position Approaching Profit Target**

```
Time 0:00 - Position at +10% (normal mode, check every 30s)
Time 0:30 - Position at +12% (normal mode)
Time 1:00 - Position at +13.5% (URGENT: within 2% of +15% target)
Time 1:05 - Position at +14.2% (urgent mode, check every 5s)
Time 1:10 - Position at +15.1% (PROFIT TARGET HIT → EXIT)
```

Without urgent mode, might miss exit at +15% and wait until +14% on next 30s check.
```

---

### 2. Add New Section: Exit Priority & Execution Configuration

**Location:** After "Position Monitoring Configuration" section

**Content:**

```markdown
## Exit Priority & Execution Configuration

### Overview

Exit conditions are organized into a 4-level priority hierarchy. Each priority level has distinct execution strategies optimized for urgency vs. price optimization.

### Exit Priority Hierarchy

#### Configuration File: position_management.yaml

```yaml
exit_priorities:
  CRITICAL:
    - stop_loss
    - circuit_breaker
  HIGH:
    - trailing_stop
    - time_based_urgent
    - liquidity_dried_up
  MEDIUM:
    - profit_target
    - partial_exit_target
  LOW:
    - early_exit
    - edge_disappeared
    - rebalance
```

**Priority Levels:**

| Level | Purpose | Exit Speed | Price Optimization |
|-------|---------|------------|-------------------|
| CRITICAL | Capital protection | IMMEDIATE | None (market orders) |
| HIGH | Risk management | FAST | Minimal |
| MEDIUM | Profit taking | MODERATE | Balanced |
| LOW | Position optimization | PATIENT | Maximum |

#### Conflict Resolution

**Rule:** If multiple exit conditions trigger simultaneously, highest priority wins.

**Example:**
- Position triggers both `profit_target` (MEDIUM) and `trailing_stop` (HIGH)
- System executes `trailing_stop` exit (higher priority)
- Ensures risk management takes precedence over profit taking

### Execution Strategies by Priority

#### Configuration File: position_management.yaml

```yaml
exit_execution:
  CRITICAL:
    order_type: market           # Market order (immediate fill)
    timeout_seconds: 5           # Fast timeout
    retry_strategy: immediate_market  # No limit attempts, go market
    
  HIGH:
    order_type: limit            # Limit order (reduce slippage)
    price_strategy: aggressive   # Best bid + 1 tick
    timeout_seconds: 10
    retry_strategy: walk_then_market  # Walk 2x, then market
    max_walks: 2
    
  MEDIUM:
    order_type: limit
    price_strategy: fair         # Best bid (no premium)
    timeout_seconds: 30
    retry_strategy: walk_price   # Walk price patiently
    max_walks: 5
    
  LOW:
    order_type: limit
    price_strategy: conservative # Best bid - 1 tick (wait for better)
    timeout_seconds: 60
    retry_strategy: walk_slowly
    max_walks: 10
```

#### Strategy Definitions

**CRITICAL: Immediate Market Orders**
- **Use Case:** Stop loss, circuit breaker
- **Execution:** Market order for entire position
- **Timeout:** 5 seconds
- **Retry:** If not filled in 5s, place another market order
- **Goal:** Fill at any price, minimize loss

**HIGH: Aggressive Limit Orders**
- **Use Case:** Trailing stop, time urgency, illiquid markets
- **Execution:** Limit at best_bid + $0.01 (aggressive)
- **Timeout:** 10 seconds
- **Retry:** Walk price 2x (10s each), then switch to market
- **Goal:** Fast fill with minimal slippage

**Example:**
```
Attempt 1: Limit at $0.68 (best bid + $0.01) → Wait 10s
If not filled:
Attempt 2: Limit at $0.67 (best bid) → Wait 10s
If not filled:
Attempt 3: Market order → Fill immediately
```

**MEDIUM: Fair Limit Orders**
- **Use Case:** Profit targets, partial exits
- **Execution:** Limit at best_bid (fair price)
- **Timeout:** 30 seconds
- **Retry:** Walk price 5x (30s each)
- **Goal:** Balanced price and speed

**LOW: Conservative Limit Orders**
- **Use Case:** Early exit, rebalance, edge disappeared
- **Execution:** Limit at best_bid - $0.01 (wait for better)
- **Timeout:** 60 seconds
- **Retry:** Walk price 10x (60s each)
- **Goal:** Best possible price, patient

#### Price Walking Explained

**What is Price Walking?**

When a limit order doesn't fill, progressively adjust price toward market until filled.

**Example (MEDIUM priority, fair limit):**

```
Market: Best bid $0.65, Best ask $0.68

Attempt 1: Limit at $0.65 (best bid) → Wait 30s → Not filled
Attempt 2: Limit at $0.66 (walk +$0.01) → Wait 30s → Not filled
Attempt 3: Limit at $0.67 (walk +$0.01) → Wait 30s → Not filled
Attempt 4: Limit at $0.68 (best ask) → Wait 30s → FILLED ✓

Total time: 2 minutes
Average price: $0.68 (vs $0.70 if used market order immediately)
Savings: $0.02 per contract
```

**Price Strategies:**

| Strategy | Starting Price | Rationale |
|----------|---------------|-----------|
| aggressive | best_bid + $0.01 | Pay premium for speed |
| fair | best_bid | Market price, no premium |
| conservative | best_bid - $0.01 | Wait for better price |

#### Best Practices

✅ **DO:**
- Use CRITICAL for stop losses (capital protection)
- Use HIGH for trailing stops (lock in profits quickly)
- Use MEDIUM for profit targets (balanced)
- Use LOW when no urgency (maximize price)

❌ **DON'T:**
- Use LOW for stop losses (too slow, losses grow)
- Use CRITICAL for profit targets (unnecessary slippage)
- Set max_walks < 2 for any level (too impatient)
- Disable circuit breakers (safety requirement)

### Customization Guidelines

**User-Customizable Parameters:**

All timeout and max_walks parameters are user-customizable:

```yaml
# Example: More aggressive HIGH priority exits
exit_execution:
  HIGH:
    timeout_seconds: 5      # Faster (was 10)
    max_walks: 1            # Less patient (was 2)
```

**Safe Ranges:**

| Parameter | Min | Max | Default |
|-----------|-----|-----|---------|
| CRITICAL timeout | 3 | 10 | 5 |
| HIGH timeout | 5 | 20 | 10 |
| MEDIUM timeout | 15 | 60 | 30 |
| LOW timeout | 30 | 120 | 60 |
| max_walks | 1 | 20 | varies |

**NOT Customizable:**
- Priority hierarchy (CRITICAL always highest)
- CRITICAL order_type (must be market)
- Exit condition assignments to priorities
```

---

### 3. Add New Section: User Customization

**Location:** After "Configuration Files Overview" section

**Content:**

[Insert content from USER_CUSTOMIZATION_STRATEGY_V1_0.md Section "Configuration Guide Updates Required"]

Include:
- Phase 1: YAML Editing
- Phase 1.5: Webapp UI
- Phase 4-5: Method Templates
- User-customizable parameter list
- Safety constraints
- Safe ranges
- Dangerous changes warning

---

### 4. Update Existing Section: Position Management

**Changes Required:**

#### Add Partial Exits Second Stage

**Current (V3.0):**
```yaml
partial_exits:
  enabled: true
  stages:
    - name: "first_target"
      profit_threshold: 0.15
      exit_percentage: 50
```

**Update to (V3.1):**
```yaml
partial_exits:
  enabled: true
  stages:
    - name: "first_target"
      profit_threshold: 0.15  # +15% profit
      exit_percentage: 50     # Exit 50% of position
      description: "Initial profit taking to reduce risk"
    
    - name: "second_target"   # NEW
      profit_threshold: 0.25  # +25% profit
      exit_percentage: 25     # Exit another 25%
      description: "Further de-risking, let 25% ride with trailing stop"

# Remaining 25% rides with trailing stop for maximum upside
```

**Explanation:**

Add detailed explanation:
- Stage 1: Take profits at +15%, de-risk 50%
- Stage 2: Take profits at +25%, de-risk another 25%
- Remaining 25%: Let it run with trailing stop protection
- Example P&L calculation

#### Add Liquidity Thresholds

**Add new subsection:**

```markdown
### Liquidity Thresholds

Configuration to handle illiquid markets:

```yaml
liquidity:
  max_spread: 0.03  # Maximum 3¢ spread (triggers liquidity_dried_up exit)
  min_volume: 50    # Minimum 50 contracts (triggers liquidity_dried_up exit)
  
  exit_on_illiquid: true   # Auto-exit if market becomes illiquid
  alert_on_illiquid: true  # Alert user when illiquidity detected
```

**Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `max_spread` | decimal | 0.03 | 0.01-0.10 | Maximum bid-ask spread |
| `min_volume` | int | 50 | 10-500 | Minimum contracts required |
| `exit_on_illiquid` | bool | true | - | Auto-exit on illiquidity |
| `alert_on_illiquid` | bool | true | - | Alert user |

**When Liquidity Dried Up Exit Triggers:**

```
Condition 1: Spread > max_spread (3¢)
    Example: Best bid $0.60, best ask $0.64 → Spread $0.04 > $0.03 ✓ TRIGGER

Condition 2: Volume < min_volume (50 contracts)
    Example: Order book shows only 30 contracts total → < 50 ✓ TRIGGER

Either condition → liquidity_dried_up exit (HIGH priority)
```

**Why This Matters:**

In illiquid markets:
- ❌ Hard to exit position (no buyers)
- ❌ High slippage (wide spreads)
- ❌ Price manipulation risk

Auto-exit protects capital by getting out before liquidity disappears completely.

**User-Customizable:**
- ✅ max_spread (adjust for sport/market type)
- ✅ min_volume (adjust based on typical market sizes)
- ✅ exit_on_illiquid (can disable, but not recommended)
```

#### Remove edge_reversal References

**Action:** Search CONFIGURATION_GUIDE_V3.0 for any references to `edge_reversal` exit condition.

**If found:**
1. Remove all documentation of edge_reversal
2. Add deprecation notice:

```markdown
### Deprecated Exit Conditions

**edge_reversal:** This exit condition was removed in V3.1 as redundant.

**Reason:** Functionality fully covered by:
- `early_exit`: Triggers when edge drops below absolute threshold (2%)
- `edge_disappeared`: Triggers when edge turns negative

**Migration:** No action required. Existing coverage is complete.
```

---

### 5. Add New Section: Configuration Hierarchy

**Location:** Early in document (after "Overview")

**Content:**

```markdown
## Configuration Hierarchy

### Phase 1: 2-Level Hierarchy

```
Priority: YAML File > Code Defaults

┌─────────────────┐
│  YAML File      │  ← User edits directly (restart required)
└────────┬────────┘
         │ Not found?
         ▼
┌─────────────────┐
│  Code Defaults  │  ← Hardcoded fallback values
└─────────────────┘
```

**Example:**
```python
# Config class
config = Config()

# 1. Check position_management.yaml for 'exit_rules.profit_targets.high_confidence'
# 2. If not found, use code default: 0.25
profit_target = config.get('exit_rules.profit_targets.high_confidence', default=0.25)
```

### Phase 1.5: 3-Level Hierarchy (Planned)

```
Priority: Database Override > YAML File > Code Defaults

┌─────────────────┐
│  Database       │  ← Per-user overrides (no restart)
│  Override       │
└────────┬────────┘
         │ Not found?
         ▼
┌─────────────────┐
│  YAML File      │  ← Global defaults
└────────┬────────┘
         │ Not found?
         ▼
┌─────────────────┐
│  Code Defaults  │  ← Hardcoded fallback values
└─────────────────┘
```

**Example:**
```python
# Config class (Phase 1.5)
config = Config(user_id=123)

# 1. Check user_config_overrides table for user 123
# 2. If not found, check position_management.yaml
# 3. If not found, use code default: 0.25
profit_target = config.get('exit_rules.profit_targets.high_confidence', default=0.25)
```

### Phase 4-5: Method-Based Configuration (Planned)

**Complete configuration bundled as "Methods"**

```
Priority: Active Method Config > Database Override > YAML > Code

┌─────────────────┐
│  Active Method  │  ← Complete bundled config for this trade
│  Configuration  │     (strategy + model + position + risk + execution)
└────────┬────────┘
         │ Parameter not in method?
         ▼
┌─────────────────┐
│  User Override  │  ← User's global overrides
└────────┬────────┘
         │ Not found?
         ▼
┌─────────────────┐
│  YAML File      │  ← System defaults
└────────┬────────┘
         │ Not found?
         ▼
┌─────────────────┐
│  Code Defaults  │  ← Hardcoded fallback
└─────────────────┘
```

**See ADR-021 and USER_CUSTOMIZATION_STRATEGY_V1_0 for details.**
```

---

### 6. Add New Section: YAML Validation

**Location:** Near end of document

**Content:**

```markdown
## YAML Validation

### Validation Rules

All YAML files are validated on load to prevent configuration errors.

#### Type Validation

```yaml
# CORRECT
kelly_fraction: 0.25          # float ✓
max_position_size: 1000       # int ✓
enabled: true                 # bool ✓

# INCORRECT
kelly_fraction: "0.25"        # string ✗ (should be float)
max_position_size: 1000.5     # float ✗ (should be int)
enabled: "true"               # string ✗ (should be bool)
```

#### Range Validation

```yaml
# CORRECT
kelly_fraction: 0.25          # 0.05 ≤ value ≤ 0.50 ✓

# INCORRECT
kelly_fraction: 0.60          # > 0.50 ✗ (over-betting, dangerous)
kelly_fraction: 0.02          # < 0.05 ✗ (too conservative, system won't trade)
```

#### Required Fields

All configuration files have required fields that must be present:

```yaml
# position_management.yaml - REQUIRED FIELDS
monitoring:
  normal_frequency: 30        # Required
  urgent_frequency: 5         # Required

exit_priorities:              # Required
  CRITICAL: [...]
  HIGH: [...]
  MEDIUM: [...]
  LOW: [...]

exit_execution:               # Required
  CRITICAL: { ... }
  HIGH: { ... }
  MEDIUM: { ... }
  LOW: { ... }
```

### Validation on Startup

**System Behavior:**

```
Starting Precog Trading Platform...
├─ Loading configuration files...
│  ├─ trading.yaml ✓
│  ├─ position_management.yaml ✓
│  ├─ trade_strategies.yaml ✓
│  ├─ probability_models.yaml ✓
│  ├─ markets.yaml ✓
│  ├─ data_sources.yaml ✓
│  └─ system.yaml ✓
├─ Validating configuration...
│  ├─ Type validation ✓
│  ├─ Range validation ✓
│  ├─ Required fields ✓
│  └─ Cross-file consistency ✓
└─ Configuration loaded successfully ✓

Ready to trade.
```

**If Validation Fails:**

```
Starting Precog Trading Platform...
├─ Loading configuration files...
│  ├─ trading.yaml ✓
│  ├─ position_management.yaml ✗
│  
ERROR: Configuration validation failed

File: config/position_management.yaml
Line 15: kelly_fraction: 0.60

Error: Value out of range
  - Current: 0.60
  - Allowed: 0.05 - 0.50
  - Reason: Values > 0.50 constitute over-betting (Kelly Criterion violation)

Fix: Edit config/position_management.yaml and restart

SYSTEM WILL NOT START WITH INVALID CONFIGURATION
```

### Manual Validation Command

```bash
# Validate all YAML files without starting system
$ python -m precog.config.validate

Validating configuration files...
✓ trading.yaml (52 parameters)
✓ position_management.yaml (84 parameters)
✓ trade_strategies.yaml (31 parameters)
✓ probability_models.yaml (23 parameters)
✓ markets.yaml (18 parameters)
✓ data_sources.yaml (15 parameters)
✓ system.yaml (27 parameters)

All configuration files valid ✓
```

### Common Validation Errors

**1. Invalid Type**
```yaml
# ERROR
max_position_size: "1000"  # String instead of int

# FIX
max_position_size: 1000
```

**2. Out of Range**
```yaml
# ERROR
kelly_fraction: 0.75  # > 0.50 maximum

# FIX
kelly_fraction: 0.25
```

**3. Missing Required Field**
```yaml
# ERROR
exit_priorities:
  CRITICAL: [...]
  # Missing HIGH, MEDIUM, LOW

# FIX
exit_priorities:
  CRITICAL: [...]
  HIGH: [...]
  MEDIUM: [...]
  LOW: [...]
```

**4. Invalid Reference**
```yaml
# ERROR
methods:
  my_method:
    strategy_id: 999  # Strategy doesn't exist

# FIX (check strategies table for valid IDs)
methods:
  my_method:
    strategy_id: 1
```
```

---

### 7. Update Cross-References

**Action:** Search entire CONFIGURATION_GUIDE_V3.0 and update references:

**Old References → New References:**
- "monitoring frequency: 60s" → "monitoring frequency: 30s normal, 5s urgent"
- "exit conditions: 11" → "exit conditions: 10 (edge_reversal removed)"
- "single partial exit" → "two-stage partial exits (50% at +15%, 25% at +25%)"
- References to Phase 1.5 → Clarify as "planned, not yet implemented"
- References to ADR-020 → Add references to ADR-021 where relevant

---

### 8. Add Consistency Check Section

**Location:** Appendix

**Content:**

```markdown
## Appendix A: Configuration Consistency Check

Use this checklist to verify configuration consistency across files.

### Core Parameters Alignment

#### Kelly Fractions

| File | Parameter | Value | Status |
|------|-----------|-------|--------|
| trading.yaml | kelly.default_fraction | 0.25 | ✓ Must match |
| trading.yaml | kelly.sport_fractions.nfl | 0.25 | ✓ NFL specific |
| trading.yaml | kelly.sport_fractions.nba | 0.22 | ✓ NBA specific |
| trading.yaml | kelly.sport_fractions.tennis | 0.18 | ✓ Tennis specific |

**Verification:**
```bash
$ grep -r "kelly_fraction" config/*.yaml
```

#### Position Limits

| File | Parameter | Value | Status |
|------|-----------|-------|--------|
| trading.yaml | position_limits.max_position_size_dollars | 1000 | ✓ Must match |
| trading.yaml | position_limits.max_total_exposure_dollars | 10000 | ✓ Must match |

#### Exit Conditions

| File | Parameter | Count | Status |
|------|-----------|-------|--------|
| position_management.yaml | exit_priorities | 10 total | ✓ Correct |
| position_management.yaml | exit_priorities.CRITICAL | 2 conditions | ✓ Correct |
| position_management.yaml | exit_priorities.HIGH | 3 conditions | ✓ Correct |
| position_management.yaml | exit_priorities.MEDIUM | 2 conditions | ✓ Correct |
| position_management.yaml | exit_priorities.LOW | 3 conditions | ✓ Correct |

**Verification:**
```bash
$ python -m precog.config.audit

Running configuration audit...
├─ Parameter consistency ✓
├─ Cross-file references ✓
├─ Exit condition count ✓
└─ Type validation ✓

Audit complete: No issues found
```

### Common Inconsistencies

**1. Mismatched Kelly Fractions**
```
PROBLEM: trading.yaml has kelly_fraction: 0.25, but method config has 0.30
FIX: Methods can override defaults (this is OK)
```

**2. Out-of-Sync Limits**
```
PROBLEM: trading.yaml max_position_size: 1000, but code has 1500
FIX: Update code to read from YAML (code should not hardcode limits)
```

**3. Missing Exit Condition**
```
PROBLEM: Code references exit condition "edge_reversal" but not in YAML
FIX: Remove code references (edge_reversal was deprecated)
```

### Automated Audit

Run full consistency audit:

```bash
$ python -m precog.config.audit --verbose

Configuration Audit Report
==========================

1. Parameter Consistency
   ✓ Kelly fractions consistent across files
   ✓ Position limits consistent
   ✓ Exit priorities complete

2. Exit Conditions
   ✓ 10 conditions defined
   ✓ All conditions mapped to priorities
   ✗ WARNING: Code references deprecated 'edge_reversal'
       Location: trading/exit_evaluator.py:142
       Fix: Remove code reference

3. Type Validation
   ✓ All parameters have correct types
   ✓ All ranges valid

4. Required Fields
   ✓ All required fields present

ISSUES FOUND: 1 warning
RECOMMENDED: Update code to remove edge_reversal reference
```
```

---

## Summary of Changes

### New Sections (7)
1. Position Monitoring Configuration
2. Exit Priority & Execution Configuration
3. User Customization (Phase 1, 1.5, 4-5)
4. Configuration Hierarchy
5. YAML Validation
6. Consistency Check (Appendix)
7. Method-Based Configuration (cross-ref to ADR-021)

### Updated Sections (3)
1. Position Management (add 2nd partial exit, liquidity)
2. Cross-References (monitoring freq, exit count, etc.)
3. Examples (update to match new parameters)

### Removed Content (1)
1. edge_reversal references (deprecated)

---

## Implementation Checklist

**Phase 1: Structural Updates (2 hours)**
- [ ] Add 7 new sections with proper headers
- [ ] Update table of contents
- [ ] Add cross-references between sections
- [ ] Add version header (V3.0 → V3.1)

**Phase 2: Content Updates (2 hours)**
- [ ] Write Position Monitoring section with examples
- [ ] Write Exit Priority & Execution section with flowcharts
- [ ] Write User Customization section (import from USER_CUSTOMIZATION_STRATEGY)
- [ ] Write Configuration Hierarchy section with diagrams
- [ ] Write YAML Validation section with examples

**Phase 3: Consistency Updates (1 hour)**
- [ ] Update all "60s" references to "30s normal, 5s urgent"
- [ ] Update "11 exit conditions" to "10 exit conditions"
- [ ] Remove all edge_reversal references
- [ ] Update partial exits to two-stage
- [ ] Add liquidity threshold documentation

**Phase 4: Quality Assurance (1 hour)**
- [ ] Verify all code examples are correct
- [ ] Verify all YAML snippets are valid
- [ ] Check all cross-references work
- [ ] Run spell check
- [ ] Verify consistency with other docs (MASTER_REQUIREMENTS, ADR-021, etc.)

**Total Estimated Time: 6 hours**

---

## Validation

After updates, verify:

1. **Alignment with MASTER_REQUIREMENTS_V2.5**
   - All REQ-MON-* requirements documented
   - All REQ-EXIT-* requirements documented

2. **Alignment with YAML_CONSISTENCY_AUDIT_V1_0**
   - All identified gaps addressed
   - All new sections documented

3. **Alignment with ADR-021**
   - Method abstraction properly explained
   - Configuration hierarchy clear

4. **Alignment with USER_CUSTOMIZATION_STRATEGY_V1_0**
   - User customization properly documented
   - Safe ranges provided
   - Safety constraints explained

5. **Internal Consistency**
   - No conflicting parameter values
   - No broken cross-references
   - No deprecated content

---

## Success Criteria

**CONFIGURATION_GUIDE_V3.1 is complete when:**

✅ All 7 new sections written and integrated  
✅ All Session 7 enhancements documented  
✅ All user customization options explained  
✅ All safety constraints clearly marked  
✅ All examples tested and validated  
✅ All cross-references working  
✅ Passes consistency check against other docs  
✅ No references to deprecated features  

---

**Document:** CONFIGURATION_GUIDE_UPDATE_SPEC_V1_0.md  
**Created:** 2025-10-21  
**Purpose:** Comprehensive update specification for CONFIGURATION_GUIDE_V3.0 → V3.1  
**Related:** YAML_CONSISTENCY_AUDIT_V1_0, USER_CUSTOMIZATION_STRATEGY_V1_0, ADR-021  
**Status:** ✅ Complete - Ready for Implementation
