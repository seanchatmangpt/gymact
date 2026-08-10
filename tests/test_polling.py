"""Chicago-style tests for `gymact.polling.poll_until`/`poll_until_async`.

Real `time.monotonic()` timing throughout, no mocked clock: each test uses real
short (0.1-0.4s) timeouts/intervals and asserts on the real elapsed wall time and
the real returned boolean/call-count state -- never an interaction-based
assertion like "was `time.sleep` called."
"""

from __future__ import annotations

import asyncio
import time

from gymact.polling import poll_until, poll_until_async


def test_poll_until_returns_true_when_condition_becomes_true_before_deadline() -> None:
    calls: list[float] = []

    def _condition() -> bool:
        calls.append(time.monotonic())
        return len(calls) >= 3

    start = time.monotonic()
    result = poll_until(_condition, timeout_seconds=2.0, interval_seconds=0.05)
    elapsed = time.monotonic() - start

    assert result is True
    assert len(calls) == 3
    # Real wall-clock bound: became true on the 3rd check (2 sleeps of 0.05s),
    # well under the 2.0s timeout -- proves it did not wait for the deadline.
    assert elapsed < 1.0


def test_poll_until_returns_false_on_real_timeout() -> None:
    calls: list[float] = []

    def _condition() -> bool:
        calls.append(time.monotonic())
        return False

    start = time.monotonic()
    result = poll_until(_condition, timeout_seconds=0.2, interval_seconds=0.05)
    elapsed = time.monotonic() - start

    assert result is False
    # Real deadline respected: elapsed time is close to, but not wildly past,
    # the requested 0.2s timeout.
    assert 0.2 <= elapsed < 1.0
    # Multiple real checks happened (initial + at least one retry).
    assert len(calls) >= 2


def test_poll_until_calls_condition_at_least_once_even_with_zero_timeout() -> None:
    calls: list[float] = []

    def _condition() -> bool:
        calls.append(time.monotonic())
        return False

    result = poll_until(_condition, timeout_seconds=0.0, interval_seconds=0.05)

    assert result is False
    assert len(calls) == 1


def test_poll_until_propagates_a_real_exception_from_condition() -> None:
    class _Boom(RuntimeError):
        pass

    def _condition() -> bool:
        raise _Boom("condition failed for real")

    try:
        poll_until(_condition, timeout_seconds=1.0, interval_seconds=0.05)
    except _Boom as exc:
        assert "condition failed for real" in str(exc)
    else:
        raise AssertionError("expected poll_until to propagate the real exception")


async def test_poll_until_async_returns_true_when_condition_becomes_true() -> None:
    calls: list[float] = []

    async def _condition() -> bool:
        calls.append(time.monotonic())
        await asyncio.sleep(0)  # real awaited hop, not a mock
        return len(calls) >= 3

    start = time.monotonic()
    result = await poll_until_async(_condition, timeout_seconds=2.0, interval_seconds=0.05)
    elapsed = time.monotonic() - start

    assert result is True
    assert len(calls) == 3
    assert elapsed < 1.0


async def test_poll_until_async_returns_false_on_real_timeout() -> None:
    calls: list[float] = []

    async def _condition() -> bool:
        calls.append(time.monotonic())
        return False

    start = time.monotonic()
    result = await poll_until_async(_condition, timeout_seconds=0.2, interval_seconds=0.05)
    elapsed = time.monotonic() - start

    assert result is False
    assert 0.2 <= elapsed < 1.0
    assert len(calls) >= 2
