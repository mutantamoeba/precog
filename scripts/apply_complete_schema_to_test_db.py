#!/usr/bin/env python3
"""
Apply complete database schema to TEST database (precog_test).

Schema application order:
1. Base schema (schema_enhanced.sql v1.1)
2. v1.3 -> v1.4 migration (adds strategies, probability_models)
3. v1.4 -> v1.5 migration (if exists)
4. Numbered migrations (001, 002, 003, etc. from database/migrations/)

Uses TEST_DB_* environment variables.
"""

import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# Load environment variables (override=True forces .env to override system vars)
load_dotenv(override=True)

# Test database configuration
db_config = {
    "host": os.getenv("TEST_DB_HOST", "localhost"),
    "port": os.getenv("TEST_DB_PORT", "5432"),
    "dbname": os.getenv("TEST_DB_NAME", "precog_test"),
    "user": os.getenv("TEST_DB_USER", "postgres"),
    "password": os.getenv("TEST_DB_PASSWORD"),
}

# Validate password
if not db_config["password"]:
    print("[ERROR] TEST_DB_PASSWORD not set in .env")
    exit(1)

print("=" * 80)
print("Applying Complete Schema to TEST Database (precog_test)")
print("=" * 80)

# Connect to database
print("\n[CONNECT] Connecting to test database...")
try:
    conn = psycopg2.connect(**db_config)
    conn.autocommit = True
    cursor = conn.cursor()
    print(f"[OK] Connected to {db_config['dbname']}")
except Exception as e:
    print(f"[ERROR] Connection failed: {e}")
    exit(1)

# Define schema files in correct order
repo_root = Path(__file__).parent.parent
schema_files = [
    # 1. Base schema (v1.1)
    repo_root / "src" / "database" / "schema_enhanced.sql",
    # 2. v1.3 -> v1.4 migration (adds strategies, probability_models)
    repo_root / "src" / "database" / "migrations" / "schema_v1.3_to_v1.4_migration.sql",
    # 3. v1.4 -> v1.5 migration
    repo_root / "src" / "database" / "migrations" / "schema_v1.4_to_v1.5_migration.sql",
]

# Apply base schemas and version migrations
print("\n[PHASE 1] Applying base schema and version migrations...")
for i, schema_file in enumerate(schema_files, 1):
    if not schema_file.exists():
        print(f"  [{i}/{len(schema_files)}] SKIPPED: {schema_file.name} (file not found)")
        continue

    print(f"\n  [{i}/{len(schema_files)}] Applying {schema_file.name}...")
    try:
        with open(schema_file, encoding="utf-8") as f:
            schema_sql = f.read()

        cursor.execute(schema_sql)
        print(f"  [OK] {schema_file.name} applied successfully")

    except psycopg2.Error as e:
        print(f"  [ERROR] Failed to apply {schema_file.name}")
        print(f"  Error: {e}")
        conn.rollback()
        exit(1)

# Find and apply numbered migrations
print("\n[PHASE 2] Applying numbered migrations...")
migrations_dir = repo_root / "database" / "migrations"
migration_files = sorted(migrations_dir.glob("[0-9]*.sql"))

if not migration_files:
    print(f"[INFO] No numbered migrations found in {migrations_dir}")
else:
    print(f"[OK] Found {len(migration_files)} numbered migrations")

    for i, migration_file in enumerate(migration_files, 1):
        print(f"\n  [{i}/{len(migration_files)}] Applying {migration_file.name}...")

        try:
            with open(migration_file, encoding="utf-8") as f:
                migration_sql = f.read()

            cursor.execute(migration_sql)
            print(f"  [OK] {migration_file.name} applied successfully")

        except psycopg2.Error as e:
            print(f"  [ERROR] Failed to apply {migration_file.name}")
            print(f"  Error: {e}")
            conn.rollback()
            exit(1)

# Verify schema
print("\n[VERIFY] Checking schema...")
cursor.execute(
    """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name
"""
)
tables = cursor.fetchall()

print(f"[OK] Database has {len(tables)} tables:")
for table in tables:
    print(f"  - {table[0]}")

# Check for critical tables
critical_tables = [
    "platforms",
    "series",
    "events",
    "markets",
    "strategies",
    "probability_models",
    "positions",
    "trades",
]
existing_table_names = [table[0] for table in tables]
missing_tables = [t for t in critical_tables if t not in existing_table_names]

if missing_tables:
    print(f"\n[WARNING] Missing critical tables: {', '.join(missing_tables)}")
else:
    print(f"\n[OK] All {len(critical_tables)} critical tables present")

cursor.close()
conn.close()

print("\n" + "=" * 80)
print("[SUCCESS] Complete schema applied to precog_test database!")
print("=" * 80)
print("\nYou can now run: python -m pytest tests/test_crud_operations.py -v")
