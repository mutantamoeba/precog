"""Temporal alignment writer service.

Background service that links market_snapshots to game_states by timestamp
proximity, populating the temporal_alignment table. Runs alongside the
ESPN and Kalshi pollers in the ServiceSupervisor.

Issue: #722 (URGENT — irreversible data loss per unplayed game)
Epic: #745 (Schema Hardening Arc, Cohort C0)

Architecture:
    ESPN Poller (30s) --> game_states (SCD Type 2)
                                                    |
                                            Temporal Alignment Writer (30s)
                                                    |
    Kalshi Poller (15s) --> market_snapshots (SCD Type 2)
                                                    |
                                              temporal_alignment table

FK chain: market_snapshots -> markets -> events -> games <- game_states

Quality thresholds (time_delta_seconds):
    exact:  <= 1s   (both polled within the same second)
    good:   <= 15s  (within Kalshi poll interval)
    fair:   <= 60s  (within a minute)
    poor:   <= 120s (noticeable lag)
    stale:  > 120s  (too old for reliable correlation)
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, ClassVar

from precog.database.connection import get_cursor
from precog.database.crud_ledger import insert_temporal_alignment_batch
from precog.schedulers.base_poller import BasePoller

logger = logging.getLogger(__name__)

# Quality thresholds in seconds.
_QUALITY_EXACT = Decimal("1")
_QUALITY_GOOD = Decimal("15")
_QUALITY_FAIR = Decimal("60")
_QUALITY_POOR = Decimal("120")

# Maximum age (seconds) of snapshots to consider. Prevents full-table scans
# when the writer has been down for a long time. For historical reconstruction,
# use a separate batch job instead.
_LOOKBACK_SECONDS = 600  # 10 minutes

# Maximum alignments per poll cycle.
_BATCH_LIMIT = 1000

# Query to find unaligned market_snapshot + game_state pairs.
# Follows the FK chain: market_snapshots -> markets -> events -> games <- game_states.
# Only processes snapshots created within the lookback window.
#
# IMPORTANT (Glokta review B1): We do NOT filter ms.row_current_ind = TRUE.
# In SCD Type 2, a snapshot becomes non-current when the next snapshot arrives
# (every ~15s). If the writer falls behind by even one cycle, non-current
# snapshots would be permanently unaligned. The lookback window + NOT EXISTS
# are sufficient to prevent reprocessing.
#
# For game_states, we use a LATERAL subquery to find the closest game_state
# by timestamp for each snapshot, rather than just the current one. This
# produces accurate alignments even when the writer runs slightly behind
# the pollers.
_UNALIGNED_QUERY = """
    SELECT
        ms.id AS market_snapshot_id,
        ms.market_id,
        ms.row_start_ts AS snapshot_time,
        ms.yes_ask_price,
        ms.no_ask_price,
        ms.spread,
        ms.volume,
        gs.id AS game_state_id,
        gs.row_start_ts AS game_state_time,
        gs.game_status,
        gs.home_score,
        gs.away_score,
        gs.period::VARCHAR AS period,
        gs.clock_display AS clock,
        g.id AS game_id,
        ABS(EXTRACT(EPOCH FROM (ms.row_start_ts - gs.row_start_ts)))::DECIMAL(10,2)
            AS time_delta_raw
    FROM market_snapshots ms
    JOIN markets m ON ms.market_id = m.id
    JOIN events e ON m.event_internal_id = e.id
    JOIN games g ON e.game_id = g.id
    CROSS JOIN LATERAL (
        SELECT gs_inner.id, gs_inner.row_start_ts, gs_inner.game_status,
               gs_inner.home_score, gs_inner.away_score,
               gs_inner.period, gs_inner.clock_display
        FROM game_states gs_inner
        WHERE gs_inner.game_id = g.id
        ORDER BY ABS(EXTRACT(EPOCH FROM (ms.row_start_ts - gs_inner.row_start_ts)))
        LIMIT 1
    ) gs
    WHERE e.game_id IS NOT NULL
      -- Idiomatic parameterized interval: pass the seconds count as a
      -- plain integer parameter and let PostgreSQL multiply. Prior
      -- versions used INTERVAL '%s seconds' which embedded the parameter
      -- inside a string literal -- safe while lookback_seconds was
      -- int-typed, but brittle if the type were ever loosened and
      -- unconventional psycopg2 usage (parameters should be values, not
      -- SQL fragments).
      AND ms.row_start_ts > NOW() - (%s * INTERVAL '1 second')
      AND NOT EXISTS (
          SELECT 1 FROM temporal_alignment ta
          WHERE ta.market_snapshot_id = ms.id
            AND ta.game_state_id = gs.id
      )
    ORDER BY ms.row_start_ts DESC
    LIMIT %s
"""


def _classify_quality(time_delta: Decimal) -> str:
    """Classify alignment quality based on time delta."""
    if time_delta <= _QUALITY_EXACT:
        return "exact"
    if time_delta <= _QUALITY_GOOD:
        return "good"
    if time_delta <= _QUALITY_FAIR:
        return "fair"
    if time_delta <= _QUALITY_POOR:
        return "poor"
    return "stale"


def find_unaligned_pairs(
    lookback_seconds: int = _LOOKBACK_SECONDS,
    batch_limit: int = _BATCH_LIMIT,
) -> list[dict[str, Any]]:
    """Find market_snapshot + game_state pairs without temporal alignments.

    Returns list of dicts ready for insert_temporal_alignment_batch().
    """
    if lookback_seconds <= 0 or batch_limit <= 0:
        raise ValueError(
            f"lookback_seconds and batch_limit must be positive, "
            f"got {lookback_seconds=}, {batch_limit=}"
        )

    with get_cursor() as cur:
        cur.execute(_UNALIGNED_QUERY, (lookback_seconds, batch_limit))
        rows = cur.fetchall()

    alignments = []
    for row in rows:
        time_delta = Decimal(str(row["time_delta_raw"]))
        quality = _classify_quality(time_delta)

        alignments.append(
            {
                "market_id": row["market_id"],
                "market_snapshot_id": row["market_snapshot_id"],
                "game_state_id": row["game_state_id"],
                "snapshot_time": row["snapshot_time"],
                "game_state_time": row["game_state_time"],
                "time_delta_seconds": time_delta,
                "alignment_quality": quality,
                "yes_ask_price": (
                    Decimal(str(row["yes_ask_price"])) if row["yes_ask_price"] is not None else None
                ),
                "no_ask_price": (
                    Decimal(str(row["no_ask_price"])) if row["no_ask_price"] is not None else None
                ),
                "spread": (Decimal(str(row["spread"])) if row["spread"] is not None else None),
                "volume": row["volume"],
                "game_status": row["game_status"],
                "home_score": row["home_score"],
                "away_score": row["away_score"],
                "period": row["period"],
                "clock": row["clock"],
                "game_id": row["game_id"],
            }
        )

    return alignments


class TemporalAlignmentWriter(BasePoller):
    """Background service that populates the temporal_alignment table.

    Polls for unaligned market_snapshot + game_state pairs and creates
    temporal_alignment rows with timestamp-based quality classification.

    Requires both ESPN and Kalshi pollers to be running to produce data.
    """

    SERVICE_KEY: ClassVar[str] = "temporal_alignment"
    HEALTH_COMPONENT: ClassVar[str] = "temporal_alignment"
    BREAKER_TYPE: ClassVar[str] = "data_stale"

    MIN_POLL_INTERVAL: ClassVar[int] = 5
    DEFAULT_POLL_INTERVAL: ClassVar[int] = 30

    def __init__(
        self,
        poll_interval: int | None = None,
        lookback_seconds: int = _LOOKBACK_SECONDS,
        batch_limit: int = _BATCH_LIMIT,
    ) -> None:
        super().__init__(poll_interval=poll_interval)
        self._lookback_seconds = lookback_seconds
        self._batch_limit = batch_limit

    def _get_job_name(self) -> str:
        return "Temporal Alignment Writer"

    def _poll_once(self) -> dict[str, int]:
        """Execute a single alignment cycle.

        Returns:
            Stats dict with items_created count (key matches BasePoller stats).
        """
        try:
            pairs = find_unaligned_pairs(
                lookback_seconds=self._lookback_seconds,
                batch_limit=self._batch_limit,
            )

            if not pairs:
                self.logger.debug("No unaligned pairs found")
                return {"items_created": 0}

            count = insert_temporal_alignment_batch(pairs)

            self.logger.info(
                "Created %d temporal alignments (%d pairs found)",
                count,
                len(pairs),
            )
            return {"items_created": count}

        except Exception:
            self.logger.exception("Temporal alignment cycle failed")
            raise


def create_temporal_alignment_writer(
    poll_interval: int = TemporalAlignmentWriter.DEFAULT_POLL_INTERVAL,
    lookback_seconds: int = _LOOKBACK_SECONDS,
    batch_limit: int = _BATCH_LIMIT,
) -> TemporalAlignmentWriter:
    """Factory function for ServiceSupervisor registration."""
    return TemporalAlignmentWriter(
        poll_interval=poll_interval,
        lookback_seconds=lookback_seconds,
        batch_limit=batch_limit,
    )
