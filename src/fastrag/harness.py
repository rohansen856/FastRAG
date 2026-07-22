"""Orchestration around every outbound provider call.

Hosted free tiers rate-limit aggressively (Groq allows 30 requests per minute),
so every provider call is wrapped in retries with jittered backoff, a per-provider
circuit breaker, and a request-wide deadline that stops a slow stage from
consuming the whole latency budget.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

import httpx

from .metrics import CIRCUIT_TRIPS, RETRIES

T = TypeVar("T")

RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


class ProviderError(RuntimeError):
    def __init__(
        self,
        provider: str,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable


class CircuitOpenError(ProviderError):
    pass


class DeadlineExceeded(ProviderError):
    pass


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff: float = 0.25
    max_backoff: float = 4.0

    def backoff(self, attempt: int) -> float:
        window = min(self.max_backoff, self.initial_backoff * (2**attempt))
        # Full jitter: without it, concurrent callers retry in lockstep and
        # re-trip the same rate limit they are backing off from.
        return random.uniform(0, window)


class Deadline:
    """A wall-clock budget shared by every stage of one request."""

    def __init__(self, budget_seconds: float) -> None:
        self._expires_at = time.monotonic() + budget_seconds

    @property
    def remaining(self) -> float:
        return max(0.0, self._expires_at - time.monotonic())

    @property
    def expired(self) -> bool:
        return self.remaining <= 0

    def check(self, provider: str, stage: str) -> None:
        if self.expired:
            raise DeadlineExceeded(provider, f"request deadline exceeded before {stage}")

    def clamp(self, timeout: float) -> float:
        return max(0.05, min(timeout, self.remaining))


class CircuitBreaker:
    """Stops hammering a provider that is already failing."""

    def __init__(self, provider: str, *, failure_threshold: int, reset_seconds: float) -> None:
        self._provider = provider
        self._threshold = failure_threshold
        self._reset_seconds = reset_seconds
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self._reset_seconds:
            # Half-open: allow one probe through and let the result decide.
            self._opened_at = None
            self._failures = self._threshold - 1
            return False
        return True

    def before(self) -> None:
        if self.is_open:
            raise CircuitOpenError(self._provider, f"{self._provider} circuit is open")

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold and self._opened_at is None:
            self._opened_at = time.monotonic()
            CIRCUIT_TRIPS.labels(provider=self._provider).inc()


def classify(provider: str, exc: BaseException) -> ProviderError:
    """Map transport and HTTP failures onto a retryable/non-retryable decision."""
    if isinstance(exc, ProviderError):
        return exc
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return ProviderError(
            provider,
            f"{provider} returned {status}",
            status_code=status,
            retryable=status in RETRYABLE_STATUS,
        )
    if isinstance(exc, httpx.TimeoutException | httpx.TransportError):
        return ProviderError(provider, f"{provider} transport error: {exc}", retryable=True)
    return ProviderError(provider, f"{provider} call failed: {exc}")


def retry_after_seconds(exc: BaseException) -> float | None:
    """Honour an explicit Retry-After rather than guessing a backoff."""
    if not isinstance(exc, httpx.HTTPStatusError):
        return None
    raw = exc.response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


class ProviderHarness:
    """Retry + circuit breaker + deadline enforcement for a single provider."""

    def __init__(
        self,
        provider: str,
        *,
        policy: RetryPolicy | None = None,
        failure_threshold: int = 5,
        reset_seconds: float = 30.0,
    ) -> None:
        self.provider = provider
        self._policy = policy or RetryPolicy()
        self._breaker = CircuitBreaker(
            provider, failure_threshold=failure_threshold, reset_seconds=reset_seconds
        )

    @property
    def policy(self) -> RetryPolicy:
        return self._policy

    @property
    def breaker(self) -> CircuitBreaker:
        return self._breaker

    async def call(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        stage: str = "call",
        deadline: Deadline | None = None,
    ) -> T:
        self._breaker.before()
        last: ProviderError | None = None
        for attempt in range(self._policy.max_attempts):
            if deadline is not None:
                deadline.check(self.provider, stage)
            try:
                result = await operation()
            except Exception as exc:  # noqa: BLE001 - normalised by classify()
                error = classify(self.provider, exc)
                last = error
                if not error.retryable or attempt == self._policy.max_attempts - 1:
                    self._breaker.record_failure()
                    raise error from exc
                reason = str(error.status_code) if error.status_code else "transport"
                RETRIES.labels(provider=self.provider, reason=reason).inc()
                delay = retry_after_seconds(exc) or self._policy.backoff(attempt)
                if deadline is not None and delay >= deadline.remaining:
                    self._breaker.record_failure()
                    raise DeadlineExceeded(
                        self.provider, f"retry backoff would exceed deadline in {stage}"
                    ) from exc
                await asyncio.sleep(delay)
            else:
                self._breaker.record_success()
                return result
        raise last or ProviderError(self.provider, "retry loop exhausted")


def harness_from_settings(provider: str, settings: object) -> ProviderHarness:
    """Build a harness using the shared retry/breaker settings."""
    return ProviderHarness(
        provider,
        policy=RetryPolicy(
            max_attempts=int(getattr(settings, "retry_max_attempts", 3)),
            initial_backoff=float(getattr(settings, "retry_initial_backoff_seconds", 0.25)),
            max_backoff=float(getattr(settings, "retry_max_backoff_seconds", 4.0)),
        ),
        failure_threshold=int(getattr(settings, "circuit_breaker_failures", 5)),
        reset_seconds=float(getattr(settings, "circuit_breaker_reset_seconds", 30.0)),
    )
