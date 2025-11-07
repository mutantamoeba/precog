"""
Rate limiting for API clients using token bucket algorithm.

This module provides thread-safe rate limiting to comply with API rate limits
and avoid 429 (Too Many Requests) errors.

Token Bucket Algorithm:
-----------------------
Imagine a bucket that holds tokens. Each API request consumes one token.
Tokens are added to the bucket at a steady rate (refill rate).
If the bucket is empty, the request must wait until a token is available.

Why Token Bucket?
- Allows bursts: If you haven't made requests for a while, bucket fills up
  and you can make multiple requests quickly (up to bucket capacity)
- Smooth rate: Prevents exceeding average rate over time
- Simple and efficient: Just track token count and last refill time

Example:
    Kalshi allows 100 requests/minute.
    - Bucket capacity: 100 tokens
    - Refill rate: 100 tokens / 60 seconds = 1.67 tokens/second
    - Each request consumes 1 token
    - If you make 10 requests quickly, 90 tokens remain
    - Tokens refill continuously, so after 6 seconds you have 100 tokens again

Reference: docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md
Related Requirements: REQ-API-005 (API Rate Limit Management)
Related ADR: ADR-051 (Rate Limiting Strategy)
"""

import time
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)


class TokenBucket:
    """
    Thread-safe token bucket rate limiter.

    Controls request rate by maintaining a "bucket" of tokens that refill
    over time. Each request consumes one token. If no tokens available,
    the request must wait.

    Attributes:
        capacity: Maximum number of tokens in bucket (burst size)
        refill_rate: Tokens added per second
        tokens: Current number of tokens available
        last_refill: Timestamp of last token refill

    Usage:
        >>> limiter = TokenBucket(capacity=100, refill_rate=1.67)
        >>> limiter.acquire()  # Waits if necessary, then consumes token
        >>> # Make API request here

    Educational Notes:
        Thread Safety:
        - Uses threading.Lock to prevent race conditions
        - Multiple threads can safely call acquire() simultaneously
        - Lock ensures only one thread modifies token count at a time

        Why This Matters:
        - Without locking, two threads could both see "10 tokens available"
        - Both would decrement, but only 9 tokens should remain
        - Lock prevents this data race
    """

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum tokens (e.g., 100 for Kalshi)
            refill_rate: Tokens per second (e.g., 1.67 for 100/min)

        Example:
            >>> # Kalshi: 100 requests per minute
            >>> limiter = TokenBucket(capacity=100, refill_rate=100/60)
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)  # Start with full bucket
        self.last_refill = time.time()
        self._lock = threading.Lock()  # Thread safety

        logger.info(
            f"TokenBucket initialized: capacity={capacity}, "
            f"refill_rate={refill_rate:.2f} tokens/sec",
            extra={"capacity": capacity, "refill_rate": refill_rate}
        )

    def _refill(self) -> None:
        """
        Refill tokens based on time elapsed.

        Called internally before each acquire().
        Adds tokens proportional to time since last refill.

        Educational Note:
            If 3 seconds passed and refill_rate is 1.67 tokens/sec:
            - Add: 3 * 1.67 = 5.01 tokens
            - But never exceed capacity (100 tokens max)

            This is why we use: min(capacity, tokens + elapsed * rate)
        """
        now = time.time()
        elapsed = now - self.last_refill

        # Calculate tokens to add (time * rate)
        tokens_to_add = elapsed * self.refill_rate

        # Add tokens, but don't exceed capacity
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)

        self.last_refill = now

        logger.debug(
            f"Refilled {tokens_to_add:.2f} tokens (elapsed={elapsed:.2f}s)",
            extra={
                "tokens_added": tokens_to_add,
                "elapsed_seconds": elapsed,
                "tokens_available": self.tokens
            }
        )

    def acquire(self, tokens: int = 1, block: bool = True) -> bool:
        """
        Acquire tokens from bucket (consume for API request).

        Args:
            tokens: Number of tokens to consume (default 1)
            block: If True, wait until tokens available. If False, return immediately.

        Returns:
            True if tokens acquired, False if not available (only when block=False)

        Raises:
            ValueError: If requested tokens exceed capacity

        Example:
            >>> limiter = TokenBucket(capacity=100, refill_rate=1.67)
            >>>
            >>> # Blocking mode (waits if needed)
            >>> limiter.acquire()  # Always returns True (after waiting)
            >>> # Make API request
            >>>
            >>> # Non-blocking mode (returns immediately)
            >>> if limiter.acquire(block=False):
            ...     # Make API request
            ... else:
            ...     print("Rate limit reached, try later")

        Educational Note:
            Blocking vs Non-blocking:
            - block=True: If no tokens, sleep and retry (default)
            - block=False: If no tokens, return False immediately

            Use block=True for background tasks (can wait)
            Use block=False for user-facing requests (fail fast)
        """
        if tokens > self.capacity:
            raise ValueError(
                f"Requested {tokens} tokens exceeds capacity {self.capacity}"
            )

        with self._lock:  # Thread-safe token check/modification
            self._refill()  # Add tokens based on elapsed time

            # Check if enough tokens available
            if self.tokens >= tokens:
                self.tokens -= tokens

                # Warn if running low (80% consumed)
                if self.tokens < self.capacity * 0.2:
                    logger.warning(
                        f"Rate limit warning: Only {self.tokens:.1f}/{self.capacity} tokens remaining",
                        extra={
                            "tokens_remaining": self.tokens,
                            "capacity": self.capacity,
                            "utilization_pct": (1 - self.tokens/self.capacity) * 100
                        }
                    )

                logger.debug(
                    f"Acquired {tokens} token(s), {self.tokens:.1f} remaining",
                    extra={"tokens_consumed": tokens, "tokens_remaining": self.tokens}
                )

                return True

            # Not enough tokens available
            if not block:
                logger.debug(
                    f"Cannot acquire {tokens} token(s), only {self.tokens:.1f} available",
                    extra={
                        "tokens_requested": tokens,
                        "tokens_available": self.tokens
                    }
                )
                return False

        # Blocking mode: Wait and retry
        # Calculate wait time (time to refill needed tokens)
        tokens_needed = tokens - self.tokens
        wait_time = tokens_needed / self.refill_rate

        logger.info(
            f"Rate limit reached, waiting {wait_time:.2f}s for {tokens_needed:.1f} tokens",
            extra={
                "wait_seconds": wait_time,
                "tokens_needed": tokens_needed
            }
        )

        time.sleep(wait_time)

        # Retry acquisition after waiting
        return self.acquire(tokens=tokens, block=True)

    def get_available_tokens(self) -> float:
        """
        Get current number of available tokens.

        Returns:
            Number of tokens currently in bucket

        Example:
            >>> limiter = TokenBucket(capacity=100, refill_rate=1.67)
            >>> tokens = limiter.get_available_tokens()
            >>> print(f"{tokens:.1f} requests available")

        Note:
            This is a snapshot. Tokens refill continuously.
        """
        with self._lock:
            self._refill()
            return self.tokens


class RateLimiter:
    """
    High-level rate limiter for API clients.

    Wraps TokenBucket with API-specific logic like handling 429 errors
    and exponential backoff.

    Usage:
        >>> limiter = RateLimiter(requests_per_minute=100)
        >>>
        >>> # Before each API request
        >>> limiter.wait_if_needed()
        >>> response = make_api_request()
        >>>
        >>> # After 429 error
        >>> limiter.handle_rate_limit_error(retry_after=60)

    Educational Note:
        This class adds API-specific handling on top of TokenBucket:
        - Converts "requests per minute" to token bucket parameters
        - Handles Retry-After header from 429 responses
        - Provides simple wait_if_needed() interface
    """

    def __init__(
        self,
        requests_per_minute: int,
        burst_size: Optional[int] = None
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute (e.g., 100)
            burst_size: Maximum burst size (defaults to requests_per_minute)

        Example:
            >>> # Kalshi: 100 requests per minute
            >>> limiter = RateLimiter(requests_per_minute=100)
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size or requests_per_minute

        # Convert to token bucket parameters
        refill_rate = requests_per_minute / 60.0  # tokens per second

        self.bucket = TokenBucket(
            capacity=self.burst_size,
            refill_rate=refill_rate
        )

        logger.info(
            f"RateLimiter initialized: {requests_per_minute} req/min "
            f"(burst: {self.burst_size})",
            extra={
                "requests_per_minute": requests_per_minute,
                "burst_size": self.burst_size
            }
        )

    def wait_if_needed(self) -> None:
        """
        Wait if rate limit would be exceeded.

        Call this before each API request. Blocks if necessary.

        Example:
            >>> limiter = RateLimiter(requests_per_minute=100)
            >>>
            >>> for i in range(200):
            ...     limiter.wait_if_needed()  # Will block after 100 requests
            ...     response = make_api_request()
        """
        self.bucket.acquire(tokens=1, block=True)

    def handle_rate_limit_error(self, retry_after: Optional[int] = None) -> None:
        """
        Handle 429 (Too Many Requests) error.

        Args:
            retry_after: Seconds to wait (from Retry-After header), or None

        Example:
            >>> limiter = RateLimiter(requests_per_minute=100)
            >>>
            >>> try:
            ...     response = make_api_request()
            ... except HTTPError as e:
            ...     if e.response.status_code == 429:
            ...         retry_after = e.response.headers.get('Retry-After')
            ...         limiter.handle_rate_limit_error(retry_after)
            ...         # Retry request

        Educational Note:
            Retry-After header tells you exactly how long to wait.
            If not provided, we use exponential backoff (60s default).
        """
        if retry_after is not None:
            wait_time = int(retry_after)
        else:
            # Default to 60 seconds if no Retry-After header
            wait_time = 60

        logger.warning(
            f"Rate limit (429) error, waiting {wait_time}s before retry",
            extra={"retry_after_seconds": wait_time}
        )

        time.sleep(wait_time)

    def get_utilization(self) -> float:
        """
        Get current rate limit utilization (0.0 to 1.0).

        Returns:
            Utilization percentage (0.0 = unused, 1.0 = fully utilized)

        Example:
            >>> limiter = RateLimiter(requests_per_minute=100)
            >>> util = limiter.get_utilization()
            >>> print(f"Rate limit {util*100:.1f}% utilized")
        """
        available = self.bucket.get_available_tokens()
        return 1.0 - (available / self.burst_size)
