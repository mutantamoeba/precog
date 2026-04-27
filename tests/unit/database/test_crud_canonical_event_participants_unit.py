"""Unit tests for crud_canonical_event_participants module -- Pattern 14 step
4 of the Cohort 1B Slice C retro.

Covers (function-by-function):
    - create_canonical_event_participant: happy path, sequence_number=1
      single-row case, sequence_number>1 multi-row case, params order,
      RETURNING projection fidelity.
    - get_canonical_event_participant_by_id: happy path (row found),
      None (not found), column projection fidelity.
    - get_canonical_event_participant_by_natural_key: happy path,
      None (not found), composite-key params shape.
    - get_canonical_participant_role_id_by_domain_and_role: happy path
      domain-scoped role, happy path cross-domain (domain_id=None) role,
      None (not seeded), case-sensitivity passthrough, NULL-branch query
      shape.

Pattern 43 (mock fidelity) discipline: mocks return the EXACT shape that the
real query returns -- full row dicts with all canonical_event_participants
columns, no extra keys, no missing keys.  Mocks of ``get_cursor`` use the
``__enter__`` / ``__exit__`` protocol consistent with sibling test modules.

Reference:
    - ``src/precog/database/crud_canonical_event_participants.py``
    - ``src/precog/database/alembic/versions/0068_canonical_entity_foundation.py``
    - ``tests/unit/database/test_crud_canonical_markets_unit.py`` (style reference)
    - ``tests/unit/database/test_crud_canonical_entity_unit.py`` (Slice B sibling)
    - ``tests/unit/database/test_crud_canonical_events_unit.py`` (Slice C sibling)
    - ADR-118 V2.38+ (Cohort 1B Pattern 14 retro)
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_canonical_event_participants import (
    create_canonical_event_participant,
    get_canonical_event_participant_by_id,
    get_canonical_event_participant_by_natural_key,
    get_canonical_participant_role_id_by_domain_and_role,
)


def _full_row_dict(
    *,
    id: int = 7,
    canonical_event_id: int = 42,
    entity_id: int = 11,
    role_id: int = 1,
    sequence_number: int = 1,
    created_at: datetime | None = None,
) -> dict:
    """Build a full canonical_event_participants row dict matching the real query shape.

    Pattern 43 fidelity: every key the real RETURNING / SELECT projection
    emits is present, with no extras.  This is the SSOT for "what does a
    canonical_event_participants row dict look like in tests".
    """
    if created_at is None:
        created_at = datetime(2026, 4, 26, 12, 0, 0, tzinfo=UTC)
    return {
        "id": id,
        "canonical_event_id": canonical_event_id,
        "entity_id": entity_id,
        "role_id": role_id,
        "sequence_number": sequence_number,
        "created_at": created_at,
    }


_ALL_PARTICIPANT_COLUMNS = (
    "id",
    "canonical_event_id",
    "entity_id",
    "role_id",
    "sequence_number",
    "created_at",
)


# =============================================================================
# create_canonical_event_participant
# =============================================================================


@pytest.mark.unit
class TestCreateCanonicalEventParticipant:
    """Unit tests for create_canonical_event_participant -- INSERT + RETURNING happy path."""

    @patch("precog.database.crud_canonical_event_participants.get_cursor")
    def test_returns_full_row_dict_on_success(self, mock_get_cursor):
        """Returns the full row dict from RETURNING projection."""
        expected_row = _full_row_dict(
            id=7,
            canonical_event_id=42,
            entity_id=11,
            role_id=1,
            sequence_number=1,
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_canonical_event_participant(
            canonical_event_id=42,
            entity_id=11,
            role_id=1,
            sequence_number=1,
        )

        assert result == expected_row
        # commit=True must be used because this is a write
        mock_get_cursor.assert_called_once_with(commit=True)
        mock_cursor.execute.assert_called_once()
        # Verify INSERT + RETURNING query shape
        sql, params = mock_cursor.execute.call_args[0]
        assert "INSERT INTO canonical_event_participants" in sql
        assert "RETURNING" in sql
        assert "canonical_event_id" in sql
        assert "sequence_number" in sql
        # Params order matches column order in INSERT statement
        assert params[0] == 42  # canonical_event_id
        assert params[1] == 11  # entity_id
        assert params[2] == 1  # role_id
        assert params[3] == 1  # sequence_number

    @patch("precog.database.crud_canonical_event_participants.get_cursor")
    def test_sequence_number_multi_row_case(self, mock_get_cursor):
        """sequence_number > 1 is passed through (multi-row-per-role discipline).

        Per ADR-118 V2.38 decision #6 (Glokta carry-forward #5): the
        composite UNIQUE on (canonical_event_id, role_id, sequence_number)
        admits the multi-row-per-role case.  Test that
        sequence_number > 1 reaches the SQL params unchanged.
        """
        expected_row = _full_row_dict(sequence_number=10)

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        # 10-candidate election case: sequence_number=10
        create_canonical_event_participant(
            canonical_event_id=99,
            entity_id=27,
            role_id=5,  # 'candidate'
            sequence_number=10,
        )

        params = mock_cursor.execute.call_args[0][1]
        assert params[3] == 10  # sequence_number

    @patch("precog.database.crud_canonical_event_participants.get_cursor")
    def test_sequence_number_no_default_at_python_layer(self, mock_get_cursor):
        """sequence_number is REQUIRED at the Python signature -- no default.

        Calling create_canonical_event_participant() without sequence_number
        must raise TypeError.  This pins the no-default discipline at the
        Python layer; the DB layer also enforces NOT NULL with no DEFAULT
        per Migration 0068, but the Python signature is the first line of
        defense (Glokta carry-forward #5).
        """
        # No mock setup needed -- we expect TypeError BEFORE any DB call.
        with pytest.raises(TypeError):
            create_canonical_event_participant(  # type: ignore[call-arg]
                canonical_event_id=42,
                entity_id=11,
                role_id=1,
                # sequence_number intentionally omitted
            )
        # Verify the DB was not touched
        mock_get_cursor.assert_not_called()

    @patch("precog.database.crud_canonical_event_participants.get_cursor")
    def test_returning_projects_all_participant_columns(self, mock_get_cursor):
        """Pattern 43 fidelity: the INSERT...RETURNING projection must include
        all 6 canonical_event_participants columns.  Mirrors Glokta Finding 7
        + Ripley Finding 5 from Cohort 2 -- without this test, a future
        refactor that drops a column from the RETURNING clause would
        silently pass because the mock dict (built by _full_row_dict()) has
        all keys regardless.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = _full_row_dict()
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_event_participant(
            canonical_event_id=42,
            entity_id=11,
            role_id=1,
            sequence_number=1,
        )

        sql = mock_cursor.execute.call_args[0][0]
        for col in _ALL_PARTICIPANT_COLUMNS:
            assert col in sql, f"Column {col!r} missing from INSERT...RETURNING projection"


# =============================================================================
# get_canonical_event_participant_by_id
# =============================================================================


@pytest.mark.unit
class TestGetCanonicalEventParticipantById:
    """Unit tests for get_canonical_event_participant_by_id -- SELECT by surrogate PK."""

    @patch("precog.database.crud_canonical_event_participants.fetch_one")
    def test_returns_row_dict_when_found(self, mock_fetch_one):
        """Returns the full row dict when a row matches the id."""
        expected_row = _full_row_dict(id=7)
        mock_fetch_one.return_value = expected_row

        result = get_canonical_event_participant_by_id(7)

        assert result == expected_row
        mock_fetch_one.assert_called_once()
        sql, params = mock_fetch_one.call_args[0]
        assert "FROM canonical_event_participants" in sql
        assert "WHERE id = %s" in sql
        assert params == (7,)

    @patch("precog.database.crud_canonical_event_participants.fetch_one")
    def test_returns_none_when_not_found(self, mock_fetch_one):
        """Returns None when no row matches the id."""
        mock_fetch_one.return_value = None

        result = get_canonical_event_participant_by_id(99999)

        assert result is None
        assert mock_fetch_one.call_count == 1
        assert mock_fetch_one.call_args[0][1] == (99999,)

    @patch("precog.database.crud_canonical_event_participants.fetch_one")
    def test_query_selects_all_participant_columns(self, mock_fetch_one):
        """Pattern 43 fidelity: SELECT projection must include all 6 columns."""
        mock_fetch_one.return_value = None

        get_canonical_event_participant_by_id(7)

        sql = mock_fetch_one.call_args[0][0]
        for col in _ALL_PARTICIPANT_COLUMNS:
            assert col in sql, f"Column {col!r} missing from SELECT projection"


# =============================================================================
# get_canonical_event_participant_by_natural_key
# =============================================================================


@pytest.mark.unit
class TestGetCanonicalEventParticipantByNaturalKey:
    """Unit tests for get_canonical_event_participant_by_natural_key -- composite NK."""

    @patch("precog.database.crud_canonical_event_participants.fetch_one")
    def test_returns_row_dict_when_found(self, mock_fetch_one):
        """Returns the full row dict when (canonical_event_id, role_id, sequence_number) matches."""
        expected_row = _full_row_dict(canonical_event_id=42, role_id=1, sequence_number=1)
        mock_fetch_one.return_value = expected_row

        result = get_canonical_event_participant_by_natural_key(
            canonical_event_id=42, role_id=1, sequence_number=1
        )

        assert result == expected_row
        sql, params = mock_fetch_one.call_args[0]
        assert "FROM canonical_event_participants" in sql
        assert "WHERE canonical_event_id = %s AND role_id = %s AND sequence_number = %s" in sql
        assert params == (42, 1, 1)

    @patch("precog.database.crud_canonical_event_participants.fetch_one")
    def test_returns_none_when_not_found(self, mock_fetch_one):
        """Returns None when no row matches the composite natural key.

        This is the "new participant slot" signal -- a None return means
        the caller should create a new canonical_event_participants row.
        """
        mock_fetch_one.return_value = None

        result = get_canonical_event_participant_by_natural_key(
            canonical_event_id=42, role_id=1, sequence_number=999
        )

        assert result is None

    @patch("precog.database.crud_canonical_event_participants.fetch_one")
    def test_query_selects_all_participant_columns(self, mock_fetch_one):
        """Pattern 43 fidelity: composite-NK SELECT projection must include all 6 columns."""
        mock_fetch_one.return_value = None

        get_canonical_event_participant_by_natural_key(
            canonical_event_id=42, role_id=1, sequence_number=1
        )

        sql = mock_fetch_one.call_args[0][0]
        for col in _ALL_PARTICIPANT_COLUMNS:
            assert col in sql, f"Column {col!r} missing from composite-NK SELECT projection"

    @patch("precog.database.crud_canonical_event_participants.fetch_one")
    def test_multi_sequence_lookup_pinned(self, mock_fetch_one):
        """Lookup for a different sequence_number on the same (event, role) pair
        passes the new sequence_number through unchanged.

        Pinning the multi-row-per-role lookup contract: the composite NK
        admits multiple rows for the same (canonical_event_id, role_id) pair
        differing only in sequence_number, and this lookup correctly
        disambiguates by sequence_number.
        """
        mock_fetch_one.return_value = None

        get_canonical_event_participant_by_natural_key(
            canonical_event_id=99, role_id=5, sequence_number=7
        )

        params = mock_fetch_one.call_args[0][1]
        assert params == (99, 5, 7)


# =============================================================================
# get_canonical_participant_role_id_by_domain_and_role
# =============================================================================


@pytest.mark.unit
class TestGetCanonicalParticipantRoleIdByDomainAndRole:
    """Unit tests for get_canonical_participant_role_id_by_domain_and_role.

    Resolver helper with a NULL-domain branch (cross-domain roles per
    ADR-118 V2.38 decision #4).  The query branches on whether ``domain_id``
    is NULL because PG treats ``WHERE col = NULL`` as always-false
    (three-valued logic) -- the equality form ``col = %s`` cannot match
    NULL rows.  Tests verify both branches.
    """

    @patch("precog.database.crud_canonical_event_participants.fetch_one")
    def test_returns_id_when_domain_scoped_pair_seeded(self, mock_fetch_one):
        """Returns the integer id for a seeded (domain_id, role) pair."""
        mock_fetch_one.return_value = {"id": 1}

        result = get_canonical_participant_role_id_by_domain_and_role(1, "home")

        assert result == 1
        sql, params = mock_fetch_one.call_args[0]
        assert "FROM canonical_participant_roles" in sql
        assert "WHERE domain_id = %s AND role = %s" in sql
        assert "IS NULL" not in sql  # equality branch, not NULL branch
        assert params == (1, "home")

    @patch("precog.database.crud_canonical_event_participants.fetch_one")
    def test_returns_none_when_domain_scoped_pair_not_seeded(self, mock_fetch_one):
        """Returns None when no canonical_participant_roles row matches the domain-scoped pair."""
        mock_fetch_one.return_value = None

        result = get_canonical_participant_role_id_by_domain_and_role(1, "unicorn_role")

        assert result is None

    @patch("precog.database.crud_canonical_event_participants.fetch_one")
    def test_returns_id_when_cross_domain_pair_seeded(self, mock_fetch_one):
        """Returns the integer id for a seeded (NULL, role) pair (cross-domain).

        Per ADR-118 V2.38 decision #4, ``domain_id`` is NULLABLE on
        canonical_participant_roles to admit cross-domain roles like
        future ``yes_side``.  This test pins the NULL-branch contract.
        """
        mock_fetch_one.return_value = {"id": 99}

        result = get_canonical_participant_role_id_by_domain_and_role(None, "yes_side")

        assert result == 99
        sql, params = mock_fetch_one.call_args[0]
        assert "FROM canonical_participant_roles" in sql
        assert "WHERE domain_id IS NULL AND role = %s" in sql
        # The NULL branch passes ONLY the role param (not domain_id, since IS NULL is literal)
        assert params == ("yes_side",)

    @patch("precog.database.crud_canonical_event_participants.fetch_one")
    def test_returns_none_when_cross_domain_pair_not_seeded(self, mock_fetch_one):
        """Returns None when no cross-domain row matches the given role text."""
        mock_fetch_one.return_value = None

        result = get_canonical_participant_role_id_by_domain_and_role(
            None, "unicorn_cross_domain_role"
        )

        assert result is None

    @patch("precog.database.crud_canonical_event_participants.fetch_one")
    def test_case_sensitive_passthrough(self, mock_fetch_one):
        """Role text is passed through unchanged (case-sensitive at the DB layer)."""
        mock_fetch_one.return_value = None

        result = get_canonical_participant_role_id_by_domain_and_role(1, "HOME")

        assert result is None
        params = mock_fetch_one.call_args[0][1]
        assert params == (1, "HOME")  # passed through verbatim

    @patch("precog.database.crud_canonical_event_participants.fetch_one")
    def test_null_domain_query_does_not_use_equality(self, mock_fetch_one):
        """NULL-domain query MUST use ``IS NULL`` not ``= NULL``.

        Pinning a critical PG three-valued-logic correctness invariant:
        ``WHERE domain_id = NULL`` is always false, so a naive
        implementation would silently return None for every cross-domain
        role lookup even when the row exists.  The implementation MUST
        branch on ``domain_id is None`` and emit ``IS NULL`` for cross-
        domain queries.
        """
        mock_fetch_one.return_value = None

        get_canonical_participant_role_id_by_domain_and_role(None, "yes_side")

        sql = mock_fetch_one.call_args[0][0]
        # Must use IS NULL, never equality with NULL
        assert "domain_id IS NULL" in sql
        assert "domain_id = %s" not in sql  # equality form must be absent in this branch
