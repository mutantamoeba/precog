#!/usr/bin/env python3
"""
Migration 026: Create Venues Table

**Purpose:**
Create normalized venues table for ESPN venue/stadium data. Prevents data
duplication across ~9,500 games/year that reference only ~150 unique venues.

**Schema:**
- venue_id: SERIAL PRIMARY KEY (surrogate key)
- espn_venue_id: VARCHAR(50) UNIQUE NOT NULL (ESPN's stable external ID)
- venue_name: VARCHAR(255) NOT NULL (e.g., "GEHA Field at Arrowhead Stadium")
- city: VARCHAR(100) (nullable - some venues may not have city data)
- state: VARCHAR(50) (nullable - international venues)
- capacity: INTEGER (nullable - capacity data not always available)
- indoor: BOOLEAN DEFAULT FALSE (important for weather-dependent analysis)
- created_at: TIMESTAMP WITH TIME ZONE (audit trail)
- updated_at: TIMESTAMP WITH TIME ZONE (tracks naming rights changes)

**Indexes:**
- idx_venues_espn_id: Fast ESPN ID lookups during data ingestion
- idx_venues_name: Text search on venue names
- idx_venues_state: Partial index for state-based queries
- idx_venues_indoor: Boolean index for weather analysis

**Constraints:**
- venues_capacity_check: capacity must be positive or NULL
- venues_espn_id_format_check: ESPN ID must be alphanumeric with dashes/underscores

**Design Decision (No SCD Type 2):**
Venues are mutable entities - when naming rights change (e.g., "Arrowhead Stadium"
-> "GEHA Field at Arrowhead Stadium"), we UPDATE in place. No historical versioning
needed because venue history doesn't affect trading decisions.

**References:**
- REQ-DATA-002: Venue Data Management
- ADR-029: ESPN Data Model with Normalized Schema
- docs/database/DATABASE_SCHEMA_SUMMARY_V1.13.md (planned)

**Migration Safe:** YES
- New table creation, no existing data affected
- Rollback script included

**Estimated Time:** <1 second

Created: 2025-11-29
Phase: 2 (Live Data Integration)
"""

import os

import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def apply_migration(connection_string: str | None = None) -> None:
    """
    Apply migration: Create venues table.

    Args:
        connection_string: PostgreSQL connection string (defaults to env vars)
    """
    if connection_string:
        conn = psycopg2.connect(connection_string)
    else:
        # Build connection from individual env vars
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        database = os.getenv("DB_NAME", "precog_dev")
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD")

        if not password:
            raise ValueError("DB_PASSWORD environment variable not set")

        conn = psycopg2.connect(
            host=host, port=port, database=database, user=user, password=password
        )
    conn.autocommit = False  # Use transaction

    try:
        with conn.cursor() as cur:
            print("Starting Migration 026: Create Venues Table")
            print("=" * 70)

            # =================================================================
            # Step 1: Create venues table
            # =================================================================
            print("[1/4] Creating venues table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS venues (
                    venue_id SERIAL PRIMARY KEY,
                    espn_venue_id VARCHAR(50) UNIQUE NOT NULL,
                    venue_name VARCHAR(255) NOT NULL,
                    city VARCHAR(100),
                    state VARCHAR(50),
                    capacity INTEGER,
                    indoor BOOLEAN DEFAULT FALSE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
                );
            """)
            print("    [OK] venues table created")

            # =================================================================
            # Step 2: Create indexes
            # =================================================================
            print("[2/4] Creating indexes...")

            # ESPN ID lookup index
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_venues_espn_id
                ON venues(espn_venue_id);
            """)
            print("    [OK] idx_venues_espn_id created")

            # Venue name index for text search
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_venues_name
                ON venues(venue_name);
            """)
            print("    [OK] idx_venues_name created")

            # Partial index for state-based queries (exclude NULLs)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_venues_state
                ON venues(state)
                WHERE state IS NOT NULL;
            """)
            print("    [OK] idx_venues_state (partial) created")

            # Indoor flag index for weather analysis
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_venues_indoor
                ON venues(indoor);
            """)
            print("    [OK] idx_venues_indoor created")

            # =================================================================
            # Step 3: Add CHECK constraints
            # =================================================================
            print("[3/4] Adding CHECK constraints...")

            # Capacity must be positive or NULL
            cur.execute("""
                ALTER TABLE venues
                ADD CONSTRAINT venues_capacity_check
                CHECK (capacity IS NULL OR capacity > 0);
            """)
            print("    [OK] venues_capacity_check constraint added")

            # ESPN ID format validation (alphanumeric with dashes/underscores)
            cur.execute("""
                ALTER TABLE venues
                ADD CONSTRAINT venues_espn_id_format_check
                CHECK (espn_venue_id ~ '^[0-9A-Za-z_-]+$');
            """)
            print("    [OK] venues_espn_id_format_check constraint added")

            # =================================================================
            # Step 4: Add trigger for updated_at
            # =================================================================
            print("[4/4] Creating updated_at trigger...")

            # Create trigger function if not exists
            cur.execute("""
                CREATE OR REPLACE FUNCTION update_venues_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """)

            # Create trigger
            cur.execute("""
                DROP TRIGGER IF EXISTS trigger_venues_updated_at ON venues;
                CREATE TRIGGER trigger_venues_updated_at
                    BEFORE UPDATE ON venues
                    FOR EACH ROW
                    EXECUTE FUNCTION update_venues_updated_at();
            """)
            print("    [OK] updated_at trigger created")

            # =================================================================
            # Commit transaction
            # =================================================================
            conn.commit()
            print("=" * 70)
            print("[OK] Migration 026 completed successfully!")
            print("    - Table: venues")
            print("    - Indexes: 4 (espn_id, name, state, indoor)")
            print("    - Constraints: 2 (capacity_check, espn_id_format)")
            print("    - Trigger: updated_at auto-update")

    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Migration 026 failed: {e}")
        raise

    finally:
        conn.close()


def rollback_migration(connection_string: str | None = None) -> None:
    """
    Rollback migration: Drop venues table and related objects.

    Args:
        connection_string: PostgreSQL connection string (defaults to env vars)
    """
    if connection_string:
        conn = psycopg2.connect(connection_string)
    else:
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        database = os.getenv("DB_NAME", "precog_dev")
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD")

        if not password:
            raise ValueError("DB_PASSWORD environment variable not set")

        conn = psycopg2.connect(
            host=host, port=port, database=database, user=user, password=password
        )
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            print("Rolling back Migration 026: Drop Venues Table")
            print("=" * 70)

            # Drop table (cascades to indexes, constraints, triggers)
            cur.execute("DROP TABLE IF EXISTS venues CASCADE;")
            print("    [OK] venues table dropped")

            # Drop trigger function
            cur.execute("DROP FUNCTION IF EXISTS update_venues_updated_at() CASCADE;")
            print("    [OK] update_venues_updated_at function dropped")

            conn.commit()
            print("=" * 70)
            print("[OK] Migration 026 rollback completed!")

    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Rollback failed: {e}")
        raise

    finally:
        conn.close()


def verify_migration(connection_string: str | None = None) -> bool:
    """
    Verify migration was applied correctly.

    Returns:
        True if verification passes, False otherwise
    """
    if connection_string:
        conn = psycopg2.connect(connection_string)
    else:
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        database = os.getenv("DB_NAME", "precog_dev")
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD")

        if not password:
            raise ValueError("DB_PASSWORD environment variable not set")

        conn = psycopg2.connect(
            host=host, port=port, database=database, user=user, password=password
        )

    try:
        with conn.cursor() as cur:
            print("Verifying Migration 026...")

            # Check table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'venues'
                );
            """)
            table_exists = cur.fetchone()[0]

            # Check columns
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'venues'
                ORDER BY ordinal_position;
            """)
            columns = [row[0] for row in cur.fetchall()]
            expected_columns = [
                "venue_id",
                "espn_venue_id",
                "venue_name",
                "city",
                "state",
                "capacity",
                "indoor",
                "created_at",
                "updated_at",
            ]

            # Check indexes
            cur.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'venues';
            """)
            indexes = [row[0] for row in cur.fetchall()]

            # Results
            print(f"    Table exists: {table_exists}")
            print(f"    Columns: {columns}")
            print(f"    Indexes: {indexes}")

            success = (
                table_exists
                and all(col in columns for col in expected_columns)
                and len(indexes) >= 4  # Primary key + 4 custom indexes
            )

            if success:
                print("[OK] Migration 026 verification passed!")
            else:
                print("[FAIL] Migration 026 verification failed!")

            return success

    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        rollback_migration()
    elif len(sys.argv) > 1 and sys.argv[1] == "--verify":
        verify_migration()
    else:
        apply_migration()
