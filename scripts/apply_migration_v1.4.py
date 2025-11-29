#!/usr/bin/env python3
"""
Apply schema v1.4 migration (V1.3 → V1.4)

Environment Safety (Issue #161):
    This script includes environment detection and confirmation prompts
    for staging/prod environments. See DATABASE_ENVIRONMENT_STRATEGY_V1.0.md
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# =============================================================================
# ENVIRONMENT DETECTION (Issue #161)
# =============================================================================
def get_environment() -> str:
    """
    Determine current database environment.

    Priority:
    1. PRECOG_ENV environment variable (explicit)
    2. DB_NAME environment variable (inferred from name)
    3. Default to 'dev' (safe default)

    Returns:
        Environment name: 'dev', 'test', 'staging', or 'prod'
    """
    # Explicit environment selection (highest priority)
    env = os.getenv("PRECOG_ENV")
    if env:
        valid_envs = ("dev", "test", "staging", "prod")
        if env not in valid_envs:
            print(f"[ERROR] Invalid PRECOG_ENV: {env}. Must be one of {valid_envs}")
            sys.exit(1)
        return env

    # Infer from database name
    db_name = os.getenv("DB_NAME", "precog_dev")
    if "test" in db_name:
        return "test"
    if "staging" in db_name:
        return "staging"
    if "prod" in db_name:
        return "prod"
    return "dev"


# Database configuration from environment
db_config = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "precog_dev"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),  # No default - must be set!
}

# Validate that password is set
if not db_config["password"]:
    print("[ERROR] DB_PASSWORD environment variable not set!")
    print("\nPlease create a .env file in the project root with:")
    print("DB_PASSWORD=your_password_here")
    sys.exit(1)

# =============================================================================
# ENVIRONMENT SAFETY CHECKS (Issue #161)
# =============================================================================
current_env = get_environment()

print("=" * 70)
print("Schema Migration: V1.3 -> V1.4")
print("=" * 70)
print()
print(f"  Environment:  {current_env.upper()}")
print(f"  Database:     {db_config['dbname']}")
print(f"  Host:         {db_config['host']}:{db_config['port']}")
print(f"  User:         {db_config['user']}")
print()

# Staging/Prod confirmation prompt
if current_env in ("staging", "prod"):
    print("=" * 70)
    print(f"  WARNING: You are about to run a migration in {current_env.upper()}!")
    print("=" * 70)
    print()
    print("  This will modify the database schema. Please ensure:")
    print("  1. You have a recent backup")
    print("  2. This migration was tested in dev/test environments")
    print("  3. You have approval to proceed")
    print()

    # Require explicit confirmation
    confirmation = input(f"  Type '{current_env.upper()}' to confirm: ")
    if confirmation != current_env.upper():
        print()
        print("[ABORTED] Migration cancelled - confirmation did not match")
        sys.exit(0)
    print()
    print("[CONFIRMED] Proceeding with migration...")
    print()

print("Connecting to database...")
conn = psycopg2.connect(**db_config)
conn.autocommit = True
cursor = conn.cursor()
print(f"[OK] Connected to {db_config['dbname']}")

print("\nReading migration file...")
with open("src/database/migrations/schema_v1.3_to_v1.4_migration.sql", encoding="utf-8") as f:
    migration_sql = f.read()

print("Applying migration...")
try:
    cursor.execute(migration_sql)
    print("[OK] Migration applied successfully!")
except Exception as e:
    print(f"[ERROR] Migration failed: {e}")
    sys.exit(1)

# Verify tables created
print("\nVerifying tables...")
cursor.execute("""
    SELECT tablename
    FROM pg_tables
    WHERE schemaname = 'public'
    AND tablename IN ('strategies', 'probability_models')
    ORDER BY tablename;
""")
tables = cursor.fetchall()
print(f"[OK] New tables: {[t[0] for t in tables]}")

# Verify columns added
print("\nVerifying new columns...")
cursor.execute("""
    SELECT table_name, column_name
    FROM information_schema.columns
    WHERE table_schema = 'public'
    AND (
        (table_name = 'positions' AND column_name = 'trailing_stop_state')
        OR (table_name = 'edges' AND column_name IN ('strategy_id', 'model_id'))
        OR (table_name = 'trades' AND column_name IN ('strategy_id', 'model_id'))
    )
    ORDER BY table_name, column_name;
""")
columns = cursor.fetchall()
print("[OK] New columns:")
for table, column in columns:
    print(f"  - {table}.{column}")

# Verify views created
print("\nVerifying views...")
cursor.execute("""
    SELECT viewname
    FROM pg_views
    WHERE schemaname = 'public'
    AND viewname IN ('active_strategies', 'active_models', 'trade_attribution')
    ORDER BY viewname;
""")
views = cursor.fetchall()
print(f"[OK] New views: {[v[0] for v in views]}")

cursor.close()
conn.close()

print("\n" + "=" * 70)
print("[SUCCESS] Migration v1.3 -> v1.4 complete!")
print("=" * 70)
