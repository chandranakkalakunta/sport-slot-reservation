"""Hermetic tests for Slice 4: preference-aware agent (ADR-0021 §3 read-side).

ALL Vertex calls are mocked — ZERO real network/Vertex/Redis calls.

Mock targets:
  - sport_slot.services.agent.orchestrator.get_preferences (orchestrator binding)
  - sport_slot.services.agent.orchestrator.get_availability
  - sport_slot.services.agent.vertex_client.generate
  - sport_slot.services.agent.vertex_client.classify_output
  - UserProfileRepository.get (for get_preferences unit tests)

Tests:
  - get_preferences: returns nested map; empty on missing profile; empty on
    missing preferences key; empty on Firestore error.
  - _preferences_text: non-empty prefs → rendered section; empty prefs → "".
  - System prompt: prefs present → "Your usual bookings" in prompt; empty → no header.
  - get_my_preferences tool dispatch: with prefs → formatted; empty → no-prefs string.
  - check_availability enrichment: BOOKABLE / TAKEN / OFF-GRID-TODAY /
    sport-mismatch / no-prefs — all branches.
  - Fail-open: get_preferences error does NOT break check_availability result.
  - No regression on book/cancel propose gate (gate integrity still holds).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sport_slot.auth.context import TenantContext
from sport_slot.services.agent.orchestrator import _preferences_text, run_agent
from sport_slot.services.agent.preferences import get_preferences
from sport_slot.services.agent.vertex_client import AgentResponse

# ── fixtures ──────────────────────────────────────────────────────────────────

CTX = TenantContext(
    uid="u1", tenant_id="t-1", tenant_slug="demo",
    role="resident", household_id="h-1",
)

TENNIS_FAC = {
    "id": "f-tennis1", "name": "Tennis Court 1", "sport": "tennis",
    "active": True, "slot_duration_minutes": 60,
    "open_time": "08:00", "close_time": "22:00",
}
BADMINTON_FAC = {
    "id": "f-badminton1", "name": "Badminton Hall A", "sport": "badminton",
    "active": True, "slot_duration_minutes": 45,
    "open_time": "07:00", "close_time": "22:00",
}
FACILITIES = [TENNIS_FAC, BADMINTON_FAC]

POLICY_SNAP = {
    "timezone": "UTC",
    "policies": {
        "booking_horizon_days": 3650,
        "booking_window_open_time": "00:00",
        "cancellation_buffer_hours": 1,
    },
}

PREFS_TENNIS = {"tennis": {"facility_id": "f-tennis1", "start_time": "21:00"}}


def _firestore_client() -> MagicMock:
    client = MagicMock()
    fac_doc = MagicMock()
    fac_doc.to_dict.return_value = TENNIS_FAC
    fac_doc.id = TENNIS_FAC["id"]
    (client.collection.return_value.document.return_value
     .collection.return_value.order_by.return_value.limit.return_value
     .stream.return_value) = [fac_doc]
    fac_snap = (client.collection.return_value.document.return_value
                .collection.return_value.document.return_value.get.return_value)
    fac_snap.exists = True
    fac_snap.to_dict.return_value = TENNIS_FAC
    ten_snap = client.collection.return_value.document.return_value.get.return_value
    ten_snap.exists = True
    ten_snap.to_dict.return_value = POLICY_SNAP
    return client


class _NoopStore:
    async def propose(self, *a, **k):
        return "noop"
    async def consume(self, *a, **k):
        return None


# ── get_preferences unit tests ────────────────────────────────────────────────

def test_get_preferences_returns_last_booked_map():
    """Profile with preferences.last_booked → returns the map."""
    profile = {"preferences": {"last_booked": {"tennis": {"facility_id": "f1", "start_time": "09:00"}}}}
    with patch("sport_slot.services.agent.preferences.UserProfileRepository.get",
               return_value=profile):
        result = get_preferences(CTX, MagicMock())
    assert result == {"tennis": {"facility_id": "f1", "start_time": "09:00"}}


def test_get_preferences_returns_empty_when_profile_missing():
    """UserProfileRepository.get returns None → returns {}."""
    with patch("sport_slot.services.agent.preferences.UserProfileRepository.get",
               return_value=None):
        result = get_preferences(CTX, MagicMock())
    assert result == {}


def test_get_preferences_returns_empty_when_preferences_key_absent():
    """Profile exists but has no 'preferences' key → returns {}."""
    with patch("sport_slot.services.agent.preferences.UserProfileRepository.get",
               return_value={"display_name": "Alice"}):
        result = get_preferences(CTX, MagicMock())
    assert result == {}


def test_get_preferences_returns_empty_on_firestore_error():
    """Firestore error → fail-open: returns {}."""
    with patch("sport_slot.services.agent.preferences.UserProfileRepository.get",
               side_effect=RuntimeError("db unavailable")):
        result = get_preferences(CTX, MagicMock())
    assert result == {}


# ── _preferences_text unit tests ──────────────────────────────────────────────

def test_preferences_text_empty_prefs_returns_empty_string():
    """No preferences → empty string (no header, no blank lines)."""
    assert _preferences_text({}, FACILITIES) == ""


def test_preferences_text_non_empty_contains_header_and_sport():
    """With preferences → 'Your usual bookings' header + sport/name/time."""
    result = _preferences_text(PREFS_TENNIS, FACILITIES)
    assert "Your usual bookings" in result
    assert "tennis" in result
    assert "Tennis Court 1" in result
    assert "21:00" in result


def test_preferences_text_facility_name_resolved_from_list():
    """facility_id is resolved to the human-readable name."""
    prefs = {"badminton": {"facility_id": "f-badminton1", "start_time": "10:00"}}
    result = _preferences_text(prefs, FACILITIES)
    assert "Badminton Hall A" in result


def test_preferences_text_falls_back_to_facility_id_when_not_in_list():
    """Unknown facility_id → falls back to raw id."""
    prefs = {"squash": {"facility_id": "f-squash99", "start_time": "08:00"}}
    result = _preferences_text(prefs, FACILITIES)
    assert "f-squash99" in result


def test_preferences_text_multiple_sports():
    """Multiple sports all appear in the rendered text."""
    prefs = {
        "tennis": {"facility_id": "f-tennis1", "start_time": "09:00"},
        "badminton": {"facility_id": "f-badminton1", "start_time": "10:00"},
    }
    result = _preferences_text(prefs, FACILITIES)
    assert "tennis" in result
    assert "badminton" in result
    assert "Tennis Court 1" in result
    assert "Badminton Hall A" in result


# ── System prompt injection ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_system_prompt_includes_preferences_when_present():
    """When get_preferences returns non-empty, 'Your usual bookings' appears in
    the system_instruction sent to Vertex on Turn 1."""
    text_response = AgentResponse(function_call=None, text="I'll help with that.")

    with (
        patch("sport_slot.services.agent.orchestrator.get_preferences",
              return_value=PREFS_TENNIS),
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=text_response) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        await run_agent(CTX, _firestore_client(), _NoopStore(), "What's available?")

    system_instr = mock_gen.call_args_list[0].kwargs["system_instruction"]
    assert "Your usual bookings (from prior history):" in system_instr
    assert "tennis" in system_instr
    assert "Tennis Court 1" in system_instr
    assert "21:00" in system_instr


@pytest.mark.asyncio
async def test_system_prompt_omits_preferences_section_when_empty():
    """When get_preferences returns {}, 'Your usual bookings' does NOT appear."""
    text_response = AgentResponse(function_call=None, text="Sure!")

    with (
        patch("sport_slot.services.agent.orchestrator.get_preferences",
              return_value={}),
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=text_response) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        await run_agent(CTX, _firestore_client(), _NoopStore(), "Anything available?")

    system_instr = mock_gen.call_args_list[0].kwargs["system_instruction"]
    # The dynamic section header rendered by _preferences_text() must be absent.
    # Rule B's static text contains "Your usual bookings" but not the section marker.
    assert "Your usual bookings (from prior history):" not in system_instr


@pytest.mark.asyncio
async def test_system_prompt_includes_tool_routing_rules():
    """The three 4.1 prompt-tuning rules are present in the system_instruction.

    Rule A: route 'usual/preferred/last' questions to get_my_preferences.
    Rule B: for book requests, use ambient preferences — do NOT call get_my_preferences.
    Rule C: MUST call book/cancel tool — never narrate the action.
    """
    text_response = AgentResponse(function_call=None, text="Got it.")

    with (
        patch("sport_slot.services.agent.orchestrator.get_preferences",
              return_value={}),
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=text_response) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        await run_agent(CTX, _firestore_client(), _NoopStore(), "Hello")

    system_instr = mock_gen.call_args_list[0].kwargs["system_instruction"]
    assert "Do not refuse such questions" in system_instr                    # rule A
    assert "Do NOT call `get_my_preferences` as a separate step" in system_instr  # rule B
    assert "MUST call the `book` or `cancel` tool" in system_instr          # rule C


# ── get_my_preferences dispatch ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_my_preferences_tool_returns_formatted_map():
    """get_my_preferences tool call → Turn 2 receives formatted preference text."""
    fc = AgentResponse(function_call=("get_my_preferences", {}), text=None)
    text_reply = AgentResponse(function_call=None, text="Your usual is Tennis Court 1 at 21:00.")

    with (
        patch("sport_slot.services.agent.orchestrator.get_preferences",
              return_value=PREFS_TENNIS),
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc, text_reply]) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        turn = await run_agent(CTX, _firestore_client(), _NoopStore(), "What's my usual court?")

    # Turn 2 message should include formatted preference text
    turn2_msg = mock_gen.call_args_list[1].kwargs["message"]
    assert "user_preferences:" in turn2_msg
    assert "tennis" in turn2_msg
    assert "f-tennis1" in turn2_msg
    assert "21:00" in turn2_msg
    assert turn.reply == "Your usual is Tennis Court 1 at 21:00."


@pytest.mark.asyncio
async def test_get_my_preferences_tool_empty_prefs_returns_no_preferences_string():
    """get_my_preferences with empty prefs → Turn 2 receives 'no remembered' string."""
    fc = AgentResponse(function_call=("get_my_preferences", {}), text=None)
    text_reply = AgentResponse(function_call=None, text="You have no saved preferences yet.")

    with (
        patch("sport_slot.services.agent.orchestrator.get_preferences",
              return_value={}),
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc, text_reply]),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        turn = await run_agent(CTX, _firestore_client(), _NoopStore(), "What are my preferences?")

    assert turn.reply == "You have no saved preferences yet."


# ── check_availability enrichment ─────────────────────────────────────────────

def _avail_result(bookable: bool = True, reason: str = "BOOKED") -> dict:
    slot = {"start": "21:00", "end": "22:00", "bookable": bookable}
    if not bookable:
        slot["reason"] = reason
    return {"facility_id": "f-tennis1", "date": "2027-06-20", "slots": [slot]}


@pytest.mark.asyncio
async def test_check_availability_enriched_with_bookable_usual_slot():
    """Usual slot exists and is bookable → Turn 2 contains '... BOOKABLE'."""
    fc = AgentResponse(
        function_call=("check_availability", {"facility_id": "f-tennis1", "date": "2027-06-20"}),
        text=None,
    )
    text_reply = AgentResponse(function_call=None, text="Your usual slot is free!")

    with (
        patch("sport_slot.services.agent.orchestrator.get_preferences",
              return_value=PREFS_TENNIS),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=_avail_result(bookable=True)),
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc, text_reply]) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        await run_agent(CTX, _firestore_client(), _NoopStore(), "Is tennis court free?")

    turn2_msg = mock_gen.call_args_list[1].kwargs["message"]
    assert "User's usual tennis slot: 21:00 — BOOKABLE" in turn2_msg


@pytest.mark.asyncio
async def test_check_availability_enriched_with_taken_usual_slot():
    """Usual slot exists but taken → Turn 2 contains 'TAKEN (BOOKED)'."""
    fc = AgentResponse(
        function_call=("check_availability", {"facility_id": "f-tennis1", "date": "2027-06-20"}),
        text=None,
    )
    text_reply = AgentResponse(function_call=None, text="Your usual slot is taken.")

    with (
        patch("sport_slot.services.agent.orchestrator.get_preferences",
              return_value=PREFS_TENNIS),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=_avail_result(bookable=False, reason="BOOKED")),
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc, text_reply]) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        await run_agent(CTX, _firestore_client(), _NoopStore(), "Is tennis court free?")

    turn2_msg = mock_gen.call_args_list[1].kwargs["message"]
    assert "User's usual tennis slot: 21:00 — TAKEN (BOOKED)" in turn2_msg


@pytest.mark.asyncio
async def test_check_availability_enriched_off_grid_when_usual_start_absent():
    """Usual start_time not in the slot grid → 'OFF-GRID-TODAY'."""
    fc = AgentResponse(
        function_call=("check_availability", {"facility_id": "f-tennis1", "date": "2027-06-20"}),
        text=None,
    )
    text_reply = AgentResponse(function_call=None, text="Available times shown.")
    # Slot grid has 09:00 only; usual is 21:00 → OFF-GRID-TODAY
    avail_no_usual = {
        "facility_id": "f-tennis1", "date": "2027-06-20",
        "slots": [{"start": "09:00", "end": "10:00", "bookable": True}],
    }

    with (
        patch("sport_slot.services.agent.orchestrator.get_preferences",
              return_value=PREFS_TENNIS),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=avail_no_usual),
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc, text_reply]) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        await run_agent(CTX, _firestore_client(), _NoopStore(), "Is tennis court free?")

    turn2_msg = mock_gen.call_args_list[1].kwargs["message"]
    assert "User's usual tennis slot: 21:00 — OFF-GRID-TODAY" in turn2_msg


@pytest.mark.asyncio
async def test_check_availability_no_enrichment_when_sport_mismatch():
    """Prefs has badminton only; query is for a tennis facility → no enrichment line."""
    fc = AgentResponse(
        function_call=("check_availability", {"facility_id": "f-tennis1", "date": "2027-06-20"}),
        text=None,
    )
    text_reply = AgentResponse(function_call=None, text="Available times shown.")
    badminton_prefs = {"badminton": {"facility_id": "f-badminton1", "start_time": "10:00"}}

    with (
        patch("sport_slot.services.agent.orchestrator.get_preferences",
              return_value=badminton_prefs),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=_avail_result(bookable=True)),
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc, text_reply]) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        await run_agent(CTX, _firestore_client(), _NoopStore(), "Is tennis court free?")

    turn2_msg = mock_gen.call_args_list[1].kwargs["message"]
    # The enrichment line would be "User's usual tennis slot: ... — STATUS"
    # The framing instruction contains "User's usual ... slot'" (no colon/status), so
    # we check absence of the colon+status suffix which only the enrichment line has.
    assert "— BOOKABLE" not in turn2_msg
    assert "— TAKEN" not in turn2_msg
    assert "— OFF-GRID-TODAY" not in turn2_msg


@pytest.mark.asyncio
async def test_check_availability_no_enrichment_when_no_prefs():
    """No preferences → no enrichment line in Turn 2."""
    fc = AgentResponse(
        function_call=("check_availability", {"facility_id": "f-tennis1", "date": "2027-06-20"}),
        text=None,
    )
    text_reply = AgentResponse(function_call=None, text="Available times shown.")

    with (
        patch("sport_slot.services.agent.orchestrator.get_preferences",
              return_value={}),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=_avail_result(bookable=True)),
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc, text_reply]) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        await run_agent(CTX, _firestore_client(), _NoopStore(), "Is tennis court free?")

    turn2_msg = mock_gen.call_args_list[1].kwargs["message"]
    assert "— BOOKABLE" not in turn2_msg
    assert "— TAKEN" not in turn2_msg
    assert "— OFF-GRID-TODAY" not in turn2_msg


# ── Fail-open: prefs error does not break check_availability ──────────────────

@pytest.mark.asyncio
async def test_check_availability_still_works_when_get_preferences_fails():
    """get_preferences raises internally but catch returns {} → no enrichment,
    slot grid still returned to Turn 2 without crashing."""
    fc = AgentResponse(
        function_call=("check_availability", {"facility_id": "f-tennis1", "date": "2027-06-20"}),
        text=None,
    )
    text_reply = AgentResponse(function_call=None, text="Here are the available slots.")
    avail = _avail_result(bookable=True)

    with (
        # Simulate get_preferences raising at the preferences.py level
        patch("sport_slot.services.agent.preferences.UserProfileRepository.get",
              side_effect=RuntimeError("profile db down")),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=avail),
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc, text_reply]) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        turn = await run_agent(CTX, _firestore_client(), _NoopStore(), "Is court free?")

    # Must still get a reply (fail-open)
    assert turn.reply == "Here are the available slots."
    # No enrichment status line (prefs returned {} due to error)
    turn2_msg = mock_gen.call_args_list[1].kwargs["message"]
    assert "— BOOKABLE" not in turn2_msg
    assert "— TAKEN" not in turn2_msg
    assert "— OFF-GRID-TODAY" not in turn2_msg


# ── Gate integrity (no regression) ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_book_propose_gate_unaffected_by_preferences():
    """Book propose→gate still works correctly with preferences in scope.
    Preferences fetched for system prompt but do NOT affect the book gate.
    """
    class _FakeStore:
        def __init__(self):
            self._store = {}
            self.proposed = []
        async def propose(self, ctx, action_type, params):
            aid = "fake-001"
            self._store[f"{ctx.uid}:{aid}"] = {"action_type": action_type, "params": params}
            self.proposed.append(params)
            return aid
        async def consume(self, ctx, action_id):
            return self._store.pop(f"{ctx.uid}:{action_id}", None)

    fc = AgentResponse(
        function_call=("book", {"facility_id": "f-tennis1", "date": "2027-07-01", "start": "09:00"}),
        text=None,
    )
    store = _FakeStore()

    avail = {"facility_id": "f-tennis1", "date": "2027-07-01",
             "slots": [{"start": "09:00", "end": "10:00", "bookable": True}]}

    with (
        patch("sport_slot.services.agent.orchestrator.get_preferences",
              return_value=PREFS_TENNIS),
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=avail),
        patch("sport_slot.services.agent.orchestrator.create_booking",
              new_callable=AsyncMock) as mock_create,
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Book tennis tomorrow at 9am")

    # Pending action written, create_booking NOT called on propose
    assert turn.pending_action_id is not None
    assert len(store.proposed) == 1
    mock_create.assert_not_called()
