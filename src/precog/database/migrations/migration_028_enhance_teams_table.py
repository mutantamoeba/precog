#!/usr/bin/env python3
"""
Migration 028: Enhance Teams Table with ESPN IDs and Multi-Sport Support

**Purpose:**
Add ESPN integration fields and multi-sport support to existing teams table.
Enables cross-referencing with ESPN API data and supporting 6 leagues.

**Schema Changes (ALTER TABLE teams):**
- espn_team_id: VARCHAR(50) - ESPN's unique team identifier
- display_name: VARCHAR(100) - Short display name (e.g., "Chiefs" vs "Kansas City Chiefs")
- conference: VARCHAR(100) - Conference affiliation (AFC, NFC, Big Ten, SEC, etc.)
- division: VARCHAR(100) - Division within conference (AFC West, etc.)
- sport: VARCHAR(20) DEFAULT 'nfl' - Sport category (football, basketball, hockey)
- league: VARCHAR(20) DEFAULT 'nfl' - Specific league (nfl, ncaaf, nba, ncaab, nhl, wnba)

**Indexes:**
- idx_teams_espn_id: UNIQUE index on espn_team_id for ESPN API lookups
- idx_teams_league: Filter by league for multi-sport queries
- idx_teams_conference: Conference-based queries

**Supported Leagues:**
- NFL (32 teams) - Already seeded
- NCAAF (130+ teams) - Partially seeded
- NBA (30 teams) - To be seeded
- NCAAB (350+ Division I teams) - Top 100+ to be seeded
- NHL (32 teams) - To be seeded
- WNBA (12 teams) - To be seeded

**Backfill Strategy:**
- Existing teams get league/sport based on current data
- ESPN IDs populated via ESPN API team lookup endpoint
- Conference/division populated from ESPN team metadata

**References:**
- REQ-DATA-003: Multi-Sport Support
- ADR-029: ESPN Data Model with Normalized Schema

**Migration Safe:** YES
- All new columns are nullable or have defaults
- Existing data preserved
- Rollback script included

**Estimated Time:** <1 second (column additions only)

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
    Apply migration: Enhance teams table with ESPN integration fields.

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
            print("Starting Migration 028: Enhance Teams Table")
            print("=" * 70)

            # =================================================================
            # Step 1: Add new columns
            # =================================================================
            print("[1/4] Adding new columns to teams table...")

            # ESPN team ID
            cur.execute("""
                ALTER TABLE teams
                ADD COLUMN IF NOT EXISTS espn_team_id VARCHAR(50);
            """)
            print("    [OK] espn_team_id column added")

            # Display name (short form)
            cur.execute("""
                ALTER TABLE teams
                ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);
            """)
            print("    [OK] display_name column added")

            # Conference
            cur.execute("""
                ALTER TABLE teams
                ADD COLUMN IF NOT EXISTS conference VARCHAR(100);
            """)
            print("    [OK] conference column added")

            # Division
            cur.execute("""
                ALTER TABLE teams
                ADD COLUMN IF NOT EXISTS division VARCHAR(100);
            """)
            print("    [OK] division column added")

            # Sport category
            cur.execute("""
                ALTER TABLE teams
                ADD COLUMN IF NOT EXISTS sport VARCHAR(20) DEFAULT 'football';
            """)
            print("    [OK] sport column added")

            # League
            cur.execute("""
                ALTER TABLE teams
                ADD COLUMN IF NOT EXISTS league VARCHAR(20) DEFAULT 'nfl';
            """)
            print("    [OK] league column added")

            # =================================================================
            # Step 2: Create indexes
            # =================================================================
            print("[2/4] Creating indexes...")

            # Unique ESPN ID index
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_espn_id
                ON teams(espn_team_id)
                WHERE espn_team_id IS NOT NULL;
            """)
            print("    [OK] idx_teams_espn_id (unique, partial) created")

            # League index
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_teams_league
                ON teams(league);
            """)
            print("    [OK] idx_teams_league created")

            # Conference index
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_teams_conference
                ON teams(conference)
                WHERE conference IS NOT NULL;
            """)
            print("    [OK] idx_teams_conference (partial) created")

            # Sport index
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_teams_sport
                ON teams(sport);
            """)
            print("    [OK] idx_teams_sport created")

            # =================================================================
            # Step 3: Add CHECK constraints
            # =================================================================
            print("[3/4] Adding CHECK constraints...")

            # Valid sport values
            cur.execute("""
                ALTER TABLE teams
                ADD CONSTRAINT teams_sport_check
                CHECK (sport IN ('football', 'basketball', 'hockey'));
            """)
            print("    [OK] teams_sport_check constraint added")

            # Valid league values
            cur.execute("""
                ALTER TABLE teams
                ADD CONSTRAINT teams_league_check
                CHECK (league IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'wnba'));
            """)
            print("    [OK] teams_league_check constraint added")

            # ESPN ID format (alphanumeric)
            cur.execute("""
                ALTER TABLE teams
                ADD CONSTRAINT teams_espn_id_format_check
                CHECK (espn_team_id IS NULL OR espn_team_id ~ '^[0-9A-Za-z_-]+$');
            """)
            print("    [OK] teams_espn_id_format_check constraint added")

            # =================================================================
            # Step 4: Backfill existing teams
            # =================================================================
            print("[4/4] Backfilling existing teams...")

            # Set sport=football, league=nfl for existing NFL teams
            cur.execute("""
                UPDATE teams
                SET sport = 'football', league = 'nfl'
                WHERE sport IS NULL OR league IS NULL;
            """)
            updated_count = cur.rowcount
            print(f"    [OK] Updated {updated_count} teams with default sport/league")

            # =================================================================
            # Commit transaction
            # =================================================================
            conn.commit()
            print("=" * 70)
            print("[OK] Migration 028 completed successfully!")
            print("    - New columns: 6 (espn_team_id, display_name, conference,")
            print("                      division, sport, league)")
            print("    - Indexes: 4 (espn_id, league, conference, sport)")
            print("    - Constraints: 3 (sport, league, espn_id_format)")
            print(f"    - Backfilled: {updated_count} teams")

    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Migration 028 failed: {e}")
        raise

    finally:
        conn.close()


def rollback_migration(connection_string: str | None = None) -> None:
    """
    Rollback migration: Remove added columns and indexes.

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
            print("Rolling back Migration 028: Remove Teams Enhancements")
            print("=" * 70)

            # Drop constraints first
            cur.execute("""
                ALTER TABLE teams DROP CONSTRAINT IF EXISTS teams_sport_check;
            """)
            cur.execute("""
                ALTER TABLE teams DROP CONSTRAINT IF EXISTS teams_league_check;
            """)
            cur.execute("""
                ALTER TABLE teams DROP CONSTRAINT IF EXISTS teams_espn_id_format_check;
            """)
            print("    [OK] Constraints dropped")

            # Drop indexes
            cur.execute("DROP INDEX IF EXISTS idx_teams_espn_id;")
            cur.execute("DROP INDEX IF EXISTS idx_teams_league;")
            cur.execute("DROP INDEX IF EXISTS idx_teams_conference;")
            cur.execute("DROP INDEX IF EXISTS idx_teams_sport;")
            print("    [OK] Indexes dropped")

            # Drop columns
            cur.execute("ALTER TABLE teams DROP COLUMN IF EXISTS espn_team_id;")
            cur.execute("ALTER TABLE teams DROP COLUMN IF EXISTS display_name;")
            cur.execute("ALTER TABLE teams DROP COLUMN IF EXISTS conference;")
            cur.execute("ALTER TABLE teams DROP COLUMN IF EXISTS division;")
            cur.execute("ALTER TABLE teams DROP COLUMN IF EXISTS sport;")
            cur.execute("ALTER TABLE teams DROP COLUMN IF EXISTS league;")
            print("    [OK] Columns dropped")

            conn.commit()
            print("=" * 70)
            print("[OK] Migration 028 rollback completed!")

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
            print("Verifying Migration 028...")

            # Check new columns exist
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'teams'
                AND column_name IN (
                    'espn_team_id', 'display_name', 'conference',
                    'division', 'sport', 'league'
                );
            """)
            new_columns = [row[0] for row in cur.fetchall()]

            # Check indexes
            cur.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'teams'
                AND indexname LIKE 'idx_teams_%';
            """)
            indexes = [row[0] for row in cur.fetchall()]

            # Results
            print(f"    New columns: {new_columns}")
            print(f"    Indexes: {indexes}")

            expected_columns = [
                "espn_team_id",
                "display_name",
                "conference",
                "division",
                "sport",
                "league",
            ]

            success = all(col in new_columns for col in expected_columns) and len(indexes) >= 4

            if success:
                print("[OK] Migration 028 verification passed!")
            else:
                print("[FAIL] Migration 028 verification failed!")

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
