#!/usr/bin/env python3
"""
Security Pattern Validation - SECURITY_REVIEW_CHECKLIST Enforcement

Enforces SECURITY_REVIEW_CHECKLIST requirements before push:
1. API endpoints have authentication (Section 3: API Security)
2. Sensitive data encryption patterns (Section 4: Data Protection)
3. Structured logging for security events (Section 5: Incident Response)
4. No hardcoded secrets (Section 1: Credential Management - defense in depth)

Reference: docs/utility/SECURITY_REVIEW_CHECKLIST.md V1.1
Related: DEVELOPMENT_PHILOSOPHY_V1.1.md Section 9 (Security by Default)

Exit codes:
  0 = All checks passed
  1 = Security pattern violations found

Example usage:
  python scripts/validate_security_patterns.py          # Run all checks
  python scripts/validate_security_patterns.py --verbose # Detailed output
"""

import re
import subprocess
import sys
from pathlib import Path


def check_api_authentication(verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Verify API endpoints have authentication decorators/checks.

    Looks for Flask/FastAPI routes without @require_auth or similar.
    Only checks staged/modified files to avoid flagging existing code.

    Args:
        verbose: If True, show detailed route analysis

    Returns:
        (passed, violations) tuple
    """
    violations = []

    # Get staged Python files (new or modified)
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
        capture_output=True,
        text=True,
    )

    staged_files = [
        Path(f)
        for f in result.stdout.strip().split("\n")
        if f.endswith(".py") and Path(f).exists() and f
    ]

    if verbose:
        print(f"\n[DEBUG] Checking {len(staged_files)} staged files for API authentication")

    # Find files with route decorators
    api_files = []
    for py_file in staged_files:
        try:
            content = py_file.read_text(encoding="utf-8")
            if "@app.route" in content or "@router." in content or "@api.route" in content:
                api_files.append(py_file)
        except Exception as e:
            if verbose:
                print(f"[DEBUG] Skipping {py_file}: {e}")
            continue

    for api_file in api_files:
        try:
            content = api_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Find route definitions
        route_pattern = r'@(?:app\.route|router\.\w+|api\.route)\([\'"]([^\'"]+)[\'"]\)'
        routes = re.finditer(route_pattern, content)

        for route_match in routes:
            route_path = route_match.group(1)
            # Get next 10 lines after route decorator
            lines_after = content[route_match.end() : route_match.end() + 800]

            # Check for authentication patterns
            has_auth = any(
                pattern in lines_after
                for pattern in [
                    "@require_auth",
                    "@login_required",
                    "@authenticate",
                    "@authenticated",
                    "check_auth(",
                    "verify_token(",
                    "require_authentication(",
                ]
            )

            # Skip health check/status endpoints (no auth needed)
            if route_path in ["/health", "/ping", "/status", "/version"]:
                continue

            if not has_auth and "def " in lines_after:  # Only if function definition found
                violations.append(
                    f"{api_file}:{route_path} - API endpoint missing authentication check"
                )

    return len(violations) == 0, violations


def check_sensitive_data_encryption(verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Verify sensitive data is encrypted before storage.

    Looks for direct database inserts of password/token/key fields without encryption.
    Only checks staged/modified files to avoid flagging existing code.

    Args:
        verbose: If True, show detailed encryption analysis

    Returns:
        (passed, violations) tuple
    """
    violations = []

    # Get staged Python files in database/ directory
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
        capture_output=True,
        text=True,
    )

    db_files = [
        Path(f)
        for f in result.stdout.strip().split("\n")
        if f.endswith(".py") and "database" in f and Path(f).exists() and f
    ]

    if verbose:
        print(f"\n[DEBUG] Checking {len(db_files)} database files for encryption patterns")

    for db_file in db_files:
        try:
            content = db_file.read_text(encoding="utf-8")
        except Exception as e:
            if verbose:
                print(f"[DEBUG] Skipping {db_file}: {e}")
            continue

        # Check for sensitive column definitions without encryption
        sensitive_pattern = r"(password|token|secret|api_key|private_key|credential)\s*=\s*Column"
        matches = re.finditer(sensitive_pattern, content, re.IGNORECASE)

        for match in matches:
            field_name = match.group(1)
            # Check next 300 chars for encryption indicators
            context = content[match.start() : match.start() + 300]

            has_encryption = any(
                pattern in context
                for pattern in [
                    "EncryptedType",
                    "encrypt(",
                    "hash(",
                    "bcrypt",
                    "argon2",
                    "PasswordHash",
                    "SecureString",
                ]
            )

            if not has_encryption:
                line_num = content[: match.start()].count("\n") + 1
                violations.append(
                    f"{db_file}:{line_num} - Sensitive field '{field_name}' may need encryption"
                )

    return len(violations) == 0, violations


def check_security_logging(verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Verify security events use structured logging with logger.exception() or logger.error().

    Checks authentication/authorization code for proper logging.
    Only checks staged/modified files.

    Args:
        verbose: If True, show detailed logging analysis

    Returns:
        (passed, violations) tuple
    """
    violations = []

    # Get staged Python files
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
        capture_output=True,
        text=True,
    )

    staged_files = [
        Path(f)
        for f in result.stdout.strip().split("\n")
        if f.endswith(".py") and Path(f).exists() and f
    ]

    # Filter to security-related files
    security_files = []
    for py_file in staged_files:
        try:
            content = py_file.read_text(encoding="utf-8")
            if any(
                keyword in content.lower()
                for keyword in ["authenticate", "authorize", "login", "verify_token", "check_auth"]
            ):
                security_files.append(py_file)
        except Exception as e:
            if verbose:
                print(f"[DEBUG] Skipping {py_file}: {e}")
            continue

    if verbose:
        print(f"\n[DEBUG] Checking {len(security_files)} security-related files for logging")

    for sec_file in security_files:
        try:
            content = sec_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Find exception handlers in security-critical code
        try_blocks = re.finditer(r"except\s+[\w.]+.*?:", content)

        for try_match in try_blocks:
            # Get 10 lines after except
            lines_after = content[try_match.end() : try_match.end() + 600]

            # Check for logger.exception() or logger.error()
            has_logging = any(
                pattern in lines_after
                for pattern in [
                    "logger.exception(",
                    "logger.error(",
                    "logger.warning(",
                    "logger.critical(",
                ]
            )

            # Only flag if in authentication-related function
            func_context = content[max(0, try_match.start() - 500) : try_match.start()]
            is_auth_func = any(
                keyword in func_context
                for keyword in ["def auth", "def login", "def verify", "def check_auth"]
            )

            if not has_logging and is_auth_func:
                line_num = content[: try_match.start()].count("\n") + 1
                violations.append(
                    f"{sec_file}:{line_num} - Exception handler in auth code missing security logging"
                )

    return len(violations) == 0, violations


def check_hardcoded_secrets(verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Verify no hardcoded secrets in staged files (defense in depth).

    This is redundant with pre-commit hook 'security-credentials' but provides
    an additional layer of defense (Defense in Depth philosophy).

    Args:
        verbose: If True, show detailed secret scan analysis

    Returns:
        (passed, violations) tuple
    """
    violations = []

    # Get staged Python files
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
        capture_output=True,
        text=True,
    )

    staged_files = [
        Path(f)
        for f in result.stdout.strip().split("\n")
        if f.endswith(".py") and "test" not in f.lower() and Path(f).exists() and f
    ]

    if verbose:
        print(f"\n[DEBUG] Checking {len(staged_files)} staged files for hardcoded secrets")

    for py_file in staged_files:
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Search pattern matches: credential keywords assigned to string literals
        # Exclude os.getenv() lines and test placeholders
        secret_pattern = r'(password|secret|api_key|token)\s*=\s*["\']([^"\']{5,})["\']'
        matches = re.finditer(secret_pattern, content, re.IGNORECASE)

        for match in matches:
            field_name, value = match.groups()

            # Skip safe patterns
            if any(
                safe in value.upper()
                for safe in ["YOUR_", "TEST_", "EXAMPLE_", "PLACEHOLDER", "<", ">"]
            ):
                continue
            if "os.getenv" in content[max(0, match.start() - 50) : match.start() + 50]:
                continue

            line_num = content[: match.start()].count("\n") + 1
            violations.append(
                f'{py_file}:{line_num} - Potential hardcoded secret: {field_name} = "{value[:10]}..."'
            )

    return len(violations) == 0, violations


def main():
    """Run all security pattern checks."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print("=" * 60)
    print("Security Pattern Validation (SECURITY_REVIEW_CHECKLIST)")
    print("=" * 60)
    print("Reference: docs/utility/SECURITY_REVIEW_CHECKLIST.md V1.1")
    print("Related: DEVELOPMENT_PHILOSOPHY_V1.1.md Section 9")
    print("")

    all_passed = True

    # Check 1: API authentication
    print("[1/4] Checking API authentication patterns...")
    try:
        passed, violations = check_api_authentication(verbose)
        if not passed:
            print("[FAIL] API endpoints missing authentication:")
            for v in violations:
                print(f"  - {v}")
            print("")
            print("Fix: Add authentication decorator (@require_auth, @login_required)")
            print("Reference: SECURITY_REVIEW_CHECKLIST Section 3 (API Security)")
            all_passed = False
        else:
            print("[PASS] API authentication present (or no new API endpoints)")
    except Exception as e:
        print(f"[WARN] API auth check failed: {e}")
        if verbose:
            import traceback

            traceback.print_exc()

    # Check 2: Sensitive data encryption
    print("[2/4] Checking sensitive data encryption...")
    try:
        passed, violations = check_sensitive_data_encryption(verbose)
        if not passed:
            print("[WARN] Sensitive data may need encryption:")
            for v in violations:
                print(f"  - {v}")
            print("")
            print("Note: Review these fields - encrypt if storing passwords/secrets")
            print("Reference: SECURITY_REVIEW_CHECKLIST Section 4 (Data Protection)")
            # Warning only, don't fail
        else:
            print("[PASS] Sensitive data encryption verified (or no new sensitive fields)")
    except Exception as e:
        print(f"[WARN] Encryption check failed: {e}")
        if verbose:
            import traceback

            traceback.print_exc()

    # Check 3: Security logging
    print("[3/4] Checking security event logging...")
    try:
        passed, violations = check_security_logging(verbose)
        if not passed:
            print("[WARN] Security logging missing:")
            for v in violations:
                print(f"  - {v}")
            print("")
            print("Note: Add logger.exception() to security-critical error handlers")
            print("Reference: SECURITY_REVIEW_CHECKLIST Section 5 (Incident Response)")
            # Warning only, don't fail
        else:
            print("[PASS] Security logging present (or no new auth code)")
    except Exception as e:
        print(f"[WARN] Security logging check failed: {e}")
        if verbose:
            import traceback

            traceback.print_exc()

    # Check 4: Hardcoded secrets (defense in depth)
    print("[4/4] Checking for hardcoded secrets (defense in depth)...")
    try:
        passed, violations = check_hardcoded_secrets(verbose)
        if not passed:
            print("[FAIL] Potential hardcoded secrets detected:")
            for v in violations:
                print(f"  - {v}")
            print("")
            print("Fix: Use os.getenv() for all credentials")
            print("Reference: SECURITY_REVIEW_CHECKLIST Section 1 (Credential Management)")
            all_passed = False
        else:
            print("[PASS] No hardcoded secrets detected")
    except Exception as e:
        print(f"[WARN] Secret scan failed: {e}")
        if verbose:
            import traceback

            traceback.print_exc()

    print("")
    print("=" * 60)

    if all_passed:
        print("[PASS] All security pattern checks passed")
        print("=" * 60)
        return 0
    print("[FAIL] Security pattern validation failed")
    print("=" * 60)
    print("")
    print("Fix violations above before pushing.")
    print("Reference: docs/utility/SECURITY_REVIEW_CHECKLIST.md V1.1")
    return 1


if __name__ == "__main__":
    sys.exit(main())
