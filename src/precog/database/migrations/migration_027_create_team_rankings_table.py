#!/usr/bin/env python3
"""
Migration 027: Create Team Rankings Table

**Purpose:**
Create team_rankings table for AP Poll, CFP, Coaches Poll, ESPN Power Index,
and ESPN FPI rankings. Tracks temporal validity (rankings change weekly).

**Schema:**
- ranking_id: SERIAL PRIMARY KEY (surrogate key)
- team_id: INTEGER REFERENCES teams(team_id) (FK to teams table)
- ranking_type: VARCHAR(50) NOT NULL (ap_poll, cfp, coaches_poll, espn_power, espn_fpi)
- rank: INTEGER NOT NULL (1-25 for polls, 1-130+ for power rankings)
- season: INTEGER NOT NULL (e.g., 2024)
- week: INTEGER (NULL for preseason/final, 1-18 for in-season)
- ranking_date: DATE NOT NULL (date ranking was published)
- points: INTEGER (AP/Coaches poll voting points)
- first_place_votes: INTEGER (number of #1 votes)
- previous_rank: INTEGER (last week's rank, for trend analysis)
- created_at: TIMESTAMP WITH TIME ZONE (audit trail)

**Indexes:**
- idx_rankings_type_season_week: Composite for "get week N rankings"
- idx_rankings_team: Team-based queries
- idx_rankings_date: Date-based queries
- idx_rankings_rank: Rank-based queries (top 10, etc.)

**Unique Constraint:**
- team_rankings_unique: (team_id, ranking_type, season, week)
  Ensures one ranking per team per type per week

**Use Cases:**
- College football rankings affect line movement
- "Ranked vs. ranked" matchups have different market dynamics
- CFP rankings directly impact bowl game markets
- Trend analysis (rising/falling teams)

**References:**
- REQ-DATA-004: Team Rankings Data
- ADR-029: ESPN Data Model with Normalized Schema

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
    Apply migration: Create team_rankings table.

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
            print("Starting Migration 027: Create Team Rankings Table")
            print("=" * 70)

            # =================================================================
            # Step 1: Create team_rankings table
            # =================================================================
            print("[1/3] Creating team_rankings table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS team_rankings (
                    ranking_id SERIAL PRIMARY KEY,
                    team_id INTEGER NOT NULL REFERENCES teams(team_id),
                    ranking_type VARCHAR(50) NOT NULL,
                    rank INTEGER NOT NULL,
                    season INTEGER NOT NULL,
                    week INTEGER,
                    ranking_date DATE NOT NULL,
                    points INTEGER,
                    first_place_votes INTEGER,
                    previous_rank INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

                    CONSTRAINT team_rankings_unique
                        UNIQUE (team_id, ranking_type, season, week)
                );
            """)
            print("    [OK] team_rankings table created")

            # =================================================================
            # Step 2: Create indexes
            # =================================================================
            print("[2/3] Creating indexes...")

            # Composite index for week N rankings queries
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_rankings_type_season_week
                ON team_rankings(ranking_type, season, week);
            """)
            print("    [OK] idx_rankings_type_season_week created")

            # Team-based queries
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_rankings_team
                ON team_rankings(team_id);
            """)
            print("    [OK] idx_rankings_team created")

            # Date-based queries
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_rankings_date
                ON team_rankings(ranking_date);
            """)
            print("    [OK] idx_rankings_date created")

            # Rank-based queries (top 10, etc.)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_rankings_rank
                ON team_rankings(rank)
                WHERE rank <= 25;
            """)
            print("    [OK] idx_rankings_rank (partial) created")

            # =================================================================
            # Step 3: Add CHECK constraints
            # =================================================================
            print("[3/3] Adding CHECK constraints...")

            # Valid ranking types
            cur.execute("""
                ALTER TABLE team_rankings
                ADD CONSTRAINT team_rankings_type_check
                CHECK (ranking_type IN (
                    'ap_poll',
                    'cfp',
                    'coaches_poll',
                    'espn_power',
                    'espn_fpi',
                    'committee'
                ));
            """)
            print("    [OK] team_rankings_type_check constraint added")

            # Rank must be positive
            cur.execute("""
                ALTER TABLE team_rankings
                ADD CONSTRAINT team_rankings_rank_check
                CHECK (rank >= 1);
            """)
            print("    [OK] team_rankings_rank_check constraint added")

            # Season must be reasonable (1900-2100)
            cur.execute("""
                ALTER TABLE team_rankings
                ADD CONSTRAINT team_rankings_season_check
                CHECK (season >= 1900 AND season <= 2100);
            """)
            print("    [OK] team_rankings_season_check constraint added")

            # Week must be NULL (preseason/final) or valid week number
            cur.execute("""
                ALTER TABLE team_rankings
                ADD CONSTRAINT team_rankings_week_check
                CHECK (week IS NULL OR (week >= 0 AND week <= 20));
            """)
            print("    [OK] team_rankings_week_check constraint added")

            # Points must be non-negative if provided
            cur.execute("""
                ALTER TABLE team_rankings
                ADD CONSTRAINT team_rankings_points_check
                CHECK (points IS NULL OR points >= 0);
            """)
            print("    [OK] team_rankings_points_check constraint added")

            # First place votes must be non-negative if provided
            cur.execute("""
                ALTER TABLE team_rankings
                ADD CONSTRAINT team_rankings_fpv_check
                CHECK (first_place_votes IS NULL OR first_place_votes >= 0);
            """)
            print("    [OK] team_rankings_fpv_check constraint added")

            # =================================================================
            # Commit transaction
            # =================================================================
            conn.commit()
            print("=" * 70)
            print("[OK] Migration 027 completed successfully!")
            print("    - Table: team_rankings")
            print("    - Indexes: 4 (type_season_week, team, date, rank)")
            print("    - Constraints: 7 (unique, type, rank, season, week, points, fpv)")
            print("    - FK: team_id -> teams(team_id)")

    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Migration 027 failed: {e}")
        raise

    finally:
        conn.close()


def rollback_migration(connection_string: str | None = None) -> None:
    """
    Rollback migration: Drop team_rankings table.

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
            print("Rolling back Migration 027: Drop Team Rankings Table")
            print("=" * 70)

            # Drop table (cascades to indexes, constraints)
            cur.execute("DROP TABLE IF EXISTS team_rankings CASCADE;")
            print("    [OK] team_rankings table dropped")

            conn.commit()
            print("=" * 70)
            print("[OK] Migration 027 rollback completed!")

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
            print("Verifying Migration 027...")

            # Check table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'team_rankings'
                );
            """)
            table_exists = cur.fetchone()[0]

            # Check columns
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'team_rankings'
                ORDER BY ordinal_position;
            """)
            columns = [row[0] for row in cur.fetchall()]
            expected_columns = [
                "ranking_id",
                "team_id",
                "ranking_type",
                "rank",
                "season",
                "week",
                "ranking_date",
                "points",
                "first_place_votes",
                "previous_rank",
                "created_at",
            ]

            # Check indexes
            cur.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'team_rankings';
            """)
            indexes = [row[0] for row in cur.fetchall()]

            # Check foreign key
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.table_constraints
                WHERE table_name = 'team_rankings'
                AND constraint_type = 'FOREIGN KEY';
            """)
            fk_count = cur.fetchone()[0]

            # Results
            print(f"    Table exists: {table_exists}")
            print(f"    Columns: {columns}")
            print(f"    Indexes: {indexes}")
            print(f"    Foreign keys: {fk_count}")

            success: bool = (
                table_exists
                and all(col in columns for col in expected_columns)
                and len(indexes) >= 4
                and fk_count >= 1
            )

            if success:
                print("[OK] Migration 027 verification passed!")
            else:
                print("[FAIL] Migration 027 verification failed!")

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
