"""Tests for bounded request and concurrency admission."""

import pytest

from app.limits import ConcurrencyGate, ConcurrencyLimitError, SlidingWindowRateLimiter


def test_sliding_window_returns_retry_after_and_expires_old_requests():
    limiter = SlidingWindowRateLimiter(2, 10)
    assert limiter.allow("scope", now=100).allowed
    assert limiter.allow("scope", now=101).allowed
    denied = limiter.allow("scope", now=102)
    assert denied.allowed is False
    assert denied.retry_after_seconds == 8
    assert limiter.allow("scope", now=111).allowed


def test_rate_limiter_bounds_key_memory():
    limiter = SlidingWindowRateLimiter(1, 10, max_keys=2)
    limiter.allow("one", now=1)
    limiter.allow("two", now=1)
    limiter.allow("three", now=1)
    assert len(limiter._windows) == 2


def test_concurrency_gate_releases_slots_on_context_exit():
    gate = ConcurrencyGate(1)
    with gate.slot("scope"):
        with pytest.raises(ConcurrencyLimitError):
            gate.acquire("scope")
    gate.acquire("scope")
    gate.release("scope")
