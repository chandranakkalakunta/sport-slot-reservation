"""Voice agent endpoint — audio in, audio out (ADR-0036, ADR-0037).

Residents-only. English-only for this sub-phase (1c) — translation and
per-tenant language configuration are staged behind
services/voice/languages.py for a future multi-language sub-phase.

Feature-flagged, default OFF: when `SPORTSLOT_VOICE_ENABLED` is not set
(or false), this endpoint behaves as if it does not exist (404) — no
existing route (`/agent/query`) is changed by this file at all.

Propose:  POST /agent/voice  multipart(audio)
            → { transcript, reply_text, reply_audio, reply_audio_mime,
                pending_action_id, pending_action_summary, decision }
Confirm:  POST /agent/voice  multipart(audio, pending_action_id)
            → same shape; `decision` is one of "affirm"/"deny"/"ambiguous"
"""

from __future__ import annotations

import base64

import structlog
from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.auth.roles import require_role
from sport_slot.config import get_settings
from sport_slot.dependencies import get_firestore_client, get_lock_service, get_redis_client
from sport_slot.services.agent.pending_actions import PendingActionStore
from sport_slot.services.lock import LockService
from sport_slot.services.voice.voice_pipeline import run_voice_turn

router = APIRouter(prefix="/agent", tags=["agent", "voice"])
log = structlog.get_logger()


class VoiceReply(BaseModel):
    transcript: str
    reply_text: str
    reply_audio: str | None = None
    reply_audio_mime: str | None = None
    pending_action_id: str | None = None
    pending_action_summary: dict | None = None
    decision: str | None = None


@router.post("/voice", response_model=VoiceReply)
async def agent_voice(
    audio: UploadFile = File(...),
    pending_action_id: str | None = Form(None),
    ctx: TenantContext = Depends(require_role("resident")),
    client=Depends(get_firestore_client),
    lock: LockService = Depends(get_lock_service),
    redis=Depends(get_redis_client),
) -> VoiceReply:
    settings = get_settings()
    if not settings.voice_enabled:
        # Behave as if this route does not exist while the feature is off.
        raise ApiError(404, error_codes.NOT_FOUND, "Not found")

    audio_bytes = await audio.read()
    if len(audio_bytes) > settings.voice_max_audio_bytes:
        log.warning(
            "voice_turn_audio_too_large",
            size_bytes=len(audio_bytes),
            limit_bytes=settings.voice_max_audio_bytes,
        )
        raise ApiError(413, error_codes.PAYLOAD_TOO_LARGE, "Audio file too large")

    store = PendingActionStore(redis)
    turn = await run_voice_turn(ctx, client, lock, store, audio_bytes, pending_action_id)

    reply_audio_b64 = (
        base64.b64encode(turn.reply_audio).decode("ascii")
        if turn.reply_audio is not None
        else None
    )

    return VoiceReply(
        transcript=turn.transcript,
        reply_text=turn.reply_text,
        reply_audio=reply_audio_b64,
        reply_audio_mime=turn.reply_audio_mime,
        pending_action_id=turn.pending_action_id,
        pending_action_summary=turn.pending_action_summary,
        decision=turn.decision,
    )
