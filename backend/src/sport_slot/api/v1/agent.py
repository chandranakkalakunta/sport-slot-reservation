"""Read-only AI query agent endpoint (ADR-0021 §2).

Residents-only. Single-turn. No booking or cancel capability.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sport_slot.auth.context import TenantContext
from sport_slot.auth.roles import require_role
from sport_slot.dependencies import get_firestore_client
from sport_slot.services.agent.orchestrator import run_agent

router = APIRouter(prefix="/agent", tags=["agent"])
log = structlog.get_logger()


class AgentQuery(BaseModel):
    message: str


class AgentReply(BaseModel):
    reply: str


@router.post("/query", response_model=AgentReply)
async def agent_query(
    body: AgentQuery,
    ctx: TenantContext = Depends(require_role("resident")),
    client=Depends(get_firestore_client),
) -> AgentReply:
    reply = await run_agent(ctx, client, body.message)
    return AgentReply(reply=reply)
