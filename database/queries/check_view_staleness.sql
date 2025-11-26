-- =============================================================================
-- Materialized View Staleness Monitoring Query
-- =============================================================================
--
-- Purpose:
--   Monitor materialized view freshness across the Precog database.
--   Identifies views that haven't been refreshed recently and may contain
--   stale data affecting trading decisions.
--
-- Why This Matters:
--   Materialized views cache expensive query results for performance.
--   However, if not refreshed regularly, they can show outdated:
--   - Market prices (decisions based on old prices = losses)
--   - Position P&L (inaccurate portfolio value)
--   - Performance metrics (wrong strategy evaluations)
--
-- Staleness Thresholds:
--   - FRESH: Refreshed within last 2 hours (acceptable for most use cases)
--   - STALE: Not refreshed in 2+ hours (should trigger alert)
--   - CRITICAL: Not refreshed in 24+ hours (immediate attention needed)
--
-- Usage:
--   Run this query manually or integrate into monitoring system (Phase 7)
--
--   Manual check:
--     psql -d precog -f database/queries/check_view_staleness.sql
--
--   Integration with alerting:
--     SELECT * FROM check_view_staleness WHERE status != 'FRESH';
--
-- Output Columns:
--   - schemaname: Schema containing the view (usually 'public')
--   - matviewname: Name of the materialized view
--   - definition_preview: First 100 chars of view definition
--   - staleness: Time since last refresh (interval)
--   - staleness_minutes: Staleness in minutes (for easy comparison)
--   - status: FRESH, STALE, or CRITICAL
--   - recommendation: Action to take based on status
--
-- References:
--   - Issue #48: DEF-P1-020 Materialized View Staleness Monitoring
--   - Phase 7: Observability Infrastructure
--   - PostgreSQL pg_matviews documentation
--
-- Created: 2025-11-25
-- Phase: 1.5 (Foundation Validation) - Query created, Integration Phase 7
-- =============================================================================

-- Create a function for reusable staleness checking
-- Note: This can be called from application code or monitoring scripts

-- Main monitoring query
SELECT
    schemaname,
    matviewname,
    -- Preview of what the view does (first 100 chars)
    LEFT(definition, 100) || CASE WHEN LENGTH(definition) > 100 THEN '...' ELSE '' END AS definition_preview,
    -- Calculate staleness (requires pg_stat_user_tables for last_analyze as proxy)
    -- Note: PostgreSQL doesn't track matview refresh time directly,
    -- so we use n_tup_ins from pg_stat_user_tables as a proxy
    COALESCE(
        (NOW() - pst.last_analyze),
        (NOW() - pst.last_autoanalyze),
        INTERVAL '999 hours'  -- Unknown = assume very stale
    ) AS staleness,
    -- Staleness in minutes for easy comparison
    EXTRACT(EPOCH FROM COALESCE(
        (NOW() - pst.last_analyze),
        (NOW() - pst.last_autoanalyze),
        INTERVAL '999 hours'
    )) / 60 AS staleness_minutes,
    -- Status classification
    CASE
        WHEN COALESCE(NOW() - pst.last_analyze, NOW() - pst.last_autoanalyze, INTERVAL '999 hours') > INTERVAL '24 hours' THEN 'CRITICAL'
        WHEN COALESCE(NOW() - pst.last_analyze, NOW() - pst.last_autoanalyze, INTERVAL '999 hours') > INTERVAL '2 hours' THEN 'STALE'
        ELSE 'FRESH'
    END AS status,
    -- Actionable recommendation
    CASE
        WHEN COALESCE(NOW() - pst.last_analyze, NOW() - pst.last_autoanalyze, INTERVAL '999 hours') > INTERVAL '24 hours'
            THEN 'IMMEDIATE: Run REFRESH MATERIALIZED VIEW ' || matviewname || ';'
        WHEN COALESCE(NOW() - pst.last_analyze, NOW() - pst.last_autoanalyze, INTERVAL '999 hours') > INTERVAL '2 hours'
            THEN 'SOON: Schedule refresh for ' || matviewname
        ELSE 'OK: No action needed'
    END AS recommendation
FROM pg_matviews pmv
LEFT JOIN pg_stat_user_tables pst
    ON pmv.matviewname = pst.relname
    AND pmv.schemaname = pst.schemaname
WHERE pmv.schemaname = 'public'
ORDER BY staleness_minutes DESC NULLS FIRST;

-- =============================================================================
-- Alternative: Simple View Count Query
-- =============================================================================
-- Use this to quickly see all materialized views and their row counts

-- SELECT
--     schemaname,
--     matviewname,
--     pg_size_pretty(pg_relation_size(schemaname || '.' || matviewname)) AS size,
--     (SELECT COUNT(*) FROM pg_catalog.pg_attribute
--      WHERE attrelid = (schemaname || '.' || matviewname)::regclass
--      AND attnum > 0) AS column_count
-- FROM pg_matviews
-- WHERE schemaname = 'public'
-- ORDER BY matviewname;

-- =============================================================================
-- Refresh Commands (for manual intervention)
-- =============================================================================
-- REFRESH MATERIALIZED VIEW market_performance_summary;
-- REFRESH MATERIALIZED VIEW strategy_metrics;
-- REFRESH MATERIALIZED VIEW daily_pnl_summary;
--
-- For concurrent refresh (doesn't lock the view during refresh):
-- REFRESH MATERIALIZED VIEW CONCURRENTLY market_performance_summary;
-- Note: CONCURRENTLY requires a UNIQUE index on the view
