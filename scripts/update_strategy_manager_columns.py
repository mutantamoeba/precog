"""Update strategy_manager.py to use strategy_type instead of approach.

This script updates:
1. Function parameter: approach -> strategy_type
2. SQL queries: approach column -> strategy_type
3. Docstrings and comments
4. Variable names

Part of Migration 021 (strategies.approach -> strategy_type)
"""

import re

file_path = "src/precog/trading/strategy_manager.py"

# Read the file
with open(file_path, encoding="utf-8") as f:
    content = f.read()

# Replacements (order matters!)
replacements = [
    # 1. Function parameter
    (r"(\s+)approach: str,", r"\1strategy_type: str,"),
    # 2. SQL columns in queries (preserve indentation/formatting)
    (r"(['\"])approach(['\"])", r"\1strategy_type\2"),  # In RETURNING clauses
    (r"(\s+)approach,", r"\1strategy_type,"),  # In column lists
    (r"(\s+)approach\n", r"\1strategy_type\n"),  # End of line
    # 3. Docstring parameters
    (r"approach: HOW strategy works", "strategy_type: HOW strategy works"),
    (r'approach="entry"', 'strategy_type="entry"'),
    # 4. Comments (update schema references from V1.9 to V1.10)
    (
        r"DATABASE_SCHEMA_SUMMARY_V1\.9\.md \(strategies table with approach/domain fields\)",
        "DATABASE_SCHEMA_SUMMARY_V1.10.md (strategies table with strategy_type/domain fields)",
    ),
]

# Apply all replacements
for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content)

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("[OK] Updated", file_path)
print("Changes:")
print("  - Function parameter: approach to strategy_type")
print("  - SQL columns: approach to strategy_type")
print("  - Docstrings and examples updated")
print("  - Schema reference: V1.9 to V1.10")
