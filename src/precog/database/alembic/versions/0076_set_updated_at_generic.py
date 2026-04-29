"""Cohort 3 close-out post-retrofit -- generic ``set_updated_at()`` trigger
function + 4-table retrofit (#1074, ADR-118 V2.42 sub-amendment A).

Slot 0076 is the FIRST of two close-out post-retrofit migrations following
Cohort 3's main 5-slot arc (slots 0071-0075).  V2.42 sub-amendment A is ratified
here; sub-amendment B (canonical_events FK polarity flip to ON DELETE SET NULL)
ships in slot 0077 -- intentionally split per session 83 design council
adjudication (Holden silent-fail vs loud-fail asymmetry + Miles failure-mode
independence + rollback granularity).  Council synthesis at
``memory/design_review_0076_synthesis.md``.

Scope (one generic function + 4 trigger instances + 3 per-table function drops):

    1. ``CREATE OR REPLACE FUNCTION set_updated_at()`` -- the generic
       PL/pgSQL function whose body is verbatim the per-table bodies that
       Migrations 0069 + 0072 shipped (``BEGIN NEW.updated_at = now();
       RETURN NEW; END;``).  Pattern 73 SSOT: ONE chokepoint for the
       ``updated_at`` maintenance contract; future cohorts adding canonical-
       tier tables with ``updated_at`` columns just ``CREATE TRIGGER ...
       EXECUTE FUNCTION set_updated_at()`` -- zero new function DDL.

    2. For ``canonical_markets`` / ``canonical_market_links`` /
       ``canonical_event_links``:  DROP TRIGGER (existing per-table
       trigger) then CREATE TRIGGER (re-pointing to the generic
       function).  Trigger names PRESERVED as ``trg_<table>_updated_at``
       (Migration 0072 carry-forward; Holden + Galadriel both signed off
       on no rename -- the function-name change is enough rename signal).

    3. For ``canonical_events``: CREATE TRIGGER (net-new install -- closes
       the orphan-trigger gap that has existed since Migration 0067 lines
       249-251 declared ``updated_at TIMESTAMPTZ NOT NULL DEFAULT now()``
       without ever installing a BEFORE UPDATE trigger to maintain it).
       Per Miles M-8: this single-table closure is operationally the
       most-valuable line in the bundle -- pre-retrofit, every UPDATE on
       canonical_events that did not explicitly set ``updated_at`` left a
       silently-stale value (alerts that key off ``updated_at`` recency
       silently lied).  Post-retrofit, the trigger enforces freshness
       reliably.  Data-correctness risk at the gap-closure boundary is
       ZERO (canonical_events has 0 rows at deploy time -- Cohort 1
       shipped the table empty, no production deploy has populated it yet,
       and slot 0076 lands before Cohort 5+ matcher pipeline begins
       writing).

    4. ``DROP FUNCTION update_canonical_markets_updated_at()`` +
       ``DROP FUNCTION update_canonical_market_links_updated_at()`` +
       ``DROP FUNCTION update_canonical_event_links_updated_at()`` --
       ALTER-then-DROP order (the trigger DROP/CREATE in step 2 MUST
       precede these DROPs; NOT CASCADE per Holden -- CASCADE would be
       dangerous if anything else has come to depend on the per-table
       function in the meantime).  Orphaning the per-table functions was
       rejected per Pattern 87 lens: shipped migrations are append-only,
       so the per-table functions would become permanent docstring debt.
       Explicit DROP keeps the schema state minimal.

Pattern 73 SSOT (rule + pointers, never duplicated bodies):

    The function body is now the single canonical home for the ``updated_at``
    maintenance contract.  Future tweaks (e.g., ``IF NEW IS DISTINCT FROM
    OLD`` no-op suppression; clock-source guarantees) edit ONE function, not
    four.  Pre-retrofit, the four per-table function bodies were byte-
    identical and would silently drift the moment any one table needed a
    tweak (the same Pattern 73 violation shape Uhura caught on slot 0072
    LINK_STATE_VALUES vocabulary -- "rule duplicated, not pointed-to").
    Zero new Python constants required this slot per Uhura's vocabulary
    audit.

Pattern 81 (lookup convention) -- N/A this slot.  No lookup tables introduced.

Pattern 84 (two-phase NOT VALID + VALIDATE for CHECK on populated tables) --
N/A this slot.  No CHECK constraints touched; functions and triggers don't
engage Pattern 84.

Pattern 87 (append-only migrations) -- REAFFIRMED CLEAN.  Migrations 0001-
0075 are NOT edited by this PR.  This PR's CRUD docstring sweeps in
``crud_canonical_events.py`` + integration-test edits in
``test_migration_0069_*.py`` + ``test_migration_0072_*.py`` are NOT
migration files; they are application code + test code, both editable
freely.  The forward-pointer Galadriel-7 noted (slot 0072 docstring
forward-pointer to ``set_updated_at()`` retrofit) is acknowledged HERE in
this docstring per the Pattern 87 carve-out -- corrections to shipped
migration docstrings live in the next migration's docstring, not in the
shipped one.

Migration 0056 RAISE EXCEPTION carve-out (CRITICAL out-of-scope fence):

    Migration 0056 installed BEFORE UPDATE triggers on these 7 IMMUTABLE
    tables, fired by ``RAISE EXCEPTION`` to enforce write-protection:

        - ``strategies``
        - ``probability_models``
        - ``trades``
        - ``settlements``
        - ``account_ledger``
        - ``position_exits``
        - ``exit_attempts``

    These triggers are NOT ``updated_at``-maintenance triggers; they are
    write-protection enforcement.  ``set_updated_at()`` MUST NOT be
    attached to any of these 7 tables.  A future "consistency cleanup" PR
    proposing to retrofit them under the generic function should fail
    design review at this docstring level.  Visual confusion alone (two
    BEFORE UPDATE triggers on the same table) is a maintenance hazard
    even before considering that the RAISE EXCEPTION fires first and the
    set_updated_at trigger would never execute.

Out-of-scope ``updated_at``-bearing tables (NOT canonical-tier):

    These tables carry ``updated_at`` columns but are intentionally NOT
    retrofitted by slot 0076 because they are non-canonical-tier:

        - ``strategy_types`` / ``model_classes`` (Migration 0002 lookup
          tables) -- per-table BEFORE UPDATE triggers already exist
          (``update_updated_at_column()``); not canonical-tier.
        - ``game_odds`` (Migration 0048; renamed from ``historical_odds``)
          -- fact table, not canonical-tier.

    If a future cohort decides to standardize the canonical-tier and the
    non-canonical-tier ``updated_at`` triggers under ONE generic function,
    that work is a separate scope decision and a separate migration.

canonical_events orphan-trigger gap closure (M-8):

    Migration 0067 lines 249-251 declared
    ``updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`` on
    ``canonical_events``.  The Cohort 2 amendment decision #4 (Migration
    0069) established the BEFORE UPDATE trigger pattern as the canonical
    template for ``updated_at`` maintenance.  The carry-forward retrofit
    of that pattern onto canonical_events never shipped -- the canonical-
    tier surface has been silently inconsistent for ~10 migrations
    (0067 -> 0075, all canonical-tier slots).  Slot 0076 closes the gap
    as the operationally most-valuable line in the bundle.  Holden's
    framing: this is a regression of the V2.39 template, not an
    oversight or an architectural choice.  Data-correctness risk: ZERO
    (canonical_events has 0 rows in dev/staging/prod at slot-0076 deploy
    time; the historical "gap period" is empty).

Naming convention pointer (M-9):

    ``set_updated_at()`` SUPERSEDES the per-table
    ``update_<table>_updated_at()`` naming convention.  Cohort 2 amendment
    decision #4 (Migration 0069 docstring lines 56-67) intentionally chose
    the per-table convention to maximize grep-ability and avoid OR-REPLACE
    aliasing risk.  ADR-118 V2.42 sub-amendment A revises this decision:
    the canonical-tier surface is small enough (~4 tables) that one generic
    chokepoint is the better long-term design.  The V2.39 template
    described the per-table function name; V2.42 sub-amendment A renames
    the template to the generic form.  Future canonical-tier tables
    adding ``updated_at`` should use ``EXECUTE FUNCTION set_updated_at()``;
    the per-table form is no longer canonical.  Closes the V2.39 vs V2.42
    naming-convention drift documented in Migration 0069 docstring lines
    56-67.

Operator runbook (M-6) -- "show me the trigger state":

    ``\\df set_updated_at`` -- display the canonical maintenance function.
    Should return EXACTLY ONE row (function name + signature + return type).

    ``SELECT trigger_name, event_object_table FROM
    information_schema.triggers WHERE action_statement LIKE '%set_updated_at%'``
    -- enumerate the trigger instances.  Should return EXACTLY FOUR rows
    post-slot-0076 (canonical_events, canonical_markets,
    canonical_market_links, canonical_event_links) -- not 3, not 5.

updated_at semantics post-retrofit (Uhura-1):

    Pre-retrofit on canonical_markets / canonical_market_links /
    canonical_event_links: ``updated_at`` advanced on every UPDATE via
    the per-table trigger.  Pre-retrofit on canonical_events:
    ``updated_at`` only advanced when application code explicitly set it
    (silent staleness if any UPDATE path forgot).

    Post-retrofit on all 4 tables: ``updated_at`` advances on every
    UPDATE via the generic ``set_updated_at()`` trigger -- including
    UPDATE statements that target columns OTHER than ``updated_at``,
    AND including FK-NULL cascades from upstream DELETEs (the SET NULL
    polarity arrives in slot 0077, but the semantic shift is named here
    so a future reader of canonical_events.updated_at can understand
    its post-slot-0077 meaning by reading ONLY this migration's
    docstring).

    The semantic shifts from "approximate last canonical-content change
    as the application chose to record" to "any DB-side UPDATE,
    including FK-NULL cascades."  Operationally cleaner -- no more
    silent staleness -- but reporting-wise, an ``updated_at`` bump now
    answers a strictly weaker question.  Operators reading
    ``updated_at`` post-retrofit need the canonical caveat: it is NOT
    a "last canonical content change" timestamp.

Round-trip CI gate compatibility (PR #1081):

    The ``downgrade()`` function reverses cleanly:

        1. Re-CREATE each of the 3 per-table functions
           (``update_canonical_markets_updated_at()``,
           ``update_canonical_market_links_updated_at()``,
           ``update_canonical_event_links_updated_at()``) with their
           ORIGINAL bodies (verbatim from Migrations 0069 + 0072).
        2. DROP TRIGGER + re-CREATE TRIGGER on each of the 3 retrofitted
           tables to point back at the per-table function.
        3. DROP TRIGGER ``trg_canonical_events_updated_at`` -- the gap-
           closer doesn't exist pre-retrofit, so rollback restores the
           historical inconsistency.  This lossiness IS INTENTIONAL per
           Holden's framing (rollback restores prior schema state
           including known imperfections).  Builder MUST NOT "fix" the
           gap in downgrade.
        4. DROP FUNCTION ``set_updated_at()`` -- after all triggers
           pointing at it have been redirected, the generic function is
           safe to drop; NOT CASCADE.

    The lossiness in step 3 is the only deliberate-imperfection point in
    the round-trip; everything else round-trips byte-for-byte against
    the round-trip oracle's ``pg_get_functiondef`` slice.

Revision ID: 0076
Revises: 0074
Create Date: 2026-04-29

Issue: #1074 (ADR-118 V2.42 sub-amendment A retrofit)
Epic: #972 (Canonical Layer Foundation -- Phase B.5)
ADR: ADR-118 V2.42 sub-amendment A (generic set_updated_at function +
    4-table retrofit; canonical_events orphan-trigger gap closure)
Council: ``memory/design_review_0076_synthesis.md`` (Holden + Galadriel +
    Miles + Uhura, session 83)
Companion: slot 0077 (#1075 canonical_events FK ON DELETE SET NULL,
    V2.42 sub-amendment B) -- separate migration, sequenced same-arc
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0076"
down_revision: str = "0074"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Tables receiving the retrofit (Pattern 73 SSOT canonical home for
# this list -- the same 4-table set is enumerated in the migration
# docstring above and in the integration tests; future readers verifying
# scope should consult this constant + the docstring).
_RETROFIT_TABLES_WITH_PRIOR_TRIGGER: tuple[str, ...] = (
    "canonical_markets",
    "canonical_market_links",
    "canonical_event_links",
)
"""Tables whose existing per-table BEFORE UPDATE trigger is rewired to the
generic ``set_updated_at()`` function in slot 0076."""

_RETROFIT_TABLE_NEW_TRIGGER: str = "canonical_events"
"""Table whose BEFORE UPDATE trigger is INSTALLED for the first time in slot
0076 (orphan-trigger gap closure -- column declared in Migration 0067, no
trigger ever shipped)."""


def upgrade() -> None:
    """Install ``set_updated_at()`` + retrofit 4 tables + drop 3 per-table fns.

    Sequence (Holden ALTER-then-DROP discipline):
        1. CREATE OR REPLACE the generic function (idempotent under re-run).
        2. Attach COMMENT ON FUNCTION (Uhura-1 semantic shift documentation).
        3. For each of the 3 retrofitted tables: DROP existing trigger,
           CREATE new trigger pointing at the generic function.
        4. CREATE the canonical_events trigger (net-new; no prior to drop).
        5. DROP the 3 per-table functions (NOT CASCADE).
    """
    # ------------------------------------------------------------------
    # Step 1: Install the generic function.
    #
    # Body verbatim from Migrations 0069 + 0072 per-table bodies.  Three
    # lines of PL/pgSQL; Pattern 73 SSOT canonical home for the
    # ``updated_at`` maintenance contract.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    # ------------------------------------------------------------------
    # Step 2: Attach COMMENT ON FUNCTION (Uhura-1).
    #
    # Documents the semantic shift to operators inspecting via
    # ``\df+ set_updated_at`` or ``\\dffunctions``.  Pattern 73 SSOT pointer:
    # the canonical home for the ``updated_at`` semantic contract is here +
    # the schema doc V2.3 § canonical_events column-level table.
    # ------------------------------------------------------------------
    op.execute(
        """
        COMMENT ON FUNCTION set_updated_at() IS
        'Updates updated_at to now() on every BEFORE UPDATE; reflects any '
        'DB-side modification including FK-NULL cascades from upstream '
        'DELETEs (per ADR-118 V2.42 sub-amendment B). NOT a "last canonical '
        'content change" timestamp post-retrofit.'
        """
    )

    # ------------------------------------------------------------------
    # Step 3: Rewire the 3 existing per-table triggers to the generic
    # function.  Trigger names PRESERVED -- Migration 0072 carry-forward
    # convention.  Per Holden + Galadriel: function-name change is enough
    # rename signal; trigger-name churn would be unnecessary cost with
    # the canonical-tier CRUD modules' docstring inventory referencing
    # the existing trigger names.
    #
    # ``DROP TRIGGER`` (no IF EXISTS) is intentional in upgrade: if any
    # of these 3 triggers is missing pre-upgrade, that is itself a
    # schema-state divergence and the upgrade should fail loud -- exactly
    # the loud-failure semantic Holden wants for trigger-DDL retrofits.
    # ------------------------------------------------------------------
    for table_name in _RETROFIT_TABLES_WITH_PRIOR_TRIGGER:
        trigger_name = f"trg_{table_name}_updated_at"
        op.execute(f"DROP TRIGGER {trigger_name} ON {table_name}")
        op.execute(
            f"""
            CREATE TRIGGER {trigger_name}
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW
                EXECUTE FUNCTION set_updated_at()
            """
        )

    # ------------------------------------------------------------------
    # Step 4: Install the canonical_events trigger (net-new -- closes
    # the orphan-trigger gap from Migration 0067).  No prior trigger to
    # drop; we go straight to CREATE TRIGGER.
    #
    # Trigger naming follows the convention preserved above:
    # ``trg_<table>_updated_at`` regardless of generic-vs-per-table
    # function dispatch.
    # ------------------------------------------------------------------
    op.execute(
        f"""
        CREATE TRIGGER trg_{_RETROFIT_TABLE_NEW_TRIGGER}_updated_at
            BEFORE UPDATE ON {_RETROFIT_TABLE_NEW_TRIGGER}
            FOR EACH ROW
            EXECUTE FUNCTION set_updated_at()
        """
    )

    # ------------------------------------------------------------------
    # Step 5: DROP the 3 per-table functions.  NOT CASCADE per Holden --
    # CASCADE would silently remove any dependent objects (including
    # surprise dependencies that have accumulated since 0069/0072
    # shipped).  All 3 triggers that USE these functions were rewired
    # in step 3 above, so the unqualified DROP succeeds cleanly.
    #
    # No IF EXISTS: same loud-failure logic as the trigger DROP in step 3.
    # If a per-table function is already missing, schema state has
    # diverged and upgrade should fail with a diagnostic error.
    # ------------------------------------------------------------------
    op.execute("DROP FUNCTION update_canonical_markets_updated_at()")
    op.execute("DROP FUNCTION update_canonical_market_links_updated_at()")
    op.execute("DROP FUNCTION update_canonical_event_links_updated_at()")


def downgrade() -> None:
    """Reverse 0076: restore per-table functions, redirect triggers, drop generic.

    Sequence (mirrors ``upgrade()`` in reverse for object-dependency safety):
        1. Re-CREATE the 3 per-table functions with VERBATIM original bodies
           from Migrations 0069 + 0072.
        2. For each of the 3 retrofitted tables: DROP trigger pointing at
           the generic function, CREATE trigger pointing back at the per-
           table function.
        3. DROP the canonical_events trigger (net-new in upgrade; restoring
           the historical orphan-trigger gap is INTENTIONAL per Holden --
           rollback restores prior schema state including known
           imperfections).
        4. DROP the generic ``set_updated_at()`` function.

    ``IF EXISTS`` is used throughout for idempotent rollback per session 59
    ``feedback_idempotent_migration_drops.md``.  Re-running the downgrade on
    a partially-rolled-back DB is a no-op rather than a crash.
    """
    # ------------------------------------------------------------------
    # Step 1: Re-CREATE per-table functions with verbatim original bodies.
    # Bodies copied verbatim from:
    #   - Migration 0069 lines 226-236 (canonical_markets)
    #   - Migration 0072 lines 401-411 (canonical_market_links)
    #   - Migration 0072 lines 469-479 (canonical_event_links)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_canonical_markets_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_canonical_market_links_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_canonical_event_links_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    # ------------------------------------------------------------------
    # Step 2: For the 3 retrofitted tables, redirect triggers back to
    # per-table functions.  The trigger NAMES are unchanged across the
    # rewire (preserved in upgrade as well); only the function reference
    # in the CREATE TRIGGER statement differs.
    # ------------------------------------------------------------------
    op.execute("DROP TRIGGER IF EXISTS trg_canonical_markets_updated_at ON canonical_markets")
    op.execute(
        """
        CREATE TRIGGER trg_canonical_markets_updated_at
            BEFORE UPDATE ON canonical_markets
            FOR EACH ROW
            EXECUTE FUNCTION update_canonical_markets_updated_at()
        """
    )

    op.execute(
        "DROP TRIGGER IF EXISTS trg_canonical_market_links_updated_at ON canonical_market_links"
    )
    op.execute(
        """
        CREATE TRIGGER trg_canonical_market_links_updated_at
            BEFORE UPDATE ON canonical_market_links
            FOR EACH ROW
            EXECUTE FUNCTION update_canonical_market_links_updated_at()
        """
    )

    op.execute(
        "DROP TRIGGER IF EXISTS trg_canonical_event_links_updated_at ON canonical_event_links"
    )
    op.execute(
        """
        CREATE TRIGGER trg_canonical_event_links_updated_at
            BEFORE UPDATE ON canonical_event_links
            FOR EACH ROW
            EXECUTE FUNCTION update_canonical_event_links_updated_at()
        """
    )

    # ------------------------------------------------------------------
    # Step 3: DROP the canonical_events trigger.
    #
    # The gap-closer trigger doesn't exist pre-slot-0076; rollback
    # restores the historical orphan-trigger inconsistency (deliberate
    # lossiness per Holden's downgrade discipline).  Future reader
    # surprised by this should re-read the migration docstring's
    # "canonical_events orphan-trigger gap closure (M-8)" section.
    # ------------------------------------------------------------------
    op.execute("DROP TRIGGER IF EXISTS trg_canonical_events_updated_at ON canonical_events")

    # ------------------------------------------------------------------
    # Step 4: DROP the generic function.  Safe at this point -- all
    # triggers that were pointing at it have been redirected in step 2
    # and the canonical_events trigger using it is dropped in step 3.
    # NOT CASCADE.
    # ------------------------------------------------------------------
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
