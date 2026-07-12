"""Hermetic tests for POST /api/v1/agent/voice (ADR-0036/0037).

All external I/O is mocked. `run_voice_turn` itself is mocked for these
route-level tests — its own logic is exhaustively tested in
test_voice_pipeline.py; here we test the route's own concerns: the
feature flag, the size cap, rate limiting, response shape, and the
residents-only gate.
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

from sport_slot.dependencies import get_firestore_client, get_lock_service, get_redis_client
from sport_slot.services.voice.voice_pipeline import VoiceTurn

RESIDENT_CLAIMS = {
    "uid": "u1", "role": "resident",
    "tenant_id": "t-1", "tenant_slug": "demo", "household_id": "h-1",
}
ADMIN_CLAIMS = {
    "uid": "u-admin", "role": "tenant_admin",
    "tenant_id": "t-1", "tenant_slug": "demo", "household_id": "h-1",
}
AUTH = {"authorization": "Bearer fake"}
HOST = {"host": "demo.slotsense.chandraailabs.com"}
VERIFY = "sport_slot.auth.dependency.fb_auth.verify_id_token"
RUN_VOICE_TURN = "sport_slot.api.v1.voice.run_voice_turn"

URL = "/api/v1/agent/voice"
_SMALL_AUDIO = b"RIFF....WAVEfmt "  # tiny placeholder, never actually decoded in these tests


def _files(content: bytes = _SMALL_AUDIO):
    return {"audio": ("clip.wav", content, "audio/wav")}


def _override_deps(app):
    app.dependency_overrides[get_firestore_client] = lambda: MagicMock()
    app.dependency_overrides[get_redis_client] = lambda: AsyncMock()
    app.dependency_overrides[get_lock_service] = lambda: MagicMock()


# ---------------------------------------------------------------------------
# Feature flag — default off, behaves as if the route does not exist
# ---------------------------------------------------------------------------


async def test_flag_off_by_default_returns_404(make_client):
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client() as client:
            _override_deps(client._transport.app)
            resp = await client.post(URL, files=_files(), headers={**AUTH, **HOST})

    assert resp.status_code == 404


async def test_flag_explicitly_off_returns_404(make_client):
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client({"SPORTSLOT_VOICE_ENABLED": "false"}) as client:
            _override_deps(client._transport.app)
            resp = await client.post(URL, files=_files(), headers={**AUTH, **HOST})

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Size cap — 413 before any pipeline work
# ---------------------------------------------------------------------------


async def test_oversized_audio_returns_413(make_client):
    oversized = b"x" * 100
    with patch(VERIFY, return_value=RESIDENT_CLAIMS), patch(RUN_VOICE_TURN) as mock_turn:
        async with make_client(
            {"SPORTSLOT_VOICE_ENABLED": "true", "SPORTSLOT_VOICE_MAX_AUDIO_BYTES": "10"}
        ) as client:
            _override_deps(client._transport.app)
            resp = await client.post(URL, files=_files(oversized), headers={**AUTH, **HOST})

    assert resp.status_code == 413
    assert resp.json()["code"] == "PAYLOAD_TOO_LARGE"
    mock_turn.assert_not_called()  # rejected before any pipeline work


# ---------------------------------------------------------------------------
# Happy path — 200 with the full response shape
# ---------------------------------------------------------------------------


async def test_happy_path_returns_full_response_shape(make_client):
    fake_turn = VoiceTurn(
        transcript="book tennis tomorrow",
        reply_text="Booked Tennis Court 1.",
        reply_audio=b"fake-mp3-bytes",
        reply_audio_mime="audio/mpeg",
        pending_action_id=None,
        pending_action_summary=None,
        decision=None,
    )
    with (
        patch(VERIFY, return_value=RESIDENT_CLAIMS),
        patch(RUN_VOICE_TURN, new_callable=AsyncMock, return_value=fake_turn),
    ):
        async with make_client({"SPORTSLOT_VOICE_ENABLED": "true"}) as client:
            _override_deps(client._transport.app)
            resp = await client.post(URL, files=_files(), headers={**AUTH, **HOST})

    assert resp.status_code == 200
    body = resp.json()
    assert body["transcript"] == "book tennis tomorrow"
    assert body["reply_text"] == "Booked Tennis Court 1."
    assert body["reply_audio"] == base64.b64encode(b"fake-mp3-bytes").decode("ascii")
    assert body["reply_audio_mime"] == "audio/mpeg"
    assert body["pending_action_id"] is None
    assert body["pending_action_summary"] is None
    assert body["decision"] is None


async def test_happy_path_with_null_audio_encodes_as_null(make_client):
    """TTS-degraded turns (reply_audio=None) must serialize as JSON null,
    never an empty/invalid base64 string."""
    fake_turn = VoiceTurn(
        transcript="book tennis tomorrow", reply_text="Booked Tennis Court 1.",
        reply_audio=None, reply_audio_mime=None,
        pending_action_id=None, pending_action_summary=None, decision=None,
    )
    with (
        patch(VERIFY, return_value=RESIDENT_CLAIMS),
        patch(RUN_VOICE_TURN, new_callable=AsyncMock, return_value=fake_turn),
    ):
        async with make_client({"SPORTSLOT_VOICE_ENABLED": "true"}) as client:
            _override_deps(client._transport.app)
            resp = await client.post(URL, files=_files(), headers={**AUTH, **HOST})

    assert resp.status_code == 200
    assert resp.json()["reply_audio"] is None
    assert resp.json()["reply_audio_mime"] is None


async def test_confirm_turn_passes_pending_action_id_through(make_client):
    fake_turn = VoiceTurn(
        transcript="yes", reply_text="Booked!", reply_audio=None, reply_audio_mime=None,
        pending_action_id=None, pending_action_summary=None, decision="affirm",
    )
    with (
        patch(VERIFY, return_value=RESIDENT_CLAIMS),
        patch(RUN_VOICE_TURN, new_callable=AsyncMock, return_value=fake_turn) as mock_turn,
    ):
        async with make_client({"SPORTSLOT_VOICE_ENABLED": "true"}) as client:
            _override_deps(client._transport.app)
            resp = await client.post(
                URL, files=_files(), data={"pending_action_id": "pa-123"},
                headers={**AUTH, **HOST},
            )

    assert resp.status_code == 200
    assert resp.json()["decision"] == "affirm"
    call_args = mock_turn.call_args.args
    assert call_args[-1] == "pa-123"


# ---------------------------------------------------------------------------
# Residents-only gate
# ---------------------------------------------------------------------------


async def test_non_resident_blocked_with_403(make_client):
    with patch(VERIFY, return_value=ADMIN_CLAIMS):
        async with make_client({"SPORTSLOT_VOICE_ENABLED": "true"}) as client:
            _override_deps(client._transport.app)
            resp = await client.post(URL, files=_files(), headers={**AUTH, **HOST})

    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN_ROLE"


# ---------------------------------------------------------------------------
# Rate limiting — inherits the app-wide default limiter (same mechanism
# already proven for /api/v1/users/me), no bespoke per-route limiter added.
# ---------------------------------------------------------------------------


async def test_rate_limit_429(make_client):
    fake_turn = VoiceTurn(
        transcript="hi", reply_text="Hello!", reply_audio=None, reply_audio_mime=None,
        pending_action_id=None, pending_action_summary=None, decision=None,
    )
    with (
        patch(VERIFY, return_value=RESIDENT_CLAIMS),
        patch(RUN_VOICE_TURN, new_callable=AsyncMock, return_value=fake_turn),
    ):
        async with make_client(
            {"SPORTSLOT_VOICE_ENABLED": "true", "SPORTSLOT_RATE_LIMIT": "2/minute"}
        ) as client:
            _override_deps(client._transport.app)
            r1 = await client.post(URL, files=_files(), headers={**AUTH, **HOST})
            r2 = await client.post(URL, files=_files(), headers={**AUTH, **HOST})
            r3 = await client.post(URL, files=_files(), headers={**AUTH, **HOST})

    assert r1.status_code == 200 and r2.status_code == 200
    assert r3.status_code == 429
    assert r3.json()["code"] == "RATE_LIMITED"
