"""Stress test configuration.

CI Strategy:
    Most stress tests are CI-safe (mocked dependencies, direct _poll_wrapper calls).
    Individual test classes/methods that start real APScheduler BackgroundSchedulers
    have @pytest.mark.skipif(_is_ci, ...) markers within the test files themselves.

    Previously, entire files were skipped via pytest_collection_modifyitems here.
    Now skip granularity is at the class/test level for maximum CI coverage.

    Run all locally: PRECOG_ENV=test python -m pytest tests/stress/ -v
"""
