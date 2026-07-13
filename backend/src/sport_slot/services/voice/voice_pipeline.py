"""Voice turn orchestrator — the full audio-in/audio-out pipeline.

ADR-0036 D1, English-only per ADR-0037: audio → STT(en-IN) → [confirm
guard | run_agent] → TTS(en-IN) → audio. Translation legs and per-tenant
language configuration (ADR-0037 D3′) are deferred to the future
multi-language sub-phase — this module already routes every language
decision through `resolve_tenant_voice_languages`, so only that resolver
changes later.

`run_agent` / `run_agent_confirm` (services/agent/orchestrator.py) are
called exactly as the text agent calls them — this module adds no new
agent behavior, only a new edge in front of the same, unmodified text
pipeline (ADR-0036 D1).

Safety-critical: the confirmation branch never calls Vertex/an LLM to
interpret yes/no. It is deterministic end-to-end (ADR-0036 D2, ADR-0037
D2′) and fails closed (AMBIGUOUS) on any doubt.
"""

from __future__ import annotations

from typing import Any, NamedTuple

import structlog

from sport_slot.auth.context import TenantContext
from sport_slot.services.agent.orchestrator import run_agent, run_agent_confirm
from sport_slot.services.agent.pending_actions import PendingActionStore
from sport_slot.services.lock import LockService
from sport_slot.services.voice.confirm_guard import ConfirmDecision, classify_confirmation
from sport_slot.services.voice.languages import resolve_tenant_voice_languages
from sport_slot.services.voice.stt import SttError, transcribe
from sport_slot.services.voice.tts import TtsError, synthesize

log = structlog.get_logger()

_DIDNT_CATCH_TEXT = "Sorry, I didn't catch that."
_CANCELLED_TEXT = "Okay, cancelled."
_PLEASE_CONFIRM_TEXT = "Please say yes or no to confirm."


class VoiceTurn(NamedTuple):
    transcript: str
    reply_text: str
    reply_audio: bytes | None
    reply_audio_mime: str | None
    pending_action_id: str | None
    pending_action_summary: dict | None
    decision: str | None


def _bcp47_to_2letter(code: str) -> str:
    return code.split("-")[0].lower()


def combine_confirm_decisions(transcript: str, languages: list[str]) -> ConfirmDecision:
    """ADR-0037 D2′ — the confirm turn checks ALL of the tenant's configured
    languages' lexicons, not only the one language STT detected.

    Auto-detect can mislabel among a tenant's own languages, and the
    confirm decision must not depend on that guess. `languages` are
    2-letter codes (e.g. "en", "hi"). Decision:

      any AFFIRM and no DENY -> AFFIRM
      any DENY and no AFFIRM -> DENY
      otherwise (both, or neither) -> AMBIGUOUS (fail-closed)
    """
    decisions = [classify_confirmation(transcript, lang) for lang in languages]
    has_affirm = ConfirmDecision.AFFIRM in decisions
    has_deny = ConfirmDecision.DENY in decisions
    if has_affirm and not has_deny:
        return ConfirmDecision.AFFIRM
    if has_deny and not has_affirm:
        return ConfirmDecision.DENY
    return ConfirmDecision.AMBIGUOUS


async def run_voice_turn(
    ctx: TenantContext,
    client: Any,  # Firestore client — untyped here deliberately, ADR-0008 Decision 3:
    # the repository layer is the only place allowed to import that SDK directly
    lock: LockService,
    store: PendingActionStore,
    audio_bytes: bytes,
    pending_action_id: str | None,
) -> VoiceTurn:
    """Execute one full voice turn. Never raises — degrades gracefully at
    every stage (STT failure, empty transcript, TTS failure) rather than
    failing the whole request.
    """
    languages = resolve_tenant_voice_languages(ctx)

    try:
        stt_result = transcribe(audio_bytes, languages)
        transcript = stt_result.transcript
        log.info(
            "voice_stt_result",
            outcome="ok" if transcript.strip() else "empty",
            transcript_chars=len(transcript),
            detected_language=stt_result.raw_language,
        )
    except SttError as exc:
        log.warning("voice_stt_result", outcome="error", error=str(exc))
        transcript = ""

    decision: str | None = None
    new_pending_id = pending_action_id
    new_summary: dict | None = None

    if not transcript.strip():
        # Empty/garbled transcript: never guess. If a confirmation was in
        # progress, leave it exactly as it was — still awaiting a real answer.
        reply_text = _DIDNT_CATCH_TEXT
    elif pending_action_id:
        # CONFIRM TURN — deterministic, no Vertex call (ADR-0036 D2, D2′).
        two_letter_langs = [_bcp47_to_2letter(lang) for lang in languages]
        decision_enum = combine_confirm_decisions(transcript, two_letter_langs)
        decision = decision_enum.value

        if decision_enum is ConfirmDecision.AFFIRM:
            reply_text = await run_agent_confirm(ctx, client, lock, store, pending_action_id)
            new_pending_id = None
        elif decision_enum is ConfirmDecision.DENY:
            # Abandon, no mutation. No new delete path: the pending action
            # expires on its own via its existing ADR-0025 TTL.
            reply_text = _CANCELLED_TEXT
            new_pending_id = None
        else:
            reply_text = _PLEASE_CONFIRM_TEXT
            new_pending_id = pending_action_id  # keep alive, re-prompt
    else:
        # NORMAL TURN — English in, English out, no translation.
        turn = await run_agent(ctx, client, store, transcript, None)
        reply_text = turn.reply
        new_pending_id = turn.pending_action_id
        new_summary = turn.pending_action_summary

    try:
        reply_audio, reply_audio_mime = synthesize(reply_text, "en-IN")
    except TtsError as exc:
        log.warning("voice_turn_tts_error", error=str(exc))
        reply_audio, reply_audio_mime = None, None

    return VoiceTurn(
        transcript=transcript,
        reply_text=reply_text,
        reply_audio=reply_audio,
        reply_audio_mime=reply_audio_mime,
        pending_action_id=new_pending_id,
        pending_action_summary=new_summary,
        decision=decision,
    )
