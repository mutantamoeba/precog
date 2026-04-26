"""Unit tests for crud_canonical_entity module -- Pattern 14 step 4 of the Cohort 1B Slice B retro.

Covers (function-by-function):
    - create_canonical_entity: happy path, JSONB metadata serialization,
      None metadata -> NULL, Decimal preservation through metadata,
      None ref_team_id passthrough (non-team kinds), trigger-raise
      passthrough (Pattern 82 V2 forward-only).
    - get_canonical_entity_by_id: happy path (row found), None (not found).
    - get_canonical_entity_by_kind_and_key: happy path (row found), None
      (not found), composite-key params shape.
    - get_canonical_entity_kind_id_by_kind: happy path (kind found),
      None (kind not seeded), case-sensitivity passthrough.

Pattern 43 (mock fidelity) discipline: mocks return the EXACT shape that the
real query returns -- full row dicts with all canonical_entity columns, no
extra keys, no missing keys.  Mocks of ``get_cursor`` use the
``__enter__`` / ``__exit__`` protocol consistent with
``test_crud_canonical_markets_unit.py``.

Pattern 82 V2 Forward-Only Direction Policy compliance test:
    ``test_crud_does_not_pre_validate_team_invariant`` is a source-grep
    assertion that the CRUD module body contains no early-return
    pre-validation of the polymorphic invariant (Pattern 82 V2 -- the
    DB trigger is the SSOT).  See module-level docstring of
    ``crud_canonical_entity.py`` for the design rationale.

Reference:
    - ``src/precog/database/crud_canonical_entity.py``
    - ``src/precog/database/alembic/versions/0068_canonical_entity_foundation.py``
    - ``tests/unit/database/test_crud_canonical_markets_unit.py`` (style reference)
    - ADR-118 V2.40 (Cohort 1 carry-forward amendment, Item 4 -- Pattern
      82 V2 Forward-Only Direction Policy)
    - DEVELOPMENT_PATTERNS V1.37 Pattern 82 V2 (lines ~12235-12239)
"""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import psycopg2
import pytest

from precog.database.crud_canonical_entity import (
    create_canonical_entity,
    get_canonical_entity_by_id,
    get_canonical_entity_by_kind_and_key,
    get_canonical_entity_kind_id_by_kind,
)


def _full_row_dict(
    *,
    id: int = 7,
    entity_kind_id: int = 1,
    entity_key: str = "BUF-NFL-001",
    display_name: str = "Buffalo Bills",
    ref_team_id: int | None = 1,
    metadata: dict | None = None,
    created_at: datetime | None = None,
) -> dict:
    """Build a full canonical_entity row dict matching the real query shape.

    Pattern 43 fidelity: every key the real RETURNING / SELECT projection
    emits is present, with no extras.  This is the SSOT for "what does a
    canonical_entity row dict look like in tests".  Mirrors the
    ``_full_row_dict`` helper in ``test_crud_canonical_markets_unit.py``.
    """
    if created_at is None:
        created_at = datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC)
    return {
        "id": id,
        "entity_kind_id": entity_kind_id,
        "entity_key": entity_key,
        "display_name": display_name,
        "ref_team_id": ref_team_id,
        "metadata": metadata,
        "created_at": created_at,
    }


# =============================================================================
# create_canonical_entity
# =============================================================================


@pytest.mark.unit
class TestCreateCanonicalEntity:
    """Unit tests for create_canonical_entity -- INSERT + RETURNING happy path."""

    @patch("precog.database.crud_canonical_entity.get_cursor")
    def test_returns_full_row_dict_on_success(self, mock_get_cursor):
        """Returns the full row dict from RETURNING projection."""
        expected_row = _full_row_dict(
            id=7,
            entity_kind_id=1,
            entity_key="BUF-NFL-001",
            display_name="Buffalo Bills",
            ref_team_id=1,
            metadata=None,
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_canonical_entity(
            entity_kind_id=1,
            entity_key="BUF-NFL-001",
            display_name="Buffalo Bills",
            ref_team_id=1,
        )

        assert result == expected_row
        # commit=True must be used because this is a write
        mock_get_cursor.assert_called_once_with(commit=True)
        mock_cursor.execute.assert_called_once()
        # Verify INSERT + RETURNING query shape
        sql, params = mock_cursor.execute.call_args[0]
        assert "INSERT INTO canonical_entity" in sql
        assert "RETURNING" in sql
        assert "entity_kind_id" in sql
        assert "entity_key" in sql
        # Params order matches column order in INSERT statement
        assert params[0] == 1  # entity_kind_id
        assert params[1] == "BUF-NFL-001"  # entity_key
        assert params[2] == "Buffalo Bills"  # display_name
        assert params[3] == 1  # ref_team_id
        assert params[4] is None  # metadata None -> NULL

    @patch("precog.database.crud_canonical_entity.get_cursor")
    def test_metadata_dict_serialized_as_json(self, mock_get_cursor):
        """metadata dict is JSON-serialized (matching crud_canonical_markets convention)."""
        meta = {"source": "espn", "import_run_id": 99}
        expected_row = _full_row_dict(metadata=meta)

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_entity(
            entity_kind_id=2,
            entity_key="MCGREGOR-CONOR",
            display_name="Conor McGregor",
            ref_team_id=None,
            metadata=meta,
        )

        params = mock_cursor.execute.call_args[0][1]
        # metadata is the 5th param (index 4)
        json_param = params[4]
        assert isinstance(json_param, str)
        assert json.loads(json_param) == meta

    @patch("precog.database.crud_canonical_entity.get_cursor")
    def test_metadata_none_passed_as_null(self, mock_get_cursor):
        """metadata=None is passed as NULL (not the string 'null')."""
        expected_row = _full_row_dict(metadata=None)

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_entity(
            entity_kind_id=1,
            entity_key="MIA-NFL-002",
            display_name="Miami Dolphins",
            ref_team_id=2,
            metadata=None,
        )

        params = mock_cursor.execute.call_args[0][1]
        assert params[4] is None  # NULL, not "null"

    @patch("precog.database.crud_canonical_entity.get_cursor")
    def test_ref_team_id_can_be_none(self, mock_get_cursor):
        """ref_team_id=None is passed through unchanged.

        Pattern 82 V2 forward-only: the trigger only fires when entity_kind
        resolves to 'team'.  For non-team kinds (e.g., 'fighter'), NULL
        ref_team_id is the typical, valid value -- the CRUD layer trusts
        the trigger to skip non-team rows and does NOT pre-validate.
        """
        expected_row = _full_row_dict(entity_kind_id=2, ref_team_id=None)

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_entity(
            entity_kind_id=2,  # fighter
            entity_key="MCGREGOR-CONOR",
            display_name="Conor McGregor",
            ref_team_id=None,
        )

        params = mock_cursor.execute.call_args[0][1]
        assert params[3] is None  # ref_team_id

    @patch("precog.database.crud_canonical_entity.get_cursor")
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
        meta = {"settle_threshold": str(Decimal("0.5000"))}
        expected_row = _full_row_dict(metadata=meta)

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = expected_row
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_entity(
            entity_kind_id=1,
            entity_key="BUF-NFL-001",
            display_name="Buffalo Bills",
            ref_team_id=1,
            metadata=meta,
        )

        params = mock_cursor.execute.call_args[0][1]
        deserialized = json.loads(params[4])
        assert deserialized["settle_threshold"] == "0.5000"

    @patch("precog.database.crud_canonical_entity.get_cursor")
    def test_propagates_trigger_raise_exception_unwrapped(self, mock_get_cursor):
        """Pattern 82 V2 forward-only: trigger RAISE EXCEPTION must propagate unwrapped.

        The CONSTRAINT TRIGGER ``trg_canonical_entity_team_backref`` is the
        single source of truth for the polymorphic invariant
        (entity_kind='team' => ref_team_id NOT NULL).  When it fires,
        psycopg2 raises ``psycopg2.errors.RaiseException``.  The CRUD
        layer MUST NOT catch and re-raise (would obscure the DB origin)
        nor wrap (would hide the canonical exception class from callers).
        This test pins that propagation contract.
        """
        mock_cursor = MagicMock()
        # Simulate the trigger firing on INSERT
        # psycopg2.errors.RaiseException is the canonical class for plpgsql
        # RAISE EXCEPTION (subclass of psycopg2.IntegrityError).
        mock_cursor.execute.side_effect = psycopg2.errors.RaiseException(
            "canonical_entity: entity_kind=team requires ref_team_id NOT NULL"
        )
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(psycopg2.errors.RaiseException) as excinfo:
            create_canonical_entity(
                entity_kind_id=1,  # 'team'
                entity_key="TEST-1021-trigger-fire",
                display_name="Test Team",
                ref_team_id=None,  # Pattern 82 V2 violation
            )
        assert "ref_team_id NOT NULL" in str(excinfo.value)

    @patch("precog.database.crud_canonical_entity.get_cursor")
    def test_returning_projects_all_canonical_entity_columns(self, mock_get_cursor):
        """Pattern 43 fidelity: the INSERT...RETURNING projection must include all
        7 canonical_entity columns. Mirrors Glokta Finding 7 + Ripley Finding 5
        from Cohort 2 (test_crud_canonical_markets_unit.py) -- without this test, a
        future refactor that drops a column from the RETURNING clause would silently
        pass because the mock dict (built by _full_row_dict()) has all keys regardless.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = _full_row_dict()
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor
        # #1050 nit 4: explicit __exit__ for consistency with the other tests
        # in TestCreateCanonicalEntity (e.g. the trigger-fire test sets both).
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_canonical_entity(
            entity_kind_id=1,
            entity_key="BUF-NFL-001",
            display_name="Buffalo Bills",
            ref_team_id=1,
        )

        sql = mock_cursor.execute.call_args[0][0]
        # Every canonical_entity column must appear in the RETURNING projection
        for col in (
            "id",
            "entity_kind_id",
            "entity_key",
            "display_name",
            "ref_team_id",
            "metadata",
            "created_at",
        ):
            assert col in sql, f"Column {col!r} missing from INSERT...RETURNING projection"


# =============================================================================
# get_canonical_entity_by_id
# =============================================================================


@pytest.mark.unit
class TestGetCanonicalEntityById:
    """Unit tests for get_canonical_entity_by_id -- SELECT by surrogate PK."""

    @patch("precog.database.crud_canonical_entity.fetch_one")
    def test_returns_row_dict_when_found(self, mock_fetch_one):
        """Returns the full row dict when a row matches the id."""
        expected_row = _full_row_dict(id=7)
        mock_fetch_one.return_value = expected_row

        result = get_canonical_entity_by_id(7)

        assert result == expected_row
        mock_fetch_one.assert_called_once()
        sql, params = mock_fetch_one.call_args[0]
        assert "FROM canonical_entity" in sql
        assert "WHERE id = %s" in sql
        assert params == (7,)

    @patch("precog.database.crud_canonical_entity.fetch_one")
    def test_returns_none_when_not_found(self, mock_fetch_one):
        """Returns None when no row matches the id."""
        mock_fetch_one.return_value = None

        result = get_canonical_entity_by_id(99999)

        assert result is None
        # Verify the call happened with the expected id parameter
        # (SQL substring check is in test_query_selects_all_canonical_entity_columns)
        assert mock_fetch_one.call_count == 1
        assert mock_fetch_one.call_args[0][1] == (99999,)

    @patch("precog.database.crud_canonical_entity.fetch_one")
    def test_query_selects_all_canonical_entity_columns(self, mock_fetch_one):
        """Verify the SELECT projection includes all canonical_entity columns.

        Pattern 43 fidelity: the projection must match the columns that
        callers downstream expect to see in the returned dict.
        """
        mock_fetch_one.return_value = None

        get_canonical_entity_by_id(7)

        sql = mock_fetch_one.call_args[0][0]
        for col in (
            "id",
            "entity_kind_id",
            "entity_key",
            "display_name",
            "ref_team_id",
            "metadata",
            "created_at",
        ):
            assert col in sql, f"Column {col!r} missing from SELECT projection"


# =============================================================================
# get_canonical_entity_by_kind_and_key
# =============================================================================


@pytest.mark.unit
class TestGetCanonicalEntityByKindAndKey:
    """Unit tests for get_canonical_entity_by_kind_and_key -- SELECT by composite NK."""

    @patch("precog.database.crud_canonical_entity.fetch_one")
    def test_returns_row_dict_when_found(self, mock_fetch_one):
        """Returns the full row dict when a (kind_id, key) pair matches."""
        expected_row = _full_row_dict(id=7, entity_kind_id=1, entity_key="BUF-NFL-001")
        mock_fetch_one.return_value = expected_row

        result = get_canonical_entity_by_kind_and_key(1, "BUF-NFL-001")

        assert result == expected_row
        sql, params = mock_fetch_one.call_args[0]
        assert "FROM canonical_entity" in sql
        assert "WHERE entity_kind_id = %s AND entity_key = %s" in sql
        assert params == (1, "BUF-NFL-001")

    @patch("precog.database.crud_canonical_entity.fetch_one")
    def test_returns_none_when_not_found(self, mock_fetch_one):
        """Returns None when no row matches (caller should create new).

        This is the "new canonical identity" signal -- a None return means
        the caller should create a new canonical_entity row.
        """
        mock_fetch_one.return_value = None

        result = get_canonical_entity_by_kind_and_key(1, "NEVER-SEEN-BEFORE")

        assert result is None

    @patch("precog.database.crud_canonical_entity.fetch_one")
    def test_query_selects_all_canonical_entity_columns(self, mock_fetch_one):
        """Pattern 43 fidelity: the (kind, key) lookup's SELECT projection must
        include all 7 canonical_entity columns. Mirrors the natural-key-hash
        projection-fidelity test in test_crud_canonical_markets_unit.py --
        without this test, a future refactor that drops a column from the
        composite-key SELECT would silently pass because the mock dict (built
        by _full_row_dict()) has all keys regardless.
        """
        mock_fetch_one.return_value = None

        get_canonical_entity_by_kind_and_key(1, "BUF-NFL-001")

        sql = mock_fetch_one.call_args[0][0]
        for col in (
            "id",
            "entity_kind_id",
            "entity_key",
            "display_name",
            "ref_team_id",
            "metadata",
            "created_at",
        ):
            assert col in sql, f"Column {col!r} missing from kind-and-key SELECT projection"

    @patch("precog.database.crud_canonical_entity.fetch_one")
    def test_empty_string_key_passes_through(self, mock_fetch_one):
        """Empty entity_key string is passed through unchanged.

        Edge case: in production callers should never pass empty entity_key
        (the column is NOT NULL but empty TEXT is technically valid storage),
        but this CRUD function does not validate input -- it forwards the
        text to the lookup.  Pinning the contract here.
        """
        mock_fetch_one.return_value = None

        result = get_canonical_entity_by_kind_and_key(1, "")

        assert result is None
        params = mock_fetch_one.call_args[0][1]
        assert params == (1, "")


# =============================================================================
# get_canonical_entity_kind_id_by_kind
# =============================================================================


@pytest.mark.unit
class TestGetCanonicalEntityKindIdByKind:
    """Unit tests for get_canonical_entity_kind_id_by_kind -- text -> id resolver."""

    @patch("precog.database.crud_canonical_entity.fetch_one")
    def test_returns_id_when_kind_seeded(self, mock_fetch_one):
        """Returns the integer id for a seeded entity_kind."""
        mock_fetch_one.return_value = {"id": 1}

        result = get_canonical_entity_kind_id_by_kind("team")

        assert result == 1
        sql, params = mock_fetch_one.call_args[0]
        assert "FROM canonical_entity_kinds" in sql
        assert "WHERE entity_kind = %s" in sql
        assert params == ("team",)

    @patch("precog.database.crud_canonical_entity.fetch_one")
    def test_returns_none_when_kind_not_seeded(self, mock_fetch_one):
        """Returns None when no canonical_entity_kinds row matches the given text."""
        mock_fetch_one.return_value = None

        result = get_canonical_entity_kind_id_by_kind("unicorn")

        assert result is None

    @patch("precog.database.crud_canonical_entity.fetch_one")
    def test_case_sensitive_passthrough(self, mock_fetch_one):
        """Kind text is passed through unchanged (case-sensitive at the DB layer).

        The seed values are lowercase ('team', 'fighter', ...).  Callers
        passing 'Team' or 'TEAM' will hit a None result; this CRUD function
        does NOT lowercase or normalize input.  Pinning the contract here.
        """
        mock_fetch_one.return_value = None

        result = get_canonical_entity_kind_id_by_kind("TEAM")

        assert result is None
        params = mock_fetch_one.call_args[0][1]
        assert params == ("TEAM",)  # passed through verbatim


# =============================================================================
# Pattern 82 V2 Forward-Only Direction Policy compliance (source-grep test)
# =============================================================================


@pytest.mark.unit
class TestPattern82V2ForwardOnlyCompliance:
    """Source-grep test that crud_canonical_entity does NOT pre-validate the
    polymorphic invariant.

    Pattern 82 V2 (DEVELOPMENT_PATTERNS V1.37 lines ~12235-12239): the DB
    trigger ``trg_canonical_entity_team_backref`` is the single source of
    truth for the rule ``entity_kind='team' => ref_team_id NOT NULL``.  The
    application layer MUST NOT pre-validate.  This test enforces that
    discipline by source-grepping the CRUD module body for forbidden
    pre-validation patterns.

    Why a source-grep test instead of behavioral?  A behavioral test (e.g.,
    "calling create_canonical_entity does not raise ValueError before the
    INSERT runs") cannot prove a NEGATIVE -- a missing-now branch could be
    silently added later.  A source-grep test pins the discipline at the
    code-review level: any future PR that introduces a forbidden pattern
    will fail this test, surfacing the Pattern 73 / Pattern 82 V2
    violation immediately.
    """

    def test_crud_does_not_pre_validate_team_invariant(self):
        """The CRUD module body MUST NOT contain a pre-validation guard
        for the polymorphic invariant.

        Forbidden patterns (source-grep):
            * ``raise ValueError`` (would indicate app-layer pre-validation)
            * ``if entity_kind == 'team'`` paired with a NULL check
            * ``raise <anything>`` inside create_canonical_entity body
              (other than re-raising via psycopg2 propagation, which is
              implicit -- not a literal raise statement in the module)
        """
        crud_module_path = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "precog"
            / "database"
            / "crud_canonical_entity.py"
        )
        assert crud_module_path.exists(), (
            f"crud_canonical_entity.py not found at {crud_module_path} -- "
            "Pattern 82 V2 source-grep test cannot run"
        )
        source = crud_module_path.read_text(encoding="utf-8")

        # Strip docstrings + comments crudely: split on lines, drop any line
        # that starts with whitespace + '#' or is inside triple-quoted
        # blocks.  We use a state machine over lines so the source-grep
        # operates on actual executable code only.
        in_docstring = False
        executable_lines = []
        for raw_line in source.splitlines():
            stripped = raw_line.strip()
            # Toggle docstring boundary on any line that opens or closes
            # a triple-quoted block.  Handles """foo""" on a single line
            # (toggle twice = no-op) and multi-line blocks correctly.
            triple_quote_count = stripped.count('"""')
            if triple_quote_count % 2 == 1:
                in_docstring = not in_docstring
                # Skip the boundary line itself (it's part of the docstring)
                continue
            if in_docstring:
                continue
            # Skip pure-comment lines
            if stripped.startswith("#"):
                continue
            executable_lines.append(raw_line)
        executable_source = "\n".join(executable_lines)

        # Forbidden: any literal raise statement in executable code.  The
        # module's only valid failure mode is psycopg2 propagation (no
        # explicit raise in the function bodies).
        assert "raise " not in executable_source, (
            "Pattern 82 V2 violation: crud_canonical_entity.py contains an "
            "explicit ``raise`` statement in executable code.  The module "
            "must NOT pre-validate; the DB trigger is the SSOT.  If you "
            "need to add a validation here, file an issue first."
        )

        # Forbidden: any reference to the team-kind invariant in executable
        # code (the rule is encoded in the trigger; mentioning it in code
        # would be a Pattern 73 violation -- duplicating the rule text).
        assert "entity_kind == 'team'" not in executable_source, (
            "Pattern 82 V2 violation: crud_canonical_entity.py references "
            "the entity_kind='team' invariant in executable code.  The DB "
            "trigger trg_canonical_entity_team_backref is the SSOT for "
            "this rule."
        )
        assert 'entity_kind == "team"' not in executable_source, (
            "Pattern 82 V2 violation: crud_canonical_entity.py references "
            "the entity_kind='team' invariant in executable code.  The DB "
            "trigger trg_canonical_entity_team_backref is the SSOT for "
            "this rule."
        )
