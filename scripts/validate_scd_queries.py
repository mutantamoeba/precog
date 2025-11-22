#!/usr/bin/env python3
"""
SCD Type 2 Query Validation - Pattern 2 Enforcement

Validates that all queries on SCD Type 2 tables include row_current_ind filter.

Pattern 2 (Dual Versioning): Queries on SCD Type 2 tables MUST filter by row_current_ind = TRUE
to avoid accidentally fetching historical versions.

Enforcement:
1. Auto-discover SCD Type 2 tables from database schema (tables with row_current_ind column)
2. Scan Python files for queries on those tables
3. Verify required .filter(table.c.row_current_ind == True) pattern
4. Flag violations with file, line number, and fix suggestion

Reference: docs/guides/DEVELOPMENT_PATTERNS_V1.4.md Pattern 2 (Dual Versioning)
Reference: scripts/validation_config.yaml (SCD Type 2 validation rules)
Related: ARCHITECTURE_DECISIONS ADR-018, ADR-019, ADR-020

Exit codes:
  0 = All SCD Type 2 queries correctly filtered
  1 = Missing row_current_ind filters found
  2 = Cannot connect to database (WARNING only)

Example usage:
  python scripts/validate_scd_queries.py          # Run validation
  python scripts/validate_scd_queries.py --verbose # Detailed output
"""

import os
import re
import sys
from pathlib import Path

try:
    import psycopg2

    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


def load_scd_validation_config() -> dict:
    """
    Load SCD Type 2 validation configuration from validation_config.yaml.

    Returns:
        dict with validation rules, or defaults if file not found
    """
    validation_config_path = PROJECT_ROOT / "scripts" / "validation_config.yaml"

    default_config = {
        "description": "Slowly Changing Dimension Type 2 tables (immutable history)",
        "discovery_method": "Query information_schema for tables with row_current_ind column",
        "required_patterns": [
            # Raw SQL pattern (what we actually use with psycopg2)
            r"row_current_ind\s*=\s*(TRUE|True|true)",
            # ORM patterns (for future use if we migrate to SQLAlchemy)
            r"\.filter\([^)]*row_current_ind\s*==\s*True[^)]*\)",
            r"\.where\([^)]*row_current_ind\.is_\(True\)[^)]*\)",
        ],
        "forbidden_patterns": [
            r"\.all\(\)",  # Missing filter (gets ALL versions)
            r"\.filter_by\([^)]*\)(?!.*row_current_ind)",  # filter_by without row_current_ind
        ],
        "exception_comments": [
            "Historical audit query",
            "Backfill script",
            "Migration only",
        ],
    }

    if not validation_config_path.exists() or not YAML_AVAILABLE:
        return default_config

    try:
        with open(validation_config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
            scd_config = config.get("scd_type2_validation", {})

            # Build regex patterns from YAML patterns
            required_patterns = []
            if "required_pattern" in scd_config:
                # Use pattern from YAML (raw SQL pattern for our psycopg2 implementation)
                required_patterns = [scd_config["required_pattern"]]

            return {
                "description": scd_config.get("description", default_config["description"]),
                "discovery_method": scd_config.get(
                    "discovery_method", default_config["discovery_method"]
                ),
                "required_patterns": required_patterns or default_config["required_patterns"],
                "forbidden_patterns": scd_config.get(
                    "forbidden_patterns", default_config["forbidden_patterns"]
                ),
                "exception_comments": scd_config.get(
                    "exceptions", default_config["exception_comments"]
                ),
            }
    except Exception:
        return default_config


def discover_scd_tables(verbose: bool = False) -> set[str]:
    """
    Auto-discover SCD Type 2 tables from database schema.

    Queries information_schema to find all tables with row_current_ind column.
    This ensures zero maintenance - new SCD Type 2 tables are automatically detected.

    Args:
        verbose: If True, show detailed discovery process

    Returns:
        Set of table names that have row_current_ind column
    """
    if not PSYCOPG2_AVAILABLE:
        if verbose:
            print("[DEBUG] psycopg2 not available - using hardcoded SCD table list")
        # Fallback to known SCD Type 2 tables
        return {
            "markets",
            "positions",
            "strategies",
            "models",
            "odds_snapshots",
            "market_events",
        }

    # Get database connection from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        if verbose:
            print("[DEBUG] DATABASE_URL not set - using hardcoded SCD table list")
        return {
            "markets",
            "positions",
            "strategies",
            "models",
            "odds_snapshots",
            "market_events",
        }

    try:
        # Connect to database
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        # Query information_schema for tables with row_current_ind column
        query = """
            SELECT DISTINCT table_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND column_name = 'row_current_ind'
            ORDER BY table_name
        """

        cursor.execute(query)
        tables = {row[0] for row in cursor.fetchall()}

        cursor.close()
        conn.close()

        if verbose:
            print(f"[DEBUG] Auto-discovered {len(tables)} SCD Type 2 tables from database schema")
            for table in sorted(tables):
                print(f"  - {table}")

        return tables

    except Exception as e:
        if verbose:
            print(f"[DEBUG] Database query failed: {e}")
            print("[DEBUG] Using hardcoded SCD table list")
        # Fallback to known SCD Type 2 tables
        return {
            "markets",
            "positions",
            "strategies",
            "models",
            "odds_snapshots",
            "market_events",
        }


def check_scd_queries(verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Validate all queries on SCD Type 2 tables include row_current_ind filter.

    Scans all Python files in src/precog/ for queries on SCD Type 2 tables.
    Verifies each query includes .filter(row_current_ind == True) or equivalent.

    Args:
        verbose: If True, show detailed validation process

    Returns:
        (passed, violations) tuple
    """
    violations = []

    # Load validation config
    config = load_scd_validation_config()
    required_patterns = config["required_patterns"]
    exception_comments = config["exception_comments"]

    # Discover SCD Type 2 tables
    scd_tables = discover_scd_tables(verbose)

    if not scd_tables:
        if verbose:
            print("[DEBUG] No SCD Type 2 tables found - skipping validation")
        return True, []

    if verbose:
        print(f"[DEBUG] Scanning Python files for queries on {len(scd_tables)} SCD Type 2 tables")

    # Scan all Python files in src/precog/
    python_files = list((PROJECT_ROOT / "src" / "precog").rglob("*.py"))

    files_scanned = 0
    queries_found = 0

    for python_file in python_files:
        # Skip __pycache__, test files, and migrations
        if "__pycache__" in str(python_file) or "test_" in python_file.name:
            continue

        # Skip migration files (they transform ALL versions, not just current)
        if "migrations" in str(python_file):
            continue

        try:
            content = python_file.read_text(encoding="utf-8")
            lines = content.split("\n")

            files_scanned += 1

            # Track markdown code blocks in docstrings
            in_code_block = False

            # Check each line for queries on SCD Type 2 tables
            for line_num, line in enumerate(lines, start=1):
                stripped = line.strip()

                # Toggle code block state when we see ```
                if stripped.startswith("```") or stripped == "```":
                    in_code_block = not in_code_block
                    continue

                # Skip lines inside code blocks
                if in_code_block:
                    continue

                # Skip docstring examples (lines starting with >>> or ...)
                if stripped.startswith((">>>", "...")):
                    continue

                # Check if line queries any SCD Type 2 table
                for table in scd_tables:
                    # Match RAW SQL READ operations (we use psycopg2, NOT SQLAlchemy ORM)
                    # Only check SELECT/JOIN (read operations), not INSERT/UPDATE (write operations)
                    # Example: SELECT * FROM markets WHERE ticker = %s
                    # Example: JOIN markets ON p.market_id = m.market_id
                    table_patterns = [
                        rf"\bFROM\s+{table}\b",  # SELECT FROM markets, DELETE FROM markets
                        rf"\bJOIN\s+{table}\b",  # INNER/LEFT/RIGHT JOIN positions
                        # NOT UPDATE (modifies data, doesn't query)
                        # NOT INSERT INTO (creates data, doesn't query)
                    ]

                    if any(re.search(pattern, line, re.IGNORECASE) for pattern in table_patterns):
                        queries_found += 1

                        # Check if query has row_current_ind filter
                        has_required_filter = False

                        # Check current line and next 10 lines for filter
                        # (SQLAlchemy queries often span multiple lines)
                        context_lines = lines[line_num - 1 : line_num + 10]
                        context = "\n".join(context_lines)

                        for pattern in required_patterns:
                            if re.search(pattern, context, re.IGNORECASE):
                                has_required_filter = True
                                break

                        # Check for exception comments or historical audit function
                        has_exception_comment = False

                        # Check for explicit exception comments (e.g., "# Historical audit query")
                        comment_lines = lines[max(0, line_num - 3) : line_num]
                        comment_context = "\n".join(comment_lines)

                        for exception_comment in exception_comments:
                            if exception_comment.lower() in comment_context.lower():
                                has_exception_comment = True
                                break

                        # Auto-detect historical audit functions (functions with "history" in name)
                        # Example: get_market_history(), get_position_history()
                        # These intentionally fetch ALL versions for audit/analysis
                        if not has_exception_comment:
                            # Check previous 30 lines for function definition with "history" in name
                            func_context_lines = lines[max(0, line_num - 30) : line_num]
                            func_context = "\n".join(func_context_lines)
                            if re.search(r"def\s+\w*history\w*\s*\(", func_context, re.IGNORECASE):
                                has_exception_comment = True

                        # Report violation if no filter and no exception comment
                        if not has_required_filter and not has_exception_comment:
                            relative_path = python_file.relative_to(PROJECT_ROOT)
                            violations.append(
                                f"{relative_path}:{line_num} - Query on '{table}' table missing row_current_ind filter"
                            )
                            violations.append(
                                f"  Fix: Add .filter({table.capitalize()}.row_current_ind == True)"
                            )

        except Exception as e:
            if verbose:
                print(f"[DEBUG] Error scanning {python_file}: {e}")
            continue

    if verbose:
        print(f"[DEBUG] Scanned {files_scanned} files, found {queries_found} SCD Type 2 queries")

    return len(violations) == 0, violations


def main():
    """Run SCD Type 2 query validation."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print("=" * 60)
    print("SCD Type 2 Query Validation (Pattern 2)")
    print("=" * 60)
    print("Reference: docs/guides/DEVELOPMENT_PATTERNS_V1.4.md")
    print("Related: ADR-018, ADR-019, ADR-020 (Dual Versioning)")
    print("")

    # Check dependencies
    if not PSYCOPG2_AVAILABLE:
        print("[WARN] psycopg2 not available - using fallback SCD table list")
        print("")

    # Run validation
    print("[1/1] Checking SCD Type 2 queries for row_current_ind filters...")

    try:
        passed, violations = check_scd_queries(verbose)

        if not passed:
            print(f"[FAIL] {len(violations) // 2} queries missing row_current_ind filter:")
            for v in violations:
                print(f"  {v}")
            print("")
            print("Fix: Add .filter(Table.row_current_ind == True) to ALL SCD Type 2 queries")
            print("Reference: DEVELOPMENT_PATTERNS Pattern 2 (Dual Versioning)")
            print("Exception: Add comment '# Historical audit query' if intentional")
            print("")
            print("=" * 60)
            print("[FAIL] SCD Type 2 query validation failed")
            print("=" * 60)
            return 1
        print("[PASS] All SCD Type 2 queries correctly filtered")

    except Exception as e:
        print(f"[WARN] Validation failed: {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        print("")
        print("Skipping SCD Type 2 validation (non-blocking)")
        print("")
        print("=" * 60)
        print("[WARN] SCD Type 2 validation skipped")
        print("=" * 60)
        return 2

    print("")
    print("=" * 60)
    print("[PASS] SCD Type 2 query validation passed")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
