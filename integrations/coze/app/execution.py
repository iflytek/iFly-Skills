"""Bounded asynchronous execution helpers shared by Skill adapters."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

from .errors import ErrorCode, ServiceError


T = TypeVar("T")

# A media call includes downloading, provider work/uploads, and artifact publication.
MEDIA_DOWNLOAD_TIMEOUT_SECONDS = 180.0
MEDIA_OPERATION_TIMEOUT_SECONDS = 600.0


@dataclass(frozen=True)
class TimeoutPolicy:
    operation_seconds: float = 60.0
    task_seconds: float = 600.0
    lease_seconds: float = 90.0

    def __post_init__(self) -> None:
        if self.operation_seconds <= 0 or self.task_seconds <= 0 or self.lease_seconds <= 0:
            raise ValueError("Execution timeouts must be positive")


def remaining_seconds(deadline: float, *, now: float | None = None) -> float:
    remaining = deadline - (time.monotonic() if now is None else now)
    return max(0.0, remaining)


async def run_with_timeout(operation: Callable[[], Awaitable[T]], timeout_seconds: float) -> T:
    """Run one upstream operation; timeout never triggers an automatic retry."""
    if timeout_seconds <= 0:
        raise ValueError("The operation timeout must be positive")
    try:
        return await asyncio.wait_for(operation(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise ServiceError(ErrorCode.TIMEOUT) from None
