"""
CRUD operations for Precog database with SCD Type 2 versioning support.

SCD Type 2 (Slowly Changing Dimension) Explained:
--------------------------------------------------
Imagine a Wikipedia article with full edit history. Instead of OVERWRITING the article
(losing the old version), Wikipedia saves each edit as a new version. You can:
- View the current version (what users see now)
- View historical versions (what it looked like on 2023-05-15)
- Compare changes between versions

We do the SAME thing for market snapshots and positions:

**Traditional Database (Loses History):**
```sql
UPDATE market_snapshots SET yes_ask_price = 0.5500 WHERE market_id = 42
-- Old price (0.5200) is GONE FOREVER
-- Can't backtest strategies with historical prices
-- Can't audit "what price did we see at 2PM yesterday?"
```

**SCD Type 2 (Preserves History):**
```sql
-- Step 1: Mark current snapshot as historical
UPDATE market_snapshots SET row_current_ind = FALSE, row_end_ts = NOW()
WHERE market_id = 42 AND row_current_ind = TRUE

-- Step 2: Insert new snapshot version
INSERT INTO market_snapshots (..., row_current_ind = TRUE, row_start_ts = NOW())
VALUES (42, 0.5500, ...)
-- Old price (0.5200) preserved with timestamps
-- Can backtest with exact historical prices
-- Full audit trail for compliance
```

Visual Example - Market Snapshot Price History:
```
┌───────────┬───────────────┬─────────────────────┬─────────────────────┬────────────────┐
│ market_id │yes_ask_price  │ row_start_ts        │ row_end_ts          │row_current_ind │
├───────────┼───────────────┼─────────────────────┼─────────────────────┼────────────────┤
│  42       │ 0.5200        │ 2024-01-01 10:00:00 │ 2024-01-01 11:00:00 │ FALSE (old)    │
│  42       │ 0.5350        │ 2024-01-01 11:00:00 │ 2024-01-01 13:00:00 │ FALSE (old)    │
│  42       │ 0.5500        │ 2024-01-01 13:00:00 │ NULL                │ TRUE (current) │
└───────────┴───────────────┴─────────────────────┴─────────────────────┴────────────────┘

Query for CURRENT price:
    SELECT * FROM market_snapshots WHERE market_id = 42 AND row_current_ind = TRUE
    -> Returns 0.5500 (latest version only)

Query for HISTORICAL prices:
    SELECT * FROM market_snapshots WHERE market_id = 42 ORDER BY row_start_ts
    -> Returns all 3 versions (complete price history)
```

Why This Matters for Trading:
------------------------------
**1. Backtesting Accuracy**
   - Test strategies against EXACT historical prices (not approximations)
   - Know "what price did the API show at 2:15:37 PM on Game Day?"
   - Reproduce trading decisions with 100% accuracy

**2. Compliance & Auditing**
   - SEC/regulatory requirement: "Why did you execute this trade?"
   - Answer: "Market showed 0.5200 at 14:15:37, our model predicted 0.5700, edge = 0.0500"
   - Prove it with immutable database records

**3. Trade Attribution**
   - Every trade links to EXACT strategy version (v1.0, v1.1, v2.0)
   - A/B testing: "Did strategy v1.1 perform better than v1.0?"
   - Know EXACTLY which config generated each trade

**4. Position Monitoring**
   - Track unrealized P&L changes over time
   - Know when trailing stop was triggered (exact price and timestamp)
   - Reconstruct "why did we exit at 0.5800 instead of 0.6000?"

**5. Debugging**
   - "Why didn't we enter this market?" -> Check historical prices
   - "Did our price feed freeze?" -> Check row timestamps
   - "When did this market close?" -> Check status history

The row_current_ind Pattern (CRITICAL):
----------------------------------------
**ALWAYS query with row_current_ind = TRUE to get current data!**

```python
# ✅ CORRECT - Gets current market price only
current_market = db.execute('''
    SELECT * FROM markets
    WHERE ticker = %s
      AND row_current_ind = TRUE
''', ('NFL-KC-YES',))

# ❌ WRONG - Gets ALL versions (including historical)
all_versions = db.execute('''
    SELECT * FROM markets
    WHERE ticker = %s
''', ('NFL-KC-YES',))
# ^ This returns 50 historical rows! Your code will use RANDOM old price!
```

**Common Mistake:**
Forgetting `row_current_ind = TRUE` causes bugs where code uses stale prices
from 3 days ago instead of current market price. ALWAYS filter by row_current_ind!

**When to query historical versions:**
```python
# Get price history for charting
history = db.execute('''
    SELECT yes_ask_price, row_start_ts, row_end_ts
    FROM market_snapshots ms
    JOIN markets m ON ms.market_id = m.id
    WHERE m.ticker = %s
    ORDER BY ms.row_start_ts DESC
    LIMIT 100
''', ('NFL-KC-YES',))
```

Performance Implications:
-------------------------
**Storage Cost:**
- Each price update creates NEW row (not UPDATE)
- 1000 price updates per day = 1000 rows (vs 1 row with UPDATE)
- PostgreSQL handles this efficiently with indexes
- Typical size: ~500 bytes/row -> 500 KB/day per active market
- For 100 active markets: ~50 MB/day (negligible)

**Query Performance:**
- `WHERE row_current_ind = TRUE` uses BTREE index (fast: <1ms)
- Historical queries may scan more rows (add LIMIT to prevent full table scan)
- Vacuum regularly to reclaim space from old versions

**When to use SCD Type 2:**
- ✅ Markets (prices change frequently, need audit trail)
- ✅ Positions (track unrealized P&L changes, trailing stops)
- ✅ Account Balance (track deposits/withdrawals/P&L)
- ❌ Strategies (use immutable versioning instead - see versioning guide)
- ❌ Probability Models (use immutable versioning instead)

Trade Attribution Pattern:
--------------------------
**EVERY trade MUST link to exact strategy and model versions:**

```python
# ✅ CORRECT - Full attribution
trade = create_trade(
    market_id=42,
    strategy_id=1,   # Links to strategies.strategy_id (v1.0)
    model_id=2,      # Links to probability_models.model_id (v2.1)
    quantity=100,
    price=Decimal("0.5200")
)

# Later: Analyze which strategy version performed best
performance = db.execute('''
    SELECT s.strategy_version, AVG(t.realized_pnl) as avg_pnl
    FROM trades t
    JOIN strategies s ON t.strategy_id = s.strategy_id
    GROUP BY s.strategy_version
    ORDER BY avg_pnl DESC
''')
# Output: v1.1 = +$4.50/trade, v1.0 = +$2.10/trade
# Conclusion: v1.1 is 2x better! Keep using it.
```

**Why immutable strategy versions matter:**
If we allowed modifying strategy configs, we'd lose ability to attribute performance.
Example: Strategy v1.0 config changes from `min_edge=0.05` to `min_edge=0.10`.
Now we can't tell which trades used which config! Solution: Create v1.1 instead.

Security - SQL Injection Prevention:
------------------------------------
**ALL functions use parameterized queries:**

```python
# ✅ CORRECT - Safe from SQL injection
ticker = user_input  # Could be malicious: "'; DROP TABLE markets; --"
result = db.execute(
    "SELECT * FROM markets WHERE ticker = %s",
    (ticker,)  # PostgreSQL escapes this safely
)

# ❌ WRONG - SQL injection vulnerability
query = f"SELECT * FROM markets WHERE ticker = '{ticker}'"
# ^ If ticker = "'; DROP TABLE markets; --" -> DELETES ALL DATA!
```

**Key principle:** NEVER concatenate user input into SQL strings.
ALWAYS use parameterized queries with %s placeholders.

Common Operations Cheat Sheet:
------------------------------
```python
# Create new market
market_pk = create_market(
    platform_id="kalshi",
    ticker="NFL-KC-YES",
    yes_ask_price=Decimal("0.5200"),
    no_ask_price=Decimal("0.4800")
)

# Get current market data (dimension + latest snapshot)
market = get_current_market("NFL-KC-YES")  # Returns latest version only

# Update market price (creates new snapshot version)
new_id = update_market_with_versioning(
    ticker="NFL-KC-YES",
    yes_ask_price=Decimal("0.5500")
)
# Old version: row_current_ind = FALSE (preserved)
# New version: row_current_ind = TRUE (active)

# Get price history for backtesting
history = get_market_history("NFL-KC-YES", limit=100)
# Returns all versions ordered by newest first

# Create position
pos_id = create_position(
    market_id=42,
    strategy_id=1,
    model_id=2,
    side='YES',
    quantity=100,
    entry_price=Decimal("0.5200")
)

# Update position price (monitoring)
update_position_price(
    position_id=pos_id,
    current_price=Decimal("0.5800"),
    trailing_stop_state={"peak": "0.5800", "stop": "0.5500"}
)

# Close position
close_position(
    position_id=pos_id,
    exit_price=Decimal("0.6000"),
    exit_reason='target_hit',
    realized_pnl=Decimal("8.00")
)

# Record trade with attribution
trade_id = create_trade(
    market_id=42,
    strategy_id=1,  # Which strategy version generated this?
    model_id=2,     # Which model version predicted probability?
    side='YES',
    quantity=100,
    price=Decimal("0.5200")
)
```

Reference: docs/database/DATABASE_SCHEMA_SUMMARY.md
Related Requirements: REQ-DB-003 (SCD Type 2 Versioning)
Related ADR: ADR-019 (Historical Data Versioning Strategy)
Related Guide: docs/guides/VERSIONING_GUIDE_V1.0.md
"""

# Phase 1a extractions
from .crud_account import (  # noqa: F401
    create_account_balance,
    create_settlement,
    update_account_balance_with_versioning,
)

# Phase 1b/1c extractions
from .crud_analytics import (  # noqa: F401
    _VALID_ENTITY_TYPES,
    _VALID_RUN_STATUSES,
    _VALID_RUN_TYPES,
    complete_backtesting_run,
    complete_evaluation_run,
    create_backtesting_run,
    create_edge,
    create_evaluation_run,
    create_prediction,
    get_backtesting_run,
    get_edge_lifecycle,
    get_edges_by_strategy,
    get_evaluation_run,
    get_performance_metrics,
    get_predictions_by_run,
    get_unresolved_predictions,
    resolve_prediction,
    update_edge_outcome,
    update_edge_status,
    upsert_performance_metric,
)
from .crud_elo import (  # noqa: F401
    get_elo_calculation_logs,
    get_team_elo_by_code,
    get_team_elo_rating,
    insert_elo_calculation_log,
    update_team_classification,
    update_team_elo_rating,
)
from .crud_events import (  # noqa: F401
    _fill_event_null_fields,
    create_event,
    create_series,
    get_event,
    get_or_create_event,
    get_or_create_series,
    get_series,
    list_series,
    update_series,
)
from .crud_game_states import (  # noqa: F401
    LEAGUE_SPORT_CATEGORY,
    TRACKED_SITUATION_KEYS,
    build_event_result,
    check_event_fully_settled,
    create_game_state,
    find_game_by_matchup,
    find_unlinked_sports_events,
    game_state_changed,
    get_current_game_state,
    get_game_state_history,
    get_games_by_date,
    get_live_games,
    get_or_create_game,
    update_bracket_counts,
    update_event,
    update_event_game_id,
    update_game_result,
    upsert_game_odds,
    upsert_game_state,
)
from .crud_historical import (  # noqa: F401
    get_historical_rankings,
    get_historical_stats,
    get_player_stats,
    get_team_ranking_history,
    get_team_stats,
    insert_historical_ranking,
    insert_historical_rankings_batch,
    insert_historical_stat,
    insert_historical_stats_batch,
)
from .crud_ledger import (  # noqa: F401
    _VALID_ALIGNMENT_QUALITIES,
    _VALID_REFERENCE_TYPES,
    _VALID_TAKER_SIDES,
    _VALID_TRANSACTION_TYPES,
    create_ledger_entry,
    get_alignments_by_market,
    get_latest_trade_time,
    get_ledger_entries,
    get_market_trades,
    get_running_balance,
    insert_temporal_alignment,
    insert_temporal_alignment_batch,
    upsert_market_trade,
    upsert_market_trades_batch,
)
from .crud_markets import (  # noqa: F401
    count_open_markets,
    create_market,
    get_current_market,
    get_latest_orderbook,
    get_market_history,
    get_markets_summary,
    get_orderbook_history,
    insert_orderbook_snapshot,
    update_market_with_versioning,
)
from .crud_orders import (  # noqa: F401
    KALSHI_STATUS_MAP,
    cancel_order,
    create_order,
    get_open_orders,
    get_order_by_external_id,
    get_order_by_id,
    update_order_fill,
    update_order_status,
)
from .crud_positions import (  # noqa: F401
    close_position,
    create_position,
    create_trade,
    get_current_positions,
    get_position_by_id,
    get_positions_with_pnl,
    get_recent_trades,
    get_trade_by_id,
    get_trades_by_market,
    update_position_price,
)
from .crud_schedulers import (  # noqa: F401
    check_active_schedulers,
    cleanup_stale_schedulers,
    delete_scheduler_status,
    get_scheduler_status,
    list_scheduler_services,
    upsert_scheduler_status,
)
from .crud_shared import (  # noqa: F401
    VALID_SYSTEM_HEALTH_COMPONENTS,
    DecimalEncoder,
    ExecutionEnvironment,
    SystemHealthComponent,
    _convert_config_strings_to_decimal,
    validate_decimal,
)
from .crud_strategies import (  # noqa: F401
    create_strategy,
    get_active_strategy_version,
    get_all_strategy_versions,
    get_strategy,
    get_strategy_by_name_and_version,
    list_strategies,
    update_strategy_status,
)
from .crud_system import (  # noqa: F401
    create_alert,
    create_circuit_breaker_event,
    get_active_breakers,
    get_system_health,
    get_system_health_summary,
    resolve_circuit_breaker,
    upsert_system_health,
)
from .crud_teams import (  # noqa: F401
    create_external_team_code,
    create_team,
    create_team_ranking,
    create_venue,
    delete_external_team_code,
    find_team_by_external_code,
    get_current_rankings,
    get_external_team_codes,
    get_team_by_espn_id,
    get_team_by_kalshi_code,
    get_team_rankings,
    get_teams_with_kalshi_codes,
    get_venue_by_espn_id,
    get_venue_by_id,
    upsert_external_team_code,
)
