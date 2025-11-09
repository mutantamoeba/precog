# Security Review Checklist

---
**Version:** 1.1
**Created:** 2025-10-28
**Last Updated:** 2025-11-09
**Status:** ✅ Active
**Purpose:** Comprehensive security review covering credentials, API security, data protection, compliance, and incident response
**Changes in V1.1:**
- Added API Security section (authentication, authorization, rate limiting)
- Added Data Protection section (encryption, PII handling)
- Added Compliance section (GDPR, PCI-DSS per REQ-SEC-009)
- Added Incident Response section (logging, alerting, breach procedures)
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

## API Security

**Purpose:** Ensure API integrations are secure and cannot be exploited.

### Authentication & Authorization
- [ ] **Kalshi API authentication implemented** (ADR-047)
  - RSA-PSS signature authentication
  - Private key stored securely (environment variable or secrets manager)
  - No API keys in code or logs
- [ ] **ESPN API authentication** (if implemented)
  - API key in headers only
  - API key loaded from environment variable
- [ ] **Internal API authentication** (Phase 5+)
  - API keys or OAuth tokens required
  - No anonymous access allowed
  - Token rotation policy defined

### Authorization
- [ ] **Role-based access control** (Phase 7+)
  - Admin, trader, readonly roles defined
  - Least privilege principle enforced
  - Unauthorized actions blocked
- [ ] **API endpoint protection**
  - Sensitive endpoints require authentication
  - Input validation on all endpoints
  - Output sanitization (no sensitive data leaked)

### Rate Limiting
- [ ] **Rate limiting implemented**
  - Kalshi: 100 req/min token bucket (ADR-048)
  - Internal APIs: Appropriate limits set
  - Rate limit headers checked
- [ ] **Rate limit monitoring**
  - Current usage tracked
  - Alert when approaching limit (>80%)
  - Graceful degradation when limit hit
- [ ] **Abuse prevention**
  - IP-based rate limiting (if applicable)
  - Account-based rate limiting
  - Circuit breakers on repeated failures

### API Security Testing
- [ ] **SQL injection prevented**
  - All queries use parameterized statements
  - No string concatenation in queries
  - Example: `cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))`
- [ ] **Command injection prevented**
  - No user input passed to shell commands
  - If necessary, use subprocess with list arguments (not shell=True)
- [ ] **Path traversal prevented**
  - File paths validated (no `../` allowed)
  - Whitelisted paths only
- [ ] **XML/JSON parsing attacks prevented**
  - JSON parsing: Use standard library json module
  - No eval() on user input
  - Schema validation on API inputs

---

## Data Protection

**Purpose:** Ensure sensitive data is encrypted and handled securely.

### Encryption at Rest
- [ ] **Database encryption** (Production - Phase 7+)
  - Sensitive columns encrypted (API keys, PII if stored)
  - Encryption key stored in secrets manager
  - Key rotation policy defined
- [ ] **File system encryption** (Production)
  - Disk encryption enabled (LUKS, BitLocker, dm-crypt)
  - Backup encryption enabled
- [ ] **Secrets encryption**
  - Secrets stored in AWS Secrets Manager, Azure Key Vault, or HashiCorp Vault
  - No plaintext secrets in production

### Encryption in Transit
- [ ] **HTTPS enforced**
  - All HTTP traffic redirected to HTTPS
  - Valid SSL/TLS certificates
  - TLS 1.2+ only (no TLS 1.0/1.1)
- [ ] **API calls encrypted**
  - Kalshi API: HTTPS only
  - ESPN API: HTTPS only
  - Database connections: SSL/TLS enabled
- [ ] **WebSocket encryption** (Phase 3+)
  - WSS (WebSocket Secure) only
  - No WS (plain WebSocket)

### PII Handling (ADR-072: Privacy-Preserving Logging)
- [ ] **PII identification**
  - PII defined: Email, phone, name, address, SSN, etc.
  - PII fields identified in database schema
  - PII fields documented
- [ ] **PII minimization**
  - Only collect PII if necessary
  - Delete PII when no longer needed
  - Anonymize/pseudonymize where possible
- [ ] **PII in logs masked**
  - Email addresses masked: `user@example.com` → `u***@e***.com`
  - Phone numbers masked: `555-1234` → `***-***4`
  - No full PII in log files
- [ ] **PII access controlled**
  - Database: Separate readonly user without PII access
  - Application: PII fields encrypted
  - Logs: PII redacted before logging

### Sensitive Data Inventory
- [ ] **Financial data protected**
  - Prices stored as DECIMAL (Pattern 1 in CLAUDE.md)
  - Account balances encrypted if stored
  - Transaction history access controlled
- [ ] **Credentials protected**
  - API keys never logged
  - Database passwords never logged
  - OAuth tokens encrypted in database
- [ ] **Trading data protected**
  - Position data access controlled
  - Strategy configurations encrypted
  - Model weights encrypted

---

## Compliance

**Purpose:** Ensure regulatory compliance (GDPR, PCI-DSS, SOC 2).

### GDPR Compliance (if handling EU user data)
- [ ] **Data retention policy documented** (REQ-COMP-003)
  - Retention periods defined: Trades (7 years), Logs (90 days), etc.
  - Automatic deletion after retention period
  - User data deletion on request
- [ ] **Right to erasure implemented**
  - User data deletion API endpoint
  - Data purged from backups
  - Third-party data processors notified
- [ ] **Data portability implemented**
  - User can export their data (JSON format)
  - Export includes all personal data
  - Export available within 30 days of request
- [ ] **Consent management**
  - User consent recorded for data processing
  - Consent can be withdrawn
  - Processing stops after withdrawal
- [ ] **Data processing agreements**
  - DPAs with third parties (Kalshi, ESPN, etc.)
  - Subprocessor list maintained
  - Transfer mechanisms documented (Standard Contractual Clauses, etc.)
- [ ] **GDPR documentation**
  - Privacy policy published
  - Data protection impact assessment (DPIA) completed
  - Records of processing activities (ROPA) maintained

### PCI-DSS Compliance (if handling payment card data)
- [ ] **Cardholder data not stored**
  - No storage of full PAN (Primary Account Number)
  - No storage of CVV/CVC
  - No storage of magnetic stripe data
- [ ] **Payment gateway integration**
  - Use Stripe, PayPal, or certified payment gateway
  - Tokenization for recurring payments
  - No direct handling of card data
- [ ] **PCI audit completed** (Production)
  - Annual PCI DSS audit or SAQ (Self-Assessment Questionnaire)
  - Remediation of any findings
  - Compliance certificate obtained
- [ ] **Network segmentation** (Production)
  - Payment systems isolated from other systems
  - Firewall rules restrict access
  - Regular penetration testing

### SOC 2 Compliance (if required)
- [ ] **Security controls documented**
  - Access control policies
  - Encryption policies
  - Incident response procedures
  - Change management procedures
- [ ] **Control effectiveness monitored**
  - Quarterly control testing
  - Remediation of control failures
  - Evidence collection automated
- [ ] **Annual SOC 2 audit** (Production)
  - Type I or Type II audit
  - Audit report distributed to customers
  - Remediation of audit findings

### Audit Trail Requirements (REQ-COMP-003)
- [ ] **Database audit trail**
  - SCD Type 2 history preserved (row_start_ts, row_end_ts)
  - All changes logged with user/timestamp
  - Audit log retention: 7 years
- [ ] **Application audit trail**
  - All trades logged with full context (strategy, model, price, timestamp)
  - All configuration changes logged
  - All user actions logged (login, logout, commands)
- [ ] **Infrastructure audit trail**
  - All production changes logged (deployments, config changes)
  - CloudTrail or equivalent enabled
  - Log retention: 1 year minimum

---

## Incident Response

**Purpose:** Ensure rapid detection and response to security incidents.

### Security Monitoring
- [ ] **Application logs monitored**
  - Centralized logging (Elasticsearch, CloudWatch Logs)
  - Log retention: 90 days
  - Full-text search enabled
- [ ] **Security event logging**
  - Failed authentication attempts logged
  - Authorization failures logged
  - Unusual API activity logged (rate limit hits, unusual endpoints)
- [ ] **Alerting configured**
  - Critical errors alert immediately (PagerDuty, Opsgenie)
  - Security events alert within 5 minutes
  - Alert escalation policy defined

### Intrusion Detection
- [ ] **Failed login monitoring**
  - Alert on >5 failed logins in 1 minute
  - Account lockout after 10 failed attempts
  - Unlock mechanism (time-based or admin)
- [ ] **Suspicious activity detection**
  - Unusual API call patterns (geographic, time-of-day)
  - Unusual database queries (SELECT *, large result sets)
  - Unusual trading behavior (large positions, rapid trading)
- [ ] **Vulnerability scanning** (Production)
  - Quarterly vulnerability scans (Nessus, OpenVAS)
  - Critical vulnerabilities patched within 24 hours
  - High vulnerabilities patched within 7 days

### Breach Response Procedures
- [ ] **Incident response plan documented**
  - Detection procedures
  - Containment procedures
  - Eradication procedures
  - Recovery procedures
  - Post-incident review
- [ ] **Notification procedures**
  - Internal notification: Security team within 1 hour
  - Executive notification: C-level within 4 hours
  - Customer notification: Within 72 hours (GDPR requirement)
  - Regulatory notification: As required (GDPR, PCI-DSS)
- [ ] **Incident response team**
  - On-call rotation defined
  - Contact information current
  - Escalation procedures clear
- [ ] **Post-mortem template**
  - Timeline reconstruction
  - Root cause analysis
  - Impact assessment
  - Remediation actions
  - Prevention measures

### Backup & Recovery (Disaster Recovery)
- [ ] **Backup strategy**
  - Database backups: Daily at 2 AM UTC
  - Application backups: Weekly
  - Encryption: All backups encrypted
  - Retention: 30 days
  - Storage: Off-site (S3, Azure Blob)
- [ ] **Backup validation**
  - Monthly restore test to staging environment
  - Verify data integrity
  - Document restore procedure
- [ ] **Recovery time objectives (RTO)**
  - Database restore: <4 hours
  - Application deployment: <1 hour
  - Full system recovery: <8 hours
- [ ] **Recovery point objectives (RPO)**
  - Database: <24 hours (daily backups)
  - Application: <7 days (weekly backups)

### Security Patch Management
- [ ] **Patch monitoring**
  - Subscribe to security advisories (Python, PostgreSQL, dependencies)
  - Weekly review of new CVEs
- [ ] **Patch testing**
  - Test patches in staging environment
  - Regression testing before production
- [ ] **Patch deployment**
  - Critical security patches: Within 24 hours
  - High-priority patches: Within 7 days
  - Medium/low patches: Within 30 days
  - Maintenance window scheduled

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

**Related Documentation:**
- **DEVELOPMENT_PHILOSOPHY_V1.1.md** - Section 9: Security by Default
  - Core principle: No credentials in code, environment variables for all credentials
  - Zero tolerance for hardcoded secrets
  - Enables per-environment configuration and safe credential rotation
- **DEVELOPMENT_PHILOSOPHY_V1.1.md** - Section 2: Defense in Depth
  - Example 2: Security (3-layer validation for credentials)
  - Pre-commit security scan → Pre-push comprehensive scan → CI/CD recorded proof
  - No way to merge hardcoded credentials into main branch
- **CLAUDE.md** - Section 8: Security Guidelines
  - Pre-commit security scan commands
  - What NEVER to commit (files and patterns)
  - Full security checklist reference
- **CLAUDE.md** - Section 4, Pattern 4: Security
  - Security pattern examples (environment variables, validation, pre-commit scan)

**Tools:**
- TruffleHog: https://github.com/trufflesecurity/truffleHog
- git-secrets: https://github.com/awslabs/git-secrets
- gitleaks: https://github.com/gitleaks/gitleaks
- BFG Repo-Cleaner: https://reps.bfg-repo-cleaner.com/

**External References:**
- OWASP Top 10: https://owasp.org/Top10/
- GitHub Security Best Practices: https://docs.github.com/en/code-security
- .env Best Practices: https://github.com/motdotla/dotenv#should-i-commit-my-env-file

---

**END OF SECURITY REVIEW CHECKLIST V1.1**
