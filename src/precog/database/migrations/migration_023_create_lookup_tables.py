#!/usr/bin/env python3
"""
Migration 023: Create Lookup Tables for strategy_type and model_class

**Rationale:**
- Replace CHECK constraints with lookup tables for extensibility
- No migrations needed to add new values (just INSERT)
- Store rich metadata (display_name, description, category)
- UI-friendly (query for dropdowns with metadata)
- Extensible (add fields without schema changes)

**Schema Changes:**
1. CREATE TABLE strategy_types (lookup table for valid strategy types)
2. CREATE TABLE model_classes (lookup table for valid model classes)
3. Seed with existing 4 strategy_type values + 7 model_class values
4. DROP CHECK constraints (strategies_strategy_type_check, probability_models_model_class_check)
5. ADD FOREIGN KEY constraints instead

**Migration Type:** Schema enhancement (non-breaking, atomic transaction)

**Benefits:**
- Add new values via INSERT (no migration): `INSERT INTO strategy_types VALUES ('hedging', ...)`
- Store metadata: description, category, is_active, display_order, help_text
- UI integration: `SELECT * FROM strategy_types WHERE is_active = TRUE ORDER BY display_order`
- Flexible: Add icon_name, tags, risk_level without schema changes

**Related Migrations:**
- Migration 013: Created strategies.approach CHECK constraint (category -> approach)
- Migration 021: Renamed strategies.approach -> strategies.strategy_type
- Migration 022: Renamed probability_models.approach -> probability_models.model_class

**References:**
- docs/database/LOOKUP_TABLES_DESIGN.md - Complete design spec
- ADR-093: Lookup Tables for Business Enums (to be created)
- REQ-DB-015: Strategy Type Lookup Table (to be created)
- REQ-DB-016: Model Class Lookup Table (to be created)

**Migration Safe:** YES
- Lookup tables created with existing values BEFORE dropping CHECK constraints
- FK constraints validate existing data (all current values exist in lookup tables)
- Atomic transaction (all-or-nothing)
- Rollback script included

**Estimated Time:** ~500ms (metadata operations + 11 row inserts)

Created: 2025-11-21
Phase: 1.5 (Foundation Validation)
"""

import os

import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def apply_migration(connection_string: str | None = None) -> None:
    """
    Apply migration: Create lookup tables and replace CHECK constraints with FKs.

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
            print("Starting Migration 023: Create Lookup Tables for strategy_type and model_class")
            print("=" * 80)

            # =================================================================
            # Step 1: Create strategy_types lookup table
            # =================================================================
            print("[1/7] Creating strategy_types lookup table...")
            cur.execute("""
                CREATE TABLE strategy_types (
                    strategy_type_code VARCHAR(50) PRIMARY KEY,
                    display_name VARCHAR(100) NOT NULL,
                    description TEXT NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE NOT NULL,
                    display_order INT DEFAULT 999 NOT NULL,
                    icon_name VARCHAR(50),
                    help_text TEXT,
                    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
                )
            """)
            print("      [OK] strategy_types table created")

            # Create indexes
            cur.execute("""
                CREATE INDEX idx_strategy_types_active
                ON strategy_types(is_active)
                WHERE is_active = TRUE
            """)
            cur.execute("CREATE INDEX idx_strategy_types_category ON strategy_types(category)")
            cur.execute("CREATE INDEX idx_strategy_types_order ON strategy_types(display_order)")
            print("      [OK] Indexes created (active, category, order)")

            # =================================================================
            # Step 2: Create model_classes lookup table
            # =================================================================
            print("[2/7] Creating model_classes lookup table...")
            cur.execute("""
                CREATE TABLE model_classes (
                    model_class_code VARCHAR(50) PRIMARY KEY,
                    display_name VARCHAR(100) NOT NULL,
                    description TEXT NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    complexity_level VARCHAR(20) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE NOT NULL,
                    display_order INT DEFAULT 999 NOT NULL,
                    icon_name VARCHAR(50),
                    help_text TEXT,
                    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
                )
            """)
            print("      [OK] model_classes table created")

            # Create indexes
            cur.execute("""
                CREATE INDEX idx_model_classes_active
                ON model_classes(is_active)
                WHERE is_active = TRUE
            """)
            cur.execute("CREATE INDEX idx_model_classes_category ON model_classes(category)")
            cur.execute(
                "CREATE INDEX idx_model_classes_complexity ON model_classes(complexity_level)"
            )
            cur.execute("CREATE INDEX idx_model_classes_order ON model_classes(display_order)")
            print("      [OK] Indexes created (active, category, complexity, order)")

            # =================================================================
            # Step 3: Seed strategy_types with 4 existing values
            # =================================================================
            print("[3/7] Seeding strategy_types with 4 initial values...")
            cur.execute("""
                INSERT INTO strategy_types (
                    strategy_type_code, display_name, description, category, display_order
                ) VALUES
                ('value', 'Value Trading',
                 'Exploit market mispricing by identifying edges where true probability exceeds market price',
                 'directional', 10),
                ('arbitrage', 'Arbitrage',
                 'Cross-platform arbitrage opportunities with identical event outcomes priced differently',
                 'arbitrage', 20),
                ('momentum', 'Momentum Trading',
                 'Trend following strategies that capitalize on sustained price movements',
                 'directional', 30),
                ('mean_reversion', 'Mean Reversion',
                 'Capitalize on temporary deviations from fundamental value by betting on reversion to mean',
                 'directional', 40)
            """)
            print("      [OK] 4 strategy types seeded (value, arbitrage, momentum, mean_reversion)")

            # =================================================================
            # Step 4: Seed model_classes with 7 existing values
            # =================================================================
            print("[4/7] Seeding model_classes with 7 initial values...")
            cur.execute("""
                INSERT INTO model_classes (
                    model_class_code, display_name, description, category, complexity_level, display_order
                ) VALUES
                ('elo', 'Elo Rating System',
                 'Dynamic rating system tracking team/competitor strength over time based on game outcomes',
                 'statistical', 'simple', 10),
                ('ensemble', 'Ensemble Model',
                 'Weighted combination of multiple models for more robust and accurate predictions',
                 'hybrid', 'moderate', 20),
                ('ml', 'Machine Learning',
                 'General machine learning algorithms (decision trees, random forests, SVM, etc.)',
                 'machine_learning', 'moderate', 30),
                ('hybrid', 'Hybrid Approach',
                 'Combines multiple modeling approaches (statistical + machine learning) for best of both worlds',
                 'hybrid', 'moderate', 40),
                ('regression', 'Statistical Regression',
                 'Linear or logistic regression models with feature engineering and interaction terms',
                 'statistical', 'simple', 50),
                ('neural_net', 'Neural Network',
                 'Deep learning models with multiple hidden layers for complex pattern recognition',
                 'machine_learning', 'advanced', 60),
                ('baseline', 'Baseline Model',
                 'Simple heuristic for benchmarking (moving average, market consensus, random guessing)',
                 'baseline', 'simple', 70)
            """)
            print(
                "      [OK] 7 model classes seeded (elo, ensemble, ml, hybrid, regression, neural_net, baseline)"
            )

            # =================================================================
            # Step 5: Drop CHECK constraints
            # =================================================================
            print("[5/7] Dropping CHECK constraints...")

            # Check if strategies constraint exists
            cur.execute("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'strategies'
                  AND constraint_type = 'CHECK'
                  AND constraint_name = 'strategies_strategy_type_check'
            """)
            if cur.fetchone():
                cur.execute("ALTER TABLE strategies DROP CONSTRAINT strategies_strategy_type_check")
                print("      [OK] Dropped strategies_strategy_type_check constraint")
            else:
                print("      - strategies_strategy_type_check not found (may not exist yet)")

            # Check if probability_models constraint exists
            cur.execute("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'probability_models'
                  AND constraint_type = 'CHECK'
                  AND constraint_name = 'probability_models_model_class_check'
            """)
            if cur.fetchone():
                cur.execute(
                    "ALTER TABLE probability_models DROP CONSTRAINT probability_models_model_class_check"
                )
                print("      [OK] Dropped probability_models_model_class_check constraint")
            else:
                print("      - probability_models_model_class_check not found (may not exist yet)")

            # =================================================================
            # Step 6: Add FOREIGN KEY constraints
            # =================================================================
            print("[6/7] Adding FOREIGN KEY constraints...")

            cur.execute("""
                ALTER TABLE strategies
                ADD CONSTRAINT fk_strategies_strategy_type
                FOREIGN KEY (strategy_type)
                REFERENCES strategy_types(strategy_type_code)
            """)
            print(
                "      [OK] Added FK: strategies.strategy_type -> strategy_types.strategy_type_code"
            )

            cur.execute("""
                ALTER TABLE probability_models
                ADD CONSTRAINT fk_probability_models_model_class
                FOREIGN KEY (model_class)
                REFERENCES model_classes(model_class_code)
            """)
            print(
                "      [OK] Added FK: probability_models.model_class -> model_classes.model_class_code"
            )

            # =================================================================
            # Step 7: Create indexes on FK columns (if not exist)
            # =================================================================
            print("[7/7] Creating indexes on FK columns...")

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_strategies_strategy_type
                ON strategies(strategy_type)
            """)
            print("      [OK] Index created: idx_strategies_strategy_type")

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_probability_models_model_class
                ON probability_models(model_class)
            """)
            print("      [OK] Index created: idx_probability_models_model_class")

            # Commit transaction
            conn.commit()
            print()
            print("=" * 80)
            print("[OK] Migration 023 applied successfully")
            print("=" * 80)

            # Verification
            print()
            print("Verification:")
            cur.execute("SELECT COUNT(*) FROM strategy_types")
            strategy_count = cur.fetchone()[0]
            print(f"  - strategy_types table: {strategy_count} rows")

            cur.execute("SELECT COUNT(*) FROM model_classes")
            model_count = cur.fetchone()[0]
            print(f"  - model_classes table: {model_count} rows")

            if strategy_count != 4:
                raise ValueError(
                    f"VERIFICATION FAILED: Expected 4 strategy_types, got {strategy_count}"
                )
            if model_count != 7:
                raise ValueError(
                    f"VERIFICATION FAILED: Expected 7 model_classes, got {model_count}"
                )

            print("  [OK] Verification passed")

    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Migration 023 failed: {e}")
        raise
    finally:
        conn.close()


def rollback_migration(connection_string: str | None = None) -> None:
    """
    Rollback migration: Drop lookup tables and restore CHECK constraints.

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
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            print("Rolling back Migration 023: Remove lookup tables, restore CHECK constraints")

            # Step 1: Drop foreign key constraints
            print("[1/3] Dropping FOREIGN KEY constraints...")
            cur.execute(
                "ALTER TABLE strategies DROP CONSTRAINT IF EXISTS fk_strategies_strategy_type"
            )
            cur.execute(
                "ALTER TABLE probability_models DROP CONSTRAINT IF EXISTS fk_probability_models_model_class"
            )
            print("      [OK] Foreign key constraints dropped")

            # Step 2: Recreate CHECK constraints
            print("[2/3] Recreating CHECK constraints...")
            cur.execute("""
                ALTER TABLE strategies
                ADD CONSTRAINT strategies_strategy_type_check
                CHECK (strategy_type IN ('value', 'arbitrage', 'momentum', 'mean_reversion'))
            """)
            print("      [OK] strategies_strategy_type_check constraint recreated")

            cur.execute("""
                ALTER TABLE probability_models
                ADD CONSTRAINT probability_models_model_class_check
                CHECK (model_class IN ('elo', 'ensemble', 'ml', 'hybrid', 'regression', 'neural_net', 'baseline'))
            """)
            print("      [OK] probability_models_model_class_check constraint recreated")

            # Step 3: Drop lookup tables
            print("[3/3] Dropping lookup tables...")
            cur.execute("DROP TABLE IF EXISTS strategy_types CASCADE")
            cur.execute("DROP TABLE IF EXISTS model_classes CASCADE")
            print("      [OK] Lookup tables dropped")

            conn.commit()
            print("[OK] Migration 023 rolled back successfully")

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
