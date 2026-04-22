"""Contract tests for TypedDict shapes in precog.trading.types.

See each test for rationale.

Current pins:
    - PositionResponse.market_id must be int (issue #952, Migration 0022).
"""


def test_position_response_market_id_is_int_per_migration_0022():
    """PositionResponse.market_id must be int (regression: #952, Phase 2 blocker).

    Migration 0022 changed positions.market_id to INTEGER. The TypedDict shape was
    forgotten during that migration and silently diverged for months until the S81
    retrospective audit caught it. Pin the invariant: mypy trusts TypedDict
    annotations as gospel, so any future drift would cascade into Phase 2 manual
    placement code (Epic #504) as silent runtime errors.
    """
    from precog.trading.types import PositionResponse

    assert PositionResponse.__annotations__["market_id"] is int, (
        "PositionResponse.market_id must be int to match DB column type "
        "(see Migration 0022 and issue #952)."
    )
