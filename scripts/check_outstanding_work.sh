#!/usr/bin/env bash
#
# Check for outstanding work from previous phase/sessions
#
# This script automates Step 1.5 of the Phase Start Protocol in CLAUDE.md.
# It checks for open issues, unmerged PRs, deferred tasks, and recent
# claude-review comments that may need addressing.
#
# Usage:
#   bash scripts/check_outstanding_work.sh [--pr-range START END]
#
# Options:
#   --pr-range START END    Check PRs in range START..END for reviews
#                          Default: last 20 merged PRs
#
# Example:
#   bash scripts/check_outstanding_work.sh --pr-range 70 85
#
# Exit Codes:
#   0 - No outstanding work found
#   1 - Outstanding work found (requires triage)
#
# Educational Note:
#   This script uses gh CLI for GitHub API access. Ensure you're authenticated:
#   gh auth status
#
# Reference:
#   CLAUDE.md - Phase Start Protocol Step 1.5

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters for summary
OPEN_ISSUES=0
OPEN_PRS=0
DEFERRED_DOCS=0
CLAUDE_REVIEWS=0

echo "========================================"
echo "Outstanding Work Check"
echo "========================================"
echo ""

# Parse command line arguments
PR_START=""
PR_END=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --pr-range)
            PR_START="$2"
            PR_END="$3"
            shift 3
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--pr-range START END]"
            exit 1
            ;;
    esac
done

# 1. Check for open GitHub Issues
echo -e "${BLUE}[1/4] Checking Open GitHub Issues...${NC}"
echo ""

if ! gh issue list --state open --limit 100 > /tmp/open_issues.txt 2>&1; then
    echo -e "${YELLOW}[WARN] Could not fetch issues (gh CLI not authenticated?)${NC}"
else
    OPEN_ISSUES=$(wc -l < /tmp/open_issues.txt | tr -d ' ')

    if [ "$OPEN_ISSUES" -gt 0 ]; then
        echo -e "${YELLOW}Found $OPEN_ISSUES open issue(s):${NC}"
        cat /tmp/open_issues.txt
        echo ""
        echo -e "${YELLOW}Action: Review and either:${NC}"
        echo "  - Add relevant issues to phase todo list"
        echo "  - Close with comment if no longer needed"
    else
        echo -e "${GREEN}[OK] No open issues${NC}"
    fi
fi
echo ""

# 2. Check for unmerged PRs
echo -e "${BLUE}[2/4] Checking Unmerged Pull Requests...${NC}"
echo ""

if ! gh pr list --state open --limit 100 > /tmp/open_prs.txt 2>&1; then
    echo -e "${YELLOW}[WARN] Could not fetch PRs${NC}"
else
    OPEN_PRS=$(wc -l < /tmp/open_prs.txt | tr -d ' ')

    if [ "$OPEN_PRS" -gt 0 ]; then
        echo -e "${YELLOW}Found $OPEN_PRS open PR(s):${NC}"
        cat /tmp/open_prs.txt
        echo ""
        echo -e "${YELLOW}Action: For each PR:${NC}"
        echo "  - Check CI status: gh pr checks <number>"
        echo "  - Merge if ready: gh pr merge <number> --squash"
        echo "  - Update if behind: git checkout <branch> && git merge origin/main"
        echo "  - Close if obsolete: gh pr close <number> --comment 'reason'"
    else
        echo -e "${GREEN}[OK] No unmerged PRs${NC}"
    fi
fi
echo ""

# 3. Check for deferred task documents
echo -e "${BLUE}[3/4] Checking Deferred Task Documents...${NC}"
echo ""

if [ -d "docs/utility" ]; then
    find docs/utility -name "PHASE_*_DEFERRED_TASKS*.md" -type f > /tmp/deferred_docs.txt 2>/dev/null || true
    DEFERRED_DOCS=$(wc -l < /tmp/deferred_docs.txt | tr -d ' ')

    if [ "$DEFERRED_DOCS" -gt 0 ]; then
        echo -e "${YELLOW}Found $DEFERRED_DOCS deferred task document(s):${NC}"
        while IFS= read -r doc; do
            echo "  - $doc"
            # Extract DEF-XXX task IDs
            grep -oE "DEF-[0-9]{3}" "$doc" 2>/dev/null | sort -u | while read -r task_id; do
                echo "    * $task_id"
            done
        done < /tmp/deferred_docs.txt
        echo ""
        echo -e "${YELLOW}Action: Review deferred tasks:${NC}"
        echo "  - Extract tasks for current phase"
        echo "  - Add to phase todo list with TodoWrite"
    else
        echo -e "${GREEN}[OK] No deferred task documents${NC}"
    fi
else
    echo -e "${YELLOW}[WARN] docs/utility directory not found${NC}"
fi
echo ""

# 4. Check for claude-review comments from recent PRs
echo -e "${BLUE}[4/4] Checking Claude Review Comments...${NC}"
echo ""

# Determine PR range
if [ -z "$PR_START" ] || [ -z "$PR_END" ]; then
    # Get last 20 merged PRs
    echo "[INFO] No --pr-range specified, checking last 20 merged PRs"
    gh pr list --state merged --limit 20 --json number --jq '.[].number' > /tmp/pr_range.txt 2>/dev/null || true
else
    # Use provided range
    seq "$PR_START" "$PR_END" > /tmp/pr_range.txt
fi

if [ -s /tmp/pr_range.txt ]; then
    echo "[INFO] Checking PRs for claude-code[bot] reviews..."
    echo ""

    while read -r pr_num; do
        # Check if PR has claude-code reviews
        reviews=$(gh pr view "$pr_num" --json reviews --jq '[.reviews[] | select(.author.login == "claude-code[bot]")] | length' 2>/dev/null || echo "0")

        if [ "$reviews" -gt 0 ]; then
            CLAUDE_REVIEWS=$((CLAUDE_REVIEWS + reviews))
            echo -e "${YELLOW}PR #$pr_num has $reviews claude-code review(s)${NC}"

            # Get PR title
            title=$(gh pr view "$pr_num" --json title --jq '.title' 2>/dev/null || echo "Unknown")
            echo "  Title: $title"

            # Extract review body (first 200 chars)
            gh pr view "$pr_num" --json reviews --jq '
                .reviews[] |
                select(.author.login == "claude-code[bot]") |
                .body[0:200] + "..."
            ' 2>/dev/null | head -5
            echo ""
        fi
    done < /tmp/pr_range.txt

    if [ "$CLAUDE_REVIEWS" -gt 0 ]; then
        echo -e "${YELLOW}Action: Review claude-code suggestions:${NC}"
        echo "  - Critical (security, bugs): Address in current phase"
        echo "  - Improvements: Add to deferred tasks (DEF-XXX)"
        echo "  - Nice-to-have: Document in next phase planning"
    else
        echo -e "${GREEN}[OK] No claude-code reviews found${NC}"
    fi
else
    echo -e "${YELLOW}[WARN] Could not determine PR range${NC}"
fi
echo ""

# Summary
echo "========================================"
echo "Summary"
echo "========================================"
echo ""
echo "Open Issues:        $OPEN_ISSUES"
echo "Unmerged PRs:       $OPEN_PRS"
echo "Deferred Docs:      $DEFERRED_DOCS"
echo "Claude Reviews:     $CLAUDE_REVIEWS"
echo ""

TOTAL=$((OPEN_ISSUES + OPEN_PRS + CLAUDE_REVIEWS))

if [ "$TOTAL" -eq 0 ]; then
    echo -e "${GREEN}[OK] No outstanding work - ready to start phase${NC}"
    exit 0
else
    echo -e "${YELLOW}[ACTION REQUIRED] $TOTAL items need triage${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review all items listed above"
    echo "  2. Create TodoWrite list with prioritized tasks"
    echo "  3. Close/merge items that are resolved"
    echo "  4. Document remaining items in phase planning"
    exit 1
fi
