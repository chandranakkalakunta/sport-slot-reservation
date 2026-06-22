"""Agent endpoint — propose (read + book intent) and execute (confirm) paths.

Residents-only. Single-turn per request. ADR-0021 §4, ADR-0022 §5/§8.

Propose:  POST /agent/query  { message: str }
            → { reply: str, pending_action_id: str | null }
Execute:  POST /agent/query  { confirm: true, pending_action_id: str }
            → { reply: str }
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sport_slot.auth.context import TenantContext
from sport_slot.auth.roles import require_role
from sport_slot.dependencies import get_firestore_client, get_lock_service, get_redis_client
from sport_slot.services.agent.orchestrator import run_agent, run_agent_confirm
from sport_slot.services.agent.pending_actions import PendingActionStore
from sport_slot.services.lock import LockService

router = APIRouter(prefix="/agent", tags=["agent"])
log = structlog.get_logger()


class AgentRequest(BaseModel):
    message: str | None = None
    confirm: bool = False
    pending_action_id: str | None = None


class AgentReply(BaseModel):
    reply: str
    pending_action_id: str | None = None


@router.post("/query", response_model=AgentReply)
async def agent_query(
    body: AgentRequest,
    ctx: TenantContext = Depends(require_role("resident")),
    client=Depends(get_firestore_client),
    lock: LockService = Depends(get_lock_service),
    redis=Depends(get_redis_client),
) -> AgentReply:
    store = PendingActionStore(redis)

    if body.confirm and body.pending_action_id:
        reply = await run_agent_confirm(ctx, client, lock, store, body.pending_action_id)
        return AgentReply(reply=reply)

    if body.message:
        turn = await run_agent(ctx, client, store, body.message)
        return AgentReply(reply=turn.reply, pending_action_id=turn.pending_action_id)

    return AgentReply(reply="Please send a message or confirm a pending action.")
