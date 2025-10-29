# Precog Multi-User Implementation Plan
## Complete Guide for Claude Code Implementation

---

**Document Version:** 2.0  
**Created:** October 18, 2025  
**Purpose:** Comprehensive implementation guide addressing versioning, multi-user, position management, and system consistency  
**Target:** Claude Code CLI for automated implementation  
**Status:** Ready for Phase 1 implementation

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Issues Identified & Solutions](#critical-issues-identified--solutions)
3. [Multi-User Architecture](#multi-user-architecture)
4. [Versioning System Redesign](#versioning-system-redesign)
5. [Position & Risk Management](#position--risk-management)
6. [Trailing Stop Loss Implementation](#trailing-stop-loss-implementation)
7. [YAML Configuration Review](#yaml-configuration-review)
8. [Database Schema Updates](#database-schema-updates)
9. [Testing Strategy](#testing-strategy)
10. [30-Day Implementation Roadmap](#30-day-implementation-roadmap)
11. [Claude Code Command Examples](#claude-code-command-examples)

---

## Executive Summary

### Project Context

**Precog** is a prediction market trading system currently in Phase 0 (documentation complete). This document addresses critical design gaps discovered during architecture review and prepares the system for multi-user webapp deployment.

### Critical Issues Addressed

1. **âš ï¸ VERSIONING SYSTEM** - Current design tracks "versions" but doesn't properly integrate with objects (strategy, model, edge)
2. **âš ï¸ MULTI-USER SCOPE** - Original design single-user; needs multi-tenant architecture for 10-20 friends
3. **âš ï¸ POSITION/RISK MANAGEMENT** - Needs review for consistency across YAML, DB, and code
4. **âš ï¸ TRAILING STOPS** - Current stop-loss is basic; needs trailing stop implementation
5. **âš ï¸ YAML/DB CONSISTENCY** - User-scoped config variables not fully integrated

### Target Architecture

**Multi-user webapp with:**
- Individual user accounts and authentication
- Per-user configuration (Kelly fractions, risk limits, enabled strategies)
- Separate user data schemas (Pattern 2: Schema-per-user for security)
- Shared market data (common schema)
- User-level and system-level circuit breakers
- Optional leaderboard and analytics

### Success Criteria

- ✅ Clean versioning system with proper object integration
- ✅ Multi-user database architecture with data isolation
- ✅ Consistent position/risk management across all layers
- ✅ Trailing stop loss fully functional
- ✅ All YAML configs align with database schema
- ✅ Comprehensive test coverage
- ✅ Ready for Phase 1 implementation via Claude Code

---

## Critical Issues Identified & Solutions

### Issue #1: Incomplete Versioning System

**Problem Identified:**
```
Current database design has "version" columns but lacks proper integration:
- strategies table has strategy_version VARCHAR
- models table has model_version VARCHAR  
- edges table has no versioning
- No strategy_versions or model_versions tracking tables
- No clear lifecycle: create â†' test â†' activate â†' deprecate
- No way to A/B test or rollback
```

**Root Cause:**
Versioning was added as an afterthought without thinking through the full lifecycle and use cases.

**Solution - Complete Versioning Architecture:**

#### 1.1 When Do We Actually Need Versioning?

**STRATEGIES: YES ✅**
- Users want to test modified strategies (e.g., halftime_entry with different thresholds)
- Need A/B testing: run v1.0 and v2.0 simultaneously
- Need rollback if new version underperforms

**MODELS: YES ✅**  
- Probability models evolve as we collect more historical data
- Need to track which model version generated each prediction
- Need to validate model improvements (v2.0 vs v1.0)

**EDGES: NO ❌**
- Edges are calculations (probability - price), not configurations
- Edge records already have timestamps for history
- Don't need versioning - just recalculate with current strategy/model

**VERDICT: Strategy and Model versioning; NOT Edge versioning**

#### 1.2 Complete Versioning Design

**Strategy Versioning Schema:**

```sql
-- Core strategies table (immutable records, one row per version)
CREATE TABLE strategies (
    strategy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    strategy_name VARCHAR(100) NOT NULL,  -- e.g., "halftime_entry"
    strategy_version VARCHAR(20) NOT NULL,  -- e.g., "1.0", "1.1", "2.0"
    
    -- Configuration (JSONB for flexibility)
    config JSONB NOT NULL,  -- All strategy parameters
    
    -- Lifecycle
    status VARCHAR(20) NOT NULL DEFAULT 'draft',  
        -- Values: 'draft', 'testing', 'active', 'inactive', 'deprecated'
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    notes TEXT,  -- Why this version was created
    
    -- Performance tracking
    paper_trades_count INTEGER DEFAULT 0,
    paper_roi DECIMAL(10,4),
    live_trades_count INTEGER DEFAULT 0,
    live_roi DECIMAL(10,4),
    
    -- Activation
    activated_at TIMESTAMP,
    deactivated_at TIMESTAMP,
    
    UNIQUE(user_id, strategy_name, strategy_version)
);

-- Index for finding active strategies per user
CREATE INDEX idx_strategies_active ON strategies(user_id, strategy_name) 
WHERE status = 'active';

-- Example data:
INSERT INTO strategies VALUES (
    'abc123',  -- strategy_id
    'user-john',  -- user_id
    'halftime_entry',  -- strategy_name
    '1.0',  -- strategy_version
    '{
        "min_lead_points": 7,
        "required_confidence": 0.08,
        "max_position_size": 1000
    }',  -- config
    'active',  -- status
    NOW(),
    'john',
    'Initial production version'
);
```

**Model Versioning Schema:**

```sql
-- Core models table (immutable records, one row per version)
CREATE TABLE probability_models (
    model_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),  -- NULL for system models
    model_name VARCHAR(100) NOT NULL,  -- e.g., "nfl_ensemble"
    model_version VARCHAR(20) NOT NULL,  -- e.g., "1.0", "2.0"
    
    -- Configuration
    config JSONB NOT NULL,  -- Model parameters, data sources, weights
    
    -- Training info
    training_start_date DATE,
    training_end_date DATE,
    training_sample_size INTEGER,
    
    -- Lifecycle  
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
        -- Values: 'draft', 'training', 'validating', 'active', 'deprecated'
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    notes TEXT,
    
    -- Validation metrics
    validation_accuracy DECIMAL(6,4),  -- e.g., 0.6500 = 65%
    validation_calibration DECIMAL(6,4),  -- Brier score
    validation_sample_size INTEGER,
    
    -- Activation
    activated_at TIMESTAMP,
    deactivated_at TIMESTAMP,
    
    UNIQUE(model_name, model_version)
);

-- Index for active models
CREATE INDEX idx_models_active ON probability_models(model_name) 
WHERE status = 'active';
```

**Edges Table (NO versioning needed):**

```sql
-- edges table tracks calculations, not versions
CREATE TABLE edges (
    edge_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    ticker VARCHAR(100) NOT NULL,
    
    -- Which strategy/model generated this edge
    strategy_id UUID REFERENCES strategies(strategy_id),
    model_id UUID REFERENCES probability_models(model_id),
    
    -- Edge calculation
    ensemble_probability DECIMAL(10,4) NOT NULL,
    market_price DECIMAL(10,4) NOT NULL,
    edge_value DECIMAL(10,4) NOT NULL,  -- ensemble_probability - market_price
    confidence DECIMAL(6,4) NOT NULL,
    
    -- Timestamps (versioning via row_current_ind instead)
    calculated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE,
    
    -- Composite primary key for versioning
    PRIMARY KEY (ticker, user_id, calculated_at)
);
```

#### 1.3 Strategy Version Lifecycle

```
[Draft] â†' [Testing] â†' [Active] â†' [Inactive/Deprecated]
   â"‚          â"‚           â"‚            â"‚
   â"‚          â"‚           â"‚            â""â"€â"€> Can reactivate later
   â"‚          â"‚           â"‚
   â"‚          â"‚           â""â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€> Only ONE active version per (user, strategy_name)
   â"‚          â"‚
   â"‚          â""â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€> Paper trading validation (optional)
   â"‚
   â""â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€> User creates/edits strategy
```

**Status Transitions:**

```python
# utils/version_lifecycle.py

class StrategyVersionLifecycle:
    """
    Manages strategy version transitions.
    
    LEARNING NOTES:
    - Only ONE version of a strategy can be 'active' per user at a time
    - When activating a new version, the old version moves to 'inactive'
    - 'testing' status allows paper trading without affecting live trading
    """
    
    VALID_TRANSITIONS = {
        'draft': ['testing', 'active', 'deprecated'],
        'testing': ['active', 'draft', 'deprecated'],
        'active': ['inactive', 'deprecated'],
        'inactive': ['active', 'deprecated'],
        'deprecated': []  # Terminal state
    }
    
    @staticmethod
    def activate_strategy_version(
        db_session,
        strategy_id: UUID,
        user_id: UUID
    ) -> Result:
        """
        Activate a strategy version.
        
        This automatically deactivates any other active version
        of the same strategy for this user.
        
        Args:
            db_session: Database session
            strategy_id: Strategy version to activate
            user_id: Owner of the strategy
            
        Returns:
            Result object with success/failure
            
        Example:
            >>> result = StrategyVersionLifecycle.activate_strategy_version(
            ...     db,
            ...     strategy_id='abc-123',
            ...     user_id='user-john'
            ... )
            >>> if result.success:
            ...     print(f"Activated {result.data['strategy_name']} v{result.data['version']}")
        """
        # Get the strategy to activate
        strategy = db_session.query(Strategy).filter(
            Strategy.strategy_id == strategy_id,
            Strategy.user_id == user_id
        ).first()
        
        if not strategy:
            return Result(success=False, error="Strategy not found")
        
        # Check current status
        if strategy.status not in StrategyVersionLifecycle.VALID_TRANSITIONS:
            return Result(
                success=False, 
                error=f"Cannot activate from status '{strategy.status}'"
            )
        
        # Deactivate any currently active version of this strategy
        db_session.query(Strategy).filter(
            Strategy.user_id == user_id,
            Strategy.strategy_name == strategy.strategy_name,
            Strategy.status == 'active'
        ).update({
            'status': 'inactive',
            'deactivated_at': datetime.now()
        })
        
        # Activate the new version
        strategy.status = 'active'
        strategy.activated_at = datetime.now()
        strategy.deactivated_at = None
        
        db_session.commit()
        
        return Result(
            success=True,
            data={
                'strategy_id': str(strategy.strategy_id),
                'strategy_name': strategy.strategy_name,
                'version': strategy.strategy_version
            }
        )
```

#### 1.4 A/B Testing Support

```python
# trading/strategy_executor.py

class StrategyExecutor:
    """
    Execute trades based on active strategies.
    
    Supports A/B testing by allocating capital between strategy versions.
    """
    
    def __init__(self, db_session, user_id: UUID):
        self.db = db_session
        self.user_id = user_id
    
    def get_active_strategies(self) -> List[Strategy]:
        """
        Get all active strategies for user.
        
        Returns list of Strategy objects with status='active'.
        For A/B testing, user can have multiple strategies active
        if they have different strategy_names.
        
        Example:
            User has TWO strategies active:
            - halftime_entry v2.0 (active)
            - q3_entry v1.5 (active)
            
            This is allowed because different strategy names.
        """
        return self.db.query(Strategy).filter(
            Strategy.user_id == self.user_id,
            Strategy.status == 'active'
        ).all()
    
    def execute_edge_signal(
        self,
        edge: Edge,
        strategy: Strategy
    ) -> Optional[Trade]:
        """
        Execute a trade based on edge signal and strategy config.
        
        Links the trade to the specific strategy version that generated it,
        enabling performance tracking per version.
        
        Args:
            edge: Edge signal (from edge detector)
            strategy: Strategy version to use
            
        Returns:
            Trade object if executed, None if filtered out
            
        Example:
            >>> edge = Edge(ticker='KXNFL-CHI-YES', edge_value=0.08, ...)
            >>> strategy = get_strategy('halftime_entry', version='2.0')
            >>> trade = executor.execute_edge_signal(edge, strategy)
            >>> print(f"Trade executed using {strategy.strategy_name} v{strategy.strategy_version}")
        """
        # Check strategy config filters
        config = strategy.config
        
        if edge.edge_value < config.get('min_edge', 0.05):
            return None
        
        if edge.confidence < config.get('min_confidence', 0.70):
            return None
        
        # Calculate position size using strategy config
        position_size = self._calculate_position_size(
            edge,
            max_size=config.get('max_position_size', 1000)
        )
        
        # Create trade
        trade = Trade(
            user_id=self.user_id,
            strategy_id=strategy.strategy_id,  # âœ… Link to version
            model_id=edge.model_id,  # âœ… Link to model version
            ticker=edge.ticker,
            side='YES' if edge.edge_value > 0 else 'NO',
            quantity=position_size,
            limit_price=edge.market_price,
            created_at=datetime.now()
        )
        
        self.db.add(trade)
        self.db.commit()
        
        return trade
```

#### 1.5 Performance Tracking by Version

```python
# analytics/strategy_performance.py

def calculate_strategy_version_performance(
    db_session,
    strategy_id: UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> StrategyPerformance:
    """
    Calculate performance metrics for a specific strategy version.
    
    This enables comparing v1.0 vs v2.0 to see if the new version
    is actually better.
    
    Returns:
        StrategyPerformance with ROI, win_rate, sharpe_ratio, etc.
        
    Example:
        >>> perf_v1 = calculate_strategy_version_performance(db, 'strat-v1')
        >>> perf_v2 = calculate_strategy_version_performance(db, 'strat-v2')
        >>> if perf_v2.roi > perf_v1.roi:
        ...     print("v2.0 is better! Let's deprecate v1.0")
    """
    # Get all trades for this strategy version
    trades = db_session.query(Trade).filter(
        Trade.strategy_id == strategy_id
    )
    
    if start_date:
        trades = trades.filter(Trade.created_at >= start_date)
    if end_date:
        trades = trades.filter(Trade.created_at <= end_date)
    
    trades = trades.all()
    
    if not trades:
        return StrategyPerformance(
            strategy_id=strategy_id,
            trade_count=0,
            roi=Decimal('0.0'),
            win_rate=Decimal('0.0')
        )
    
    # Calculate metrics
    total_pnl = sum(t.realized_pnl or Decimal('0.0') for t in trades)
    total_risk = sum(t.quantity * t.limit_price for t in trades)
    roi = total_pnl / total_risk if total_risk > 0 else Decimal('0.0')
    
    wins = [t for t in trades if (t.realized_pnl or 0) > 0]
    win_rate = Decimal(len(wins)) / Decimal(len(trades)) if trades else Decimal('0.0')
    
    return StrategyPerformance(
        strategy_id=strategy_id,
        trade_count=len(trades),
        roi=roi,
        win_rate=win_rate,
        total_pnl=total_pnl,
        avg_pnl_per_trade=total_pnl / len(trades) if trades else Decimal('0.0')
    )
```

---

### Issue #2: Multi-User Architecture

**Problem Identified:**
```
Current design assumes single user:
- No users table
- No authentication/authorization
- No per-user configuration
- No data isolation
- No user-level circuit breakers
```

**Solution - Multi-Tenant Architecture:**

#### 2.1 User Management Schema

```sql
-- Users table (authentication & profile)
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    
    -- Authentication (passwords hashed with bcrypt)
    password_hash VARCHAR(255) NOT NULL,
    
    -- Profile
    display_name VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login TIMESTAMP,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    
    -- Settings
    timezone VARCHAR(50) DEFAULT 'UTC',
    notification_preferences JSONB DEFAULT '{}',
    
    -- Schema name for data isolation (Pattern 2)
    data_schema VARCHAR(100) UNIQUE,
        -- e.g., 'user_john', 'user_mary'
        -- Each user gets their own PostgreSQL schema
    
    CONSTRAINT valid_username CHECK (username ~ '^[a-zA-Z0-9_]{3,50}$')
);

-- User API keys (encrypted storage)
CREATE TABLE user_api_keys (
    key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,  -- 'kalshi', 'polymarket', etc.
    
    -- Encrypted API credentials
    api_key_encrypted BYTEA NOT NULL,
    api_secret_encrypted BYTEA,
    additional_config JSONB,  -- Platform-specific settings
    
    -- Metadata
    key_name VARCHAR(100),  -- User-friendly name
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_used TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    
    UNIQUE(user_id, platform)
);

-- User configuration overrides
CREATE TABLE user_config_overrides (
    override_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    config_key VARCHAR(255) NOT NULL,  -- e.g., 'trading.kelly_fraction_nfl'
    config_value JSONB NOT NULL,
    
    -- Metadata
    set_at TIMESTAMP NOT NULL DEFAULT NOW(),
    set_by VARCHAR(100),  -- Username who made the change
    notes TEXT,
    
    -- Priority (higher = overrides lower)
    priority INTEGER DEFAULT 100,
    
    UNIQUE(user_id, config_key)
);

-- User trading permissions
CREATE TABLE user_permissions (
    permission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Trading permissions
    can_trade_live BOOLEAN DEFAULT FALSE,  -- Must be explicitly enabled
    can_paper_trade BOOLEAN DEFAULT TRUE,
    
    -- Position limits
    max_position_size_dollars DECIMAL(12,2) DEFAULT 1000.00,
    max_total_exposure_dollars DECIMAL(12,2) DEFAULT 10000.00,
    max_daily_loss_dollars DECIMAL(12,2) DEFAULT 500.00,
    
    -- Strategy permissions
    allowed_strategies TEXT[],  -- Array of strategy names
    allowed_sports TEXT[],  -- e.g., ['nfl', 'ncaaf']
    
    -- Rate limits
    max_trades_per_day INTEGER DEFAULT 50,
    max_trades_per_hour INTEGER DEFAULT 10,
    
    -- Audit
    granted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    granted_by UUID REFERENCES users(user_id),
    
    UNIQUE(user_id)
);
```

#### 2.2 Data Isolation Pattern (Schema-per-user)

```
PostgreSQL Database: precog_production
â"‚
â"œâ"€â"€ Schema: public (shared data)
â"‚   â"œâ"€â"€ users
â"‚   â"œâ"€â"€ user_api_keys
â"‚   â"œâ"€â"€ user_permissions
â"‚   â"œâ"€â"€ platforms (shared)
â"‚   â"œâ"€â"€ series (shared)
â"‚   â"œâ"€â"€ events (shared)
â"‚   â"œâ"€â"€ markets (shared - everyone sees same market prices)
â"‚   â""â"€â"€ game_states (shared - everyone sees same game stats)
â"‚
â"œâ"€â"€ Schema: user_john (John's private data)
â"‚   â"œâ"€â"€ strategies
â"‚   â"œâ"€â"€ probability_models
â"‚   â"œâ"€â"€ edges
â"‚   â"œâ"€â"€ positions
â"‚   â"œâ"€â"€ trades
â"‚   â"œâ"€â"€ settlements
â"‚   â"œâ"€â"€ account_balance
â"‚   â""â"€â"€ alert_history
â"‚
â""â"€â"€ Schema: user_mary (Mary's private data)
    â"œâ"€â"€ strategies
    â"œâ"€â"€ probability_models
    â"œâ"€â"€ edges
    â"œâ"€â"€ positions
    â"œâ"€â"€ trades
    â""â"€â"€ ... (same tables as John, but separate data)
```

**Why Schema-per-user?**
- ✅ **Complete data isolation** - Impossible for users to see each other's data
- ✅ **Easier to delete user** - DROP SCHEMA user_john CASCADE
- ✅ **Better security** - PostgreSQL Row Level Security as backup
- ✅ **Simpler queries** - SET search_path = user_john; SELECT * FROM trades;

**Implementation:**

```python
# database/multi_tenant.py

class MultiTenantDatabase:
    """
    Manages multi-tenant database with schema-per-user pattern.
    
    LEARNING NOTES:
    - Each user gets their own PostgreSQL schema (e.g., user_john)
    - Shared data (markets, events) lives in 'public' schema
    - User data (trades, positions) lives in user's schema
    - This provides complete data isolation for security
    """
    
    @staticmethod
    def create_user_schema(
        db_session,
        user_id: UUID,
        username: str
    ) -> str:
        """
        Create a new PostgreSQL schema for a user.
        
        This schema will contain all user-specific tables:
        - strategies
        - probability_models  
        - edges
        - positions
        - trades
        - settlements
        - account_balance
        - alert_history
        
        Args:
            db_session: Database session
            user_id: UUID of the user
            username: Username (will be sanitized for schema name)
            
        Returns:
            Schema name (e.g., 'user_john')
            
        Example:
            >>> schema = MultiTenantDatabase.create_user_schema(
            ...     db,
            ...     user_id=uuid.uuid4(),
            ...     username='john'
            ... )
            >>> print(schema)  # 'user_john'
        """
        # Sanitize username for schema name
        schema_name = f"user_{re.sub(r'[^a-z0-9_]', '', username.lower())}"
        
        # Create schema
        db_session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        
        # Grant permissions
        db_session.execute(text(f"""
            GRANT ALL PRIVILEGES ON SCHEMA {schema_name} TO precog_app;
        """))
        
        # Create user-specific tables in this schema
        for table_sql in USER_SCHEMA_TABLES:
            # Replace 'public.' with 'user_john.'
            table_sql_customized = table_sql.replace(
                'CREATE TABLE',
                f'CREATE TABLE {schema_name}.'
            )
            db_session.execute(text(table_sql_customized))
        
        # Update users table with schema name
        db_session.execute(text("""
            UPDATE users SET data_schema = :schema WHERE user_id = :user_id
        """), {'schema': schema_name, 'user_id': str(user_id)})
        
        db_session.commit()
        
        return schema_name
    
    @staticmethod
    def get_user_session(
        base_session,
        user_id: UUID
    ) -> UserDatabaseSession:
        """
        Create a database session scoped to a specific user.
        
        This session automatically uses the user's schema for all queries,
        making it impossible to accidentally query another user's data.
        
        Args:
            base_session: Base database session
            user_id: User to scope session to
            
        Returns:
            UserDatabaseSession with search_path set to user's schema
            
        Example:
            >>> user_session = MultiTenantDatabase.get_user_session(db, user_id)
            >>> 
            >>> # This query runs in user_john schema automatically
            >>> trades = user_session.query(Trade).all()
            >>> 
            >>> # To query shared data, use explicit schema
            >>> markets = user_session.query(Market).filter(...).all()
        """
        # Get user's schema name
        user = base_session.query(User).filter(
            User.user_id == user_id
        ).first()
        
        if not user or not user.data_schema:
            raise ValueError(f"User {user_id} not found or schema not created")
        
        # Create new session with user's search path
        user_session = UserDatabaseSession(bind=base_session.bind)
        user_session.execute(text(f"SET search_path TO {user.data_schema}, public"))
        
        # Attach metadata for logging
        user_session.user_id = user_id
        user_session.user_schema = user.data_schema
        
        return user_session
```

#### 2.3 User Configuration System

```python
# config/user_config.py

class UserConfig:
    """
    User-specific configuration with priority:
    1. user_config_overrides table (highest)
    2. YAML files
    3. Code defaults (lowest)
    
    Allows each user to customize:
    - Kelly fractions
    - Position size limits
    - Enabled strategies
    - Risk parameters
    - Notification settings
    """
    
    def __init__(self, db_session, user_id: UUID):
        self.db = db_session
        self.user_id = user_id
        self._yaml_config = load_yaml_configs()  # Global configs
        self._user_overrides = self._load_user_overrides()
    
    def _load_user_overrides(self) -> Dict:
        """Load user-specific overrides from database."""
        overrides = self.db.query(UserConfigOverride).filter(
            UserConfigOverride.user_id == self.user_id
        ).all()
        
        result = {}
        for override in overrides:
            result[override.config_key] = override.config_value
        
        return result
    
    def get(self, config_key: str, default=None):
        """
        Get config value with priority.
        
        Priority:
        1. Database override (user-specific)
        2. YAML file (global)
        3. Default parameter
        
        Args:
            config_key: Dot-notation key (e.g., 'trading.kelly_fraction_nfl')
            default: Default value if not found
            
        Returns:
            Config value
            
        Example:
            >>> config = UserConfig(db, user_id='john')
            >>> kelly = config.get('trading.kelly_fraction_nfl', 0.25)
            >>> # John has override: returns 0.30
            >>> # Mary has no override: returns 0.25 from YAML
        """
        # Check database override first
        if config_key in self._user_overrides:
            return self._user_overrides[config_key]
        
        # Check YAML
        keys = config_key.split('.')
        value = self._yaml_config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set_override(
        self,
        config_key: str,
        config_value: Any,
        notes: str = None
    ):
        """
        Set a user-specific config override.
        
        This allows runtime changes without editing YAML files.
        
        Args:
            config_key: Key to override
            config_value: New value
            notes: Optional explanation
            
        Example:
            >>> config.set_override(
            ...     'trading.kelly_fraction_nfl',
            ...     0.30,
            ...     notes='Increased after 2 months of successful trading'
            ... )
        """
        # Check if override exists
        existing = self.db.query(UserConfigOverride).filter(
            UserConfigOverride.user_id == self.user_id,
            UserConfigOverride.config_key == config_key
        ).first()
        
        if existing:
            existing.config_value = config_value
            existing.set_at = datetime.now()
            existing.notes = notes
        else:
            override = UserConfigOverride(
                user_id=self.user_id,
                config_key=config_key,
                config_value=config_value,
                notes=notes
            )
            self.db.add(override)
        
        self.db.commit()
        
        # Refresh cache
        self._user_overrides[config_key] = config_value
```

---

### Issue #3: Position & Risk Management Consistency

**Problem Identified:**
```
Position management spread across multiple places:
- YAML: position_management.yaml (config)
- DB: positions table (data)
- Code: Needs review for consistency
- Unclear how user-scoped limits work
```

**Solution - Unified Position Management:**

#### 3.1 Complete Position Management YAML

```yaml
# config/position_management.yaml

# Position Management Configuration
# Version: 2.0
# Last Updated: 2025-10-18
#
# OVERVIEW:
# This file defines how positions are managed throughout their lifecycle:
# 1. Entry rules (when to open positions)
# 2. Monitoring (how often to check positions)
# 3. Exit rules (when to close positions)
# 4. Risk limits (position size, exposure)
#
# USER CUSTOMIZATION:
# Users can override any parameter via user_config_overrides table.
# Example: User 'john' can set kelly_fraction_nfl = 0.30 instead of 0.25

# ==============================================================================
# POSITION LIFECYCLE
# ==============================================================================

position_lifecycle:
  # Entry rules (when to open positions)
  entry:
    # Minimum edge required to enter (user-customizable)
    min_edge_required: 0.0500  # 5% minimum edge
    
    # Confidence thresholds for automated vs manual review
    confidence_thresholds:
      auto_execute: 0.7500       # ≥75% confidence: auto-execute
      manual_review: 0.6000      # 60-75%: alert user for approval
      ignore: 0.5000             # <60%: skip
    
    # Position sizing method
    sizing_method: "kelly_criterion"  # Options: 'kelly_criterion', 'fixed', 'volatility_adjusted'
    
    # Kelly Criterion settings (user-customizable)
    kelly_settings:
      # Base Kelly fractions by sport
      kelly_fraction_nfl: 0.2500      # 25% of Kelly (conservative)
      kelly_fraction_ncaaf: 0.2500
      kelly_fraction_nba: 0.2200      # 22% (more variance)
      kelly_fraction_mlb: 0.2000
      kelly_fraction_tennis: 0.1800   # 18% (highest variance)
      
      # Adjust Kelly based on confidence
      confidence_multipliers:
        high: 1.00    # confidence ≥ 0.80
        medium: 0.80  # confidence 0.60-0.80
        low: 0.60     # confidence 0.50-0.60
      
      # Correlation adjustments
      correlation_limit: 0.6000  # Reduce size if correlated positions > 60%
      correlation_multiplier: 0.7000  # Reduce to 70% of Kelly if correlated
    
    # Fixed sizing (if sizing_method = 'fixed')
    fixed_settings:
      default_position_size_dollars: 100.00
    
  # Monitoring rules (how often to check positions)
  monitoring:
    # Check frequency (dynamic based on conditions)
    check_frequency_default: 60       # Every 60 seconds (normal)
    check_frequency_critical: 15      # Every 15 seconds when critical
    check_frequency_slow: 120         # Every 2 minutes when stable
    
    # Critical conditions (check more frequently)
    critical_conditions:
      - "period IN ('Q4', 'OT') AND time_remaining < 300"  # Final 5 minutes
      - "unrealized_pnl_pct > 0.1500"                      # Up 15%+
      - "unrealized_pnl_pct < -0.1000"                     # Down 10%+
      - "market_spread < 0.0200"                           # Spread < 2Â¢
      - "edge < 0.0300"                                    # Edge < 3%
    
    # Slow conditions (check less frequently)
    slow_conditions:
      - "period IN ('Q1', 'Q2') AND unrealized_pnl_pct BETWEEN -0.0500 AND 0.0500"
  
  # Exit rules (when to close positions)
  exit_rules:
    # Profit targets (user-customizable)
    profit_target:
      default_pct: 0.2000             # Take profit at +20%
      
      # Adjust based on confidence
      confidence_adjustments:
        high: 0.2500                  # 25% for high confidence
        medium: 0.2000                # 20% for medium
        low: 0.1500                   # 15% for low confidence
      
      # Adjust based on time remaining
      time_adjustments:
        - condition: "time_remaining < 120"
          multiplier: 0.8000          # 16% target near end
        - condition: "time_remaining < 60"
          multiplier: 0.6000          # 12% target at end
    
    # Stop losses (user-customizable)
    stop_loss:
      default_pct: -0.1500            # Stop loss at -15%
      
      # Adjust based on confidence
      confidence_adjustments:
        high: -0.1000                 # Tighter stop for high confidence
        medium: -0.1500
        low: -0.2000                  # Wider stop for low confidence
      
      # Trailing stop loss (see Issue #4 for details)
      trailing_enabled: true
      trailing_activation: 0.1000     # Activate after +10% gain
      trailing_distance: 0.0500       # Trail by 5%
      trailing_tighten_rate: 0.0100   # Tighten 1% per 5% gain
    
    # Early exit if edge disappears
    early_exit_threshold: 0.0300      # Exit if edge drops below 3%
    
    # Hold to settlement? (strategy-dependent)
    hold_until_settlement: false      # Don't always hold
    
    # Partial exit rules
    partial_exit:
      enabled: true
      trigger: "unrealized_pnl_pct > 0.1500"  # At +15% profit
      exit_percentage: 0.5000         # Sell 50% of position
      remaining_target: 0.3000        # New 30% target for remainder
  
  # Scaling rules (add/reduce position)
  scaling:
    # Scale in (add to position)
    scale_in:
      enabled: true
      max_scale_factor: 2.0           # Max 2x original position
      
      triggers:
        - condition: "edge_increased_by >= 0.0500"
          add_percentage: 0.5000      # Add 50% more
        - condition: "price_moved_against_us >= 0.0300 AND edge_still_positive"
          add_percentage: 0.3000      # Average down (carefully)
    
    # Scale out (reduce position)
    scale_out:
      enabled: true
      
      triggers:
        - condition: "unrealized_pnl_pct > 0.1000 AND edge < 0.0200"
          reduce_percentage: 0.3000   # Take 30% off table
        - condition: "edge_decreased_by >= 0.0300"
          reduce_percentage: 0.5000   # Reduce 50% if edge shrinks

# ==============================================================================
# RISK LIMITS (User-Customizable)
# ==============================================================================

risk_limits:
  # Position-level limits
  position:
    # Maximum position size (user-customizable)
    max_position_size_dollars: 1000.00
    
    # Minimum position size (avoid tiny positions)
    min_position_size_dollars: 50.00
    
    # Max quantity per ticker
    max_quantity_per_ticker: 10000  # contracts
  
  # Exposure limits
  exposure:
    # Total exposure across all positions (user-customizable)
    max_total_exposure_dollars: 10000.00
    
    # Max exposure per sport
    max_exposure_per_sport:
      nfl: 5000.00
      ncaaf: 3000.00
      nba: 3000.00
      mlb: 2000.00
      tennis: 1000.00
    
    # Max exposure per event
    max_exposure_per_event_dollars: 2000.00
    
    # Max correlated exposure (same team, same day)
    max_correlated_exposure_dollars: 3000.00
  
  # Loss limits (circuit breakers)
  loss_limits:
    # Daily loss limit (user-customizable)
    max_daily_loss_dollars: 500.00
    
    # Weekly loss limit
    max_weekly_loss_dollars: 1500.00
    
    # Per-position max loss
    max_loss_per_position_dollars: 200.00

# ==============================================================================
# STRATEGY-SPECIFIC OVERRIDES
# ==============================================================================

strategy_overrides:
  # Different strategies can have different exit rules
  halftime_entry:
    profit_target: 0.2500             # Higher target for halftime entries
    stop_loss: -0.1500
    trailing_enabled: true
    hold_until_settlement: true       # Usually hold these
  
  live_continuous:
    profit_target: 0.1500             # Lower target for live trading
    stop_loss: -0.1000                # Tighter stop
    trailing_enabled: true
    hold_until_settlement: false      # More active management
  
  q3_entry:
    profit_target: 0.2000
    stop_loss: -0.1200
    trailing_enabled: true
    hold_until_settlement: true

# ==============================================================================
# MONITORING ALERTS
# ==============================================================================

alerts:
  # Alert triggers
  triggers:
    - condition: "unrealized_pnl_pct > 0.2000"
      alert_type: "profit_target_approaching"
      notify_user: true
    
    - condition: "unrealized_pnl_pct < -0.1000"
      alert_type: "stop_loss_approaching"
      notify_user: true
    
    - condition: "edge < 0.0200 AND unrealized_pnl_pct < 0.0500"
      alert_type: "edge_disappearing"
      notify_user: true
  
  # Alert channels
  channels:
    email: true
    sms: false                        # Phase 7+
    webapp_notification: true
    slack: false                      # Phase 7+
```

#### 3.2 Risk Management Class

```python
# risk/position_manager.py

class PositionManager:
    """
    Manages position lifecycle and risk limits.
    
    Enforces user-specific risk limits and monitors positions
    for exit conditions (profit target, stop loss, trailing stop).
    
    LEARNING NOTES:
    - All risk limits are user-customizable via user_config_overrides
    - System checks positions every 15-120 seconds (dynamic frequency)
    - Multiple exit conditions can trigger simultaneously (uses most conservative)
    """
    
    def __init__(self, db_session, user_id: UUID):
        self.db = db_session
        self.user_id = user_id
        self.config = UserConfig(db_session, user_id)
    
    def check_can_open_position(
        self,
        ticker: str,
        proposed_size_dollars: Decimal,
        sport: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if user can open a new position without violating risk limits.
        
        Checks:
        1. Position size limit
        2. Total exposure limit
        3. Sport exposure limit
        4. Event exposure limit
        5. Correlated exposure limit
        6. Daily loss circuit breaker
        
        Args:
            ticker: Market ticker
            proposed_size_dollars: Proposed position size
            sport: Sport category
            
        Returns:
            (can_open, reason_if_not)
            
        Example:
            >>> manager = PositionManager(db, user_id='john')
            >>> can_open, reason = manager.check_can_open_position(
            ...     ticker='KXNFL-CHI-YES',
            ...     proposed_size_dollars=Decimal('500.00'),
            ...     sport='nfl'
            ... )
            >>> if not can_open:
            ...     print(f"Cannot open: {reason}")
        """
        # Check 1: Position size limit
        max_position_size = Decimal(
            self.config.get('risk_limits.position.max_position_size_dollars', 1000)
        )
        if proposed_size_dollars > max_position_size:
            return (
                False,
                f"Position size ${proposed_size_dollars} exceeds limit ${max_position_size}"
            )
        
        # Check 2: Total exposure limit
        current_exposure = self._calculate_total_exposure()
        max_total_exposure = Decimal(
            self.config.get('risk_limits.exposure.max_total_exposure_dollars', 10000)
        )
        if current_exposure + proposed_size_dollars > max_total_exposure:
            return (
                False,
                f"Would exceed total exposure limit: "
                f"${current_exposure + proposed_size_dollars} > ${max_total_exposure}"
            )
        
        # Check 3: Sport exposure limit
        current_sport_exposure = self._calculate_sport_exposure(sport)
        max_sport_exposure = Decimal(
            self.config.get(f'risk_limits.exposure.max_exposure_per_sport.{sport}', 5000)
        )
        if current_sport_exposure + proposed_size_dollars > max_sport_exposure:
            return (
                False,
                f"Would exceed {sport.upper()} exposure limit: "
                f"${current_sport_exposure + proposed_size_dollars} > ${max_sport_exposure}"
            )
        
        # Check 4: Event exposure limit
        event_id = self._get_event_id_from_ticker(ticker)
        current_event_exposure = self._calculate_event_exposure(event_id)
        max_event_exposure = Decimal(
            self.config.get('risk_limits.exposure.max_exposure_per_event_dollars', 2000)
        )
        if current_event_exposure + proposed_size_dollars > max_event_exposure:
            return (
                False,
                f"Would exceed per-event exposure limit"
            )
        
        # Check 5: Daily loss circuit breaker
        daily_pnl = self._calculate_daily_pnl()
        max_daily_loss = Decimal(
            self.config.get('risk_limits.loss_limits.max_daily_loss_dollars', -500)
        )
        if daily_pnl < max_daily_loss:
            return (
                False,
                f"Daily loss circuit breaker triggered: ${daily_pnl} < ${max_daily_loss}"
            )
        
        # All checks passed
        return (True, None)
    
    def monitor_position(self, position_id: UUID) -> PositionAction:
        """
        Check if position should be exited or adjusted.
        
        Evaluates exit conditions:
        - Profit target reached
        - Stop loss hit
        - Trailing stop triggered
        - Edge disappeared
        - Partial exit conditions
        
        Returns:
            PositionAction (HOLD, EXIT_FULL, EXIT_PARTIAL, SCALE_IN, SCALE_OUT)
            
        Example:
            >>> action = manager.monitor_position(position_id)
            >>> if action.action_type == 'EXIT_FULL':
            ...     close_position(position_id, reason=action.reason)
        """
        position = self.db.query(Position).filter(
            Position.position_id == position_id,
            Position.user_id == self.user_id
        ).first()
        
        if not position:
            return PositionAction(action_type='ERROR', reason='Position not found')
        
        # Calculate current P&L
        unrealized_pnl_pct = self._calculate_unrealized_pnl_pct(position)
        
        # Get exit thresholds (user-specific)
        profit_target = self._get_profit_target(position)
        stop_loss = self._get_stop_loss(position)
        
        # Check profit target
        if unrealized_pnl_pct >= profit_target:
            return PositionAction(
                action_type='EXIT_FULL',
                reason=f'Profit target reached: {unrealized_pnl_pct:.2%} >= {profit_target:.2%}',
                priority='HIGH'
            )
        
        # Check stop loss
        if unrealized_pnl_pct <= stop_loss:
            return PositionAction(
                action_type='EXIT_FULL',
                reason=f'Stop loss hit: {unrealized_pnl_pct:.2%} <= {stop_loss:.2%}',
                priority='CRITICAL'
            )
        
        # Check trailing stop (if enabled and activated)
        trailing_action = self._check_trailing_stop(position, unrealized_pnl_pct)
        if trailing_action:
            return trailing_action
        
        # Check edge disappearance
        current_edge = self._get_current_edge(position.ticker)
        early_exit_threshold = Decimal(
            self.config.get('position_lifecycle.exit_rules.early_exit_threshold', 0.03)
        )
        if current_edge is not None and current_edge < early_exit_threshold:
            return PositionAction(
                action_type='EXIT_FULL',
                reason=f'Edge disappeared: {current_edge:.2%} < {early_exit_threshold:.2%}',
                priority='MEDIUM'
            )
        
        # Check partial exit conditions
        partial_enabled = self.config.get('position_lifecycle.exit_rules.partial_exit.enabled', True)
        if partial_enabled:
            partial_trigger = Decimal(
                self.config.get('position_lifecycle.exit_rules.partial_exit.trigger', 0.15)
            )
            if unrealized_pnl_pct >= partial_trigger:
                exit_pct = Decimal(
                    self.config.get('position_lifecycle.exit_rules.partial_exit.exit_percentage', 0.5)
                )
                return PositionAction(
                    action_type='EXIT_PARTIAL',
                    reason=f'Partial exit triggered at {unrealized_pnl_pct:.2%}',
                    exit_percentage=exit_pct,
                    priority='MEDIUM'
                )
        
        # No action needed
        return PositionAction(action_type='HOLD', reason='All conditions normal')
```

---

### Issue #4: Trailing Stop Loss Implementation

**Problem Identified:**
```
Current stop loss is basic (fixed percentage).
Need trailing stop loss that:
- Activates after position is profitable
- Follows price up, locking in gains
- Tightens as profit increases
```

**Solution - Complete Trailing Stop Implementation:**

#### 4.1 Trailing Stop Logic

```python
# risk/trailing_stop.py

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from datetime import datetime

@dataclass
class TrailingStopState:
    """
    State of a trailing stop for a position.
    
    LEARNING NOTES:
    - Trailing stops "follow" the price up
    - Once activated, they never widen, only tighten
    - If price falls from peak, stop loss triggers
    
    Example:
        Entry price: $0.50
        Current price: $0.65 (+30%)
        Trailing stop activated at +10%
        Trailing distance: 5%
        
        Peak price seen: $0.65
        Current stop price: $0.65 * (1 - 0.05) = $0.6175
        
        If price falls to $0.61, stop loss triggers!
    """
    position_id: UUID
    is_activated: bool
    activation_pnl_pct: Decimal  # PnL% when trailing stop activated
    peak_price_seen: Decimal  # Highest price seen since activation
    current_stop_price: Decimal  # Current stop loss price
    last_updated: datetime

class TrailingStopManager:
    """
    Manages trailing stop losses for positions.
    
    Trailing stops protect profits by following price up,
    then triggering if price falls back down.
    """
    
    def __init__(self, db_session, user_config: UserConfig):
        self.db = db_session
        self.config = user_config
    
    def initialize_trailing_stop(
        self,
        position: Position
    ) -> Optional[TrailingStopState]:
        """
        Initialize trailing stop for a position.
        
        Trailing stop is NOT activated immediately.
        It activates only after position reaches activation threshold.
        
        Args:
            position: Position to initialize trailing stop for
            
        Returns:
            TrailingStopState (not yet activated)
            
        Example:
            >>> position = get_position('pos-123')
            >>> trailing = manager.initialize_trailing_stop(position)
            >>> print(f"Trailing stop initialized, not yet activated")
            >>> print(f"Will activate at {trailing.activation_pnl_pct:.1%} profit")
        """
        # Check if trailing stops enabled for this strategy
        strategy = position.strategy
        trailing_enabled = self.config.get(
            f'strategy_overrides.{strategy.strategy_name}.trailing_enabled',
            default=self.config.get(
                'position_lifecycle.exit_rules.stop_loss.trailing_enabled',
                True
            )
        )
        
        if not trailing_enabled:
            return None
        
        # Get activation threshold
        activation_threshold = Decimal(
            self.config.get(
                'position_lifecycle.exit_rules.stop_loss.trailing_activation',
                0.10  # Default: activate after +10% profit
            )
        )
        
        return TrailingStopState(
            position_id=position.position_id,
            is_activated=False,
            activation_pnl_pct=activation_threshold,
            peak_price_seen=position.entry_price,  # Start at entry
            current_stop_price=Decimal('0.0'),
            last_updated=datetime.now()
        )
    
    def update_trailing_stop(
        self,
        position: Position,
        current_price: Decimal,
        trailing_state: TrailingStopState
    ) -> Tuple[TrailingStopState, Optional[str]]:
        """
        Update trailing stop based on current price.
        
        Logic:
        1. If not activated, check if should activate
        2. If activated, update peak price if higher
        3. Calculate current stop price from peak
        4. Apply tightening rule (stop gets closer as profit increases)
        
        Args:
            position: Position
            current_price: Current market price
            trailing_state: Current trailing stop state
            
        Returns:
            (updated_state, trigger_reason_if_stopped)
            
        Example:
            >>> # Position bought at $0.50, now at $0.65
            >>> state, trigger = manager.update_trailing_stop(
            ...     position,
            ...     current_price=Decimal('0.65'),
            ...     trailing_state=state
            ... )
            >>> if trigger:
            ...     print(f"Trailing stop triggered: {trigger}")
            ... else:
            ...     print(f"New stop price: ${state.current_stop_price}")
        """
        entry_price = position.entry_price
        unrealized_pnl_pct = (current_price - entry_price) / entry_price
        
        # Step 1: Check if should activate
        if not trailing_state.is_activated:
            if unrealized_pnl_pct >= trailing_state.activation_pnl_pct:
                # ACTIVATE!
                trailing_state.is_activated = True
                trailing_state.peak_price_seen = current_price
                
                # Calculate initial stop price
                trailing_distance = Decimal(
                    self.config.get(
                        'position_lifecycle.exit_rules.stop_loss.trailing_distance',
                        0.05  # Default: 5% trail
                    )
                )
                trailing_state.current_stop_price = current_price * (
                    Decimal('1.0') - trailing_distance
                )
                trailing_state.last_updated = datetime.now()
                
                return (trailing_state, None)
            else:
                # Not yet activated, no stop
                return (trailing_state, None)
        
        # Step 2: Trailing stop is activated, update
        
        # Update peak if price is higher
        if current_price > trailing_state.peak_price_seen:
            trailing_state.peak_price_seen = current_price
        
        # Calculate base trailing distance
        base_trailing_distance = Decimal(
            self.config.get(
                'position_lifecycle.exit_rules.stop_loss.trailing_distance',
                0.05
            )
        )
        
        # Apply tightening rule (stop gets closer as profit increases)
        # For every 5% gain above activation, tighten by 1%
        tighten_rate = Decimal(
            self.config.get(
                'position_lifecycle.exit_rules.stop_loss.trailing_tighten_rate',
                0.01  # Tighten 1% per 5% gain
            )
        )
        
        profit_above_activation = unrealized_pnl_pct - trailing_state.activation_pnl_pct
        if profit_above_activation > Decimal('0.0'):
            # Tighten for every 5% gain
            tighten_amount = (profit_above_activation / Decimal('0.05')) * tighten_rate
            effective_trailing_distance = base_trailing_distance - tighten_amount
            
            # Floor at 2% (don't get too tight)
            effective_trailing_distance = max(
                effective_trailing_distance,
                Decimal('0.02')
            )
        else:
            effective_trailing_distance = base_trailing_distance
        
        # Calculate new stop price from peak
        new_stop_price = trailing_state.peak_price_seen * (
            Decimal('1.0') - effective_trailing_distance
        )
        
        # Ensure stop only tightens, never widens
        trailing_state.current_stop_price = max(
            trailing_state.current_stop_price,
            new_stop_price
        )
        
        trailing_state.last_updated = datetime.now()
        
        # Step 3: Check if stop triggered
        if current_price <= trailing_state.current_stop_price:
            return (
                trailing_state,
                f"Trailing stop triggered: price ${current_price} <= stop ${trailing_state.current_stop_price}"
            )
        
        # No trigger
        return (trailing_state, None)
    
    def get_trailing_stop_display(
        self,
        position: Position,
        trailing_state: TrailingStopState
    ) -> Dict:
        """
        Get human-readable trailing stop info for display.
        
        Returns dictionary with:
        - is_activated
        - activation_threshold
        - peak_price
        - current_stop_price
        - distance_from_current
        
        Example:
            >>> display = manager.get_trailing_stop_display(position, state)
            >>> print(f"Trailing Stop: {'ACTIVE' if display['is_activated'] else 'INACTIVE'}")
            >>> if display['is_activated']:
            ...     print(f"Stop Price: ${display['current_stop_price']:.4f}")
            ...     print(f"Distance: {display['distance_from_current']:.2%}")
        """
        if not trailing_state.is_activated:
            return {
                'is_activated': False,
                'activation_threshold': trailing_state.activation_pnl_pct,
                'will_activate_at_price': position.entry_price * (
                    Decimal('1.0') + trailing_state.activation_pnl_pct
                )
            }
        
        current_price = self._get_current_market_price(position.ticker)
        distance_from_current = (
            current_price - trailing_state.current_stop_price
        ) / current_price
        
        return {
            'is_activated': True,
            'peak_price': trailing_state.peak_price_seen,
            'current_stop_price': trailing_state.current_stop_price,
            'distance_from_current': distance_from_current,
            'current_price': current_price
        }
```

#### 4.2 Database Schema for Trailing Stops

```sql
-- Add to positions table
ALTER TABLE positions ADD COLUMN trailing_stop_state JSONB;

-- Example data:
UPDATE positions SET trailing_stop_state = '{
  "is_activated": true,
  "activation_pnl_pct": 0.1000,
  "peak_price_seen": 0.6500,
  "current_stop_price": 0.6175,
  "last_updated": "2025-10-18T15:30:00Z"
}'::jsonb
WHERE position_id = 'pos-123';
```

#### 4.3 Trailing Stop Visualization (for webapp)

```python
# Example output for user interface:

"""
Position: KXNFL-CHI-YES
Entry Price: $0.50
Current Price: $0.65
Unrealized P&L: +30.0%

Trailing Stop: âœ… ACTIVE
ââ"€â"€ Activation Level: +10.0% ($0.55)
ââ"€â"€ Peak Price Seen: $0.65
ââ"€â"€ Current Stop Price: $0.6175
ââ"€â"€ Distance from Peak: 5.0%
â""â"€â"€ Protection Locked In: +23.5%

If price falls to $0.6175, position will automatically close.
Profit is now protected - worst case is +23.5% gain!
"""
```

---

### Issue #5: YAML/DB Consistency with User-Scoped Config

**Problem Identified:**
```
User-scoped configuration variables added but:
- YAML files don't clearly indicate which params are user-customizable
- Database schema for user_config_overrides exists but not fully integrated
- Unclear which configs live where
```

**Solution - Complete Config Documentation:**

#### 5.1 Updated YAML with User-Customizable Annotations

See Section 3.1 for complete `position_management.yaml` with annotations.

**Key principles:**
- âœ… Comment "user-customizable" on every param users can override
- âœ… Provide examples of overrides
- âœ… Document priority: DB override > YAML > code default

#### 5.2 Configuration Consistency Matrix

| Configuration Parameter | YAML Location | User Customizable? | DB Override Table | Code Default |
|------------------------|---------------|-------------------|------------------|--------------|
| **Position Sizing** |
| Kelly fraction (NFL) | `position_management.yaml` → `kelly_settings.kelly_fraction_nfl` | ✅ YES | `user_config_overrides` | `Decimal('0.25')` |
| Kelly fraction (NBA) | `position_management.yaml` → `kelly_settings.kelly_fraction_nba` | ✅ YES | `user_config_overrides` | `Decimal('0.22')` |
| Max position size | `position_management.yaml` → `risk_limits.position.max_position_size_dollars` | ✅ YES | `user_config_overrides` AND `user_permissions.max_position_size_dollars` | `Decimal('1000.00')` |
| **Risk Limits** |
| Max total exposure | `position_management.yaml` → `risk_limits.exposure.max_total_exposure_dollars` | ✅ YES | `user_config_overrides` AND `user_permissions` | `Decimal('10000.00')` |
| Daily loss limit | `position_management.yaml` → `risk_limits.loss_limits.max_daily_loss_dollars` | ✅ YES | `user_config_overrides` AND `user_permissions` | `Decimal('-500.00')` |
| **Exit Rules** |
| Profit target | `position_management.yaml` → `exit_rules.profit_target.default_pct` | ✅ YES | `user_config_overrides` | `Decimal('0.20')` |
| Stop loss | `position_management.yaml` → `exit_rules.stop_loss.default_pct` | ✅ YES | `user_config_overrides` | `Decimal('-0.15')` |
| Trailing stop enabled | `position_management.yaml` → `exit_rules.stop_loss.trailing_enabled` | ✅ YES | `user_config_overrides` | `true` |
| **Strategy Config** |
| Strategy enabled | `trade_strategies.yaml` → `strategies.[name].enabled` | ✅ YES | `user_config_overrides` | varies |
| Strategy thresholds | `trade_strategies.yaml` → `strategies.[name].config` | ✅ YES | `user_config_overrides` | varies |
| **System Config** |
| API endpoints | `data_sources.yaml` | ❌ NO | N/A | per platform |
| Database config | `.env` | ❌ NO | N/A | env vars |

#### 5.3 Config Loader with Priority

Already shown in Issue #2, section 2.3 - see `UserConfig` class.

---

## Multi-User Architecture

### Schema Design

See Issue #2 for complete multi-user schema including:
- `users` table
- `user_api_keys` table
- `user_config_overrides` table
- `user_permissions` table
- Schema-per-user pattern

### Authentication Flow

```python
# api/auth.py

from flask import Flask, request, jsonify
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity
)
import bcrypt

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
jwt = JWTManager(app)

@app.route('/api/auth/register', methods=['POST'])
def register():
    """
    Register a new user.
    
    Creates:
    1. User record
    2. User schema (for data isolation)
    3. Default permissions
    4. Initial config overrides
    
    Request:
        POST /api/auth/register
        {
            "username": "john",
            "email": "john@example.com",
            "password": "securepassword123"
        }
    
    Response:
        {
            "user_id": "uuid",
            "username": "john",
            "access_token": "jwt_token"
        }
    """
    data = request.get_json()
    
    # Validate input
    if not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password required'}), 400
    
    # Hash password
    password_hash = bcrypt.hashpw(
        data['password'].encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')
    
    # Create user
    user = User(
        username=data['username'],
        email=data['email'],
        password_hash=password_hash
    )
    db.session.add(user)
    db.session.flush()  # Get user_id
    
    # Create user schema
    schema_name = MultiTenantDatabase.create_user_schema(
        db.session,
        user.user_id,
        user.username
    )
    
    # Create default permissions
    permissions = UserPermissions(
        user_id=user.user_id,
        can_trade_live=False,  # Disabled by default
        can_paper_trade=True,
        max_position_size_dollars=Decimal('100.00'),  # Conservative start
        max_total_exposure_dollars=Decimal('1000.00'),
        max_daily_loss_dollars=Decimal('50.00')
    )
    db.session.add(permissions)
    
    db.session.commit()
    
    # Generate JWT token
    access_token = create_access_token(identity=str(user.user_id))
    
    return jsonify({
        'user_id': str(user.user_id),
        'username': user.username,
        'access_token': access_token
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    """
    Login endpoint.
    
    Request:
        POST /api/auth/login
        {
            "username": "john",
            "password": "securepassword123"
        }
    
    Response:
        {
            "access_token": "jwt_token",
            "user_id": "uuid",
            "username": "john"
        }
    """
    data = request.get_json()
    
    # Find user
    user = db.session.query(User).filter(
        User.username == data.get('username')
    ).first()
    
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Check password
    if not bcrypt.checkpw(
        data.get('password', '').encode('utf-8'),
        user.password_hash.encode('utf-8')
    ):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Update last login
    user.last_login = datetime.now()
    db.session.commit()
    
    # Generate JWT
    access_token = create_access_token(identity=str(user.user_id))
    
    return jsonify({
        'access_token': access_token,
        'user_id': str(user.user_id),
        'username': user.username
    }), 200

@app.route('/api/user/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """
    Get user profile.
    
    Headers:
        Authorization: Bearer <jwt_token>
    
    Response:
        {
            "user_id": "uuid",
            "username": "john",
            "email": "john@example.com",
            "permissions": {...},
            "config_overrides": {...}
        }
    """
    user_id = UUID(get_jwt_identity())
    
    user = db.session.query(User).filter(
        User.user_id == user_id
    ).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Get permissions
    permissions = db.session.query(UserPermissions).filter(
        UserPermissions.user_id == user_id
    ).first()
    
    # Get config overrides
    overrides = db.session.query(UserConfigOverride).filter(
        UserConfigOverride.user_id == user_id
    ).all()
    
    return jsonify({
        'user_id': str(user.user_id),
        'username': user.username,
        'email': user.email,
        'permissions': {
            'can_trade_live': permissions.can_trade_live,
            'max_position_size': str(permissions.max_position_size_dollars),
            'max_total_exposure': str(permissions.max_total_exposure_dollars)
        },
        'config_overrides': {
            o.config_key: o.config_value for o in overrides
        }
    })
```

---

## Database Schema Updates

### Complete Schema

```sql
-- ==============================================================================
-- SHARED SCHEMA (public) - Market data visible to all users
-- ==============================================================================

-- Users table (authentication & profile)
CREATE TABLE public.users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    timezone VARCHAR(50) DEFAULT 'UTC',
    notification_preferences JSONB DEFAULT '{}',
    data_schema VARCHAR(100) UNIQUE,
    CONSTRAINT valid_username CHECK (username ~ '^[a-zA-Z0-9_]{3,50}$')
);

-- User API keys (encrypted)
CREATE TABLE public.user_api_keys (
    key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(user_id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,
    api_key_encrypted BYTEA NOT NULL,
    api_secret_encrypted BYTEA,
    additional_config JSONB,
    key_name VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_used TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, platform)
);

-- User configuration overrides
CREATE TABLE public.user_config_overrides (
    override_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(user_id) ON DELETE CASCADE,
    config_key VARCHAR(255) NOT NULL,
    config_value JSONB NOT NULL,
    set_at TIMESTAMP NOT NULL DEFAULT NOW(),
    set_by VARCHAR(100),
    notes TEXT,
    priority INTEGER DEFAULT 100,
    UNIQUE(user_id, config_key)
);

-- User permissions
CREATE TABLE public.user_permissions (
    permission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(user_id) ON DELETE CASCADE,
    can_trade_live BOOLEAN DEFAULT FALSE,
    can_paper_trade BOOLEAN DEFAULT TRUE,
    max_position_size_dollars DECIMAL(12,2) DEFAULT 1000.00,
    max_total_exposure_dollars DECIMAL(12,2) DEFAULT 10000.00,
    max_daily_loss_dollars DECIMAL(12,2) DEFAULT 500.00,
    allowed_strategies TEXT[],
    allowed_sports TEXT[],
    max_trades_per_day INTEGER DEFAULT 50,
    max_trades_per_hour INTEGER DEFAULT 10,
    granted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    granted_by UUID REFERENCES public.users(user_id),
    UNIQUE(user_id)
);

-- Shared market data (all users see same data)
CREATE TABLE public.platforms (...);  -- Existing
CREATE TABLE public.series (...);     -- Existing
CREATE TABLE public.events (...);     -- Existing
CREATE TABLE public.markets (...);    -- Existing
CREATE TABLE public.game_states (...); -- Existing

-- ==============================================================================
-- USER SCHEMA (user_john, user_mary, etc.) - Private user data
-- ==============================================================================

-- NOTE: These tables are created PER USER in their own schema
-- Example: user_john.strategies, user_mary.strategies

-- Strategies (with versioning)
CREATE TABLE strategies (
    strategy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,  -- References public.users
    strategy_name VARCHAR(100) NOT NULL,
    strategy_version VARCHAR(20) NOT NULL,
    config JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    notes TEXT,
    paper_trades_count INTEGER DEFAULT 0,
    paper_roi DECIMAL(10,4),
    live_trades_count INTEGER DEFAULT 0,
    live_roi DECIMAL(10,4),
    activated_at TIMESTAMP,
    deactivated_at TIMESTAMP,
    UNIQUE(user_id, strategy_name, strategy_version)
);

-- Probability models (with versioning)
CREATE TABLE probability_models (
    model_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,  -- NULL for system models
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    config JSONB NOT NULL,
    training_start_date DATE,
    training_end_date DATE,
    training_sample_size INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    notes TEXT,
    validation_accuracy DECIMAL(6,4),
    validation_calibration DECIMAL(6,4),
    validation_sample_size INTEGER,
    activated_at TIMESTAMP,
    deactivated_at TIMESTAMP,
    UNIQUE(model_name, model_version)
);

-- Edges (NO versioning, has timestamps)
CREATE TABLE edges (
    edge_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    ticker VARCHAR(100) NOT NULL,
    strategy_id UUID REFERENCES strategies(strategy_id),
    model_id UUID REFERENCES probability_models(model_id),
    ensemble_probability DECIMAL(10,4) NOT NULL,
    market_price DECIMAL(10,4) NOT NULL,
    edge_value DECIMAL(10,4) NOT NULL,
    confidence DECIMAL(6,4) NOT NULL,
    calculated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE
);

-- Positions (with trailing stop state)
CREATE TABLE positions (
    position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    strategy_id UUID REFERENCES strategies(strategy_id),
    ticker VARCHAR(100) NOT NULL,
    side VARCHAR(3) NOT NULL,
    entry_price DECIMAL(10,4) NOT NULL,
    quantity INTEGER NOT NULL,
    entry_time TIMESTAMP NOT NULL DEFAULT NOW(),
    exit_time TIMESTAMP,
    exit_price DECIMAL(10,4),
    realized_pnl DECIMAL(12,4),
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    trailing_stop_state JSONB,  -- âœ… NEW: Trailing stop data
    row_current_ind BOOLEAN DEFAULT TRUE
);

-- Trades (append-only, links to strategy/model versions)
CREATE TABLE trades (
    trade_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    strategy_id UUID REFERENCES strategies(strategy_id),  -- âœ… Links to version
    model_id UUID REFERENCES probability_models(model_id),  -- âœ… Links to version
    position_id UUID REFERENCES positions(position_id),
    ticker VARCHAR(100) NOT NULL,
    side VARCHAR(3) NOT NULL,
    quantity INTEGER NOT NULL,
    limit_price DECIMAL(10,4),
    filled_price DECIMAL(10,4),
    order_id VARCHAR(100),
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    filled_at TIMESTAMP,
    realized_pnl DECIMAL(12,4)
);

-- Other existing tables (settlements, account_balance, alert_history)
-- ... (unchanged)
```

---

## Testing Strategy

### Test Coverage Requirements

**Phase 1 (Foundation):**
- ✅ Unit tests for all classes (80%+ coverage)
- ✅ Integration tests for database operations
- ✅ API client tests (mock Kalshi responses)

**Phase 1.5 (Multi-User):**
- ✅ User registration/login flow
- ✅ Data isolation (user A cannot see user B's data)
- ✅ Config override priority
- ✅ Trailing stop logic
- ✅ Versioning lifecycle

### Test Cases

```python
# tests/test_versioning.py

def test_strategy_version_lifecycle():
    """Test strategy version transitions: draft â†' testing â†' active â†' inactive."""
    # Create draft strategy
    strategy = create_strategy(
        user_id='test-user',
        name='halftime_entry',
        version='1.0',
        status='draft'
    )
    assert strategy.status == 'draft'
    
    # Transition to testing
    lifecycle.transition(strategy, 'testing')
    assert strategy.status == 'testing'
    
    # Transition to active
    lifecycle.transition(strategy, 'active')
    assert strategy.status == 'active'
    
    # Create v2.0 and activate (should deactivate v1.0)
    strategy_v2 = create_strategy(
        user_id='test-user',
        name='halftime_entry',
        version='2.0',
        status='draft'
    )
    lifecycle.activate_strategy_version(db, strategy_v2.strategy_id, 'test-user')
    
    # Check v1.0 is now inactive
    db.session.refresh(strategy)
    assert strategy.status == 'inactive'
    
    # Check v2.0 is active
    assert strategy_v2.status == 'active'

def test_trailing_stop_activation():
    """Test trailing stop activates at correct profit level."""
    position = create_test_position(entry_price=Decimal('0.50'))
    trailing = manager.initialize_trailing_stop(position)
    
    # Not activated yet
    assert not trailing.is_activated
    
    # Price moves up but not enough
    state, trigger = manager.update_trailing_stop(
        position,
        current_price=Decimal('0.54'),  # +8%, below +10% threshold
        trailing_state=trailing
    )
    assert not state.is_activated
    assert trigger is None
    
    # Price moves up past threshold
    state, trigger = manager.update_trailing_stop(
        position,
        current_price=Decimal('0.56'),  # +12%, above +10% threshold
        trailing_state=state
    )
    assert state.is_activated  # âœ… Activated!
    assert state.peak_price_seen == Decimal('0.56')
    assert state.current_stop_price == Decimal('0.532')  # 5% trail

def test_trailing_stop_tightening():
    """Test trailing stop tightens as profit increases."""
    position = create_test_position(entry_price=Decimal('0.50'))
    trailing = manager.initialize_trailing_stop(position)
    
    # Activate at +12%
    state, _ = manager.update_trailing_stop(
        position, Decimal('0.56'), trailing
    )
    assert state.current_stop_price == Decimal('0.532')  # 5% trail
    
    # Price moves to +30%
    state, _ = manager.update_trailing_stop(
        position, Decimal('0.65'), state
    )
    # Trail should tighten: base 5%, minus 4% (20%/5% * 1%), = 1% trail
    # But floor at 2%, so 2% trail
    assert state.current_stop_price >= Decimal('0.637')  # 2% trail

def test_user_data_isolation():
    """Test users cannot see each other's data."""
    # Create two users
    user_john = create_user('john')
    user_mary = create_user('mary')
    
    # John creates a strategy
    strategy_john = create_strategy(
        user_id=user_john.user_id,
        name='halftime_entry',
        version='1.0'
    )
    
    # Mary's session
    mary_session = MultiTenantDatabase.get_user_session(db, user_mary.user_id)
    
    # Mary cannot see John's strategy
    strategies = mary_session.query(Strategy).all()
    assert len(strategies) == 0
    
    # John's session
    john_session = MultiTenantDatabase.get_user_session(db, user_john.user_id)
    
    # John can see his own strategy
    strategies = john_session.query(Strategy).all()
    assert len(strategies) == 1
    assert strategies[0].strategy_id == strategy_john.strategy_id

def test_config_override_priority():
    """Test config priority: DB override > YAML > default."""
    user_id = create_test_user()
    config = UserConfig(db, user_id)
    
    # No override, should use YAML
    kelly = config.get('trading.kelly_fraction_nfl')
    assert kelly == Decimal('0.25')  # From YAML
    
    # Set override
    config.set_override('trading.kelly_fraction_nfl', Decimal('0.30'))
    
    # Should now use override
    kelly = config.get('trading.kelly_fraction_nfl')
    assert kelly == Decimal('0.30')  # From database
```

---

## 30-Day Implementation Roadmap

### Week 1: Multi-User Foundation (Days 1-7)

**Day 1-2: Database Schema**
- Create `users`, `user_api_keys`, `user_config_overrides`, `user_permissions` tables
- Implement schema-per-user pattern
- Write migration scripts
- **Deliverable:** Database setup complete

**Day 3-4: Authentication**
- Implement registration endpoint
- Implement login endpoint with JWT
- Implement password hashing (bcrypt)
- **Deliverable:** Users can register and login

**Day 5-6: Multi-Tenant Database**
- Implement `MultiTenantDatabase` class
- Implement `create_user_schema()` 
- Implement `get_user_session()`
- Write tests for data isolation
- **Deliverable:** User schemas created automatically

**Day 7: User Config System**
- Implement `UserConfig` class
- Implement `get()` with priority
- Implement `set_override()`
- Write tests
- **Deliverable:** User-specific configs working

### Week 2: Versioning System (Days 8-14)

**Day 8-9: Strategy Versioning**
- Update `strategies` table schema
- Implement `StrategyVersionLifecycle` class
- Implement status transitions
- Implement activation/deactivation
- **Deliverable:** Strategy versioning working

**Day 10-11: Model Versioning**
- Update `probability_models` table schema
- Implement model lifecycle
- Link trades to model versions
- **Deliverable:** Model versioning working

**Day 12-13: Version Performance Tracking**
- Implement `calculate_strategy_version_performance()`
- Create performance comparison reports
- Add version history views
- **Deliverable:** Can compare v1.0 vs v2.0 performance

**Day 14: Testing & Documentation**
- Write version lifecycle tests
- Write documentation
- Create version management guide for users
- **Deliverable:** Versioning fully documented

### Week 3: Trailing Stops & Position Management (Days 15-21)

**Day 15-16: Trailing Stop Logic**
- Implement `TrailingStopManager` class
- Implement `initialize_trailing_stop()`
- Implement `update_trailing_stop()`
- Add `trailing_stop_state` to `positions` table
- **Deliverable:** Trailing stops logic complete

**Day 17-18: Position Manager Integration**
- Update `PositionManager` class
- Integrate trailing stops with monitoring
- Implement dynamic check frequency
- **Deliverable:** Positions monitored with trailing stops

**Day 19-20: Risk Management**
- Implement `check_can_open_position()`
- Integrate user permissions
- Implement circuit breakers
- **Deliverable:** Risk limits enforced

**Day 21: Testing**
- Write trailing stop tests
- Write position manager tests
- Write risk limit tests
- **Deliverable:** All tests passing

### Week 4: Integration & Polish (Days 22-30)

**Day 22-24: API Endpoints**
- Create user profile endpoint
- Create config override endpoints
- Create strategy management endpoints
- Create position monitoring endpoints
- **Deliverable:** Complete REST API

**Day 25-26: Documentation**
- Update all YAML configs with annotations
- Create user guide
- Create admin guide
- Update architecture docs
- **Deliverable:** Complete documentation

**Day 27-28: End-to-End Testing**
- Test complete user flow
- Test multi-user scenarios
- Test edge cases
- Load testing
- **Deliverable:** System fully tested

**Day 29-30: Deployment Preparation**
- Set up production database
- Configure environment variables
- Set up monitoring
- Create deployment runbook
- **Deliverable:** Ready for deployment

---

## Claude Code Command Examples

### Day 1: Database Schema

```bash
# Create user management tables
claude-code "Create database/migrations/002_user_tables.sql. 
Implement users, user_api_keys, user_config_overrides, and user_permissions tables 
per the schema in CLAUDE_CODE_IMPLEMENTATION_PLAN.md section 'Multi-User Architecture'.
Use UUID primary keys, proper foreign keys, and constraints."

# Create multi-tenant utilities
claude-code "Create database/multi_tenant.py. 
Implement MultiTenantDatabase class with create_user_schema() and get_user_session() methods.
Include complete docstrings and type hints. Follow schema-per-user pattern from implementation plan."
```

### Day 5: User Config System

```bash
# Implement user config
claude-code "Create config/user_config.py.
Implement UserConfig class with priority: DB override > YAML > default.
Include get(), set_override(), and _load_user_overrides() methods.
Add extensive docstrings with examples."

# Test user config
claude-code "Create tests/test_user_config.py.
Test config priority, override persistence, and YAML fallback.
Minimum 90% coverage."
```

### Day 8: Strategy Versioning

```bash
# Implement strategy versioning
claude-code "Create utils/version_lifecycle.py.
Implement StrategyVersionLifecycle class with activate_strategy_version() method.
Handle status transitions: draft â†' testing â†' active â†' inactive.
Ensure only one active version per (user, strategy_name)."

# Test versioning
claude-code "Create tests/test_versioning.py.
Test strategy version lifecycle, activation, deactivation, and performance tracking.
Include test for activating v2.0 auto-deactivating v1.0."
```

### Day 15: Trailing Stops

```bash
# Implement trailing stop manager
claude-code "Create risk/trailing_stop.py.
Implement TrailingStopManager with initialize_trailing_stop() and update_trailing_stop().
Include tightening logic: for every 5% gain, tighten trail by 1%.
Floor at 2% trail. Add complete docstrings with examples."

# Test trailing stops
claude-code "Create tests/test_trailing_stop.py.
Test activation threshold, tightening, triggering, and peak tracking.
Include edge cases: price spike then drop, multiple updates."
```

### Day 22: API Endpoints

```bash
# Create user endpoints
claude-code "Create api/user_endpoints.py.
Implement Flask routes: /api/user/profile, /api/user/config, /api/user/strategies.
Use @jwt_required() decorator. Return JSON responses.
Include error handling and validation."

# Test API endpoints
claude-code "Create tests/test_api_user.py.
Test authentication, profile retrieval, config updates, and strategy management.
Mock JWT tokens and database. Test error cases."
```

---

## Appendix: Quick Reference

### Key Files to Create

```
Phase 1.5 (Multi-User):
â"œâ"€â"€ database/
â"‚   â"œâ"€â"€ migrations/002_user_tables.sql
â"‚   â""â"€â"€ multi_tenant.py
â"œâ"€â"€ config/
â"‚   â""â"€â"€ user_config.py
â"œâ"€â"€ api/
â"‚   â"œâ"€â"€ auth.py
â"‚   â""â"€â"€ user_endpoints.py
â"œâ"€â"€ utils/
â"‚   â""â"€â"€ version_lifecycle.py
â"œâ"€â"€ risk/
â"‚   â"œâ"€â"€ position_manager.py
â"‚   â""â"€â"€ trailing_stop.py
â""â"€â"€ tests/
    â"œâ"€â"€ test_multi_tenant.py
    â"œâ"€â"€ test_user_config.py
    â"œâ"€â"€ test_versioning.py
    â"œâ"€â"€ test_trailing_stop.py
    â"œâ"€â"€ test_position_manager.py
    â""â"€â"€ test_api_user.py
```

### Configuration Files to Update

```
config/
â"œâ"€â"€ position_management.yaml  (âœ… Complete rewrite in this doc)
â"œâ"€â"€ trade_strategies.yaml     (Add user_id field)
â"œâ"€â"€ trading.yaml              (Add user customization notes)
â""â"€â"€ system.yaml               (Add multi-user settings)
```

### Database Tables Added

```
public.users
public.user_api_keys
public.user_config_overrides
public.user_permissions

user_john.strategies (updated schema)
user_john.probability_models (updated schema)
user_john.edges (updated schema)
user_john.positions (added trailing_stop_state)
user_john.trades (added strategy_id, model_id links)
```

---

## Success Criteria

### Multi-User
- ✅ Users can register and login
- ✅ User data is completely isolated (schema-per-user)
- ✅ Users can customize Kelly fractions, position sizes, risk limits
- ✅ User API keys are encrypted
- ✅ JWT authentication working

### Versioning
- ✅ Strategy versions can be created, tested, activated, deprecated
- ✅ Only one active version per (user, strategy)
- ✅ Trades link to strategy/model versions
- ✅ Can compare performance between versions
- ✅ Can rollback to previous version

### Position Management
- ✅ Trailing stops activate at profit threshold
- ✅ Trailing stops tighten as profit increases
- ✅ Risk limits enforced (position, exposure, daily loss)
- ✅ Dynamic monitoring frequency based on conditions
- ✅ User-specific risk limits working

### Configuration
- ✅ Config priority working: DB > YAML > default
- ✅ Users can override any config parameter
- ✅ YAML files clearly document which params are user-customizable
- ✅ Config changes reflected immediately

### Testing
- ✅ 80%+ code coverage
- ✅ All integration tests passing
- ✅ Data isolation verified
- ✅ No security vulnerabilities

---

## Conclusion

This implementation plan addresses all five critical issues:

1. **âœ… Versioning System** - Complete redesign with proper object integration
2. **âœ… Multi-User Architecture** - Full multi-tenant system with data isolation
3. **âœ… Position/Risk Management** - Unified system consistent across YAML, DB, code
4. **âœ… Trailing Stops** - Complete implementation with tightening logic
5. **âœ… YAML/DB Consistency** - Full documentation and user customization support

The system is now ready for Phase 1 implementation via Claude Code. All specifications are complete, no ambiguities remain, and the 30-day roadmap provides clear milestones.

**Next Steps:**
1. Review this document
2. Ask any clarifying questions
3. Begin Day 1 implementation via Claude Code

---

**END OF IMPLEMENTATION PLAN**
