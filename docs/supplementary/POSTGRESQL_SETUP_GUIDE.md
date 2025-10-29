# PostgreSQL User & Password Setup Guide

**Date:** 2025-10-17
**Purpose:** Guide for setting up PostgreSQL authentication for Precog project

---

## Current Situation

- ✅ PostgreSQL 18.0 is installed
- ✅ PostgreSQL service is running
- ❌ Authentication is blocking access (password required)
- ❌ Need to either find existing password or reset it

---

## Method 1: Find Your PostgreSQL Password (Windows)

### Check Installation Records

PostgreSQL on Windows may have stored the password during installation:

1. **Check Installation Log:**
   ```
   C:\Program Files\PostgreSQL\18\installation_log.txt
   ```

2. **Check Windows Credential Manager:**
   - Press `Win + R`, type: `control /name Microsoft.CredentialManager`
   - Look for "Generic Credentials" → "PostgreSQL"

3. **Check Environment Variables:**
   ```bash
   echo %PGPASSWORD%
   ```

---

## Method 2: Reset PostgreSQL Password (Recommended)

### Step 1: Locate pg_hba.conf

```bash
# Find PostgreSQL data directory
psql --version  # Shows version (18.0)

# Common location on Windows:
# C:\Program Files\PostgreSQL\18\data\pg_hba.conf
```

### Step 2: Edit pg_hba.conf to Allow Trust Authentication

**Location:** `C:\Program Files\PostgreSQL\18\data\pg_hba.conf`

Find this line:
```
# IPv4 local connections:
host    all             all             127.0.0.1/32            scram-sha-256
```

Change to:
```
# IPv4 local connections:
host    all             all             127.0.0.1/32            trust
```

**Also change this line:**
```
# IPv6 local connections:
host    all             all             ::1/128                 scram-sha-256
```

To:
```
# IPv6 local connections:
host    all             all             ::1/128                 trust
```

### Step 3: Restart PostgreSQL Service

```bash
# Stop PostgreSQL service
net stop postgresql-x64-18

# Start PostgreSQL service
net start postgresql-x64-18
```

### Step 4: Connect Without Password

```bash
# Should now work without password
psql -U postgres
```

### Step 5: Set New Password

Inside psql:
```sql
ALTER USER postgres WITH PASSWORD 'your_new_password_here';
```

### Step 6: Revert pg_hba.conf Back to Secure Settings

Change back from `trust` to `scram-sha-256`:
```
# IPv4 local connections:
host    all             all             127.0.0.1/32            scram-sha-256

# IPv6 local connections:
host    all             all             ::1/128                 scram-sha-256
```

### Step 7: Restart PostgreSQL Again

```bash
net stop postgresql-x64-18
net start postgresql-x64-18
```

### Step 8: Test New Password

```bash
psql -U postgres
# Enter your new password when prompted
```

---

## Method 3: Create New User Instead

If you don't want to use the `postgres` superuser:

```bash
# Connect as postgres (using Method 2 if needed)
psql -U postgres

# Create new user
CREATE USER precog_user WITH PASSWORD 'secure_password_here';

# Create database
CREATE DATABASE precog_dev OWNER precog_user;

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE precog_dev TO precog_user;

# Quit
\q
```

Then update `.env` file:
```bash
DB_USER=precog_user
DB_PASSWORD=secure_password_here
DB_NAME=precog_dev
```

---

## Method 4: Using Windows Authentication (Easiest)

PostgreSQL on Windows can use your Windows login:

### Step 1: Check if Windows Auth is Enabled

Check `pg_hba.conf` for:
```
# TYPE  DATABASE        USER            ADDRESS                 METHOD
host    all             all             127.0.0.1/32            sspi
```

### Step 2: If Not Enabled, Add It

Add this line to `pg_hba.conf`:
```
host    all             all             127.0.0.1/32            sspi
```

### Step 3: Restart PostgreSQL

```bash
net stop postgresql-x64-18
net start postgresql-x64-18
```

### Step 4: Connect Using Windows Auth

```bash
# Connect without -U flag (uses Windows user)
psql -d postgres

# Or with current Windows username
psql -U %USERNAME% -d postgres
```

---

## Quick Start: Simplest Approach

### For Development (Less Secure but Fast):

**1. Edit pg_hba.conf**
```
C:\Program Files\PostgreSQL\18\data\pg_hba.conf
```

**2. Change authentication to `trust` for local connections**
```
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
```

**3. Restart PostgreSQL**
```bash
net stop postgresql-x64-18
net start postgresql-x64-18
```

**4. Create database (no password needed now)**
```bash
createdb -U postgres precog_dev
```

**5. Update .env file**
```bash
DB_USER=postgres
DB_PASSWORD=
DB_NAME=precog_dev
```

**Note:** This is only for local development! For production, use secure password authentication.

---

## Verify Setup

Once you have authentication working, verify with:

```bash
# List databases
psql -U postgres -l

# Connect to precog_dev
psql -U postgres -d precog_dev

# Inside psql, check connection
\conninfo

# Should show: You are connected to database "precog_dev"
```

---

## Update .env File

After getting authentication working, update `.env`:

```bash
# PostgreSQL Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=precog_dev
DB_USER=postgres               # or your custom user
DB_PASSWORD=your_password_here # or empty if using trust auth
```

---

## Test Connection from Python

Run our test script:
```bash
cd C:\Users\emtol\Repos\precog-repo
.\venv\Scripts\activate
python test_db_connection.py
```

Should output:
```
✓ Connection successful!
✓ PostgreSQL version: PostgreSQL 18.0...
✓ Connected to database: precog_dev
✓ Database connection test PASSED
```

---

## Common Issues

### Issue 1: "password authentication failed"
- **Solution:** Use Method 2 (reset password) or Method 4 (Windows auth)

### Issue 2: "psql: command not found"
- **Solution:** Add PostgreSQL to PATH:
  ```
  C:\Program Files\PostgreSQL\18\bin
  ```

### Issue 3: "connection refused"
- **Solution:** PostgreSQL service not running:
  ```bash
  net start postgresql-x64-18
  ```

### Issue 4: Can't edit pg_hba.conf (permission denied)
- **Solution:** Run Notepad as Administrator:
  - Right-click Notepad → "Run as administrator"
  - Open `C:\Program Files\PostgreSQL\18\data\pg_hba.conf`

---

## Security Notes

- **Development:** `trust` authentication is acceptable for local development
- **Production:** Always use `scram-sha-256` with strong passwords
- **Password Storage:** Never commit passwords to git (`.env` is in `.gitignore`)
- **Access Control:** Restrict `pg_hba.conf` to localhost only (`127.0.0.1/32`)

---

## Next Steps After Setup

1. ✅ Verify database connection works
2. ✅ Update `.env` with correct credentials
3. ✅ Run `python test_db_connection.py` successfully
4. 🚀 Begin Phase 1 Task A1: Implement database schema

---

**Document:** POSTGRESQL_SETUP_GUIDE.md
**Created:** 2025-10-17
**Purpose:** PostgreSQL authentication setup for Precog project
**Status:** Instructions for user action

---

**END OF POSTGRESQL_SETUP_GUIDE.md**
