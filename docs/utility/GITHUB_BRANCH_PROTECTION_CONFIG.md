# GitHub Branch Protection Configuration

**Version:** 1.0
**Created:** 2025-11-07
**Last Updated:** 2025-11-07
**Purpose:** Documents the GitHub branch protection rules configured for the main branch
**Related:** DEF-003 (GitHub Branch Protection Rules)

---

## Overview

This document provides the exact configuration for GitHub branch protection rules on the `main` branch. These settings were configured via the GitHub API on 2025-11-07 to ensure code quality and enforce PR-based workflows.

**Why This Document Exists:**
- Branch protection rules are configured via GitHub API (not stored in code)
- Settings could be lost if protection is disabled/re-enabled
- Provides exact reproduction steps for setting up protection

---

## Current Configuration

### Branch: `main`

**Protection Enabled:** Yes
**Last Updated:** 2025-11-07T13:35:00Z (during PR #3 merge)

---

## Required Status Checks

**Strict Status Checks:** `true`
All status checks must pass before merging. The PR branch must be up-to-date with the base branch before merging.

### Required Checks (5 core checks + 1 summary)

| Check Name | Description | Workflow File | Typical Duration |
|------------|-------------|---------------|------------------|
| **Pre-commit Validation (Ruff, Mypy, Security)** | Runs Ruff formatter/linter, Mypy type checking, and security scans | `.github/workflows/ci.yml` | ~1-2 min |
| **Security Scanning (Bandit & Safety)** | Runs Bandit (code security) and Safety (dependency vulnerabilities) | `.github/workflows/ci.yml` | ~20-30 sec |
| **Documentation Validation** | Validates documentation consistency (9 checks via `validate_docs.py`) | `.github/workflows/ci.yml` | ~5-10 sec |
| **Quick Validation Suite** | Fast validation for rapid feedback (Ruff + docs + fast tests) | `.github/workflows/ci.yml` | ~30-60 sec |
| **CI Summary** | Summary check that aggregates all test results | `.github/workflows/ci.yml` | ~1-5 sec |

**Note:** Individual test matrix jobs (Python 3.12/3.13/3.14 on ubuntu/windows) are NOT required checks. Only the CI Summary check is required, which aggregates their results.

**Rationale for Required Checks:**
- **Pre-commit Validation**: Ensures code style, type safety, and basic security before merge
- **Security Scanning**: Catches security vulnerabilities early
- **Documentation Validation**: Maintains documentation consistency across all docs
- **Quick Validation Suite**: Provides fast feedback for rapid iteration
- **CI Summary**: Ensures all test matrix combinations pass (without requiring each individually)

**Rationale for NOT Requiring Test Matrix Jobs:**
- Test jobs (Python 3.12/3.13/3.14 on ubuntu/windows) run as matrix (6 jobs total)
- Requiring all 6 individually would make the required checks list very long
- CI Summary check already aggregates their results (fails if any test job fails)
- This keeps the protection UI clean while maintaining full test coverage enforcement

---

## Pull Request Requirements

**Require Pull Request Reviews:** Yes
**Required Approving Review Count:** 0
*(No reviews required for solo development, but PRs are mandatory)*

**Dismiss Stale Reviews:** `true`
Approvals are dismissed when new commits are pushed to the PR branch.

**Require Code Owner Reviews:** `false`
No CODEOWNERS file is currently used.

---

## Admin Enforcement

**Enforce for Administrators:** `true`

⚠️ **CRITICAL:** This setting ensures that even users with admin access cannot bypass branch protection rules. Direct pushes to `main` are blocked for everyone, including admins. All changes must go through pull requests with passing CI checks.

**Implication:** If you need to make an emergency fix that bypasses CI:
1. You CANNOT push directly to main (even as admin)
2. You MUST temporarily disable branch protection
3. Make the fix
4. Re-enable protection using this document's configuration

---

## Additional Settings

| Setting | Value | Description |
|---------|-------|-------------|
| **Required Linear History** | `false` | Merge commits are allowed (squash merges preferred but not enforced) |
| **Allow Force Pushes** | `false` | Force pushes to `main` are blocked |
| **Allow Deletions** | `false` | Branch deletion is blocked |
| **Required Conversation Resolution** | `true` | All PR conversations must be resolved before merge |
| **Lock Branch** | `false` | Branch is not locked (accepts new commits via PRs) |
| **Allow Fork Syncing** | `false` | Fork syncing is disabled |
| **Restrictions** | `null` | No user/team restrictions (all contributors can create PRs) |

---

## API Configuration Payload

### Complete JSON Payload

This is the exact JSON payload used to configure branch protection via GitHub API:

```json
{
  "required_status_checks": {
    "strict": true,
    "checks": [
      {"context": "Pre-commit Validation (Ruff, Mypy, Security)"},
      {"context": "Security Scanning (Bandit & Safety)"},
      {"context": "Documentation Validation"},
      {"context": "Quick Validation Suite"},
      {"context": "CI Summary"}
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 0
  },
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": false
}
```

---

## Reproduction Steps

### Method 1: Using GitHub CLI (Recommended)

```bash
# Authenticate with GitHub CLI (if not already)
gh auth login

# Apply branch protection configuration
gh api -X PUT \
  repos/mutantamoeba/precog/branches/main/protection \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "checks": [
      {"context": "Pre-commit Validation (Ruff, Mypy, Security)"},
      {"context": "Security Scanning (Bandit & Safety)"},
      {"context": "Documentation Validation"},
      {"context": "Quick Validation Suite"},
      {"context": "CI Summary"}
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 0
  },
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": false
}
EOF
```

### Method 2: Using GitHub Web UI

1. Go to: `https://github.com/mutantamoeba/precog/settings/branches`
2. Click "Add rule" or edit existing "main" branch rule
3. Configure settings to match table above:
   - Check "Require a pull request before merging"
   - Uncheck "Require approvals" (set to 0)
   - Check "Require status checks to pass before merging"
   - Check "Require branches to be up to date before merging"
   - Add required status checks:
     - Pre-commit Validation (Ruff, Mypy, Security)
     - Security Scanning (Bandit & Safety)
     - Documentation Validation
     - Quick Validation Suite
     - CI Summary
   - Check "Do not allow bypassing the above settings" (enforce_admins)
   - Check "Require conversation resolution before merging"
   - Uncheck "Allow force pushes"
   - Uncheck "Allow deletions"
4. Click "Save changes"

---

## Verification

### Verify Branch Protection is Active

```bash
# Check current protection status
gh api repos/mutantamoeba/precog/branches/main/protection | jq .

# Check required status checks
gh api repos/mutantamoeba/precog/branches/main/protection/required_status_checks | jq .
```

Expected output should show:
- `enforce_admins.enabled: true`
- 5 required status checks
- `required_pull_request_reviews.required_approving_review_count: 0`

### Test Protection Works

```bash
# Attempt direct push to main (should fail)
git checkout main
echo "test" > test.txt
git add test.txt
git commit -m "Test protection"
git push origin main
# Expected: Error "Changes must be made through a pull request"
```

---

## Troubleshooting

### Issue: Required checks not appearing

**Symptom:** Status checks pass in CI but don't show up in branch protection

**Cause:** Check names in branch protection don't match workflow job names

**Solution:**
1. Check exact check names from a recent PR:
   ```bash
   gh pr checks <PR_NUMBER>
   ```
2. Update branch protection with exact names (case-sensitive, whitespace-sensitive)

### Issue: PRs mergeable despite failing checks

**Symptom:** Merge button is enabled even with failing CI checks

**Cause:** `strict: false` in required_status_checks OR check names don't match

**Solution:**
1. Verify `strict: true` is set
2. Verify check names match exactly (run `gh pr checks` to see actual names)
3. Re-apply configuration using reproduction steps above

### Issue: Admins can bypass protection

**Symptom:** Admin users can push directly to main or merge without checks

**Cause:** `enforce_admins: false`

**Solution:**
1. Verify `enforce_admins: true` in configuration
2. Re-apply configuration
3. Test with admin account (should still fail)

---

## History

| Date | Change | Reason | Updated By |
|------|--------|--------|------------|
| 2025-11-07 | Initial configuration | Complete DEF-003 (Branch Protection Rules) | Claude (via API) |
| 2025-11-07 | Updated check names | Fix mismatch between old short names and new descriptive workflow names | Claude (via API) |

**Initial Configuration Details:**
- Previous check names (short): `pre-commit-checks`, `security-scan`, `documentation-validation`, `test`, `validate-quick`, `ci-summary`
- Updated check names (descriptive): Full names matching CI workflow (see Required Checks table above)
- Reason: Old short names were causing "zombie" protection that could never be satisfied

---

## Related Documentation

- **DEF-003 Documentation:** `docs/utility/PHASE_0.7_DEFERRED_TASKS_V1.0.md` (lines 65-97)
- **CI Workflow:** `.github/workflows/ci.yml`
- **Pre-commit Config:** `.pre-commit-config.yaml`
- **GitHub Docs:** https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches

---

## Future Enhancements (DEF-003 Deferred Tasks)

The following enhancements are documented in `PHASE_0.7_DEFERRED_TASKS_V1.0.md` but not yet implemented:

1. **Consider requiring all test matrix jobs** (vs. just CI Summary)
   - Pro: More explicit protection
   - Con: Noisier required checks list
   - Current: CI Summary aggregates all tests (sufficient for now)

2. **Add CODEOWNERS file for automatic review assignments**
   - Enable `require_code_owner_reviews: true`
   - Auto-assign reviews based on file patterns

3. **Consider requiring signed commits**
   - Add `required_signatures: true`
   - Requires GPG key setup for all contributors

---

## Security Implications

**CRITICAL SECURITY FEATURES:**

1. ✅ **Enforce Admins:** All users (including admins) must go through PRs
2. ✅ **No Force Push:** Prevents history rewriting on main
3. ✅ **No Deletions:** Prevents accidental branch deletion
4. ✅ **Required Security Scan:** Bandit + Safety must pass
5. ✅ **Required Pre-commit:** Credentials scan must pass

**What This Prevents:**
- ❌ Direct commits to main (accidental or malicious)
- ❌ Pushing code with hardcoded credentials
- ❌ Merging code with security vulnerabilities
- ❌ Merging code that breaks tests
- ❌ Rewriting git history on main branch

**What This Does NOT Prevent:**
- ⚠️ Malicious code in dependencies (mitigated by Safety scan)
- ⚠️ Logic bugs that pass tests
- ⚠️ Social engineering attacks on contributors

---

**END OF DOCUMENT**
