"""Create external_team_codes table for persistent cross-platform team mapping.

Replaces the fragile in-memory collision resolution with a persistent,
auditable, multi-source team code mapping table. Each row maps a source
platform's team code to the canonical team_id in our teams table.

Table Design:
    - (source, source_team_code, league) is UNIQUE — each platform can only
      map a given code+league to one team
    - team_id FK to teams(team_id) — every external code must resolve to
      a known team
    - confidence tracks how the mapping was established:
      'exact'     = verified by API or manual human check
      'manual'    = set by a human but not independently verified
      'heuristic' = inferred (e.g., Kalshi code assumed to match ESPN code)

Indexes:
    - idx_external_team_codes_team   — fast lookup by team_id
    - idx_external_team_codes_source — fast lookup by (source, league)

Revision ID: 0045
Revises: 0044
Create Date: 2026-03-29

Related:
    - Issue #516: External team codes table
    - Issue #495: Polymarket integration (needs this table)
    - Issue #496: Cross-platform event matching (needs this table)
    - Issue #502: MLB enablement (needs this table)
    - Migration 0041: teams.kalshi_team_code column (predecessor approach)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0045"
down_revision: str = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create external_team_codes table with indexes.

    Educational Note:
        The UNIQUE constraint on (source, source_team_code, league) ensures
        that a given platform can only map a code+league combination to one
        team. For example, Kalshi's "JAC" in "nfl" can only point to one
        team_id. If Kalshi starts using "JAC" for a different sport, that's
        a separate row because the league differs.

        The ON DELETE CASCADE is intentionally NOT used — if a team is
        deleted, we want the FK violation to alert us rather than silently
        cascading. Team deletions are rare and should be handled manually.
    """
    op.execute(
        """
        CREATE TABLE external_team_codes (
            id SERIAL PRIMARY KEY,
            team_id INTEGER NOT NULL REFERENCES teams(team_id),
            source VARCHAR(30) NOT NULL,
            source_team_code VARCHAR(30) NOT NULL,
            league VARCHAR(20) NOT NULL,
            confidence VARCHAR(20) NOT NULL DEFAULT 'heuristic',
            verified_at TIMESTAMP WITH TIME ZONE,
            notes TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE (source, source_team_code, league)
        )
        """
    )

    # Index for lookups by team_id (e.g., "what codes does team X have?")
    op.execute("CREATE INDEX idx_external_team_codes_team ON external_team_codes(team_id)")

    # Index for lookups by source + league (e.g., "all Kalshi NFL codes")
    op.execute("CREATE INDEX idx_external_team_codes_source ON external_team_codes(source, league)")


def downgrade() -> None:
    """Drop external_team_codes table and its indexes.

    Indexes are dropped automatically when the table is dropped.
    """
    op.execute("DROP TABLE IF EXISTS external_team_codes")
