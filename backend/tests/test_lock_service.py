from unittest.mock import AsyncMock

import pytest
from redis import exceptions as redis_exceptions

from sport_slot.services.lock import LockService, LockUnavailableError


async def test_acquire_returns_token():
    client = AsyncMock()
    client.set.return_value = True
    token = await LockService(client).acquire("k")
    assert token
    client.set.assert_awaited_once()
    kwargs = client.set.await_args.kwargs
    assert kwargs["nx"] is True and kwargs["px"] == 10_000


async def test_acquire_contended_returns_none():
    client = AsyncMock()
    client.set.return_value = None
    assert await LockService(client).acquire("k") is None


async def test_acquire_redis_down_raises():
    client = AsyncMock()
    client.set.side_effect = redis_exceptions.ConnectionError("down")
    with pytest.raises(LockUnavailableError):
        await LockService(client).acquire("k")


async def test_release_owner_checked():
    client = AsyncMock()
    await LockService(client).release("k", "tok")
    args = client.eval.await_args.args
    assert "get" in args[0] and args[1] == 1
    assert args[2] == "k" and args[3] == "tok"


async def test_release_swallows_errors():
    client = AsyncMock()
    client.eval.side_effect = redis_exceptions.ConnectionError("down")
    await LockService(client).release("k", "tok")  # no raise


def test_slot_key_format():
    assert LockService.slot_key("t1", "f1", "2026-06-13", "18:00") == \
        "lock:t1:f1:2026-06-13:18:00"
