#!/usr/bin/env python3
"""
Apply schema v1.4 migration
"""
import psycopg2

# Database configuration
db_config = {
    'host': 'localhost',
    'port': '5432',
    'dbname': 'precog_dev',
    'user': 'postgres',
    'password': 'suckbluefrogs'
}

print("Connecting to database...")
conn = psycopg2.connect(**db_config)
conn.autocommit = True
cursor = conn.cursor()

print("Reading migration file...")
with open('src/database/migrations/schema_v1.3_to_v1.4_migration.sql', 'r', encoding='utf-8') as f:
    migration_sql = f.read()

print("Applying migration...")
try:
    cursor.execute(migration_sql)
    print("[OK] Migration applied successfully!")
except Exception as e:
    print(f"[ERROR] Migration failed: {e}")
    exit(1)

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
print(f"[OK] New columns:")
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

print("\n" + "="*60)
print("[SUCCESS] Migration v1.3 → v1.4 complete!")
print("="*60)
