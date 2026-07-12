"""Hermetic tests for the voice turn orchestrator (ADR-0036/0037).

STT, TTS, run_agent, and run_agent_confirm are all mocked — no real API
calls, no real Vertex/Firestore access. `classify_confirmation` (the
confirm/deny guard) is used FOR REAL: it is a pure, already-unit-tested
deterministic function, and exercising it for real here proves the
pipeline's wiring, not just its mocks.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sport_slot.auth.context import TenantContext
from sport_slot.services.agent.orchestrator import AgentTurn
from sport_slot.services.voice.confirm_guard import ConfirmDecision
from sport_slot.services.voice.stt import SttError, SttResult
from sport_slot.services.voice.tts import TtsError
from sport_slot.services.voice.voice_pipeline import combine_confirm_decisions, run_voice_turn

CTX = TenantContext(uid="u1", tenant_id="t-1", tenant_slug="demo",
                     role="resident", household_id="h-1")

STT = "sport_slot.services.voice.voice_pipeline.transcribe"
TTS = "sport_slot.services.voice.voice_pipeline.synthesize"
RUN_AGENT = "sport_slot.services.voice.voice_pipeline.run_agent"
RUN_AGENT_CONFIRM = "sport_slot.services.voice.voice_pipeline.run_agent_confirm"

_AUDIO = (b"fake-audio", "audio/mpeg")


def _stt_result(transcript: str) -> SttResult:
    return SttResult(
        transcript=transcript, language="en", raw_language="en-IN",
        confidence=0.9, is_supported_language=True,
    )


# ---------------------------------------------------------------------------
# combine_confirm_decisions — the D2' safety core
# ---------------------------------------------------------------------------


def test_combine_affirm_only():
    assert combine_confirm_decisions("yes", ["en"]) == ConfirmDecision.AFFIRM


def test_combine_deny_only():
    assert combine_confirm_decisions("no", ["en"]) == ConfirmDecision.DENY


def test_combine_both_present_single_language_is_ambiguous():
    assert combine_confirm_decisions("yes no", ["en"]) == ConfirmDecision.AMBIGUOUS


def test_combine_neither_present_is_ambiguous():
    assert combine_confirm_decisions("maybe later", ["en"]) == ConfirmDecision.AMBIGUOUS


def test_combine_cross_language_affirm_only():
    """"haan" is Hindi-affirm and ambiguous (no match) in English — combine
    must still resolve to AFFIRM from the language that actually matched,
    not be dragged down by the other language's non-match."""
    assert combine_confirm_decisions("haan", ["en", "hi"]) == ConfirmDecision.AFFIRM


def test_combine_cross_language_conflict_is_ambiguous():
    """The D2' safety property: an utterance that is AFFIRM in one of the
    tenant's languages and DENY in another must fail closed, never guess
    based on which language STT happened to detect."""
    decision = combine_confirm_decisions("yes nahi", ["en", "hi"])
    assert decision == ConfirmDecision.AMBIGUOUS


# ---------------------------------------------------------------------------
# run_voice_turn — normal turn (no pending_action_id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_normal_turn_calls_run_agent_and_synthesizes_reply():
    agent_turn = AgentTurn(reply="Booked Tennis Court 1.", pending_action_id=None,
                            pending_action_summary=None)
    with (
        patch(STT, return_value=_stt_result("book tennis tomorrow")),
        patch(RUN_AGENT, new_callable=AsyncMock, return_value=agent_turn) as mock_run_agent,
        patch(RUN_AGENT_CONFIRM, new_callable=AsyncMock) as mock_confirm,
        patch(TTS, return_value=_AUDIO),
    ):
        turn = await run_voice_turn(CTX, MagicMock(), MagicMock(), MagicMock(), b"audio", None)

    assert turn.transcript == "book tennis tomorrow"
    assert turn.reply_text == "Booked Tennis Court 1."
    assert turn.reply_audio == b"fake-audio"
    assert turn.reply_audio_mime == "audio/mpeg"
    assert turn.pending_action_id is None
    assert turn.decision is None
    mock_run_agent.assert_awaited_once_with(CTX, mock_run_agent.call_args.args[1],
                                             mock_run_agent.call_args.args[2],
                                             "book tennis tomorrow", None)
    mock_confirm.assert_not_awaited()


@pytest.mark.asyncio
async def test_propose_turn_returns_pending_action_and_summary():
    agent_turn = AgentTurn(
        reply="Confirm booking Tennis Court 1 tomorrow at 18:00?",
        pending_action_id="pa-123",
        pending_action_summary={"facility_name": "Tennis Court 1", "date": "2026-07-15"},
    )
    with (
        patch(STT, return_value=_stt_result("book tennis tomorrow at 6pm")),
        patch(RUN_AGENT, new_callable=AsyncMock, return_value=agent_turn),
        patch(TTS, return_value=_AUDIO),
    ):
        turn = await run_voice_turn(CTX, MagicMock(), MagicMock(), MagicMock(), b"audio", None)

    assert turn.pending_action_id == "pa-123"
    assert turn.pending_action_summary == {"facility_name": "Tennis Court 1", "date": "2026-07-15"}
    assert turn.decision is None


# ---------------------------------------------------------------------------
# run_voice_turn — confirm turn: AFFIRM / DENY / AMBIGUOUS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_affirm_calls_run_agent_confirm_and_clears_pending():
    lock = MagicMock()
    store = MagicMock()
    with (
        patch(STT, return_value=_stt_result("yes")),
        patch(RUN_AGENT_CONFIRM, new_callable=AsyncMock,
              return_value="Booked!") as mock_confirm,
        patch(RUN_AGENT, new_callable=AsyncMock) as mock_run_agent,
        patch(TTS, return_value=_AUDIO),
    ):
        turn = await run_voice_turn(CTX, MagicMock(), lock, store, b"audio", "pa-123")

    mock_confirm.assert_awaited_once_with(CTX, mock_confirm.call_args.args[1], lock, store, "pa-123")
    mock_run_agent.assert_not_awaited()
    assert turn.reply_text == "Booked!"
    assert turn.pending_action_id is None
    assert turn.decision == "affirm"


@pytest.mark.asyncio
async def test_confirm_deny_does_not_call_run_agent_confirm_and_clears_pending():
    with (
        patch(STT, return_value=_stt_result("no")),
        patch(RUN_AGENT_CONFIRM, new_callable=AsyncMock) as mock_confirm,
        patch(TTS, return_value=_AUDIO),
    ):
        turn = await run_voice_turn(CTX, MagicMock(), MagicMock(), MagicMock(), b"audio", "pa-123")

    mock_confirm.assert_not_awaited()
    assert turn.reply_text == "Okay, cancelled."
    assert turn.pending_action_id is None
    assert turn.decision == "deny"


@pytest.mark.asyncio
async def test_confirm_ambiguous_reprompts_and_keeps_pending_alive():
    with (
        patch(STT, return_value=_stt_result("yes no")),
        patch(RUN_AGENT_CONFIRM, new_callable=AsyncMock) as mock_confirm,
        patch(TTS, return_value=_AUDIO),
    ):
        turn = await run_voice_turn(CTX, MagicMock(), MagicMock(), MagicMock(), b"audio", "pa-123")

    mock_confirm.assert_not_awaited()
    assert turn.reply_text == "Please say yes or no to confirm."
    assert turn.pending_action_id == "pa-123"  # echoed back, kept alive
    assert turn.decision == "ambiguous"


# ---------------------------------------------------------------------------
# Empty / garbled transcript — never guess
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_transcript_mid_confirm_keeps_pending_and_does_not_guess():
    with (
        patch(STT, return_value=_stt_result("")),
        patch(RUN_AGENT_CONFIRM, new_callable=AsyncMock) as mock_confirm,
        patch(TTS, return_value=_AUDIO),
    ):
        turn = await run_voice_turn(CTX, MagicMock(), MagicMock(), MagicMock(), b"audio", "pa-123")

    mock_confirm.assert_not_awaited()
    assert turn.reply_text == "Sorry, I didn't catch that."
    assert turn.pending_action_id == "pa-123"  # untouched, still awaiting confirm
    assert turn.decision is None


@pytest.mark.asyncio
async def test_empty_transcript_normal_turn_does_not_call_agent():
    with (
        patch(STT, return_value=_stt_result("   ")),
        patch(RUN_AGENT, new_callable=AsyncMock) as mock_run_agent,
        patch(TTS, return_value=_AUDIO),
    ):
        turn = await run_voice_turn(CTX, MagicMock(), MagicMock(), MagicMock(), b"audio", None)

    mock_run_agent.assert_not_awaited()
    assert turn.reply_text == "Sorry, I didn't catch that."
    assert turn.pending_action_id is None
    assert turn.decision is None


@pytest.mark.asyncio
async def test_stt_error_degrades_like_empty_transcript():
    with (
        patch(STT, side_effect=SttError("api down")),
        patch(RUN_AGENT, new_callable=AsyncMock) as mock_run_agent,
        patch(TTS, return_value=_AUDIO),
    ):
        turn = await run_voice_turn(CTX, MagicMock(), MagicMock(), MagicMock(), b"audio", None)

    mock_run_agent.assert_not_awaited()
    assert turn.transcript == ""
    assert turn.reply_text == "Sorry, I didn't catch that."


# ---------------------------------------------------------------------------
# TTS failure degrades to text-only — the turn itself still succeeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tts_failure_degrades_to_text_only():
    agent_turn = AgentTurn(reply="Booked Tennis Court 1.", pending_action_id=None,
                            pending_action_summary=None)
    with (
        patch(STT, return_value=_stt_result("book tennis tomorrow")),
        patch(RUN_AGENT, new_callable=AsyncMock, return_value=agent_turn),
        patch(TTS, side_effect=TtsError("tts down")),
    ):
        turn = await run_voice_turn(CTX, MagicMock(), MagicMock(), MagicMock(), b"audio", None)

    assert turn.reply_text == "Booked Tennis Court 1."
    assert turn.reply_audio is None
    assert turn.reply_audio_mime is None
