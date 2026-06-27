"""Generic single-use pending action store — Redis-backed, tenant+uid scoped.

Key format:  agent_pending:{tenant_id}:{uid}:{action_id}
Latest ptr:  agent_pending_latest:{tenant_id}:{uid}:{action_type}

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

    @staticmethod
    def _latest_key(ctx: TenantContext, action_type: str) -> str:
        return f"agent_pending_latest:{ctx.tenant_id}:{ctx.uid}:{action_type}"

    async def propose(self, ctx: TenantContext, action_type: str, params: dict) -> str:
        """Write a pending action; returns the action_id. Raises on Redis error."""
        action_id = uuid.uuid4().hex
        key = self._key(ctx, action_id)
        payload = json.dumps({"action_type": action_type, "params": params})
        await self._redis.set(key, payload, px=_TTL_MS)
        # Secondary pointer so get_latest_for_user can find this by type without the action_id
        latest_key = self._latest_key(ctx, action_type)
        await self._redis.set(latest_key, action_id, px=_TTL_MS)
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

    async def get_latest_for_user(
        self, ctx: TenantContext, action_type: str
    ) -> tuple[str, dict] | None:
        """Return (action_id, action_data) for the most recent action of this type.

        Does NOT consume. Caller must call consume() explicitly to single-use it.
        Returns None if no such action exists, is expired, or on Redis error.
        """
        latest_key = self._latest_key(ctx, action_type)
        try:
            action_id_val = await self._redis.get(latest_key)
            if action_id_val is None:
                return None
            action_id = (
                action_id_val.decode()
                if isinstance(action_id_val, bytes)
                else action_id_val
            )
            val = await self._redis.get(self._key(ctx, action_id))
            if val is None:
                return None
            return action_id, json.loads(val)
        except Exception as exc:
            log.warning("pending_action_get_latest_error", error=str(exc))
            return None
