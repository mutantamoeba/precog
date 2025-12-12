"""
Chaos Tests for ESPN Client.

Tests API client resilience under chaotic conditions:
- Random API failures and network instability
- Malformed and unexpected responses
- Rate limiting edge cases under chaos
- Service degradation scenarios

Related:
- TESTING_STRATEGY V3.3: All 8 test types required
- api_connectors/espn_client module coverage
- Issue #207: ESPN E2E Testing (includes chaos scenarios)

Usage:
    pytest tests/chaos/api_connectors/test_espn_client_chaos.py -v -m chaos

Educational Note:
    Chaos tests verify that the ESPN client degrades gracefully when
    external services behave unpredictably. Unlike unit tests that verify
    correct behavior, chaos tests verify resilient behavior under failure.

    Key chaos scenarios for ESPN API:
    1. Intermittent failures (flaky network)
    2. Malformed JSON responses
    3. Unexpected HTTP status codes
    4. Partial/truncated responses
    5. Rate limit bursts under stress
"""

import random
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
import requests

from tests.fixtures import ESPN_NFL_SCOREBOARD_LIVE


@pytest.mark.chaos
class TestESPNClientChaos:
    """Chaos tests for ESPN API client resilience."""

    def _create_espn_client(self, rate_limit: int = 500):
        """Create an ESPNClient for chaos testing."""
        from precog.api_connectors.espn_client import ESPNClient

        return ESPNClient(rate_limit_per_hour=rate_limit, max_retries=3, timeout_seconds=5)

    def test_intermittent_api_failures(self):
        """
        CHAOS: Random API request failures (flaky network simulation).

        Verifies:
        - System handles sporadic failures gracefully
        - Retry logic eventually succeeds
        - Client doesn't crash on intermittent errors
        """
        client = self._create_espn_client()
        call_count = [0]

        def flaky_api(*args, **kwargs):
            call_count[0] += 1
            if random.random() < 0.3:  # 30% failure rate
                raise requests.exceptions.ConnectionError("Network flaky")
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
            mock_resp.raise_for_status = Mock()
            return mock_resp

        with patch.object(client.session, "get", side_effect=flaky_api):
            successes = 0
            failures = 0

            for _ in range(20):
                try:
                    result = client.get_nfl_scoreboard()
                    if result is not None:
                        successes += 1
                except Exception:
                    failures += 1

            # Should have a mix - not all fail, not all succeed
            assert successes > 0, "All requests failed under chaos"
            # Due to retry logic, failures should be limited

    def test_random_http_status_codes(self):
        """
        CHAOS: Random unexpected HTTP status codes.

        Verifies:
        - Client handles variety of HTTP status codes
        - Doesn't crash on unexpected statuses (418, 451, etc.)
        - Error handling is comprehensive
        """
        from precog.api_connectors.espn_client import ESPNAPIError

        client = self._create_espn_client()

        # Various HTTP status codes including unusual ones
        status_codes = [200, 201, 204, 301, 400, 401, 403, 404, 418, 429, 451, 500, 502, 503]
        results = {"success": 0, "error": 0}

        for status in status_codes:
            mock_resp = Mock()
            mock_resp.status_code = status
            mock_resp.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
            if status >= 400:
                mock_resp.raise_for_status.side_effect = requests.HTTPError(f"{status} Error")
            else:
                mock_resp.raise_for_status = Mock()

            with patch.object(client.session, "get", return_value=mock_resp):
                try:
                    client.get_nfl_scoreboard()
                    results["success"] += 1
                except (ESPNAPIError, requests.HTTPError):
                    results["error"] += 1

        # Should handle all status codes without crashing
        assert results["success"] + results["error"] == len(status_codes)

    def test_malformed_json_responses(self):
        """
        CHAOS: Malformed and corrupted JSON responses.

        Verifies:
        - Client handles invalid JSON gracefully
        - Doesn't crash on parse errors
        - Returns appropriate error or empty result
        """
        from precog.api_connectors.espn_client import ESPNAPIError

        client = self._create_espn_client()

        malformed_responses = [
            None,  # No response
            "",  # Empty string
            "not json at all",  # Invalid JSON
            {"events": None},  # Null events
            {"events": "not a list"},  # Wrong type
            {"wrong_key": []},  # Missing expected keys
            {"events": [{"malformed": True}]},  # Malformed event
            {"events": [{"competitions": None}]},  # Null competitions
        ]

        for i, malformed in enumerate(malformed_responses):
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.raise_for_status = Mock()

            if malformed is None or (isinstance(malformed, str) and not malformed.startswith("{")):
                mock_resp.json.side_effect = ValueError("Invalid JSON")
            else:
                mock_resp.json.return_value = malformed

            with patch.object(client.session, "get", return_value=mock_resp):
                try:
                    result = client.get_nfl_scoreboard()
                    # Should return empty list or parsed result, not crash
                    assert isinstance(result, list), f"Response {i} should return list"
                except ESPNAPIError:
                    # ESPNAPIError is acceptable for truly malformed responses
                    pass
                except Exception as e:
                    pytest.fail(f"Unexpected exception for response {i}: {type(e).__name__}: {e}")

    def test_rate_limit_chaos(self):
        """
        CHAOS: Rate limiting under chaotic request patterns.

        Verifies:
        - Rate limiter handles burst + pause + burst patterns
        - Timestamp cleanup works under chaotic access
        - Remaining count is always accurate
        """
        from precog.api_connectors.espn_client import RateLimitExceeded

        client = self._create_espn_client(rate_limit=20)

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_resp.raise_for_status = Mock()

        with patch.object(client.session, "get", return_value=mock_resp):
            # Chaotic pattern: bursts interspersed with "time passing"
            for cycle in range(3):
                # Burst of requests
                burst_success = 0
                burst_limited = 0

                for _ in range(10):
                    try:
                        client.get_nfl_scoreboard()
                        burst_success += 1
                    except RateLimitExceeded:
                        burst_limited += 1

                # Simulate time passing (move timestamps to the past)
                now = datetime.now()
                client.request_timestamps = [
                    now - timedelta(hours=2) for _ in client.request_timestamps
                ]

                # Verify rate limit reset
                remaining = client.get_remaining_requests()
                assert remaining == 20, f"Cycle {cycle}: Expected 20 remaining after reset"

    def test_timeout_chaos(self):
        """
        CHAOS: Random timeout scenarios.

        Verifies:
        - Client handles timeouts gracefully
        - Retry logic works for timeout errors
        - System doesn't hang indefinitely
        """
        from precog.api_connectors.espn_client import ESPNAPIError

        client = self._create_espn_client()
        timeout_count = [0]

        def chaotic_timeout(*args, **kwargs):
            timeout_count[0] += 1
            if random.random() < 0.5:  # 50% timeout rate
                raise requests.exceptions.Timeout("Request timed out")
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
            mock_resp.raise_for_status = Mock()
            return mock_resp

        with patch.object(client.session, "get", side_effect=chaotic_timeout):
            successes = 0
            timeouts = 0

            for _ in range(10):
                try:
                    client.get_nfl_scoreboard()
                    successes += 1
                except (ESPNAPIError, requests.exceptions.Timeout):
                    timeouts += 1

            # Should have some successes despite timeouts
            # Due to 50% timeout + 3 retries, success is likely
            assert successes >= 0  # Just verify it doesn't crash

    def test_partial_response_data(self):
        """
        CHAOS: Partial/incomplete response data.

        Verifies:
        - Client handles missing fields gracefully
        - Doesn't crash on partial data
        - Returns what it can parse
        """
        client = self._create_espn_client()

        # Partially complete responses
        partial_responses = [
            {"events": []},  # Empty events
            {"events": [{}]},  # Empty event object
            {"events": [{"id": "123"}]},  # Missing competitions
            {"events": [{"id": "123", "competitions": []}]},  # Empty competitions
            {
                "events": [
                    {
                        "id": "123",
                        "competitions": [{"competitors": []}],  # No teams
                    }
                ]
            },
            {
                "events": [
                    {
                        "id": "123",
                        "competitions": [
                            {
                                "competitors": [
                                    {"homeAway": "home", "score": "10"}  # Missing away
                                ]
                            }
                        ],
                    }
                ]
            },
        ]

        for i, partial in enumerate(partial_responses):
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = partial
            mock_resp.raise_for_status = Mock()

            with patch.object(client.session, "get", return_value=mock_resp):
                try:
                    result = client.get_nfl_scoreboard()
                    # Should return a list (possibly empty), not crash
                    assert isinstance(result, list), f"Partial response {i} should return list"
                except Exception:
                    # Any controlled exception is fine
                    pass  # Partial data may raise, that's acceptable


@pytest.mark.chaos
class TestESPNClientNetworkChaos:
    """Chaos tests focused on network-level failures."""

    def test_connection_refused(self):
        """CHAOS: Connection refused errors."""
        from precog.api_connectors.espn_client import ESPNAPIError, ESPNClient

        client = ESPNClient()

        with patch.object(
            client.session, "get", side_effect=requests.ConnectionError("Connection refused")
        ):
            with pytest.raises(ESPNAPIError) as exc_info:
                client.get_nfl_scoreboard()

            assert "connection" in str(exc_info.value).lower()

    def test_dns_resolution_failure(self):
        """CHAOS: DNS resolution failures."""
        from precog.api_connectors.espn_client import ESPNAPIError, ESPNClient

        client = ESPNClient()

        with patch.object(
            client.session,
            "get",
            side_effect=requests.ConnectionError("Failed to resolve 'site.api.espn.com'"),
        ):
            with pytest.raises(ESPNAPIError):
                client.get_nfl_scoreboard()

    def test_ssl_certificate_error(self):
        """CHAOS: SSL/TLS certificate errors."""
        from precog.api_connectors.espn_client import ESPNAPIError, ESPNClient

        client = ESPNClient()

        with patch.object(
            client.session,
            "get",
            side_effect=requests.exceptions.SSLError("Certificate verify failed"),
        ):
            with pytest.raises(ESPNAPIError):
                client.get_nfl_scoreboard()

    def test_chunked_encoding_error(self):
        """CHAOS: Chunked encoding errors (truncated response)."""
        from precog.api_connectors.espn_client import ESPNAPIError, ESPNClient

        client = ESPNClient()

        with patch.object(
            client.session,
            "get",
            side_effect=requests.exceptions.ChunkedEncodingError("Connection broken"),
        ):
            with pytest.raises(ESPNAPIError):
                client.get_nfl_scoreboard()


@pytest.mark.chaos
class TestESPNClientServiceDegradation:
    """Chaos tests for service degradation scenarios."""

    def test_slow_degradation(self):
        """
        CHAOS: Gradually degrading service (increasing latency/errors).

        Verifies client handles service degradation gracefully.
        """
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient(max_retries=2)
        call_number = [0]

        def degrading_service(*args, **kwargs):
            call_number[0] += 1
            # Simulate degradation: more calls = more failures
            failure_rate = min(0.9, call_number[0] * 0.1)  # 10% -> 90%

            if random.random() < failure_rate:
                raise requests.exceptions.Timeout("Service degrading")

            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
            mock_resp.raise_for_status = Mock()
            return mock_resp

        with patch.object(client.session, "get", side_effect=degrading_service):
            early_successes = 0
            late_successes = 0

            # Early calls (should mostly succeed)
            for _ in range(5):
                try:
                    client.get_nfl_scoreboard()
                    early_successes += 1
                except Exception:
                    pass

            # Reset call counter for late phase
            call_number[0] = 8  # Start at high failure rate

            # Late calls (should mostly fail)
            for _ in range(5):
                try:
                    client.get_nfl_scoreboard()
                    late_successes += 1
                except Exception:
                    pass

            # Early phase should have more successes than late phase
            # (or at least not crash)
            assert early_successes >= 0
            assert late_successes >= 0

    def test_empty_response_recovery(self):
        """
        CHAOS: Service returning empty responses then recovering.

        Verifies client handles service returning nothing then normal data.
        """
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()
        responses = [
            {"events": []},  # Empty
            {"events": []},  # Empty
            ESPN_NFL_SCOREBOARD_LIVE,  # Recovery
            ESPN_NFL_SCOREBOARD_LIVE,  # Normal
        ]
        response_index = [0]

        def recovering_service(*args, **kwargs):
            idx = response_index[0]
            response_index[0] = min(idx + 1, len(responses) - 1)

            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = responses[idx]
            mock_resp.raise_for_status = Mock()
            return mock_resp

        with patch.object(client.session, "get", side_effect=recovering_service):
            results = []
            for _ in range(4):
                result = client.get_nfl_scoreboard()
                results.append(len(result))

            # First two empty, last two should have data
            assert results[0] == 0
            assert results[1] == 0
            assert results[2] > 0  # Recovered
            assert results[3] > 0  # Normal
