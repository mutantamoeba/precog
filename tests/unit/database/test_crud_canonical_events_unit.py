"""Unit tests for crud_canonical_events module -- Pattern 14 step 4 of the
Cohort 1A Slice C retro.

Covers (function-by-function):
    - create_canonical_event: happy path, JSONB metadata serialization,
      None metadata -> NULL, Decimal preservation through metadata, BYTEA
      natural_key_hash passthrough, lifecycle_phase default.
    - get_canonical_event_by_id: happy path (row found), None (not found),
      column projection fidelity.
    - get_canonical_event_by_natural_key_hash: happy path (row found),
      None (not found), BYTEA params shape, column projection fidelity.
    - retire_canonical_event: True (row updated), False (no row),
      retired_at-only SET clause discipline.
    - get_canonical_event_domain_id_by_domain: happy path, None (not seeded),
      case-sensitivity passthrough.
    - get_canonical_event_type_id_by_domain_and_type: happy path, None (not
      seeded), composite-key params shape.

Pattern 43 (mock fidelity) discipline: mocks return the EXACT shape that the
real query returns -- full row dicts with all canonical_events columns, no
extra keys, no missing keys.  Mocks of ``get_cursor`` use the
``__enter__`` / ``__exit__`` protocol consistent with
``test_crud_canonical_markets_unit.py`` and
``test_crud_canonical_entity_unit.py``.

Reference:
    - ``src/precog/database/crud_canonical_events.py``
    - ``src/precog/database/alembic/versions/0067_canonical_events_foundation.py``
    - ``tests/unit/database/test_crud_canonical_markets_unit.py`` (style reference)
    - ``tests/unit/database/test_crud_canonical_entity_unit.py`` (Slice B sibling)
    - ADR-118 V2.38+ (Cohort 1A Pattern 14 retro)
"""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_canonical_events import (
    create_canonical_event,
    get_canonical_event_by_id,
    get_canonical_event_by_natural_key_hash,
    get_canonical_event_domain_id_by_domain,
    get_canonical_event_type_id_by_domain_and_type,
    retire_canonical_event,
)


def _sample_natural_key_hash(suffix: bytes = b"sample") -> bytes:
    """Return a 32-byte sha256 digest for use as a natural_key_hash test value."""
    return hashlib.sha256(b"canonical|event|nk|" + suffix).digest()


def _full_row_dict(
    *,
    id: int = 7,
    domain_id: int = 1,
    event_type_id: int = 1,
    entities_sorted: list[int] | None = None,
    resolution_window: str = "[2026-09-04 17:00+00, 2026-09-04 21:00+00]",
    resolution_rule_fp: bytes | None = None,
    natural_key_hash: bytes | None = None,
    title: str = "Buffalo Bills @ Miami Dolphins, Week 1",
    description: str | None = None,
    game_id: int | None = 42,
    series_id: int | None = None,
    lifecycle_phase: str = "proposed",
    metadata: dict | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    retired_at: datetime | None = None,
) -> dict:
    """Build a full canonical_events row dict matching the real query shape.

    Pattern 43 fidelity: every key the real RETURNING / SELECT projection
    emits is present, with no extras.  This is the SSOT for "what does a
    canonical_events row dict look like in tests".  Mirrors the
    ``_full_row_dict`` helper in ``test_crud_canonical_markets_unit.py``.
    """
    if entities_sorted is None:
        entities_sorted = [1, 2]
    if natural_key_hash is None:
        natural_key_hash = _sample_natural_key_hash()
    if created_at is None:
        created_at = datetime(2026, 4, 26, 12, 0, 0, tzinfo=UTC)
    if updated_at is None:
        updated_at = datetime(2026, 4, 26, 12, 0, 0, tzinfo=UTC)
    return {
        "id": id,
        "domain_id": domain_id,
        "event_type_id": event_type_id,
        "entities_sorted": entities_sorted,
        "resolution_window": resolution_window,
        "resolution_rule_fp": resolution_rule_fp,
        "natural_key_hash": natural_key_hash,
        "title": title,
        "description": description,
        "game_id": game_id,
        "series_id": series_id,
        "lifecycle_phase": lifecycle_phase,
        "metadata": metadata,
        "created_at": created_at,
        "updated_at": updated_at,
        "retired_at": retired_at,
    }


_ALL_CANONICAL_EVENTS_COLUMNS = (
    "id",
    "domain_id",
    "event_type_id",
    "entities_sorted",
    "resolution_window",
    "resolution_rule_fp",
    "natural_key_hash",
    "title",
    "description",
    "game_id",
    "series_id",
    "lifecycle_phase",
    "metadata",
    "created_at",
    "updated_at",
    "retired_at",
)


# =============================================================================
# create_canonical_event
# =============================================================================


@pytest.mark.unit
class TestCreateCanonicalEvent:
    """Unit tests for create_canonical_event -- INSERT + RETURNING happy path."""

    @patch("precog.database.crud_canonical_events.get_cursor")
    def test_returns_full_row_dict_on_success(self, mock_get_cursor):
        """Returns the full row dict from RETURNING projection."""
        nk = _sample_natural_key_hash()
        expected_row = _full_row_dict(
            id=7,
            domain_id=1,
            event_type_id=1,
            natural_key_hash=nk,
            metadata=None,
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_canonical_event(
            domain_id=1,
            event_type_id=1,
            entities_sorted=[1, 2],
            resolution_window="[2026-09-04 17:00+00, 2026-09-04 21:00+00]",
            natural_key_hash=nk,
            title="Buffalo Bills @ Miami Dolphins, Week 1",
            game_id=42,
        )

        assert result == expected_row
        # commit=True must be used because this is a write
        mock_get_cursor.assert_called_once_with(commit=True)
        mock_cursor.execute.assert_called_once()
        # Verify INSERT + RETURNING query shape
        sql, params = mock_cursor.execute.call_args[0]
        assert "INSERT INTO canonical_events" in sql
        assert "RETURNING" in sql
        assert "domain_id" in sql
        assert "event_type_id" in sql
        # Params order matches column order in INSERT statement
        assert params[0] == 1  # domain_id
        assert params[1] == 1  # event_type_id
        assert params[2] == [1, 2]  # entities_sorted
        assert params[3] == "[2026-09-04 17:00+00, 2026-09-04 21:00+00]"  # resolution_window
        assert params[4] is None  # resolution_rule_fp
        assert params[5] == nk  # natural_key_hash (bytes passthrough)
        assert params[6] == "Buffalo Bills @ Miami Dolphins, Week 1"  # title
        assert params[7] is None  # description
        assert params[8] == 42  # game_id
        assert params[9] is None  # series_id
        assert params[10] == "proposed"  # lifecycle_phase default
        assert params[11] is None  # metadata None -> NULL

    @patch("precog.database.crud_canonical_events.get_cursor")
    def test_metadata_dict_serialized_as_json(self, mock_get_cursor):
        """metadata dict is JSON-serialized (matching crud_canonical_markets convention)."""
        nk = _sample_natural_key_hash()
        meta = {"source": "espn", "import_run_id": 99}
        expected_row = _full_row_dict(metadata=meta)

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_event(
            domain_id=1,
            event_type_id=1,
            entities_sorted=[1, 2],
            resolution_window="[2026-09-04 17:00+00, 2026-09-04 21:00+00]",
            natural_key_hash=nk,
            title="Test Event",
            metadata=meta,
        )

        params = mock_cursor.execute.call_args[0][1]
        # metadata is the 12th param (index 11)
        json_param = params[11]
        assert isinstance(json_param, str)
        assert json.loads(json_param) == meta

    @patch("precog.database.crud_canonical_events.get_cursor")
    def test_metadata_none_passed_as_null(self, mock_get_cursor):
        """metadata=None is passed as NULL (not the string 'null')."""
        nk = _sample_natural_key_hash()
        expected_row = _full_row_dict(metadata=None)

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_event(
            domain_id=1,
            event_type_id=1,
            entities_sorted=[1, 2],
            resolution_window="[2026-09-04 17:00+00, 2026-09-04 21:00+00]",
            natural_key_hash=nk,
            title="Test Event",
            metadata=None,
        )

        params = mock_cursor.execute.call_args[0][1]
        assert params[11] is None  # NULL, not "null"

    @patch("precog.database.crud_canonical_events.get_cursor")
    def test_lifecycle_phase_default_is_proposed(self, mock_get_cursor):
        """lifecycle_phase defaults to 'proposed' when not passed."""
        nk = _sample_natural_key_hash()
        expected_row = _full_row_dict(lifecycle_phase="proposed")

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_event(
            domain_id=1,
            event_type_id=1,
            entities_sorted=[1, 2],
            resolution_window="[2026-09-04 17:00+00, 2026-09-04 21:00+00]",
            natural_key_hash=nk,
            title="Test Event",
        )

        params = mock_cursor.execute.call_args[0][1]
        # lifecycle_phase is the 11th param (index 10)
        assert params[10] == "proposed"

    @patch("precog.database.crud_canonical_events.get_cursor")
    def test_lifecycle_phase_explicit_override(self, mock_get_cursor):
        """lifecycle_phase can be overridden by caller."""
        nk = _sample_natural_key_hash()
        expected_row = _full_row_dict(lifecycle_phase="matched")

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_event(
            domain_id=1,
            event_type_id=1,
            entities_sorted=[1, 2],
            resolution_window="[2026-09-04 17:00+00, 2026-09-04 21:00+00]",
            natural_key_hash=nk,
            title="Test Event",
            lifecycle_phase="matched",
        )

        params = mock_cursor.execute.call_args[0][1]
        assert params[10] == "matched"

    @patch("precog.database.crud_canonical_events.get_cursor")
    def test_decimal_in_metadata_preserved_via_json(self, mock_get_cursor):
        """Decimal values in metadata round-trip via JSON without precision loss.

        Educational Note:
            ``json.dumps`` cannot serialize Decimal directly, so callers must
            stringify Decimals before passing them in metadata.  This test
            pins the contract: stringified Decimals are preserved verbatim
            through the JSON layer.  Mirrors the
            ``test_crud_canonical_markets_unit.test_decimal_in_metadata_preserved_via_json``
            pattern.
        """
        nk = _sample_natural_key_hash()
        meta = {"settle_threshold": str(Decimal("0.5000"))}
        expected_row = _full_row_dict(metadata=meta)

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_event(
            domain_id=1,
            event_type_id=1,
            entities_sorted=[1, 2],
            resolution_window="[2026-09-04 17:00+00, 2026-09-04 21:00+00]",
            natural_key_hash=nk,
            title="Test Event",
            metadata=meta,
        )

        params = mock_cursor.execute.call_args[0][1]
        deserialized = json.loads(params[11])
        assert deserialized["settle_threshold"] == "0.5000"

    @patch("precog.database.crud_canonical_events.get_cursor")
    def test_natural_key_hash_bytes_passthrough(self, mock_get_cursor):
        """natural_key_hash is passed as raw bytes (BYTEA -- no encoding)."""
        nk = _sample_natural_key_hash(b"unique-suffix")
        assert isinstance(nk, bytes)
        assert len(nk) == 32  # sha256 digest
        expected_row = _full_row_dict(natural_key_hash=nk)

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_event(
            domain_id=1,
            event_type_id=1,
            entities_sorted=[1, 2],
            resolution_window="[2026-09-04 17:00+00, 2026-09-04 21:00+00]",
            natural_key_hash=nk,
            title="Test Event",
        )

        params = mock_cursor.execute.call_args[0][1]
        assert params[5] == nk
        assert isinstance(params[5], bytes)

    @patch("precog.database.crud_canonical_events.get_cursor")
    def test_returning_projects_all_canonical_events_columns(self, mock_get_cursor):
        """Pattern 43 fidelity: the INSERT...RETURNING projection must include all
        16 canonical_events columns. Mirrors Glokta Finding 7 + Ripley Finding 5
        from Cohort 2 (test_crud_canonical_markets_unit.py) -- without this test, a
        future refactor that drops a column from the RETURNING clause would silently
        pass because the mock dict (built by _full_row_dict()) has all keys regardless.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = _full_row_dict()
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_event(
            domain_id=1,
            event_type_id=1,
            entities_sorted=[1, 2],
            resolution_window="[2026-09-04 17:00+00, 2026-09-04 21:00+00]",
            natural_key_hash=_sample_natural_key_hash(),
            title="Test Event",
        )

        sql = mock_cursor.execute.call_args[0][0]
        # Every canonical_events column must appear in the RETURNING projection
        for col in _ALL_CANONICAL_EVENTS_COLUMNS:
            assert col in sql, f"Column {col!r} missing from INSERT...RETURNING projection"


# =============================================================================
# get_canonical_event_by_id
# =============================================================================


@pytest.mark.unit
class TestGetCanonicalEventById:
    """Unit tests for get_canonical_event_by_id -- SELECT by surrogate PK."""

    @patch("precog.database.crud_canonical_events.fetch_one")
    def test_returns_row_dict_when_found(self, mock_fetch_one):
        """Returns the full row dict when a row matches the id."""
        expected_row = _full_row_dict(id=7)
        mock_fetch_one.return_value = expected_row

        result = get_canonical_event_by_id(7)

        assert result == expected_row
        mock_fetch_one.assert_called_once()
        sql, params = mock_fetch_one.call_args[0]
        assert "FROM canonical_events" in sql
        assert "WHERE id = %s" in sql
        assert params == (7,)

    @patch("precog.database.crud_canonical_events.fetch_one")
    def test_returns_none_when_not_found(self, mock_fetch_one):
        """Returns None when no row matches the id."""
        mock_fetch_one.return_value = None

        result = get_canonical_event_by_id(99999)

        assert result is None
        assert mock_fetch_one.call_count == 1
        assert mock_fetch_one.call_args[0][1] == (99999,)

    @patch("precog.database.crud_canonical_events.fetch_one")
    def test_query_selects_all_canonical_events_columns(self, mock_fetch_one):
        """Pattern 43 fidelity: SELECT projection must include all 16 columns."""
        mock_fetch_one.return_value = None

        get_canonical_event_by_id(7)

        sql = mock_fetch_one.call_args[0][0]
        for col in _ALL_CANONICAL_EVENTS_COLUMNS:
            assert col in sql, f"Column {col!r} missing from SELECT projection"


# =============================================================================
# get_canonical_event_by_natural_key_hash
# =============================================================================


@pytest.mark.unit
class TestGetCanonicalEventByNaturalKeyHash:
    """Unit tests for get_canonical_event_by_natural_key_hash -- SELECT by NK hash."""

    @patch("precog.database.crud_canonical_events.fetch_one")
    def test_returns_row_dict_when_found(self, mock_fetch_one):
        """Returns the full row dict when an NK match is found."""
        nk = _sample_natural_key_hash()
        expected_row = _full_row_dict(natural_key_hash=nk)
        mock_fetch_one.return_value = expected_row

        result = get_canonical_event_by_natural_key_hash(nk)

        assert result == expected_row
        sql, params = mock_fetch_one.call_args[0]
        assert "FROM canonical_events" in sql
        assert "WHERE natural_key_hash = %s" in sql
        assert params == (nk,)
        assert isinstance(params[0], bytes)

    @patch("precog.database.crud_canonical_events.fetch_one")
    def test_returns_none_when_not_found(self, mock_fetch_one):
        """Returns None when no canonical event has the given NK hash.

        This is the matcher's "new canonical identity" signal -- a None return
        means the caller should create a new canonical_events row.
        """
        mock_fetch_one.return_value = None
        nk = _sample_natural_key_hash(b"never-seen-before")

        result = get_canonical_event_by_natural_key_hash(nk)

        assert result is None

    @patch("precog.database.crud_canonical_events.fetch_one")
    def test_empty_bytes_passes_through(self, mock_fetch_one):
        """Empty bytes (b'') is passed through unchanged."""
        mock_fetch_one.return_value = None

        result = get_canonical_event_by_natural_key_hash(b"")

        assert result is None
        params = mock_fetch_one.call_args[0][1]
        assert params == (b"",)

    @patch("precog.database.crud_canonical_events.fetch_one")
    def test_query_selects_all_canonical_events_columns(self, mock_fetch_one):
        """Pattern 43 fidelity: NK-hash SELECT projection must include all 16 columns."""
        mock_fetch_one.return_value = None
        get_canonical_event_by_natural_key_hash(b"\xaa\xbb\xcc\xdd")

        sql = mock_fetch_one.call_args[0][0]
        for col in _ALL_CANONICAL_EVENTS_COLUMNS:
            assert col in sql, f"Column {col!r} missing from natural-key-hash SELECT projection"


# =============================================================================
# retire_canonical_event
# =============================================================================


@pytest.mark.unit
class TestRetireCanonicalEvent:
    """Unit tests for retire_canonical_event -- UPDATE retired_at = now()."""

    @patch("precog.database.crud_canonical_events.get_cursor")
    def test_returns_true_when_row_updated(self, mock_get_cursor):
        """Returns True when a row was matched and updated (rowcount=1)."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = retire_canonical_event(7)

        assert result is True
        mock_get_cursor.assert_called_once_with(commit=True)
        sql, params = mock_cursor.execute.call_args[0]
        assert "UPDATE canonical_events" in sql
        assert "retired_at = now()" in sql
        assert "WHERE id = %s" in sql
        assert params == (7,)

    @patch("precog.database.crud_canonical_events.get_cursor")
    def test_returns_false_when_no_row_matched(self, mock_get_cursor):
        """Returns False when no row matched the given id (rowcount=0)."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = retire_canonical_event(99999)

        assert result is False

    @patch("precog.database.crud_canonical_events.get_cursor")
    def test_does_not_write_updated_at_directly(self, mock_get_cursor):
        """retire_canonical_event does NOT explicitly write updated_at.

        The BEFORE UPDATE trigger retrofit (#1007) will refresh ``updated_at``
        automatically once installed.  Until then, ``updated_at`` remains a
        static creation timestamp; either way, this function MUST NOT write
        it directly (Pattern 73 violation -- duplicating the trigger's
        future behavior in application code).  Mirrors the same discipline
        in ``crud_canonical_markets.retire_canonical_market`` even though
        canonical_events does not yet have the trigger.
        """
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        retire_canonical_event(7)

        sql = mock_cursor.execute.call_args[0][0]
        # The SET clause should ONLY touch retired_at, not updated_at
        set_clause = sql.split("WHERE")[0]
        assert "retired_at" in set_clause
        assert "updated_at" not in set_clause


# =============================================================================
# get_canonical_event_domain_id_by_domain
# =============================================================================


@pytest.mark.unit
class TestGetCanonicalEventDomainIdByDomain:
    """Unit tests for get_canonical_event_domain_id_by_domain -- text -> id resolver."""

    @patch("precog.database.crud_canonical_events.fetch_one")
    def test_returns_id_when_domain_seeded(self, mock_fetch_one):
        """Returns the integer id for a seeded domain."""
        mock_fetch_one.return_value = {"id": 1}

        result = get_canonical_event_domain_id_by_domain("sports")

        assert result == 1
        sql, params = mock_fetch_one.call_args[0]
        assert "FROM canonical_event_domains" in sql
        assert "WHERE domain = %s" in sql
        assert params == ("sports",)

    @patch("precog.database.crud_canonical_events.fetch_one")
    def test_returns_none_when_domain_not_seeded(self, mock_fetch_one):
        """Returns None when no canonical_event_domains row matches the given text."""
        mock_fetch_one.return_value = None

        result = get_canonical_event_domain_id_by_domain("unicorn_domain")

        assert result is None

    @patch("precog.database.crud_canonical_events.fetch_one")
    def test_case_sensitive_passthrough(self, mock_fetch_one):
        """Domain text is passed through unchanged (case-sensitive at the DB layer).

        The seed values are lowercase ('sports', 'politics', ...).  Callers
        passing 'Sports' or 'SPORTS' will hit a None result; this CRUD
        function does NOT lowercase or normalize input.  Pinning the
        contract here.
        """
        mock_fetch_one.return_value = None

        result = get_canonical_event_domain_id_by_domain("SPORTS")

        assert result is None
        params = mock_fetch_one.call_args[0][1]
        assert params == ("SPORTS",)  # passed through verbatim


# =============================================================================
# get_canonical_event_type_id_by_domain_and_type
# =============================================================================


@pytest.mark.unit
class TestGetCanonicalEventTypeIdByDomainAndType:
    """Unit tests for get_canonical_event_type_id_by_domain_and_type -- composite resolver."""

    @patch("precog.database.crud_canonical_events.fetch_one")
    def test_returns_id_when_pair_seeded(self, mock_fetch_one):
        """Returns the integer id for a seeded (domain_id, event_type) pair."""
        mock_fetch_one.return_value = {"id": 1}

        result = get_canonical_event_type_id_by_domain_and_type(1, "game")

        assert result == 1
        sql, params = mock_fetch_one.call_args[0]
        assert "FROM canonical_event_types" in sql
        assert "WHERE domain_id = %s AND event_type = %s" in sql
        assert params == (1, "game")

    @patch("precog.database.crud_canonical_events.fetch_one")
    def test_returns_none_when_pair_not_seeded(self, mock_fetch_one):
        """Returns None when no canonical_event_types row matches the pair."""
        mock_fetch_one.return_value = None

        result = get_canonical_event_type_id_by_domain_and_type(1, "unicorn_type")

        assert result is None

    @patch("precog.database.crud_canonical_events.fetch_one")
    def test_case_sensitive_passthrough(self, mock_fetch_one):
        """Event type text is passed through unchanged (case-sensitive)."""
        mock_fetch_one.return_value = None

        result = get_canonical_event_type_id_by_domain_and_type(1, "GAME")

        assert result is None
        params = mock_fetch_one.call_args[0][1]
        assert params == (1, "GAME")  # passed through verbatim
