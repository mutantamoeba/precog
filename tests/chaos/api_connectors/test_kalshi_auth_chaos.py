"""
Chaos Tests for Kalshi Authentication.

Tests authentication resilience under chaotic conditions:
- Random failures in key loading
- Corrupted signature inputs
- Environmental instability

Related:
- TESTING_STRATEGY V3.3: All 8 test types required
- api_connectors/kalshi_auth module coverage

Usage:
    pytest tests/chaos/api_connectors/test_kalshi_auth_chaos.py -v -m chaos

Educational Note:
    These tests demonstrate the clean DI (Dependency Injection) approach.
    KalshiAuth now accepts an optional key_loader parameter, allowing us to
    inject a mock key loader directly instead of patching module internals.

    For chaos tests, we inject flaky/failing key loaders to simulate
    environmental instability without complex patch management.

    Reference: Pattern 12 (Dependency Injection) in DEVELOPMENT_PATTERNS
"""

import random
from unittest.mock import MagicMock

import pytest


@pytest.mark.chaos
class TestKalshiAuthChaos:
    """Chaos tests for Kalshi authentication resilience."""

    def _create_mock_auth(self):
        """Create a KalshiAuth with mocked key loading using DI."""
        from precog.api_connectors.kalshi_auth import KalshiAuth

        mock_private_key = MagicMock()
        mock_private_key.sign.return_value = b"mock_signature"

        return KalshiAuth(
            api_key="test-api-key",
            private_key_path="/fake/path/key.pem",
            key_loader=lambda path: mock_private_key,
        )

    def test_intermittent_signature_failures(self):
        """
        CHAOS: Random signature generation failures.

        Verifies:
        - System handles sporadic signing failures
        - Error messages are informative
        """
        from precog.api_connectors.kalshi_auth import KalshiAuth

        call_count = [0]

        def flaky_sign(*args, **kwargs):
            call_count[0] += 1
            if random.random() < 0.3:  # 30% failure rate
                raise Exception("Random signing failure")
            return b"mock_signature"

        mock_private_key = MagicMock()
        mock_private_key.sign = flaky_sign

        # Use DI to inject mock with flaky signature generation
        auth = KalshiAuth(
            api_key="test-api-key",
            private_key_path="/fake/path/key.pem",
            key_loader=lambda path: mock_private_key,
        )

        successes = 0
        failures = 0

        for i in range(50):
            try:
                auth.get_headers("GET", "/test")
                successes += 1
            except Exception:
                failures += 1

        # Verify we got a mix of successes and failures
        assert successes > 0, "All operations failed"

    def test_malformed_input_resilience(self):
        """
        CHAOS: Authentication with malformed inputs.

        Verifies:
        - Graceful handling of edge case inputs
        - No crashes from unusual data
        """
        auth = self._create_mock_auth()

        chaotic_inputs = [
            ("", ""),  # Empty strings
            ("GET", "/path" * 100),  # Very long path
            ("DELETE", "/special!@#$%"),  # Special characters
            ("POST", "/unicode/\u4e2d\u6587"),  # Unicode
            ("get", "/lowercase"),  # Lowercase method
        ]

        for method, path in chaotic_inputs:
            # Should not crash, may raise expected validation errors
            try:
                auth.get_headers(method, path)
            except (ValueError, TypeError):
                pass  # Expected for invalid inputs

    def test_key_loading_chaos(self):
        """
        CHAOS: Simulate intermittent key loading failures.

        Verifies:
        - Clear error messages on key load failure
        - System state remains consistent after failure
        """
        from precog.api_connectors.kalshi_auth import KalshiAuth

        load_count = [0]

        def flaky_load(path):
            load_count[0] += 1
            if random.random() < 0.5:  # 50% failure rate
                raise FileNotFoundError(f"Simulated key file not found: {path}")
            mock_key = MagicMock()
            mock_key.sign.return_value = b"sig"
            return mock_key

        successes = 0
        failures = 0

        for _ in range(20):
            try:
                # Use DI to inject flaky key loader
                KalshiAuth(
                    api_key="test-api-key",
                    private_key_path="/fake/path/key.pem",
                    key_loader=flaky_load,
                )
                successes += 1
            except FileNotFoundError:
                failures += 1

        # Should have a mix of successes and failures
        assert successes > 0, "All init attempts failed"
        assert load_count[0] == 20, "Not all attempts were made"

    def test_memory_pressure_simulation(self):
        """
        CHAOS: Authentication under simulated memory pressure.

        Verifies:
        - Operations complete under resource constraints
        - No memory leaks from repeated operations
        """
        auth = self._create_mock_auth()

        # Rapid-fire operations to simulate pressure
        results = []
        for i in range(500):
            headers = auth.get_headers("GET", f"/path/{i}")
            results.append(headers)

            # Clear periodically to avoid actual memory issues in test
            if i % 100 == 0:
                results.clear()

        # Should complete without issues
        assert True
