"""
Live Database Schema Audit Script (Pattern 47).

Spins up an ephemeral PostgreSQL container via testcontainers, applies all
Alembic migrations (0001-0057), then queries information_schema to produce
an authoritative inventory of:
  1. Primary keys (table, column, data type)
  2. Foreign keys (child -> parent, ON DELETE action)
  3. Business key candidates (VARCHAR *_id/*_key columns that are NOT PK and NOT FK)

Usage:
    python scripts/schema_audit_live.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg2
from testcontainers.postgres import PostgresContainer

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

_AUDIT_USER = "audit_user"
_AUDIT_PASSWORD = "audit_password"
_AUDIT_DB = "precog_audit"


def apply_migrations(host, port, database, user, password):
    alembic_dir = SRC_DIR / "precog" / "database"
    env = os.environ.copy()
    for prefix in ("DEV", "TEST", "STAGING", "PROD"):
        env[f"{prefix}_DB_HOST"] = str(host)
        env[f"{prefix}_DB_PORT"] = str(port)
        env[f"{prefix}_DB_NAME"] = database
        env[f"{prefix}_DB_USER"] = user
        env[f"{prefix}_DB_PASSWORD"] = password
    env["DB_HOST"] = str(host)
    env["DB_PORT"] = str(port)
    env["DB_NAME"] = database
    env["DB_USER"] = user
    env["DB_PASSWORD"] = password

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(alembic_dir),
        env=env,
        capture_output=True,
        timeout=120,
    )
    if result.returncode != 0:
        print("=== ALEMBIC MIGRATION FAILED ===")
        print("STDOUT:", result.stdout.decode(errors="replace"))
        print("STDERR:", result.stderr.decode(errors="replace"))
        sys.exit(1)
    print("Alembic migrations applied successfully.")


def query_primary_keys(cur):
    cur.execute("""
        SELECT tc.table_name, kcu.column_name AS pk_column, c.data_type, c.udt_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        JOIN information_schema.columns c
            ON c.table_name = kcu.table_name AND c.column_name = kcu.column_name AND c.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
            AND tc.table_schema = 'public'
            AND tc.table_name != 'alembic_version'
        ORDER BY tc.table_name, kcu.ordinal_position;
    """)
    return cur.fetchall()


def query_foreign_keys(cur):
    cur.execute("""
        SELECT tc.table_name AS child_table, kcu.column_name AS child_column,
               ccu.table_name AS parent_table, ccu.column_name AS parent_column,
               rc.delete_rule AS on_delete
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
        JOIN information_schema.referential_constraints rc
            ON tc.constraint_name = rc.constraint_name AND tc.table_schema = rc.constraint_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
        ORDER BY tc.table_name, kcu.column_name;
    """)
    return cur.fetchall()


def query_business_keys(cur, pk_columns, fk_columns):
    cur.execute("""
        SELECT c.table_name, c.column_name, c.data_type, c.is_nullable, c.character_maximum_length
        FROM information_schema.columns c
        JOIN information_schema.tables t
            ON c.table_name = t.table_name AND c.table_schema = t.table_schema
        WHERE c.table_schema = 'public'
            AND t.table_type = 'BASE TABLE'
            AND c.table_name != 'alembic_version'
            AND (c.column_name LIKE '%%_id' OR c.column_name LIKE '%%_key')
            AND c.data_type IN ('character varying', 'text')
        ORDER BY c.table_name, c.column_name;
    """)
    rows = cur.fetchall()
    return [r for r in rows if (r[0], r[1]) not in pk_columns and (r[0], r[1]) not in fk_columns]


def print_table(title, headers, rows, widths=None):
    if widths is None:
        widths = [len(h) for h in headers]
        for row in rows:
            for i, val in enumerate(row):
                widths[i] = max(widths[i], len(str(val or "")))
    print(f"\n=== {title} ===")
    print(" | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    print("-|-".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        print(" | ".join(str(val or "").ljust(widths[i]) for i, val in enumerate(row)))
    print(f"\n({len(rows)} rows)")


def main():
    print("Starting PostgreSQL container...")
    container = PostgresContainer(
        image="postgres:15",
        username=_AUDIT_USER,
        password=_AUDIT_PASSWORD,
        dbname=_AUDIT_DB,
    )
    with container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)
        print(f"Container running at {host}:{port}")

        print("Applying Alembic migrations...")
        apply_migrations(host, port, _AUDIT_DB, _AUDIT_USER, _AUDIT_PASSWORD)

        conn = psycopg2.connect(
            host=host, port=port, dbname=_AUDIT_DB, user=_AUDIT_USER, password=_AUDIT_PASSWORD
        )
        conn.autocommit = True
        cur = conn.cursor()

        pk_rows = query_primary_keys(cur)
        pk_set = {(r[0], r[1]) for r in pk_rows}
        pk_display = [
            (r[0], r[1], f"{r[2]} ({r[3]})" if r[3] and r[3] not in r[2] else r[2]) for r in pk_rows
        ]
        print_table("PRIMARY KEYS", ["table_name", "pk_column", "data_type"], pk_display)

        fk_rows = query_foreign_keys(cur)
        fk_set = {(r[0], r[1]) for r in fk_rows}
        print_table(
            "FOREIGN KEYS",
            ["child_table", "child_column", "parent_table", "parent_column", "on_delete"],
            fk_rows,
        )

        bk_rows = query_business_keys(cur, pk_set, fk_set)
        bk_display = [(r[0], r[1], f"{r[2]}({r[4]})" if r[4] else r[2], r[3]) for r in bk_rows]
        print_table(
            "BUSINESS KEY CANDIDATES (VARCHAR *_id/*_key columns, NOT PK, NOT FK)",
            ["table_name", "column_name", "data_type", "is_nullable"],
            bk_display,
        )

        print("\n=== SUMMARY ===")
        cur.execute("""SELECT count(*) FROM information_schema.tables
                       WHERE table_schema='public' AND table_type='BASE TABLE' AND table_name!='alembic_version';""")
        print(f"Total tables: {cur.fetchone()[0]}")
        print(f"Total PK columns: {len(pk_rows)}")
        print(f"Total FK constraints: {len(fk_rows)}")
        print(f"Business key candidates: {len(bk_rows)}")
        cur.close()
        conn.close()
    print("\nContainer stopped. Audit complete.")


if __name__ == "__main__":
    main()
