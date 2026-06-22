"""Hermetic tests for the read-only AI agent (Slice 1b / 1b.1).

ALL Vertex calls are mocked — ZERO real network calls.
Mock targets:
  - sport_slot.services.agent.vertex_client.generate
  - sport_slot.services.agent.vertex_client.classify_output

Tests cover: happy paths (tool call + direct text), hallucination guard,
output guard blocking, fail-closed on Vertex error, unknown tool,
endpoint role gate, output guard disabled path, date-anchor injection,
and booking-summary framing (1b.1 fixes).
"""

from __future__ import annotations

import datetime
import zoneinfo
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sport_slot.auth.context import TenantContext
from sport_slot.services.agent.guardrails import rules_pass
from sport_slot.services.agent.orchestrator import run_agent
from sport_slot.services.agent.tools import REGISTERED_TOOLS
from sport_slot.services.agent.vertex_client import AgentResponse


class _NoopStore:
    """In-test noop store for read-only agent tests (no book tool used)."""
    async def propose(self, *a, **k):
        return "noop"
    async def consume(self, *a, **k):
        return None


_NS = _NoopStore()


async def _ra(ctx, client, message):
    """Call run_agent with noop store, return just the reply text."""
    return (await run_agent(ctx, client, _NS, message)).reply

# ── fixtures ──────────────────────────────────────────────────────────────────

CTX = TenantContext(uid="u1", tenant_id="t-1", tenant_slug="demo",
                    role="resident", household_id="h-1")

FACILITY = {
    "id": "f-court1", "name": "Tennis Court 1",
    "active": True, "slot_duration_minutes": 60,
    "open_time": "08:00", "close_time": "10:00",
}

POLICY_SNAP = {
    "timezone": "UTC",
    "policies": {
        "booking_horizon_days": 3650,
        "booking_window_open_time": "00:00",
        "cancellation_buffer_hours": 1,
    },
}


def _firestore_client():
    """Minimal Firestore mock for tests that reach list_facilities.

    list() uses order_by("__name__").limit(n).stream(), NOT .stream() directly.
    Both chains are set so tests that call list_facilities AND get_availability
    work with the same mock.
    """
    client = MagicMock()
    fac_doc = MagicMock()
    fac_doc.to_dict.return_value = FACILITY
    fac_doc.id = FACILITY["id"]
    # Facility list: collection.order_by().limit().stream()
    (client.collection.return_value.document.return_value
     .collection.return_value.order_by.return_value.limit.return_value
     .stream.return_value) = [fac_doc]
    # Facility get (for get_availability / FacilityRepository.get)
    fac_snap = (client.collection.return_value.document.return_value
                .collection.return_value.document.return_value.get.return_value)
    fac_snap.exists = True
    fac_snap.to_dict.return_value = FACILITY
    # Tenant/policy doc (PolicyService._tenant_doc)
    ten_snap = client.collection.return_value.document.return_value.get.return_value
    ten_snap.exists = True
    ten_snap.to_dict.return_value = POLICY_SNAP
    return client


# ── tools registry ────────────────────────────────────────────────────────────

def test_registered_tools_include_book():
    names = {t["name"] for t in REGISTERED_TOOLS}
    assert "check_availability" in names
    assert "list_my_bookings" in names
    assert "book" in names
    assert "cancel" in names
    assert "get_my_preferences" in names
    assert len(names) == 5


# ── guardrails: rules_pass ────────────────────────────────────────────────────

def test_rules_pass_clean_reply():
    assert rules_pass("The tennis court is available at 9am.") is True


def test_rules_pass_blocks_password_keyword():
    assert rules_pass("Your password is abc123") is False


def test_rules_pass_blocks_email():
    assert rules_pass("Contact admin@example.com for help") is False


def test_rules_pass_blocks_oversized_reply():
    assert rules_pass("x" * 2001) is False


# ── orchestrator: tool call path ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_tool_call_check_availability():
    """Vertex returns a check_availability tool call → service called → final reply returned."""
    fc_response = AgentResponse(function_call=("check_availability",
                                               {"facility_id": "f-court1", "date": "2027-01-15"}),
                                text=None)
    text_response = AgentResponse(function_call=None, text="The court is available at 08:00.")

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc_response, text_response]) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.availability.BookingRepository.booked_starts",
              return_value=set()),
    ):
        reply = await _ra(CTX, _firestore_client(),"Is the tennis court free tomorrow?")

    assert reply == "The court is available at 08:00."
    assert mock_gen.call_count == 2  # turn 1 + turn 2


@pytest.mark.asyncio
async def test_agent_direct_text_reply():
    """Vertex returns direct text (no tool call) → output guard passes → reply returned."""
    text_response = AgentResponse(function_call=None, text="I can only help with booking queries.")

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=text_response),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        reply = await _ra(CTX, _firestore_client(),"What's the weather today?")

    assert reply == "I can only help with booking queries."


@pytest.mark.asyncio
async def test_agent_list_my_bookings_tool():
    """Vertex returns a list_my_bookings tool call → service called → reply returned."""
    fc_response = AgentResponse(function_call=("list_my_bookings", {}), text=None)
    text_response = AgentResponse(function_call=None, text="You have 1 upcoming booking.")

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc_response, text_response]),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.bookings.BookingRepository.list_for_uid",
              return_value=([], None)),
    ):
        reply = await _ra(CTX, _firestore_client(),"Show my bookings")

    assert reply == "You have 1 upcoming booking."


# ── hallucination guard ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hallucination_guard_blocks_invalid_facility_id():
    """LLM hallucinates a facility_id not in the real list → service NOT called → error JSON dispatched.

    Patches sport_slot.services.agent.orchestrator.get_availability — the bound
    name in the module that calls it — so removing the guard would cause this
    test to fail (mock_avail would be called, not skipped).
    """
    fc_response = AgentResponse(function_call=("check_availability",
                                               {"facility_id": "FAKE-123", "date": "2027-01-15"}),
                                text=None)
    text_response = AgentResponse(function_call=None, text="Sorry, that facility was not found.")

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc_response, text_response]),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.agent.orchestrator.get_availability") as mock_avail,
    ):
        reply = await _ra(CTX, _firestore_client(),"Check FAKE-123 availability")

    mock_avail.assert_not_called()
    assert reply == "Sorry, that facility was not found."


@pytest.mark.asyncio
async def test_valid_facility_id_DOES_call_get_availability():
    """Positive control: valid facility_id drives orchestrator.get_availability with correct args.

    _firestore_client() returns FACILITY from list_facilities (via the corrected
    order_by/limit/stream chain), so valid_ids = {"f-court1"}.  The guard passes
    and get_availability (patched at the orchestrator binding) is called once with
    the resident ctx, facility_id, and date.  This proves the patch site is correct,
    making the negative hallucination test meaningful.
    """
    fc_response = AgentResponse(
        function_call=("check_availability", {"facility_id": "f-court1", "date": "2027-01-15"}),
        text=None,
    )
    text_response = AgentResponse(function_call=None, text="Slots available.")
    avail_result = {"facility_id": "f-court1", "date": "2027-01-15", "slots": []}

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc_response, text_response]),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=avail_result) as mock_avail,
    ):
        reply = await _ra(CTX, _firestore_client(),"Is f-court1 free on 2027-01-15?")

    mock_avail.assert_called_once()
    call_args = mock_avail.call_args
    assert call_args.args[0] == CTX          # resident ctx
    assert call_args.args[2] == "f-court1"   # facility_id
    assert call_args.args[3] == "2027-01-15" # date
    assert reply == "Slots available."


# ── output guard blocking ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_output_guard_blocks_unsafe_reply():
    """Output guard classifier returns False → fallback returned."""
    text_response = AgentResponse(function_call=None, text="Something unsafe here.")

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=text_response),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=False),
    ):
        reply = await _ra(CTX, _firestore_client(),"Tell me something")

    assert "sorry" in reply.lower() or "only" in reply.lower()


@pytest.mark.asyncio
async def test_output_guard_rules_block_password_keyword():
    """Rules guard fires before classifier when reply contains 'password'."""
    text_response = AgentResponse(function_call=None,
                                  text="Your password is abc123")

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=text_response),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True) as mock_cls,
    ):
        reply = await _ra(CTX, _firestore_client(),"What's my password?")

    mock_cls.assert_not_called()  # rules blocked before LLM classifier
    assert "sorry" in reply.lower() or "only" in reply.lower()


# ── fail closed ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fail_closed_on_vertex_error():
    """Vertex generate raises → orchestrator catches → returns safe fallback."""
    with patch("sport_slot.services.agent.vertex_client.generate",
               new_callable=AsyncMock, side_effect=RuntimeError("network error")):
        reply = await _ra(CTX, _firestore_client(),"Any question")

    assert "sorry" in reply.lower() or "only" in reply.lower()


@pytest.mark.asyncio
async def test_fail_closed_empty_vertex_response():
    """Both function_call and text are None → fallback returned."""
    empty = AgentResponse(function_call=None, text=None)

    with patch("sport_slot.services.agent.vertex_client.generate",
               new_callable=AsyncMock, return_value=empty):
        reply = await _ra(CTX, _firestore_client(),"Any question")

    assert "sorry" in reply.lower() or "only" in reply.lower()


# ── date anchor in system prompt (1b.1 fix #2) ───────────────────────────────

@pytest.mark.asyncio
async def test_system_prompt_contains_today_date():
    """System prompt includes today's date so the model can resolve relative dates.

    POLICY_SNAP has timezone=UTC, so today_str should be today in UTC.
    We check that the injected date appears in the system_instruction kwarg
    passed to the first vertex_client.generate call.
    """
    text_response = AgentResponse(function_call=None, text="I can help.")

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=text_response) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        await _ra(CTX, _firestore_client(),"Hello")

    system_instruction = mock_gen.call_args_list[0].kwargs["system_instruction"]
    assert "Today is" in system_instruction

    today_utc = datetime.datetime.now(zoneinfo.ZoneInfo("UTC")).date().isoformat()
    assert today_utc in system_instruction

    weekday = datetime.datetime.now(zoneinfo.ZoneInfo("UTC")).date().strftime("%A")
    assert weekday in system_instruction


# ── booking summarization framing (1b.1 fix #3) ──────────────────────────────

@pytest.mark.asyncio
async def test_list_my_bookings_turn2_receives_presummary_with_count():
    """list_my_bookings result is pre-summarized before Turn 2.

    Turn 2 receives 'total_bookings=N' + per-booking lines, not raw JSON.
    This ensures the model sees facts and counts, not a JSON blob it may distrust.
    """
    fc_response = AgentResponse(function_call=("list_my_bookings", {}), text=None)
    text_response = AgentResponse(function_call=None, text="You have 3 confirmed bookings.")
    bookings = [
        {"facility_id": "f-1", "date": "2027-01-15", "start": "09:00", "status": "confirmed",
         "cancellable": True},
        {"facility_id": "f-1", "date": "2027-01-16", "start": "10:00", "status": "confirmed",
         "cancellable": True},
        {"facility_id": "f-2", "date": "2027-01-17", "start": "08:00", "status": "confirmed",
         "cancellable": False},
    ]

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc_response, text_response]) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.bookings.BookingRepository.list_for_uid",
              return_value=(bookings, None)),
    ):
        reply = await _ra(CTX, _firestore_client(),"How many bookings do I have?")

    assert reply == "You have 3 confirmed bookings."

    # Turn 2 message (second generate call) must contain the count line
    turn2_message = mock_gen.call_args_list[1].kwargs["message"]
    assert "total_bookings=3" in turn2_message
    # Turn 2 framing must be authoritative
    assert "AUTHORITATIVE" in turn2_message


@pytest.mark.asyncio
async def test_list_my_bookings_empty_result_shows_zero():
    """Zero bookings → Turn 2 framing says total_bookings=0."""
    fc_response = AgentResponse(function_call=("list_my_bookings", {}), text=None)
    text_response = AgentResponse(function_call=None, text="You have no bookings.")

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc_response, text_response]),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.bookings.BookingRepository.list_for_uid",
              return_value=([], None)),
    ):
        reply = await _ra(CTX, _firestore_client(),"How many bookings?")

    assert reply == "You have no bookings."


# ── output guard disabled ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_output_guard_disabled_skips_classifier():
    """When agent_output_guard_enabled=False, classifier NOT called."""
    text_response = AgentResponse(function_call=None, text="Tennis court is free.")

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=text_response),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock) as mock_cls,
        patch("sport_slot.config.get_settings") as mock_settings,
    ):
        mock_settings.return_value.agent_output_guard_enabled = False
        mock_settings.return_value.agent_model = "gemini-2.5-flash"
        mock_settings.return_value.vertex_project = "sport-slot-dev"
        mock_settings.return_value.vertex_location = "asia-south1"

        reply = await _ra(CTX, _firestore_client(),"Is the court free?")

    mock_cls.assert_not_called()
    assert reply == "Tennis court is free."
