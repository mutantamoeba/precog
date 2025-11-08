#!/usr/bin/env python3
"""
Test script to verify PostgreSQL TEST database connection.
Uses TEST_DB_* environment variables.
"""

import os

import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get TEST database credentials
db_config = {
    "host": os.getenv("TEST_DB_HOST", "localhost"),
    "port": os.getenv("TEST_DB_PORT", "5432"),
    "dbname": os.getenv("TEST_DB_NAME", "precog_test"),
    "user": os.getenv("TEST_DB_USER", "postgres"),
    "password": os.getenv("TEST_DB_PASSWORD", ""),
}

print("Testing PostgreSQL TEST database connection...")
print(f"Host: {db_config['host']}")
print(f"Port: {db_config['port']}")
print(f"Database: {db_config['dbname']}")
print(f"User: {db_config['user']}")
print(f"Password: {'***' if db_config['password'] else '(empty)'}")
print()

try:
    # Attempt connection
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()

    # Get PostgreSQL version
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]

    print("[OK] Connection successful!")
    print(f"PostgreSQL version: {version[:50]}...")

    # Check if database exists
    cursor.execute("SELECT current_database();")
    db_name = cursor.fetchone()[0]
    print(f"[OK] Connected to database: {db_name}")

    cursor.close()
    conn.close()
    print("\n[OK] Database connection test PASSED")

except psycopg2.Error as e:
    print("[FAIL] Connection failed!")
    print(f"Error: {e}")
    print("\nPlease check:")
    print("1. PostgreSQL service is running")
    print("2. Database 'precog_test' exists")
    print("3. .env file has TEST_DB_USER and TEST_DB_PASSWORD")
    print("4. PostgreSQL pg_hba.conf allows local connections")
    exit(1)
