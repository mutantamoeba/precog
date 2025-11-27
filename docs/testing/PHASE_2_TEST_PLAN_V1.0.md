# Phase 2 Test Plan - Live Data Integration

**Version:** 1.0
**Created:** 2025-11-27
**Phase:** Phase 2 (Codename: "Observer")
**Status:** 🔵 Approved - Ready for Implementation
**Purpose:** Comprehensive test planning for ESPN API Client, Task Scheduler, Data Quality Validation, and Historical Backfill

---

## Document Purpose

This document provides a complete test plan for Phase 2 deliverables, created BEFORE implementation begins (following CLAUDE.md mandate: "DO NOT write production code until test planning complete").

**Reference Documents:**
- `docs/foundation/DEVELOPMENT_PHASES_V1.6.md` (Phase 2 specification, lines 954-1110)
- `docs/foundation/TESTING_STRATEGY_V3.1.md` (8 test types, coverage tiers)
- `scripts/validation_config.yaml` (Phase 2 deliverables, coverage targets)
- `docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md` (ESPN API integration patterns)

---

## Table of Contents

1. [Requirements Analysis](#1-requirements-analysis)
2. [Test Categories by Deliverable](#2-test-categories-by-deliverable)
3. [Test Infrastructure](#3-test-infrastructure)
4. [Critical Test Scenarios](#4-critical-test-scenarios)
5. [Edge Cases](#5-edge-cases)
6. [Performance Baselines](#6-performance-baselines)
7. [Security Test Scenarios](#7-security-test-scenarios)
8. [Success Criteria](#8-success-criteria)

---

## 1. Requirements Analysis

### Phase 2 Deliverables (from DEVELOPMENT_PHASES_V1.6.md)

| Deliverable | File | Coverage Target | Test Types |
|-------------|------|-----------------|------------|
| ESPN API Client | `src/precog/api_connectors/espn_client.py` | ≥85% | Unit, Property, Integration, Stress, E2E |
| Task Scheduler | `src/precog/schedulers/market_updater.py` | ≥85% | Unit, Integration, Stress, Race Condition |
| Data Quality Validator | `src/precog/data/quality_validator.py` | ≥80% | Unit, Property, Integration, Stress |
| Historical Backfill | `scripts/backfill_nflfastr.py` | ≥75% | Unit, Integration, Stress |
| Game States CRUD | `src/precog/database/crud_operations.py` | ≥85% | Unit, Property, Integration, Race Condition |

### Relevant Requirements

**Live Data Requirements (to be created as REQs during implementation):**
- **REQ-DATA-001:** ESPN API Integration
  - Fetch NFL/NCAAF scoreboard data
  - Parse game state (scores, period, time remaining, status)
  - Rate limiting (500 req/hour limit)

- **REQ-DATA-002:** Data Freshness Validation
  - Reject stale data (>60 seconds old)
  - Timestamp validation on all game state updates
  - Log warning when data is older than threshold

- **REQ-DATA-003:** Historical Data Backfill
  - Load nflfastR data (2019-2024 seasons)
  - Populate odds_matrices table
  - Deduplicate and validate data quality

- **REQ-SCHED-001:** Task Scheduling
  - APScheduler 3.10+ implementation
  - Poll ESPN every 15 seconds during active games
  - Conditional polling (only when games live)

**Supporting Requirements (existing):**
- **REQ-DB-003:** SCD Type 2 Tracking (game_states table)
- **REQ-SYS-003:** Decimal Precision (all probabilities/prices)
- **Pattern 2:** Dual Versioning (row_current_ind filtering)

---

## 2. Test Categories by Deliverable

### 2.1 ESPN API Client (`api_connectors/espn_client.py`)

**Unit Tests** (target: 20+ tests)
```python
# tests/unit/api_connectors/test_espn_client.py

# Response Parsing
def test_parse_nfl_scoreboard_returns_games(): ...
def test_parse_ncaaf_scoreboard_returns_games(): ...
def test_parse_game_state_extracts_scores(): ...
def test_parse_game_state_extracts_period(): ...
def test_parse_game_state_extracts_time_remaining(): ...
def test_parse_game_status_active(): ...
def test_parse_game_status_final(): ...
def test_parse_game_status_scheduled(): ...
def test_parse_game_status_halftime(): ...

# Error Handling
def test_invalid_json_raises_parsing_error(): ...
def test_missing_fields_uses_defaults(): ...
def test_malformed_timestamp_logs_warning(): ...

# Decimal Conversion (Pattern 1)
def test_win_probability_returns_decimal(): ...
def test_spread_returns_decimal(): ...
```

**Property Tests** (target: 5+ properties)
```python
# tests/property/api_connectors/test_espn_client_properties.py

@given(st.integers(min_value=0, max_value=100))
def test_scores_always_non_negative(home_score, away_score): ...

@given(game_status_strategy())
def test_status_always_valid_enum(status): ...

@given(st.datetimes())
def test_timestamp_always_parseable(timestamp): ...

@given(st.decimals(min_value=0, max_value=1, places=4))
def test_probability_always_valid_range(prob): ...
```

**Integration Tests** (target: 10+ tests)
```python
# tests/integration/api_connectors/test_espn_client_integration.py

@pytest.mark.integration
def test_fetch_nfl_scoreboard_real_api(): ...

@pytest.mark.integration
def test_fetch_ncaaf_scoreboard_real_api(): ...

@pytest.mark.integration
def test_rate_limit_respected(): ...

@pytest.mark.integration
def test_api_error_retry_behavior(): ...
```

**Stress Tests** (target: 3+ tests)
```python
# tests/stress/api_connectors/test_espn_rate_limits.py

@pytest.mark.stress
def test_500_requests_within_hour_limit(): ...

@pytest.mark.stress
def test_concurrent_requests_thread_safe(): ...

@pytest.mark.stress
def test_sustained_polling_15_second_intervals(): ...
```

**E2E Tests** (target: 2+ tests)
```python
# tests/e2e/test_live_data_pipeline.py

@pytest.mark.e2e
def test_complete_data_pipeline_nfl_game(): ...

@pytest.mark.e2e
def test_game_state_stored_in_database(): ...
```

### 2.2 Task Scheduler (`schedulers/market_updater.py`)

**Unit Tests** (target: 15+ tests)
```python
# tests/unit/schedulers/test_market_updater.py

# Job Configuration
def test_create_polling_job_with_interval(): ...
def test_create_conditional_job(): ...
def test_job_executes_at_correct_interval(): ...

# Conditional Logic
def test_skip_polling_when_no_active_games(): ...
def test_resume_polling_when_games_start(): ...
def test_game_detection_logic(): ...

# State Management
def test_job_state_persisted(): ...
def test_job_history_logged(): ...
```

**Integration Tests** (target: 5+ tests)
```python
# tests/integration/schedulers/test_scheduler_integration.py

@pytest.mark.integration
def test_apscheduler_job_execution(): ...

@pytest.mark.integration
def test_scheduler_database_interaction(): ...

@pytest.mark.integration
def test_job_failure_recovery(): ...
```

**Stress Tests** (target: 3+ tests)
```python
# tests/stress/schedulers/test_concurrent_jobs.py

@pytest.mark.stress
def test_50_concurrent_game_updates(): ...

@pytest.mark.stress
def test_sustained_15_second_polling_1_hour(): ...

@pytest.mark.stress
def test_scheduler_under_memory_pressure(): ...
```

**Race Condition Tests** (target: 3+ tests)
```python
# tests/race_condition/schedulers/test_job_overlap.py

@pytest.mark.race_condition
def test_overlapping_jobs_handled(): ...

@pytest.mark.race_condition
def test_concurrent_database_writes(): ...

@pytest.mark.race_condition
def test_scheduler_shutdown_during_job(): ...
```

### 2.3 Data Quality Validator (`data/quality_validator.py`)

**Unit Tests** (target: 15+ tests)
```python
# tests/unit/data/test_quality_validator.py

# Timestamp Validation
def test_reject_stale_data_over_60_seconds(): ...
def test_accept_fresh_data_under_60_seconds(): ...
def test_timestamp_format_validation(): ...

# Data Consistency
def test_scores_monotonic_increasing(): ...
def test_period_transitions_logical(): ...
def test_game_status_valid_enum(): ...

# Missing Data
def test_missing_required_fields_rejected(): ...
def test_optional_fields_have_defaults(): ...
def test_graceful_degradation_partial_data(): ...
```

**Property Tests** (target: 5+ properties)
```python
# tests/property/data/test_quality_validator_properties.py

@given(timestamp_strategy())
def test_timestamp_validation_deterministic(ts): ...

@given(st.lists(st.integers(min_value=0), min_size=2))
def test_score_monotonicity_property(scores): ...

@given(game_state_strategy())
def test_validation_always_returns_bool(state): ...
```

**Integration Tests** (target: 5+ tests)
```python
# tests/integration/data/test_quality_validator_integration.py

@pytest.mark.integration
def test_validator_with_real_espn_response(): ...

@pytest.mark.integration
def test_validator_database_logging(): ...

@pytest.mark.integration
def test_alert_on_quality_anomalies(): ...
```

### 2.4 Historical Backfill (`scripts/backfill_nflfastr.py`)

**Unit Tests** (target: 10+ tests)
```python
# tests/unit/scripts/test_backfill_nflfastr.py

# Data Parsing
def test_parse_nflfastr_csv(): ...
def test_map_game_situation_to_odds(): ...
def test_decimal_conversion_win_probability(): ...

# Deduplication
def test_detect_duplicate_records(): ...
def test_upsert_logic(): ...

# Data Validation
def test_season_range_validation(): ...
def test_required_columns_present(): ...
```

**Integration Tests** (target: 3+ tests)
```python
# tests/integration/scripts/test_backfill_integration.py

@pytest.mark.integration
def test_backfill_single_season_to_database(): ...

@pytest.mark.integration
def test_odds_matrices_table_populated(): ...

@pytest.mark.integration
def test_backfill_idempotent(): ...
```

**Stress Tests** (target: 2+ tests)
```python
# tests/stress/scripts/test_backfill_stress.py

@pytest.mark.stress
def test_backfill_5_years_under_10_minutes(): ...

@pytest.mark.stress
def test_backfill_memory_usage_bounded(): ...
```

---

## 3. Test Infrastructure

### New Fixtures Required

```python
# tests/fixtures/espn_responses.py

ESPN_NFL_SCOREBOARD_SAMPLE = {
    "events": [
        {
            "id": "401547417",
            "name": "Kansas City Chiefs at Buffalo Bills",
            "status": {"type": {"state": "in", "completed": False}},
            "competitions": [{
                "competitors": [
                    {"team": {"abbreviation": "BUF"}, "score": "14"},
                    {"team": {"abbreviation": "KC"}, "score": "21"}
                ],
                "situation": {"lastPlay": {...}, "downDistanceText": "2nd & 7"}
            }]
        }
    ]
}

ESPN_NCAAF_SCOREBOARD_SAMPLE = {...}
ESPN_GAME_FINAL_SAMPLE = {...}
ESPN_GAME_PREGAME_SAMPLE = {...}
```

```python
# tests/fixtures/factories.py

class ESPNGameFactory(factory.Factory):
    class Meta:
        model = dict

    id = factory.Sequence(lambda n: f"40154{n}")
    home_team = factory.Faker("random_element", elements=["BUF", "KC", "NE", "MIA"])
    away_team = factory.Faker("random_element", elements=["DAL", "NYG", "PHI", "WSH"])
    home_score = factory.Faker("random_int", min=0, max=50)
    away_score = factory.Faker("random_int", min=0, max=50)
    period = factory.Faker("random_int", min=1, max=4)
    status = factory.Faker("random_element", elements=["pre", "in", "post"])
```

```python
# tests/fixtures/mock_scheduler.py

class MockAPScheduler:
    """Mock APScheduler for testing job execution without real scheduling."""

    def __init__(self):
        self.jobs = []
        self.executed_jobs = []

    def add_job(self, func, trigger, **kwargs):
        job_id = kwargs.get("id", f"job_{len(self.jobs)}")
        self.jobs.append({"func": func, "trigger": trigger, "id": job_id})
        return job_id

    def execute_job_now(self, job_id):
        """Execute a job immediately for testing."""
        job = next((j for j in self.jobs if j["id"] == job_id), None)
        if job:
            job["func"]()
            self.executed_jobs.append(job_id)
```

### conftest.py Updates

```python
# tests/conftest.py additions

@pytest.fixture
def espn_mock_responses():
    """Provide mock ESPN API responses for testing."""
    return {
        "nfl_scoreboard": ESPN_NFL_SCOREBOARD_SAMPLE,
        "ncaaf_scoreboard": ESPN_NCAAF_SCOREBOARD_SAMPLE,
        "game_final": ESPN_GAME_FINAL_SAMPLE,
        "game_pregame": ESPN_GAME_PREGAME_SAMPLE,
    }

@pytest.fixture
def mock_scheduler():
    """Provide mock APScheduler for testing."""
    return MockAPScheduler()

@pytest.fixture
def game_state_factory():
    """Provide ESPNGameFactory for generating test game states."""
    return ESPNGameFactory

@pytest.fixture
async def async_event_loop():
    """Provide event loop for async tests (pytest-asyncio)."""
    loop = asyncio.get_event_loop()
    yield loop
```

### Validation Script Updates

Update `scripts/validate_schema_consistency.py` (~5 min):
- [ ] Add `game_states` table to `versioned_tables` list (SCD Type 2 table)
- [ ] Add any new price columns if tables have financial data

---

## 4. Critical Test Scenarios

### From DEVELOPMENT_PHASES_V1.6.md Section "Critical Test Scenarios"

| # | Scenario | Test Type | Priority |
|---|----------|-----------|----------|
| 1 | Live feed ingestion with mocked ESPN streams | Integration | 🔴 Critical |
| 2 | Async event loop stress/concurrency tests | Stress | 🔴 Critical |
| 3 | Failover/retry for REST endpoints | Integration | 🟡 High |
| 4 | SCD Type-2 validation for game state updates | Property | 🔴 Critical |
| 5 | End-to-end pipeline (ESPN API → parsing → validation → DB) | E2E | 🔴 Critical |
| 6 | APScheduler job reliability (1 hour sustained) | Stress | 🟡 High |
| 7 | Historical backfill (5 years under 10 min) | Stress | 🟢 Medium |

### Critical Test Implementations

```python
# Critical Test 1: Live feed ingestion
@pytest.mark.integration
@pytest.mark.critical
def test_live_feed_ingestion_with_mocked_espn(db_pool, espn_mock_responses):
    """Verify data flows from mocked ESPN API to game_states table."""
    # 1. Set up mock ESPN response
    # 2. Call ESPN client to fetch data
    # 3. Process through quality validator
    # 4. Insert into game_states table
    # 5. Verify data stored correctly with SCD Type 2

# Critical Test 2: Async concurrency
@pytest.mark.stress
@pytest.mark.critical
async def test_async_50_concurrent_game_updates(async_event_loop, db_pool):
    """Handle 50+ concurrent game updates without lag."""
    # 1. Create 50 mock game state updates
    # 2. Submit all concurrently
    # 3. Verify all complete within 2 seconds
    # 4. Verify no data corruption

# Critical Test 4: SCD Type 2 validation
@pytest.mark.property
@pytest.mark.critical
@given(game_state_strategy())
def test_scd_type2_row_current_ind_property(state, db_pool):
    """Verify row_current_ind logic for game state updates."""
    # 1. Insert initial state (row_current_ind = TRUE)
    # 2. Update state (old row = FALSE, new row = TRUE)
    # 3. Verify only ONE row has row_current_ind = TRUE per game_id

# Critical Test 5: End-to-end pipeline
@pytest.mark.e2e
@pytest.mark.critical
def test_complete_data_pipeline(db_pool, espn_mock_responses):
    """Complete flow: ESPN API -> parsing -> validation -> database."""
    # 1. Mock ESPN API response
    # 2. Parse with ESPN client
    # 3. Validate with quality validator
    # 4. Store in database
    # 5. Query back and verify data integrity
```

---

## 5. Edge Cases

### ESPN API Edge Cases

| # | Edge Case | Expected Behavior | Test Name |
|---|-----------|-------------------|-----------|
| 1 | ESPN API returns stale data (>60s old) | Reject with warning log | `test_reject_stale_data` |
| 2 | ESPN API returns malformed JSON | Graceful error, use cached data | `test_malformed_json_handling` |
| 3 | ESPN API rate limit exceeded (429) | Backoff, retry after Retry-After | `test_rate_limit_backoff` |
| 4 | Network timeout during API call | Retry with exponential backoff | `test_network_timeout_retry` |
| 5 | Missing data fields in response | Use defaults or skip with warning | `test_missing_fields_defaults` |
| 6 | Game status transitions mid-poll | SCD Type 2 tracks history | `test_status_transition_tracking` |

### Scheduler Edge Cases

| # | Edge Case | Expected Behavior | Test Name |
|---|-----------|-------------------|-----------|
| 1 | APScheduler job overlaps (prev still running) | Skip or queue | `test_overlapping_jobs` |
| 2 | No active games (off-season) | No polling, no API calls | `test_no_games_no_polling` |
| 3 | Scheduler crash mid-job | Job state preserved, resume | `test_crash_recovery` |
| 4 | Database connection lost during job | Retry with fresh connection | `test_db_reconnect` |

### Backfill Edge Cases

| # | Edge Case | Expected Behavior | Test Name |
|---|-----------|-------------------|-----------|
| 1 | Duplicate data in nflfastR | Upsert logic handles | `test_duplicate_handling` |
| 2 | Missing seasons in data | Skip with warning, continue | `test_missing_season_skip` |
| 3 | Corrupted CSV row | Skip row, log error | `test_corrupted_row_skip` |
| 4 | Disk full during backfill | Graceful stop, report progress | `test_disk_full_handling` |

---

## 6. Performance Baselines

From DEVELOPMENT_PHASES_V1.6.md Section "Performance Baselines":

| Operation | Target | Test Type | Measurement |
|-----------|--------|-----------|-------------|
| ESPN API response parsing | <50ms per game | Unit | `time.perf_counter()` |
| Database insert (game state) | <10ms | Integration | `time.perf_counter()` |
| APScheduler job execution overhead | <100ms | Integration | Job start → job end |
| Concurrent game processing (50 games) | <2 seconds total | Stress | End-to-end timing |
| Historical backfill (5 years) | <10 minutes total | Stress | Script execution time |

### Performance Test Implementations

```python
@pytest.mark.performance
def test_espn_parsing_under_50ms(espn_mock_responses):
    """Verify ESPN response parsing completes in <50ms."""
    import time
    start = time.perf_counter()

    for _ in range(100):  # 100 games
        parse_espn_game(espn_mock_responses["nfl_scoreboard"]["events"][0])

    elapsed = (time.perf_counter() - start) / 100 * 1000  # ms per game
    assert elapsed < 50, f"Parsing took {elapsed:.2f}ms, expected <50ms"

@pytest.mark.performance
def test_database_insert_under_10ms(db_pool, game_state_factory):
    """Verify database insert completes in <10ms."""
    import time
    game_state = game_state_factory.build()

    start = time.perf_counter()
    insert_game_state(db_pool, game_state)
    elapsed = (time.perf_counter() - start) * 1000

    assert elapsed < 10, f"Insert took {elapsed:.2f}ms, expected <10ms"
```

---

## 7. Security Test Scenarios

From DEVELOPMENT_PHASES_V1.6.md Section "Security Test Scenarios":

| # | Security Scenario | Test Type | Priority |
|---|-------------------|-----------|----------|
| 1 | ESPN API calls don't expose credentials | Unit | 🔴 Critical |
| 2 | Input sanitization for game state data | Unit | 🔴 Critical |
| 3 | Timestamp validation prevents time-based attacks | Unit | 🟡 High |
| 4 | Rate limiting prevents API abuse | Integration | 🟡 High |

### Security Test Implementations

```python
@pytest.mark.security
def test_no_credentials_in_api_calls():
    """Verify ESPN API calls don't include sensitive data."""
    # ESPN is a public API, but verify no accidental credential exposure
    client = ESPNClient()
    request = client._build_request("scoreboard")
    assert "api_key" not in request.url.lower()
    assert "token" not in request.headers

@pytest.mark.security
def test_input_sanitization_game_state(db_pool):
    """Verify game state data is sanitized before database insert."""
    malicious_data = {
        "game_id": "'; DROP TABLE game_states; --",
        "home_team": "<script>alert('xss')</script>",
    }
    # Should raise validation error, not execute injection
    with pytest.raises(ValidationError):
        insert_game_state(db_pool, malicious_data)

@pytest.mark.security
def test_timestamp_validation_prevents_time_attacks():
    """Verify timestamp validation prevents time manipulation."""
    future_timestamp = datetime.now() + timedelta(days=365)
    with pytest.raises(ValidationError, match="timestamp in future"):
        validate_timestamp(future_timestamp)
```

---

## 8. Success Criteria

### Coverage Requirements (from validation_config.yaml)

| Module | Target | Minimum Acceptable |
|--------|--------|-------------------|
| `espn_client.py` | 85% | 80% |
| `market_updater.py` | 85% | 80% |
| `quality_validator.py` | 80% | 75% |
| `backfill_nflfastr.py` | 75% | 70% |
| **Overall Phase 2** | **≥80%** | **75%** |

### Test Count Requirements

| Deliverable | Unit | Property | Integration | Stress | E2E | Total |
|-------------|------|----------|-------------|--------|-----|-------|
| ESPN API Client | 20+ | 5+ | 10+ | 3+ | 2+ | 40+ |
| Task Scheduler | 15+ | - | 5+ | 3+ | - | 23+ |
| Data Quality Validator | 15+ | 5+ | 5+ | - | - | 25+ |
| Historical Backfill | 10+ | - | 3+ | 2+ | - | 15+ |
| **Total Phase 2** | **60+** | **10+** | **23+** | **8+** | **2+** | **103+** |

### Critical Scenario Coverage

All 7 critical scenarios from Section 4 must have passing tests:
- [ ] Live feed ingestion (mocked ESPN streams)
- [ ] Async event loop stress/concurrency
- [ ] Failover/retry for REST endpoints
- [ ] SCD Type-2 validation
- [ ] End-to-end pipeline
- [ ] APScheduler reliability (1 hour)
- [ ] Historical backfill performance

### Test Execution Time

- Unit tests: <30 seconds
- Integration tests: <60 seconds
- Property tests: <30 seconds (100 examples each)
- Stress tests: <5 minutes
- E2E tests: <2 minutes
- **Total suite**: <10 minutes locally

---

## Appendix: Test File Locations

```
tests/
├── unit/
│   ├── api_connectors/
│   │   └── test_espn_client.py
│   ├── schedulers/
│   │   └── test_market_updater.py
│   ├── data/
│   │   └── test_quality_validator.py
│   └── scripts/
│       └── test_backfill_nflfastr.py
├── property/
│   ├── api_connectors/
│   │   └── test_espn_client_properties.py
│   └── data/
│       └── test_quality_validator_properties.py
├── integration/
│   ├── api_connectors/
│   │   └── test_espn_client_integration.py
│   ├── schedulers/
│   │   └── test_scheduler_integration.py
│   ├── data/
│   │   └── test_quality_validator_integration.py
│   └── scripts/
│       └── test_backfill_integration.py
├── stress/
│   ├── api_connectors/
│   │   └── test_espn_rate_limits.py
│   └── schedulers/
│       └── test_concurrent_jobs.py
├── e2e/
│   └── test_live_data_pipeline.py
└── fixtures/
    ├── espn_responses.py
    ├── mock_scheduler.py
    └── factories.py (update with ESPNGameFactory)
```

---

## Document Status

**Phase 2 Test Planning Checklist:**
- [x] Requirements analysis (Section 1)
- [x] Test categories needed (Section 2)
- [x] Test infrastructure updates (Section 3)
- [x] Critical test scenarios (Section 4)
- [x] Edge cases (Section 5)
- [x] Performance baselines (Section 6)
- [x] Security test scenarios (Section 7)
- [x] Success criteria (Section 8)

**Status:** ✅ **Phase 2 Test Planning Complete**

---

**END OF PHASE_2_TEST_PLAN_V1.0.md**
