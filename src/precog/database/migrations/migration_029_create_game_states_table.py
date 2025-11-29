#!/usr/bin/env python3
"""
Migration 029: Create Game States Table (SCD Type 2)

**Purpose:**
Create game_states table for live game state tracking with complete history
preservation using SCD Type 2 versioning. Enables historical playback and
backtesting.

**SCD Type 2 Architecture:**
- Each game state change creates a NEW row (not an update)
- row_start_timestamp: When this version became current
- row_end_timestamp: When this version was superseded (NULL if current)
- row_current_ind: TRUE for the current version, FALSE for historical
- Partial unique index ensures only ONE current row per game

**Schema:**
Core Fields:
- id: SERIAL PRIMARY KEY (surrogate key for SCD Type 2)
- game_state_id: VARCHAR(50) (business key - e.g., "GS-12345")
- espn_event_id: VARCHAR(50) NOT NULL (ESPN's game identifier)
- home_team_id: INTEGER REFERENCES teams(team_id)
- away_team_id: INTEGER REFERENCES teams(team_id)
- venue_id: INTEGER REFERENCES venues(venue_id)

Score Fields:
- home_score: INTEGER NOT NULL DEFAULT 0
- away_score: INTEGER NOT NULL DEFAULT 0
- period: INTEGER NOT NULL DEFAULT 0 (quarter, half, period)
- clock_seconds: DECIMAL(10,2) (remaining time in period)
- clock_display: VARCHAR(20) (formatted clock - "12:34")
- game_status: VARCHAR(50) NOT NULL (pre, in_progress, halftime, final, etc.)

Metadata:
- game_date: TIMESTAMP WITH TIME ZONE
- broadcast: VARCHAR(100) (TV network)
- neutral_site: BOOLEAN DEFAULT FALSE
- season_type: VARCHAR(20) (preseason, regular, playoff, bowl)
- week_number: INTEGER
- league: VARCHAR(20) NOT NULL (nfl, ncaaf, nba, ncaab, nhl, wnba)

Sport-Specific JSONB:
- situation: JSONB (downs, fouls, power plays, etc.)
- linescores: JSONB (period-by-period scores)

SCD Type 2:
- row_start_timestamp: TIMESTAMP WITH TIME ZONE DEFAULT NOW()
- row_end_timestamp: TIMESTAMP WITH TIME ZONE (NULL if current)
- row_current_ind: BOOLEAN DEFAULT TRUE

**Indexes:**
- idx_game_states_event: espn_event_id for fast event lookups
- idx_game_states_current: Partial index for current rows
- idx_game_states_current_unique: Ensures one current row per event
- idx_game_states_date: game_date for date-range queries
- idx_game_states_status: game_status for finding live games
- idx_game_states_league: league for multi-sport filtering
- idx_game_states_situation: GIN index on JSONB situation

**Storage Estimate:**
~1.8M rows/year (9,500 games x ~190 updates/game average)
~900 MB/year with indexes

**Use Cases:**
- "What was the score at halftime?" - Historical query
- "Get all current live games" - Current row query
- Backtesting model accuracy on historical game states

**References:**
- REQ-DATA-001: Game State Collection
- ADR-029: ESPN Data Model with Normalized Schema
- Migration 016: SCD Type 2 surrogate key pattern

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
    Apply migration: Create game_states table with SCD Type 2 versioning.

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
            print("Starting Migration 029: Create Game States Table (SCD Type 2)")
            print("=" * 70)

            # =================================================================
            # Step 1: Create game_states table
            # =================================================================
            print("[1/4] Creating game_states table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS game_states (
                    -- Surrogate primary key (SCD Type 2)
                    id SERIAL PRIMARY KEY,

                    -- Business key
                    game_state_id VARCHAR(50) NOT NULL,

                    -- Event identification
                    espn_event_id VARCHAR(50) NOT NULL,

                    -- Team references
                    home_team_id INTEGER REFERENCES teams(team_id),
                    away_team_id INTEGER REFERENCES teams(team_id),

                    -- Venue reference
                    venue_id INTEGER REFERENCES venues(venue_id),

                    -- Score fields
                    home_score INTEGER NOT NULL DEFAULT 0,
                    away_score INTEGER NOT NULL DEFAULT 0,
                    period INTEGER NOT NULL DEFAULT 0,
                    clock_seconds DECIMAL(10,2),
                    clock_display VARCHAR(20),
                    game_status VARCHAR(50) NOT NULL,

                    -- Metadata
                    game_date TIMESTAMP WITH TIME ZONE,
                    broadcast VARCHAR(100),
                    neutral_site BOOLEAN DEFAULT FALSE NOT NULL,
                    season_type VARCHAR(20),
                    week_number INTEGER,
                    league VARCHAR(20) NOT NULL,

                    -- Sport-specific JSONB
                    situation JSONB,
                    linescores JSONB,

                    -- Data source tracking
                    data_source VARCHAR(50) DEFAULT 'espn' NOT NULL,

                    -- SCD Type 2 versioning
                    row_start_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
                    row_end_timestamp TIMESTAMP WITH TIME ZONE,
                    row_current_ind BOOLEAN DEFAULT TRUE NOT NULL
                );
            """)
            print("    [OK] game_states table created")

            # =================================================================
            # Step 2: Create indexes
            # =================================================================
            print("[2/4] Creating indexes...")

            # Event ID lookup
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_game_states_event
                ON game_states(espn_event_id);
            """)
            print("    [OK] idx_game_states_event created")

            # Current rows only (partial index)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_game_states_current
                ON game_states(espn_event_id)
                WHERE row_current_ind = TRUE;
            """)
            print("    [OK] idx_game_states_current (partial) created")

            # Unique constraint on current rows (SCD Type 2 integrity)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_game_states_current_unique
                ON game_states(espn_event_id)
                WHERE row_current_ind = TRUE;
            """)
            print("    [OK] idx_game_states_current_unique (SCD Type 2) created")

            # Date-based queries
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_game_states_date
                ON game_states(game_date);
            """)
            print("    [OK] idx_game_states_date created")

            # Status queries (find live games)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_game_states_status
                ON game_states(game_status)
                WHERE row_current_ind = TRUE;
            """)
            print("    [OK] idx_game_states_status (partial) created")

            # League queries (multi-sport)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_game_states_league
                ON game_states(league)
                WHERE row_current_ind = TRUE;
            """)
            print("    [OK] idx_game_states_league (partial) created")

            # GIN index on situation JSONB
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_game_states_situation
                ON game_states USING GIN (situation);
            """)
            print("    [OK] idx_game_states_situation (GIN) created")

            # Teams lookup
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_game_states_teams
                ON game_states(home_team_id, away_team_id)
                WHERE row_current_ind = TRUE;
            """)
            print("    [OK] idx_game_states_teams (partial) created")

            # Business key index
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_game_states_business_key
                ON game_states(game_state_id);
            """)
            print("    [OK] idx_game_states_business_key created")

            # =================================================================
            # Step 3: Add CHECK constraints
            # =================================================================
            print("[3/4] Adding CHECK constraints...")

            # Valid game status values
            cur.execute("""
                ALTER TABLE game_states
                ADD CONSTRAINT game_states_status_check
                CHECK (game_status IN (
                    'pre',
                    'in_progress',
                    'halftime',
                    'end_of_period',
                    'final',
                    'final_ot',
                    'delayed',
                    'postponed',
                    'cancelled',
                    'suspended'
                ));
            """)
            print("    [OK] game_states_status_check constraint added")

            # Valid season type values
            cur.execute("""
                ALTER TABLE game_states
                ADD CONSTRAINT game_states_season_type_check
                CHECK (season_type IS NULL OR season_type IN (
                    'preseason',
                    'regular',
                    'playoff',
                    'bowl',
                    'allstar',
                    'exhibition'
                ));
            """)
            print("    [OK] game_states_season_type_check constraint added")

            # Valid league values
            cur.execute("""
                ALTER TABLE game_states
                ADD CONSTRAINT game_states_league_check
                CHECK (league IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'wnba'));
            """)
            print("    [OK] game_states_league_check constraint added")

            # Scores must be non-negative
            cur.execute("""
                ALTER TABLE game_states
                ADD CONSTRAINT game_states_scores_check
                CHECK (home_score >= 0 AND away_score >= 0);
            """)
            print("    [OK] game_states_scores_check constraint added")

            # Period must be non-negative
            cur.execute("""
                ALTER TABLE game_states
                ADD CONSTRAINT game_states_period_check
                CHECK (period >= 0);
            """)
            print("    [OK] game_states_period_check constraint added")

            # Clock seconds must be non-negative if present
            cur.execute("""
                ALTER TABLE game_states
                ADD CONSTRAINT game_states_clock_check
                CHECK (clock_seconds IS NULL OR clock_seconds >= 0);
            """)
            print("    [OK] game_states_clock_check constraint added")

            # Week number validation (0-20 for regular season + playoffs)
            cur.execute("""
                ALTER TABLE game_states
                ADD CONSTRAINT game_states_week_check
                CHECK (week_number IS NULL OR (week_number >= 0 AND week_number <= 25));
            """)
            print("    [OK] game_states_week_check constraint added")

            # =================================================================
            # Step 4: Create SCD Type 2 trigger function
            # =================================================================
            print("[4/4] Creating SCD Type 2 trigger function...")

            # Note: The actual SCD Type 2 logic is in the CRUD upsert_game_state()
            # function, not a database trigger. This is intentional because:
            # 1. Python logic is easier to test
            # 2. More flexibility for batch operations
            # 3. Clearer error handling

            # However, we'll create a simple trigger to set row_start_timestamp
            cur.execute("""
                CREATE OR REPLACE FUNCTION set_game_states_timestamp()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF NEW.row_start_timestamp IS NULL THEN
                        NEW.row_start_timestamp = NOW();
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """)

            cur.execute("""
                DROP TRIGGER IF EXISTS trigger_game_states_timestamp ON game_states;
                CREATE TRIGGER trigger_game_states_timestamp
                    BEFORE INSERT ON game_states
                    FOR EACH ROW
                    EXECUTE FUNCTION set_game_states_timestamp();
            """)
            print("    [OK] row_start_timestamp trigger created")

            # =================================================================
            # Commit transaction
            # =================================================================
            conn.commit()
            print("=" * 70)
            print("[OK] Migration 029 completed successfully!")
            print("    - Table: game_states (SCD Type 2)")
            print("    - Indexes: 9 (event, current, current_unique, date, status,")
            print("                  league, situation GIN, teams, business_key)")
            print("    - Constraints: 7 (status, season_type, league, scores,")
            print("                      period, clock, week)")
            print("    - FKs: 3 (home_team, away_team, venue)")
            print("    - Trigger: row_start_timestamp auto-set")

    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Migration 029 failed: {e}")
        raise

    finally:
        conn.close()


def rollback_migration(connection_string: str | None = None) -> None:
    """
    Rollback migration: Drop game_states table and related objects.

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
            print("Rolling back Migration 029: Drop Game States Table")
            print("=" * 70)

            # Drop table (cascades to indexes, constraints, triggers)
            cur.execute("DROP TABLE IF EXISTS game_states CASCADE;")
            print("    [OK] game_states table dropped")

            # Drop trigger function
            cur.execute("DROP FUNCTION IF EXISTS set_game_states_timestamp() CASCADE;")
            print("    [OK] set_game_states_timestamp function dropped")

            conn.commit()
            print("=" * 70)
            print("[OK] Migration 029 rollback completed!")

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
            print("Verifying Migration 029...")

            # Check table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'game_states'
                );
            """)
            table_exists = cur.fetchone()[0]

            # Check SCD Type 2 columns
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'game_states'
                AND column_name IN (
                    'id', 'game_state_id', 'row_start_timestamp',
                    'row_end_timestamp', 'row_current_ind'
                );
            """)
            scd_columns = [row[0] for row in cur.fetchall()]

            # Check unique index for SCD Type 2
            cur.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'game_states'
                AND indexname = 'idx_game_states_current_unique';
            """)
            unique_index = cur.fetchone()

            # Check foreign keys
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.table_constraints
                WHERE table_name = 'game_states'
                AND constraint_type = 'FOREIGN KEY';
            """)
            fk_count = cur.fetchone()[0]

            # Check indexes count
            cur.execute("""
                SELECT COUNT(*) FROM pg_indexes
                WHERE tablename = 'game_states';
            """)
            index_count = cur.fetchone()[0]

            # Results
            print(f"    Table exists: {table_exists}")
            print(f"    SCD Type 2 columns: {scd_columns}")
            print(f"    Unique index exists: {unique_index is not None}")
            print(f"    Foreign keys: {fk_count}")
            print(f"    Total indexes: {index_count}")

            expected_scd_columns = [
                "id",
                "game_state_id",
                "row_start_timestamp",
                "row_end_timestamp",
                "row_current_ind",
            ]

            success: bool = (
                table_exists
                and all(col in scd_columns for col in expected_scd_columns)
                and unique_index is not None
                and fk_count >= 3
                and index_count >= 8
            )

            if success:
                print("[OK] Migration 029 verification passed!")
                print("    SCD Type 2 architecture validated:")
                print("    - Surrogate PK (id)")
                print("    - Business key (game_state_id)")
                print("    - Temporal columns (row_start/end_timestamp)")
                print("    - Current indicator (row_current_ind)")
                print("    - Unique constraint on current rows")
            else:
                print("[FAIL] Migration 029 verification failed!")

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
