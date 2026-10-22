"""Tests for bounded async execution."""

import asyncio
import time

import pytest

from app.errors import ErrorCode, ServiceError
from app.execution import TimeoutPolicy, remaining_seconds, run_with_timeout


def test_remaining_seconds_uses_default_monotonic_clock(monkeypatch):
    monkeypatch.setattr(time, "monotonic", lambda: 100.0)
    assert remaining_seconds(110) == 10
    assert remaining_seconds(90) == 0


def test_remaining_seconds_uses_real_monotonic_clock():
    assert 0 < remaining_seconds(time.monotonic() + 5) <= 5


def test_timeout_policy_and_remaining_budget():
    policy = TimeoutPolicy()
    assert policy.task_seconds > policy.operation_seconds
    assert remaining_seconds(110, now=100) == 10
    assert remaining_seconds(90, now=100) == 0


def test_async_operation_completes_within_budget():
    async def operation():
        await asyncio.sleep(0)
        return "done"

    assert asyncio.run(run_with_timeout(operation, 1)) == "done"


def test_async_timeout_maps_to_safe_service_error_without_retry():
    async def operation():
        await asyncio.sleep(0.05)
        return "late"

    with pytest.raises(ServiceError) as error:
        asyncio.run(run_with_timeout(operation, 0.001))
    assert error.value.code == ErrorCode.TIMEOUT
