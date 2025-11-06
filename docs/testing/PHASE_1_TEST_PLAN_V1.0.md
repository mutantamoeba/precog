# Phase 1 Test Plan

---
**Version:** 1.0
**Created:** 2025-10-31
**Phase:** Phase 1 (Core Infrastructure - Kalshi API, CLI, Config)
**Status:** 📋 Planning Complete - Ready for Implementation
**Reference:** `docs/foundation/DEVELOPMENT_PHASES_V1.4.md` (Phase 1 Test Planning Checklist)

---

## Overview

This test plan outlines the comprehensive testing strategy for Phase 1 implementation, covering:
- Kalshi API client with RSA-PSS authentication
- CLI commands using Typer framework
- Configuration system (YAML + .env)
- Database CRUD operations (already 87% coverage - maintain)

**Test Planning Completed:** 2025-10-31
**Implementation Target:** December 2025 - January 2026
**Estimated Test Development:** ~2 weeks (parallel with implementation)

---

## 1. Requirements Analysis ✅

### API Requirements (REQ-API-001 through REQ-API-006)

**REQ-API-001: Kalshi API Integration**
- Implement REST client for Kalshi API
- Endpoints: `/markets`, `/events`, `/series`, `/portfolio/balance`, `/portfolio/positions`, `/portfolio/orders`
- Parse all prices from `*_dollars` fields as `Decimal` (CRITICAL - NOT cents, NOT float)
- Handle pagination for large responses
- **Critical Paths:**
  - RSA-PSS authentication (NOT HMAC-SHA256)
  - Decimal price parsing from JSON
  - Rate limiting (100 req/min)

**REQ-API-002: RSA-PSS Authentication**
- Use `cryptography` library for RSA-PSS signatures
- Token refresh every 30 minutes
- Private key loaded from environment variable (NEVER hardcoded)
- **Critical Paths:**
  - Signature validation
  - Token expiration handling
  - Credential security

**REQ-API-005: API Rate Limit Management**
- Track requests per minute (100 req/min limit)
- Implement throttling when approaching limit (80% threshold)
- Handle 429 (Too Many Requests) responses
- **Critical Paths:**
  - Thread-safe request counting
  - Rate limiter overhead <1ms per request

**REQ-API-006: API Error Handling**
- Exponential backoff retry logic (max 3 retries)
- Handle 4xx errors (client errors) - NO retry
- Handle 5xx errors (server errors) - retry with backoff
- Network timeout handling (30 second default)
- **Critical Paths:**
  - Retry logic correctness
  - Error message clarity

### CLI Requirements (REQ-CLI-001 through REQ-CLI-005)

**REQ-CLI-001: CLI Framework with Typer**
- Use Typer for type-safe CLI
- Auto-generated help text from docstrings
- Type hints for all arguments and options
- **Critical Paths:**
  - Argument validation
  - Help text generation

**REQ-CLI-002: Balance Fetch Command**
- `main.py fetch-balance` - Display account balance
- Output format: Human-readable with Decimal precision
- Error handling for API failures
- **Critical Paths:**
  - Decimal display (show 4 decimal places)
  - Connection error handling

**REQ-CLI-003: Positions Fetch Command**
- `main.py fetch-positions` - List current positions
- Table output with columns: Market, Side, Quantity, Entry Price, Current Price, P&L
- Filter options: --status (open/closed), --market
- **Critical Paths:**
  - Decimal precision in P&L calculation
  - Table formatting

**REQ-CLI-004: Fills Fetch Command**
- `main.py fetch-fills` - List trade fills
- Filter options: --market, --date-range
- **Critical Paths:**
  - Date parsing and filtering
  - API pagination handling

**REQ-CLI-005: Settlements Fetch Command**
- `main.py fetch-settlements` - List market settlements
- **Critical Paths:**
  - Settlement data parsing
  - Final market state handling

### System Requirements (REQ-SYS-001 through REQ-SYS-006)

**REQ-SYS-001: Database Schema Versioning**
- Already implemented with SCD Type 2 (database/ complete)
- Maintain 87% coverage baseline
- **Critical Paths:**
  - row_current_ind filtering (ALWAYS query with = TRUE)

**REQ-SYS-002: Configuration Management (YAML)**
- Three-tier precedence: Database overrides > YAML > Defaults
- YAML schema validation
- Decimal range validation (e.g., Kelly fractions 0.10-0.50)
- **Critical Paths:**
  - Config precedence resolution
  - Decimal value parsing from YAML
  - Environment variable substitution

**REQ-SYS-003: Decimal Precision for Prices**
- 100% of prices use Python Decimal (NEVER float)
- All database columns use DECIMAL(10,4)
- JSON parsing converts to Decimal immediately
- **Critical Paths:**
  - Type safety (prevent float contamination)
  - Arithmetic operations preserve Decimal type
  - Sub-penny precision (0.4275, 0.4976)

**REQ-SYS-006: Structured Logging**
- Already implemented with structlog (utils/logger.py complete)
- Decimal serialization working correctly
- **Critical Paths:**
  - No print() in production code (only logger.info())

### New Modules to Test

1. `api_connectors/kalshi_client.py` - Kalshi API client (NEW)
2. `main.py` - CLI entry point with Typer commands (NEW)
3. `config/config_loader.py` - Already exists, needs expansion for DB overrides

---

## 2. Test Categories ✅

### Unit Tests (≥80% coverage target)

**API Client Methods:**
- `KalshiClient.__init__()` - Load credentials from env
- `KalshiClient.authenticate()` - RSA-PSS signature generation
- `KalshiClient.refresh_token()` - Token refresh logic
- `KalshiClient.get_markets()` - Market data parsing (Decimal)
- `KalshiClient.get_balance()` - Balance parsing (Decimal)
- `KalshiClient.get_positions()` - Position data parsing
- `KalshiClient.get_fills()` - Fill data parsing
- `KalshiClient.get_settlements()` - Settlement data parsing
- `KalshiClient._make_request()` - Low-level HTTP with rate limiting
- `RateLimiter.acquire()` - Rate limit enforcement
- `RateLimiter.is_exceeded()` - Threshold detection

**CLI Argument Parsing:**
- `fetch_balance()` - Command with no args
- `fetch_positions()` - Command with --status and --market filters
- `fetch_fills()` - Command with date range filters
- `fetch_settlements()` - Command with market filter
- Error handling for invalid arguments

**Config Loading:**
- `ConfigLoader.load_config()` - YAML file loading
- `ConfigLoader.get_with_override()` - DB override precedence
- `ConfigLoader.validate_decimal_range()` - Range validation
- `ConfigLoader.substitute_env_vars()` - Env var substitution

**Decimal Conversion Utilities:**
- `parse_decimal_price()` - JSON → Decimal conversion
- `format_decimal_display()` - Decimal → string (4 decimal places)
- Type validation (reject float)

### Integration Tests (with mocking)

**API Client with Mocked HTTP Responses:**
- Mock successful API responses (200 OK) with sample JSON
- Mock 401 Unauthorized → trigger re-authentication
- Mock 429 Too Many Requests → trigger rate limit handling
- Mock 500 Server Error → trigger retry with exponential backoff
- Mock network timeout → trigger timeout handling
- Mock pagination (multiple pages of results)

**Database CRUD with Mocked Connections:**
- CLI commands should work without live database (use temp SQLite for CLI tests)
- Test config overrides stored in database
- Test SCD Type 2 versioning (row_current_ind queries)

**CLI Workflow End-to-End:**
- `fetch-balance` → API call → display output
- `fetch-positions --status open` → API call → filter → table display
- `fetch-fills --date-range 2025-01-01:2025-01-31` → API call → filter → display
- Error scenarios: API down, invalid credentials, network error

**Config Precedence Validation:**
- Test 1: YAML value only → use YAML
- Test 2: DB override exists → use DB value (ignore YAML)
- Test 3: Neither exists → use default
- Test 4: Env var substitution → ${API_KEY} → actual value

### Critical Tests (MUST PASS for Phase 1 completion)

1. **Decimal Precision Test:**
   - Parse sub-penny prices (0.4275, 0.4976) → verify exact Decimal
   - Arithmetic: (Decimal("0.4975") + Decimal("0.0025")) == Decimal("0.5000")
   - Type check: `isinstance(price, Decimal)` (NOT `isinstance(price, float)`)

2. **RSA-PSS Authentication Test:**
   - Generate signature with test private key
   - Verify signature matches expected format
   - Handle missing private key → clear error message

3. **Rate Limit Enforcement Test:**
   - Make 100 requests rapidly → all succeed
   - Make 101st request → delayed or rate limited
   - Verify throttling at 80% (80 req/min) → requests queued

4. **SQL Injection Prevention Test:**
   - Pass malicious input to CLI (e.g., `'; DROP TABLE markets;--`)
   - Verify parameterized queries prevent injection
   - Verify data is sanitized before database operations

### Mocking Strategy

**Mock All External Dependencies:**
- `requests.get()`, `requests.post()` → `@mock.patch('requests.get')`
- Database connections → use pytest fixture with temp SQLite
- File system → `@mock.patch('pathlib.Path.exists')`
- Environment variables → `@mock.patch.dict(os.environ, {...})`

**Sample API Responses (tests/fixtures/api_responses.py):**
```python
KALSHI_MARKET_RESPONSE = {
    "markets": [{
        "ticker": "NFL-KC-YES",
        "yes_bid_dollars": "0.5200",  # String in API response
        "yes_ask_dollars": "0.5250",
        "no_bid_dollars": "0.4750",
        "no_ask_dollars": "0.4800"
    }]
}

KALSHI_BALANCE_RESPONSE = {
    "balance_dollars": "1234.5678"
}
```

---

## 3. Test Infrastructure Updates ✅

### New Fixtures to Create

**File: `tests/fixtures/api_responses.py` (NEW)**
```python
"""Sample API responses for mocking."""
from decimal import Decimal

# Kalshi API responses (as returned by API - strings for dollars)
KALSHI_MARKET_RESPONSE = {...}
KALSHI_BALANCE_RESPONSE = {...}
KALSHI_POSITIONS_RESPONSE = {...}
KALSHI_FILLS_RESPONSE = {...}
KALSHI_ERROR_401_RESPONSE = {...}
KALSHI_ERROR_429_RESPONSE = {...}

# ESPN API responses
ESPN_GAME_RESPONSE = {...}

# Expected parsed results (after Decimal conversion)
EXPECTED_MARKET_DATA = {
    "ticker": "NFL-KC-YES",
    "yes_bid": Decimal("0.5200"),
    "yes_ask": Decimal("0.5250"),
    # ...
}
```

### Factory Updates

**File: `tests/fixtures/factories.py` (UPDATE)**
```python
# Add new factories

class KalshiAPIFactory:
    """Factory for creating mock Kalshi API clients."""
    @staticmethod
    def create(authenticated=True, rate_limited=False):
        client = KalshiClient()
        if authenticated:
            client._token = "mock_token_abc123"
            client._token_expires = datetime.now() + timedelta(minutes=30)
        return client

class CLICommandFactory:
    """Factory for creating CLI command test contexts."""
    @staticmethod
    def create_runner():
        from typer.testing import CliRunner
        return CliRunner()
```

### Config Test Files

**Directory: `tests/fixtures/sample_configs/` (NEW)**

**File: `valid_config.yaml`**
```yaml
trading:
  kelly_fraction: 0.25  # Will be converted to Decimal("0.25")
  max_position_size: 1000
  min_edge: 0.05

api:
  kalshi:
    base_url: "https://api.kalshi.com"
    timeout: 30
```

**File: `invalid_kelly.yaml`** (for error testing)
```yaml
trading:
  kelly_fraction: 0.75  # INVALID - must be 0.10-0.50
```

**File: `with_env_vars.yaml`**
```yaml
api:
  kalshi:
    api_key: ${KALSHI_API_KEY}  # Will be substituted from environment
```

### Conftest Updates

**File: `tests/conftest.py` (UPDATE)**
```python
# Add new fixtures

@pytest.fixture
def mock_kalshi_client(monkeypatch):
    """Mock KalshiClient with sample responses."""
    import requests_mock
    with requests_mock.Mocker() as m:
        # Mock successful market fetch
        m.get("https://api.kalshi.com/v1/markets",
              json=KALSHI_MARKET_RESPONSE)
        yield m

@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary directory with sample config files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Write valid config
    (config_dir / "trading.yaml").write_text("""
trading:
  kelly_fraction: 0.25
""")

    return config_dir

@pytest.fixture
def cli_runner():
    """Typer CLI test runner."""
    from typer.testing import CliRunner
    return CliRunner()
```

---

## 4. Critical Test Scenarios ✅

Based on user requirements and DEVELOPMENT_PHASES checklist:

### Scenario 1: API Client Fully Functional

**Test:** `test_kalshi_api_client_integration`
- Initialize client with env credentials
- Authenticate (generate RSA-PSS signature)
- Fetch markets → verify Decimal prices
- Fetch balance → verify Decimal balance
- Fetch positions → verify data structure
- All operations use Decimal (NOT float)

**Success Criteria:**
- 100% of prices are `Decimal` type
- API requests include valid authentication headers
- Rate limiter prevents exceeding 100 req/min

### Scenario 2: CLI Commands Validated

**Test:** `test_cli_fetch_balance`
- Run `main.py fetch-balance`
- Verify API called with correct endpoint
- Verify Decimal balance displayed correctly
- Test error handling (API down, invalid credentials)

**Test:** `test_cli_fetch_positions_with_filters`
- Run `main.py fetch-positions --status open`
- Verify filter applied correctly
- Verify table output formatted correctly

**Success Criteria:**
- All CLI commands execute without errors
- Help text generated automatically from docstrings
- Type validation working (invalid args rejected)

### Scenario 3: Config System with Precedence

**Test:** `test_config_precedence_db_overrides_yaml`
- Set kelly_fraction in YAML: 0.25
- Set DB override: kelly_fraction = 0.30
- Load config
- Verify result: Decimal("0.30") (DB override wins)

**Test:** `test_config_env_var_substitution`
- YAML: `api_key: ${KALSHI_API_KEY}`
- Env: `KALSHI_API_KEY=test_key_123`
- Load config
- Verify: `config['api_key'] == "test_key_123"`

**Success Criteria:**
- Config precedence: DB > YAML > default
- Decimal values parsed correctly from YAML
- Env var substitution working

### Scenario 4: Decimal Precision Maintained

**Test:** `test_decimal_precision_preserved`
- Parse API response: `{"yes_bid_dollars": "0.5275"}`
- Verify: `isinstance(price, Decimal)` and `price == Decimal("0.5275")`
- Arithmetic: `price + Decimal("0.0025") == Decimal("0.5300")`
- String conversion: `str(price)` preserves 4 decimals

**Test:** `test_reject_float_contamination`
- Attempt to pass float to Decimal field
- Verify type error or validation error
- Verify float never enters database

**Success Criteria:**
- 100% of price operations use Decimal
- Sub-penny precision maintained (0.4275, 0.4976)
- No float rounding errors

### Scenario 5: Unit Tests ≥80% Coverage

**Coverage Targets:**
- `api_connectors/kalshi_client.py`: ≥90%
- `main.py` (CLI): ≥85%
- `config/config_loader.py`: ≥85%
- `database/crud_operations.py`: ≥87% (maintain existing)

**Test Metrics:**
- Run `pytest --cov=. --cov-report=term-missing`
- Verify all critical modules meet targets
- Verify overall coverage ≥80%

**Success Criteria:**
- Automated coverage reporting in CI
- Coverage thresholds enforced by pyproject.toml
- No critical modules below target

---

## 5. Performance Baselines ✅

**API Client Request Processing:** <100ms (excluding network)
- Measure: Time from response received to Decimal parsing complete
- Test: `test_api_client_performance`
- Baseline: Parse 100 markets in <100ms total (<1ms each)

**CLI Startup Time:** <500ms
- Measure: Time from `python main.py` to first output
- Test: `test_cli_startup_performance`
- Baseline: Import time + Typer initialization <500ms

**Config File Loading:** <50ms
- Measure: Time to load and parse YAML files
- Test: `test_config_loading_performance`
- Baseline: Load 7 YAML files (trading.yaml, system.yaml, etc.) in <50ms

**Database Query (Single Record):** <10ms
- Already tested in Phase 0.7
- Maintain existing baseline

**Rate Limiter Overhead:** <1ms per request
- Measure: Time added by rate limiter checks
- Test: `test_rate_limiter_overhead`
- Baseline: 1000 rate limit checks in <1 second

---

## 6. Security Test Scenarios ✅

### API Credentials Security

**Test:** `test_api_keys_from_environment`
- Verify API keys loaded from `os.getenv('KALSHI_API_KEY')`
- Verify NO hardcoded keys in source code
- Test missing key → clear error message (NOT silent failure)

**Test:** `test_private_key_security`
- Verify RSA private key loaded from env variable
- Verify key NEVER logged or printed
- Test invalid key format → clear error

### RSA-PSS Authentication

**Test:** `test_rsa_pss_signature_generation`
- Generate signature with test private key
- Verify signature format (base64 encoded)
- Verify signature changes with different message
- Test signature validation with public key

**Test:** `test_authentication_token_refresh`
- Mock token expiration (set expiry to past)
- Make API request
- Verify automatic token refresh triggered
- Verify new token used for request

### Rate Limit Enforcement

**Test:** `test_rate_limit_prevents_api_abuse`
- Make 100 requests (at limit)
- Verify all succeed
- Make 101st request
- Verify rate limiter delays or rejects request

**Test:** `test_rate_limit_429_handling`
- Mock 429 (Too Many Requests) response
- Verify client backs off
- Verify retry after cooldown period

### SQL Injection Prevention

**Test:** `test_sql_injection_prevented`
- CLI input: `--market "'; DROP TABLE markets;--"`
- Verify parameterized query used
- Verify malicious input treated as data (NOT executed)

**Test:** `test_input_sanitization`
- Special characters in CLI args
- Verify proper escaping/validation
- Verify no code execution possible

### Credential Logging Prevention

**Test:** `test_no_credentials_in_logs`
- Make API request with authentication
- Capture log output
- Verify NO API keys or tokens in logs
- Verify error messages don't leak credentials

**Test:** `test_no_credentials_in_error_messages`
- Trigger authentication error
- Verify error message: "Invalid API key" (NOT actual key value)

---

## 7. Edge Cases to Test ✅

### API Error Handling

**Test:** `test_api_4xx_error_no_retry`
- Mock 400 Bad Request response
- Verify NO retry attempted (client error)
- Verify clear error message

**Test:** `test_api_5xx_error_retry_with_backoff`
- Mock 500 Server Error, then 500, then 200 success
- Verify retry attempted with exponential backoff
- Verify max 3 retries, then failure
- Verify backoff delays: 1s, 2s, 4s

**Test:** `test_api_rate_limit_429_handling`
- Mock 429 Too Many Requests
- Verify client backs off for Retry-After period
- Verify retry after cooldown

### Decimal Precision Edge Cases

**Test:** `test_sub_penny_precision`
- Parse prices: 0.4275, 0.4976, 0.0001, 0.9999
- Verify exact Decimal representation
- Arithmetic: Decimal("0.4975") + Decimal("0.0025") == Decimal("0.5000")

**Test:** `test_decimal_string_conversion`
- Decimal("0.5200") → "0.5200" (preserve trailing zeros)
- Display in CLI: "$0.5200" (4 decimal places)

**Test:** `test_decimal_arithmetic_precision`
- Spread calculation: ask - bid = exact difference
- P&L calculation: (exit_price - entry_price) * quantity
- Verify no rounding errors

### Config File Edge Cases

**Test:** `test_missing_yaml_file`
- Delete required YAML file
- Load config
- Verify clear error message: "File not found: trading.yaml"

**Test:** `test_malformed_yaml`
- Invalid YAML syntax (missing colon, bad indentation)
- Load config
- Verify YAML parse error with line number

**Test:** `test_invalid_decimal_range`
- kelly_fraction: 0.75 (INVALID - must be 0.10-0.50)
- Load config
- Verify validation error: "kelly_fraction must be between 0.10 and 0.50"

**Test:** `test_missing_env_variable`
- YAML: `api_key: ${MISSING_VAR}`
- Env: MISSING_VAR not set
- Load config
- Verify error: "Environment variable MISSING_VAR not found"

### Network Edge Cases

**Test:** `test_network_timeout`
- Mock request timeout (>30 seconds)
- Verify timeout exception raised
- Verify clear error message

**Test:** `test_network_connection_error`
- Mock connection refused (API server down)
- Verify connection error handled gracefully
- Verify user-friendly error message

### Token Expiration Edge Cases

**Test:** `test_expired_token_refresh`
- Set token expiry to past time
- Make API request
- Verify automatic refresh triggered BEFORE request
- Verify request succeeds with new token

**Test:** `test_concurrent_requests_token_refresh`
- Make 10 concurrent requests with expired token
- Verify only ONE token refresh (not 10)
- Verify all requests use refreshed token

### Config Precedence Edge Cases

**Test:** `test_db_override_precedence`
- YAML: kelly_fraction = 0.25
- DB override: kelly_fraction = 0.30
- Default: kelly_fraction = 0.20
- Result: Decimal("0.30") (DB wins)

**Test:** `test_yaml_over_default`
- YAML: kelly_fraction = 0.25
- No DB override
- Default: kelly_fraction = 0.20
- Result: Decimal("0.25") (YAML wins)

**Test:** `test_default_fallback`
- No YAML value
- No DB override
- Default: kelly_fraction = 0.20
- Result: Decimal("0.20") (default used)

---

## 8. Success Criteria ✅

### Coverage Targets (MANDATORY)

**Overall Coverage:** ≥80%
- Enforced by pyproject.toml
- Enforced by CI/CD (Phase 0.7)
- Codecov reporting enabled

**Critical Module Coverage:**
- `api_connectors/kalshi_client.py`: ≥90%
- `main.py` (CLI): ≥85%
- `config/config_loader.py`: ≥85%
- `database/crud_operations.py`: ≥87% (maintain existing baseline)

**Measurement:**
```bash
pytest --cov=. --cov-report=term-missing
```

### Test Quality Criteria

**All Critical Scenarios Tested:**
- [x] Decimal precision maintained (100% of prices)
- [x] RSA-PSS authentication working
- [x] Rate limiting enforced
- [x] Config precedence: DB > YAML > default
- [x] SQL injection prevented
- [x] API error handling (4xx, 5xx, timeout)

**All Edge Cases Covered:**
- [x] Sub-penny prices (0.4275, 0.4976)
- [x] Network errors and timeouts
- [x] Token expiration and refresh
- [x] Malformed YAML files
- [x] Missing environment variables
- [x] Concurrent API requests

### Test Performance

**Test Suite Execution Time:** <30 seconds locally
- Unit tests: <10 seconds
- Integration tests (with mocking): <20 seconds
- Run in parallel with pytest-xdist

**CI/CD Execution Time:** <5 minutes
- Matrix testing (4 combinations) in parallel
- Total time limited by slowest job

### Test Organization

**Pytest Markers:**
- `@pytest.mark.unit` - Fast unit tests (no external dependencies)
- `@pytest.mark.integration` - Integration tests (with mocking)
- `@pytest.mark.critical` - Must-pass tests for Phase 1 completion
- `@pytest.mark.slow` - Tests >1 second (run separately)

**File Organization:**
```
tests/
├── unit/
│   ├── test_kalshi_client_unit.py
│   ├── test_cli_parsing_unit.py
│   └── test_config_loader_unit.py
├── integration/
│   ├── test_kalshi_api_integration.py
│   ├── test_cli_workflow_integration.py
│   └── test_config_precedence_integration.py
├── fixtures/
│   ├── api_responses.py (NEW)
│   ├── factories.py (UPDATE)
│   └── sample_configs/ (NEW DIRECTORY)
└── conftest.py (UPDATE)
```

### Security Validation

**Zero Security Vulnerabilities:**
- Bandit scan: Clean (no issues)
- Safety scan: Clean (no vulnerable dependencies)
- Secret detection: No hardcoded credentials

**Manual Security Checks:**
- [x] API keys from environment (NOT hardcoded)
- [x] Private keys never logged
- [x] SQL injection tests pass
- [x] Input sanitization working
- [x] Error messages don't leak credentials

### Documentation

**API Usage Documentation:**
- Docstrings for all public methods
- Type hints for all parameters
- Usage examples in docstrings

**CLI Help Text:**
- Auto-generated from Typer docstrings
- All commands have --help output
- Examples provided for complex commands

**Test Documentation:**
- Each test has clear docstring explaining purpose
- Critical scenarios documented with rationale
- Edge cases documented with expected behavior

---

## Test Implementation Timeline

### Week 1: Test Infrastructure Setup
- [ ] Create `tests/fixtures/api_responses.py` with sample JSON responses
- [ ] Add `KalshiAPIFactory` and `CLICommandFactory` to `tests/fixtures/factories.py`
- [ ] Create `tests/fixtures/sample_configs/` directory with valid/invalid YAML files
- [ ] Update `tests/conftest.py` with new fixtures (mock_kalshi_client, temp_config_dir, cli_runner)
- [ ] Set up test organization (unit/ and integration/ directories)

### Week 2: Unit Tests (Parallel with Implementation)
- [ ] `test_kalshi_client_unit.py` - API client methods (≥90% coverage)
- [ ] `test_cli_parsing_unit.py` - CLI argument parsing (≥85% coverage)
- [ ] `test_config_loader_unit.py` - Config loading and precedence (≥85% coverage)
- [ ] `test_decimal_utils_unit.py` - Decimal conversion and validation

### Week 3: Integration Tests (Parallel with Implementation)
- [ ] `test_kalshi_api_integration.py` - API client with mocked HTTP responses
- [ ] `test_cli_workflow_integration.py` - End-to-end CLI workflows
- [ ] `test_config_precedence_integration.py` - Config system with DB/YAML/defaults
- [ ] `test_rate_limiter_integration.py` - Rate limiting with concurrent requests

### Week 4: Critical & Edge Case Tests
- [ ] `test_decimal_precision_critical.py` - Decimal precision tests (CRITICAL)
- [ ] `test_authentication_critical.py` - RSA-PSS auth tests (CRITICAL)
- [ ] `test_sql_injection_critical.py` - Security tests (CRITICAL)
- [ ] `test_edge_cases.py` - All edge cases from Section 7

### Week 5: Test Refinement & Coverage
- [ ] Run coverage analysis: `pytest --cov=. --cov-report=html`
- [ ] Identify uncovered lines and add tests
- [ ] Ensure all critical modules meet coverage targets
- [ ] Run full test suite: `pytest tests/ -v`
- [ ] Verify all tests pass in <30 seconds

### Week 6: Documentation & Validation
- [ ] Add docstrings to all test functions
- [ ] Document test fixtures and factories
- [ ] Run security scans (Bandit, Safety)
- [ ] Validate CI/CD integration
- [ ] Update SESSION_HANDOFF: "✅ Phase 1 test planning complete"

---

## Success Criteria Summary

**Phase 1 testing is complete when:**

- ✅ All critical scenarios tested and passing
- ✅ All edge cases covered
- ✅ Overall coverage ≥80% (enforced by CI)
- ✅ Critical module coverage:
  - kalshi_client.py: ≥90%
  - main.py: ≥85%
  - config_loader.py: ≥85%
- ✅ Test suite runs in <30 seconds
- ✅ Zero security vulnerabilities
- ✅ All tests marked with appropriate markers
- ✅ All tests passing in CI/CD (4 platform combinations)

---

## References

**Requirements Documents:**
- `docs/foundation/MASTER_REQUIREMENTS_V2.9.md` - All REQ-API, REQ-CLI, REQ-SYS requirements
- `docs/foundation/DEVELOPMENT_PHASES_V1.4.md` - Phase 1 test checklist

**Testing Infrastructure:**
- `docs/foundation/TESTING_STRATEGY_V2.0.md` - Comprehensive testing strategy
- `docs/testing/PHASE_TEST_PLANNING_TEMPLATE_V1.0.md` - 8-section checklist template

**API Documentation:**
- `docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md` - Kalshi/ESPN/Balldontlie APIs
- `docs/api-integration/KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md` - CRITICAL reference

**Existing Tests:**
- `tests/test_config_loader.py` - Config loader tests (87% coverage baseline)
- `tests/test_database_connection.py` - Database connection tests
- `tests/test_crud_operations.py` - CRUD operations tests (87% coverage)

---

**END OF PHASE 1 TEST PLAN V1.0**
