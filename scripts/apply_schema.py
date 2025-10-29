#!/usr/bin/env python3
"""
Apply database schema to precog_dev
"""
import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database configuration from environment
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'precog_dev'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD')  # No default - must be set!
}

# Validate that password is set
if not db_config['password']:
    print("[ERROR] DB_PASSWORD environment variable not set!")
    print("\nPlease create a .env file in the project root with:")
    print("DB_PASSWORD=your_password_here")
    exit(1)

print("Connecting to database...")
conn = psycopg2.connect(**db_config)
conn.autocommit = True
cursor = conn.cursor()

print("Reading enhanced schema file...")
with open('src/database/schema_enhanced.sql', 'r', encoding='utf-8') as f:
    schema_sql = f.read()

print("Applying schema...")
try:
    cursor.execute(schema_sql)
    print("[OK] Schema applied successfully!")
except Exception as e:
    print(f"[ERROR] Failed to apply schema: {e}")
    exit(1)

# Verify tables created
print("\nVerifying tables...")
cursor.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name;
""")

tables = cursor.fetchall()
print(f"[OK] Created {len(tables)} tables:")
for table in tables:
    print(f"  - {table[0]}")

# Verify DECIMAL columns
print("\nVerifying DECIMAL precision on price columns...")
cursor.execute("""
    SELECT table_name, column_name, data_type, numeric_precision, numeric_scale
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND data_type = 'numeric'
    ORDER BY table_name, column_name;
""")

decimal_columns = cursor.fetchall()
print(f"[OK] Found {len(decimal_columns)} DECIMAL columns:")
for col in decimal_columns:
    table, column, dtype, precision, scale = col
    print(f"  - {table}.{column}: DECIMAL({precision},{scale})")

# Check Kalshi platform inserted
print("\nVerifying initial data...")
cursor.execute("SELECT platform_id, display_name FROM platforms;")
platforms = cursor.fetchall()
print(f"[OK] {len(platforms)} platform(s) inserted:")
for p in platforms:
    print(f"  - {p[0]}: {p[1]}")

cursor.close()
conn.close()

print("\n" + "="*60)
print("[SUCCESS] Database schema applied and verified!")
print("="*60)
