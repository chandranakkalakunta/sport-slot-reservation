"""Generic single-use pending action store — Redis-backed, tenant+uid scoped.

Key format: agent_pending:{tenant_id}:{uid}:{action_id}
Scope enforcement is by key construction: a resident cannot consume another
resident's pending action (wrong uid → different key → cache miss).

ADR-0021 §4 / ADR-0022 §5.
"""

from __future__ import annotations

import json
import uuid

import structlog

from sport_slot.auth.context import TenantContext

log = structlog.get_logger()

_TTL_MS = 300_000  # 5 minutes


class PendingActionStore:
    def __init__(self, redis_client):
        self._redis = redis_client

    @staticmethod
    def _key(ctx: TenantContext, action_id: str) -> str:
        return f"agent_pending:{ctx.tenant_id}:{ctx.uid}:{action_id}"

    async def propose(self, ctx: TenantContext, action_type: str, params: dict) -> str:
        """Write a pending action; returns the action_id. Raises on Redis error."""
        action_id = uuid.uuid4().hex
        key = self._key(ctx, action_id)
        payload = json.dumps({"action_type": action_type, "params": params})
        await self._redis.set(key, payload, px=_TTL_MS)
        return action_id

    async def consume(self, ctx: TenantContext, action_id: str) -> dict | None:
        """Read-and-delete (single-use). Returns None if missing/expired/error."""
        key = self._key(ctx, action_id)
        try:
            val = await self._redis.get(key)
            if val is None:
                return None
            await self._redis.delete(key)
            return json.loads(val)
        except Exception as exc:
            log.warning("pending_action_consume_error", error=str(exc))
            return None
