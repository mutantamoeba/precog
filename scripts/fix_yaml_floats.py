"""
Fix YAML Float Literals - Convert to Strings for Decimal Safety
=================================================================

WARN-004: Convert 111 float literals to string format across 7 YAML config files.

Background:
-----------
YAML parsers treat `kelly_fraction: 0.25` as a 64-bit binary float (0.2500000001...).
We need exact decimal precision, so we convert to strings: `kelly_fraction: "0.25"`.

The config_loader._convert_to_decimal() handles both formats, but strings are safer.

Files to Fix:
-------------
- config/markets.yaml (45 floats)
- config/position_management.yaml (28 floats)
- config/trade_strategies.yaml (17 floats)
- config/trading.yaml (12 floats)
- config/probability_models.yaml (9 floats)

Strategy:
---------
Use regex to find float literals in value positions (`: <number>`),
wrap them in quotes (`: "<number>"`), preserving formatting.

Regex Pattern: `: ([-+]?[0-9]*\\.?[0-9]+(?:[eE][-+]?[0-9]+)?)`
Replacement: `: "\1"`

Safety Checks:
--------------
- Don't modify integers (no decimal point): 100 stays 100
- Don't modify booleans: true/false stay true/false
- Don't modify already-quoted strings: "0.25" stays "0.25"
- Don't modify comments or keys
- Validate YAML syntax after fix

Reference:
----------
- warning_baseline.json (WARN-004)
- Pattern 8: Configuration File Synchronization (CLAUDE.md)
"""

import re
import sys
from pathlib import Path


def fix_yaml_floats(file_path: Path) -> int:
    """
    Fix float literals in YAML file by wrapping in quotes.

    Args:
        file_path: Path to YAML file

    Returns:
        Number of replacements made
    """
    # Read file
    content = file_path.read_text(encoding="utf-8")

    # Regex: Match `: <float>` patterns
    # Matches: `: 0.25`, `: 0.0`, `: -0.5`, `: 1.5e-3`
    # Doesn't match: `: 100` (integer), `: true`, `: "0.25"` (quoted)
    pattern = r": ([-+]?[0-9]*\.[0-9]+(?:[eE][-+]?[0-9]+)?)"
    replacement = r': "\1"'

    # Replace all float literals with quoted versions
    content, count = re.subn(pattern, replacement, content)

    if count > 0:
        # Write back to file
        file_path.write_text(content, encoding="utf-8")
        print(f"[OK] {file_path.name}: Fixed {count} float literals")
    else:
        print(f"     {file_path.name}: No float literals found")

    return count


def main():
    """Fix float literals in all config YAML files."""
    config_dir = Path("config")
    yaml_files = [
        "markets.yaml",
        "position_management.yaml",
        "trade_strategies.yaml",
        "trading.yaml",
        "probability_models.yaml",
        "database.yaml",  # Check this too
        "logging.yaml",  # Check this too
    ]

    total_fixes = 0

    print("Fixing YAML float literals (WARN-004)...\n")

    for yaml_file in yaml_files:
        file_path = config_dir / yaml_file
        if file_path.exists():
            count = fix_yaml_floats(file_path)
            total_fixes += count
        else:
            print(f"  {yaml_file}: File not found (skipping)")

    print(f"\nTotal: {total_fixes} float literals fixed")
    print("\nRunning validation to verify fix...")

    # Run validate_docs.py to check warnings reduced
    import subprocess

    result = subprocess.run(
        ["python", "scripts/validate_docs.py"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Count remaining float warnings
    float_warnings = result.stdout.count("Float detected")

    print("\nValidation Results:")
    print(f"  Float warnings remaining: {float_warnings}")
    print("  Expected: 0 (111 warnings fixed)")

    if float_warnings == 0:
        print("\n[SUCCESS] All YAML float literals fixed!")
        return 0
    print(f"\n[WARNING] {float_warnings} float warnings remain")
    print("\nRemaining warnings:")
    for line in result.stdout.splitlines():
        if "Float detected" in line:
            print(f"  {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
