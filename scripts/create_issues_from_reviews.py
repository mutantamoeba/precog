#!/usr/bin/env python3
"""
Create GitHub issues from claude-code review comments.

This script takes extracted claude-code review comments (from
extract_claude_review_comments.sh) and creates GitHub issues with
appropriate labels, priorities, and references.

Usage:
    python scripts/create_issues_from_reviews.py <reviews_file> [--dry-run] [--label LABEL]

Arguments:
    reviews_file    JSON file from extract_claude_review_comments.sh

Options:
    --dry-run       Preview issues without creating them
    --label LABEL   Additional label to add (e.g., 'phase-2')
    --skip-low      Skip low-priority reviews

Examples:
    # Dry run (preview only)
    bash scripts/extract_claude_review_comments.sh 70 85 --format json > reviews.json
    python scripts/create_issues_from_reviews.py reviews.json --dry-run

    # Create issues with phase label
    python scripts/create_issues_from_reviews.py reviews.json --label phase-2

    # Create only critical/high priority issues
    python scripts/create_issues_from_reviews.py reviews.json --skip-low

Exit Codes:
    0 - Success
    1 - Error (file not found, API error, etc.)

Educational Note:
    This automates GitHub issue creation from review comments,
    streamlining the workflow from PR review -> Issue -> Implementation.
    Uses PyGithub library for GitHub API interaction.

Reference:
    Phase Completion Protocol Step 7 - AI Code Review Analysis
    Requires: pip install PyGithub
"""

import argparse
import json
import sys
from typing import Any

try:
    from github import Github, GithubException
except ImportError:
    print("Error: PyGithub not installed. Run: pip install PyGithub")
    sys.exit(1)


def load_reviews(filepath: str) -> list[dict[str, Any]]:
    """Load review comments from JSON file.

    Args:
        filepath: Path to JSON file from extract_claude_review_comments.sh

    Returns:
        List of review comment dictionaries

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    with open(filepath, encoding="utf-8") as f:
        data: list[dict[str, Any]] = json.load(f)
        return data


def create_issue_title(review: dict) -> str:
    """Generate issue title from review comment.

    Args:
        review: Review dictionary with pr, title, priority, category, comment

    Returns:
        Formatted issue title

    Example:
        "claude-review: Add retry logic to API client (PR #75)"
    """
    pr_num = review["pr"]

    # Extract first sentence of comment as summary
    comment = review["comment"]
    first_sentence = comment.split(".")[0].strip()

    # Limit to 80 chars
    if len(first_sentence) > 60:
        first_sentence = first_sentence[:57] + "..."

    return f"claude-review: {first_sentence} (PR #{pr_num})"


def create_issue_body(review: dict) -> str:
    """Generate issue body from review comment.

    Args:
        review: Review dictionary

    Returns:
        Formatted issue body in markdown
    """
    pr_num = review["pr"]
    pr_title = review["title"]
    priority = review["priority"]
    category = review["category"]
    comment = review["comment"]

    return f"""## Claude Code Review Suggestion

**Source PR:** #{pr_num} - {pr_title}
**Priority:** {priority}
**Category:** {category}

### Review Comment

{comment}

### Triage Decision

- [ ] **Accept** - Implement in current phase
- [ ] **Defer** - Add to `PHASE_X_DEFERRED_TASKS.md` with DEF-XXX ID
- [ ] **Reject** - Close with rationale (comment why not applicable)

### Implementation Notes

<!-- Add notes during implementation -->

---

🤖 Auto-generated from claude-code[bot] review comment
"""


def get_labels(review: dict, additional_labels: list[str]) -> list[str]:
    """Determine labels for issue based on review category and priority.

    Args:
        review: Review dictionary
        additional_labels: Extra labels to add (e.g., 'phase-2')

    Returns:
        List of label names
    """
    labels = ["claude-review"]

    # Add category label
    category_map = {
        "Security": "security",
        "Testing": "testing",
        "Performance": "performance",
        "Documentation": "documentation",
        "Code Quality": "code-quality",
    }
    if review["category"] in category_map:
        labels.append(category_map[review["category"]])

    # Add priority label
    priority_map = {
        "Critical": "priority-critical",
        "High": "priority-high",
        "Medium": "priority-medium",
        "Low": "priority-low",
    }
    if review["priority"] in priority_map:
        labels.append(priority_map[review["priority"]])

    # Add additional labels
    labels.extend(additional_labels)

    return labels


def create_issues(
    reviews: list[dict],
    repo_name: str,
    dry_run: bool = False,
    additional_labels: list[str] | None = None,
    skip_low: bool = False,
) -> int:
    """Create GitHub issues from review comments.

    Args:
        reviews: List of review dictionaries
        repo_name: GitHub repository (e.g., 'user/repo')
        dry_run: If True, preview only (don't create)
        additional_labels: Extra labels to add
        skip_low: If True, skip low-priority reviews

    Returns:
        Number of issues created (or would be created if dry_run)
    """
    if additional_labels is None:
        additional_labels = []

    # Initialize GitHub API
    try:
        gh = Github()  # Uses GITHUB_TOKEN env var
        repo = gh.get_repo(repo_name)
    except GithubException as e:
        print(f"Error: GitHub API error: {e}")
        print("Ensure GITHUB_TOKEN environment variable is set")
        sys.exit(1)

    created_count = 0

    for review in reviews:
        # Skip low priority if requested
        if skip_low and review["priority"] == "Low":
            print(f"[SKIP] Low priority review from PR #{review['pr']}")
            continue

        title = create_issue_title(review)
        body = create_issue_body(review)
        labels = get_labels(review, additional_labels)

        if dry_run:
            print(f"\n{'=' * 60}")
            print("[DRY RUN] Would create issue:")
            print(f"Title: {title}")
            print(f"Labels: {', '.join(labels)}")
            print(f"\nBody:\n{body}")
            print(f"{'=' * 60}\n")
        else:
            try:
                issue = repo.create_issue(title=title, body=body, labels=labels)
                print(f"[OK] Created issue #{issue.number}: {title}")
            except GithubException as e:
                print(f"[ERROR] Failed to create issue: {e}")
                continue

        created_count += 1

    return created_count


def main():
    parser = argparse.ArgumentParser(
        description="Create GitHub issues from claude-code review comments"
    )
    parser.add_argument("reviews_file", help="JSON file from extract_claude_review_comments.sh")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview issues without creating them"
    )
    parser.add_argument(
        "--label",
        action="append",
        dest="labels",
        default=[],
        help="Additional label to add (can be used multiple times)",
    )
    parser.add_argument("--skip-low", action="store_true", help="Skip low-priority reviews")
    parser.add_argument(
        "--repo",
        default="mutantamoeba/precog",
        help="GitHub repository (default: mutantamoeba/precog)",
    )

    args = parser.parse_args()

    # Load reviews
    try:
        reviews = load_reviews(args.reviews_file)
    except FileNotFoundError:
        print(f"Error: File not found: {args.reviews_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {args.reviews_file}: {e}")
        sys.exit(1)

    print(f"Loaded {len(reviews)} review comments")

    # Create issues
    created = create_issues(
        reviews=reviews,
        repo_name=args.repo,
        dry_run=args.dry_run,
        additional_labels=args.labels,
        skip_low=args.skip_low,
    )

    if args.dry_run:
        print(f"\n[DRY RUN] Would create {created} issue(s)")
    else:
        print(f"\n[OK] Created {created} issue(s)")

    sys.exit(0)


if __name__ == "__main__":
    main()
