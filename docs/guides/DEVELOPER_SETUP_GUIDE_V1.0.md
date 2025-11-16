# Developer Setup Guide

**Version:** 1.0
**Created:** 2025-11-16
**Last Updated:** 2025-11-16
**Purpose:** Complete guide for setting up Precog development environment
**Target Audience:** New developers joining the project

---

## Overview

This guide walks you through setting up your development environment for the Precog project, from installing required tools to verifying your setup is working correctly.

**Time to Complete:** ~2-3 hours (first-time setup)

**What You'll Install:**
- Python 3.12+
- PostgreSQL 15+
- Git
- GitHub CLI (gh)
- Pre-commit hooks
- Development tools (Ruff, Mypy, pytest)

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Python Setup](#python-setup)
3. [PostgreSQL Setup](#postgresql-setup)
4. [Git Setup](#git-setup)
5. [GitHub CLI Setup](#github-cli-setup)
6. [Repository Setup](#repository-setup)
7. [Pre-Commit Hooks](#pre-commit-hooks)
8. [Verification](#verification)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

**Operating Systems Supported:**
- Windows 10/11
- macOS 12+ (Monterey or later)
- Linux (Ubuntu 20.04+, Debian 11+, or equivalent)

**Required Permissions:**
- Administrator/sudo access (for installing tools)
- GitHub account with repository access
- Ability to install command-line tools

---

## Python Setup

### Python 3.12+ Installation

**Windows:**
```powershell
# Option 1: Microsoft Store (recommended)
# Search for "Python 3.12" in Microsoft Store and install

# Option 2: Winget
winget install Python.Python.3.12

# Option 3: Download from python.org
# Visit https://www.python.org/downloads/ and download Python 3.12+
```

**macOS:**
```bash
# Option 1: Homebrew (recommended)
brew install python@3.12

# Option 2: pyenv (for managing multiple Python versions)
brew install pyenv
pyenv install 3.12.0
pyenv global 3.12.0
```

**Linux (Ubuntu/Debian):**
```bash
# Add deadsnakes PPA (for latest Python versions)
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update

# Install Python 3.12
sudo apt install python3.12 python3.12-venv python3.12-dev

# Set as default (optional)
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
```

### Verify Installation

```bash
python --version
# Should show: Python 3.12.x

pip --version
# Should show: pip 23.x.x from ... (python 3.12)
```

**If `python` command not found:**
- Windows: Add Python to PATH (installer option "Add Python to PATH")
- macOS/Linux: Use `python3` instead of `python`

### Create Virtual Environment (Optional but Recommended)

```bash
# Navigate to project directory (after cloning - see Repository Setup)
cd precog-repo

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate

# macOS/Linux:
source venv/bin/activate

# Verify activation (should show (venv) in prompt)
which python  # macOS/Linux
where python  # Windows
```

---

## PostgreSQL Setup

### PostgreSQL 15+ Installation

**Windows:**
```powershell
# Option 1: Winget
winget install PostgreSQL.PostgreSQL.15

# Option 2: Download installer from postgresql.org
# Visit https://www.postgresql.org/download/windows/
# Download and run EDB installer (includes pgAdmin GUI)
```

**macOS:**
```bash
# Homebrew (recommended)
brew install postgresql@15

# Start PostgreSQL service
brew services start postgresql@15
```

**Linux (Ubuntu/Debian):**
```bash
# Add PostgreSQL APT repository
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt update

# Install PostgreSQL 15
sudo apt install postgresql-15 postgresql-client-15

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql  # Start on boot
```

### Create Precog Database

```bash
# Option 1: Using psql command-line
psql -U postgres -c "CREATE DATABASE precog;"

# Option 2: Using pgAdmin GUI (Windows)
# Open pgAdmin → Right-click Databases → Create → Database → Name: precog

# Option 3: Using createdb utility
createdb -U postgres precog
```

### Set Up Database User (Optional - for non-admin access)

```bash
psql -U postgres <<EOF
CREATE USER precog_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE precog TO precog_user;
EOF
```

### Apply Schema

```bash
# Navigate to project directory
cd precog-repo

# Apply database schema
psql -U postgres -d precog -f database/precog_schema_v1.7.sql

# Verify tables created
psql -U postgres -d precog -c "\dt"
# Should show 25 tables (platforms, series, events, markets, etc.)
```

**Full PostgreSQL setup guide:** See `docs/guides/POSTGRESQL_SETUP_GUIDE.md` for detailed instructions and troubleshooting.

---

## Git Setup

### Git Installation

**Windows:**
```powershell
# Option 1: Winget
winget install Git.Git

# Option 2: Download from git-scm.com
# Visit https://git-scm.com/download/win
```

**macOS:**
```bash
# Xcode Command Line Tools (includes Git)
xcode-select --install

# Or Homebrew
brew install git
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt install git
```

### Configure Git

```bash
# Set your identity
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Set default branch name
git config --global init.defaultBranch main

# Enable colored output
git config --global color.ui auto

# Set default editor (optional)
git config --global core.editor "code --wait"  # VS Code
# Or: nano, vim, emacs, etc.
```

### Verify Installation

```bash
git --version
# Should show: git version 2.x.x

git config --list
# Should show your name, email, etc.
```

---

## GitHub CLI Setup

**Purpose:** Required for issue tracking reconciliation and PR management.

### Installation

**Windows:**
```powershell
# Option 1: Winget (recommended)
winget install GitHub.cli

# Option 2: Scoop
scoop install gh

# Option 3: Download installer
# Visit https://cli.github.com/ and download .msi installer
```

**macOS:**
```bash
# Homebrew
brew install gh
```

**Linux (Ubuntu/Debian):**
```bash
# Add GitHub CLI repository
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update

# Install GitHub CLI
sudo apt install gh
```

### Authentication

```bash
# Authenticate with GitHub
gh auth login

# Follow interactive prompts:
# - What account do you want to log into? → GitHub.com
# - What is your preferred protocol? → HTTPS or SSH (your choice)
# - Authenticate Git with your GitHub credentials? → Yes
# - How would you like to authenticate? → Login with a web browser (recommended)

# Copy the one-time code displayed
# Press Enter to open browser
# Paste code in browser and authorize
```

### Verify Authentication

```bash
gh --version
# Should show: gh version 2.x.x

gh auth status
# Should show:
#   Logged in to github.com as <your-username>
#   Token: *******************
```

**Used By:**
- `scripts/reconcile_issue_tracking.sh` - Issue tracking reconciliation
- PR creation and management workflows
- CI/CD status checks

---

## Repository Setup

### Clone Repository

```bash
# Navigate to desired parent directory
cd ~/projects  # macOS/Linux
cd C:\projects  # Windows

# Clone repository (HTTPS)
git clone https://github.com/mutantamoeba/precog.git precog-repo

# Or clone with SSH (if you have SSH key set up)
git clone git@github.com:mutantamoeba/precog.git precog-repo

# Navigate into repository
cd precog-repo
```

### Install Python Dependencies

```bash
# Activate virtual environment (if using)
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt

# Verify installation
python -m pytest --version
python -m ruff --version
python -m mypy --version
```

**Key Dependencies Installed:**
- **pytest** - Testing framework
- **ruff** - Linter and formatter (replaces Black, Flake8, isort)
- **mypy** - Type checker
- **pre-commit** - Git hook framework
- **structlog** - Structured logging
- **hypothesis** - Property-based testing
- **psycopg2** - PostgreSQL adapter
- **pyyaml** - YAML configuration parser
- **python-dotenv** - Environment variable management

### Set Up Environment Variables

```bash
# Copy environment template
cp .env.template .env

# Edit .env file with your credentials
# Windows: notepad .env
# macOS/Linux: nano .env

# Required variables:
DATABASE_URL=postgresql://postgres:password@localhost:5432/precog
KALSHI_API_KEY=your_api_key_here
KALSHI_API_SECRET=your_api_secret_here
KALSHI_BASE_URL=https://api.kalshi.com/v1
```

**Security Note:**
- `.env` is in `.gitignore` - NEVER commit this file
- Store production credentials in secure vault (1Password, Azure Key Vault, etc.)
- Use different credentials for development and production

---

## Pre-Commit Hooks

Pre-commit hooks run automatically before every `git commit` to catch code quality issues early.

### Installation

```bash
# Install pre-commit framework (already in requirements.txt)
pip install pre-commit

# Install git hooks
pre-commit install

# Verify installation
pre-commit --version
# Should show: pre-commit 3.x.x

ls -la .git/hooks/pre-commit  # macOS/Linux
dir .git\hooks\pre-commit     # Windows
# Should exist and be executable
```

### Test Pre-Commit Hooks

```bash
# Run hooks on all files (initial check)
pre-commit run --all-files

# Expected output:
# Ruff Linter..................................................Passed
# Ruff Formatter...............................................Passed
# Mypy Type Checking...........................................Passed
# Security Scan (Hardcoded Credentials)........................Passed
# ... (12+ checks)
```

**What Hooks Check:**
1. ✅ Ruff linting (code quality)
2. ✅ Ruff formatting (auto-fix)
3. ✅ Mypy type checking
4. ✅ Security scan (hardcoded credentials)
5. ✅ Code review basics (REQ traceability)
6. ✅ Decimal precision check (Pattern 1 enforcement)
7. ✅ Trailing whitespace (auto-fix)
8. ✅ End-of-file newlines (auto-fix)
9. ✅ Mixed line endings (auto-fix CRLF→LF)
10. ✅ Large files check (>1MB)
11. ✅ Merge conflict markers
12. ✅ YAML/JSON syntax validation
13. ✅ Python AST validation
14. ✅ Debug statements (pdb, breakpoint)

**If hooks fail:**
- Fix the issues reported
- Re-run `git commit`
- Hooks auto-fix formatting issues (Ruff format, whitespace, line endings)

**Emergency bypass (NOT RECOMMENDED):**
```bash
git commit --no-verify
# Only use when hooks are blocking emergency fixes
# CI will still run all checks
```

---

## Verification

Run these commands to verify your setup is complete:

### 1. Python Environment

```bash
python --version
# Expected: Python 3.12.x

pip list | grep -E "(pytest|ruff|mypy)"
# Expected: pytest 8.x.x, ruff 0.x.x, mypy 1.x.x
```

### 2. Database Connection

```bash
python scripts/test_db_connection.py
# Expected:
# [OK] Successfully connected to database
# [OK] Database: precog
# [OK] 25 tables found
```

### 3. Tests Passing

```bash
python -m pytest tests/ -v
# Expected:
# ================== 391 passed, 9 skipped in X.XXs ==================
```

### 4. Code Quality

```bash
# Quick validation (Ruff, docs, Mypy)
bash scripts/validate_quick.sh
# Expected:
# [OK] QUICK VALIDATION PASSED
```

### 5. GitHub CLI

```bash
gh auth status
# Expected:
# Logged in to github.com as <your-username>

gh repo view mutantamoeba/precog
# Expected: Repository details displayed
```

### 6. Pre-Commit Hooks

```bash
# Create test commit
echo "# Test" >> README.md
git add README.md
git commit -m "test: Verify pre-commit hooks"
# Expected: All hooks pass, commit succeeds

# Undo test commit
git reset HEAD~1
git checkout README.md
```

---

## Troubleshooting

### Python Version Issues

**Problem:** `python` command not found
**Solution:**
```bash
# Use python3 instead
python3 --version

# Or add alias (macOS/Linux)
echo "alias python=python3" >> ~/.bashrc
source ~/.bashrc

# Windows: Add Python to PATH
# System Properties → Environment Variables → Path → Add Python installation directory
```

**Problem:** Wrong Python version (e.g., Python 3.9 instead of 3.12)
**Solution:**
```bash
# Use pyenv to manage multiple versions (macOS/Linux)
pyenv install 3.12.0
pyenv global 3.12.0

# Or use python3.12 explicitly
python3.12 -m venv venv
```

### PostgreSQL Connection Issues

**Problem:** `FATAL: password authentication failed for user "postgres"`
**Solution:**
```bash
# Reset postgres password
# Windows: Use pgAdmin GUI
# macOS/Linux:
sudo -u postgres psql
ALTER USER postgres WITH PASSWORD 'new_password';
\q

# Update DATABASE_URL in .env with new password
```

**Problem:** `psql: error: connection to server on socket "/tmp/.s.PGSQL.5432" failed`
**Solution:**
```bash
# Check if PostgreSQL is running
# Windows: Services → PostgreSQL → Start
# macOS: brew services start postgresql@15
# Linux: sudo systemctl start postgresql

# Verify service status
# macOS: brew services list
# Linux: sudo systemctl status postgresql
```

### Git/GitHub CLI Issues

**Problem:** `gh auth login` fails with "browser failed to open"
**Solution:**
```bash
# Use token authentication instead
gh auth login --with-token < your_token.txt

# Or manually paste token
gh auth login
# Choose: Paste an authentication token
```

**Problem:** `Permission denied (publickey)` when cloning with SSH
**Solution:**
```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "your.email@example.com"

# Add to GitHub
cat ~/.ssh/id_ed25519.pub
# Copy output and add at: https://github.com/settings/ssh/new

# Or use HTTPS instead
git clone https://github.com/mutantamoeba/precog.git
```

### Pre-Commit Hook Issues

**Problem:** Hooks fail with `ModuleNotFoundError: No module named 'ruff'`
**Solution:**
```bash
# Re-install pre-commit with dependencies
pip install pre-commit
pre-commit install --install-hooks
pre-commit run --all-files
```

**Problem:** Hooks stuck on "Initializing environment" for >5 minutes
**Solution:**
```bash
# Clear pre-commit cache
pre-commit clean
pre-commit install --install-hooks
```

### Test Failures

**Problem:** Tests fail with `psycopg2.OperationalError: FATAL: database "precog" does not exist`
**Solution:**
```bash
# Create database
createdb -U postgres precog

# Apply schema
psql -U postgres -d precog -f database/precog_schema_v1.7.sql
```

**Problem:** Import errors `ModuleNotFoundError: No module named 'precog'`
**Solution:**
```bash
# Install package in editable mode
pip install -e .

# Or run tests from project root
cd precog-repo
python -m pytest tests/
```

---

## Next Steps

After completing this setup:

1. **Read Project Documentation:**
   - `CLAUDE.md` - Project context and development patterns
   - `SESSION_HANDOFF.md` - Recent work and priorities
   - `docs/foundation/PROJECT_OVERVIEW_V1.4.md` - System architecture

2. **Review Development Workflow:**
   - `docs/guides/DEVELOPMENT_PATTERNS_V1.2.md` - Critical patterns (Decimal precision, versioning, security)
   - `docs/utility/DOCUMENTATION_WORKFLOW_GUIDE_V1.0.md` - Document consistency rules

3. **Run First Task:**
   - Check `SESSION_HANDOFF.md` for current priorities
   - Pick a small task to familiarize yourself with codebase
   - Create feature branch: `git checkout -b feature/your-task-name`
   - Make changes, commit, push, create PR

4. **Join Development Workflow:**
   - Pre-commit hooks run automatically before commit
   - Pre-push hooks run automatically before push
   - CI/CD runs on GitHub Actions after push
   - Branch protection requires passing CI before merge

---

## Getting Help

**Documentation:**
- `CLAUDE.md` - Main project context
- `docs/foundation/MASTER_INDEX_V2.11.md` - Complete document inventory
- `docs/guides/` - Implementation guides

**Common Issues:**
- Check `#troubleshooting` section above
- Search existing GitHub issues: `gh issue list`
- Check CI/CD logs for test failures

**Contact:**
- Create GitHub issue for setup problems
- Tag with `question` label
- Include error messages and environment details (OS, Python version, etc.)

---

**END OF DOCUMENT**
