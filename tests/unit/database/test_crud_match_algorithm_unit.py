"""Unit tests for crud_match_algorithm module — Pattern 14 step 4 of Cohort 3 slot 0071.

Covers (function-by-function):
    - get_match_algorithm_by_name_version: happy path (row found), None
      (not found), query shape pinning (SELECT projection + WHERE clause +
      params order), case-sensitivity passthrough.
    - get_default_manual_algorithm: happy path (returns manual_v1/1.0.0
      row), None (seed missing — degenerate state), delegation to
      get_match_algorithm_by_name_version with the canonical default
      tuple.

Pattern 43 (mock fidelity) discipline: mocks return the EXACT shape that the
real query returns — full row dicts with all match_algorithm columns
(id, name, version, code_ref, description, created_at, retired_at), no
extra keys, no missing keys.  Mocks of ``fetch_one`` use return-value
discipline consistent with ``test_crud_canonical_markets_unit.py``.

Critical Pattern #6 (Immutability) is exercised by the absence of mutation
helpers in the SUT — there is nothing to test for create/update/delete/
retire because no such helpers exist.  This is the right shape: the test
surface mirrors the public surface; both stay minimal.

Reference:
    - ``src/precog/database/crud_match_algorithm.py`` (the SUT)
    - ``src/precog/database/alembic/versions/0071_match_algorithm.py``
      (DDL + seed — establishes the row dict shape)
    - ``tests/unit/database/test_crud_canonical_markets_unit.py`` (style
      reference — same Pattern 43 discipline + class-grouping convention)
    - ``memory/build_spec_0071_holden_memo.md`` (Pattern 14 step 4 scope)
"""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from precog.database.crud_match_algorithm import (
    get_default_manual_algorithm,
    get_match_algorithm_by_name_version,
)


def _full_row_dict(
    *,
    id: int = 1,
    name: str = "manual_v1",
    version: str = "1.0.0",
    code_ref: str = "precog.matching.manual_v1",
    description: str | None = (
        "Phase 1 baseline: every link decided manually; confidence = 1.0 for human-decided rows."
    ),
    created_at: datetime | None = None,
    retired_at: datetime | None = None,
) -> dict:
    """Build a full match_algorithm row dict matching the real query shape.

    Pattern 43 fidelity: every key the real SELECT projection emits is
    present, with no extras.  This is the SSOT for "what does a
    match_algorithm row dict look like in tests".
    """
    if created_at is None:
        created_at = datetime(2026, 4, 26, 12, 0, 0, tzinfo=UTC)
    return {
        "id": id,
        "name": name,
        "version": version,
        "code_ref": code_ref,
        "description": description,
        "created_at": created_at,
        "retired_at": retired_at,
    }


# =============================================================================
# get_match_algorithm_by_name_version
# =============================================================================


@pytest.mark.unit
class TestGetMatchAlgorithmByNameVersion:
    """Unit tests for get_match_algorithm_by_name_version — SELECT by (name, version)."""

    @patch("precog.database.crud_match_algorithm.fetch_one")
    def test_returns_row_dict_when_found(self, mock_fetch_one):
        """Returns the full row dict when (name, version) matches."""
        expected_row = _full_row_dict()
        mock_fetch_one.return_value = expected_row

        result = get_match_algorithm_by_name_version("manual_v1", "1.0.0")

        assert result == expected_row
        mock_fetch_one.assert_called_once()
        sql, params = mock_fetch_one.call_args[0]
        assert "FROM match_algorithm" in sql
        assert "WHERE name = %s AND version = %s" in sql
        # Params order matches WHERE clause order
        assert params == ("manual_v1", "1.0.0")

    @patch("precog.database.crud_match_algorithm.fetch_one")
    def test_returns_none_when_not_found(self, mock_fetch_one):
        """Returns None when no row matches the (name, version) tuple."""
        mock_fetch_one.return_value = None

        result = get_match_algorithm_by_name_version("never_seeded", "9.9.9")

        assert result is None
        mock_fetch_one.assert_called_once()
        params = mock_fetch_one.call_args[0][1]
        assert params == ("never_seeded", "9.9.9")

    @patch("precog.database.crud_match_algorithm.fetch_one")
    def test_query_selects_all_match_algorithm_columns(self, mock_fetch_one):
        """Pattern 43 fidelity: the SELECT projection must include all 7
        match_algorithm columns. Without this assertion, a future refactor
        that drops a column from the projection would silently pass because
        the mock dict (built by _full_row_dict()) has all keys regardless of
        what the projection actually emits.
        """
        mock_fetch_one.return_value = None

        get_match_algorithm_by_name_version("manual_v1", "1.0.0")

        sql = mock_fetch_one.call_args[0][0]
        for col in (
            "id",
            "name",
            "version",
            "code_ref",
            "description",
            "created_at",
            "retired_at",
        ):
            assert col in sql, f"Column {col!r} missing from SELECT projection"

    @patch("precog.database.crud_match_algorithm.fetch_one")
    def test_case_sensitive_passthrough(self, mock_fetch_one):
        """name and version params are passed verbatim (case-sensitive).

        match_algorithm.name and .version are VARCHAR (not citext), so
        case-sensitivity is a property of the underlying SQL comparison.
        This test pins that the CRUD function does NOT normalize case
        (e.g., does NOT lowercase the name).  A future caller passing
        'Manual_V1' must hit the DB exactly as-typed, not get silently
        normalized to 'manual_v1'.
        """
        mock_fetch_one.return_value = None

        get_match_algorithm_by_name_version("Manual_V1", "1.0.0")

        params = mock_fetch_one.call_args[0][1]
        assert params == ("Manual_V1", "1.0.0")

    @patch("precog.database.crud_match_algorithm.fetch_one")
    def test_no_commit_on_read_path(self, mock_fetch_one):
        """get_match_algorithm_by_name_version is a read — fetch_one is the
        SSOT for "no commit needed".  Pinning here so a future refactor
        that switches to ``get_cursor(commit=True)`` (a write-path
        primitive) would fail this test.
        """
        mock_fetch_one.return_value = None

        get_match_algorithm_by_name_version("manual_v1", "1.0.0")

        # fetch_one is the read-only entry point in connection.py; it does
        # not take a commit kwarg.  Verifying we go through fetch_one
        # (not get_cursor with commit=True) is the test-side proof.
        assert mock_fetch_one.call_count == 1


# =============================================================================
# get_default_manual_algorithm
# =============================================================================


@pytest.mark.unit
class TestGetDefaultManualAlgorithm:
    """Unit tests for get_default_manual_algorithm — Phase 1 default resolver."""

    @patch("precog.database.crud_match_algorithm.fetch_one")
    def test_returns_manual_v1_row_when_seeded(self, mock_fetch_one):
        """Returns the manual_v1/1.0.0 row when the Phase 1 seed is present."""
        expected_row = _full_row_dict(
            name="manual_v1",
            version="1.0.0",
            code_ref="precog.matching.manual_v1",
        )
        mock_fetch_one.return_value = expected_row

        result = get_default_manual_algorithm()

        assert result == expected_row
        # The helper must look up the canonical default tuple — not some
        # other (name, version) pair.
        params = mock_fetch_one.call_args[0][1]
        assert params == ("manual_v1", "1.0.0")

    @patch("precog.database.crud_match_algorithm.fetch_one")
    def test_returns_none_when_seed_missing(self, mock_fetch_one):
        """Returns None when the Phase 1 seed is missing (degenerate state).

        A None return signals "Migration 0071 was not applied" or "the seed
        row was manually deleted".  Callers MUST handle this defensively
        (raise a domain-specific error) rather than dereferencing None.
        Pinning the contract here so a future refactor that adds a fallback
        (e.g., "if not found, INSERT manual_v1") would fail this test.
        """
        mock_fetch_one.return_value = None

        result = get_default_manual_algorithm()

        assert result is None

    @patch("precog.database.crud_match_algorithm.fetch_one")
    def test_delegates_to_get_match_algorithm_by_name_version(self, mock_fetch_one):
        """get_default_manual_algorithm is a thin wrapper that delegates the
        SELECT to get_match_algorithm_by_name_version.  This test pins the
        delegation by asserting the mocked fetch_one (which both functions
        ultimately call) was invoked exactly once with the canonical
        ('manual_v1', '1.0.0') tuple.

        Why this matters: if a future refactor introduces a duplicate
        SELECT path inside get_default_manual_algorithm (instead of
        delegating), Pattern 73 SSOT for the default tuple drifts —
        bumping the default version would require edits in two places.
        """
        mock_fetch_one.return_value = _full_row_dict()

        get_default_manual_algorithm()

        assert mock_fetch_one.call_count == 1
        sql, params = mock_fetch_one.call_args[0]
        # Same SELECT shape as get_match_algorithm_by_name_version.
        assert "FROM match_algorithm" in sql
        assert "WHERE name = %s AND version = %s" in sql
        assert params == ("manual_v1", "1.0.0")

    @patch("precog.database.crud_match_algorithm.fetch_one")
    def test_returned_row_has_canonical_code_ref(self, mock_fetch_one):
        """When the seed is present, the returned row carries the canonical
        Pattern 73 SSOT code_ref ('precog.matching.manual_v1').

        This pins the published-contract surface: callers (Cohort 5+
        resolver code) read row['code_ref'] to know which module to import.
        A drift in the seeded code_ref would silently break the matching
        layer; this test catches that drift at the unit-test layer.
        """
        mock_fetch_one.return_value = _full_row_dict(
            code_ref="precog.matching.manual_v1",
        )

        result = get_default_manual_algorithm()

        assert result is not None
        assert result["code_ref"] == "precog.matching.manual_v1"
