# Environment Configuration Guide V1.0

---
**Version:** 1.0
**Created:** 2025-12-11
**Status:** Active
**Purpose:** Comprehensive guide to Precog's two-axis environment configuration system
**Audience:** Developers, operators, system administrators
**Related Issue:** #202 (Two-Axis Environment Configuration)
**Related ADR:** ADR-105 (Two-Axis Environment Model)
---

## Table of Contents

1. [Overview](#overview)
2. [Two-Axis Model Explained](#two-axis-model-explained)
3. [Configuration Variables](#configuration-variables)
4. [Safety Guardrails](#safety-guardrails)
5. [CLI Usage](#cli-usage)
6. [Common Scenarios](#common-scenarios)
7. [Troubleshooting](#troubleshooting)

---

## Overview

Precog uses a **two-axis environment model** that independently controls:

1. **Application Environment (Axis 1)**: Database selection, logging, safety guards
2. **Market API Mode (Axis 2)**: API endpoints (demo vs live)

### Why Two Axes?

Database environments and API environments serve different purposes:

| Axis | Controls | Purpose |
|------|----------|---------|
| App Environment | Internal infrastructure | Database, logging, safety guards |
| Market Mode | External connections | API endpoints, real vs fake money |

This separation provides flexibility while maintaining safety. A developer might need:

- **Staging + Demo**: Safe pre-production testing
- **Dev + Live**: Debugging production issues (dangerous, requires confirmation)
- **Test + Demo**: Automated integration tests

---

## Two-Axis Model Explained

### Axis 1: Application Environment (PRECOG_ENV)

Controls which database and internal configuration is used.

| Value | Database | Description | Risk Level |
|-------|----------|-------------|------------|
| `dev` / `development` | `precog_dev` | Local development | Low |
| `test` | `precog_test` | Automated testing | Low |
| `staging` | `precog_staging` | Pre-production validation | Medium |
| `prod` / `production` | `precog_prod` | Live trading | **CRITICAL** |

**Detection Priority:**
1. `--app-env` CLI option (highest priority)
2. `PRECOG_ENV` environment variable
3. `DB_NAME` inference (from database name)
4. Default to `development` (safe default)

### Axis 2: Market API Mode (KALSHI_MODE)

Controls which API endpoints are used for prediction markets.

| Value | API Endpoint | Description | Financial Risk |
|-------|--------------|-------------|----------------|
| `demo` | Demo API | Fake money, safe for testing | None |
| `live` | Production API | Real money, actual trades | **FINANCIAL** |

**Detection:**
- `KALSHI_MODE` environment variable
- Default to `demo` (safe default if not set)

---

## Configuration Variables

### Required Variables

```bash
# Axis 1: Application Environment
PRECOG_ENV=dev  # Options: dev, test, staging, prod

# Axis 2: Market API Mode
KALSHI_MODE=demo  # Options: demo, live

# Database Connection
DB_HOST=localhost
DB_PORT=5432
DB_USER=<your_username>
DB_PASSWORD=<your_password>
```

### Optional Variables

```bash
# Override database name (usually derived from PRECOG_ENV)
DB_NAME=custom_database_name

# Connection pool settings
DB_POOL_MIN_CONN=2   # Minimum warm connections
DB_POOL_MAX_CONN=10  # Maximum connections

# Safety confirmation (required for dangerous combinations)
PRECOG_DANGEROUS_CONFIRMED=yes  # Required for dev/staging + live
PRECOG_PROD_CONFIRMED=yes       # Required for production access

# Logging
LOG_LEVEL=INFO  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### API Credentials

```bash
# Demo environment (for testing)
KALSHI_DEMO_API_KEY=<your_demo_api_key>
KALSHI_DEMO_KEYFILE=<path_to_demo_private_key.pem>

# Production environment (REAL MONEY)
KALSHI_PROD_API_KEY=<your_prod_api_key>
KALSHI_PROD_KEYFILE=<path_to_prod_private_key.pem>
```

---

## Safety Guardrails

### Combination Safety Matrix

| App Environment | Demo API | Live API |
|-----------------|----------|----------|
| Development | ALLOWED | WARNING |
| Test | ALLOWED | **BLOCKED** |
| Staging | ALLOWED | WARNING |
| Production | **BLOCKED** | ALLOWED |

### Blocked Combinations

These combinations are prevented at startup:

1. **Test + Live API**: Never test with real money
   - Reason: Automated tests could execute real trades
   - Error: `EnvironmentError: BLOCKED: Test environment must NEVER use live API`

2. **Production + Demo API**: Production must use real API
   - Reason: Demo API has no real markets
   - Error: `EnvironmentError: BLOCKED: Production environment must use live API`

### Warning Combinations

These combinations issue a warning but are allowed:

1. **Development + Live API**: Debugging production issues
   - Risk: Real money in development database
   - Warning: `UserWarning: Development database with LIVE API (real money!)`

2. **Staging + Live API**: Pre-production with real API
   - Risk: Real trades in staging environment
   - Warning: `UserWarning: Staging database with LIVE API (real money!)`

### Requiring Confirmation

For warning-level combinations, you can require explicit confirmation:

```python
from precog.config.environment import load_environment_config

# This will raise EnvironmentError if PRECOG_DANGEROUS_CONFIRMED is not set
config = load_environment_config(
    validate=True,
    require_confirmation=True
)
```

To confirm:
```bash
export PRECOG_DANGEROUS_CONFIRMED=yes
```

---

## CLI Usage

### Viewing Current Environment

```bash
# Show current two-axis configuration
python main.py env

# Show with environment variables
python main.py env --verbose
```

**Example Output:**
```
Two-Axis Environment Configuration

  Axis 1: Application Environment (Database)
+-----------------------------------------+
| Setting     | Value                     |
|-------------+---------------------------|
| Environment | development               |
| Database    | precog_dev                |
| Risk Level  | Low                       |
| Description | Local development         |
+-----------------------------------------+

  Axis 2: Market API Mode (Kalshi)
+-------------------------------------+
| Setting     | Value                 |
|-------------+-----------------------|
| Mode        | demo                  |
| Risk Level  | None                  |
| Description | Demo API (fake money) |
+-------------------------------------+

Combination Safety: ALLOWED
```

### Overriding Application Environment

Use `--app-env` to override the environment for a single command:

```bash
# Run command as if in staging environment
python main.py --app-env staging env

# Run command as if in production (careful!)
python main.py --app-env prod env
```

### Environment Variable Override

The CLI respects environment variables:

```bash
# Set environment for all commands in this shell
export PRECOG_ENV=staging
export KALSHI_MODE=demo

python main.py env
# Shows: staging + demo

# Override with CLI for single command
python main.py --app-env prod env
# Shows: prod + demo (CLI wins)
```

---

## Common Scenarios

### Scenario 1: Local Development (Safest)

```bash
# .env file
PRECOG_ENV=dev
KALSHI_MODE=demo
DB_NAME=precog_dev
```

Use case: Day-to-day development and testing

### Scenario 2: Running Automated Tests

```bash
# Set environment for test runner
export PRECOG_ENV=test
export KALSHI_MODE=demo

# Run tests
python -m pytest tests/
```

Use case: CI/CD pipeline, local test runs

### Scenario 3: Pre-Production Validation

```bash
# .env file
PRECOG_ENV=staging
KALSHI_MODE=demo
```

Use case: Testing new features before production

### Scenario 4: Production Trading

```bash
# .env file
PRECOG_ENV=prod
KALSHI_MODE=live
PRECOG_PROD_CONFIRMED=yes
```

Use case: Actual live trading with real money

### Scenario 5: Debugging Production Issues

```bash
# Temporarily use live API with dev database
# WARNING: This involves real money!
export PRECOG_ENV=dev
export KALSHI_MODE=live
export PRECOG_DANGEROUS_CONFIRMED=yes

# Now commands use dev database but live API
python main.py fetch-balance
```

Use case: Investigating production API issues without affecting production database

---

## Troubleshooting

### Error: "BLOCKED: Test environment must NEVER use live API"

**Cause:** `PRECOG_ENV=test` with `KALSHI_MODE=live`

**Solution:** Test environments should only use demo API:
```bash
export KALSHI_MODE=demo
```

### Error: "BLOCKED: Production environment must use live API"

**Cause:** `PRECOG_ENV=prod` with `KALSHI_MODE=demo`

**Solution:** Production must use live API:
```bash
export KALSHI_MODE=live
```

### Warning: "Development database with LIVE API (real money!)"

**Cause:** `PRECOG_ENV=dev` with `KALSHI_MODE=live`

**If intentional:** Set confirmation:
```bash
export PRECOG_DANGEROUS_CONFIRMED=yes
```

**If unintentional:** Switch to demo:
```bash
export KALSHI_MODE=demo
```

### Error: "Invalid --app-env value"

**Cause:** Invalid environment string passed to CLI

**Solution:** Use valid values: `dev`, `test`, `staging`, `prod`
```bash
python main.py --app-env dev env  # Correct
python main.py --app-env local env  # Wrong
```

### Database Connection Issues

If database connection fails after changing environment:

1. Verify the database exists:
   ```bash
   psql -l | grep precog
   ```

2. Check database name matches environment:
   ```bash
   python main.py env --verbose
   # Look at "DB_NAME" in Environment Variables
   ```

3. Ensure credentials are correct in `.env` file

---

## Architecture Reference

### Module Locations

- **Environment Configuration:** `src/precog/config/environment.py`
- **Database Connection:** `src/precog/database/connection.py`
- **Kalshi Client:** `src/precog/api_connectors/kalshi_client.py`
- **CLI Entry Point:** `main.py`

### Key Functions

```python
# Get current application environment
from precog.config.environment import get_app_environment
app_env = get_app_environment()  # Returns AppEnvironment enum

# Get market API mode
from precog.config.environment import get_market_mode
kalshi_mode = get_market_mode("kalshi")  # Returns MarketMode enum

# Load full configuration with validation
from precog.config.environment import load_environment_config
config = load_environment_config(validate=True)

# Require specific environment (raises RuntimeError if mismatch)
from precog.config.environment import require_app_environment
require_app_environment(AppEnvironment.PRODUCTION)
```

### Test Coverage

- **Unit Tests:** `tests/unit/config/test_environment.py` (71 tests)
- **Integration Tests:** `tests/integration/config/test_environment_integration.py` (21 tests)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-11 | Initial release with two-axis environment model |

---

**END OF ENVIRONMENT_CONFIGURATION_GUIDE_V1.0.md**
