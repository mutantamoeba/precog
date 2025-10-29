# Security Review Checklist

---
**Version:** 1.0
**Created:** 2025-10-28
**Status:** ✅ Active
**Purpose:** Ensure no sensitive data is committed to version control
---

## Document Purpose

This checklist provides a systematic approach to identifying and preventing security vulnerabilities before committing code to git. Use this before EVERY commit and during phase completion reviews.

---

## Pre-Commit Security Review (Before Every Git Commit)

Run these checks **BEFORE** running `git add` or `git commit`.

### 1. Hardcoded Credentials Check

**Manual Review:**
- [ ] No hardcoded passwords in any `.py`, `.js`, `.ts`, `.sql` files
- [ ] No API keys in source code (search for `api_key`, `API_KEY`, `apiKey`)
- [ ] No tokens in configuration files (search for `token`, `TOKEN`, `bearer`)
- [ ] No database connection strings with embedded passwords
- [ ] All credentials loaded from environment variables (`.env`) or secure vaults

**Automated Search:**
```bash
# Search for common credential patterns
git grep -i "password\s*=\s*['\"]" -- '*.py' '*.js' '*.yaml' '*.sql'
git grep -i "api_key\s*=\s*['\"]" -- '*.py' '*.js' '*.yaml'
git grep -i "secret\s*=\s*['\"]" -- '*.py' '*.js' '*.yaml'
git grep "postgres://.*:.*@" -- '*.py' '*.js' '*.sql'
```

**What to Look For:**
```python
# ❌ BAD - Hardcoded password
'password': 'suckbluefrogs'
db_password = "mySecretPass123"

# ✅ GOOD - Environment variable
'password': os.getenv('DB_PASSWORD')
db_password = os.getenv('DB_PASSWORD', '')
```

### 2. Sensitive Files Check

**Files That Should NEVER Be Committed:**
- [ ] No `.env` files (only `.env.template` with placeholders)
- [ ] No `/_keys/` folder contents (private keys, certificates)
- [ ] No `*.pem`, `*.key`, `*.p12`, `*.pfx` files (cryptographic keys)
- [ ] No backup files with data: `*.sql.bak`, `*.dump`, `database/*.sql` with real data
- [ ] No IDE config with secrets: `.vscode/settings.json` with tokens

**Automated Search:**
```bash
# Check for sensitive file patterns
git status --ignored | grep -E "\.(env|pem|key|p12|pfx|dump)$"
git ls-files | grep -E "\.env$|_keys/|\.pem$|\.key$"
```

### 3. Configuration Safety

**YAML and Config Files:**
- [ ] `.env.template` has placeholder values only (e.g., `your_api_key_here`)
- [ ] `config/*.yaml` contain no real credentials
- [ ] No production URLs or IP addresses exposed
- [ ] No internal system paths revealed

**Examples:**
```yaml
# ❌ BAD - Real credentials
kalshi_api_key: "sk_live_abc123def456"

# ✅ GOOD - Placeholder
kalshi_api_key: "${KALSHI_API_KEY}"  # Loaded from .env
```

### 4. Scripts & Code Review

**Check All Scripts in `/scripts/` Directory:**
- [ ] Database scripts use `os.getenv('DB_PASSWORD')`
- [ ] Migration scripts load credentials from environment
- [ ] Test scripts don't contain real database passwords
- [ ] Setup scripts use `.env` file

**Pattern to Follow:**
```python
# ✅ GOOD - Use this pattern everywhere
import os
from dotenv import load_dotenv

load_dotenv()

db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'precog'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD')  # No default!
}

if not db_config['password']:
    raise ValueError("DB_PASSWORD not found in environment variables")
```

### 5. Documentation Review

- [ ] README/docs don't include real credentials in examples
- [ ] Session handoffs don't contain secrets
- [ ] Code comments don't reveal security details (no "password is abc123")
- [ ] Architecture diagrams don't show production IPs

---

## .gitignore Validation

### Required Entries

Verify these entries exist in `.gitignore`:

```gitignore
# Environment variables
.env
.env.local
.env.*.local

# Database
*.db
*.sqlite
*.sqlite3
*.dump
*.sql.bak
database/*.sql  # If database folder contains scripts with data

# Keys and certificates
_keys/
*.pem
*.key
*.p12
*.pfx
*.cer
*.crt

# Backup files
*.bak
*.backup
*.old
*.tmp

# IDE configurations (if they contain secrets)
.vscode/settings.json
.idea/workspace.xml
```

### Validate .gitignore Works

```bash
# Check what would be committed
git status

# Check ignored files
git status --ignored

# Verify sensitive files are ignored
echo "Test" > .env
git status | grep ".env"  # Should show "nothing to commit"
```

---

## Phase Completion Security Review

Run this comprehensive review at the end of each phase.

### Step 1: Full Repository Scan (5 minutes)

```bash
# Search for ALL potential secrets in tracked files
git grep -E "(password|secret|key|token|api_key)" -- '*.py' '*.js' '*.yaml' '*.sql' '*.md'

# Search for connection strings
git grep -E "(postgres://|mysql://|mongodb://)" -- '*'

# Search for email addresses (might indicate test accounts)
git grep -E "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}" -- '*.py' '*.sql'

# Check for hardcoded IPs
git grep -E "\b([0-9]{1,3}\.){3}[0-9]{1,3}\b" -- '*.py' '*.yaml'
```

### Step 2: Review New Files

```bash
# List all files added this phase
git diff --name-status origin/main | grep "^A"

# Review each new file for secrets
git diff origin/main --stat
```

### Step 3: Database Folder Audit

**If `/database/` folder exists:**
- [ ] No `.sql` files with real data or passwords
- [ ] Migrations use parameterized queries, not hardcoded values
- [ ] Seed data uses fake/test data only
- [ ] Connection scripts load from environment variables

**Recommended:**
- Add `/database/*.sql` to .gitignore if scripts contain any data
- Keep only schema definitions and migration templates in version control

### Step 4: Scripts Folder Audit

**Check ALL files in `/scripts/`:**
```bash
# Find all scripts with password patterns
grep -r "password.*=.*['\"]" scripts/

# Find all scripts NOT using environment variables
grep -L "os.getenv" scripts/*.py
```

### Step 5: Dependency Security Scan

```bash
# Check for known vulnerabilities in dependencies
pip install pip-audit
pip-audit

# Or use safety
pip install safety
safety check
```

---

## Git History Scan (Monthly)

### Using Automated Tools

**Option 1: TruffleHog (Recommended)**
```bash
# Install
pip install truffleHog

# Scan entire history
trufflehog --regex --entropy=True file://path/to/repo
```

**Option 2: git-secrets**
```bash
# Install (macOS)
brew install git-secrets

# Install (Linux)
git clone https://github.com/awslabs/git-secrets.git
cd git-secrets && make install

# Scan repository
git secrets --scan
git secrets --scan-history
```

**Option 3: gitleaks**
```bash
# Install
brew install gitleaks

# Scan repository
gitleaks detect --source . --verbose
```

---

## If Secrets Are Found in Git History

### Immediate Response Plan

1. **Stop all commits immediately**
2. **Rotate compromised credentials** (change passwords, revoke API keys)
3. **Choose remediation strategy:**

#### Strategy A: Fresh Start (No Collaborators Yet)
```bash
# 1. Fix all issues first (remove hardcoded passwords)
# 2. Delete git history
rm -rf .git

# 3. Reinitialize
git init
git add .
git commit -m "Initial commit with secure configuration"

# 4. Force push
git remote add origin <repo-url>
git push -u --force origin main
```

#### Strategy B: BFG Repo-Cleaner (Has Collaborators)
```bash
# 1. Install BFG (requires Java)
# Download from: https://reps.bfg-repo-cleaner.com/

# 2. Clone mirror backup
git clone --mirror https://github.com/user/repo.git repo-backup.git

# 3. Create passwords.txt with secrets to remove
echo "suckbluefrogs" > secrets.txt

# 4. Run BFG
java -jar bfg.jar --replace-text secrets.txt

# 5. Clean up
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 6. Force push (NOTIFY COLLABORATORS FIRST!)
git push --force
```

3. **Verify secrets removed:**
```bash
git log --all --full-history -- "*password*"
git grep "suckbluefrogs"  # Should return nothing
```

4. **Update security checklist** to prevent recurrence

---

## Password Rotation Checklist

When credentials are exposed:

**Immediate (Within 1 hour):**
- [ ] Change PostgreSQL database password
- [ ] Revoke exposed API keys (Kalshi, ESPN, etc.)
- [ ] Generate new API keys
- [ ] Update `.env` file with new credentials

**Within 24 hours:**
- [ ] Review access logs for unauthorized access
- [ ] Notify team members if repository was shared
- [ ] Update documentation with new security procedures

**Within 1 week:**
- [ ] Implement automated secret scanning (git hooks)
- [ ] Add pre-commit hooks to block secrets
- [ ] Schedule monthly security audits

---

## Automated Prevention (Pre-commit Hooks)

### Install git-secrets

```bash
# Install
brew install git-secrets  # macOS
# or for Linux, see: https://github.com/awslabs/git-secrets

# Initialize in repository
cd /path/to/precog-repo
git secrets --install

# Add patterns to detect
git secrets --register-aws
git secrets --add 'password\s*=\s*["\'][^"\']+["\']'
git secrets --add 'api_key\s*=\s*["\'][^"\']+["\']'
git secrets --add 'postgres://[^@]+:[^@]+@'
```

### Custom Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash

echo "Running security checks..."

# Check for hardcoded passwords
if git grep -E "(password|secret|api_key)\s*=\s*['\"][^'\"]{8,}['\"]" -- '*.py' '*.js' '*.yaml'; then
    echo "❌ ERROR: Hardcoded credentials detected!"
    echo "Please use environment variables instead."
    exit 1
fi

# Check for .env file
if git diff --cached --name-only | grep -E "^\.env$"; then
    echo "❌ ERROR: Attempting to commit .env file!"
    echo "Only .env.template should be committed."
    exit 1
fi

echo "✅ Security checks passed"
exit 0
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

---

## Quick Reference: Safe Patterns

### ✅ SAFE - Always Use These

```python
# Environment variables
import os
password = os.getenv('DB_PASSWORD')

# .env file
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv('KALSHI_API_KEY')

# Raise error if missing
password = os.environ['DB_PASSWORD']  # Raises KeyError if not set
```

### ❌ UNSAFE - Never Use These

```python
# Hardcoded credentials
password = "suckbluefrogs"
api_key = "sk_live_abc123"

# Credentials in comments
# The password is: suckbluefrogs

# Credentials in git commit messages
git commit -m "Fixed login, password is abc123"
```

---

## Security Review Sign-off

At the end of each phase, the following person should sign off:

**Phase Reviewed:** Phase ______
**Reviewed By:** _______________
**Date:** _______________
**Security Issues Found:** ☐ None  ☐ Minor  ☐ Critical
**All Issues Resolved:** ☐ Yes  ☐ No (explain below)

**Notes:**
_________________________________________
_________________________________________

---

## Maintenance

**Review Frequency:**
- Pre-commit: Every commit
- Phase completion: End of each phase
- Monthly audit: First Monday of each month
- Dependency scan: Weekly (automated CI/CD)

**Document Updates:**
- Update this checklist when new secret types are discovered
- Add new patterns when vulnerabilities are found
- Review annually for completeness

---

## Resources

**Tools:**
- TruffleHog: https://github.com/trufflesecurity/truffleHog
- git-secrets: https://github.com/awslabs/git-secrets
- gitleaks: https://github.com/gitleaks/gitleaks
- BFG Repo-Cleaner: https://reps.bfg-repo-cleaner.com/

**References:**
- OWASP Top 10: https://owasp.org/Top10/
- GitHub Security Best Practices: https://docs.github.com/en/code-security
- .env Best Practices: https://github.com/motdotla/dotenv#should-i-commit-my-env-file

---

**END OF SECURITY REVIEW CHECKLIST V1.0**
