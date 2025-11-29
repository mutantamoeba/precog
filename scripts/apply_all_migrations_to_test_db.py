#!/usr/bin/env python3
"""
Apply all database migrations to TEST database (precog_test).
Uses TEST_DB_* environment variables.

Environment Safety (Issue #161):
    This script ONLY works with test databases. It will refuse to run
    against dev/staging/prod databases. See DATABASE_ENVIRONMENT_STRATEGY_V1.0.md
"""

import os
import sys
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
    sys.exit(1)

# =============================================================================
# ENVIRONMENT SAFETY CHECK (Issue #161)
# =============================================================================
# This script is ONLY for test database - enforce this strictly
db_name = db_config["dbname"] or ""
if "test" not in db_name.lower():
    print("=" * 70)
    print("[ERROR] ENVIRONMENT SAFETY VIOLATION")
    print("=" * 70)
    print()
    print("  This script is for TEST databases only!")
    print(f"  Database name '{db_name}' does not contain 'test'")
    print()
    print("  If you want to migrate dev/staging/prod, use:")
    print("    - scripts/apply_migration_v1.4.py")
    print("    - scripts/apply_migration_v1.5.py")
    print()
    print("  Or set TEST_DB_NAME=precog_test in your .env file")
    print("=" * 70)
    sys.exit(1)

print("=" * 70)
print("Applying All Migrations to TEST Database")
print("=" * 70)
print()
print("  Environment:  TEST (enforced)")
print(f"  Database:     {db_config['dbname']}")
print(f"  Host:         {db_config['host']}:{db_config['port']}")
print(f"  User:         {db_config['user']}")
print()

# Connect to database
print("[1/3] Connecting to test database...")
try:
    conn = psycopg2.connect(**db_config)
    conn.autocommit = True
    cursor = conn.cursor()
    print(f"[OK] Connected to {db_config['dbname']}")
except Exception as e:
    print(f"[ERROR] Connection failed: {e}")
    sys.exit(1)

# Find all migration files
print("\n[2/3] Finding migration files...")
migrations_dir = Path(__file__).parent.parent / "database" / "migrations"
migration_files = sorted(migrations_dir.glob("*.sql"))

if not migration_files:
    print(f"[ERROR] No migration files found in {migrations_dir}")
    sys.exit(1)

print(f"[OK] Found {len(migration_files)} migration files")

# Apply each migration
print("\n[3/3] Applying migrations...")
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
        sys.exit(1)

# Verify schema
print("\n[VERIFY] Checking schema...")
cursor.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name
""")
tables = cursor.fetchall()

print(f"[OK] Database has {len(tables)} tables:")
for table in tables:
    print(f"  - {table[0]}")

cursor.close()
conn.close()

print("\n" + "=" * 70)
print(f"[SUCCESS] All migrations applied to {db_config['dbname']}!")
print("=" * 70)
print("\nYou can now run: pytest tests/test_crud_operations.py -v")
