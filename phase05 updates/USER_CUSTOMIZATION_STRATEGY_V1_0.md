# User Customization Strategy V1.0

**Version:** 1.0  
**Created:** 2025-10-21  
**Status:** ✅ Design Complete  
**Implementation:** Phase 1 (basic), Phase 1.5 (full), Phase 4-5 (methods)

---

## Purpose

Define how users can customize position management, entry, exit, and risk parameters across different phases of the Precog trading platform.

---

## Evolution Across Phases

### Phase 1: Single-User YAML Configuration

**Status:** Current  
**Customization Method:** Direct YAML editing

**Capabilities:**
- ✅ User edits `position_management.yaml`, `trading.yaml`, etc. directly
- ✅ All parameters marked with `# user-customizable` can be changed
- ✅ Changes require application restart
- ✅ Version controlled (Git)

**Limitations:**
- ❌ No runtime changes (requires restart)
- ❌ No per-trade customization
- ❌ No A/B testing
- ❌ Single configuration for all trades

**Configuration Hierarchy:**
```
Priority: YAML File > Code Defaults
```

**Example:**
```yaml
# position_management.yaml
exit_rules:
  profit_targets:
    high_confidence: 0.25  # user-customizable: Change to 0.20 for conservative
    medium_confidence: 0.20  # user-customizable
    low_confidence: 0.15  # user-customizable
```

---

### Phase 1.5: Multi-User Database Overrides

**Status:** Planned  
**Customization Method:** Webapp UI + Database

**Capabilities:**
- ✅ Each user has their own configuration overrides
- ✅ Runtime changes (no restart required)
- ✅ User-specific risk limits enforced
- ✅ Override any `# user-customizable` parameter
- ✅ Fallback to YAML if no override set

**Configuration Hierarchy:**
```
Priority: Database Override > YAML File > Code Defaults
```

**Database Schema:**
```sql
CREATE TABLE user_config_overrides (
    override_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id),
    config_key VARCHAR(200) NOT NULL,  -- e.g., "exit_rules.profit_targets.high_confidence"
    config_value JSONB NOT NULL,       -- e.g., 0.20
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, config_key)
);
```

**Example Usage:**
```python
# Config class checks hierarchy
config = Config(user_id=123)

# 1. Check database override for user 123
# 2. If not found, check YAML file
# 3. If not found, use code default
profit_target = config.get('exit_rules.profit_targets.high_confidence', default=0.25)
```

**UI Example:**
```
User Settings > Position Management > Exit Rules

Profit Target (High Confidence): [0.25] ← Edit to override YAML default
Profit Target (Medium Confidence): [0.20]
Profit Target (Low Confidence): [0.15]

[Reset to Default] [Save Changes]
```

---

### Phase 4-5: Method-Based Configuration (ADR-021)

**Status:** Designed (ADR-021)  
**Customization Method:** Method Templates + Webapp

**Capabilities:**
- ✅ Bundle complete configurations as reusable "Methods"
- ✅ Method templates: "Conservative NFL", "Aggressive NBA", "Arbitrage"
- ✅ Clone and customize templates
- ✅ A/B test different methods
- ✅ Per-method enable/disable of exit rules
- ✅ Immutable versions (reproducibility)
- ✅ Performance comparison by method

**Method Structure (from ADR-021):**
```json
{
    "method_id": 1,
    "method_name": "Conservative NFL",
    "method_version": "v1.0",
    "strategy_id": 1,  // halftime_entry v1.0
    "model_id": 1,     // elo_nfl v1.0
    
    "position_mgmt_config": {
        "trailing_stop": {
            "enabled": true,  // ← Can disable per method
            "activation_threshold": 0.10,
            "initial_distance": 0.05
        },
        "profit_targets": {
            "high_confidence": 0.20,  // ← Conservative (was 0.25)
            "medium_confidence": 0.15,
            "low_confidence": 0.10
        },
        "stop_loss": {
            "enabled": true,  // ← Can disable per method
            "high_confidence": -0.10,  // ← Tighter (was -0.15)
            "medium_confidence": -0.08,
            "low_confidence": -0.05
        },
        "partial_exits": {
            "enabled": true,  // ← Can disable per method
            "stages": [
                {"profit_threshold": 0.15, "percentage": 50},
                {"profit_threshold": 0.25, "percentage": 25}
            ]
        },
        "exit_conditions": {
            "early_exit": {"enabled": true},  // ← Can disable per method
            "edge_disappeared": {"enabled": true},
            "circuit_breaker": {"enabled": true},
            "time_based_urgent": {"enabled": true},
            "liquidity_dried_up": {"enabled": true},
            "rebalance": {"enabled": false}  // ← Disabled for conservative
        }
    },
    
    "risk_config": {
        "kelly_fraction": 0.15,  // ← More conservative (was 0.25)
        "max_position_size_dollars": 500,  // ← Smaller (was 1000)
        "max_total_exposure_dollars": 5000,
        "daily_loss_limit_dollars": 200
    },
    
    "execution_config": {
        "algorithm": "simple_limit",  // No advanced execution
        "default_order_type": "limit",
        "max_slippage_percent": 0.01  // ← Tighter (was 0.02)
    }
}
```

**User Workflow:**

1. **Select Template:**
   ```
   Method Templates:
   - Conservative NFL (tight stops, small sizes, simple execution)
   - Aggressive NFL (loose stops, larger sizes, advanced execution)
   - Arbitrage (settlement arb, high Kelly, market orders)
   - Custom (build from scratch)
   ```

2. **Customize:**
   ```
   Conservative NFL v1.0 → Clone to "My Conservative NFL v1.0"
   
   Position Management:
   - Trailing Stop: [✓ Enabled] Activation: [10%] Distance: [5%]
   - Profit Target: [✓ Enabled] High: [20%] Med: [15%] Low: [10%]
   - Stop Loss: [✓ Enabled] High: [-10%] Med: [-8%] Low: [-5%]
   - Partial Exits: [✓ Enabled]
     - Stage 1: [15%] profit → exit [50%]
     - Stage 2: [25%] profit → exit [25%]
   
   Exit Conditions:
   - [✓] Early Exit (edge drops below threshold)
   - [✓] Edge Disappeared (edge turns negative)
   - [✓] Stop Loss
   - [✓] Profit Target
   - [✓] Trailing Stop
   - [✗] Rebalance (disabled for conservative)
   
   Risk:
   - Kelly Fraction: [0.15]
   - Max Position: [$500]
   - Daily Loss Limit: [$200]
   
   [Save as v1.0] [Test in Paper Trading]
   ```

3. **A/B Test:**
   ```python
   # Trades link to method_id
   SELECT 
       m.method_name,
       COUNT(*) as trades,
       AVG(t.roi) as avg_roi,
       STDDEV(t.roi) as volatility
   FROM trades t
   JOIN methods m ON t.method_id = m.method_id
   GROUP BY m.method_name;
   
   # Result:
   # Conservative NFL: 45 trades, 8.2% avg_roi, 3.1% volatility
   # Aggressive NFL: 38 trades, 12.5% avg_roi, 7.8% volatility
   ```

4. **Version and Iterate:**
   ```
   My Conservative NFL v1.0 → (test 50 trades) → 8.2% ROI
   
   Hypothesis: Tighten profit targets to reduce risk
   
   My Conservative NFL v2.0 → (test 50 trades) → 9.1% ROI ✓ Better!
   
   Changes: profit_targets.high_confidence: 0.20 → 0.18
   ```

---

## User-Customizable Parameters

### Definition

**A parameter is "user-customizable" if:**
1. It's marked with `# user-customizable` comment in YAML
2. It's included in `user_config_overrides` database table (Phase 1.5+)
3. It's editable in Method configuration UI (Phase 4-5)
4. Changing it does NOT require code changes

**A parameter is NOT user-customizable if:**
1. It's a system constant (e.g., database connection URL)
2. Changing it would break safety constraints
3. It requires code/algorithm changes to implement

---

### Complete List of User-Customizable Parameters

#### Position Management (position_management.yaml)

**Monitoring:**
- ✅ `monitoring.normal_frequency` (30s default)
- ✅ `monitoring.urgent_frequency` (5s default)
- ✅ `monitoring.urgent_conditions.*` (all thresholds)
- ❌ `monitoring.max_api_calls_per_minute` (safety constraint)

**Trailing Stops:**
- ✅ `trailing_stop.enabled` (true/false)
- ✅ `trailing_stop.activation_threshold` (0.10 default)
- ✅ `trailing_stop.initial_distance` (0.05 default)
- ✅ `trailing_stop.tightening_rate` (0.01 default)
- ✅ `trailing_stop.floor_distance` (0.02 default)

**Profit Targets:**
- ✅ `profit_targets.high_confidence` (0.25 default)
- ✅ `profit_targets.medium_confidence` (0.20 default)
- ✅ `profit_targets.low_confidence` (0.15 default)
- ✅ `profit_targets.enabled` (true/false)

**Stop Loss:**
- ✅ `stop_loss.high_confidence` (-0.15 default)
- ✅ `stop_loss.medium_confidence` (-0.12 default)
- ✅ `stop_loss.low_confidence` (-0.08 default)
- ✅ `stop_loss.enabled` (true/false)

**Partial Exits:**
- ✅ `partial_exits.enabled` (true/false)
- ✅ `partial_exits.stages[0].profit_threshold` (0.15 default)
- ✅ `partial_exits.stages[0].percentage` (50 default)
- ✅ `partial_exits.stages[1].profit_threshold` (0.25 default)
- ✅ `partial_exits.stages[1].percentage` (25 default)

**Exit Conditions (Enable/Disable):**
- ✅ `exit_conditions.early_exit.enabled` (true/false)
- ✅ `exit_conditions.edge_disappeared.enabled` (true/false)
- ✅ `exit_conditions.rebalance.enabled` (true/false)
- ✅ `exit_conditions.liquidity_dried_up.enabled` (true/false)
- ❌ `exit_conditions.stop_loss.enabled` (always enabled for safety)
- ❌ `exit_conditions.circuit_breaker.enabled` (always enabled for safety)

**Liquidity:**
- ✅ `liquidity.max_spread` (0.03 default)
- ✅ `liquidity.min_volume` (50 default)
- ✅ `liquidity.exit_on_illiquid` (true/false)

#### Risk Management (trading.yaml)

**Kelly Sizing:**
- ✅ `kelly.default_fraction` (0.25 default)
- ✅ `kelly.sport_fractions.nfl` (0.25 default)
- ✅ `kelly.sport_fractions.nba` (0.22 default)
- ✅ `kelly.sport_fractions.tennis` (0.18 default)
- ✅ `kelly.floor` (0.0050 default)
- ✅ `kelly.cap` (0.5000 default)

**Position Limits:**
- ✅ `position_limits.max_position_size_dollars` ($1000 default)
- ✅ `position_limits.max_total_exposure_dollars` ($10000 default)
- ✅ `position_limits.max_correlated_exposure_dollars` ($5000 default)
- ✅ `position_limits.max_open_positions` (10 default)

**Loss Limits:**
- ✅ `loss_limits.daily_loss_limit_dollars` ($500 default)
- ❌ `loss_limits.circuit_breaker.consecutive_losses` (5 - safety)
- ❌ `loss_limits.circuit_breaker.rapid_loss_dollars` ($200 - safety)

**Edge Thresholds:**
- ✅ `edge_thresholds.min_edge` (0.05 default)
- ✅ `edge_thresholds.auto_execute` (0.15 default)
- ✅ `edge_thresholds.manual_review` (0.08 default)

#### Execution (trading.yaml)

**Order Execution:**
- ✅ `execution.default_order_type` (limit/market)
- ✅ `execution.max_slippage_percent` (0.02 default)
- ✅ `execution.order_timeout_seconds` (30 default)
- ✅ `execution.partial_fills` (true/false)

**Exit Execution (by priority):**
- ✅ `exit_execution.CRITICAL.timeout_seconds` (5 default)
- ✅ `exit_execution.HIGH.timeout_seconds` (10 default)
- ✅ `exit_execution.HIGH.max_walks` (2 default)
- ✅ `exit_execution.MEDIUM.timeout_seconds` (30 default)
- ✅ `exit_execution.MEDIUM.max_walks` (5 default)
- ✅ `exit_execution.LOW.timeout_seconds` (60 default)
- ✅ `exit_execution.LOW.max_walks` (10 default)

---

## Safety Constraints (NOT User-Customizable)

**These parameters are NEVER customizable for safety:**

1. **Circuit Breakers:**
   - `circuit_breaker.consecutive_losses` = 5 (hardcoded)
   - `circuit_breaker.rapid_loss_dollars` = $200 (hardcoded)
   - `circuit_breaker.rapid_loss_minutes` = 15 (hardcoded)
   - **Reason:** Prevent catastrophic losses from user misconfiguration

2. **API Rate Limits:**
   - `monitoring.max_api_calls_per_minute` = 60 (hardcoded)
   - **Reason:** Prevent API bans from Kalshi

3. **Critical Exit Conditions:**
   - `stop_loss.enabled` = true (always on)
   - `circuit_breaker.enabled` = true (always on)
   - **Reason:** Capital protection is mandatory

4. **Position Limits (Absolute Caps):**
   - User can set `max_position_size` up to $5000 maximum
   - User can set `daily_loss_limit` up to $2000 maximum
   - **Reason:** Prevent bankrupting the account

---

## Configuration Guide Updates Required

### Add to CONFIGURATION_GUIDE_V3.1.md

**New Section: User Customization**

```markdown
## User Customization

### Phase 1: YAML Editing

**How to Customize:**

1. Open `config/position_management.yaml`
2. Find parameter marked with `# user-customizable`
3. Edit value
4. Save file
5. Restart application

**Example:**
```yaml
profit_targets:
  high_confidence: 0.25  # user-customizable: Change to 0.20 for conservative approach
```

Change to:
```yaml
profit_targets:
  high_confidence: 0.20  # Changed for conservative approach
```

**Safe Ranges:**
- Kelly fractions: 0.15 - 0.35 (conservative to aggressive)
- Profit targets: 0.10 - 0.40 (10% - 40%)
- Stop losses: -0.05 to -0.25 (-5% to -25%)
- Position sizes: $100 - $5000

**Dangerous Changes:**
- Kelly > 0.50 (over-betting)
- Stop loss > -0.05 (too tight, churning)
- Stop loss < -0.30 (too loose, large losses)
- Disabling circuit breakers (NOT ALLOWED)

### Phase 1.5: Webapp UI

**How to Customize:**

1. Navigate to Settings > Position Management
2. Override any parameter
3. Save changes (no restart required)
4. Reset to default if needed

**Priority:**
- Your override > YAML default > Code default

### Phase 4-5: Method Templates

**How to Customize:**

1. Clone a method template ("Conservative NFL")
2. Customize parameters in UI
3. Enable/disable exit conditions
4. Save as new version
5. Paper trade to test
6. Compare performance vs other methods

**Per-Method Configuration:**
- Each method has its own complete config
- Can enable trailing stops in one method, disable in another
- Can use aggressive sizing in one, conservative in another
- A/B test to find best approach
```

---

## Implementation Checklist

### Phase 1 (Current)

- [ ] Mark all customizable parameters with `# user-customizable` in YAMLs
- [ ] Document safe ranges for each parameter
- [ ] Add validation to reject dangerous values
- [ ] Update CONFIGURATION_GUIDE with customization section

### Phase 1.5 (Multi-User)

- [ ] Create `user_config_overrides` table
- [ ] Implement Config class with 3-level hierarchy
- [ ] Build webapp UI for parameter overrides
- [ ] Add user-specific risk limit enforcement
- [ ] Allow runtime config changes (no restart)

### Phase 4-5 (Methods)

- [ ] Implement methods table (ADR-021)
- [ ] Create method templates ("Conservative NFL", etc.)
- [ ] Build method customization UI
- [ ] Enable per-method exit condition toggles
- [ ] Implement method versioning
- [ ] Build method performance comparison dashboard

---

## Summary

**Phase 1:** Single user, YAML editing, restart required  
**Phase 1.5:** Multi-user, database overrides, no restart  
**Phase 4-5:** Method templates, A/B testing, complete customization

**All phases support:**
- ✅ Customizing profit targets, stop losses, Kelly fractions
- ✅ Enabling/disabling exit conditions (except safety-critical ones)
- ✅ Adjusting monitoring frequency and thresholds
- ✅ Tuning partial exit rules
- ✅ Modifying liquidity thresholds

**No phase supports:**
- ❌ Disabling circuit breakers (safety)
- ❌ Exceeding API rate limits (safety)
- ❌ Bypassing position size caps (safety)

---

**Document Status:** ✅ Complete  
**Next:** Update CONFIGURATION_GUIDE_V3.0 → V3.1 with user customization section  
**Related:** ADR-021 (Method Abstraction), YAML_CONSISTENCY_AUDIT_V1_0
