-- Migration 011: Create Venues Table
-- Date: 2025-11-27
-- Phase: 2 (Live Data Integration)
-- Purpose: Create normalized venues table for stadium/arena data from ESPN API
-- Related: ADR-029 (ESPN Data Model), REQ-DATA-002 (Venue Data Management)

-- ============================================================================
-- BACKGROUND: Venue Normalization
-- ============================================================================
-- Decision: Normalize venue data into dedicated table with ESPN ID linkage
-- Rationale:
--   - Venues are referenced by multiple games but have static metadata
--   - Normalizing prevents data duplication (~9,500 games/year reference ~150 venues)
--   - ESPN venue IDs provide reliable external reference for data reconciliation
--   - Indoor/outdoor and capacity affect game predictions (weather, home advantage)
--
-- See: docs/utility/ESPN_DATA_MODEL_IMPLEMENTATION_PLAN_V1.0.md

-- ============================================================================
-- STEP 1: Create venues Table
-- ============================================================================

CREATE TABLE venues (
    venue_id SERIAL PRIMARY KEY,
    espn_venue_id VARCHAR(50) UNIQUE NOT NULL,  -- ESPN's venue identifier
    venue_name VARCHAR(255) NOT NULL,           -- 'GEHA Field at Arrowhead Stadium'
    city VARCHAR(100),                          -- 'Kansas City'
    state VARCHAR(50),                          -- 'Missouri' or 'MO'
    capacity INTEGER,                           -- 76416
    indoor BOOLEAN DEFAULT FALSE,               -- TRUE for domes/arenas

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()

    -- ❌ NO row_current_ind - venues are mutable entities (capacity can change)
    -- Updates tracked via updated_at timestamp
);

-- ============================================================================
-- STEP 2: Create Indexes
-- ============================================================================

-- Primary lookup by ESPN ID (most common access pattern)
CREATE INDEX idx_venues_espn_id ON venues(espn_venue_id);

-- Name search for admin queries
CREATE INDEX idx_venues_name ON venues(venue_name);

-- Geographic filtering (e.g., find all venues in Texas)
CREATE INDEX idx_venues_state ON venues(state) WHERE state IS NOT NULL;

-- Indoor filter for weather-dependent analysis
CREATE INDEX idx_venues_indoor ON venues(indoor);

-- ============================================================================
-- STEP 3: Add Comments
-- ============================================================================

COMMENT ON TABLE venues IS 'Normalized venue/stadium data from ESPN API (REQ-DATA-002)';
COMMENT ON COLUMN venues.espn_venue_id IS 'ESPN unique venue identifier (e.g., "3622" for Arrowhead)';
COMMENT ON COLUMN venues.venue_name IS 'Full venue name including naming rights (e.g., "GEHA Field at Arrowhead Stadium")';
COMMENT ON COLUMN venues.city IS 'City where venue is located';
COMMENT ON COLUMN venues.state IS 'State/province abbreviation or full name';
COMMENT ON COLUMN venues.capacity IS 'Maximum seating capacity';
COMMENT ON COLUMN venues.indoor IS 'TRUE for domed stadiums/indoor arenas, FALSE for outdoor venues';

-- ============================================================================
-- STEP 4: Add CHECK Constraints
-- ============================================================================

-- Capacity must be positive if specified
ALTER TABLE venues
ADD CONSTRAINT venues_capacity_check
CHECK (capacity IS NULL OR capacity > 0);

-- ESPN venue ID format (typically numeric string)
ALTER TABLE venues
ADD CONSTRAINT venues_espn_id_format_check
CHECK (espn_venue_id ~ '^[0-9A-Za-z_-]+$');

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    table_exists BOOLEAN;
    column_count INT;
    index_count INT;
BEGIN
    -- Check table exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'venues'
    ) INTO table_exists;

    IF NOT table_exists THEN
        RAISE EXCEPTION 'Migration 011 failed: venues table not created';
    END IF;

    -- Check column count
    SELECT COUNT(*) INTO column_count
    FROM information_schema.columns
    WHERE table_name = 'venues'
    AND column_name IN ('venue_id', 'espn_venue_id', 'venue_name', 'city',
                        'state', 'capacity', 'indoor', 'created_at', 'updated_at');

    IF column_count < 9 THEN
        RAISE EXCEPTION 'Migration 011 failed: venues table missing columns (found %, expected 9)', column_count;
    END IF;

    -- Check indexes exist
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE tablename = 'venues'
    AND indexname IN ('idx_venues_espn_id', 'idx_venues_name', 'idx_venues_state', 'idx_venues_indoor');

    IF index_count < 4 THEN
        RAISE EXCEPTION 'Migration 011 failed: venues table missing indexes (found %, expected 4)', index_count;
    END IF;

    RAISE NOTICE 'Migration 011 successful: Created venues table with indexes and constraints';
END $$;

-- ============================================================================
-- USAGE NOTES
-- ============================================================================
--
-- Example: Insert venue from ESPN API
-- INSERT INTO venues (espn_venue_id, venue_name, city, state, capacity, indoor)
-- VALUES ('3622', 'GEHA Field at Arrowhead Stadium', 'Kansas City', 'Missouri', 76416, FALSE);
--
-- Example: Get venue for game state
-- SELECT v.* FROM venues v
-- JOIN game_states gs ON gs.venue_id = v.venue_id
-- WHERE gs.espn_event_id = '401547417';
--
-- Example: Find all indoor venues (for weather-independent games)
-- SELECT venue_name, city, state, capacity FROM venues WHERE indoor = TRUE;
--
