-- Migration 002: Add Alerts Table
-- Version: 002
-- Created: 2025-10-23
-- Phase: 1 (Foundation Completion)
-- Purpose: Create centralized alerts table for notification logging and tracking

-- ==============================================================================
-- ALERTS TABLE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS alerts (
    -- Primary Key
    alert_id SERIAL PRIMARY KEY,
    alert_uuid UUID DEFAULT gen_random_uuid() UNIQUE,

    -- Classification
    alert_type VARCHAR NOT NULL,        -- 'circuit_breaker', 'api_failure', 'loss_threshold', 'health_degraded'
    severity VARCHAR NOT NULL,          -- 'critical', 'high', 'medium', 'low'
    category VARCHAR,                   -- 'risk', 'system', 'trading', 'data'
    component VARCHAR NOT NULL,         -- 'kalshi_api', 'edge_detector', 'position_manager'

    -- Message
    message TEXT NOT NULL,              -- Human-readable alert message
    details JSONB,                      -- Additional context (stack traces, metrics, config values)

    -- Source tracking
    source_table VARCHAR,               -- 'circuit_breaker_events', 'system_health', 'trades'
    source_id INT,                      -- FK to source table record

    -- Timestamps
    triggered_at TIMESTAMP DEFAULT NOW() NOT NULL,
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP,

    -- Acknowledgement & Resolution
    acknowledged_by VARCHAR,            -- Username or system
    acknowledged_notes TEXT,
    resolved_by VARCHAR,
    resolved_notes TEXT,
    resolution_action VARCHAR,          -- 'fixed', 'false_positive', 'ignored', 'escalated'

    -- Notification tracking
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_channels JSONB,        -- {'email': true, 'sms': true, 'slack': false}
    notification_sent_at TIMESTAMP,
    notification_attempts INT DEFAULT 0,
    notification_errors JSONB,          -- Track delivery failures

    -- Deduplication
    fingerprint VARCHAR(64),            -- MD5 hash for detecting duplicates
    suppressed BOOLEAN DEFAULT FALSE,   -- Rate-limited/suppressed duplicate

    -- Metadata
    environment VARCHAR,                -- 'demo', 'prod'
    tags JSONB,                         -- Flexible tagging

    -- Constraints
    CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    CHECK (resolution_action IS NULL OR resolution_action IN ('fixed', 'false_positive', 'ignored', 'escalated'))
);

-- ==============================================================================
-- INDEXES
-- ==============================================================================

-- Query by alert type
CREATE INDEX idx_alerts_type ON alerts(alert_type);

-- Query by severity (most common filter)
CREATE INDEX idx_alerts_severity ON alerts(severity);

-- Query by component
CREATE INDEX idx_alerts_component ON alerts(component);

-- Query by triggered time (for time-based analysis)
CREATE INDEX idx_alerts_triggered ON alerts(triggered_at DESC);

-- Query unresolved alerts (critical for dashboard)
CREATE INDEX idx_alerts_unresolved ON alerts(resolved_at) WHERE resolved_at IS NULL;

-- Query by fingerprint (for deduplication)
CREATE INDEX idx_alerts_fingerprint ON alerts(fingerprint) WHERE fingerprint IS NOT NULL;

-- Query by environment (separate demo from prod)
CREATE INDEX idx_alerts_environment ON alerts(environment);

-- ==============================================================================
-- COMMENTS
-- ==============================================================================

COMMENT ON TABLE alerts IS 'Centralized alert/notification logging with acknowledgement tracking';
COMMENT ON COLUMN alerts.alert_type IS 'Type of alert: circuit_breaker, api_failure, loss_threshold, etc.';
COMMENT ON COLUMN alerts.severity IS 'Severity level for routing: critical (email+SMS), high (email), medium (file), low (file)';
COMMENT ON COLUMN alerts.category IS 'High-level category: risk, system, trading, data';
COMMENT ON COLUMN alerts.component IS 'Which component triggered alert: kalshi_api, edge_detector, position_manager, etc.';
COMMENT ON COLUMN alerts.message IS 'Human-readable alert message';
COMMENT ON COLUMN alerts.details IS 'JSONB context: stack traces, metrics, configuration values';
COMMENT ON COLUMN alerts.source_table IS 'Originating table if alert links to specific record';
COMMENT ON COLUMN alerts.source_id IS 'ID of record in source_table';
COMMENT ON COLUMN alerts.fingerprint IS 'MD5 hash of (alert_type + component + key details) for deduplication';
COMMENT ON COLUMN alerts.suppressed IS 'True if alert was suppressed due to rate limiting or deduplication';
COMMENT ON COLUMN alerts.notification_channels IS 'JSONB tracking which channels were notified: {email: true, sms: false, slack: false}';
COMMENT ON COLUMN alerts.notification_errors IS 'JSONB tracking notification delivery failures';
COMMENT ON COLUMN alerts.resolution_action IS 'How alert was resolved: fixed, false_positive, ignored, escalated';

-- ==============================================================================
-- EXAMPLE DATA
-- ==============================================================================

-- Example 1: Circuit breaker alert (critical)
-- INSERT INTO alerts (
--     alert_type, severity, category, component, message, details,
--     notification_channels, fingerprint, environment
-- ) VALUES (
--     'circuit_breaker', 'critical', 'risk', 'position_manager',
--     'Daily loss limit exceeded: $525.00 / $500.00 limit',
--     '{"current_loss": 525.00, "limit": 500.00, "breaker_type": "daily_loss_limit"}',
--     '{"email": true, "sms": true, "console": true, "file": true}',
--     md5('circuit_breaker:position_manager:daily_loss_limit'),
--     'demo'
-- );

-- Example 2: API failure alert (high)
-- INSERT INTO alerts (
--     alert_type, severity, category, component, message, details,
--     notification_channels, fingerprint, environment
-- ) VALUES (
--     'api_failure', 'high', 'system', 'kalshi_api',
--     'API request failed 5 times in 5 minutes',
--     '{"failure_count": 5, "window_minutes": 5, "last_error": "Connection timeout"}',
--     '{"email": true, "console": true, "file": true}',
--     md5('api_failure:kalshi_api:5_failures'),
--     'prod'
-- );

-- Example 3: Model degradation alert (medium)
-- INSERT INTO alerts (
--     alert_type, severity, category, component, message, details,
--     notification_channels, fingerprint, environment
-- ) VALUES (
--     'model_degradation', 'medium', 'trading', 'edge_detector',
--     'Model accuracy dropped below 85% threshold',
--     '{"model_id": 1, "current_accuracy": 0.78, "threshold": 0.85, "sample_size": 100}',
--     '{"console": true, "file": true}',
--     md5('model_degradation:edge_detector:model_1'),
--     'prod'
-- );

-- ==============================================================================
-- VERIFICATION QUERIES
-- ==============================================================================

-- Verify table created
-- SELECT table_name, column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'alerts'
-- ORDER BY ordinal_position;

-- Verify indexes created
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename = 'alerts';

-- Get unresolved critical alerts
-- SELECT alert_id, alert_type, component, message, triggered_at
-- FROM alerts
-- WHERE severity = 'critical'
--   AND resolved_at IS NULL
-- ORDER BY triggered_at DESC;

-- Get alert summary by severity
-- SELECT severity, COUNT(*) as count
-- FROM alerts
-- WHERE triggered_at > NOW() - INTERVAL '24 hours'
-- GROUP BY severity
-- ORDER BY CASE severity
--     WHEN 'critical' THEN 1
--     WHEN 'high' THEN 2
--     WHEN 'medium' THEN 3
--     WHEN 'low' THEN 4
-- END;

-- ==============================================================================
-- ROLLBACK SCRIPT
-- ==============================================================================

-- To rollback this migration:
-- DROP TABLE IF EXISTS alerts CASCADE;
