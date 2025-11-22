#!/usr/bin/env python3
"""
Migration 022: Rename probability_models.approach -> probability_models.model_class

**Rationale:**
- Terminology clarity: "approach" is ambiguous (used in both strategies and probability_models)
- Domain-specific naming: model_class describes HOW the model calculates probabilities
- Prevents confusion: strategy_type (trading style) vs model_class (calculation methodology)

**Schema Change:**
- Column rename: probability_models.approach -> probability_models.model_class
- CHECK constraint rename: probability_models_approach_check -> probability_models_model_class_check
- Index rename (if exists): idx_probability_models_approach -> idx_probability_models_model_class

**Valid model_class values:**
- 'elo': Elo rating system
- 'ensemble': Ensemble of multiple models
- 'regression': Regression-based models
- 'neural_net': Neural network models
- 'power_ranking': Power ranking systems
- 'market_odds': Market consensus probabilities

**Migration Type:** Schema refactoring (non-breaking if done atomically)

**Related Migrations:**
- Migration 009: Created probability_models table
- Migration 013: Added approach column to probability_models
- Migration 021: Renames strategies.approach -> strategy_type

**Reference:**
- Pattern 16: Schema-Code Alignment (avoid backward compatibility tech debt)
- User request 2025-11-21: "rename approach to domain-specific terms"

Created: 2025-11-21
Author: Claude Code
"""

import os

import psycopg2


def apply_migration(connection_string: str | None = None) -> None:
    """
    Apply migration: Rename probability_models.approach -> probability_models.model_class

    Args:
        connection_string: PostgreSQL connection string (defaults to DATABASE_URL env var)
    """
    conn_str = connection_string or os.getenv("DATABASE_URL")
    if not conn_str:
        raise ValueError("DATABASE_URL environment variable not set")

    conn = psycopg2.connect(conn_str)
    conn.autocommit = False  # Use transaction

    try:
        with conn.cursor() as cur:
            print("Starting Migration 022: Rename probability_models.approach -> model_class")

            # Step 1: Rename column
            print("  [1/3] Renaming column probability_models.approach -> model_class...")
            cur.execute("""
                ALTER TABLE probability_models
                RENAME COLUMN approach TO model_class
            """)

            # Step 2: Rename CHECK constraint
            print("  [2/3] Renaming CHECK constraint...")
            cur.execute("""
                ALTER TABLE probability_models
                RENAME CONSTRAINT probability_models_approach_check TO probability_models_model_class_check
            """)

            # Step 3: Rename index (if exists)
            print("  [3/3] Renaming index (if exists)...")
            # Check if index exists
            cur.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'probability_models'
                  AND indexname = 'idx_probability_models_approach'
            """)
            if cur.fetchone():
                cur.execute("""
                    ALTER INDEX idx_probability_models_approach
                    RENAME TO idx_probability_models_model_class
                """)
                print("      [OK] Index renamed")
            else:
                print("      - No index to rename (idx_probability_models_approach not found)")

            # Commit transaction
            conn.commit()
            print("[OK] Migration 022 applied successfully")

            # Verification
            print("\nVerification:")
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'probability_models'
                  AND column_name IN ('model_class', 'approach')
                ORDER BY column_name
            """)
            columns = cur.fetchall()
            for col_name, col_type in columns:
                print(f"  - {col_name}: {col_type}")

            if not any(col[0] == "model_class" for col in columns):
                raise ValueError("VERIFICATION FAILED: model_class column not found!")
            if any(col[0] == "approach" for col in columns):
                raise ValueError("VERIFICATION FAILED: approach column still exists!")

            print("  [OK] Verification passed")

    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Migration 022 failed: {e}")
        raise
    finally:
        conn.close()


def rollback_migration(connection_string: str | None = None) -> None:
    """
    Rollback migration: Rename probability_models.model_class -> probability_models.approach

    Args:
        connection_string: PostgreSQL connection string
    """
    conn_str = connection_string or os.getenv("DATABASE_URL")
    if not conn_str:
        raise ValueError("DATABASE_URL environment variable not set")

    conn = psycopg2.connect(conn_str)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            print("Rolling back Migration 022: Rename model_class -> approach")

            cur.execute("ALTER TABLE probability_models RENAME COLUMN model_class TO approach")
            cur.execute(
                "ALTER TABLE probability_models RENAME CONSTRAINT probability_models_model_class_check TO probability_models_approach_check"
            )

            # Rename index if exists
            cur.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'probability_models'
                  AND indexname = 'idx_probability_models_model_class'
            """)
            if cur.fetchone():
                cur.execute(
                    "ALTER INDEX idx_probability_models_model_class RENAME TO idx_probability_models_approach"
                )

            conn.commit()
            print("[OK] Migration 022 rolled back successfully")

    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Rollback failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        rollback_migration()
    else:
        apply_migration()
