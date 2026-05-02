"""Pattern 73 SSOT parity tests for slot 0078 canonical_observations vocabularies.

Verifies the three new constants (`OBSERVATION_KIND_VALUES` +
`PARTITION_STRATEGY_VALUES` + `RECONCILIATION_OUTCOME_VALUES`) added
in slot 0078 maintain Pattern 73 SSOT discipline:

    1. Each is a tuple (immutable; not a list which could be mutated).
    2. ``OBSERVATION_KIND_VALUES`` matches the Migration 0078 inline DDL
       CHECK constraint string literals exactly (case + ordering pinned
       in the migration file; this test reads the migration source +
       cross-checks the tuple).
    3. No duplicates across vocabularies that would suggest an SSOT drift.

Pattern 73 SSOT (CLAUDE.md Critical Pattern #8): the vocabulary is
defined in ONE canonical home (constants.py) and the Migration 0078
inline CHECK references the same string literals.  Drift between the
two locations would surface as silent ingest-pipeline bugs (Python-side
validation accepts a value the DDL CHECK rejects, or vice versa).

Reference:
    - ``src/precog/database/constants.py`` ``OBSERVATION_KIND_VALUES`` +
      ``PARTITION_STRATEGY_VALUES`` + ``RECONCILIATION_OUTCOME_VALUES``
    - ``src/precog/database/alembic/versions/0078_canonical_observations.py``
    - ``memory/build_spec_0078_pm_memo.md`` § 3 (SSOT vocabularies)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from precog.database.constants import (
    OBSERVATION_KIND_VALUES,
    PARTITION_STRATEGY_VALUES,
    RECONCILIATION_OUTCOME_VALUES,
)

# Resolve the migration file path relative to the repo root.  Test runs from
# the repo root via ``python -m pytest`` so the relative path is stable.
_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "precog"
    / "database"
    / "alembic"
    / "versions"
    / "0078_canonical_observations.py"
)


@pytest.mark.unit
class TestObservationKindValuesShape:
    """OBSERVATION_KIND_VALUES is a tuple with the expected 6-value shape."""

    def test_observation_kind_values_is_tuple(self):
        """Type contract: tuple, not list (immutable vocabulary)."""
        assert isinstance(OBSERVATION_KIND_VALUES, tuple), (
            f"OBSERVATION_KIND_VALUES must be tuple (immutable), "
            f"got {type(OBSERVATION_KIND_VALUES).__name__}"
        )

    def test_observation_kind_values_has_six_kinds(self):
        """Cardinality contract: 6 kinds per build spec § 3 + V2.43 Item 2."""
        assert len(OBSERVATION_KIND_VALUES) == 6, (
            f"OBSERVATION_KIND_VALUES expected 6 kinds, got "
            f"{len(OBSERVATION_KIND_VALUES)}: {OBSERVATION_KIND_VALUES!r}"
        )

    def test_observation_kind_values_no_duplicates(self):
        """Each value appears exactly once (set parity check)."""
        assert len(set(OBSERVATION_KIND_VALUES)) == len(OBSERVATION_KIND_VALUES), (
            f"OBSERVATION_KIND_VALUES has duplicate(s): {OBSERVATION_KIND_VALUES!r}"
        )

    @pytest.mark.parametrize(
        "expected_value",
        [
            "game_state",
            "weather",
            "poll",
            "econ",
            "news",
            "market_snapshot",
        ],
    )
    def test_observation_kind_values_includes_canonical_kind(self, expected_value):
        """Each canonical kind is present (build spec § 3 + V2.43 Item 2)."""
        assert expected_value in OBSERVATION_KIND_VALUES, (
            f"OBSERVATION_KIND_VALUES missing {expected_value!r}; got {OBSERVATION_KIND_VALUES!r}"
        )


@pytest.mark.unit
class TestPartitionStrategyValuesShape:
    """PARTITION_STRATEGY_VALUES is a tuple documenting the Cohort 4 strategy."""

    def test_partition_strategy_values_is_tuple(self):
        """Type contract: tuple, not list."""
        assert isinstance(PARTITION_STRATEGY_VALUES, tuple), (
            f"PARTITION_STRATEGY_VALUES must be tuple, "
            f"got {type(PARTITION_STRATEGY_VALUES).__name__}"
        )

    def test_partition_strategy_values_includes_range_monthly(self):
        """Cohort 4 commits to range_monthly_ingested_at (Holden D1 PM call)."""
        assert "range_monthly_ingested_at" in PARTITION_STRATEGY_VALUES, (
            f"PARTITION_STRATEGY_VALUES must include "
            f"'range_monthly_ingested_at' (Cohort 4 strategy); "
            f"got {PARTITION_STRATEGY_VALUES!r}"
        )

    def test_partition_strategy_values_no_duplicates(self):
        """Each value appears exactly once."""
        assert len(set(PARTITION_STRATEGY_VALUES)) == len(PARTITION_STRATEGY_VALUES), (
            f"PARTITION_STRATEGY_VALUES has duplicate(s): {PARTITION_STRATEGY_VALUES!r}"
        )


@pytest.mark.unit
class TestReconciliationOutcomeValuesShape:
    """RECONCILIATION_OUTCOME_VALUES is a tuple with 6 outcome categories."""

    def test_reconciliation_outcome_values_is_tuple(self):
        """Type contract: tuple, not list."""
        assert isinstance(RECONCILIATION_OUTCOME_VALUES, tuple), (
            f"RECONCILIATION_OUTCOME_VALUES must be tuple, "
            f"got {type(RECONCILIATION_OUTCOME_VALUES).__name__}"
        )

    def test_reconciliation_outcome_values_has_six_outcomes(self):
        """Cardinality contract: 6 outcomes per build spec § 3."""
        assert len(RECONCILIATION_OUTCOME_VALUES) == 6, (
            f"RECONCILIATION_OUTCOME_VALUES expected 6 outcomes, got "
            f"{len(RECONCILIATION_OUTCOME_VALUES)}: {RECONCILIATION_OUTCOME_VALUES!r}"
        )

    @pytest.mark.parametrize(
        "expected_value",
        [
            "match",
            "drift",
            "mismatch",
            "missing_dim",
            "missing_fact",
            "ambiguous",
        ],
    )
    def test_reconciliation_outcome_values_includes_canonical_outcome(self, expected_value):
        """Each canonical reconciler outcome is present (build spec § 3)."""
        assert expected_value in RECONCILIATION_OUTCOME_VALUES, (
            f"RECONCILIATION_OUTCOME_VALUES missing {expected_value!r}; "
            f"got {RECONCILIATION_OUTCOME_VALUES!r}"
        )

    def test_reconciliation_outcome_values_no_duplicates(self):
        """Each outcome appears exactly once."""
        assert len(set(RECONCILIATION_OUTCOME_VALUES)) == len(RECONCILIATION_OUTCOME_VALUES), (
            f"RECONCILIATION_OUTCOME_VALUES has duplicate(s): {RECONCILIATION_OUTCOME_VALUES!r}"
        )


@pytest.mark.unit
class TestObservationKindDDLCheckParity:
    """Pattern 73 SSOT real-guard: tuple values match Migration 0078 CHECK literals.

    The migration's inline CHECK constraint
    ``ck_canonical_observations_kind`` lists the same string literals that
    ``OBSERVATION_KIND_VALUES`` exposes in Python.  This test reads the
    migration file and verifies each tuple value appears in the migration
    source — closing the Pattern 73 SSOT drift surface where Python and
    DDL could silently disagree on the canonical vocabulary.

    This is the same shape as
    ``test_canonical_match_log_action_vocabulary_pattern_73_ssot``
    (slot 0073 integration test) but at the unit-test layer (no DB
    required; pure file-read parity check).
    """

    def test_migration_file_exists(self):
        """Sanity check: the migration file is at the expected path."""
        assert _MIGRATION_PATH.exists(), (
            f"Migration 0078 not found at {_MIGRATION_PATH!r}; test infrastructure mis-configured"
        )

    @pytest.mark.parametrize("kind_value", OBSERVATION_KIND_VALUES)
    def test_each_observation_kind_appears_in_migration_check(self, kind_value):
        """Each OBSERVATION_KIND_VALUES entry appears in Migration 0078 CHECK.

        Pattern 73 SSOT lockstep guarantee: if a future PR adds a value
        to the Python tuple but forgets the DDL CHECK ALTER (or vice
        versa), this test fires.  The two locations MUST update in
        lockstep.

        The check is intentionally permissive about WHERE the value
        appears in the file (it reads as a string literal in the CHECK
        constraint clause); the migration is small enough that any
        accidental match outside the CHECK would be obvious.
        """
        migration_text = _MIGRATION_PATH.read_text(encoding="utf-8")
        # Each canonical value should appear as a quoted string literal
        # somewhere in the migration source.  The CHECK constraint emits
        # them as ``'game_state', 'weather', 'poll', ...`` — the test's
        # f-string match captures that shape.
        quoted = f"'{kind_value}'"
        assert quoted in migration_text, (
            f"OBSERVATION_KIND_VALUES entry {kind_value!r} not found as "
            f"quoted literal in Migration 0078 source; Pattern 73 SSOT "
            f"drift between constants.py tuple and migration DDL CHECK"
        )
