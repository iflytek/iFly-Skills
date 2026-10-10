"""Small bounded local limiters for request and worker admission."""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
import threading
import time
from typing import Hashable


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: float = 0.0


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float, *, max_keys: int = 10000):
        if max_requests <= 0 or window_seconds <= 0 or max_keys <= 0:
            raise ValueError("Rate-limit values must be positive")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._windows: OrderedDict[Hashable, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def allow(self, key: Hashable, *, now: float | None = None) -> RateLimitDecision:
        timestamp = time.monotonic() if now is None else now
        with self._lock:
            window = self._windows.setdefault(key, deque())
            self._windows.move_to_end(key)
            while window and window[0] <= timestamp - self.window_seconds:
                window.popleft()
            if len(window) >= self.max_requests:
                return RateLimitDecision(False, max(0.0, window[0] + self.window_seconds - timestamp))
            window.append(timestamp)
            while len(self._windows) > self.max_keys:
                self._windows.popitem(last=False)
            return RateLimitDecision(True)


class ConcurrencyLimitError(RuntimeError):
    """No worker slot is available for this scope."""


class ConcurrencyGate:
    def __init__(self, maximum: int):
        if maximum <= 0:
            raise ValueError("Concurrency limit must be positive")
        self.maximum = maximum
        self._active: dict[Hashable, int] = {}
        self._lock = threading.Lock()

    def acquire(self, key: Hashable) -> None:
        with self._lock:
            active = self._active.get(key, 0)
            if active >= self.maximum:
                raise ConcurrencyLimitError("The concurrency limit has been reached.")
            self._active[key] = active + 1

    def release(self, key: Hashable) -> None:
        with self._lock:
            active = self._active.get(key, 0)
            if active <= 1:
                self._active.pop(key, None)
            else:
                self._active[key] = active - 1

    def slot(self, key: Hashable):
        gate = self

        class _Slot:
            def __enter__(self):
                gate.acquire(key)
                return self

            def __exit__(self, exc_type, exc, tb):
                gate.release(key)

        return _Slot()
