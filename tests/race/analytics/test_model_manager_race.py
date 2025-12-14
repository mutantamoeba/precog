"""
Race Condition Tests for ModelManager.

Tests thread safety and concurrent access patterns.

Reference: TESTING_STRATEGY V3.2 - Race tests for concurrent safety
Related Requirements: REQ-VER-001 (Immutable Version Configs)

Usage:
    pytest tests/race/analytics/test_model_manager_race.py -v -m race
"""

import threading
import time
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from precog.analytics.model_manager import ModelManager

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def manager() -> ModelManager:
    """Create a ModelManager instance for testing."""
    return ModelManager()


# =============================================================================
# Race Condition Tests: Concurrent Serialization
# =============================================================================


@pytest.mark.race
class TestConcurrentSerialization:
    """Race condition tests for concurrent serialization."""

    def test_concurrent_config_serialization(self, manager: ModelManager) -> None:
        """Test concurrent config serialization is thread-safe."""
        results: list[str] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def serialize_config(thread_id: int) -> None:
            try:
                config = {
                    "thread_id": Decimal(f"{thread_id}"),
                    "value": Decimal("32.0"),
                }
                result = manager._prepare_config_for_db(config)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=serialize_config, args=(i,)) for i in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20

    def test_concurrent_config_deserialization(self, manager: ModelManager) -> None:
        """Test concurrent config deserialization is thread-safe."""
        results: list[dict[str, Any]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def deserialize_config(thread_id: int) -> None:
            try:
                config = {
                    "thread_id": f"{thread_id}",
                    "value": "32.0",
                }
                result = manager._parse_config_from_db(config)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=deserialize_config, args=(i,)) for i in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        for result in results:
            assert isinstance(result["value"], Decimal)

    def test_concurrent_roundtrip(self, manager: ModelManager) -> None:
        """Test concurrent round-trip operations."""
        import json

        results: list[dict[str, Any]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def roundtrip(thread_id: int) -> None:
            try:
                original = {"id": Decimal(f"{thread_id}"), "value": Decimal("99.99")}
                json_str = manager._prepare_config_for_db(original)
                parsed = json.loads(json_str)
                restored = manager._parse_config_from_db(parsed)
                with lock:
                    results.append((original, restored))
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=roundtrip, args=(i,)) for i in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        for original, restored in results:
            assert original["id"] == restored["id"]
            assert original["value"] == restored["value"]


# =============================================================================
# Race Condition Tests: Concurrent Validation
# =============================================================================


@pytest.mark.race
class TestConcurrentValidation:
    """Race condition tests for concurrent status validation."""

    def test_concurrent_status_validation(self, manager: ModelManager) -> None:
        """Test concurrent status validation is thread-safe."""
        results: list[bool] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def validate_transition(current: str, new: str) -> None:
            try:
                manager._validate_status_transition(current, new)
                with lock:
                    results.append(True)
            except Exception as e:
                with lock:
                    if "Invalid transition" in str(e):
                        results.append(False)  # Expected invalid
                    else:
                        errors.append(e)

        # Mix of valid and invalid transitions
        transitions = [
            ("draft", "testing"),
            ("testing", "active"),
            ("active", "deprecated"),
            ("deprecated", "active"),  # Invalid
            ("draft", "active"),  # Invalid
        ] * 4  # 20 total

        threads = [
            threading.Thread(target=validate_transition, args=trans) for trans in transitions
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        # Count valid results (12 valid transitions * 1)
        valid_count = sum(1 for r in results if r is True)
        assert valid_count == 12  # 3 valid transitions * 4 = 12

    def test_many_threads_same_validation(self, manager: ModelManager) -> None:
        """Test many threads validating same transition."""
        results: list[bool] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def validate() -> None:
            try:
                manager._validate_status_transition("draft", "testing")
                with lock:
                    results.append(True)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=validate) for _ in range(50)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 50
        assert all(r is True for r in results)


# =============================================================================
# Race Condition Tests: Concurrent DB Operations (Mocked)
# =============================================================================


@pytest.mark.race
class TestConcurrentDBOperations:
    """Race condition tests for concurrent DB operations (mocked)."""

    @patch("precog.analytics.model_manager.get_connection")
    @patch("precog.analytics.model_manager.release_connection")
    def test_concurrent_model_retrieval(
        self,
        mock_release: MagicMock,
        mock_get_conn: MagicMock,
        manager: ModelManager,
    ) -> None:
        """Test concurrent model retrieval is thread-safe."""

        # Each thread gets its own mock connection
        def create_mock_conn() -> MagicMock:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = (
                1,
                "test_model",
                "v1.0",
                "elo",
                "nfl",
                {"k_factor": "32.0"},
                "Test model",
                "draft",
                None,
                None,
                None,
                "2024-01-01",
                "tester",
                None,
            )
            mock_cursor.description = [
                ("model_id",),
                ("model_name",),
                ("model_version",),
                ("model_class",),
                ("domain",),
                ("config",),
                ("description",),
                ("status",),
                ("validation_calibration",),
                ("validation_accuracy",),
                ("validation_sample_size",),
                ("created_at",),
                ("created_by",),
                ("notes",),
            ]
            return mock_conn

        mock_get_conn.side_effect = create_mock_conn

        results: list[dict[str, Any] | None] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def get_model() -> None:
            try:
                result = manager.get_model(model_id=1)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=get_model) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        for result in results:
            assert result is not None
            assert result["model_name"] == "test_model"

    @patch("precog.analytics.model_manager.get_connection")
    @patch("precog.analytics.model_manager.release_connection")
    def test_concurrent_list_models(
        self,
        mock_release: MagicMock,
        mock_get_conn: MagicMock,
        manager: ModelManager,
    ) -> None:
        """Test concurrent list operations are thread-safe."""

        def create_mock_conn() -> MagicMock:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [
                (
                    i,
                    f"model_{i}",
                    "v1.0",
                    "elo",
                    "nfl",
                    {"k_factor": "32.0"},
                    f"Model {i}",
                    "draft",
                    None,
                    None,
                    None,
                    "2024-01-01",
                    "tester",
                    None,
                )
                for i in range(5)
            ]
            mock_cursor.description = [
                ("model_id",),
                ("model_name",),
                ("model_version",),
                ("model_class",),
                ("domain",),
                ("config",),
                ("description",),
                ("status",),
                ("validation_calibration",),
                ("validation_accuracy",),
                ("validation_sample_size",),
                ("created_at",),
                ("created_by",),
                ("notes",),
            ]
            return mock_conn

        mock_get_conn.side_effect = create_mock_conn

        results: list[list[dict[str, Any]]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def list_models() -> None:
            try:
                result = manager.list_models()
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=list_models) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        for result in results:
            assert len(result) == 5


# =============================================================================
# Race Condition Tests: Mixed Operations
# =============================================================================


@pytest.mark.race
class TestMixedOperations:
    """Race condition tests for mixed concurrent operations."""

    def test_concurrent_serialize_and_deserialize(self, manager: ModelManager) -> None:
        """Test concurrent serialize and deserialize operations."""

        serialize_results: list[str] = []
        deserialize_results: list[dict[str, Any]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def serialize(idx: int) -> None:
            try:
                config = {"id": Decimal(f"{idx}"), "value": Decimal("1.0")}
                result = manager._prepare_config_for_db(config)
                with lock:
                    serialize_results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        def deserialize(idx: int) -> None:
            try:
                config = {"id": f"{idx}", "value": "2.0"}
                result = manager._parse_config_from_db(config)
                with lock:
                    deserialize_results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = []
        for i in range(10):
            threads.append(threading.Thread(target=serialize, args=(i,)))
            threads.append(threading.Thread(target=deserialize, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(serialize_results) == 10
        assert len(deserialize_results) == 10

    def test_rapid_succession_operations(self, manager: ModelManager) -> None:
        """Test rapid succession of operations from multiple threads."""
        operation_count = 0
        lock = threading.Lock()
        errors: list[Exception] = []

        def rapid_operations() -> None:
            nonlocal operation_count
            try:
                for _ in range(50):
                    # Serialize
                    config = {"value": Decimal("1.0")}
                    manager._prepare_config_for_db(config)

                    # Deserialize
                    manager._parse_config_from_db({"value": "2.0"})

                    # Validate
                    manager._validate_status_transition("draft", "testing")

                    with lock:
                        operation_count += 3
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=rapid_operations) for _ in range(5)]

        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start

        assert len(errors) == 0
        assert operation_count == 750  # 5 threads * 50 iterations * 3 ops
        assert elapsed < 5.0
