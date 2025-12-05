"""Update model_manager.py to use model_class instead of approach.

This script updates:
1. Function parameter: approach -> model_class
2. SQL queries: approach column -> model_class
3. Docstrings and comments
4. Variable names

Part of Migration 022 (probability_models.approach -> model_class)
"""

import re

file_path = "src/precog/analytics/model_manager.py"

# Read the file
with open(file_path, encoding="utf-8") as f:
    content = f.read()

# Replacements (order matters!)
replacements = [
    # 1. Function parameter
    (r"(\s+)approach: str,", r"\1model_class: str,"),
    (r"approach: str \| None = None", "model_class: str | None = None"),
    # 2. SQL columns in queries (preserve indentation/formatting)
    (r"(['\"])approach(['\"])", r"\1model_class\2"),  # In RETURNING clauses
    (r"(\s+)approach,", r"\1model_class,"),  # In column lists
    (r"(\s+)approach\n", r"\1model_class\n"),  # End of line
    (r"approach =", "model_class ="),  # In WHERE clauses
    # 3. Docstring parameters
    (r"approach: HOW model works", "model_class: HOW model works"),
    (r"approach: Filter by approach", "model_class: Filter by model class"),
    (r"approach='elo'", "model_class='elo'"),
    (r'approach="elo"', 'model_class="elo"'),
    # 4. Comments (update schema references from V1.9 to V1.10)
    (
        r"DATABASE_SCHEMA_SUMMARY_V1\.9\.md \(probability_models table with approach/domain fields\)",
        "DATABASE_SCHEMA_SUMMARY_V1.10.md (probability_models table with model_class/domain fields)",
    ),
]

# Apply all replacements
for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content)

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"[OK] Updated {file_path}")
print("Changes:")
print("  - Function parameter: approach -> model_class")
print("  - SQL columns: approach -> model_class")
print("  - Docstrings and examples updated")
print("  - Schema reference: V1.9 -> V1.10")
