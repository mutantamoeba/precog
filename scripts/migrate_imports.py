"""
Migrate imports to use precog namespace after src/ layout migration.

This script updates all import statements across the codebase to use the
new `precog` package namespace instead of direct module imports.

Educational Note:
    This demonstrates automated refactoring - when making large-scale changes
    like package restructuring, automation prevents human error and ensures
    consistency across dozens of files.

Usage:
    python scripts/migrate_imports.py

Reference:
    docs/utility/PHASE_1_DEFERRED_TASKS_V1.0.md - DEF-P1-010 (src/ layout migration)
"""

import re
from pathlib import Path


def update_imports_in_file(file_path: Path) -> tuple[int, list[str]]:
    """Update imports in a single file to use precog namespace.

    Args:
        file_path: Path to Python file to update

    Returns:
        Tuple of (num_changes, list_of_changes)

    Educational Note:
        We use regex patterns to match import statements. This is safer than
        simple string replacement because it ensures we only match actual
        import statements, not strings or comments that happen to contain
        the module names.
    """
    with open(file_path, encoding="utf-8") as f:
        original_content = f.read()

    content = original_content
    changes = []

    # Pattern 1: from api_connectors... -> from precog.api_connectors...
    # Pattern 2: from database... -> from precog.database...
    # Pattern 3: from config... -> from precog.config...
    # Pattern 4: from utils... -> from precog.utils...
    # Pattern 5: @patch("api_connectors... -> @patch("precog.api_connectors...
    # Pattern 6: @patch("database... -> @patch("precog.database...
    # Pattern 7: @patch("config... -> @patch("precog.config...
    # Pattern 8: @patch("utils... -> @patch("precog.utils...
    # Pattern 9: import api_connectors.X -> import precog.api_connectors.X
    # Pattern 10: import database.X -> import precog.database.X
    # Pattern 11: import config.X -> import precog.config.X
    # Pattern 12: import utils.X -> import precog.utils.X
    patterns = [
        (r"^(\s*)from api_connectors\b", r"\1from precog.api_connectors"),
        (r"^(\s*)from database\b", r"\1from precog.database"),
        (r"^(\s*)from config\b", r"\1from precog.config"),
        (r"^(\s*)from utils\b", r"\1from precog.utils"),
        (r"^(\s*)import api_connectors\.(\w+)", r"\1import precog.api_connectors.\2"),
        (r"^(\s*)import database\.(\w+)", r"\1import precog.database.\2"),
        (r"^(\s*)import config\.(\w+)", r"\1import precog.config.\2"),
        (r"^(\s*)import utils\.(\w+)", r"\1import precog.utils.\2"),
        (r"^(\s*)import api_connectors\b", r"\1import precog.api_connectors"),
        (r"^(\s*)import database\b", r"\1import precog.database"),
        (r"^(\s*)import config\b", r"\1import precog.config"),
        (r"^(\s*)import utils\b", r"\1import precog.utils"),
        (r'"api_connectors\.', '"precog.api_connectors.'),
        (r'"database\.', '"precog.database.'),
        (r'"config\.', '"precog.config.'),
        (r'"utils\.', '"precog.utils.'),
        (r"'api_connectors\.", "'precog.api_connectors."),
        (r"'database\.", "'precog.database."),
        (r"'config\.", "'precog.config."),
        (r"'utils\.", "'precog.utils."),
    ]

    for pattern, replacement in patterns:
        # Use MULTILINE flag so ^ matches start of each line
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        if new_content != content:
            # Count how many times this pattern matched
            num_matches = len(re.findall(pattern, content, flags=re.MULTILINE))
            changes.append(f"{pattern} -> {replacement} ({num_matches} occurrences)")
            content = new_content

    # Only write if changes were made
    if content != original_content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    num_changes = len(changes)
    return num_changes, changes


def migrate_all_imports() -> dict[str, int]:
    """Migrate imports in all Python files.

    Returns:
        Dictionary mapping category to number of files changed

    Educational Note:
        We process files in categories (source, tests, scripts, main.py)
        to track migration progress and provide clear feedback.
    """
    stats = {
        "source_modules": 0,
        "tests": 0,
        "scripts": 0,
        "main_py": 0,
        "total_changes": 0,
    }

    # Category 1: Source modules in src/precog/
    print("\n[1/4] Updating source modules in src/precog/...")
    for py_file in Path("src/precog").rglob("*.py"):
        if py_file.name == "__init__.py" and py_file.parent == Path("src/precog"):
            continue  # Skip top-level __init__.py
        num_changes, changes = update_imports_in_file(py_file)
        if num_changes > 0:
            print(f"  [OK] {py_file.relative_to('src/precog')}: {num_changes} changes")
            for change in changes:
                print(f"    - {change}")
            stats["source_modules"] += 1
            stats["total_changes"] += num_changes

    # Category 2: Tests
    print("\n[2/4] Updating tests/...")
    for py_file in Path("tests").rglob("*.py"):
        num_changes, changes = update_imports_in_file(py_file)
        if num_changes > 0:
            print(f"  [OK] {py_file.relative_to('tests')}: {num_changes} changes")
            for change in changes:
                print(f"    - {change}")
            stats["tests"] += 1
            stats["total_changes"] += num_changes

    # Category 3: Scripts
    print("\n[3/4] Updating scripts/...")
    for py_file in Path("scripts").rglob("*.py"):
        if py_file.name == "migrate_imports.py":
            continue  # Skip this script
        num_changes, changes = update_imports_in_file(py_file)
        if num_changes > 0:
            print(f"  [OK] {py_file.relative_to('scripts')}: {num_changes} changes")
            for change in changes:
                print(f"    - {change}")
            stats["scripts"] += 1
            stats["total_changes"] += num_changes

    # Category 4: main.py (if exists at root)
    print("\n[4/4] Updating main.py...")
    main_py = Path("main.py")
    if main_py.exists():
        num_changes, changes = update_imports_in_file(main_py)
        if num_changes > 0:
            print(f"  [OK] main.py: {num_changes} changes")
            for change in changes:
                print(f"    - {change}")
            stats["main_py"] = 1
            stats["total_changes"] += num_changes

    return stats


def main() -> None:
    """Run import migration and print summary."""
    print("=" * 70)
    print("Import Migration to precog Namespace")
    print("=" * 70)

    stats = migrate_all_imports()

    print("\n" + "=" * 70)
    print("Migration Summary")
    print("=" * 70)
    print(f"Source modules updated: {stats['source_modules']}")
    print(f"Test files updated:     {stats['tests']}")
    print(f"Script files updated:   {stats['scripts']}")
    print(f"main.py updated:        {'Yes' if stats['main_py'] else 'No'}")
    print(f"Total import changes:   {stats['total_changes']}")
    print("=" * 70)

    if stats["total_changes"] > 0:
        print("\n[OK] Migration complete! Next steps:")
        print("   1. Run tests: pytest tests/ -v")
        print("   2. Install package: pip install -e .")
        print("   3. Verify coverage: pytest --cov=precog")
    else:
        print("\n[OK] No changes needed (already migrated or no imports to update)")


if __name__ == "__main__":
    main()
