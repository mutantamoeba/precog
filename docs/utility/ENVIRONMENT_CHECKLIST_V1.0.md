# Environment Setup Checklist - Windows 11

---
**Version:** 1.0
**Created:** 2025-10-09
**Platform:** Windows 11
**Target:** Python 3.12 + PostgreSQL 15+ + Git + VSCode + Claude Code
**Time Required:** 2-3 hours first time
---

## Overview

This guide walks you through setting up your Windows 11 development environment from scratch. Even if you have some tools installed, follow each section to ensure everything is configured correctly.

**What You'll Install:**
1. Python 3.12
2. PostgreSQL 15
3. Git
4. Visual Studio Code
5. Claude Code CLI
6. Project dependencies

**Prerequisites:**
- Windows 11 (any edition)
- Administrator access
- Internet connection
- ~5 GB free disk space

---

## Part 1: Windows Terminal & Package Manager (15 min)

### Why This Matters
Windows Terminal is a modern command-line interface that's much better than the old Command Prompt. We'll use it for all command-line operations.

### Install Windows Terminal

**Already on Windows 11?** Windows Terminal comes pre-installed! Just search for "Terminal" in the Start menu.

**If not found:**
```powershell
# Open PowerShell as Administrator
# Search "PowerShell" → Right-click → "Run as Administrator"

# Install Windows Terminal
winget install Microsoft.WindowsTerminal
```

### Set PowerShell as Default

1. Open Windows Terminal
2. Press `Ctrl + ,` (opens Settings)
3. Under "Startup" → "Default profile" → Select "Windows PowerShell"
4. Click "Save"

### Enable Script Execution (IMPORTANT)

```powershell
# Open Windows Terminal as Administrator
# Run this command:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Type 'Y' and press Enter when prompted
```

**What this does:** Allows running Python scripts and development tools. Without this, many things won't work.

### Verify Winget is Working

```powershell
# Run this command:
winget --version

# Should see something like: v1.6.3482
# If error, restart your computer and try again
```

**What is winget?** Windows Package Manager - think of it like an app store for developers. Makes installing software much easier.

---

## Part 2: Python 3.12 Installation (20 min)

### Why Python 3.12?
This project uses Python 3.12 features and libraries. Older versions (3.10, 3.11) might work but aren't tested. Newer versions (3.13+) might have compatibility issues with some libraries.

### Install Python 3.12

```powershell
# Install Python 3.12
winget install Python.Python.3.12

# Verify installation (close and reopen Terminal first!)
python --version

# Should see: Python 3.12.x
```

**If `python` command not found:**
1. Close and reopen Windows Terminal
2. If still not found, search for "Edit system environment variables" in Start menu
3. Click "Environment Variables"
4. Under "System variables", find "Path"
5. Click "Edit" → "New" → Add: `C:\Users\[YourUsername]\AppData\Local\Programs\Python\Python312`
6. Add another: `C:\Users\[YourUsername]\AppData\Local\Programs\Python\Python312\Scripts`
7. Click "OK" on all windows
8. Close and reopen Terminal

### Upgrade pip (Python's Package Manager)

```powershell
# Upgrade pip to latest version
python -m pip install --upgrade pip

# Verify pip works
pip --version

# Should see: pip 24.x.x from ...
```

### Install pipx (For Claude Code)

```powershell
# Install pipx (manages Python CLI tools)
pip install pipx

# Add pipx to PATH
python -m pipx ensurepath

# Close and reopen Terminal

# Verify
pipx --version
```

**What is pipx?** It installs Python CLI tools in isolated environments, preventing version conflicts. Claude Code will be installed via pipx.

---

## Part 3: Git Installation (15 min)

### Why Git?
Version control system - tracks changes to your code, allows collaboration, and integrates with Claude Code.

### Install Git

```powershell
# Install Git
winget install Git.Git

# Close and reopen Terminal

# Verify installation
git --version

# Should see: git version 2.43.x
```

### Configure Git

```powershell
# Set your name (appears in commit history)
git config --global user.name "Your Name"

# Set your email
git config --global user.email "your.email@example.com"

# Set default branch name to 'main'
git config --global init.defaultBranch main

# Verify configuration
git config --global --list
```

### Configure Line Endings (IMPORTANT for Windows)

```powershell
# Windows uses CRLF line endings, Linux/Mac use LF
# This setting auto-converts so code works on all platforms
git config --global core.autocrlf true
```

### Generate SSH Key (Optional but Recommended)

If you plan to push code to GitHub/GitLab:

```powershell
# Generate SSH key
ssh-keygen -t ed25519 -C "your.email@example.com"

# Press Enter 3 times (default location, no passphrase)

# Display public key
type $env:USERPROFILE\.ssh\id_ed25519.pub

# Copy this output and add to GitHub: Settings → SSH Keys → New SSH Key
```

---

## Part 4: PostgreSQL Installation (30 min)

### Why PostgreSQL?
Production-grade database that handles the complex queries and data volumes this project requires. Free and open-source.

### Install PostgreSQL 15

**Option A: Using Winget (Recommended)**
```powershell
# Install PostgreSQL 15
winget install PostgreSQL.PostgreSQL.15

# During installation:
# - Note the password you set (YOU WILL NEED THIS!)
# - Accept default port: 5432
# - Accept default locale
# - Do not install Stack Builder (we don't need it)
```

**Option B: Manual Download**
1. Visit: https://www.postgresql.org/download/windows/
2. Download installer for Windows (version 15.x)
3. Run installer, use same settings as above

### Verify PostgreSQL is Running

```powershell
# Check if PostgreSQL service is running
Get-Service -Name postgresql*

# Should show Status: Running

# If not running:
Start-Service -Name postgresql-x64-15
```

### Add PostgreSQL to PATH

```powershell
# Test if psql command works
psql --version

# If error "command not found":
# 1. Search "Edit system environment variables" in Start menu
# 2. Click "Environment Variables"
# 3. Under "System variables", find "Path", click "Edit"
# 4. Click "New" and add: C:\Program Files\PostgreSQL\15\bin
# 5. Click OK on all windows
# 6. Close and reopen Terminal
# 7. Try again: psql --version
```

### Create Project Database

```powershell
# Connect to PostgreSQL as postgres superuser
psql -U postgres

# You'll be prompted for the password you set during installation
# Once connected (you'll see postgres=# prompt):

# Create the database
CREATE DATABASE precog_prod;

# Create a user for the application
CREATE USER precog_trader WITH PASSWORD 'your_secure_password_here';

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE precog_prod TO precog_trader;

# Exit psql
\q
```

### Verify Database Creation

```powershell
# Connect to the new database
psql -U precog_trader -d precog_prod

# Should see: precog_prod=#
# If successful, exit:
\q
```

### Install pgAdmin (Optional GUI)

If you prefer a graphical interface for database management:

```powershell
# Install pgAdmin
winget install PostgreSQL.pgAdmin
```

**Using pgAdmin:**
1. Open pgAdmin from Start menu
2. Right-click "Servers" → "Register" → "Server"
3. Name: "Precog"
4. Host: localhost
5. Port: 5432
6. Username: precog_trader
7. Password: [your password]

---

## Part 5: Visual Studio Code Setup (25 min)

### Install VSCode

```powershell
# Install Visual Studio Code
winget install Microsoft.VisualStudioCode

# Close and reopen Terminal

# Verify installation
code --version
```

### Essential VSCode Extensions

```powershell
# Install Python extension
code --install-extension ms-python.python

# Install Python Debugger
code --install-extension ms-python.debugpy

# Install Pylance (Python language server)
code --install-extension ms-python.vscode-pylance

# Install PostgreSQL extension
code --install-extension ckolkman.vscode-postgres

# Install YAML extension (for config files)
code --install-extension redhat.vscode-yaml

# Install Git Graph (visualize git history)
code --install-extension mhutchie.git-graph

# Install Error Lens (shows errors inline)
code --install-extension usernamehw.errorlens
```

### Configure VSCode for Python

1. Open VSCode
2. Press `Ctrl + Shift + P` (opens command palette)
3. Type "Python: Select Interpreter"
4. Choose Python 3.12.x

### Configure VSCode Settings

1. Press `Ctrl + ,` (opens Settings)
2. Search for each setting and configure:

```json
{
    // Python
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "python.languageServer": "Pylance",

    // Editor
    "editor.formatOnSave": true,
    "editor.rulers": [88, 120],
    "files.trimTrailingWhitespace": true,
    "files.insertFinalNewline": true,

    // Terminal
    "terminal.integrated.defaultProfile.windows": "PowerShell",

    // Git
    "git.autofetch": true,
    "git.confirmSync": false
}
```

**To edit as JSON:**
1. Press `Ctrl + Shift + P`
2. Type "Preferences: Open User Settings (JSON)"
3. Paste the above (merge with existing settings)

---

## Part 6: Claude Code Installation (20 min)

### What is Claude Code?

Claude Code is a command-line tool that lets you delegate coding tasks to Claude AI directly from your terminal. Think of it as an AI pair programmer that can:
- Read and write code files
- Run commands and tests
- Make architectural decisions
- Generate entire modules
- Debug issues

### Install Claude Code

```powershell
# Install Claude Code via pipx
pipx install claude-code

# Verify installation
claude-code --version
```

### Configure Claude Code API Key

1. Go to: https://console.anthropic.com/
2. Sign in (or create account)
3. Click "API Keys" in sidebar
4. Click "Create Key"
5. Copy the key (starts with `sk-ant-`)

```powershell
# Set API key as environment variable
# Open PowerShell as Administrator

# Add to your PowerShell profile (persistent):
notepad $PROFILE

# Add this line to the file:
$env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"

# Save and close

# Reload profile
. $PROFILE

# Verify
echo $env:ANTHROPIC_API_KEY
```

**Alternative: Use .env file (recommended for this project)**
We'll set this up later in the project-specific configuration.

### Test Claude Code

```powershell
# Create a test directory
mkdir test-claude-code
cd test-claude-code

# Initialize git (Claude Code requires git)
git init

# Test Claude Code
claude-code "Create a hello world Python script"

# You should see Claude Code create hello.py
# Check the file: type hello.py
```

### VSCode Integration with Claude Code

```powershell
# Install VSCode extension for Claude Code (if available)
# Check marketplace: Ctrl+Shift+X → Search "Claude Code"
```

**How to Use Claude Code:**
```powershell
# From project root:
claude-code "implement the MarketRepository class"
claude-code "write tests for edge_detector.py"
claude-code "debug the API authentication issue"
claude-code "explain how the Kelly Criterion sizing works"
```

**Best Practices:**
- Be specific in your requests
- Provide context (file names, error messages)
- Review generated code before committing
- Ask for explanations when learning
- Start with small tasks to build confidence

---

## Part 7: Project Setup (30 min)

### Create Project Directory

```powershell
# Navigate to where you want the project
cd C:\Users\[YourUsername]\Projects

# Create project directory
mkdir prescient
cd prescient

# Initialize git
git init
```

### Create Python Virtual Environment

**Why virtual environment?** Isolates project dependencies from system Python, preventing version conflicts.

```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate

# Your prompt should now show (venv) at the start
# This means you're in the virtual environment
```

**Important:** Always activate the virtual environment before working on the project!

```powershell
# To activate (do this every time you open Terminal for this project):
cd C:\Users\[YourUsername]\Projects\prescient
.\venv\Scripts\Activate

# To deactivate (when done working):
deactivate
```

### Create Project Structure

```powershell
# Create directory structure
mkdir src
mkdir src\api
mkdir src\database
mkdir src\models
mkdir src\trading
mkdir src\utils
mkdir config
mkdir logs
mkdir tests
mkdir docs
mkdir scripts

# Create empty __init__.py files (marks directories as Python packages)
New-Item -Path "src\__init__.py" -ItemType File
New-Item -Path "src\api\__init__.py" -ItemType File
New-Item -Path "src\database\__init__.py" -ItemType File
New-Item -Path "src\models\__init__.py" -ItemType File
New-Item -Path "src\trading\__init__.py" -ItemType File
New-Item -Path "src\utils\__init__.py" -ItemType File
```

### Create requirements.txt

```powershell
# Create requirements.txt with initial dependencies
@"
# Core dependencies
python-dotenv==1.0.0
pyyaml==6.0.1
psycopg2-binary==2.9.9
sqlalchemy==2.0.23
alembic==1.13.0

# API clients
requests==2.31.0
httpx==0.25.2
websockets==12.0

# Data processing
pandas==2.1.4
numpy==1.26.2

# Async support
aiohttp==3.9.1
asyncio==3.4.3

# Utilities
python-dateutil==2.8.2
pytz==2023.3

# Development tools
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
black==23.12.1
pylint==3.0.3
mypy==1.7.1

# Monitoring and logging
structlog==23.2.0
"@ | Out-File -FilePath requirements.txt -Encoding UTF8

# Install dependencies
pip install -r requirements.txt
```

**What each dependency does:**

| Package | Purpose |
|---------|---------|
| python-dotenv | Load environment variables from .env file |
| pyyaml | Parse YAML config files |
| psycopg2-binary | PostgreSQL database driver |
| sqlalchemy | ORM for database operations |
| alembic | Database migration tool |
| requests/httpx | HTTP client for API calls |
| websockets | WebSocket client for real-time data |
| pandas/numpy | Data manipulation and analysis |
| aiohttp/asyncio | Async HTTP and I/O |
| pytest | Testing framework |
| black | Code formatter |
| pylint | Code linter |
| structlog | Structured logging |

### Create .env Template

```powershell
# We'll create a comprehensive .env.template later
# For now, create a basic one:

@"
# Environment
TRADING_ENV=dev

# Database (Development)
DEV_DB_HOST=localhost
DEV_DB_PORT=5432
DEV_DB_NAME=precog_dev
DEV_DB_USER=precog_trader
DEV_DB_PASSWORD=your_password_here

# Database (Production)
PROD_DB_HOST=localhost
PROD_DB_PORT=5432
PROD_DB_NAME=precog_prod
PROD_DB_USER=precog_trader
PROD_DB_PASSWORD=your_password_here

# Kalshi API (we'll add these later)
KALSHI_API_KEY=
KALSHI_API_SECRET_PATH=

# Claude Code
ANTHROPIC_API_KEY=sk-ant-your-key-here
"@ | Out-File -FilePath .env -Encoding UTF8

# Add .env to .gitignore (IMPORTANT - never commit secrets!)
@"
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/

# Environment
.env
*.pem
*.key

# IDE
.vscode/
.idea/
*.swp
*.swo

# Database
*.db
*.sqlite

# Logs
logs/*.log

# OS
.DS_Store
Thumbs.db
"@ | Out-File -FilePath .gitignore -Encoding UTF8
```

### Configure VSCode for This Project

```powershell
# Create .vscode directory
mkdir .vscode

# Create settings.json
@"
{
    "python.defaultInterpreterPath": "${workspaceFolder}\\venv\\Scripts\\python.exe",
    "python.envFile": "${workspaceFolder}\\.env",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "tests"
    ],
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.organizeImports": true
        }
    },
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true
    }
}
"@ | Out-File -FilePath .vscode\settings.json -Encoding UTF8

# Create launch.json for debugging
@"
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Current File",
            "type": "python",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal",
            "envFile": "${workspaceFolder}\\.env"
        },
        {
            "name": "Python: Main",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}\\src\\main.py",
            "console": "integratedTerminal",
            "envFile": "${workspaceFolder}\\.env"
        }
    ]
}
"@ | Out-File -FilePath .vscode\launch.json -Encoding UTF8
```

---

## Part 8: Verification & Testing (15 min)

### System Health Check Script

Create a health check script to verify everything is working:

```powershell
# Create health_check.py
@"
#!/usr/bin/env python3
"""System health check script."""

import sys
import subprocess
from pathlib import Path

def check_python():
    version = sys.version_info
    if version.major == 3 and version.minor == 12:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    print(f"❌ Python {version.major}.{version.minor}.{version.micro} (need 3.12)")
    return False

def check_git():
    try:
        result = subprocess.run(['git', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    print("❌ Git not found")
    return False

def check_postgres():
    try:
        result = subprocess.run(['psql', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    print("❌ PostgreSQL not found")
    return False

def check_venv():
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ Virtual environment active")
        return True
    print("❌ Virtual environment not active (run: .\\venv\\Scripts\\Activate)")
    return False

def check_env_file():
    if Path('.env').exists():
        print("✅ .env file exists")
        return True
    print("❌ .env file not found")
    return False

def check_requirements():
    try:
        import dotenv
        import yaml
        import psycopg2
        import sqlalchemy
        import requests
        print("✅ Core dependencies installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        return False

def main():
    print("=== System Health Check ===\n")

    checks = [
        ("Python 3.12", check_python),
        ("Git", check_git),
        ("PostgreSQL", check_postgres),
        ("Virtual Environment", check_venv),
        (".env File", check_env_file),
        ("Dependencies", check_requirements),
    ]

    results = []
    for name, check in checks:
        results.append(check())

    print(f"\n=== Summary ===")
    passed = sum(results)
    total = len(results)
    print(f"{passed}/{total} checks passed")

    if passed == total:
        print("\n🎉 Environment is fully configured!")
        return 0
    else:
        print("\n⚠️  Some issues need attention")
        return 1

if __name__ == '__main__':
    sys.exit(main())
"@ | Out-File -FilePath health_check.py -Encoding UTF8

# Run health check
python health_check.py
```

### Test Database Connection

```powershell
# Create test_db.py
@"
#!/usr/bin/env python3
"""Test database connection."""

import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

try:
    conn = psycopg2.connect(
        host=os.getenv('DEV_DB_HOST', 'localhost'),
        port=os.getenv('DEV_DB_PORT', '5432'),
        database=os.getenv('DEV_DB_NAME', 'precog_prod'),
        user=os.getenv('DEV_DB_USER', 'precog_trader'),
        password=os.getenv('DEV_DB_PASSWORD')
    )
    print("✅ Database connection successful!")

    # Test query
    cur = conn.cursor()
    cur.execute('SELECT version();')
    version = cur.fetchone()
    print(f"PostgreSQL version: {version[0]}")

    cur.close()
    conn.close()

except Exception as e:
    print(f"❌ Database connection failed: {e}")
    print("\nCheck:")
    print("1. PostgreSQL service is running")
    print("2. Database exists: precog_prod")
    print("3. User exists: precog_trader")
    print("4. .env file has correct password")
"@ | Out-File -FilePath test_db.py -Encoding UTF8

# Run database test
python test_db.py
```

### Test Claude Code

```powershell
# Test Claude Code works with project
claude-code "create a simple hello world function in src/utils/hello.py"

# Check if file was created
if (Test-Path "src\utils\hello.py") {
    Write-Host "✅ Claude Code working!"
} else {
    Write-Host "❌ Claude Code test failed"
}
```

---

## Part 9: Daily Workflow (Reference)

### Starting Your Work Session

```powershell
# 1. Open Windows Terminal
# 2. Navigate to project
cd C:\Users\[YourUsername]\Projects\prescient

# 3. Activate virtual environment
.\venv\Scripts\Activate

# 4. Open VSCode
code .

# 5. Pull latest changes (if using Git)
git pull

# 6. Check system health (optional)
python health_check.py
```

### Ending Your Work Session

```powershell
# 1. Commit your changes
git add .
git commit -m "Description of changes"

# 2. Push to remote (if configured)
git push

# 3. Deactivate virtual environment
deactivate

# 4. Close VSCode and Terminal
```

---

## Troubleshooting

### "Command not found" errors

**Solution:** PATH environment variable issue
1. Restart Windows Terminal
2. If still failing, check Part 2 (Python), Part 3 (Git), or Part 4 (PostgreSQL) for PATH setup
3. Worst case: Restart computer

### "Permission denied" errors

**Solution:** Run as Administrator
1. Right-click Windows Terminal
2. Select "Run as Administrator"
3. Re-run the command

### Virtual environment won't activate

**Solution:**
```powershell
# Ensure you're in project directory
cd C:\Users\[YourUsername]\Projects\prescient

# Try activating with full path
C:\Users\[YourUsername]\Projects\prescient\venv\Scripts\Activate.ps1

# If still failing, check execution policy
Get-ExecutionPolicy
# Should be: RemoteSigned or Unrestricted

# If not, set it:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Database connection fails

**Checklist:**
1. Is PostgreSQL service running? `Get-Service postgresql*`
2. Can you connect with psql? `psql -U precog_trader -d precog_prod`
3. Is password correct in .env file?
4. Did you create the database? See Part 4, "Create Project Database"

### Claude Code not working

**Checklist:**
1. Is ANTHROPIC_API_KEY set? `echo $env:ANTHROPIC_API_KEY`
2. Is git initialized? `git status` (should not error)
3. Is Claude Code installed? `claude-code --version`
4. Try reinstalling: `pipx uninstall claude-code` then `pipx install claude-code`

### Import errors in Python

**Solution:** Dependencies not installed or wrong virtual environment

```powershell
# Ensure virtual environment is active
.\venv\Scripts\Activate

# Reinstall dependencies
pip install -r requirements.txt

# If specific package missing:
pip install package-name
```

---

## Quick Reference

### Common Commands

```powershell
# Virtual Environment
.\venv\Scripts\Activate          # Activate
deactivate                        # Deactivate

# Package Management
pip install package-name          # Install package
pip install -r requirements.txt   # Install all dependencies
pip list                          # List installed packages
pip freeze > requirements.txt     # Save current packages

# Database
psql -U precog_trader -d precog_prod    # Connect to DB
\dt                               # List tables (in psql)
\q                                # Quit psql

# Git
git status                        # Check changes
git add .                         # Stage all changes
git commit -m "message"           # Commit changes
git push                          # Push to remote
git pull                          # Pull from remote

# Claude Code
claude-code "your instruction"    # Run Claude Code
claude-code --help                # Show help

# Project
python health_check.py            # Check system health
python test_db.py                 # Test database connection
```

---

## Next Steps

Once everything is verified:

1. ✅ Review PROJECT_STATUS.md to understand project state
2. ✅ Review CONFIGURATION_GUIDE.md to understand system architecture
3. ✅ Create 7 YAML configuration files (next task)
4. ✅ Create .env.template with all API keys
5. ✅ Start Phase 1: Core Implementation

---

## Maintenance

### Keep Tools Updated

```powershell
# Update Python packages
pip install --upgrade pip
pip list --outdated
pip install --upgrade package-name

# Update Claude Code
pipx upgrade claude-code

# Update VSCode extensions
# Open VSCode → Extensions (Ctrl+Shift+X) → Click update icon
```

### Weekly Checklist

- [ ] Update pip packages
- [ ] Pull latest project changes
- [ ] Backup database (see DATABASE_SCHEMA_SUMMARY.md for backup commands)
- [ ] Review logs for errors

---

## Getting Help

**If stuck:**
1. Review this checklist - most issues are covered
2. Check error message carefully - often tells you exactly what's wrong
3. Search the error message online
4. Ask Claude (in chat or via Claude Code)
5. Review PROJECT_STATUS.md for known issues

**Common resources:**
- Python docs: https://docs.python.org/3.12/
- PostgreSQL docs: https://www.postgresql.org/docs/15/
- Git docs: https://git-scm.com/doc
- VSCode docs: https://code.visualstudio.com/docs
- Claude Code docs: https://docs.anthropic.com/claude-code

---

## Checklist Summary

Use this as a final verification:

**System:**
- [ ] Windows Terminal installed and configured
- [ ] PowerShell execution policy set
- [ ] Winget working

**Development Tools:**
- [ ] Python 3.12 installed and in PATH
- [ ] pip upgraded and working
- [ ] pipx installed
- [ ] Git installed and configured
- [ ] SSH key generated (optional)

**Database:**
- [ ] PostgreSQL 15 installed
- [ ] PostgreSQL service running
- [ ] psql command in PATH
- [ ] Project database created
- [ ] Can connect to database

**IDE:**
- [ ] VSCode installed
- [ ] Python extensions installed
- [ ] VSCode configured for project

**AI Assistant:**
- [ ] Claude Code installed
- [ ] ANTHROPIC_API_KEY configured
- [ ] Claude Code tested and working

**Project:**
- [ ] Project directory created
- [ ] Virtual environment created and activated
- [ ] Dependencies installed
- [ ] .env file created
- [ ] .gitignore created
- [ ] VSCode workspace configured
- [ ] Health check passes
- [ ] Database test passes

**Confidence Check:**
- [ ] I can open Terminal and activate venv
- [ ] I can run Python scripts
- [ ] I can connect to PostgreSQL
- [ ] I can use Git commands
- [ ] I can use Claude Code
- [ ] I can open the project in VSCode

---

**If ALL boxes checked:** 🎉 **You're ready to build!**

**If SOME boxes unchecked:** Review those sections and resolve issues.

**If MANY boxes unchecked:** Start over from Part 1 - something went wrong.

---

**END OF ENVIRONMENT CHECKLIST**

**Time to completion:** ~2-3 hours first time, ~30 min for updates/fixes

**This is a living document:** Update as you discover Windows 11-specific issues!
