#!/usr/bin/env python3
"""
Simple database connection test - bypasses .env parsing issues
"""
import psycopg2

# Direct credentials (matching your .env file)
db_config = {
    'host': 'localhost',
    'port': '5432',
    'dbname': 'precog_dev',
    'user': 'postgres',
    'password': 'suckbluefrogs'
}

print("Testing PostgreSQL connection...")
print(f"Host: {db_config['host']}")
print(f"Port: {db_config['port']}")
print(f"Database: {db_config['dbname']}")
print(f"User: {db_config['user']}")
print()

try:
    # Attempt connection
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()

    # Get PostgreSQL version
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]

    print("[OK] Connection successful!")
    print(f"PostgreSQL version: {version[:80]}...")
    print()

    # Check if database exists
    cursor.execute("SELECT current_database();")
    db_name = cursor.fetchone()[0]
    print(f"[OK] Connected to database: {db_name}")

    # Check for existing tables
    cursor.execute("""
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'public';
    """)
    table_count = cursor.fetchone()[0]
    print(f"[OK] Tables in public schema: {table_count}")

    cursor.close()
    conn.close()

    print()
    print("=" * 60)
    print("[SUCCESS] Database connection test PASSED")
    print("=" * 60)
    print()
    print("Ready to begin Phase 1 implementation!")

except psycopg2.Error as e:
    print(f"[ERROR] Connection failed!")
    print(f"Error: {e}")
    print("\nPlease check:")
    print("1. PostgreSQL service is running")
    print("2. Database 'precog_dev' exists")
    print("3. Username and password are correct")
    exit(1)
