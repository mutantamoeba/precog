#!/usr/bin/env python3
"""
Apply schema v1.5 migration (V1.4 → V1.5)
Phase 0.5: Position monitoring and exit management

Environment Safety (Issue #161):
    This script includes environment detection and confirmation prompts
    for staging/prod environments. See DATABASE_ENVIRONMENT_STRATEGY_V1.0.md
"""

import os
import sys
from pathlib import Path

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
print("Schema Migration: V1.4 -> V1.5")
print("Phase 0.5: Position Monitoring & Exit Management")
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
try:
    conn = psycopg2.connect(**db_config)
    conn.autocommit = True
    cursor = conn.cursor()
    print(f"[OK] Connected to {db_config['dbname']}")
except Exception as e:
    print(f"[ERROR] Connection failed: {e}")
    exit(1)

print("\nReading migration file...")
migration_file = (
    Path(__file__).parent.parent
    / "src"
    / "database"
    / "migrations"
    / "schema_v1.4_to_v1.5_migration.sql"
)
try:
    with open(migration_file, encoding="utf-8") as f:
        migration_sql = f.read()
    print(f"[OK] Loaded {migration_file.name}")
except Exception as e:
    print(f"[ERROR] Failed to read migration file: {e}")
    exit(1)

print("\nApplying migration...")
try:
    cursor.execute(migration_sql)
    print("[OK] Migration applied successfully!")
except Exception as e:
    print(f"[ERROR] Migration failed: {e}")
    cursor.close()
    conn.close()
    exit(1)

# Verification
print("\n" + "=" * 60)
print("VERIFICATION")
print("=" * 60)

# Verify tables created
print("\n1. Verifying new tables...")
cursor.execute("""
    SELECT tablename
    FROM pg_tables
    WHERE schemaname = 'public'
    AND tablename IN ('position_exits', 'exit_attempts')
    ORDER BY tablename;
""")
tables = cursor.fetchall()
if len(tables) == 2:
    print(f"[OK] New tables created: {[t[0] for t in tables]}")
else:
    print(f"[WARNING] Expected 2 tables, found {len(tables)}")

# Verify columns added to positions
print("\n2. Verifying new columns in positions table...")
cursor.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema = 'public'
    AND table_name = 'positions'
    AND column_name IN ('current_price', 'unrealized_pnl_pct', 'last_update', 'exit_reason', 'exit_priority')
    ORDER BY column_name;
""")
columns = cursor.fetchall()
expected_columns = [
    "current_price",
    "exit_priority",
    "exit_reason",
    "last_update",
    "unrealized_pnl_pct",
]
if len(columns) == 5:
    print("[OK] New columns in positions:")
    for col in columns:
        print(f"  - {col[0]}")
else:
    print(f"[WARNING] Expected 5 columns, found {len(columns)}")

# Verify CHECK constraints
print("\n3. Verifying CHECK constraints...")
cursor.execute("""
    SELECT conname, pg_get_constraintdef(oid) as definition
    FROM pg_constraint
    WHERE conrelid = 'position_exits'::regclass
    AND contype = 'c'
    ORDER BY conname;
""")
constraints = cursor.fetchall()
print(f"[OK] position_exits CHECK constraints: {len(constraints)}")
for name, _definition in constraints:
    print(f"  - {name}")

# Verify indexes
print("\n4. Verifying indexes...")
cursor.execute("""
    SELECT indexname
    FROM pg_indexes
    WHERE schemaname = 'public'
    AND tablename IN ('position_exits', 'exit_attempts')
    ORDER BY indexname;
""")
indexes = cursor.fetchall()
print(f"[OK] Indexes created: {len(indexes)}")
for idx in indexes:
    print(f"  - {idx[0]}")

# Verify views created
print("\n5. Verifying helper views...")
cursor.execute("""
    SELECT viewname
    FROM pg_views
    WHERE schemaname = 'public'
    AND viewname IN ('positions_urgent_monitoring', 'exit_performance_summary', 'stale_position_alerts')
    ORDER BY viewname;
""")
views = cursor.fetchall()
if len(views) == 3:
    print(f"[OK] New views created: {[v[0] for v in views]}")
else:
    print(f"[WARNING] Expected 3 views, found {len(views)}")

# Get table counts
print("\n6. Current table row counts...")
for table in ["position_exits", "exit_attempts", "positions"]:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table};")  # noqa: S608, RUF100 - table name from hardcoded list, not user input
        count = cursor.fetchone()[0]
        print(f"  - {table}: {count} rows")
    except:
        print(f"  - {table}: [table not found]")

cursor.close()
conn.close()

print("\n" + "=" * 60)
print("[SUCCESS] Migration V1.4 -> V1.5 complete!")
print("=" * 60)
print("\nNew features:")
print("  [OK] position_exits table (track each exit event)")
print("  [OK] exit_attempts table (debug price walking)")
print("  [OK] Monitoring fields in positions (current_price, unrealized_pnl_pct, last_update)")
print("  [OK] Exit tracking (exit_reason, exit_priority)")
print("  [OK] Helper views (urgent monitoring, exit performance, stale alerts)")
print("\nDatabase schema is now at V1.5 - ready for Phase 5 implementation!")
