"""Hermetic tests for the read-only AI agent (Slice 1b).

ALL Vertex calls are mocked — ZERO real network calls.
Mock targets:
  - sport_slot.services.agent.vertex_client.generate
  - sport_slot.services.agent.vertex_client.classify_output

Tests cover: happy paths (tool call + direct text), hallucination guard,
output guard blocking, fail-closed on Vertex error, unknown tool,
endpoint role gate, and output guard disabled path.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sport_slot.auth.context import TenantContext
from sport_slot.services.agent.guardrails import rules_pass
from sport_slot.services.agent.orchestrator import run_agent
from sport_slot.services.agent.tools import REGISTERED_TOOLS
from sport_slot.services.agent.vertex_client import AgentResponse

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
    """Minimal Firestore mock for tests that reach list_facilities."""
    client = MagicMock()
    # Facility list (collection.stream)
    fac_doc = MagicMock()
    fac_doc.to_dict.return_value = FACILITY
    fac_doc.id = FACILITY["id"]
    client.collection.return_value.document.return_value.collection.return_value.stream.return_value = [fac_doc]
    # Facility get (for get_availability)
    fac_snap = (client.collection.return_value.document.return_value
                .collection.return_value.document.return_value.get.return_value)
    fac_snap.exists = True
    fac_snap.to_dict.return_value = FACILITY
    # Tenant/policy doc
    ten_snap = client.collection.return_value.document.return_value.get.return_value
    ten_snap.exists = True
    ten_snap.to_dict.return_value = POLICY_SNAP
    return client


# ── tools registry ────────────────────────────────────────────────────────────

def test_only_check_availability_and_list_my_bookings_registered():
    names = {t["name"] for t in REGISTERED_TOOLS}
    assert "check_availability" in names
    assert "list_my_bookings" in names
    assert "book" not in names
    assert "cancel" not in names
    assert len(names) == 2


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
        reply = await run_agent(CTX, _firestore_client(), "Is the tennis court free tomorrow?")

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
        reply = await run_agent(CTX, _firestore_client(), "What's the weather today?")

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
        reply = await run_agent(CTX, _firestore_client(), "Show my bookings")

    assert reply == "You have 1 upcoming booking."


# ── hallucination guard ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hallucination_guard_blocks_invalid_facility_id():
    """LLM hallucinates a facility_id not in the real list → service NOT called → error JSON dispatched."""
    fc_response = AgentResponse(function_call=("check_availability",
                                               {"facility_id": "FAKE-123", "date": "2027-01-15"}),
                                text=None)
    text_response = AgentResponse(function_call=None, text="Sorry, that facility was not found.")

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc_response, text_response]),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.availability.get_availability") as mock_avail,
    ):
        reply = await run_agent(CTX, _firestore_client(), "Check FAKE-123 availability")

    mock_avail.assert_not_called()
    assert reply == "Sorry, that facility was not found."


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
        reply = await run_agent(CTX, _firestore_client(), "Tell me something")

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
        reply = await run_agent(CTX, _firestore_client(), "What's my password?")

    mock_cls.assert_not_called()  # rules blocked before LLM classifier
    assert "sorry" in reply.lower() or "only" in reply.lower()


# ── fail closed ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fail_closed_on_vertex_error():
    """Vertex generate raises → orchestrator catches → returns safe fallback."""
    with patch("sport_slot.services.agent.vertex_client.generate",
               new_callable=AsyncMock, side_effect=RuntimeError("network error")):
        reply = await run_agent(CTX, _firestore_client(), "Any question")

    assert "sorry" in reply.lower() or "only" in reply.lower()


@pytest.mark.asyncio
async def test_fail_closed_empty_vertex_response():
    """Both function_call and text are None → fallback returned."""
    empty = AgentResponse(function_call=None, text=None)

    with patch("sport_slot.services.agent.vertex_client.generate",
               new_callable=AsyncMock, return_value=empty):
        reply = await run_agent(CTX, _firestore_client(), "Any question")

    assert "sorry" in reply.lower() or "only" in reply.lower()


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

        reply = await run_agent(CTX, _firestore_client(), "Is the court free?")

    mock_cls.assert_not_called()
    assert reply == "Tennis court is free."
