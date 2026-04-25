"""Unit tests for crud_canonical_markets module â€" Pattern 14 step 4 of the Cohort 2 bundle.

Covers (function-by-function):
    - create_canonical_market: happy path, JSONB metadata serialization,
      None metadata â†' NULL, Decimal preservation through metadata, BYTEA
      natural_key_hash passthrough.
    - get_canonical_market_by_id: happy path (row found), None (not found).
    - get_canonical_market_by_natural_key_hash: happy path (row found), None
      (not found), BYTEA params shape.
    - retire_canonical_market: True (row updated), False (no row).
    - get_canonical_for_platform_market: raises NotImplementedError (stub
      until Migration 0071 ships canonical_market_links).

Pattern 43 (mock fidelity) discipline: mocks return the EXACT shape that the
real query returns â€" full row dicts with all canonical_markets columns, no
extra keys, no missing keys.  Mocks of ``get_cursor`` use the
``__enter__`` / ``__exit__`` protocol consistent with
``test_crud_events_unit.py``.

Reference:
    - ``src/precog/database/crud_canonical_markets.py``
    - ``src/precog/database/alembic/versions/0069_canonical_markets_foundation.py``
    - ``tests/unit/database/test_crud_events_unit.py`` (style reference)
    - ADR-118 V2.39 Cohort 2 amendment (Holden Finding 11 â€" Pattern 14 5-step bundle)
"""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_canonical_markets import (
    create_canonical_market,
    get_canonical_for_platform_market,
    get_canonical_market_by_id,
    get_canonical_market_by_natural_key_hash,
    retire_canonical_market,
)


def _sample_natural_key_hash(suffix: bytes = b"sample") -> bytes:
    """Return a 32-byte sha256 digest for use as a natural_key_hash test value."""
    return hashlib.sha256(b"canonical|market|nk|" + suffix).digest()


def _full_row_dict(
    *,
    id: int = 7,
    canonical_event_id: int = 42,
    market_type_general: str = "binary",
    outcome_label: str | None = "Yes",
    natural_key_hash: bytes | None = None,
    metadata: dict | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    retired_at: datetime | None = None,
) -> dict:
    """Build a full canonical_markets row dict matching the real query shape.

    Pattern 43 fidelity: every key the real RETURNING / SELECT projection
    emits is present, with no extras.  This is the SSOT for "what does a
    canonical_markets row dict look like in tests".
    """
    if natural_key_hash is None:
        natural_key_hash = _sample_natural_key_hash()
    if created_at is None:
        created_at = datetime(2026, 4, 24, 12, 0, 0, tzinfo=UTC)
    if updated_at is None:
        updated_at = datetime(2026, 4, 24, 12, 0, 0, tzinfo=UTC)
    return {
        "id": id,
        "canonical_event_id": canonical_event_id,
        "market_type_general": market_type_general,
        "outcome_label": outcome_label,
        "natural_key_hash": natural_key_hash,
        "metadata": metadata,
        "created_at": created_at,
        "updated_at": updated_at,
        "retired_at": retired_at,
    }


# =============================================================================
# create_canonical_market
# =============================================================================


@pytest.mark.unit
class TestCreateCanonicalMarket:
    """Unit tests for create_canonical_market â€" INSERT + RETURNING happy path."""

    @patch("precog.database.crud_canonical_markets.get_cursor")
    def test_returns_full_row_dict_on_success(self, mock_get_cursor):
        """Returns the full row dict from RETURNING projection."""
        nk = _sample_natural_key_hash()
        expected_row = _full_row_dict(
            id=7,
            canonical_event_id=42,
            market_type_general="binary",
            outcome_label="Yes",
            natural_key_hash=nk,
            metadata=None,
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_canonical_market(
            canonical_event_id=42,
            market_type_general="binary",
            outcome_label="Yes",
            natural_key_hash=nk,
        )

        assert result == expected_row
        # commit=True must be used because this is a write
        mock_get_cursor.assert_called_once_with(commit=True)
        mock_cursor.execute.assert_called_once()
        # Verify INSERT + RETURNING query shape
        sql, params = mock_cursor.execute.call_args[0]
        assert "INSERT INTO canonical_markets" in sql
        assert "RETURNING" in sql
        assert "canonical_event_id" in sql
        assert "market_type_general" in sql
        # Params order matches column order in INSERT statement
        assert params[0] == 42  # canonical_event_id
        assert params[1] == "binary"  # market_type_general
        assert params[2] == "Yes"  # outcome_label
        assert params[3] == nk  # natural_key_hash (bytes passthrough)
        assert params[4] is None  # metadata None â†' NULL

    @patch("precog.database.crud_canonical_markets.get_cursor")
    def test_metadata_dict_serialized_as_json(self, mock_get_cursor):
        """metadata dict is JSON-serialized (matching crud_events convention)."""
        nk = _sample_natural_key_hash()
        meta = {"source": "kalshi", "import_run_id": 99}
        expected_row = _full_row_dict(metadata=meta)

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_market(
            canonical_event_id=42,
            market_type_general="categorical",
            outcome_label=None,
            natural_key_hash=nk,
            metadata=meta,
        )

        params = mock_cursor.execute.call_args[0][1]
        # metadata is the 5th param (index 4)
        json_param = params[4]
        assert isinstance(json_param, str)
        assert json.loads(json_param) == meta

    @patch("precog.database.crud_canonical_markets.get_cursor")
    def test_metadata_none_passed_as_null(self, mock_get_cursor):
        """metadata=None is passed as NULL (not the string 'null')."""
        nk = _sample_natural_key_hash()
        expected_row = _full_row_dict(metadata=None)

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_market(
            canonical_event_id=42,
            market_type_general="scalar",
            outcome_label="Over 45.5",
            natural_key_hash=nk,
            metadata=None,
        )

        params = mock_cursor.execute.call_args[0][1]
        assert params[4] is None  # NULL, not "null"

    @patch("precog.database.crud_canonical_markets.get_cursor")
    def test_outcome_label_can_be_none(self, mock_get_cursor):
        """outcome_label=None is passed as NULL (column is nullable per DDL)."""
        nk = _sample_natural_key_hash()
        expected_row = _full_row_dict(outcome_label=None)

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_market(
            canonical_event_id=42,
            market_type_general="binary",
            outcome_label=None,
            natural_key_hash=nk,
        )

        params = mock_cursor.execute.call_args[0][1]
        assert params[2] is None  # outcome_label

    @patch("precog.database.crud_canonical_markets.get_cursor")
    def test_decimal_in_metadata_preserved_via_json(self, mock_get_cursor):
        """Decimal values in metadata round-trip via JSON without precision loss.

        Educational Note:
            ``json.dumps`` cannot serialize Decimal directly, so callers must
            stringify Decimals before passing them in metadata.  This test
            pins the contract: stringified Decimals are preserved verbatim
            through the JSON layer.  Mirrors the
            ``test_crud_events_unit.test_decimal_precision_preserved`` pattern.
        """
        nk = _sample_natural_key_hash()
        meta = {"settlement_value": str(Decimal("0.3333"))}
        expected_row = _full_row_dict(metadata=meta)

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_market(
            canonical_event_id=42,
            market_type_general="scalar",
            outcome_label="Q1 EPS",
            natural_key_hash=nk,
            metadata=meta,
        )

        params = mock_cursor.execute.call_args[0][1]
        deserialized = json.loads(params[4])
        assert deserialized["settlement_value"] == "0.3333"

    @patch("precog.database.crud_canonical_markets.get_cursor")
    def test_natural_key_hash_bytes_passthrough(self, mock_get_cursor):
        """natural_key_hash is passed as raw bytes (BYTEA â€" no encoding)."""
        nk = _sample_natural_key_hash(b"unique-suffix")
        assert isinstance(nk, bytes)
        assert len(nk) == 32  # sha256 digest
        expected_row = _full_row_dict(natural_key_hash=nk)

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_market(
            canonical_event_id=42,
            market_type_general="binary",
            outcome_label="Yes",
            natural_key_hash=nk,
        )

        params = mock_cursor.execute.call_args[0][1]
        assert params[3] == nk
        assert isinstance(params[3], bytes)

    @patch("precog.database.crud_canonical_markets.get_cursor")
    def test_returning_projects_all_canonical_markets_columns(self, mock_get_cursor):
        """Pattern 43 fidelity: the INSERT...RETURNING projection must include all
        9 canonical_markets columns. Closes Glokta Finding 7 + Ripley Finding 5 --
        without this test, a future refactor that drops a column from the RETURNING
        clause would silently pass because the mock dict (built by _full_row_dict())
        has all keys regardless of what RETURNING actually projects.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = _full_row_dict()
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        create_canonical_market(
            canonical_event_id=1,
            market_type_general="binary",
            outcome_label="Yes",
            natural_key_hash=b"\x00" * 32,
        )

        sql = mock_cursor.execute.call_args[0][0]
        # Every canonical_markets column must appear in the RETURNING projection
        for col in (
            "id",
            "canonical_event_id",
            "market_type_general",
            "outcome_label",
            "natural_key_hash",
            "metadata",
            "created_at",
            "updated_at",
            "retired_at",
        ):
            assert col in sql, f"Column {col!r} missing from INSERT...RETURNING projection"


# =============================================================================
# get_canonical_market_by_id
# =============================================================================


@pytest.mark.unit
class TestGetCanonicalMarketById:
    """Unit tests for get_canonical_market_by_id â€" SELECT by surrogate PK."""

    @patch("precog.database.crud_canonical_markets.fetch_one")
    def test_returns_row_dict_when_found(self, mock_fetch_one):
        """Returns the full row dict when a row matches the id."""
        expected_row = _full_row_dict(id=7)
        mock_fetch_one.return_value = expected_row

        result = get_canonical_market_by_id(7)

        assert result == expected_row
        mock_fetch_one.assert_called_once()
        sql, params = mock_fetch_one.call_args[0]
        assert "FROM canonical_markets" in sql
        assert "WHERE id = %s" in sql
        assert params == (7,)

    @patch("precog.database.crud_canonical_markets.fetch_one")
    def test_returns_none_when_not_found(self, mock_fetch_one):
        """Returns None when no row matches the id."""
        mock_fetch_one.return_value = None

        result = get_canonical_market_by_id(99999)

        assert result is None
        # Verify the call happened with the expected id parameter
        # (SQL substring check is in test_query_selects_all_canonical_markets_columns)
        assert mock_fetch_one.call_count == 1
        assert mock_fetch_one.call_args[0][1] == (99999,)

    @patch("precog.database.crud_canonical_markets.fetch_one")
    def test_query_selects_all_canonical_markets_columns(self, mock_fetch_one):
        """Verify the SELECT projection includes all canonical_markets columns.

        Pattern 43 fidelity: the projection must match the columns that
        callers downstream expect to see in the returned dict.
        """
        mock_fetch_one.return_value = None

        get_canonical_market_by_id(7)

        sql = mock_fetch_one.call_args[0][0]
        for col in (
            "id",
            "canonical_event_id",
            "market_type_general",
            "outcome_label",
            "natural_key_hash",
            "metadata",
            "created_at",
            "updated_at",
            "retired_at",
        ):
            assert col in sql, f"Column {col!r} missing from SELECT projection"

    @patch("precog.database.crud_canonical_markets.fetch_one")
    def test_natural_key_hash_query_selects_all_canonical_markets_columns(self, mock_fetch_one):
        """Pattern 43 fidelity: the natural-key-hash lookup's SELECT projection must
        include all 9 canonical_markets columns. Closes Glokta Finding 7 + Ripley
        Finding 5 -- without this test, a future refactor that drops a column from
        the natural-key-hash SELECT would silently pass because the mock dict (built
        by _full_row_dict()) has all keys regardless.
        """
        from precog.database.crud_canonical_markets import get_canonical_market_by_natural_key_hash

        mock_fetch_one.return_value = None
        get_canonical_market_by_natural_key_hash(b"\xaa\xbb\xcc\xdd")

        sql = mock_fetch_one.call_args[0][0]
        for col in (
            "id",
            "canonical_event_id",
            "market_type_general",
            "outcome_label",
            "natural_key_hash",
            "metadata",
            "created_at",
            "updated_at",
            "retired_at",
        ):
            assert col in sql, f"Column {col!r} missing from natural-key-hash SELECT projection"


# =============================================================================
# get_canonical_market_by_natural_key_hash
# =============================================================================


@pytest.mark.unit
class TestGetCanonicalMarketByNaturalKeyHash:
    """Unit tests for get_canonical_market_by_natural_key_hash â€" SELECT by NK hash."""

    @patch("precog.database.crud_canonical_markets.fetch_one")
    def test_returns_row_dict_when_found(self, mock_fetch_one):
        """Returns the full row dict when an NK match is found."""
        nk = _sample_natural_key_hash()
        expected_row = _full_row_dict(natural_key_hash=nk)
        mock_fetch_one.return_value = expected_row

        result = get_canonical_market_by_natural_key_hash(nk)

        assert result == expected_row
        sql, params = mock_fetch_one.call_args[0]
        assert "FROM canonical_markets" in sql
        assert "WHERE natural_key_hash = %s" in sql
        assert params == (nk,)
        assert isinstance(params[0], bytes)

    @patch("precog.database.crud_canonical_markets.fetch_one")
    def test_returns_none_when_not_found(self, mock_fetch_one):
        """Returns None when no canonical market has the given NK hash.

        This is the matcher's "new canonical identity" signal â€" a None return
        means the caller should create a new canonical_markets row.
        """
        mock_fetch_one.return_value = None
        nk = _sample_natural_key_hash(b"never-seen-before")

        result = get_canonical_market_by_natural_key_hash(nk)

        assert result is None

    @patch("precog.database.crud_canonical_markets.fetch_one")
    def test_empty_bytes_passes_through(self, mock_fetch_one):
        """Empty bytes (b'') is passed through unchanged.

        Edge case: in production callers should never pass empty bytes (the
        column is NOT NULL but empty BYTEA is technically valid storage),
        but this CRUD function does not validate input â€" it forwards the
        bytes to the lookup.  Pinning the contract here.
        """
        mock_fetch_one.return_value = None

        result = get_canonical_market_by_natural_key_hash(b"")

        assert result is None
        params = mock_fetch_one.call_args[0][1]
        assert params == (b"",)


# =============================================================================
# retire_canonical_market
# =============================================================================


@pytest.mark.unit
class TestRetireCanonicalMarket:
    """Unit tests for retire_canonical_market â€" UPDATE retired_at = now()."""

    @patch("precog.database.crud_canonical_markets.get_cursor")
    def test_returns_true_when_row_updated(self, mock_get_cursor):
        """Returns True when a row was matched and updated (rowcount=1)."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = retire_canonical_market(7)

        assert result is True
        mock_get_cursor.assert_called_once_with(commit=True)
        sql, params = mock_cursor.execute.call_args[0]
        assert "UPDATE canonical_markets" in sql
        assert "retired_at = now()" in sql
        assert "WHERE id = %s" in sql
        assert params == (7,)

    @patch("precog.database.crud_canonical_markets.get_cursor")
    def test_returns_false_when_no_row_matched(self, mock_get_cursor):
        """Returns False when no row matched the given id (rowcount=0)."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = retire_canonical_market(99999)

        assert result is False

    @patch("precog.database.crud_canonical_markets.get_cursor")
    def test_does_not_write_updated_at_directly(self, mock_get_cursor):
        """retire_canonical_market does NOT explicitly write updated_at.

        The BEFORE UPDATE trigger ``trg_canonical_markets_updated_at``
        refreshes ``updated_at`` automatically.  Callers (and this function)
        must rely on the trigger; writing updated_at here would be a
        Pattern 73 violation (duplicating the trigger's behavior in
        application code).
        """
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        retire_canonical_market(7)

        sql = mock_cursor.execute.call_args[0][0]
        # The SET clause should ONLY touch retired_at, not updated_at
        set_clause = sql.split("WHERE")[0]
        assert "retired_at" in set_clause
        assert "updated_at" not in set_clause


# =============================================================================
# get_canonical_for_platform_market (stub â€" raises NotImplementedError)
# =============================================================================


@pytest.mark.unit
class TestGetCanonicalForPlatformMarketStub:
    """Unit tests pinning the NotImplementedError stub contract.

    The helper exists at-signature per ADR-118 V2.39 Cohort 2 amendment
    Pattern 14 footnote (Holden Finding 11) so the Pattern 73 SSOT contract
    for "give me canonical for this market" (Galadriel Finding 5) is
    published before consumers can implement against it.  The body cannot
    land until Migration 0071 ships ``canonical_market_links`` (Cohort 3);
    until then, the helper raises ``NotImplementedError``.
    """

    def test_raises_not_implemented_error(self):
        """Calling the helper raises NotImplementedError (no DB call attempted)."""
        with pytest.raises(NotImplementedError):
            get_canonical_for_platform_market(platform_market_id=42)

    def test_error_message_cites_migration_0071_and_design_rationale(self):
        """The NotImplementedError message documents WHY the helper is stubbed.

        Future readers (or AI agents picking up Cohort 3) need the error to
        explain the contract surface and the unblocking migration.  Pinning
        the message keeps the rationale findable from the failure trace,
        not just the docstring.
        """
        with pytest.raises(NotImplementedError) as excinfo:
            get_canonical_for_platform_market(platform_market_id=42)
        msg = str(excinfo.value)
        assert "Migration 0071" in msg
        assert "canonical_market_links" in msg
        assert "Cohort 3" in msg
        # Both findings cited so future readers can trace the design memo
        assert "Galadriel Finding 5" in msg
        assert "Holden Finding 11" in msg

    def test_error_raised_for_any_input(self):
        """Even for edge-case inputs, the helper consistently raises NotImplementedError."""
        for bad_input in (0, -1, 999_999_999):
            with pytest.raises(NotImplementedError):
                get_canonical_for_platform_market(platform_market_id=bad_input)
