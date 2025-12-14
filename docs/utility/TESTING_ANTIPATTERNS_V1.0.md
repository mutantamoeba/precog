# Testing Antipatterns Discovered

---
**Version:** 1.0
**Created:** 2025-12-09
**Last Updated:** 2025-12-09
**Purpose:** Document testing antipatterns discovered during Phase 2.5 development
**Phase:** 2.5 (Live Data Collection)
**Status:** Active - Lessons Learned
---

## Overview

This document captures testing antipatterns discovered during Phase 2.5 development, specifically during ESPN polling implementation and end-to-end testing. These patterns led to issues that passed unit tests but failed in production-like scenarios.

## Antipattern 1: Testing Against Empty/Unseeded Databases

### The Problem

Unit tests passed with 100% coverage, but integration testing against a real database failed with:
- "Team not found" warnings for every ESPN game
- Teams table was empty in precog_test/precog_dev databases

### What Happened

1. **Unit tests mocked database calls** - All unit tests used mocks that simulated successful team lookups
2. **Integration tests used real database** - When running against precog_test, the teams table was empty
3. **Seed data not applied** - The SQL seed files (001-007_*_teams.sql) existed but weren't applied to test databases
4. **CI/CD passed** - CI used isolated test fixtures, not real database connections

### The Antipattern

```python
# ANTIPATTERN: Mocking hides missing seed data
@patch('precog.database.crud_operations.get_team_by_espn_id')
def test_process_game(mock_get_team):
    mock_get_team.return_value = {'id': 1, 'name': 'Test Team'}
    # Test passes but never validates real database has teams
    result = process_game(game_data)
    assert result['success']
```

### The Fix

```python
# CORRECT: Integration tests require seed data
@pytest.fixture(scope="module")
def seeded_database():
    """Ensure test database has required seed data before tests."""
    # Check if teams exist
    with get_connection() as conn:
        result = conn.execute("SELECT COUNT(*) FROM teams")
        if result.scalar() == 0:
            pytest.skip("Database not seeded - run seed scripts first")
    yield

def test_process_game_integration(seeded_database):
    """Test with real database - requires seed data."""
    result = process_game(real_espn_game_data)
    assert result['home_team_id'] is not None
```

### Prevention Checklist

- [ ] Integration tests should verify prerequisite data exists
- [ ] Add "seeding required" markers to integration tests
- [ ] CI pipeline should run seed scripts before integration tests
- [ ] Document database prerequisites in test README

---

## Antipattern 2: Not Testing API Edge Cases Against Database Constraints

### The Problem

ESPN API returned `capacity: 0` for venues with unknown capacity. Database constraint required `capacity > 0 OR capacity IS NULL`, causing constraint violation errors.

### What Happened

1. **Unit tests used typical values** - Test fixtures used capacity values like 50000, 70000
2. **Edge case not considered** - Nobody tested capacity=0 (unknown capacity)
3. **Database constraint mismatch** - DB enforced `capacity > 0`, but API could return 0
4. **Production failure** - First real poll failed on venue upsert with constraint violation

### The Antipattern

```python
# ANTIPATTERN: Only testing happy path values
def test_upsert_venue():
    venue_data = {
        'name': 'Test Stadium',
        'capacity': 50000,  # Always a "normal" value
    }
    result = upsert_venue(venue_data)
    assert result['success']
```

### The Fix

```python
# CORRECT: Test API edge cases against DB constraints
@pytest.mark.parametrize("capacity,expected", [
    (50000, 50000),      # Normal capacity
    (0, None),           # ESPN returns 0 for unknown -> normalize to NULL
    (None, None),        # Explicit NULL
    (-1, None),          # Invalid negative -> normalize to NULL
])
def test_upsert_venue_capacity_edge_cases(capacity, expected):
    """Test that API edge cases are normalized before DB insert."""
    venue_data = {'name': 'Test Stadium', 'capacity': capacity}
    result = upsert_venue(venue_data)
    assert result['capacity'] == expected

def test_venue_capacity_db_constraint():
    """Test that constraint is respected after normalization."""
    # This should NOT raise a constraint error
    venue_data = {'name': 'Unknown Arena', 'capacity': 0}
    result = upsert_venue(venue_data)  # 0 -> None before insert
    assert result['success']
```

### Prevention Checklist

- [ ] Document all database constraints in schema documentation
- [ ] For each API field, identify edge cases (0, negative, empty string, None)
- [ ] Add parametrized tests covering all edge cases
- [ ] Normalization layer should exist between API and database

---

## Antipattern 3: Environment Configuration Drift

### The Problem

Multiple environment variables competed for the same configuration:
- `.env` had `ENVIRONMENT=development`
- Code checked `PRECOG_ENV` (not set)
- Fallback to `DB_NAME=precog_test`

### What Happened

1. **Implicit defaults masked the issue** - Code defaulted to precog_test when PRECOG_ENV unset
2. **No validation** - No check that environment configuration was consistent
3. **Manual workarounds** - Developers set DB_NAME directly, hiding the configuration problem
4. **Seeds applied to wrong database** - Some seeds went to precog_dev, some to precog_test

### The Antipattern

```python
# ANTIPATTERN: Multiple fallbacks hide configuration issues
db_name = os.getenv('DB_NAME',
    os.getenv('PRECOG_ENV', 'test').replace('development', 'dev') + '_precog'
)
# This works but nobody knows which variable is actually being used
```

### The Fix

See ADR-105 (Two-Axis Environment Configuration) for the proper solution:
- Single PRECOG_ENV controls database
- Separate {MARKET}_MODE controls API endpoints
- Fail fast if required variables are unset

### Prevention Checklist

- [ ] Document all environment variables in .env.template
- [ ] Validate required variables at startup
- [ ] Fail fast with clear error messages
- [ ] Use explicit configuration, not cascading defaults
- [ ] Log which configuration source is being used

---

## Antipattern 4: Mock Isolation Masking Integration Issues

### The Problem

Unit tests were so isolated with mocks that they couldn't detect when the real components didn't work together.

### What Happened

1. **Perfect mocks** - Each component had comprehensive mocks
2. **Contract mismatch** - Mock returned `{'id': 1}` but real function returned `{'team_id': 1}`
3. **Unit tests passed** - All assertions against mock data succeeded
4. **Integration failed** - Real code failed due to field name mismatch

### The Antipattern

```python
# ANTIPATTERN: Mock doesn't match real return type
@patch('precog.database.crud_operations.get_team_by_espn_id')
def test_game_processing(mock_get_team):
    mock_get_team.return_value = {'id': 1, 'name': 'Team'}  # Wrong!
    # Real function returns {'team_id': 1, 'team_name': 'Team'}
```

### The Fix

```python
# CORRECT: Use TypedDict fixtures that match real return types
from precog.database.types import TeamRow

def create_team_fixture() -> TeamRow:
    """Create fixture matching real database return type."""
    return TeamRow(
        team_id=1,
        team_name='Test Team',
        espn_id=123,
        # ... all required fields
    )

@patch('precog.database.crud_operations.get_team_by_espn_id')
def test_game_processing(mock_get_team):
    mock_get_team.return_value = create_team_fixture()  # Type-checked
```

### Prevention Checklist

- [ ] Define TypedDict for all return types
- [ ] Use fixture factories that create typed objects
- [ ] Mypy strict mode to catch type mismatches
- [ ] Contract tests that verify mock behavior matches real behavior

---

## Summary: Lessons Learned

| Antipattern | Detection | Prevention |
|-------------|-----------|------------|
| Empty database testing | Integration test failures | Seed data fixtures, prerequisite checks |
| Missing edge case tests | Production constraint violations | Parametrized tests, API-to-DB mapping tests |
| Environment drift | Wrong database used | Explicit config, fail fast validation |
| Mock isolation | Integration failures after unit success | Typed fixtures, contract tests |

---

## Related Documents

- `docs/utility/PHASE_2_TEST_COVERAGE_GAPS_V1.0.md` - Test type coverage gaps
- `docs/utility/PHASE_2.5_DEFERRED_TASKS_V1.1.md` - DEF-P2.5-007 (Two-Axis Environment Config)
- `docs/foundation/TESTING_STRATEGY_V3.8.md` - Required test types
- `ADR-105` - Two-Axis Environment Configuration (Planned)

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-09 | Initial creation documenting 4 antipatterns from Phase 2.5 |

---

**END OF TESTING_ANTIPATTERNS_V1.0.md**
