#!/usr/bin/env python3
"""
Quick test script to verify PostgreSQL database connection
"""

import os

import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database credentials
db_config = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "precog_dev"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
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

    print("✓ Connection successful!")
    print(f"PostgreSQL version: {version[:50]}...")

    # Check if database exists
    cursor.execute("SELECT current_database();")
    db_name = cursor.fetchone()[0]
    print(f"✓ Connected to database: {db_name}")

    cursor.close()
    conn.close()
    print("\n✓ Database connection test PASSED")

except psycopg2.Error as e:
    print("✗ Connection failed!")
    print(f"Error: {e}")
    print("\nPlease check:")
    print("1. PostgreSQL service is running")
    print("2. Database 'precog_dev' exists (run: createdb precog_dev)")
    print("3. .env file has correct DB_USER and DB_PASSWORD")
    print("4. PostgreSQL pg_hba.conf allows local connections")
    exit(1)
