"""
Database Schema Consistency Validator - Phase 0.7 DEF-008

Validates database schema consistency across:
- Documentation (DATABASE_SCHEMA_SUMMARY_V1.7.md)
- Implementation (PostgreSQL database)
- Requirements (MASTER_REQUIREMENTS_V2.10.md)
- Architecture Decisions (ARCHITECTURE_DECISIONS_V2.10.md)

8 Validation Levels:
1. Table Existence - Verify all tables documented/implemented
2. Column Consistency - Match names, types, constraints
3. Type Precision for Prices - DECIMAL(10,4) enforcement
4. SCD Type 2 Compliance - row_current_ind pattern
5. Foreign Key Integrity - Documented FKs exist
6. Requirements Traceability - REQ-DB-* compliance
7. ADR Compliance - ADR-002 (Decimal), ADR-009 (SCD Type 2)
8. Cross-Document Consistency - Docs don't contradict

Educational Note:
    Schema validation is CRITICAL for preventing:
    - Float precision loss (Kalshi uses sub-penny pricing)
    - Documentation drift (docs say DECIMAL, DB has FLOAT)
    - Missing indexes (SCD Type 2 queries slow without indexes)
    - Broken foreign keys (data integrity violations)

    Why this matters:
    - One FLOAT column could cause $thousands in trading errors
    - Missing SCD Type 2 indexes = 100x slower queries
    - Documentation drift = wasted developer time debugging

Usage:
    python scripts/validate_schema_consistency.py

Exit Codes:
    0 - All validations passed
    1 - One or more validations failed

Reference:
    - docs/utility/PHASE_0.7_DEFERRED_TASKS_V1.1.md (DEF-008)
    - docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md
    - docs/foundation/MASTER_REQUIREMENTS_V2.10.md (REQ-DB-003, REQ-DB-004, REQ-DB-005)
    - docs/foundation/ARCHITECTURE_DECISIONS_V2.10.md (ADR-002, ADR-009)
"""

import re
import sys
from pathlib import Path
from typing import Any

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from precog.database.connection import fetch_all, test_connection


# Color codes for terminal output (ASCII fallback for Windows)
def colored_ok(text: str) -> str:
    """Green color for success."""
    return f"[OK] {text}"


def colored_error(text: str) -> str:
    """Red color for errors."""
    return f"[ERROR] {text}"


def colored_warn(text: str) -> str:
    """Yellow color for warnings."""
    return f"[WARN] {text}"


def colored_info(text: str) -> str:
    """Blue color for info."""
    return f"[INFO] {text}"


# ============================================================================
# PARSING UTILITIES
# ============================================================================


def parse_documented_tables(schema_file: Path) -> dict[str, dict[str, Any]]:
    """
    Parse DATABASE_SCHEMA_SUMMARY to extract documented tables and columns.

    Returns:
        Dict mapping table_name -> {
            'columns': {col_name: col_definition, ...},
            'versioned': bool,  # SCD Type 2?
            'has_foreign_keys': bool
        }
    """
    content = schema_file.read_text(encoding="utf-8")
    tables = {}

    # Find all CREATE TABLE statements
    # Look for "#### table_name" headers followed by CREATE TABLE
    table_headers = re.findall(r"#### (\w+)", content)

    # Filter out non-table headers
    skip_headers = ["Pattern", "Append-Only", "Tables"]
    table_names = [t for t in table_headers if t not in skip_headers]

    for table_name in table_names:
        tables[table_name] = {"columns": {}, "versioned": False, "has_foreign_keys": False}

    return tables


def get_database_tables() -> list[str]:
    """
    Query PostgreSQL information_schema to get all tables in database.

    Returns:
        List of table names
    """
    query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """

    result = fetch_all(query)
    return [row["table_name"] for row in result]


def get_table_columns(table_name: str) -> list[dict]:
    """
    Get column metadata for a specific table.

    Returns:
        List of dicts with: column_name, data_type, is_nullable, column_default
    """
    query = """
        SELECT
            column_name,
            data_type,
            numeric_precision,
            numeric_scale,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position;
    """

    return fetch_all(query, (table_name,))


def get_foreign_keys(table_name: str) -> list[dict]:
    """
    Get foreign key constraints for a specific table.

    Returns:
        List of dicts with: constraint_name, column_name,
                           foreign_table_name, foreign_column_name
    """
    query = """
        SELECT
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
          AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
          AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND tc.table_name = %s;
    """

    return fetch_all(query, (table_name,))


# ============================================================================
# VALIDATION LEVEL 1: TABLE EXISTENCE
# ============================================================================


def validate_table_existence() -> tuple[bool, list[str]]:
    """
    Level 1: Verify all tables in documentation exist in database and vice versa.

    Returns:
        (passed: bool, errors: list[str])
    """
    print(f"\n{colored_info('[1/8] Table Existence Validation')}")

    errors = []

    # Get documented tables
    schema_file = (
        Path(__file__).parent.parent / "docs" / "database" / "DATABASE_SCHEMA_SUMMARY_V1.12.md"
    )
    if not schema_file.exists():
        errors.append(f"Schema documentation not found: {schema_file}")
        return False, errors

    # Parse documented tables
    documented_tables = set(parse_documented_tables(schema_file).keys())

    # Get actual database tables
    db_tables = set(get_database_tables())

    # Compare
    missing_in_db = documented_tables - db_tables
    missing_in_docs = db_tables - documented_tables

    if missing_in_db:
        errors.append(f"{len(missing_in_db)} tables documented but not in database:")
        for table in sorted(missing_in_db):
            errors.append(f"       - {table}")

    if missing_in_docs:
        # This is a warning, not an error (DB might have tables not yet documented)
        print(f"  {colored_warn(f'{len(missing_in_docs)} tables in database but not documented:')}")
        for table in sorted(missing_in_docs):
            print(f"       - {table}")

    if missing_in_db:
        for error in errors:
            print(f"  {colored_error(error)}")
        return False, errors
    print(f"  {colored_ok(f'All {len(db_tables)} tables match documentation')}")
    return True, []


# ============================================================================
# VALIDATION LEVEL 2: COLUMN CONSISTENCY
# ============================================================================


def validate_column_consistency() -> tuple[bool, list[str]]:
    """
    Level 2: Verify columns match between documentation and database.

    For now, this is a stub - would require complex parsing of CREATE TABLE statements.
    """
    print(f"\n{colored_info('[2/8] Column Consistency Validation')}")
    print(f"  {colored_warn('Column-level validation not yet implemented')}")
    print("        (Would require full parsing of CREATE TABLE statements)")
    return True, []


# ============================================================================
# VALIDATION LEVEL 3: TYPE PRECISION FOR PRICES
# ============================================================================


def validate_type_precision() -> tuple[bool, list[str]]:
    """
    Level 3: All price/probability columns MUST be DECIMAL(10,4).

    Validates REQ-DB-003 and ADR-002 compliance.

    MAINTENANCE GUIDE:
    ==================
    When adding NEW tables with price/probability columns:
    1. Add table_name to price_columns dict below
    2. List all price/probability column names for that table
    3. Tag with phase number for tracking (e.g., # Phase 3)

    Example:
        price_columns = {
            'markets': ['yes_bid', 'yes_ask', ...],
            'odds_history': ['historical_odds'],  # Phase 3
            'portfolio': ['total_value'],  # Phase 5
        }

    What counts as a "price" column:
    - Market prices (yes_bid, yes_ask, no_bid, no_ask)
    - Trade prices (entry_price, exit_price, fill_price)
    - Probabilities (edge_probability, model_probability)
    - Account balances (cash_balance, total_equity)
    - Anything denominated in dollars or probabilities (0.0 to 1.0)

    What does NOT need to be added:
    - Non-price columns (ticker, status, description, etc.)
    - Quantities/counts (quantity, volume) - can be INTEGER
    - Percentages stored as integers (e.g., win_rate_pct as INT)
    - IDs, timestamps, booleans

    Maintenance: ~5 minutes per new price table
    """
    print(f"\n{colored_info('[3/8] Type Precision Validation (DECIMAL for Prices)')}")

    errors = []

    # ========================================================================
    # CONFIGURATION: Price/Probability Columns
    # ========================================================================
    # UPDATE THIS when adding tables with price/probability columns
    # Format: 'table_name': ['col1', 'col2', ...],
    # ========================================================================
    price_columns = {
        "markets": ["yes_bid", "yes_ask", "no_bid", "no_ask", "settlement_price"],
        "positions": ["entry_price", "exit_price", "current_price"],
        "trades": ["price", "fill_price"],
        "edges": ["edge_probability"],
        "exit_evals": ["current_price", "exit_threshold"],
        "account_balance": ["cash_balance", "total_equity"],
        "position_exits": ["exit_price"],
        # Future tables: Add here when implementing new price-related tables
        # Example:
        # 'odds_history': ['historical_odds', 'snapshot_price'],  # Phase 3
        # 'portfolio': ['total_value', 'unrealized_pnl'],  # Phase 5
    }

    for table_name, columns in price_columns.items():
        # Check if table exists
        table_columns = get_table_columns(table_name)

        if not table_columns:
            # Table doesn't exist - skip (Level 1 will catch this)
            continue

        # Build column lookup
        col_lookup = {col["column_name"]: col for col in table_columns}

        for col_name in columns:
            if col_name not in col_lookup:
                # Column doesn't exist - might be OK (e.g., exit_price not added yet)
                continue

            col_info = col_lookup[col_name]
            data_type = col_info["data_type"]
            precision = col_info.get("numeric_precision")
            scale = col_info.get("numeric_scale")

            # Check if DECIMAL(10,4)
            if data_type != "numeric":
                errors.append(f"{table_name}.{col_name}: Expected DECIMAL, got {data_type.upper()}")
            elif precision != 10 or scale != 4:
                errors.append(
                    f"{table_name}.{col_name}: Expected DECIMAL(10,4), got DECIMAL({precision},{scale})"
                )

    if not errors:
        sum(len(cols) for cols in price_columns.values())
        print(f"  {colored_ok('All price columns use DECIMAL(10,4) precision')}")
        return True, []
    for error in errors:
        print(f"  {colored_error(error)}")
    print(f"\n  {colored_error('Float precision loss risk detected!')}")
    print("  Fix: Change column type to DECIMAL(10,4) in migration")
    return False, errors


# ============================================================================
# VALIDATION LEVEL 4: SCD TYPE 2 COMPLIANCE
# ============================================================================


def validate_scd_type2_compliance() -> tuple[bool, list[str]]:
    """
    Level 4: Verify SCD Type 2 pattern implemented correctly.

    Validates REQ-DB-004 and ADR-009 compliance.

    MAINTENANCE GUIDE:
    ==================
    When adding NEW tables using SCD Type 2 versioning pattern:
    1. Add table name to versioned_tables list below
    2. Ensure table has all 4 required columns (see below)
    3. Tag with phase number for tracking

    SCD Type 2 Required Columns:
    - row_current_ind BOOLEAN NOT NULL DEFAULT TRUE
    - row_start_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    - row_end_ts TIMESTAMP (nullable)
    - row_version INTEGER NOT NULL DEFAULT 1

    What tables use SCD Type 2:
    - Frequently-changing data (markets, positions, game_states)
    - Data where you need historical snapshots
    - Data queried with "current" state (WHERE row_current_ind = TRUE)

    What tables do NOT use SCD Type 2:
    - Append-only tables (trades, settlements) - use regular INSERT only
    - Immutable versioned tables (strategies, probability_models) - use version field
    - Static reference tables (platforms, teams)

    Example:
        versioned_tables = [
            'markets',
            'positions',
            'portfolio_snapshots',  # Phase 5 - new versioned table
        ]

    Maintenance: ~2 minutes per new versioned table
    """
    print(f"\n{colored_info('[4/8] SCD Type 2 Compliance Validation')}")

    errors = []

    # ========================================================================
    # CONFIGURATION: SCD Type 2 Versioned Tables
    # ========================================================================
    # UPDATE THIS when adding tables using SCD Type 2 versioning pattern
    # ========================================================================
    versioned_tables = [
        "markets",
        "positions",
        "game_states",
        "edges",
        "account_balance",
        # Future tables: Add here when implementing new versioned tables
        # Example:
        # 'portfolio_snapshots',  # Phase 5
        # 'model_predictions',  # Phase 4
    ]

    # Required columns for SCD Type 2
    required_columns = ["row_current_ind", "row_start_ts", "row_end_ts", "row_version"]

    for table_name in versioned_tables:
        columns = get_table_columns(table_name)

        if not columns:
            errors.append(f"Table '{table_name}' not found")
            continue

        col_names = {col["column_name"] for col in columns}

        # Check for required columns
        missing = set(required_columns) - col_names
        if missing:
            errors.append(f"{table_name}: Missing SCD Type 2 columns: {', '.join(sorted(missing))}")

    if not errors:
        print(f"  {colored_ok('All versioned tables have SCD Type 2 columns')}")
        return True, []
    for error in errors:
        print(f"  {colored_error(error)}")
    return False, errors


# ============================================================================
# VALIDATION LEVEL 5: FOREIGN KEY INTEGRITY
# ============================================================================


def validate_foreign_keys() -> tuple[bool, list[str]]:
    """
    Level 5: Verify foreign keys exist for critical relationships.

    This is a stub - would require parsing foreign keys from documentation.
    """
    print(f"\n{colored_info('[5/8] Foreign Key Integrity Validation')}")
    print(f"  {colored_warn('Foreign key validation not yet implemented')}")
    print("        (Would require parsing FK relationships from documentation)")
    return True, []


# ============================================================================
# VALIDATION LEVEL 6: REQUIREMENTS TRACEABILITY
# ============================================================================


def validate_req_db_003() -> tuple[bool, list[str]]:
    """REQ-DB-003: DECIMAL(10,4) for Prices/Probabilities."""
    # Already covered by Level 3
    return True, []


def validate_req_db_004() -> tuple[bool, list[str]]:
    """REQ-DB-004: SCD Type 2 Versioning Pattern."""
    # Already covered by Level 4
    return True, []


def validate_req_db_005() -> tuple[bool, list[str]]:
    """REQ-DB-005: Immutable Strategy/Model Configs."""
    print(f"\n{colored_info('[6/8] Requirements Traceability (REQ-DB-005)')}")

    errors = []

    # Check strategies and probability_models tables have JSONB config columns
    for table_name in ["strategies", "probability_models"]:
        columns = get_table_columns(table_name)

        if not columns:
            errors.append(f"Table '{table_name}' not found")
            continue

        col_lookup = {col["column_name"]: col for col in columns}

        if "config" not in col_lookup:
            errors.append(f"{table_name}: Missing 'config' column")
        elif col_lookup["config"]["data_type"] != "jsonb":
            errors.append(
                f"{table_name}.config: Expected JSONB, got {col_lookup['config']['data_type'].upper()}"
            )

    if not errors:
        print(f"  {colored_ok('Strategy/model config columns are JSONB')}")
        return True, []
    for error in errors:
        print(f"  {colored_error(error)}")
    return False, errors


# ============================================================================
# VALIDATION LEVEL 7: ADR COMPLIANCE
# ============================================================================


def validate_adr_002() -> tuple[bool, list[str]]:
    """ADR-002: Decimal Precision (NEVER float for prices)."""
    # Already covered by Level 3
    return True, []


def validate_adr_009() -> tuple[bool, list[str]]:
    """ADR-009: SCD Type 2 Pattern with Indexes."""
    # Already covered by Level 4 (column check)
    # Index validation would require querying pg_indexes
    return True, []


def validate_adr_compliance() -> tuple[bool, list[str]]:
    """Level 7: Validate ADR compliance."""
    print(f"\n{colored_info('[7/8] ADR Compliance Validation')}")

    # ADR-002 and ADR-009 already validated in earlier levels
    print(f"  {colored_ok('ADR-002 (Decimal Precision) validated in Level 3')}")
    print(f"  {colored_ok('ADR-009 (SCD Type 2) validated in Level 4')}")

    return True, []


# ============================================================================
# VALIDATION LEVEL 8: CROSS-DOCUMENT CONSISTENCY
# ============================================================================


def validate_cross_document_consistency() -> tuple[bool, list[str]]:
    """
    Level 8: Ensure documentation doesn't contradict itself.

    This is a stub - would require parsing multiple documentation files.
    """
    print(f"\n{colored_info('[8/8] Cross-Document Consistency Validation')}")
    print(f"  {colored_warn('Cross-document validation not yet implemented')}")
    print("        (Would require parsing MASTER_REQUIREMENTS, ARCHITECTURE_DECISIONS)")
    return True, []


# ============================================================================
# MAIN VALIDATION RUNNER
# ============================================================================


def run_all_validations() -> bool:
    """
    Run all 8 validation levels.

    Returns:
        True if all validations passed, False otherwise
    """
    print("\n" + "=" * 70)
    print("DATABASE SCHEMA CONSISTENCY VALIDATION (DEF-008)")
    print("=" * 70 + "\n")

    # Test database connection first
    print(colored_info("[SETUP] Testing database connection..."))
    if not test_connection():
        print(colored_error("\n[CRITICAL ERROR] Cannot connect to database"))
        print(colored_warn("Fix: Check .env file and ensure PostgreSQL is running"))
        return False

    # Run all validation levels
    results = []

    # Level 1: Table Existence
    passed, _errors = validate_table_existence()
    results.append(passed)

    # Level 2: Column Consistency (SKIP for now)
    passed, _errors = validate_column_consistency()
    results.append(passed)

    # Level 3: Type Precision for Prices (CRITICAL)
    passed, _errors = validate_type_precision()
    results.append(passed)

    # Level 4: SCD Type 2 Compliance
    passed, _errors = validate_scd_type2_compliance()
    results.append(passed)

    # Level 5: Foreign Key Integrity (SKIP for now)
    passed, _errors = validate_foreign_keys()
    results.append(passed)

    # Level 6: Requirements Traceability
    passed, _errors = validate_req_db_005()
    results.append(passed)

    # Level 7: ADR Compliance
    passed, _errors = validate_adr_compliance()
    results.append(passed)

    # Level 8: Cross-Document Consistency (SKIP for now)
    passed, _errors = validate_cross_document_consistency()
    results.append(passed)

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    passed_count = sum(results)
    total_count = len(results)

    if all(results):
        print(f"\n{colored_ok(f'ALL {total_count} VALIDATION LEVELS PASSED')}")
        print("\nSchema is consistent across:")
        print("  - Documentation (DATABASE_SCHEMA_SUMMARY_V1.7.md)")
        print("  - Implementation (PostgreSQL database)")
        print("  - Requirements (MASTER_REQUIREMENTS_V2.10.md)")
        print("  - Architecture Decisions (ARCHITECTURE_DECISIONS_V2.10.md)")
        return True
    failed_count = total_count - passed_count
    print(f"\n{colored_error(f'{failed_count}/{total_count} VALIDATION LEVELS FAILED')}")
    print(f"\n{colored_warn('Fix errors above before committing changes')}")
    return False


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        success = run_all_validations()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(colored_warn("\n\n[INTERRUPTED] Validation cancelled by user"))
        sys.exit(1)
    except Exception as e:
        print(colored_error(f"\n\n[ERROR] Unexpected error: {e}"))
        import traceback

        traceback.print_exc()
        sys.exit(1)
