"""Distributed slot lock — Redis SET NX PX (ADR-0009).

Fail Closed: Redis unreachable raises LockUnavailableError (503 at
the route), never bypasses. Release is owner-checked via Lua so a
client whose lock TTL-expired cannot delete a successor's lock.
"""

import uuid

from redis import exceptions as redis_exceptions

_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
else
  return 0
end
"""


class LockUnavailableError(Exception):
    pass


class LockService:
    def __init__(self, client):
        self._client = client

    @staticmethod
    def slot_key(tenant_id: str, facility_id: str, date: str, start: str) -> str:
        return f"lock:{tenant_id}:{facility_id}:{date}:{start}"

    async def acquire(self, key: str, ttl_ms: int = 10_000) -> str | None:
        """Returns an owner token, or None if the lock is held."""
        token = uuid.uuid4().hex
        try:
            ok = await self._client.set(key, token, nx=True, px=ttl_ms)
        except (redis_exceptions.RedisError, OSError) as exc:
            raise LockUnavailableError(str(exc)) from exc
        return token if ok else None

    async def release(self, key: str, token: str) -> None:
        """Best-effort owner-checked release; TTL covers failures."""
        try:
            await self._client.eval(_RELEASE_LUA, 1, key, token)
        except (redis_exceptions.RedisError, OSError):
            pass
