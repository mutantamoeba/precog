#!/usr/bin/env bash
#
# reconcile_issue_tracking.sh
#
# Purpose: Reconcile GitHub issue status with documentation status
#
# Checks for discrepancies between:
# - GitHub Issues (actual state)
# - PHASE_1_PR_REVIEW_DEFERRED_TASKS_V1.0.md (documented state)
#
# Exit codes:
#   0 - All issues synchronized (GitHub state matches documentation)
#   1 - Discrepancies found (requires manual reconciliation)
#
# Usage:
#   bash scripts/reconcile_issue_tracking.sh
#
# Educational Note:
#   This script addresses the workflow gap where issues are closed in GitHub
#   without updating documentation, or vice versa. It's part of the Phase
#   Completion Assessment Protocol to ensure documentation remains current.
#
# Reference:
#   - CLAUDE.md V1.18 - Issue Closure Protocol
#   - PHASE_COMPLETION_ASSESSMENT_PROTOCOL_V1.0.md
#
# Dependencies:
#   - GitHub CLI (gh): Required for fetching issue data
#     Installation:
#       Windows: winget install GitHub.cli
#       macOS:   brew install gh
#       Linux:   See https://cli.github.com/ for distribution-specific instructions
#     Authentication:
#       Run 'gh auth login' before first use
#     Verification:
#       gh --version (should show: gh version 2.x.x)
#
#   Note: Script will exit with error code 1 if gh CLI not installed.
#         See docs/guides/DEVELOPER_SETUP_GUIDE_V1.0.md for full setup instructions.
#
# Example Output:
#   Issue Tracking Reconciliation Report
#   =====================================
#
#   Closed in GitHub, Open in Docs:
#   - #29: DEF-P1-001 (Float usage in calculations)
#   - #31: DEF-P1-003 (Path sanitization)
#
#   Open in GitHub, Closed in Docs:
#   - #37: DEF-P1-009 (Add retry logic)
#
#   Result: DISCREPANCIES FOUND (2 issues require reconciliation)

set -euo pipefail

# Colors for output (ASCII-safe for Windows compatibility)
readonly RED='[ERROR]'
readonly GREEN='[OK]'
readonly YELLOW='[WARN]'
readonly BLUE='[INFO]'

# File paths
readonly DEFERRED_TASKS_DOC="docs/utility/PHASE_1_PR_REVIEW_DEFERRED_TASKS_V1.0.md"
readonly TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# Output files
readonly GITHUB_ISSUES_FILE="$TEMP_DIR/github_issues.txt"
readonly DOC_STATUS_FILE="$TEMP_DIR/doc_status.txt"
readonly REPORT_FILE="$TEMP_DIR/reconciliation_report.md"

# Counters
DISCREPANCIES_FOUND=0

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo "$BLUE $1"
}

log_success() {
    echo "$GREEN $1"
}

log_warning() {
    echo "$YELLOW $1"
}

log_error() {
    echo "$RED $1"
}

# ============================================================================
# Step 1: Fetch GitHub Issue Status
# ============================================================================

fetch_github_issues() {
    log_info "Fetching GitHub issues with 'deferred-task' label..."

    # Check if gh CLI is available
    if ! command -v gh &> /dev/null; then
        log_error "GitHub CLI (gh) not found. Install from: https://cli.github.com/"
        exit 1
    fi

    # Fetch all issues with deferred-task label (both open and closed)
    gh issue list --label deferred-task --state all --limit 100 --json number,title,state \
        --jq '.[] | "\(.number)|\(.state)|\(.title)"' > "$GITHUB_ISSUES_FILE"

    local issue_count=$(wc -l < "$GITHUB_ISSUES_FILE")
    log_success "Found $issue_count issues with 'deferred-task' label"
}

# ============================================================================
# Step 2: Parse Documentation Status
# ============================================================================

parse_documentation_status() {
    log_info "Parsing documentation status from $DEFERRED_TASKS_DOC..."

    # Check if documentation file exists
    if [[ ! -f "$DEFERRED_TASKS_DOC" ]]; then
        log_error "Documentation file not found: $DEFERRED_TASKS_DOC"
        exit 1
    fi

    # Extract issue status from documentation
    # Look for patterns like:
    # - **Status:** Open / Complete
    # - Issue #XX: ... (Status: Open/Complete)
    # - [#XX](link) - Status: Open/Complete

    # This is a simplified parser - adjust regex based on actual doc format
    grep -E "(Issue #[0-9]+|#[0-9]+.*Status)" "$DEFERRED_TASKS_DOC" | \
        sed -E 's/.*#([0-9]+).*Status:?\s*(Open|Complete|Closed).*/\1|\2/g' | \
        sort -u > "$DOC_STATUS_FILE" || true

    local doc_count=$(wc -l < "$DOC_STATUS_FILE")
    log_success "Found $doc_count issues documented"
}

# ============================================================================
# Step 3: Compare and Report Discrepancies
# ============================================================================

compare_and_report() {
    log_info "Comparing GitHub state with documentation state..."

    # Initialize report
    {
        echo "# Issue Tracking Reconciliation Report"
        echo ""
        echo "**Date:** $(date +%Y-%m-%d)"
        echo "**Documentation:** $DEFERRED_TASKS_DOC"
        echo ""
        echo "---"
        echo ""
    } > "$REPORT_FILE"

    # Arrays to store discrepancies
    local closed_in_github_open_in_docs=()
    local open_in_github_closed_in_docs=()

    # Parse GitHub issues
    while IFS='|' read -r issue_num github_state issue_title; do
        # Look for this issue in documentation
        local doc_status=""
        if grep -q "^${issue_num}|" "$DOC_STATUS_FILE" 2>/dev/null; then
            doc_status=$(grep "^${issue_num}|" "$DOC_STATUS_FILE" | cut -d'|' -f2)
        else
            # Issue not found in documentation
            log_warning "Issue #$issue_num not found in documentation"
            continue
        fi

        # Normalize states
        github_state_normalized="${github_state^^}"  # Convert to uppercase
        doc_status_normalized="${doc_status^^}"

        # Check for discrepancies
        if [[ "$github_state_normalized" == "CLOSED" ]] && [[ "$doc_status_normalized" == "OPEN" ]]; then
            closed_in_github_open_in_docs+=("#$issue_num: $issue_title")
            ((DISCREPANCIES_FOUND++))
        elif [[ "$github_state_normalized" == "OPEN" ]] && [[ "$doc_status_normalized" =~ ^(COMPLETE|CLOSED)$ ]]; then
            open_in_github_closed_in_docs+=("#$issue_num: $issue_title")
            ((DISCREPANCIES_FOUND++))
        fi
    done < "$GITHUB_ISSUES_FILE"

    # Generate report sections
    {
        echo "## Discrepancies Found: $DISCREPANCIES_FOUND"
        echo ""

        if [[ ${#closed_in_github_open_in_docs[@]} -gt 0 ]]; then
            echo "### Closed in GitHub, Open in Documentation"
            echo ""
            echo "**Action Required:** Update documentation to mark as Complete"
            echo ""
            for issue in "${closed_in_github_open_in_docs[@]}"; do
                echo "- $issue"
            done
            echo ""
        fi

        if [[ ${#open_in_github_closed_in_docs[@]} -gt 0 ]]; then
            echo "### Open in GitHub, Closed in Documentation"
            echo ""
            echo "**Action Required:** Either close GitHub issue or update documentation to mark as Open"
            echo ""
            for issue in "${open_in_github_closed_in_docs[@]}"; do
                echo "- $issue"
            done
            echo ""
        fi

        if [[ $DISCREPANCIES_FOUND -eq 0 ]]; then
            echo "### All Issues Synchronized"
            echo ""
            echo "GitHub issue status matches documentation status for all tracked issues."
            echo ""
        fi

        echo "---"
        echo ""
        echo "## Recommendations"
        echo ""
        if [[ $DISCREPANCIES_FOUND -gt 0 ]]; then
            echo "1. Review each discrepancy above"
            echo "2. For closed GitHub issues: Update $DEFERRED_TASKS_DOC to mark as Complete"
            echo "3. For open GitHub issues marked complete: Verify issue was actually resolved, then close GitHub issue"
            echo "4. Re-run this script to verify synchronization"
        else
            echo "No action required. Issue tracking is synchronized."
        fi
        echo ""
    } >> "$REPORT_FILE"

    # Display report
    cat "$REPORT_FILE"
}

# ============================================================================
# Step 4: Exit with Appropriate Code
# ============================================================================

exit_with_status() {
    echo ""
    echo "=========================================="
    if [[ $DISCREPANCIES_FOUND -eq 0 ]]; then
        log_success "RESULT: All issues synchronized"
        echo "=========================================="
        exit 0
    else
        log_error "RESULT: $DISCREPANCIES_FOUND discrepancies found"
        echo "=========================================="
        echo ""
        log_info "Report saved to: $REPORT_FILE"
        log_info "Review discrepancies and update documentation or GitHub issues accordingly."
        exit 1
    fi
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    echo "=========================================="
    echo "Issue Tracking Reconciliation"
    echo "=========================================="
    echo ""

    fetch_github_issues
    parse_documentation_status
    compare_and_report
    exit_with_status
}

# Run main function
main "$@"
