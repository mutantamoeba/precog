# ADR-021: Method Abstraction Layer

**Status:** ✅ Accepted (Design), 🔵 Pending Implementation  
**Date:** 2025-10-21  
**Phase:** 0.5 (Design), 4-5 (Implementation)  
**Supersedes:** None  
**Related:** ADR-019 (Immutable Versions), ADR-002 (Database Versioning)

---

## Context

**Problem:** Trade attribution is incomplete.

**Current Attribution (Phase 0.5):**
```sql
SELECT 
    t.trade_id,
    s.strategy_name,      -- "halftime_entry"
    s.strategy_version,   -- "v1.0"
    m.model_name,         -- "elo_nfl"
    m.model_version       -- "v1.0"
FROM trades t
JOIN strategies s ON t.strategy_id = s.strategy_id
JOIN probability_models m ON t.model_id = m.model_id;
```

**What's Missing:**
- ❌ Position management rules used (trailing stop config, exit thresholds)
- ❌ Risk parameters applied (Kelly fraction, position limits)
- ❌ Execution algorithm used (simple limit vs advanced)
- ❌ Sport-specific parameters (NFL vs NBA vs Tennis configs)

**Why It Matters:**

1. **Incomplete A/B Testing**
   - Can compare strategies and models
   - Cannot compare complete trading approaches
   - Example: "Conservative" vs "Aggressive" differs in 6+ dimensions

2. **Configuration Drift**
   - Position management YAML changes over time
   - Risk parameters tuned between trades
   - Cannot reproduce historical trades exactly

3. **Performance Attribution**
   - Is poor performance due to bad strategy? Bad model? Bad risk params?
   - Cannot isolate which component needs improvement

**Real-World Example:**

Two traders want different approaches:
```yaml
# Trader A: "Conservative NFL"
- Strategy: halftime_entry (enter at halftime only)
- Model: elo_nfl (proven model)
- Position Mgmt: Tight trailing stops (3%), exit at 15% profit
- Risk: Kelly 0.15, max position $500
- Execution: Simple limit orders
- Sport Config: NFL only, min_volume 200

# Trader B: "Aggressive NFL"  
- Strategy: live_continuous (trade momentum changes)
- Model: ensemble_nfl (higher-variance model)
- Position Mgmt: Loose trailing stops (7%), hold for 30% profit
- Risk: Kelly 0.25, max position $1000
- Execution: Dynamic Depth Walker (Phase 8)
- Sport Config: NFL, min_volume 50

# Question: Which approach is better?
# Current System: Cannot compare (too many variables in YAML)
# With Methods: `SELECT method_name, AVG(roi) FROM trades GROUP BY method_name`
```

---

## Decision

**Introduce "Method" abstraction layer** that bundles:
- Strategy (entry logic)
- Probability Model (edge calculation)
- Position Management Config (exit rules)
- Risk Config (sizing, limits)
- Execution Config (order types, algorithms)
- Sport-Specific Config (per-sport parameters)

**Key Properties:**
- Methods are IMMUTABLE versions (same pattern as strategies/models)
- Trades link to method_id for complete attribution
- Methods can be exported/imported/shared
- A/B testing at method level
- Templates for common approaches

---

## Architecture Design

### 1. Database Schema

```sql
-- ============================================
-- METHODS TABLE (Core)
-- ============================================
CREATE TABLE methods (
    method_id SERIAL PRIMARY KEY,
    
    -- Identity
    method_name VARCHAR(100) NOT NULL,
    method_version VARCHAR(20) NOT NULL,
    description TEXT,
    
    -- Component Links (immutable references)
    strategy_id INT NOT NULL REFERENCES strategies(strategy_id),
    model_id INT NOT NULL REFERENCES probability_models(model_id),
    
    -- Position Management Config (IMMUTABLE)
    position_mgmt_config JSONB NOT NULL,
    /* Example:
    {
        "trailing_stop": {
            "activation_threshold": 0.10,
            "initial_distance": 0.05,
            "tightening_rate": 0.01,
            "floor_distance": 0.02
        },
        "profit_targets": {
            "high_confidence": 0.25,
            "medium_confidence": 0.20,
            "low_confidence": 0.15
        },
        "stop_loss": {
            "high_confidence": -0.15,
            "medium_confidence": -0.12,
            "low_confidence": -0.08
        },
        "partial_exits": {
            "enabled": true,
            "first_exit": {
                "profit_threshold": 0.15,
                "percentage": 50
            },
            "second_exit": {
                "profit_threshold": 0.25,
                "percentage": 25
            }
        },
        "scaling": {
            "scale_in": {
                "enabled": true,
                "edge_increase_threshold": 0.05,
                "max_additions": 2
            },
            "scale_out": {
                "enabled": true,
                "edge_decrease_threshold": 0.02
            }
        },
        "early_exit": {
            "edge_threshold": 0.02,
            "enabled": true
        }
    }
    */
    
    -- Risk Config (IMMUTABLE)
    risk_config JSONB NOT NULL,
    /* Example:
    {
        "kelly_fraction": 0.25,
        "max_position_size_dollars": 1000,
        "max_total_exposure_dollars": 10000,
        "max_correlated_exposure_dollars": 5000,
        "min_edge_threshold": 0.05,
        "daily_loss_limit_dollars": 500,
        "circuit_breakers": {
            "consecutive_losses": 5,
            "rapid_loss_dollars": 200,
            "rapid_loss_minutes": 15
        }
    }
    */
    
    -- Execution Config (IMMUTABLE)
    execution_config JSONB NOT NULL,
    /* Example:
    {
        "algorithm": "simple_limit",
        "default_order_type": "limit",
        "max_slippage_percent": 0.02,
        "order_timeout_seconds": 30,
        "partial_fills": true,
        "advanced_params": {
            "dynamic_depth_walker": {
                "enabled": false,
                "walk_interval_seconds": 4,
                "max_walks": 10,
                "min_volume_threshold": 50
            }
        }
    }
    */
    
    -- Sport-Specific Config (IMMUTABLE)
    sport_config JSONB NOT NULL,
    /* Example:
    {
        "nfl": {
            "enabled": true,
            "kelly_fraction_override": 0.25,
            "min_volume": 100,
            "max_spread": 0.08,
            "time_restrictions": {
                "pregame_hours": 2,
                "postgame_minutes": 30
            }
        },
        "nba": {
            "enabled": true,
            "kelly_fraction_override": 0.22,
            "min_volume": 75,
            "max_spread": 0.10
        },
        "tennis": {
            "enabled": false
        }
    }
    */
    
    -- Configuration Hash (for quick comparison)
    config_hash VARCHAR(64) NOT NULL,
    -- MD5(strategy_id || model_id || position_mgmt_config || risk_config || execution_config || sport_config)
    
    -- Lifecycle Management
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    -- 'draft' → 'testing' → 'active' → 'inactive' → 'deprecated'
    CHECK (status IN ('draft', 'testing', 'active', 'inactive', 'deprecated')),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100),
    activated_at TIMESTAMP,
    deactivated_at TIMESTAMP,
    
    -- Performance Metrics (MUTABLE - updated as trades execute)
    paper_trades_count INT DEFAULT 0,
    paper_roi DECIMAL(10,4),
    paper_sharpe DECIMAL(10,4),
    paper_win_rate DECIMAL(6,4),
    
    live_trades_count INT DEFAULT 0,
    live_roi DECIMAL(10,4),
    live_sharpe DECIMAL(10,4),
    live_win_rate DECIMAL(6,4),
    
    -- Notes
    notes TEXT,
    
    -- Constraints
    UNIQUE(method_name, method_version),
    CHECK (method_version ~ '^v[0-9]+\.[0-9]+$')  -- Enforce vX.Y format
);

-- Indexes
CREATE INDEX idx_methods_status ON methods(status);
CREATE INDEX idx_methods_strategy ON methods(strategy_id);
CREATE INDEX idx_methods_model ON methods(model_id);
CREATE INDEX idx_methods_hash ON methods(config_hash);
CREATE INDEX idx_methods_name_version ON methods(method_name, method_version);

-- ============================================
-- METHOD TEMPLATES (Reusable Configs)
-- ============================================
CREATE TABLE method_templates (
    template_id SERIAL PRIMARY KEY,
    
    -- Identity
    template_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    category VARCHAR(50),  -- 'conservative', 'aggressive', 'moderate', 'experimental'
    
    -- Default Configs (can be overridden when creating method)
    position_mgmt_config JSONB NOT NULL,
    risk_config JSONB NOT NULL,
    execution_config JSONB NOT NULL,
    sport_config JSONB NOT NULL,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100),
    is_public BOOLEAN DEFAULT TRUE,
    usage_count INT DEFAULT 0,  -- How many methods created from this template
    
    notes TEXT
);

-- Seed templates
INSERT INTO method_templates (template_name, category, description, position_mgmt_config, risk_config, execution_config, sport_config) VALUES
('conservative', 'conservative', 'Low-risk approach with tight stops and early exits', 
    '{"trailing_stop": {"activation_threshold": 0.10, "initial_distance": 0.03}, "profit_targets": {"high_confidence": 0.15}}'::jsonb,
    '{"kelly_fraction": 0.15, "max_position_size_dollars": 500}'::jsonb,
    '{"algorithm": "simple_limit", "max_slippage_percent": 0.015}'::jsonb,
    '{"nfl": {"enabled": true, "min_volume": 200}, "nba": {"enabled": true, "min_volume": 150}}'::jsonb
),
('aggressive', 'aggressive', 'High-risk approach targeting bigger gains',
    '{"trailing_stop": {"activation_threshold": 0.15, "initial_distance": 0.07}, "profit_targets": {"high_confidence": 0.30}}'::jsonb,
    '{"kelly_fraction": 0.25, "max_position_size_dollars": 1000}'::jsonb,
    '{"algorithm": "simple_limit", "max_slippage_percent": 0.025}'::jsonb,
    '{"nfl": {"enabled": true, "min_volume": 100}, "nba": {"enabled": true, "min_volume": 75}}'::jsonb
),
('moderate', 'moderate', 'Balanced approach between risk and return',
    '{"trailing_stop": {"activation_threshold": 0.12, "initial_distance": 0.05}, "profit_targets": {"high_confidence": 0.20}}'::jsonb,
    '{"kelly_fraction": 0.20, "max_position_size_dollars": 750}'::jsonb,
    '{"algorithm": "simple_limit", "max_slippage_percent": 0.020}'::jsonb,
    '{"nfl": {"enabled": true, "min_volume": 150}, "nba": {"enabled": true, "min_volume": 100}}'::jsonb
);

-- ============================================
-- TRADE ATTRIBUTION UPDATES
-- ============================================

-- Add method_id to edges and trades tables
ALTER TABLE edges ADD COLUMN method_id INT REFERENCES methods(method_id);
ALTER TABLE trades ADD COLUMN method_id INT REFERENCES methods(method_id);

CREATE INDEX idx_edges_method ON edges(method_id);
CREATE INDEX idx_trades_method ON trades(method_id);

-- ============================================
-- HELPER VIEWS
-- ============================================

-- Active methods
CREATE VIEW active_methods AS
SELECT * FROM methods
WHERE status = 'active'
ORDER BY method_name, method_version DESC;

-- Method performance comparison
CREATE VIEW method_performance AS
SELECT
    m.method_id,
    m.method_name,
    m.method_version,
    m.status,
    s.strategy_name,
    pm.model_name,
    m.live_trades_count,
    m.live_roi,
    m.live_sharpe,
    m.live_win_rate,
    m.activated_at,
    COUNT(t.trade_id) as actual_trade_count,
    AVG(t.edge_at_execution) as avg_edge,
    SUM(CASE WHEN t.price > 0 THEN 1 ELSE 0 END)::FLOAT / 
        NULLIF(COUNT(t.trade_id), 0) as actual_win_rate
FROM methods m
LEFT JOIN strategies s ON m.strategy_id = s.strategy_id
LEFT JOIN probability_models pm ON m.model_id = pm.model_id
LEFT JOIN trades t ON m.method_id = t.method_id
WHERE m.status IN ('active', 'inactive')
GROUP BY m.method_id, m.method_name, m.method_version, m.status,
         s.strategy_name, pm.model_name, m.live_trades_count,
         m.live_roi, m.live_sharpe, m.live_win_rate, m.activated_at
ORDER BY m.live_roi DESC NULLS LAST;

-- Complete trade attribution
CREATE VIEW complete_trade_attribution AS
SELECT
    t.trade_id,
    t.created_at,
    t.side,
    t.price,
    t.quantity,
    
    -- Market
    mk.ticker as market_ticker,
    mk.title as market_title,
    
    -- Method
    m.method_name,
    m.method_version,
    
    -- Strategy
    s.strategy_name,
    s.strategy_version,
    s.config as strategy_config,
    
    -- Model
    pm.model_name,
    pm.model_version,
    pm.config as model_config,
    
    -- Method Configs
    m.position_mgmt_config,
    m.risk_config,
    m.execution_config,
    m.sport_config,
    
    -- Trade Context
    t.edge_at_execution,
    t.confidence_at_execution
    
FROM trades t
JOIN markets mk ON t.market_id = mk.market_id
LEFT JOIN methods m ON t.method_id = m.method_id
LEFT JOIN strategies s ON m.strategy_id = s.strategy_id
LEFT JOIN probability_models pm ON m.model_id = pm.model_id
ORDER BY t.created_at DESC;
```

### 2. Python Implementation

```python
# models/method.py

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional
import hashlib
import json

@dataclass
class Method:
    """
    Complete trading method specification.
    
    Bundles strategy, model, position management, risk, and execution configs.
    Methods are immutable once created (same pattern as strategies/models).
    """
    
    method_id: Optional[int] = None
    method_name: str = None
    method_version: str = None
    description: str = ""
    
    # Component links
    strategy_id: int = None
    model_id: int = None
    
    # Immutable configs
    position_mgmt_config: Dict = None
    risk_config: Dict = None
    execution_config: Dict = None
    sport_config: Dict = None
    
    # Lifecycle
    status: str = "draft"
    created_by: str = None
    
    # Performance (mutable)
    paper_trades_count: int = 0
    paper_roi: Optional[Decimal] = None
    live_trades_count: int = 0
    live_roi: Optional[Decimal] = None
    
    def __post_init__(self):
        """Generate config hash."""
        self.config_hash = self._generate_hash()
    
    def _generate_hash(self) -> str:
        """Generate MD5 hash of all configs for comparison."""
        config_string = json.dumps({
            "strategy_id": self.strategy_id,
            "model_id": self.model_id,
            "position_mgmt": self.position_mgmt_config,
            "risk": self.risk_config,
            "execution": self.execution_config,
            "sport": self.sport_config
        }, sort_keys=True)
        
        return hashlib.md5(config_string.encode()).hexdigest()
    
    @classmethod
    def from_template(
        cls,
        method_name: str,
        method_version: str,
        strategy_id: int,
        model_id: int,
        template_name: str = "moderate",
        overrides: Optional[Dict] = None
    ):
        """
        Create method from template.
        
        Args:
            method_name: Unique method name
            method_version: Version (e.g., "v1.0")
            strategy_id: Strategy to use
            model_id: Model to use
            template_name: Template to base configs on
            overrides: Optional config overrides
            
        Example:
            >>> method = Method.from_template(
            ...     method_name="my_conservative_nfl",
            ...     method_version="v1.0",
            ...     strategy_id=1,
            ...     model_id=2,
            ...     template_name="conservative",
            ...     overrides={
            ...         "risk_config": {"kelly_fraction": 0.18}
            ...     }
            ... )
        """
        # Load template from database
        template = MethodTemplate.get_by_name(template_name)
        
        # Start with template configs
        position_mgmt = template.position_mgmt_config
        risk = template.risk_config
        execution = template.execution_config
        sport = template.sport_config
        
        # Apply overrides
        if overrides:
            if "position_mgmt_config" in overrides:
                position_mgmt.update(overrides["position_mgmt_config"])
            if "risk_config" in overrides:
                risk.update(overrides["risk_config"])
            if "execution_config" in overrides:
                execution.update(overrides["execution_config"])
            if "sport_config" in overrides:
                sport.update(overrides["sport_config"])
        
        return cls(
            method_name=method_name,
            method_version=method_version,
            strategy_id=strategy_id,
            model_id=model_id,
            position_mgmt_config=position_mgmt,
            risk_config=risk,
            execution_config=execution,
            sport_config=sport
        )
    
    def validate(self) -> bool:
        """
        Validate method configuration.
        
        Ensures all components are compatible and configs are valid.
        """
        errors = []
        
        # 1. Validate version format
        import re
        if not re.match(r'^v\d+\.\d+$', self.method_version):
            errors.append(f"Invalid version format: {self.method_version}")
        
        # 2. Validate configs are complete
        required_position = ["trailing_stop", "profit_targets", "stop_loss"]
        for key in required_position:
            if key not in self.position_mgmt_config:
                errors.append(f"Missing position_mgmt_config key: {key}")
        
        required_risk = ["kelly_fraction", "max_position_size_dollars"]
        for key in required_risk:
            if key not in self.risk_config:
                errors.append(f"Missing risk_config key: {key}")
        
        # 3. Validate component compatibility
        strategy = Strategy.get_by_id(self.strategy_id)
        
        # Aggressive strategies should have higher Kelly fraction
        if "aggressive" in strategy.strategy_name:
            if self.risk_config["kelly_fraction"] < 0.20:
                errors.append(
                    f"Aggressive strategy requires kelly >= 0.20, "
                    f"got {self.risk_config['kelly_fraction']}"
                )
        
        # 4. Validate sport configs
        if not any(sport_cfg.get("enabled") for sport_cfg in self.sport_config.values()):
            errors.append("At least one sport must be enabled")
        
        if errors:
            raise ValidationError(f"Method validation failed: {errors}")
        
        return True
    
    def get_config_for_sport(self, sport: str) -> Dict:
        """Get sport-specific configuration."""
        base_config = {
            "position_mgmt": self.position_mgmt_config,
            "risk": self.risk_config,
            "execution": self.execution_config
        }
        
        # Apply sport-specific overrides
        if sport in self.sport_config:
            sport_overrides = self.sport_config[sport]
            
            # Override Kelly fraction if specified
            if "kelly_fraction_override" in sport_overrides:
                base_config["risk"]["kelly_fraction"] = \
                    sport_overrides["kelly_fraction_override"]
            
            # Add sport-specific constraints
            base_config["sport_constraints"] = sport_overrides
        
        return base_config
    
    def export(self) -> Dict:
        """Export method as JSON for sharing."""
        return {
            "method_name": self.method_name,
            "method_version": self.method_version,
            "description": self.description,
            "strategy": {
                "name": Strategy.get_by_id(self.strategy_id).strategy_name,
                "version": Strategy.get_by_id(self.strategy_id).strategy_version
            },
            "model": {
                "name": ProbabilityModel.get_by_id(self.model_id).model_name,
                "version": ProbabilityModel.get_by_id(self.model_id).model_version
            },
            "configs": {
                "position_mgmt": self.position_mgmt_config,
                "risk": self.risk_config,
                "execution": self.execution_config,
                "sport": self.sport_config
            },
            "config_hash": self.config_hash
        }
    
    @classmethod
    def import_from_json(cls, data: Dict):
        """Import method from exported JSON."""
        # Look up strategy and model by name/version
        strategy = Strategy.get_by_name_version(
            data["strategy"]["name"],
            data["strategy"]["version"]
        )
        model = ProbabilityModel.get_by_name_version(
            data["model"]["name"],
            data["model"]["version"]
        )
        
        return cls(
            method_name=data["method_name"],
            method_version=data["method_version"],
            description=data.get("description", ""),
            strategy_id=strategy.strategy_id,
            model_id=model.model_id,
            position_mgmt_config=data["configs"]["position_mgmt"],
            risk_config=data["configs"]["risk"],
            execution_config=data["configs"]["execution"],
            sport_config=data["configs"]["sport"]
        )


# managers/method_manager.py

class MethodManager:
    """Manages method lifecycle and operations."""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def create_method(
        self,
        method_name: str,
        method_version: str,
        strategy_id: int,
        model_id: int,
        template_name: str = "moderate",
        overrides: Optional[Dict] = None
    ) -> Method:
        """
        Create new method from template.
        
        Example:
            >>> manager = MethodManager(db_session)
            >>> method = manager.create_method(
            ...     method_name="conservative_nfl",
            ...     method_version="v1.0",
            ...     strategy_id=1,
            ...     model_id=2,
            ...     template_name="conservative"
            ... )
        """
        # Create from template
        method = Method.from_template(
            method_name=method_name,
            method_version=method_version,
            strategy_id=strategy_id,
            model_id=model_id,
            template_name=template_name,
            overrides=overrides
        )
        
        # Validate
        method.validate()
        
        # Save to database
        self.db.add(method)
        self.db.commit()
        
        return method
    
    def activate_method(self, method_id: int):
        """Activate method for live trading."""
        method = self.db.query(Method).get(method_id)
        
        # Validation before activation
        if method.status != "testing":
            raise ValueError(f"Can only activate methods in 'testing' status")
        
        if method.paper_trades_count < 10:
            raise ValueError("Need at least 10 paper trades before activating")
        
        if method.paper_roi < 0:
            raise ValueError("Cannot activate method with negative paper ROI")
        
        # Activate
        method.status = "active"
        method.activated_at = datetime.now()
        self.db.commit()
    
    def compare_methods(self, method_ids: List[int]) -> pd.DataFrame:
        """
        Compare performance of multiple methods.
        
        Returns:
            DataFrame with side-by-side comparison
        """
        query = """
        SELECT
            method_name,
            method_version,
            live_trades_count,
            live_roi,
            live_sharpe,
            live_win_rate
        FROM methods
        WHERE method_id = ANY(:method_ids)
        ORDER BY live_roi DESC
        """
        
        return pd.read_sql(query, self.db.bind, params={"method_ids": method_ids})
    
    def get_config_for_trade(self, method_id: int, sport: str) -> Dict:
        """
        Get complete config for executing a trade.
        
        Used by trading engine to get all parameters.
        """
        method = self.db.query(Method).get(method_id)
        return method.get_config_for_sport(sport)
```

---

## Usage Examples

### Creating Methods

```python
# Create conservative NFL method
conservative_nfl = MethodManager(db).create_method(
    method_name="conservative_nfl",
    method_version="v1.0",
    strategy_id=1,  # halftime_entry v1.0
    model_id=2,     # elo_nfl v1.0
    template_name="conservative",
    overrides={
        "sport_config": {
            "nfl": {"enabled": True, "min_volume": 200},
            "nba": {"enabled": False}
        }
    }
)

# Create aggressive multi-sport method
aggressive_multi = MethodManager(db).create_method(
    method_name="aggressive_multi",
    method_version="v1.0",
    strategy_id=3,  # live_continuous v1.0
    model_id=4,     # ensemble_nfl v1.0
    template_name="aggressive",
    overrides={
        "risk_config": {
            "kelly_fraction": 0.28  # Extra aggressive
        },
        "sport_config": {
            "nfl": {"enabled": True, "kelly_fraction_override": 0.28},
            "nba": {"enabled": True, "kelly_fraction_override": 0.25},
            "tennis": {"enabled": True, "kelly_fraction_override": 0.22}
        }
    }
)
```

### Trade Attribution

```python
# When placing trade, link to method
def execute_trade(edge_id, method_id):
    """Execute trade with full attribution."""
    
    # Get method config
    method = Method.get_by_id(method_id)
    config = method.get_config_for_sport(edge.sport)
    
    # Calculate position size using method's Kelly fraction
    kelly = config["risk"]["kelly_fraction"]
    size = calculate_kelly_size(edge, kelly)
    
    # Place order using method's execution config
    order = place_order(
        market=edge.market_id,
        side=edge.side,
        size=size,
        execution_config=config["execution"]
    )
    
    # Record trade with method attribution
    trade = Trade(
        market_id=edge.market_id,
        edge_id=edge.edge_id,
        method_id=method_id,  # ← Complete attribution
        strategy_id=method.strategy_id,
        model_id=method.model_id,
        order_id=order.order_id,
        price=order.filled_price,
        quantity=order.filled_quantity
    )
    
    db.add(trade)
    db.commit()
```

### A/B Testing

```python
# Compare two methods
comparison = MethodManager(db).compare_methods([
    conservative_nfl.method_id,
    aggressive_nfl.method_id
])

print(comparison)
# Output:
#   method_name         | live_roi | live_trades | live_sharpe
#   conservative_nfl    | 0.1250   | 42          | 1.8
#   aggressive_nfl      | 0.1100   | 38          | 1.2

# Query: Which specific configs differ?
query = """
SELECT 
    m1.method_name as method_1,
    m2.method_name as method_2,
    m1.risk_config->'kelly_fraction' as kelly_1,
    m2.risk_config->'kelly_fraction' as kelly_2,
    m1.position_mgmt_config->'trailing_stop'->'initial_distance' as stop_1,
    m2.position_mgmt_config->'trailing_stop'->'initial_distance' as stop_2
FROM methods m1, methods m2
WHERE m1.method_id = 1 AND m2.method_id = 2
"""
```

### Exporting and Sharing

```python
# Export method as JSON
method_json = conservative_nfl.export()

# Save to file
with open("conservative_nfl_v1.0.json", "w") as f:
    json.dump(method_json, f, indent=2)

# Import someone else's method
with open("expert_trader_method.json") as f:
    imported_data = json.load(f)

imported_method = Method.import_from_json(imported_data)
db.add(imported_method)
db.commit()
```

---

## Implementation Phases

### Phase 0.5 (Current - Design Only)
**Deliverables:**
- ✅ ADR-021 (this document)
- ✅ Database schema design
- ✅ Requirements (REQ-METH-001 through REQ-METH-015)
- ✅ Update MASTER_REQUIREMENTS
- ✅ Placeholder in DATABASE_SCHEMA_SUMMARY V1.5

**Success Criteria:**
- [ ] Complete schema designed
- [ ] All requirements documented
- [ ] Schema ready for Phase 4 implementation

### Phase 4 (Weeks 7-8) - Model Versioning Implementation
**Deliverables:**
- Create `methods` table
- Create `method_templates` table
- Implement Method class
- Implement MethodManager
- Add method_id to edges and trades

**Success Criteria:**
- [ ] Can create methods from templates
- [ ] Methods validate on creation
- [ ] Methods export/import correctly
- [ ] Method templates seeded in database

### Phase 5 (Weeks 9-12) - Trade Attribution
**Deliverables:**
- Link trades to methods
- Update trade execution to use method configs
- Implement method comparison queries
- Build method performance views

**Success Criteria:**
- [ ] All new trades link to method_id
- [ ] Can query trades by method
- [ ] Method performance metrics update
- [ ] A/B testing works

---

## Requirements

### REQ-METH-001: Method Creation
System SHALL support creating methods from templates with optional config overrides.

### REQ-METH-002: Method Immutability
Method configs (position_mgmt, risk, execution, sport) SHALL be immutable once method is created.

### REQ-METH-003: Method Versioning
Methods SHALL use semantic versioning (vX.Y format). Config changes require new version.

### REQ-METH-004: Trade Attribution
All trades SHALL link to method_id for complete attribution.

### REQ-METH-005: Method Lifecycle
Methods SHALL support lifecycle: draft → testing → active → inactive → deprecated.

### REQ-METH-006: Method Validation
System SHALL validate method configs before activation (compatibility, completeness).

### REQ-METH-007: Method Templates
System SHALL provide reusable templates (conservative, aggressive, moderate).

### REQ-METH-008: Sport-Specific Configs
Methods SHALL support sport-specific parameter overrides.

### REQ-METH-009: Method Comparison
System SHALL support A/B testing at method level with performance metrics.

### REQ-METH-010: Method Export/Import
Methods SHALL be exportable as JSON and importable from JSON.

### REQ-METH-011: Config Hash
System SHALL generate config hash for quick method comparison.

### REQ-METH-012: Performance Tracking
System SHALL track paper and live performance metrics per method.

### REQ-METH-013: Complete Attribution View
System SHALL provide view showing complete trade attribution (method + all components).

### REQ-METH-014: Active Method Query
System SHALL provide efficient query for active methods only.

### REQ-METH-015: Method Component Links
Methods SHALL link to specific strategy_id and model_id (immutable references).

---

## Migration Strategy

### Backward Compatibility

**Existing trades (without method_id):**
```sql
-- Trades before Phase 4 won't have method_id
-- That's OK - method_id is nullable
SELECT * FROM trades WHERE method_id IS NULL;  -- Legacy trades
```

**Creating "legacy" method:**
```python
# Can create a "legacy_v1" method representing old configuration
legacy_method = Method(
    method_name="legacy",
    method_version="v1.0",
    strategy_id=1,
    model_id=1,
    position_mgmt_config=load_from_yaml("position_management.yaml"),
    risk_config=load_from_yaml("trading.yaml", "risk"),
    execution_config={"algorithm": "simple_limit"},
    sport_config={"nfl": {"enabled": True}}
)

# Optionally backfill old trades
UPDATE trades 
SET method_id = legacy_method.method_id
WHERE method_id IS NULL AND created_at < '2025-11-01';
```

---

## Alternative Approaches Considered

### Option 1: Separate Tables Per Config Type
```sql
CREATE TABLE position_management_configs (...);
CREATE TABLE risk_configs (...);
CREATE TABLE execution_configs (...);
```

**Rejected Because:**
- ❌ 4 tables instead of 1 (complexity)
- ❌ Requires 4 foreign keys per method
- ❌ Harder to export/import complete method
- ❌ JSONB is perfect for semi-structured config

### Option 2: Config in YAML Only (No Database)
```yaml
# methods/conservative_nfl_v1.0.yaml
strategy: halftime_entry v1.0
model: elo_nfl v1.0
position_mgmt: {...}
```

**Rejected Because:**
- ❌ Cannot link trades to method version
- ❌ Configuration drift over time
- ❌ Cannot query/compare methods in SQL
- ❌ Harder to validate compatibility

### Option 3: Everything in Single Config JSONB
```sql
CREATE TABLE methods (
    method_id SERIAL PRIMARY KEY,
    all_config JSONB  -- Everything in one blob
);
```

**Rejected Because:**
- ❌ Cannot link to strategy/model tables (no FKs)
- ❌ Harder to query specific config sections
- ❌ Less type safety
- ❌ Harder to validate

---

## Performance Considerations

**Storage:**
- JSONB configs: ~1-2KB per method
- Expected methods: 50-100 in first year
- Total storage: <200KB (negligible)

**Query Performance:**
- method_id indexed on trades: O(1) lookup
- Config hash indexed: Fast duplicate detection
- JSONB queries: Use GIN indexes if needed

**Optimization:**
```sql
-- If JSONB queries slow, add GIN index
CREATE INDEX idx_methods_position_config 
ON methods USING GIN (position_mgmt_config);

-- Query specific config
SELECT * FROM methods
WHERE position_mgmt_config->>'trailing_stop'->'activation_threshold' > '0.10';
```

---

## Testing Strategy

### Unit Tests
```python
def test_method_creation():
    """Test creating method from template."""
    method = Method.from_template(
        method_name="test_method",
        method_version="v1.0",
        strategy_id=1,
        model_id=1,
        template_name="conservative"
    )
    assert method.config_hash is not None

def test_method_validation():
    """Test method validation catches errors."""
    method = Method(...)
    method.risk_config = {}  # Missing required keys
    
    with pytest.raises(ValidationError):
        method.validate()

def test_method_immutability():
    """Test that configs cannot be changed."""
    method = Method(...)
    db.add(method)
    db.commit()
    
    # Try to change config
    method.risk_config["kelly_fraction"] = 0.50
    
    # Should fail (or be prevented by ORM)
    with pytest.raises(ImmutabilityError):
        db.commit()
```

### Integration Tests
```python
def test_complete_trade_attribution():
    """Test that trades link to methods correctly."""
    method = create_method()
    edge = create_edge()
    
    trade = execute_trade(edge.edge_id, method.method_id)
    
    # Query complete attribution
    attribution = db.query(CompleteTradeAttribution).filter_by(
        trade_id=trade.trade_id
    ).first()
    
    assert attribution.method_name == method.method_name
    assert attribution.strategy_name is not None
    assert attribution.model_name is not None
    assert attribution.position_mgmt_config is not None
```

---

## Documentation References

- **DATABASE_SCHEMA_SUMMARY_V1.5.md**: Complete methods table schema
- **MASTER_REQUIREMENTS_V2.5.md**: Requirements REQ-METH-001 through REQ-METH-015
- **VERSIONING_GUIDE.md**: Versioning patterns for methods
- **API_INTEGRATION_GUIDE.md**: How methods integrate with trading execution

---

## Approval

**Decided By:** Project Lead  
**Date:** 2025-10-21  
**Design Review:** Phase 0.5  
**Implementation:** Phase 4 (Models), Phase 5 (Trade Attribution)

---

## Summary

**Introduce Method abstraction layer** that bundles complete trading approach (strategy + model + position management + risk + execution + sport configs). Methods are immutable versions enabling:
- Complete trade attribution
- Cohesive A/B testing
- Configuration reproducibility
- Export/import/sharing

**Design now in Phase 0.5, implement in Phase 4/5.**
