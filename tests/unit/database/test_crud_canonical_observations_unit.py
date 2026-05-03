"""Unit tests for crud_canonical_observations module — Cohort 4 slot 0078.

Covers (function-by-function):
    - append_observation_row: happy path + Pattern 73 SSOT real-guard
      validation on observation_kind + composite-PK-tuple return shape +
      payload_hash derivation determinism + JSON-serialization
      correctness for the payload column.
    - _compute_payload_hash: SHA-256 determinism + key-order independence
      + distinct hashes for distinct payloads.

Pattern 73 SSOT real-guard discipline (slot 0073 strengthened convention):
    OBSERVATION_KIND_VALUES is imported and USED in real-guard
    ValueError-raising validation in the SUT.  The unit test asserts
    the validation fires; the side-effect-only convention does NOT
    survive into slot 0078.

Pattern 43 (mock fidelity) discipline: mocks return the EXACT shape that
the real query returns.  The append RETURNING projection is
``(id, ingested_at)`` — a composite-PK tuple — so the mock fetchone
returns ``{"id": <int>, "ingested_at": <datetime>}``.

Reference:
    - ``src/precog/database/crud_canonical_observations.py``
    - ``src/precog/database/alembic/versions/0078_canonical_observations.py``
    - ``tests/unit/database/test_crud_canonical_match_log_unit.py`` (style
      reference + restricted-API discipline precedent)
    - ``memory/build_spec_0078_pm_memo.md`` § 8a (unit test surface
      requirements)
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from precog.database.constants import OBSERVATION_KIND_VALUES
from precog.database.crud_canonical_observations import (
    _compute_payload_hash,
    append_observation_row,
)


def _wire_observation_cursor_mock(
    mock_get_cursor_factory: MagicMock,
    *,
    returning_id: int = 99,
    returning_ingested_at: datetime | None = None,
) -> MagicMock:
    """Wire ``get_cursor`` mock so it acts as a context manager + RETURNING.

    Pattern 43 fidelity: the canonical_observations RETURNING projection
    is composite ``(id, ingested_at)``; the mock cursor's fetchone
    returns a RealDictCursor-style dict with both keys.  Mirrors the
    slot-0073 ``wire_get_cursor_mock`` shape but tailored to the
    composite-PK return.

    Cannot reuse the slot-0073 helper because that one only sets ``id``;
    the canonical_observations RETURNING is composite per V2.43 Item 3.
    """
    if returning_ingested_at is None:
        returning_ingested_at = datetime(2026, 5, 15, 19, 30, 5, tzinfo=UTC)

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "id": returning_id,
        "ingested_at": returning_ingested_at,
    }
    mock_get_cursor_factory.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_get_cursor_factory.return_value.__exit__ = MagicMock(return_value=False)
    return mock_cursor


# =============================================================================
# _compute_payload_hash — determinism + key-order independence
# =============================================================================


@pytest.mark.unit
class TestComputePayloadHash:
    """SHA-256 of canonicalized JSON; key-order independent; distinct on diff."""

    def test_hash_is_bytes(self):
        """Returns bytes (not hex string, not int)."""
        result = _compute_payload_hash({"a": 1})
        assert isinstance(result, bytes), (
            f"_compute_payload_hash must return bytes, got {type(result).__name__}"
        )

    def test_hash_is_32_bytes_sha256(self):
        """SHA-256 digest is always 32 bytes."""
        result = _compute_payload_hash({"a": 1})
        assert len(result) == 32, f"SHA-256 digest must be 32 bytes, got {len(result)}"

    def test_hash_deterministic_same_payload(self):
        """Same payload hashes to same bytes (deterministic)."""
        payload = {"home_score": 14, "away_score": 7, "quarter": 2}
        hash1 = _compute_payload_hash(payload)
        hash2 = _compute_payload_hash(payload)
        assert hash1 == hash2, "_compute_payload_hash must be deterministic"

    def test_hash_key_order_independent(self):
        """Key-order independence (sort_keys=True canonicalization)."""
        payload_a = {"a": 1, "b": 2, "c": 3}
        payload_b = {"c": 3, "a": 1, "b": 2}
        payload_c = {"b": 2, "c": 3, "a": 1}
        hash_a = _compute_payload_hash(payload_a)
        hash_b = _compute_payload_hash(payload_b)
        hash_c = _compute_payload_hash(payload_c)
        assert hash_a == hash_b == hash_c, (
            "_compute_payload_hash must be key-order independent (sort_keys=True canonicalization)"
        )

    def test_hash_distinct_for_distinct_payloads(self):
        """Different payloads produce different hashes."""
        hash_a = _compute_payload_hash({"a": 1})
        hash_b = _compute_payload_hash({"a": 2})
        assert hash_a != hash_b, (
            "_compute_payload_hash must produce distinct outputs for distinct payloads"
        )

    def test_hash_distinct_for_nested_payload_change(self):
        """Nested-dict mutations produce distinct hashes."""
        hash_a = _compute_payload_hash({"team": {"home": 14, "away": 7}})
        hash_b = _compute_payload_hash({"team": {"home": 14, "away": 8}})
        assert hash_a != hash_b, (
            "Nested-dict mutation must produce distinct hash (canonicalization recurses)"
        )

    def test_hash_raises_on_non_serializable(self):
        """Non-JSON-serializable payload raises TypeError."""
        # datetime is not JSON-serializable by default
        unserializable = {"created": datetime(2026, 5, 15, tzinfo=UTC)}
        with pytest.raises(TypeError):
            _compute_payload_hash(unserializable)


# =============================================================================
# append_observation_row — happy path
# =============================================================================


@pytest.mark.unit
class TestAppendObservationRowHappyPath:
    """Happy path: valid inputs produce single INSERT with composite-PK return."""

    @patch("precog.database.crud_canonical_observations.get_cursor")
    def test_append_observation_row_returns_composite_pk_tuple(self, mock_get_cursor_factory):
        """Returns (id, ingested_at) tuple per V2.43 Item 3 composite-FK invariant."""
        ingested_at = datetime(2026, 5, 15, 19, 30, 5, tzinfo=UTC)
        _wire_observation_cursor_mock(
            mock_get_cursor_factory,
            returning_id=42,
            returning_ingested_at=ingested_at,
        )

        result = append_observation_row(
            observation_kind="game_state",
            source_id=1,
            canonical_primary_event_id=42,
            payload={"home_score": 14, "away_score": 7},
            event_occurred_at=datetime(2026, 5, 15, 19, 30, tzinfo=UTC),
            source_published_at=datetime(2026, 5, 15, 19, 30, 5, tzinfo=UTC),
        )

        assert isinstance(result, tuple), "Return must be a tuple (composite PK)"
        assert len(result) == 2, "Return tuple must have 2 elements (id, ingested_at)"
        obs_id, obs_ingested_at = result
        assert obs_id == 42, f"Expected id=42, got {obs_id!r}"
        assert obs_ingested_at == ingested_at, (
            f"Expected ingested_at={ingested_at!r}, got {obs_ingested_at!r}"
        )

    @patch("precog.database.crud_canonical_observations.get_cursor")
    def test_append_observation_row_executes_insert_with_returning(self, mock_get_cursor_factory):
        """SQL is INSERT INTO canonical_observations ... RETURNING id, ingested_at."""
        mock_cursor = _wire_observation_cursor_mock(mock_get_cursor_factory)

        append_observation_row(
            observation_kind="game_state",
            source_id=1,
            canonical_primary_event_id=42,
            payload={"x": 1},
            event_occurred_at=None,
            source_published_at=datetime(2026, 5, 15, tzinfo=UTC),
        )

        mock_get_cursor_factory.assert_called_once_with(commit=True)
        sql, _params = mock_cursor.execute.call_args[0]
        assert "INSERT INTO canonical_observations" in sql
        assert "RETURNING id, ingested_at" in sql

    @patch("precog.database.crud_canonical_observations.get_cursor")
    def test_append_observation_row_includes_all_columns_in_insert(self, mock_get_cursor_factory):
        """INSERT covers all 7 user-supplied columns (rest are DEFAULT).

        V2.45 (Migration 0084) update: payload column DROPPED;
        canonical_event_id RENAMED to canonical_primary_event_id.  The
        function still accepts ``payload`` as a parameter (consumed for
        SHA-256 hash derivation) but the value is NOT stored on the
        canonical_observations row.
        """
        mock_cursor = _wire_observation_cursor_mock(mock_get_cursor_factory)

        append_observation_row(
            observation_kind="game_state",
            source_id=1,
            canonical_primary_event_id=42,
            payload={"x": 1},
            event_occurred_at=None,
            source_published_at=datetime(2026, 5, 15, tzinfo=UTC),
        )

        sql, _ = mock_cursor.execute.call_args[0]
        for col in (
            "observation_kind",
            "source_id",
            "canonical_primary_event_id",
            "payload_hash",
            "event_occurred_at",
            "source_published_at",
            "valid_until",
        ):
            assert col in sql, f"INSERT must include column {col!r}"
        # V2.45: payload column DROPPED — not in INSERT.
        assert "payload," not in sql.replace("payload_hash", ""), (
            "V2.45 Migration 0084 dropped the payload column; INSERT must NOT include it"
        )
        # V2.45: no JSONB cast (no JSONB column in INSERT post-payload-drop).
        assert "::jsonb" not in sql, (
            "V2.45 Migration 0084 dropped the payload JSONB column; "
            "no ::jsonb cast should remain in the INSERT"
        )

    @patch("precog.database.crud_canonical_observations.get_cursor")
    def test_append_observation_row_consumes_payload_for_hash(self, mock_get_cursor_factory):
        """payload dict is consumed for SHA-256 hash derivation (not stored post-V2.45).

        V2.45 update: payload column dropped from canonical_observations.
        The function still accepts payload, hashes it for dedup, but
        does NOT pass payload itself to SQL.  Only payload_hash crosses
        the SQL boundary.
        """
        mock_cursor = _wire_observation_cursor_mock(mock_get_cursor_factory)

        payload = {"home_score": 14, "away_score": 7}
        append_observation_row(
            observation_kind="game_state",
            source_id=1,
            canonical_primary_event_id=42,
            payload=payload,
            event_occurred_at=None,
            source_published_at=datetime(2026, 5, 15, tzinfo=UTC),
        )

        params = mock_cursor.execute.call_args[0][1]
        # V2.45 SQL parameter order:
        #   0: observation_kind
        #   1: source_id
        #   2: canonical_primary_event_id
        #   3: payload_hash (BYTEA)
        #   4: event_occurred_at
        #   5: source_published_at
        #   6: valid_until
        # The payload dict itself MUST NOT appear in params; only its hash.
        for param in params:
            assert param != payload, (
                "V2.45: payload dict must NOT be passed to SQL (column dropped); "
                "only payload_hash should cross the SQL boundary"
            )

    @patch("precog.database.crud_canonical_observations.get_cursor")
    def test_append_observation_row_passes_payload_hash_as_bytes(self, mock_get_cursor_factory):
        """payload_hash param is BYTEA (Python bytes) per BYTEA column type."""
        mock_cursor = _wire_observation_cursor_mock(mock_get_cursor_factory)

        append_observation_row(
            observation_kind="game_state",
            source_id=1,
            canonical_primary_event_id=42,
            payload={"x": 1},
            event_occurred_at=None,
            source_published_at=datetime(2026, 5, 15, tzinfo=UTC),
        )

        params = mock_cursor.execute.call_args[0][1]
        # V2.45 param positions: payload_hash is at position 3 —
        # observation_kind, source_id, canonical_primary_event_id, payload_hash, ...
        payload_hash_param = params[3]
        assert isinstance(payload_hash_param, bytes), (
            f"payload_hash param must be bytes (BYTEA), got {type(payload_hash_param).__name__}"
        )
        assert len(payload_hash_param) == 32, (
            f"SHA-256 digest must be 32 bytes, got {len(payload_hash_param)}"
        )

    @patch("precog.database.crud_canonical_observations.get_cursor")
    def test_append_observation_row_canonical_primary_event_id_none_passes_through(
        self, mock_get_cursor_factory
    ):
        """canonical_primary_event_id=None is forwarded as SQL NULL (cross-domain default)."""
        mock_cursor = _wire_observation_cursor_mock(mock_get_cursor_factory)

        append_observation_row(
            observation_kind="weather",  # cross-domain — typically NULL canonical_event
            source_id=1,
            canonical_primary_event_id=None,
            payload={"temperature_c": 22.5},
            event_occurred_at=None,
            source_published_at=datetime(2026, 5, 15, tzinfo=UTC),
        )

        params = mock_cursor.execute.call_args[0][1]
        # V2.45 param positions: canonical_primary_event_id is at position 2.
        assert params[2] is None, "canonical_primary_event_id=None must pass as SQL NULL"

    @patch("precog.database.crud_canonical_observations.get_cursor")
    def test_append_observation_row_event_occurred_at_none_passes_through(
        self, mock_get_cursor_factory
    ):
        """event_occurred_at=None is forwarded as SQL NULL (econ/news default)."""
        mock_cursor = _wire_observation_cursor_mock(mock_get_cursor_factory)

        append_observation_row(
            observation_kind="econ",
            source_id=1,
            canonical_primary_event_id=None,
            payload={"cpi": 312.5},
            event_occurred_at=None,
            source_published_at=datetime(2026, 5, 15, tzinfo=UTC),
        )

        params = mock_cursor.execute.call_args[0][1]
        # V2.45 param positions: event_occurred_at is at position 4
        # (was 5 pre-V2.45; payload at position 4 was dropped).
        assert params[4] is None

    @patch("precog.database.crud_canonical_observations.get_cursor")
    def test_append_observation_row_valid_until_none_passes_through(self, mock_get_cursor_factory):
        """valid_until=None (default) is forwarded as SQL NULL (currently-valid)."""
        mock_cursor = _wire_observation_cursor_mock(mock_get_cursor_factory)

        append_observation_row(
            observation_kind="game_state",
            source_id=1,
            canonical_primary_event_id=42,
            payload={"x": 1},
            event_occurred_at=None,
            source_published_at=datetime(2026, 5, 15, tzinfo=UTC),
            # valid_until omitted; defaults to None
        )

        params = mock_cursor.execute.call_args[0][1]
        # V2.45 param positions: valid_until is at position 6 (last;
        # was 7 pre-V2.45 with payload at 4).
        assert params[6] is None


# =============================================================================
# append_observation_row — Pattern 73 SSOT real-guard validation
# =============================================================================


@pytest.mark.unit
class TestAppendObservationRowRejectsInvalidKind:
    """Pattern 73 SSOT real-guard validation on observation_kind.

    The slot-0073 strengthened convention applied to slot 0078: the
    constants.py tuple is imported and USED in real-guard validation,
    NOT side-effect-only.  This test asserts the validation fires.
    """

    @patch("precog.database.crud_canonical_observations.get_cursor")
    def test_rejects_invalid_observation_kind(self, mock_get_cursor_factory):
        """observation_kind not in OBSERVATION_KIND_VALUES raises ValueError before SQL."""
        for bad_kind in (
            "not_a_real_kind",
            "GAME_STATE",  # wrong case
            "game-state",  # wrong separator
            "",  # empty
            "sports_event",  # plausible but not canonical
        ):
            with pytest.raises(ValueError, match="OBSERVATION_KIND_VALUES"):
                append_observation_row(
                    observation_kind=bad_kind,
                    source_id=1,
                    canonical_primary_event_id=42,
                    payload={"x": 1},
                    event_occurred_at=None,
                    source_published_at=datetime(2026, 5, 15, tzinfo=UTC),
                )
        # No SQL was ever attempted (validation fires before get_cursor).
        mock_get_cursor_factory.assert_not_called()

    @patch("precog.database.crud_canonical_observations.get_cursor")
    def test_accepts_every_canonical_kind(self, mock_get_cursor_factory):
        """Every value in OBSERVATION_KIND_VALUES is accepted (Pattern 73 SSOT lockstep).

        If this fails, the constant and the real-guard validation drifted
        apart — exactly the failure mode Pattern 73 SSOT prevents.
        """
        mock_cursor = _wire_observation_cursor_mock(mock_get_cursor_factory)

        for canonical_kind in OBSERVATION_KIND_VALUES:
            # Should NOT raise.
            append_observation_row(
                observation_kind=canonical_kind,
                source_id=1,
                canonical_primary_event_id=None,
                payload={"x": 1},
                event_occurred_at=None,
                source_published_at=datetime(2026, 5, 15, tzinfo=UTC),
            )
        # Each call hits the cursor exactly once.
        assert mock_cursor.execute.call_count == len(OBSERVATION_KIND_VALUES), (
            f"Expected {len(OBSERVATION_KIND_VALUES)} INSERTs (one per kind), "
            f"got {mock_cursor.execute.call_count}"
        )


# =============================================================================
# append_observation_row — payload_hash determinism crosscheck
# =============================================================================


@pytest.mark.unit
class TestAppendObservationRowPayloadHashCrosscheck:
    """The payload_hash sent to SQL matches _compute_payload_hash() output.

    This is the integration point between the helper and the writer:
    if the writer ever derived the hash differently from the helper
    (e.g., by canonicalizing differently), the dedup UNIQUE would
    diverge from operator expectations.  This test pins the contract.
    """

    @patch("precog.database.crud_canonical_observations.get_cursor")
    def test_payload_hash_in_sql_params_matches_compute_helper(self, mock_get_cursor_factory):
        """The hash bytes passed to SQL == _compute_payload_hash(payload)."""
        mock_cursor = _wire_observation_cursor_mock(mock_get_cursor_factory)

        payload = {"home": 14, "away": 7, "quarter": 2}
        expected_hash = _compute_payload_hash(payload)

        append_observation_row(
            observation_kind="game_state",
            source_id=1,
            canonical_primary_event_id=42,
            payload=payload,
            event_occurred_at=None,
            source_published_at=datetime(2026, 5, 15, tzinfo=UTC),
        )

        params = mock_cursor.execute.call_args[0][1]
        # V2.45 param positions: payload_hash is at position 3.
        actual_hash = params[3]
        assert actual_hash == expected_hash, (
            "payload_hash sent to SQL must equal _compute_payload_hash(payload); "
            "drift here would corrupt dedup UNIQUE semantics"
        )
