# Configuration Guide (UPDATED)

---
**Version:** 2.0  
**Last Updated:** October 8, 2025  
**Status:** ✅ Current  
**Changes in v2.0:** 
- Fixed decimal pricing throughout (was incorrectly showing integer cents)
- Added platform-specific configuration sections
- Added sport/category-specific trading parameters
- Added configuration validation rules
- Added configuration versioning strategy
- Enhanced for multi-platform and multi-sport expansion
---

## Overview

Prescient uses YAML-based configuration with **three-tier priority**:
1. **Database Overrides** (highest priority) - Runtime changes via `config_overrides` table
2. **Environment Variables** (.env file) - Secrets and environment-specific values
3. **YAML Files** (lowest priority) - Default configuration

**Philosophy:** Configuration should be easy to understand, easy to change, and hard to break.

---

## Configuration Files (7 Core Files)

### Location
All configuration files stored in `/config` directory

### File Structure
```
config/
├── trading.yaml              # Trading parameters and risk limits
├── trade_strategies.yaml     # Strategy definitions (when to enter)
├── position_management.yaml  # Position lifecycle (what to do after entry)
├── odds_models.yaml          # Odds calculation configuration
├── markets.yaml              # Platforms and markets to monitor
├── data_sources.yaml         # API endpoints and polling
└── system.yaml               # System-wide settings

# All config files include version header:
config_version: "2.0"
last_updated: "2025-10-08"
```

---

## 1. trading.yaml

**Purpose:** Trading parameters, position sizing, risk limits

### Global Defaults

```yaml
config_version: "2.0"
last_updated: "2025-10-08"

# Global trading parameters (apply unless overridden)
global_defaults:
  position_sizing:
    kelly_fraction: 0.25              # Conservative Kelly (25%)
    max_position_size: 1000           # Max $1000 per position
    max_total_exposure: 10000         # Max $10,000 across all positions
    max_correlated_exposure: 5000     # Max $5,000 in correlated markets
  
  confidence_thresholds:
    # ⚠️ CRITICAL: Use DECIMAL format (0.0500 not 5)
    ignore_threshold: 0.0500          # Ignore if edge < 5%
    alert_threshold: 0.0800           # Alert if edge >= 8%
    auto_execute_threshold: 0.1500    # Auto-trade if edge >= 15%
```

### Category-Specific Parameters

**Sports Markets (Fast-Moving, Liquid)**
```yaml
categories:
  sports:
    # Sport-specific overrides
    nfl:
      enabled: true
      liquidity:
        min_volume: 100               # Minimum 100 contracts traded
        min_open_interest: 50         # Minimum 50 contracts outstanding
      
      execution:
        max_spread: 0.0500            # Max 5¢ spread (DECIMAL format!)
        min_time_remaining: 60        # Don't trade with <60 sec left
        slippage_tolerance: 0.0100    # 1¢ slippage acceptable
      
      position_sizing:
        kelly_fraction: 0.25          # Standard
        max_position_size: 1000       # $1000 max per NFL game
        max_positions_per_day: 5      # Max 5 NFL games same day
      
      confidence_thresholds:
        auto_execute_threshold: 0.1500  # 15% edge
        alert_threshold: 0.0800
        ignore_threshold: 0.0500
    
    nba:
      enabled: true
      liquidity:
        min_volume: 80                # Slightly lower (less liquid)
        min_open_interest: 40
      
      execution:
        max_spread: 0.0600            # Wider spread acceptable (6¢)
        min_time_remaining: 120       # More time needed (scoring faster)
        slippage_tolerance: 0.0150    # 1.5¢
      
      position_sizing:
        kelly_fraction: 0.22          # Slightly more conservative
        max_position_size: 800        # Lower than NFL
        max_positions_per_day: 8      # More games per day
      
      confidence_thresholds:
        auto_execute_threshold: 0.1700  # Higher threshold (more volatile)
        alert_threshold: 0.1000
        ignore_threshold: 0.0600
    
    ncaaf:
      enabled: true
      liquidity:
        min_volume: 50                # Lower standards
        min_open_interest: 25
      
      execution:
        max_spread: 0.0800            # Wider spreads (less liquid)
        min_time_remaining: 120
        slippage_tolerance: 0.0200
      
      position_sizing:
        kelly_fraction: 0.20          # More conservative (less data)
        max_position_size: 500        # Lower limits
        max_positions_per_day: 10     # Many games on Saturdays
      
      confidence_thresholds:
        auto_execute_threshold: 0.2000  # 20% (need high edge)
        alert_threshold: 0.1200
        ignore_threshold: 0.0700
    
    # Tennis (Phase 7)
    tennis:
      enabled: false                  # Not ready yet
      liquidity:
        min_volume: 30
        min_open_interest: 15
      
      execution:
        max_spread: 0.1000            # Wider (can swing dramatically)
        allow_in_play: true           # Can trade during match
        pause_on_serve_break: true    # Don't trade during momentum shifts
      
      position_sizing:
        kelly_fraction: 0.18          # Very conservative (high variance)
        max_position_size: 400
        max_positions_per_tournament: 5
      
      confidence_thresholds:
        auto_execute_threshold: 0.2500  # 25% (need very high edge)
        alert_threshold: 0.1500
        ignore_threshold: 0.1000
```

**Non-Sports Markets (Slower, More Research Required)**
```yaml
  non_sports:
    # Politics markets
    politics:
      enabled: false                  # Phase 8+
      liquidity:
        min_volume: 10                # Much lower liquidity OK
        min_open_interest: 5
      
      execution:
        max_spread: 0.1500            # Very wide spreads acceptable (15¢)
        require_manual_approval: true # ALWAYS require manual review
        allow_overnight_holds: true   # Can hold for days/weeks
      
      position_sizing:
        kelly_fraction: 0.15          # Very conservative
        max_position_size: 300        # Lower limits
        max_total_politics_exposure: 2000  # Cap total politics exposure
      
      confidence_thresholds:
        auto_execute_threshold: null  # Never auto-execute
        alert_threshold: 0.2000       # 20% edge needed for alert
        ignore_threshold: 0.1000
      
      holding_period:
        min_days: 7                   # Don't day-trade politics
        max_days: 90                  # Exit after 3 months max
    
    # Entertainment markets
    entertainment:
      enabled: false                  # Phase 8+
      liquidity:
        min_volume: 5
        min_open_interest: 3
      
      execution:
        max_spread: 0.2000            # Very wide (20¢)
        require_manual_approval: true
        allow_overnight_holds: true
      
      position_sizing:
        kelly_fraction: 0.12          # Extremely conservative
        max_position_size: 200
        max_total_entertainment_exposure: 1000
      
      confidence_thresholds:
        auto_execute_threshold: null
        alert_threshold: 0.2500       # 25% edge
        ignore_threshold: 0.1500
```

### Platform-Specific Overrides

**Kalshi Configuration**
```yaml
platform_specific:
  kalshi:
    fee_structure:
      # ⚠️ Use DECIMAL format for all fees
      maker_fee: 0.0000               # No maker fees currently
      taker_fee: 0.0070               # 0.7% taker fee
    
    execution:
      use_websocket: true             # Real-time price updates
      websocket_fallback_rest: true   # Fall back to REST if disconnected
      rest_polling_interval: 60       # Seconds (backup)
    
    rate_limits:
      rest_requests_per_minute: 100
      websocket_messages_per_second: 10
      order_placement_per_hour: 50    # Be conservative
    
    pricing:
      # ⚠️ CRITICAL: Always parse _dollars fields
      use_decimal_pricing: true       # MUST be true
      precision: 4                    # 4 decimal places (0.0001)
      validate_sub_penny: true        # Validate prices like 0.4275
  
  # Polymarket (Phase 10)
  polymarket:
    enabled: false
    fee_structure:
      # Polymarket uses gas fees (variable)
      base_gas_estimate: 0.0050       # ~$5 per trade (estimate)
      gas_price_buffer: 1.20          # 20% buffer for price spikes
    
    execution:
      use_websocket: false            # Check if available
      rest_polling_interval: 30       # More frequent polling needed
    
    rate_limits:
      rest_requests_per_minute: 60
      order_placement_per_hour: 30    # Conservative with gas
    
    pricing:
      use_decimal_pricing: true
      precision: 6                    # Polymarket may use more precision
```

### Correlation Detection

```yaml
correlation_detection:
  enabled: true
  
  # Define correlation tiers
  tiers:
    perfect_correlation:              # 1.0 correlation
      threshold: 1.0
      max_exposure_multiplier: 1.0    # Cannot hold both sides
      examples:
        - "Same market, different platforms (arbitrage)"
        - "Same event, complementary outcomes (YES/NO)"
    
    high_correlation:                 # 0.7-0.9 correlation
      threshold: 0.70
      max_exposure_multiplier: 0.5    # Max 50% of position size
      examples:
        - "Same game: 'Team wins' + 'Team covers spread'"
        - "Same player: 'Scores TD' + 'Over yards'"
    
    moderate_correlation:             # 0.4-0.6 correlation
      threshold: 0.40
      max_exposure_multiplier: null   # Use max_correlated_exposure
      examples:
        - "Multiple games same sport same day"
        - "Related political events"
  
  # How to calculate correlation
  calculation_method: "historical"    # Use historical price movements
  lookback_period_days: 90
  minimum_samples: 50                 # Need 50+ data points
  
  # Actions on detection
  actions:
    block_over_limit: true            # Prevent trades exceeding limits
    alert_on_detection: true          # Alert when correlation detected
    log_all_checks: true              # Log for analysis
```

---

## 2. trade_strategies.yaml

**Purpose:** Define **WHEN** to enter positions (strategies for market entry)

```yaml
config_version: "2.0"
last_updated: "2025-10-08"

# Strategy definitions
strategies:
  # NFL/NCAAF Halftime Entry
  halftime_entry:
    enabled: true
    description: "Enter position at halftime based on lead and momentum"
    
    # Which sports does this apply to?
    applicable_sports: ["nfl", "ncaaf"]
    
    # When to trigger this strategy
    entry_conditions:
      period: "Halftime"              # Must be halftime
      min_edge: 0.0800                # Min 8% EV (DECIMAL format!)
      min_confidence: "medium"        # At least medium confidence
    
    # Sport-specific parameters
    sports_config:
      nfl:
        lead_range:
          min_points: 7               # Leading by 7+ points
          max_points: 20              # But not blowout (>20)
        
        required_data_freshness: 60   # Data must be <60s old
        
        momentum_factors:
          check_last_drive: true      # Did they score on last drive?
          check_2h_receive: true      # Will they receive 2nd half kick?
        
        position_limits:
          max_bet_size: 1000          # Override default
          max_positions_halftime: 3   # Max 3 halftime bets per day
      
      ncaaf:
        lead_range:
          min_points: 10              # Need bigger lead (more variance)
          max_points: 24
        
        required_data_freshness: 90
        
        momentum_factors:
          check_last_drive: true
          check_2h_receive: true
          check_turnovers: true       # Turnovers matter more in NCAAF
        
        position_limits:
          max_bet_size: 500           # Lower than NFL
          max_positions_halftime: 5   # More games on Saturdays
  
  # Late Q4 Entry (Final Minutes)
  late_q4_entry:
    enabled: true
    description: "Enter in final minutes with strong edge"
    
    applicable_sports: ["nfl", "nba", "ncaaf"]
    
    entry_conditions:
      period: "Q4"
      time_remaining_range:
        min: 60                       # At least 60 seconds left
        max: 300                      # No more than 5 minutes
      min_edge: 0.1200                # Higher threshold (12%)
      min_confidence: "high"
    
    sports_config:
      nfl:
        lead_range:
          min_points: 3               # Close games only
          max_points: 10              # Not blowouts
        
        avoid_overtime_risk: true     # Don't trade if OT likely
        
        possession_matters: true      # Who has ball matters
        
        position_limits:
          max_bet_size: 800
          max_positions_late_game: 2
      
      nba:
        lead_range:
          min_points: 5
          max_points: 15
        
        avoid_overtime_risk: true
        
        foul_situation_check: true    # Check team fouls
        
        position_limits:
          max_bet_size: 600
          max_positions_late_game: 3
      
      ncaaf:
        lead_range:
          min_points: 7
          max_points: 14
        
        avoid_overtime_risk: true
        timeouts_check: true          # Check timeouts remaining
        
        position_limits:
          max_bet_size: 400
          max_positions_late_game: 4
  
  # Live Continuous Trading
  live_continuous:
    enabled: true
    description: "Trade anytime during game when edge detected"
    
    applicable_sports: ["nfl", "nba", "ncaaf"]
    
    entry_conditions:
      period: ["Q1", "Q2", "Q3", "Q4"]  # Any quarter
      min_edge: 0.1500                   # Higher threshold (15%)
      min_confidence: "high"
    
    # Additional filters
    filters:
      min_game_progress: 0.10         # At least 10% of game complete
      max_game_progress: 0.90         # Stop trading at 90% complete
      
      avoid_periods:                  # Don't trade during:
        - "End_of_Q1"                 # Last 30 sec Q1 (volatile)
        - "End_of_Q3"                 # Last 30 sec Q3
        - "Injury_Timeout"            # During injury timeouts
    
    position_limits:
      max_bet_size: 700
      max_positions_continuous: 3     # Max 3 live positions
  
  # Value Betting (Pre-Game)
  pregame_value:
    enabled: false                    # Phase 7+
    description: "Enter before game starts based on odds mismatch"
    
    entry_conditions:
      min_time_to_start: 1800         # At least 30 min before game
      max_time_to_start: 86400        # No more than 24 hours
      min_edge: 0.0800
      min_confidence: "medium"
    
    # Only bet pregame if market is liquid
    liquidity_requirements:
      min_volume: 200
      min_open_interest: 100
      max_spread: 0.0400              # 4¢ max spread
```

---

## 3. position_management.yaml

**Purpose:** Define **WHAT** to do after entering position (lifecycle management)

```yaml
config_version: "2.0"
last_updated: "2025-10-08"

# Position monitoring
position_lifecycle:
  monitoring:
    # Default monitoring frequency
    check_frequency_default: 60       # Check every 60 seconds
    
    # Increase frequency when critical
    check_frequency_critical: 15      # Check every 15 seconds when:
    critical_conditions:
      - "period == 'Q4' AND time_remaining < 300"   # Final 5 min
      - "unrealized_pnl_pct > 0.15"                 # Up 15%+
      - "unrealized_pnl_pct < -0.10"                # Down 10%+
      - "market_spread < 0.0200"                    # Spread narrowing
      - "edge < 0.0300"                             # Edge disappearing
    
    # Reduce frequency when stable
    check_frequency_slow: 120         # Check every 2 min when:
    slow_conditions:
      - "period IN ('Q1', 'Q2') AND unrealized_pnl_pct BETWEEN -0.05 AND 0.05"
  
  # Exit rules
  exit_rules:
    # Profit targets
    profit_target:
      # ⚠️ Use DECIMAL format (0.2000 not 20)
      default_pct: 0.2000             # Take profit at +20%
      
      # Adjust based on confidence
      confidence_adjustments:
        high: 0.2500                  # Higher target for high confidence
        medium: 0.2000
        low: 0.1500
      
      # Adjust based on time remaining
      time_adjustments:
        - condition: "time_remaining < 120"
          multiplier: 0.80            # Lower target near end (0.20 * 0.80 = 0.16 = 16%)
        - condition: "time_remaining < 60"
          multiplier: 0.60            # Very low target at end
    
    # Stop losses
    stop_loss:
      default_pct: -0.1500            # Stop loss at -15%
      
      # Adjust based on confidence
      confidence_adjustments:
        high: -0.1000                 # Tighter stop for high confidence
        medium: -0.1500
        low: -0.2000                  # Wider stop for low confidence
      
      # Trailing stop loss
      trailing_enabled: true
      trailing_activation: 0.1000     # Activate after +10% gain
      trailing_distance: 0.0500       # Trail by 5%
    
    # Early exit if edge disappears
    early_exit_threshold: 0.0300      # Exit if edge drops below 3%
    
    # Hold to settlement?
    hold_until_settlement: false      # Don't always hold to end
    
    # Partial exit rules
    partial_exit:
      enabled: true
      trigger: "unrealized_pnl_pct > 0.1500"  # 15% profit
      exit_percentage: 0.5000         # Sell 50% of position
      remaining_target: 0.3000        # New target for remaining 50%
  
  # Scaling rules (add/reduce position size)
  scaling:
    # Scale in (add to position)
    scale_in:
      enabled: true
      max_scale_factor: 2.0           # Max double position size
      
      triggers:
        - condition: "edge_increased_by >= 0.0500"  # Edge increased 5%
          add_percentage: 0.5000      # Add 50% more
        - condition: "price_moved_against_us >= 0.0300 AND edge_still_positive"
          add_percentage: 0.3000      # Average down (carefully!)
      
      limits:
        max_scales_per_position: 2    # Max 2 scale-ins
        min_time_between_scales: 300  # 5 minutes between scales
    
    # Scale out (reduce position)
    scale_out:
      enabled: true
      
      triggers:
        - condition: "edge_decreased_by >= 0.0300"  # Edge dropped 3%
          exit_percentage: 0.5000     # Exit 50%
        - condition: "volatility_spike > 2.0"       # Volatility doubled
          exit_percentage: 0.3000     # Reduce by 30%
  
  # Position review schedule
  periodic_review:
    enabled: true
    review_interval: 300              # Review all positions every 5 min
    
    review_checks:
      - "Is edge still positive?"
      - "Is confidence level still valid?"
      - "Has game state changed dramatically?"
      - "Is liquidity still adequate?"
      - "Are we approaching exit thresholds?"
```

---

## 4. odds_models.yaml

**Purpose:** Configure odds calculation models

```yaml
config_version: "2.0"
last_updated: "2025-10-08"

# Model registry
models:
  # NFL Win Probability Model
  nfl:
    active: true
    version: "v1.0"
    description: "NFL win probabilities by game state"
    
    # Model source data
    data_sources:
      - "Pro Football Reference (2019-2024)"
      - "ESPN Stats (2019-2024)"
      - "Advanced metrics (EPA, DVOA, etc.)"
    
    # Confidence calculation
    confidence_calculation:
      factors: ["sample_size", "ci_width", "recency"]
      
      high_confidence_requires:
        min_sample_size: 500
        max_ci_width: 0.1000          # ±10%
        data_recency: "2023-2024"
      
      medium_confidence_requires:
        min_sample_size: 200
        max_ci_width: 0.1500          # ±15%
        data_recency: "2021-2024"
      
      low_confidence_requires:
        min_sample_size: 100
        max_ci_width: 0.2000          # ±20%
        data_recency: "2019-2024"
    
    # Adjustments (stored in config, not in odds matrix)
    adjustments:
      home_advantage: 0.0300          # +3% for home team
      playoff_modifier: 0.0200        # +2% in playoffs
      weather_impact: true            # Adjust for weather
      
      # Situational adjustments
      favorite_underdog_adjustment: false  # NOT in config (in model)
      rest_days_adjustment: true
      travel_distance_adjustment: false
    
    # Model file location
    model_file: "odds_matrices/nfl_v1.0.json"
    
    # Update schedule
    update_schedule:
      frequency: "weekly"             # Update every week in season
      season_start: "2025-09-05"
      season_end: "2026-02-15"
  
  # NBA Win Probability Model
  nba:
    active: true
    version: "v1.0"
    description: "NBA win probabilities by game state"
    
    data_sources:
      - "Basketball Reference (2019-2024)"
      - "ESPN Stats (2019-2024)"
    
    confidence_calculation:
      factors: ["sample_size", "ci_width", "recency"]
      
      high_confidence_requires:
        min_sample_size: 500
        max_ci_width: 0.1200          # NBA more volatile
        data_recency: "2023-2024"
    
    adjustments:
      home_advantage: 0.0400          # +4% for home (stronger than NFL)
      playoff_modifier: 0.0300
      rest_days_adjustment: true      # Back-to-back matters
    
    model_file: "odds_matrices/nba_v1.0.json"
  
  # NCAAF Win Probability Model
  ncaaf:
    active: true
    version: "v1.0"
    description: "NCAAF win probabilities"
    
    data_sources:
      - "Sports Reference NCAAF (2019-2024)"
      - "ESPN College Football (2019-2024)"
    
    confidence_calculation:
      factors: ["sample_size", "ci_width", "recency", "division"]
      
      high_confidence_requires:
        min_sample_size: 300          # Less data available
        max_ci_width: 0.1500          # More variance
        division: "FBS"               # Only FBS high confidence
    
    adjustments:
      home_advantage: 0.0450          # +4.5% (stronger than NFL)
      conference_rivalry: 0.0200      # +2% for rivals
      division_strength: true         # Adjust for FBS vs FCS
    
    model_file: "odds_matrices/ncaaf_v1.0.json"
  
  # Tennis (Phase 7 - placeholder)
  tennis:
    active: false
    version: "v0.5"
    description: "Tennis match win probabilities"
    
    # Tennis is more complex - many factors
    data_sources:
      - "ATP/WTA historical data"
      - "Tennis Abstract"
    
    adjustments:
      surface_impact: true            # Clay vs Hard vs Grass
      head_to_head: true              # Past matchups matter
      ranking_difference: true
      fatigue_factor: true            # Tournaments matter
    
    model_file: "odds_matrices/tennis_v0.5.json"
  
  # Politics (Phase 8 - placeholder)
  politics:
    active: false
    version: "v0.1"
    description: "Political event probabilities"
    
    # Very different from sports
    data_sources:
      - "RealClearPolitics polls"
      - "FiveThirtyEight models"
      - "Historical election data"
    
    confidence_calculation:
      factors: ["polling_average", "sample_size", "days_until_event", "polling_margin"]
    
    adjustments:
      polling_bias: true              # Adjust for known biases
      undecided_voter_allocation: true
      historical_accuracy: true       # Weight recent polls more
    
    model_file: "odds_matrices/politics_v0.1.json"
```

---

## 5. markets.yaml

**Purpose:** Define which markets to monitor

```yaml
config_version: "2.0"
last_updated: "2025-10-08"

# Platform configurations
platforms:
  # Kalshi
  kalshi:
    enabled: true
    platform_id: "kalshi"
    display_name: "Kalshi"
    
    # API credentials (stored in .env)
    api_key_env: "KALSHI_API_KEY"
    api_secret_env: "KALSHI_API_SECRET"
    
    # Environments
    environments:
      demo:
        base_url: "https://demo-api.kalshi.co/trade-api/v2"
        websocket_url: "wss://demo-api.kalshi.co/trade-api/ws/v2"
        enabled: true
      
      prod:
        base_url: "https://trading-api.kalshi.com/trade-api/v2"
        websocket_url: "wss://trading-api.kalshi.com/trade-api/ws/v2"
        enabled: false                # Start with demo only
    
    # Active environment
    active_environment: "demo"
    
    # Categories to monitor
    categories:
      sports:
        enabled: true
        
        subcategories:
          nfl:
            enabled: true
            # Platform-specific series identifiers
            series_tickers: ["KXNFLGAME"]
            
            # Filters
            filter_method: "series_ticker"
            include_futures: false    # Don't trade season futures yet
            include_props: false      # Don't trade player props yet
          
          nba:
            enabled: true
            series_tickers: ["KXNBA", "KXNBAEAST", "KXNBAWEST"]
            filter_method: "series_ticker"
            include_futures: false
            include_props: false
          
          ncaaf:
            enabled: true
            series_tickers: ["KXNCAAFGAME"]
            filter_method: "series_ticker"
            include_futures: false
          
          mlb:
            enabled: false            # Phase 7
            series_tickers: ["KXMLB"]
          
          tennis:
            enabled: false            # Phase 7
            series_tickers: ["KXTENNIS"]
      
      politics:
        enabled: false                # Phase 8
        # Will use different filter method
      
      entertainment:
        enabled: false                # Phase 8
  
  # Polymarket (Phase 10)
  polymarket:
    enabled: false
    platform_id: "polymarket"
    display_name: "Polymarket"
    
    api_key_env: "POLYMARKET_PRIVATE_KEY"
    
    environments:
      mainnet:
        base_url: "https://polymarket.com/api"
        chain_id: 137                 # Polygon mainnet
        enabled: false
    
    active_environment: "mainnet"
    
    categories:
      crypto:
        enabled: false
        filter_method: "tags"         # Different from Kalshi!
        tags: ["bitcoin", "ethereum", "crypto"]
      
      politics:
        enabled: false
        filter_method: "tags"
        tags: ["election", "president", "congress"]
      
      sports:
        enabled: false
        filter_method: "tags"
        tags: ["nfl", "nba", "sports"]

# Multi-platform settings
multi_platform:
  enabled: false                      # Phase 10
  
  # Cross-platform features
  features:
    arbitrage_detection: false        # Detect price differences
    unified_position_tracking: false  # Track positions across platforms
    optimal_platform_selection: false # Choose best platform per trade
  
  # Arbitrage settings
  arbitrage:
    min_profit_threshold: 0.0200      # Min 2% profit after fees
    max_execution_time: 5             # Must execute both sides in 5 sec
    include_gas_fees: true            # Factor in Polymarket gas
```

---

## 6. data_sources.yaml

**Purpose:** Configure external APIs and polling

```yaml
config_version: "2.0"
last_updated: "2025-10-08"

# API endpoint configurations
apis:
  # ESPN (primary sports data)
  espn:
    enabled: true
    base_url: "https://site.api.espn.com"
    requires_api_key: false           # Public API
    
    endpoints:
      nfl_scoreboard: "/apis/site/v2/sports/football/nfl/scoreboard"
      nba_scoreboard: "/apis/site/v2/sports/basketball/nba/scoreboard"
      ncaaf_scoreboard: "/apis/site/v2/sports/football/college-football/scoreboard"
      mlb_scoreboard: "/apis/site/v2/sports/baseball/mlb/scoreboard"
    
    # Polling frequency by game state
    polling:
      frequency_pregame: 300          # Every 5 min before game
      frequency_active_game: 15       # Every 15 sec during game
      frequency_postgame: 600         # Every 10 min after game
      frequency_no_games: 3600        # Every hour when no games
    
    # Rate limits
    rate_limits:
      requests_per_minute: 60
      requests_per_day: unlimited     # Public API
      burst_limit: 10                 # Max 10 requests in burst
    
    # Retry logic
    retry:
      max_attempts: 3
      backoff_multiplier: 2           # 2, 4, 8 seconds
      timeout: 10                     # 10 second timeout
  
  # BallDontLie (backup NBA data)
  balldontlie:
    enabled: true
    base_url: "https://api.balldontlie.io"
    requires_api_key: true
    api_key_env: "BALLDONTLIE_API_KEY"
    
    endpoints:
      games: "/v1/games"
      stats: "/v1/stats"
    
    polling:
      frequency: 30                   # Backup data source
    
    rate_limits:
      requests_per_minute: 60         # Free tier
      requests_per_day: 1000
  
  # Sports Reference (historical data)
  sports_reference:
    enabled: false                    # Phase 4 (model building)
    base_url: "https://www.pro-football-reference.com"
    requires_scraping: true           # Not an API
    
    usage: "historical_data_only"     # Don't use for live data
  
  # RealClearPolitics (Phase 8 - politics)
  realclearpolitics:
    enabled: false
    base_url: "https://www.realclearpolitics.com"
    requires_scraping: true           # No public API
    
    polling:
      frequency: 3600                 # Every hour (polls change slowly)

# Fallback strategy
fallback_strategy:
  enabled: true
  
  # Define fallback order per sport
  sports:
    nfl:
      primary: "espn"
      secondary: null                 # No good backup for NFL
      failure_threshold: 3            # Switch after 3 failures
      retry_primary_after: 300        # Try primary again after 5 min
    
    nba:
      primary: "espn"
      secondary: "balldontlie"
      failure_threshold: 3
      retry_primary_after: 300
    
    ncaaf:
      primary: "espn"
      secondary: null
      failure_threshold: 3
      retry_primary_after: 300

# Data quality checks
data_quality:
  enabled: true
  
  checks:
    # Freshness check
    staleness_threshold: 60           # Alert if data >60s old
    
    # Consistency checks
    validate_score_monotonic: true    # Scores should only increase
    validate_time_decreasing: true    # Time should decrease
    validate_status_transitions: true # Valid status changes only
    
    # Outlier detection
    flag_large_score_jumps: true      # Flag if score jumps >14 points
    max_score_jump: 14
  
  # Actions on quality issues
  actions:
    on_stale_data:
      - "log_warning"
      - "switch_to_fallback"
      - "pause_trading_if_critical"
    
    on_consistency_error:
      - "log_error"
      - "quarantine_data"
      - "manual_review_required"
```

---

## 7. system.yaml

**Purpose:** System-wide configuration

```yaml
config_version: "2.0"
last_updated: "2025-10-08"

# Database configuration
database:
  connection_pool_size: 10
  connection_timeout: 30              # seconds
  enable_query_logging: false         # Set true for debugging
  log_slow_queries: true
  slow_query_threshold: 1000          # Log queries >1 second
  
  # Environment-specific settings
  environments:
    demo:
      host: "localhost"
      port: 5432
      database: "prescient_demo"
      auto_rollback: false
    
    prod:
      host: "localhost"               # Later: AWS RDS
      port: 5432
      database: "prescient_prod"
      auto_rollback: false
    
    test:
      host: "localhost"
      port: 5432
      database: "prescient_test"
      auto_rollback: true             # Rollback after tests
  
  # Active environment
  active_environment: "demo"
  
  # Backup schedule
  backup_schedule: "0 2 * * *"        # Daily at 2 AM (cron format)
  backup_retention_days: 90
  
  # Archival strategy
  archival:
    enabled: true
    hot_storage_months: 18            # Keep 18 months readily accessible
    warm_storage_years: 3.5           # Archive 3.5 years to S3/Glacier
    cold_storage_years: 10            # Long-term archive 10 years

# Logging configuration
logging:
  level: "INFO"                       # DEBUG, INFO, WARNING, ERROR, CRITICAL
  rotation: "30 days"
  compression: true
  max_size_mb: 100                    # Rotate when file exceeds 100MB
  
  # Log destinations
  destinations:
    file:
      enabled: true
      path: "logs/prescient.log"
      format: "detailed"              # timestamp, level, module, message
    
    console:
      enabled: true
      format: "pretty"                # Human-readable
      colored: true
    
    database:
      enabled: true                   # Log critical events to DB
      tables: ["trades", "circuit_breakers", "errors", "api_calls"]
      log_levels: ["WARNING", "ERROR", "CRITICAL"]
  
  # What to log
  log_categories:
    api_calls: true                   # Log all API calls
    trades: true                      # Log all trade decisions
    edges: true                       # Log edge calculations
    position_updates: true
    config_changes: true
    circuit_breakers: true
    errors: true

# Monitoring configuration
monitoring:
  health_check_interval: 300          # Check health every 5 min
  
  # Alert channels
  alert_channels:
    console:
      enabled: true
      min_level: "WARNING"
    
    email:
      enabled: false                  # Phase 6+
      smtp_host: "smtp.protonmail.com"
      smtp_port: 587
      smtp_user_env: "SMTP_USER"
      smtp_password_env: "SMTP_PASSWORD"
      recipients: ["your_email@proton.me"]
      min_level: "ERROR"
    
    sms:
      enabled: false                  # Phase 6+
      service: "twilio"
      account_sid_env: "TWILIO_ACCOUNT_SID"
      auth_token_env: "TWILIO_AUTH_TOKEN"
      from_number_env: "TWILIO_PHONE_NUMBER"
      to_numbers: ["+1234567890"]
      min_level: "CRITICAL"
  
  # Circuit breakers
  circuit_breakers:
    daily_loss_limit:
      enabled: true
      # ⚠️ Use DECIMAL format (not -500)
      threshold: -500.00              # Stop trading at -$500/day
      reset: "daily"                  # Reset at midnight
      reset_time: "00:00:00"          # UTC
      
      actions:
        - "halt_all_trading"
        - "alert_critical"
        - "log_to_database"
        - "require_manual_restart"
    
    hourly_trade_limit:
      enabled: true
      threshold: 10                   # Max 10 trades/hour
      reset: "hourly"
      
      actions:
        - "pause_trading_for_remainder_of_hour"
        - "alert_warning"
    
    api_failure_limit:
      enabled: true
      threshold: 5                    # Stop after 5 consecutive failures
      backoff: "exponential"          # 1s, 2s, 4s, 8s, 16s
      max_backoff: 300                # Max 5 min backoff
      
      actions:
        - "switch_to_fallback_api"
        - "alert_warning"
        - "log_failure_details"
    
    data_staleness:
      enabled: true
      threshold: 60                   # Alert if data >60 seconds old
      
      actions:
        - "pause_trading"
        - "alert_warning"
        - "attempt_data_refresh"
    
    position_concentration:
      enabled: true
      max_single_position_pct: 0.10   # Max 10% of total capital
      max_correlated_pct: 0.50        # Max 50% in correlated positions
      
      actions:
        - "block_trade"
        - "alert_warning"
    
    rapid_loss:
      enabled: true
      threshold_pct: 0.05             # If down 5% in 15 minutes
      time_window_seconds: 900
      
      actions:
        - "pause_trading_for_minutes: 30"
        - "alert_critical"
        - "require_manual_review"

# Scheduling
scheduling:
  # Market data updates
  market_update_frequency: 60         # seconds (default)
  
  # Dynamic scheduling based on game state
  dynamic_scheduling:
    enabled: true
    
    schedules:
      pregame:
        market_update: 300            # Every 5 min
        odds_recalculation: 600       # Every 10 min
      
      active_game:
        market_update: 15             # Every 15 sec
        odds_recalculation: 30        # Every 30 sec
        position_check: 15            # Every 15 sec
      
      postgame:
        market_update: 600            # Every 10 min
        settlement_check: 300         # Every 5 min
      
      critical_time:                  # Last 5 min of game
        market_update: 5              # Every 5 sec
        odds_recalculation: 10        # Every 10 sec
        position_check: 5             # Every 5 sec
  
  # Position reconciliation
  position_reconciliation_frequency: 300  # Every 5 min
  
  # Daily jobs (cron format)
  daily_jobs:
    - name: "backup_database"
      schedule: "0 2 * * *"           # 2 AM daily
    
    - name: "generate_daily_report"
      schedule: "0 6 * * *"           # 6 AM daily
    
    - name: "model_validation_check"
      schedule: "0 12 * * *"          # Noon daily
    
    - name: "cleanup_old_logs"
      schedule: "0 3 * * 0"           # 3 AM Sunday

# Performance
performance:
  # Connection pooling
  enable_connection_pooling: true
  pool_size: 10
  pool_overflow: 5
  pool_recycle: 3600                  # Recycle connections after 1 hour
  
  # Caching
  enable_caching: true
  cache_backend: "memory"             # Later: "redis"
  cache_ttl_seconds: 300              # 5 minutes
  
  # Query optimization
  enable_query_plan_cache: true
  prepared_statements: true
  
  # Rate limiting
  enable_rate_limiting: true
  max_requests_per_second: 10

# Security
security:
  # API key storage
  api_keys_encrypted: true            # Phase 6+
  encryption_key_env: "ENCRYPTION_KEY"
  
  # Database credentials
  db_password_env: "DB_PASSWORD"
  
  # Secrets management
  use_aws_secrets_manager: false      # Phase 6+
  secrets_manager_region: "us-east-1"
  
  # Audit logging
  audit_all_trades: true
  audit_all_config_changes: true
  audit_retention_days: 365
```

---

## Environment Variables (.env)

```bash
# ============================================
# API CREDENTIALS - KALSHI
# ============================================
# Demo Environment
KALSHI_DEMO_API_KEY=your_demo_key_here
KALSHI_DEMO_API_SECRET=your_demo_secret_here

# Production Environment
KALSHI_PROD_API_KEY=your_prod_key_here
KALSHI_PROD_API_SECRET=your_prod_secret_here

# ============================================
# API CREDENTIALS - POLYMARKET (Phase 10)
# ============================================
POLYMARKET_PRIVATE_KEY=your_private_key_here

# ============================================
# API CREDENTIALS - DATA SOURCES
# ============================================
BALLDONTLIE_API_KEY=your_key_here

# ============================================
# DATABASE CREDENTIALS
# ============================================
DB_HOST=localhost
DB_PORT=5432
DB_NAME=prescient_prod
DB_USER=postgres
DB_PASSWORD=your_secure_password_here

# ============================================
# ALERT SERVICES (Phase 6+)
# ============================================
# Email (Proton Mail)
SMTP_HOST=smtp.protonmail.com
SMTP_PORT=587
SMTP_USER=your_email@proton.me
SMTP_PASSWORD=your_app_password_here

# SMS (Twilio)
TWILIO_ACCOUNT_SID=your_sid_here
TWILIO_AUTH_TOKEN=your_token_here
TWILIO_PHONE_NUMBER=+1234567890
ALERT_PHONE_NUMBER=+1234567890

# ============================================
# SECURITY (Phase 6+)
# ============================================
ENCRYPTION_KEY=your_encryption_key_here
JWT_SECRET=your_jwt_secret_here

# ============================================
# AWS (Phase 6+)
# ============================================
AWS_ACCESS_KEY_ID=your_aws_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_here
AWS_REGION=us-east-1
```

---

## Configuration Access in Code

### Loading Configuration

```python
from utils.config import Config
from decimal import Decimal

# Initialize config system
config = Config()

# Get value with dot notation
min_volume = config.get('trading.categories.sports.nfl.liquidity.min_volume')
# Returns: 100

# Get with default value
timeout = config.get('api.timeout', default=30)

# Get decimal values (CRITICAL for prices!)
max_spread = config.get('trading.categories.sports.nfl.execution.max_spread')
# Returns: Decimal('0.0500')  # NOT 0.05 float!

# Check if feature enabled
if config.get('trade_strategies.strategies.halftime_entry.enabled'):
    execute_halftime_strategy()

# Get platform-specific config
kalshi_config = config.get('markets.platforms.kalshi')
```

### Priority Resolution

```python
# Priority order: DB Override > YAML > Code Default

def get_config_value(key: str, default=None):
    """
    1. Check database for override
    2. If not found, check YAML
    3. If not in YAML, use default
    """
    # Check database first
    override = db.query("""
        SELECT override_value 
        FROM config_overrides 
        WHERE config_key = %s 
          AND active = TRUE
          AND (expires_at IS NULL OR expires_at > NOW())
    """, key)
    
    if override:
        return override
    
    # Check YAML
    yaml_value = config.get(key)
    if yaml_value is not None:
        return yaml_value
    
    # Use default
    return default
```

### Runtime Updates (Database Overrides)

```python
# Update config without restart
config.set_override(
    key='trading.categories.sports.nfl.execution.max_spread',
    value=Decimal('0.0800'),  # ⚠️ ALWAYS use Decimal for prices!
    reason='Testing wider spread tolerance during low liquidity',
    expires_at=datetime.now() + timedelta(hours=24)
)

# Remove override (revert to YAML)
config.remove_override('trading.categories.sports.nfl.execution.max_spread')

# List all active overrides
overrides = config.list_overrides()
```

---

## CLI Configuration Commands

```bash
# View configuration
python main.py config-show                      # Show all config
python main.py config-show --category trading   # Show just trading config
python main.py config-get trading.categories.sports.nfl.execution.max_spread
# Output: 0.0500

# Validate configuration
python main.py config-validate                  # Validate all YAML files
python main.py config-validate --file trading.yaml

# List overrides
python main.py config-list-overrides
python main.py config-list-overrides --active-only
python main.py config-list-overrides --expired

# Set runtime override
python main.py config-set \
  trading.categories.sports.nfl.execution.max_spread \
  0.0800 \
  --reason "Testing wider spread" \
  --expires "24h"

# Remove override
python main.py config-remove-override \
  trading.categories.sports.nfl.execution.max_spread

# Configuration migration
python main.py config-migrate --from-version 1.0 --to-version 2.0
```

---

## Configuration Validation Rules

### Automatic Validation

When `config-validate` runs, it checks:

```python
# Validation rules
VALIDATION_RULES = {
    # Decimals must be in range
    'trading.*.confidence_thresholds.*': {
        'type': Decimal,
        'min': Decimal('0.0001'),
        'max': Decimal('1.0000')
    },
    
    # Kelly fraction must be reasonable
    'trading.*.position_sizing.kelly_fraction': {
        'type': Decimal,
        'min': Decimal('0.01'),
        'max': Decimal('1.00')
    },
    
    # Max spread must be positive
    'trading.*.execution.max_spread': {
        'type': Decimal,
        'min': Decimal('0.0001'),
        'max': Decimal('0.5000')  # 50¢ max
    },
    
    # Logical relationships
    'trading.*.position_sizing': {
        'rules': [
            'max_position_size < max_total_exposure',
            'max_correlated_exposure <= max_total_exposure'
        ]
    },
    
    # Thresholds must be ordered
    'trading.*.confidence_thresholds': {
        'rules': [
            'ignore_threshold < alert_threshold',
            'alert_threshold < auto_execute_threshold'
        ]
    }
}
```

---

## Configuration Versioning & Migration

### Version Header (All YAML Files)

```yaml
# Every YAML file starts with:
config_version: "2.0"
last_updated: "2025-10-08"
```

### Migration Scripts

When config structure changes:

```bash
# Example migration from v1.0 to v2.0
python main.py config-migrate --from 1.0 --to 2.0

# What it does:
# 1. Backs up old config to config/backups/
# 2. Applies structural changes
# 3. Validates new config
# 4. Updates version headers
```

### Backward Compatibility

System supports two versions during transition:

```python
# Config loader handles both formats
def load_trading_config():
    config = load_yaml('trading.yaml')
    version = config.get('config_version')
    
    if version == "1.0":
        # Old format: single threshold
        return convert_v1_to_v2(config)
    
    elif version == "2.0":
        # New format: category-specific
        return config
    
    else:
        raise ValueError(f"Unsupported config version: {version}")
```

---

## Best Practices

### When to Use Each Configuration Method

**YAML Files:**
- Default settings for production
- Settings that rarely change
- Settings needed at startup
- Anything that should be version-controlled

**Database Overrides:**
- Emergency adjustments during live trading
- Temporary experiments
- Circuit breaker resets
- Per-market customizations
- A/B testing parameters

**Environment Variables:**
- Secrets (API keys, passwords)
- Environment-specific values (database hosts)
- Deployment configuration
- Never commit to Git

### Configuration Change Workflow

1. **Test in demo environment first**
   ```bash
   # Set demo override
   python main.py config-set --env demo trading.*.max_spread 0.0800
   ```

2. **Validate with config-validate**
   ```bash
   python main.py config-validate
   ```

3. **Use DB override for live testing**
   ```bash
   # 24-hour experiment
   python main.py config-set trading.*.max_spread 0.0800 \
     --expires "24h" \
     --reason "Testing wider spread tolerance"
   ```

4. **Monitor results**
   - Check trade execution
   - Monitor edge capture rate
   - Watch for adverse selection

5. **If successful, update YAML permanently**
   ```bash
   # Edit config/trading.yaml
   # Commit to Git
   git add config/trading.yaml
   git commit -m "Increase max_spread to 0.0800 based on testing"
   ```

6. **Document rationale**
   - Update DESIGN_DECISIONS.md
   - Add entry to CHANGELOG.md

---

## Troubleshooting

### Common Issues

**Issue:** Config changes not taking effect
```bash
# Check override precedence
python main.py config-debug trading.categories.sports.nfl.execution.max_spread
# Shows: DB Override > YAML > Default
```

**Issue:** Decimal values showing as floats
```python
# ❌ WRONG
max_spread = 0.05

# ✅ CORRECT
max_spread = Decimal('0.0500')
```

**Issue:** Config validation failing
```bash
# See detailed errors
python main.py config-validate --verbose
```

---

## Next Steps

1. **Review all YAML files** in `/config` directory
2. **Set up `.env` file** with your API credentials
3. **Validate configuration** before Phase 1
   ```bash
   python main.py config-validate
   ```
4. **Test configuration loading** in Phase 1

---

**Document Version:** 2.0  
**Last Updated:** October 8, 2025  
**Changes:** Corrected decimal pricing, added platform/sport-specific configs, enhanced for multi-platform expansion  
**Purpose:** Configuration reference and usage guide
