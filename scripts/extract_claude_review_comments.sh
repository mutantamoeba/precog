#!/usr/bin/env bash
#
# Extract claude-review comments from merged PRs
#
# This script extracts review comments from claude-code[bot] for a range
# of PRs and outputs them in structured format for documentation or
# issue creation.
#
# Usage:
#   bash scripts/extract_claude_review_comments.sh <start_pr> <end_pr> [--format FORMAT]
#
# Arguments:
#   start_pr    First PR number to check
#   end_pr      Last PR number to check
#
# Options:
#   --format FORMAT    Output format: markdown (default), json, csv
#   --output FILE      Output file (default: stdout)
#   --priority LEVEL   Filter by priority: all (default), critical, high, medium, low
#
# Examples:
#   # Extract reviews from PRs 70-85 as markdown
#   bash scripts/extract_claude_review_comments.sh 70 85
#
#   # Extract high-priority reviews as JSON
#   bash scripts/extract_claude_review_comments.sh 70 85 --format json --priority high
#
#   # Save to file
#   bash scripts/extract_claude_review_comments.sh 70 85 --output reviews.md
#
# Output Format (markdown):
#   ## PR #75: Add Kalshi API Client
#   **Priority:** High
#   **Category:** Security
#   **Review Comment:**
#   Add retry logic with exponential backoff for rate limit errors...
#
# Educational Note:
#   This automates the manual review comment extraction from
#   Phase Completion Protocol Step 7 (AI Code Review Analysis).
#
# Reference:
#   CLAUDE.md - Phase Completion Protocol Step 7

set -euo pipefail

# Default values
FORMAT="markdown"
OUTPUT=""
PRIORITY_FILTER="all"

# Color codes
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

# Parse arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <start_pr> <end_pr> [--format FORMAT] [--output FILE] [--priority LEVEL]"
    exit 1
fi

START_PR=$1
END_PR=$2
shift 2

while [[ $# -gt 0 ]]; do
    case $1 in
        --format)
            FORMAT="$2"
            shift 2
            ;;
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        --priority)
            PRIORITY_FILTER="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate format
if [[ ! "$FORMAT" =~ ^(markdown|json|csv)$ ]]; then
    echo "Error: Invalid format '$FORMAT'. Must be: markdown, json, csv"
    exit 1
fi

# Function to categorize review comment
categorize_review() {
    local body="$1"

    # Simple keyword-based categorization
    if echo "$body" | grep -qi "security\|vulnerability\|credential\|XSS\|injection"; then
        echo "Security"
    elif echo "$body" | grep -qi "test\|coverage\|assertion"; then
        echo "Testing"
    elif echo "$body" | grep -qi "performance\|optimize\|slow"; then
        echo "Performance"
    elif echo "$body" | grep -qi "documentation\|comment\|docstring"; then
        echo "Documentation"
    elif echo "$body" | grep -qi "refactor\|complexity\|clean"; then
        echo "Code Quality"
    else
        echo "General"
    fi
}

# Function to extract priority
extract_priority() {
    local body="$1"

    if echo "$body" | grep -qi "critical\|urgent\|security"; then
        echo "Critical"
    elif echo "$body" | grep -qi "important\|should\|recommend"; then
        echo "High"
    elif echo "$body" | grep -qi "consider\|might\|could"; then
        echo "Medium"
    else
        echo "Low"
    fi
}

# Initialize output
if [ "$FORMAT" = "json" ]; then
    echo "["
elif [ "$FORMAT" = "csv" ]; then
    echo "PR,Title,Priority,Category,Comment"
fi

FIRST_ITEM=true

# Process each PR
for pr_num in $(seq "$START_PR" "$END_PR"); do
    # Check if PR exists and has reviews
    if ! pr_data=$(gh pr view "$pr_num" --json number,title,reviews 2>/dev/null); then
        continue
    fi

    # Extract claude-code reviews
    reviews=$(echo "$pr_data" | jq -r '
        .reviews[] |
        select(.author.login == "claude-code[bot]") |
        .body
    ' 2>/dev/null || echo "")

    if [ -z "$reviews" ]; then
        continue
    fi

    pr_title=$(echo "$pr_data" | jq -r '.title')

    # Process each review
    echo "$reviews" | while IFS= read -r review_body; do
        category=$(categorize_review "$review_body")
        priority=$(extract_priority "$review_body")

        # Filter by priority if specified
        if [ "$PRIORITY_FILTER" != "all" ]; then
            if [ "${priority,,}" != "${PRIORITY_FILTER,,}" ]; then
                continue
            fi
        fi

        # Output based on format
        case $FORMAT in
            markdown)
                echo ""
                echo "## PR #$pr_num: $pr_title"
                echo "**Priority:** $priority"
                echo "**Category:** $category"
                echo "**Review Comment:**"
                echo "$review_body"
                echo ""
                ;;
            json)
                if [ "$FIRST_ITEM" = false ]; then
                    echo ","
                fi
                jq -n \
                    --arg pr "$pr_num" \
                    --arg title "$pr_title" \
                    --arg priority "$priority" \
                    --arg category "$category" \
                    --arg body "$review_body" \
                    '{pr: $pr, title: $title, priority: $priority, category: $category, comment: $body}'
                FIRST_ITEM=false
                ;;
            csv)
                # Escape quotes in CSV
                escaped_title=$(echo "$pr_title" | sed 's/"/""/g')
                escaped_body=$(echo "$review_body" | sed 's/"/""/g' | tr '\n' ' ')
                echo "\"$pr_num\",\"$escaped_title\",\"$priority\",\"$category\",\"$escaped_body\""
                ;;
        esac
    done
done

# Close JSON array
if [ "$FORMAT" = "json" ]; then
    echo ""
    echo "]"
fi

echo -e "${GREEN}[OK] Extracted claude-code reviews from PRs $START_PR-$END_PR${NC}" >&2
