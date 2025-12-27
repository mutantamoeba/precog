# Database Tables Reference - Quick Lookup

---
**Created:** 2025-10-23
**Last Updated:** 2025-12-26
**Database:** precog_dev
**Schema:** public
**Total Tables:** 31
**Purpose:** Quick reference for developers - detailed data dictionary in DATABASE_SCHEMA_SUMMARY_V1.15.md
---

## Quick Summary: All 31 Tables in precog_dev

### Core Platform (4 tables)
1. **platforms** - Multi-platform support (Kalshi, Polymarket)
2. **series** - Market hierarchy
3. **events** - Game/event instances
4. **markets** - Binary outcomes with DECIMAL(10,4) prices

### Live Sports Data (4 tables - Phase 2)
5. **venues** - Normalized stadium/arena data from ESPN API (NEW v1.12)
6. **teams** - Team entities with Elo ratings and multi-sport support
7. **team_rankings** - AP Poll, CFP, Coaches Poll with temporal validity (NEW v1.12)
8. **game_states** - Live game state tracking with SCD Type 2 versioning (NEW v1.12)

### Data & Analytics (3 tables)
9. **probability_matrices** - Historical probabilities
10. **probability_models** - Immutable model versions (no row_current_ind)
11. **strategies** - Immutable strategy versions (no row_current_ind)

### Trading & Risk (7 tables)
12. **edges** - EV+ opportunities with strategy_id/model_id FKs
13. **positions** - Open positions with trailing_stop_state JSONB + monitoring fields
14. **trades** - Executed orders with strategy_id/model_id attribution
15. **position_exits** - Exit events (Phase 5, append-only)
16. **exit_attempts** - Order attempts for debugging (Phase 5, append-only)
17. **settlements** - Final outcomes
18. **account_balance** - Account balances with versioning

### System Utilities (4 tables)
19. **config_overrides** - Database config overrides
20. **circuit_breaker_events** - Risk management events
21. **system_health** - System monitoring
22. **alerts** - Centralized alert/notification logging

### Lookup Tables (2 tables - Phase 1.5)
23. **strategy_types** - Strategy approach enum values
24. **model_classes** - Model approach enum values

### Performance Tracking (5 tables - Phase 1.5-2)
25. **performance_metrics** - Unified metrics for strategies/models
26. **evaluation_runs** - Model validation/backtesting tracking
27. **predictions** - Individual + ensemble predictions
28. **ab_test_groups** - A/B testing configuration (Phase 9)
29. **ab_test_results** - A/B test outcomes (Phase 9)

### Cold Storage (2 tables - Phase 2+)
30. **performance_metrics_archive** - Archival for 42+ month old data
31. **model_calibration_summary** - Materialized view for calibration

---

## Key Features

✅ **DECIMAL Precision** - All prices use numeric(10,4)
✅ **Two Versioning Patterns** - row_current_ind vs immutable versions
✅ **Trade Attribution** - Every trade links to strategy & model versions
✅ **Phase 5 Exit Management** - 10 exit conditions, partial exits, price walking
✅ **SCD Type 2** - Complete history for markets, positions, game_states
✅ **Multi-Sport Support** - 6 leagues: NFL, NCAAF, NBA, NCAAB, NHL, WNBA

---

## Phase 2 Tables (NEW in v1.12)

### venues
```sql
-- Normalized stadium/arena data
SELECT * FROM venues WHERE espn_venue_id = '3622';  -- Arrowhead Stadium
```

### team_rankings
```sql
-- Get current AP Poll top 10
SELECT t.team_name, tr.rank, tr.points
FROM team_rankings tr
JOIN teams t ON tr.team_id = t.team_id
WHERE tr.ranking_type = 'ap_poll'
  AND tr.season = 2024
  AND tr.week = (SELECT MAX(week) FROM team_rankings WHERE ranking_type = 'ap_poll' AND season = 2024)
ORDER BY tr.rank
LIMIT 10;
```

### game_states (SCD Type 2)
```sql
-- Get current game state
SELECT * FROM game_states
WHERE espn_event_id = '401547417'
  AND row_current_ind = TRUE;

-- Get game state history
SELECT game_state_id, home_score, away_score, clock_display, row_start_timestamp
FROM game_states
WHERE espn_event_id = '401547417'
ORDER BY row_start_timestamp;
```

---

## Common Query Patterns

### Get Current Market Price
```sql
SELECT yes_price, no_price
FROM markets
WHERE ticker = 'NFL-KC-BUF-YES'
  AND row_current_ind = TRUE;
```

### Get Active Strategy Version
```sql
SELECT * FROM strategies
WHERE strategy_name = 'halftime_entry'
  AND status = 'active'
ORDER BY strategy_version DESC
LIMIT 1;
```

### Get Open Positions with Latest Prices
```sql
SELECT
    p.*,
    m.yes_price as current_market_price,
    (m.yes_price - p.entry_price) * p.quantity as unrealized_pnl
FROM positions p
JOIN markets m ON p.market_id = m.market_id
WHERE p.status = 'open'
  AND p.row_current_ind = TRUE
  AND m.row_current_ind = TRUE;
```

### Get Live Games with Teams
```sql
SELECT
    gs.espn_event_id,
    t_home.display_name AS home_team,
    gs.home_score,
    t_away.display_name AS away_team,
    gs.away_score,
    gs.clock_display,
    gs.game_status
FROM game_states gs
JOIN teams t_home ON gs.home_team_id = t_home.team_id
JOIN teams t_away ON gs.away_team_id = t_away.team_id
WHERE gs.row_current_ind = TRUE
  AND gs.game_status = 'in_progress'
ORDER BY gs.league, gs.game_date;
```

---

**For complete schema details:** See `DATABASE_SCHEMA_SUMMARY_V1.15.md`
**For comprehensive data dictionary:** Planned for Phase 6-7

**END OF REFERENCE**
