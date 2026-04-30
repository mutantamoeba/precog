"""Regression test for the autouse ``_reset_module_lazy_caches`` fixture.

The fixture in ``tests/conftest.py`` resets module-level lazy-initialized
cache globals (e.g., ``crud_canonical_match_log._MANUAL_V1_ID_CACHE``) before
every test runs.  This closes the test-isolation gap that surfaced via slot
0074's PR #1094 mid-session CI failure (session 82): unit tests passed
locally because an earlier integration test had populated the cache, but
failed in CI's fresh worker process where the cache-population attempt
raised ``ValueError: Database password not found``.

If a future refactor removes the fixture, modifies the
``_LAZY_CACHE_GLOBALS`` registry incorrectly, or breaks the reset semantics
in any way, ``test_cache_reset_between_tests_b`` below will fail with a
clear message pointing back at the fixture.

The two tests below MUST run in the same worker process for the regression
to surface — if pytest-xdist distributes them across workers, the cache
state isn't shared and the test silently passes.  Both tests live in the
same class AND share an ``xdist_group`` marker so they co-locate under
``--dist=loadgroup``.

Note (corrected per claude-review on PR #1096 — #1095 close-out item 15):
pytest-xdist's DEFAULT distribution is ``--dist=load`` (load-balancing,
which CAN split same-class tests across workers); the ``xdist_group``
marker pins both tests to the same worker only when xdist is run with
``--dist=loadgroup``.  An earlier draft of this docstring claimed
``loadscope`` was the default — both the default name AND the marker's
binding mode were wrong.  See the class-level docstring for the
load-balancing failure mode the marker prevents.
"""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.xdist_group("conftest_lazy_cache_reset_regression")
class TestModuleLazyCacheResetFixture:
    """Verify the autouse fixture resets registered caches between tests.

    Test naming uses ``_a`` / ``_b`` suffixes to make the order-dependent
    pairing explicit: ``_a`` pollutes the cache, ``_b`` asserts it was reset.
    Pytest's default test discovery order is filesystem + alphabetical, so
    ``_a`` runs before ``_b`` reliably.

    The ``xdist_group`` marker pins both tests to the same worker process
    under pytest-xdist parallel execution with ``--dist=loadgroup``.
    Without the marker (or under xdist's default ``--dist=load`` /
    ``LoadScheduling``), the two tests could be distributed across
    separate worker processes — ``_b`` would observe a clean cache
    because its worker never ran ``_a`` (each xdist worker is a fresh
    Python process with its own module-state copy).  Under that
    distribution, ``_b`` would pass even if the fixture were broken —
    silently false-pass.  The xdist_group marker forces both tests to
    the same worker so the cross-test pollution-vs-reset behavior is
    actually exercised under parallel CI when ``--dist=loadgroup`` is
    in effect.
    """

    def test_cache_reset_between_tests_a_pollutes(self) -> None:
        """First test in the pair: pollute the cache to a sentinel value.

        The fixture should have reset the cache to ``None`` before this
        test runs.  This test then writes a sentinel to simulate real-
        world cache pollution (which happens whenever
        ``get_manual_v1_algorithm_id()`` is called against a real DB).
        """
        from precog.database import crud_canonical_match_log

        # Fixture-reset precondition: cache starts at None.
        assert crud_canonical_match_log._MANUAL_V1_ID_CACHE is None, (
            "Cache was non-None at test start — fixture is not running "
            "BEFORE the test (autouse contract violated)"
        )

        # Pollute the cache.  Without the fixture, this pollution would
        # leak into the next test.
        crud_canonical_match_log._MANUAL_V1_ID_CACHE = 9999

    def test_cache_reset_between_tests_b_observes_clean_state(self) -> None:
        """Second test in the pair: observe the cache was reset.

        Without the autouse fixture, this test would see ``9999`` (the
        sentinel left behind by ``_a``) and fail.  With the fixture
        running, the cache is reset to ``None`` before this test runs
        regardless of any prior pollution.
        """
        from precog.database import crud_canonical_match_log

        assert crud_canonical_match_log._MANUAL_V1_ID_CACHE is None, (
            "Cache was not reset between tests — the autouse fixture "
            "_reset_module_lazy_caches in tests/conftest.py is broken, "
            "removed, or no longer covers _MANUAL_V1_ID_CACHE.  "
            "See the comment block in tests/conftest.py for the bug class "
            "this fixture closes (slot 0074 / PR #1094 / session 82)."
        )
