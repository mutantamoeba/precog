#!/usr/bin/env python3
"""
Simple database connection test - uses environment variables for security
"""
import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database credentials from environment
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
    print("\nOr set the environment variable:")
    print("export DB_PASSWORD=your_password_here  # Linux/Mac")
    print("set DB_PASSWORD=your_password_here     # Windows CMD")
    exit(1)

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
