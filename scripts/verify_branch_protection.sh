#!/bin/bash
# Branch Protection Verification Script
#
# Purpose: Verify GitHub branch protection rules are configured correctly for main branch
# Related: ADR-054 (Branch Protection Strategy), DEF-003, REQ-CICD-003
# Phase: 1.5 (Verification Infrastructure)
#
# This script validates that the 6 required CI status checks are configured in branch protection:
# 1. Pre-commit Validation
# 2. Tests (ubuntu-latest, 3.12)
# 3. Tests (ubuntu-latest, 3.13)
# 4. Tests (windows-latest, 3.12)
# 5. Tests (windows-latest, 3.13)
# 6. Security Scanning (Ruff & Safety)
#
# Usage: ./scripts/verify_branch_protection.sh
# Requirements: GitHub CLI (gh) installed and authenticated
# Exit Codes: 0 = all checks configured, 1 = missing checks or errors

set -e  # Exit on error

echo "========================================="
echo "Branch Protection Verification"
echo "========================================="
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "[FAIL] GitHub CLI (gh) not installed"
    echo ""
    echo "Install instructions:"
    echo "  Windows: winget install GitHub.cli"
    echo "  Mac: brew install gh"
    echo "  Linux: https://github.com/cli/cli/blob/trunk/docs/install_linux.md"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "[FAIL] GitHub CLI not authenticated"
    echo ""
    echo "Run: gh auth login"
    exit 1
fi

echo "[OK] GitHub CLI installed and authenticated"
echo ""

# Define required status checks (must match .github/workflows/ci.yml job names)
REQUIRED_CHECKS=(
    "pre-commit-checks"
    "test (ubuntu-latest, 3.12)"
    "test (ubuntu-latest, 3.13)"
    "test (windows-latest, 3.12)"
    "test (windows-latest, 3.13)"
    "security-scan"
)

echo "Fetching branch protection configuration for 'main' branch..."
echo ""

# Fetch branch protection configuration
PROTECTION_JSON=$(gh api repos/:owner/:repo/branches/main/protection 2>&1) || {
    echo "[FAIL] Could not fetch branch protection configuration"
    echo ""
    echo "Error details:"
    echo "$PROTECTION_JSON"
    echo ""
    echo "Possible causes:"
    echo "  - Branch protection not configured"
    echo "  - Insufficient permissions"
    echo "  - Repository not found"
    exit 1
}

# Extract required status checks
CONFIGURED_CHECKS=$(echo "$PROTECTION_JSON" | jq -r '.required_status_checks.contexts[]? // empty' 2>/dev/null) || {
    echo "[WARN] Branch protection exists but required status checks not configured"
    echo ""
    echo "To configure, run:"
    echo "  gh api repos/:owner/:repo/branches/main/protection/required_status_checks \\"
    echo "    -X PATCH \\"
    echo "    -f contexts[]='pre-commit-checks' \\"
    echo "    -f contexts[]='test (ubuntu-latest, 3.12)' \\"
    echo "    -f contexts[]='test (ubuntu-latest, 3.13)' \\"
    echo "    -f contexts[]='test (windows-latest, 3.12)' \\"
    echo "    -f contexts[]='test (windows-latest, 3.13)' \\"
    echo "    -f contexts[]='security-scan'"
    exit 1
}

# Verify each required check is configured
MISSING_CHECKS=()
echo "Checking required status checks:"
echo ""

for check in "${REQUIRED_CHECKS[@]}"; do
    if echo "$CONFIGURED_CHECKS" | grep -Fxq "$check"; then
        echo "  [OK] $check"
    else
        echo "  [FAIL] $check - NOT CONFIGURED"
        MISSING_CHECKS+=("$check")
    fi
done

echo ""

# Check for extra configured checks (informational only)
EXTRA_CHECKS=()
while IFS= read -r configured_check; do
    found=false
    for required_check in "${REQUIRED_CHECKS[@]}"; do
        if [[ "$configured_check" == "$required_check" ]]; then
            found=true
            break
        fi
    done
    if ! $found; then
        EXTRA_CHECKS+=("$configured_check")
    fi
done <<< "$CONFIGURED_CHECKS"

if [ ${#EXTRA_CHECKS[@]} -gt 0 ]; then
    echo "Extra configured checks (not required but acceptable):"
    for check in "${EXTRA_CHECKS[@]}"; do
        echo "  [INFO] $check"
    done
    echo ""
fi

# Report results
echo "========================================="
echo "Verification Summary"
echo "========================================="
echo ""

if [ ${#MISSING_CHECKS[@]} -eq 0 ]; then
    echo "[PASS] All 6 required status checks configured correctly"
    echo ""
    echo "Branch protection is active with:"
    echo "  - ${#REQUIRED_CHECKS[@]} required status checks"
    if [ ${#EXTRA_CHECKS[@]} -gt 0 ]; then
        echo "  - ${#EXTRA_CHECKS[@]} additional status checks"
    fi
    exit 0
else
    echo "[FAIL] ${#MISSING_CHECKS[@]} required status check(s) missing"
    echo ""
    echo "Missing checks:"
    for check in "${MISSING_CHECKS[@]}"; do
        echo "  - $check"
    done
    echo ""
    echo "To add missing checks, use:"
    echo "  gh api repos/:owner/:repo/branches/main/protection/required_status_checks -X PATCH \\"
    for check in "${MISSING_CHECKS[@]}"; do
        echo "    -f contexts[]='$check' \\"
    done
    echo ""
    exit 1
fi
