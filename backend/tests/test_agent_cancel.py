"""Hermetic tests for the agent cancel propose→confirm→execute gate (Slice 3b).

ALL Vertex calls are mocked — ZERO real network/Vertex/Redis calls.
cancel_booking is mocked at the orchestrator binding.

Mock targets:
  - sport_slot.services.agent.vertex_client.generate
  - sport_slot.services.agent.orchestrator.list_my_bookings
  - sport_slot.services.agent.orchestrator.PolicyService
  - sport_slot.services.agent.orchestrator.cancel_booking
  - FakePendingActionStore (in-memory, no Redis)

Tests:
  - _parse_date_hint: ISO / today / tomorrow / weekday / unrecognised
  - _filter_cancel_candidates: pure function, all branches
  - PROPOSE 0-candidates: no pending action, "no bookings" reply
  - PROPOSE 1-candidate: pending action written, confirm prompt, cancel_booking NOT called
  - PROPOSE many-candidates: disambiguation NL, no pending action
  - PROPOSE date_hint narrows: multiple bookings → date_hint selects one
  - PROPOSE missing sport: safe reply, no pending action
  - PROPOSE list_my_bookings error: safe reply
  - PROPOSE policy error: safe reply
  - PROPOSE store.propose error: safe reply
  - EXECUTE happy: cancel_booking called with stored booking_id + source="agent"
  - EXECUTE 409: "already cancelled" NL reply
  - EXECUTE 422: "cancellation window" NL reply
  - EXECUTE 404: "not found" NL reply
  - EXECUTE other ApiError: generic fallback
  - EXECUTE expired: cancel_booking NOT called
  - GATE INTEGRITY: propose never calls cancel_booking; execute never calls Vertex
  - SOURCE/AUDIT: cancel_booking(source="agent") writes "agent.booking_cancelled"

Note: hermetic tests prove plumbing + gate. Live round-trip validated separately.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.services.agent.orchestrator import (
    _filter_cancel_candidates,
    _parse_date_hint,
    run_agent,
    run_agent_confirm,
)
from sport_slot.services.agent.vertex_client import AgentResponse

# ── fixtures ──────────────────────────────────────────────────────────────────

CTX = TenantContext(
    uid="u1", tenant_id="t-1", tenant_slug="demo",
    role="resident", household_id="h-1",
)

TENNIS_FAC = {
    "id": "f-tennis1", "name": "Tennis Court 1", "sport": "tennis",
    "active": True, "slot_duration_minutes": 60,
    "open_time": "08:00", "close_time": "20:00",
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
        "max_slots_per_user_per_sport_per_day": 5,
        "cancellation_buffer_hours": 1,
    },
}


def _future_date(days: int = 3) -> str:
    return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()


def _booking(
    booking_id: str = "bk-1",
    facility_id: str = "f-tennis1",
    days_ahead: int = 3,
    start: str = "10:00",
    status: str = "confirmed",
) -> dict:
    date_str = _future_date(days_ahead)
    return {
        "id": booking_id,
        "uid": CTX.uid,
        "facility_id": facility_id,
        "date": date_str,
        "start": start,
        "end": "11:00",
        "status": status,
        "cancellable": True,
    }


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


class FakePendingActionStore:
    def __init__(self) -> None:
        self._store: dict[str, dict] = {}
        self.propose_calls: list[tuple] = []
        self.consume_calls: list[tuple] = []

    def _key(self, ctx: TenantContext, action_id: str) -> str:
        return f"{ctx.tenant_id}:{ctx.uid}:{action_id}"

    async def propose(self, ctx: TenantContext, action_type: str, params: dict) -> str:
        action_id = f"pending-{len(self._store) + 1:03d}"
        self._store[self._key(ctx, action_id)] = {"action_type": action_type, "params": params}
        self.propose_calls.append((ctx, action_type, params))
        return action_id

    async def consume(self, ctx: TenantContext, action_id: str) -> dict | None:
        self.consume_calls.append((ctx, action_id))
        return self._store.pop(self._key(ctx, action_id), None)


class FakeLock:
    async def acquire(self, key: str, ttl_ms: int = 10_000) -> str:
        return "tok"

    async def release(self, key: str, token: str) -> None:
        pass

    @staticmethod
    def slot_key(*args: str) -> str:
        return ":".join(args)


def _policy_mock(buffer_hours: int = 1) -> MagicMock:
    """Return a mock PolicyService instance."""
    policy = MagicMock()
    policy.tenant_timezone.return_value = "UTC"
    policy.get.return_value = buffer_hours
    return policy


# ── _parse_date_hint ───────────────────────────────────────────────────────────

class TestParseDateHint:
    _today = datetime.date(2027, 6, 14)  # a Monday

    def test_iso_date(self):
        assert _parse_date_hint("2027-06-20", self._today) == datetime.date(2027, 6, 20)

    def test_today(self):
        assert _parse_date_hint("today", self._today) == self._today

    def test_tomorrow(self):
        assert _parse_date_hint("tomorrow", self._today) == datetime.date(2027, 6, 15)

    def test_weekday_name_next_occurrence(self):
        # today is Monday 2027-06-14; next Saturday is 2027-06-19
        result = _parse_date_hint("saturday", self._today)
        assert result == datetime.date(2027, 6, 19)

    def test_weekday_today(self):
        # today is Monday — "monday" should return today
        result = _parse_date_hint("monday", self._today)
        assert result == self._today

    def test_unrecognised_returns_none(self):
        assert _parse_date_hint("next week", self._today) is None
        assert _parse_date_hint("some day", self._today) is None

    def test_case_insensitive(self):
        assert _parse_date_hint("Saturday", self._today) == datetime.date(2027, 6, 19)
        assert _parse_date_hint("TOMORROW", self._today) == datetime.date(2027, 6, 15)


# ── _filter_cancel_candidates ─────────────────────────────────────────────────

class TestFilterCancelCandidates:
    # Fixed reference: 2027-06-14 00:00:00, buffer=1h
    _now = datetime.datetime(2027, 6, 14, 0, 0, 0)
    _buffer = 1

    def _future(self, days: int) -> str:
        return (self._now.date() + datetime.timedelta(days=days)).isoformat()

    def _booking(self, facility_id="f-tennis1", days=3, start="10:00",
                 status="confirmed") -> dict:
        return {
            "id": f"{facility_id}_{self._future(days)}_{start}",
            "uid": "u1",
            "facility_id": facility_id,
            "date": self._future(days),
            "start": start,
            "end": "11:00",
            "status": status,
        }

    def test_returns_matching_confirmed_future_tennis_booking(self):
        b = self._booking()
        result = _filter_cancel_candidates([b], FACILITIES, "tennis", None, self._now, self._buffer)
        assert result == [b]

    def test_excludes_cancelled_booking(self):
        b = self._booking(status="cancelled")
        result = _filter_cancel_candidates([b], FACILITIES, "tennis", None, self._now, self._buffer)
        assert result == []

    def test_excludes_wrong_sport(self):
        b = self._booking()  # tennis facility
        result = _filter_cancel_candidates([b], FACILITIES, "badminton", None, self._now, self._buffer)
        assert result == []

    def test_excludes_booking_outside_7_day_window(self):
        b = self._booking(days=8)
        result = _filter_cancel_candidates([b], FACILITIES, "tennis", None, self._now, self._buffer)
        assert result == []

    def test_includes_booking_on_day_7(self):
        b = self._booking(days=7)
        result = _filter_cancel_candidates([b], FACILITIES, "tennis", None, self._now, self._buffer)
        assert result == [b]

    def test_excludes_past_booking(self):
        past_date = (self._now.date() - datetime.timedelta(days=1)).isoformat()
        b = {**self._booking(), "date": past_date}
        result = _filter_cancel_candidates([b], FACILITIES, "tennis", None, self._now, self._buffer)
        assert result == []

    def test_excludes_within_buffer(self):
        # Slot is today at 00:30 — within 1-hour buffer from now (00:00)
        today = self._now.date().isoformat()
        b = {**self._booking(), "date": today, "start": "00:30"}
        result = _filter_cancel_candidates([b], FACILITIES, "tennis", None, self._now, self._buffer)
        assert result == []

    def test_excludes_facility_not_in_list(self):
        b = self._booking(facility_id="unknown-fac")
        result = _filter_cancel_candidates([b], FACILITIES, "tennis", None, self._now, self._buffer)
        assert result == []

    def test_date_hint_narrows_results(self):
        b1 = self._booking(days=2)
        b2 = self._booking(days=4)
        date_hint = self._future(2)
        result = _filter_cancel_candidates([b1, b2], FACILITIES, "tennis",
                                           date_hint, self._now, self._buffer)
        assert result == [b1]

    def test_date_hint_unrecognised_ignored(self):
        b1 = self._booking(days=2)
        b2 = self._booking(days=4)
        result = _filter_cancel_candidates([b1, b2], FACILITIES, "tennis",
                                           "sometime", self._now, self._buffer)
        assert result == [b1, b2]

    def test_multiple_sports_returns_only_matching(self):
        tennis = self._booking(facility_id="f-tennis1", days=2)
        badminton = self._booking(facility_id="f-badminton1", days=3)
        result = _filter_cancel_candidates([tennis, badminton], FACILITIES, "badminton",
                                           None, self._now, self._buffer)
        assert result == [badminton]

    def test_sport_match_is_case_insensitive(self):
        b = self._booking()
        result = _filter_cancel_candidates([b], FACILITIES, "Tennis", None, self._now, self._buffer)
        assert result == [b]


# ── PROPOSE: zero candidates ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_propose_cancel_zero_candidates_no_pending_action():
    """0 matching bookings → no pending action, "no bookings" reply."""
    fc = AgentResponse(function_call=("cancel", {"sport": "tennis"}), text=None)
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.orchestrator.list_my_bookings",
              return_value={"items": [], "next_cursor": None}),
        patch("sport_slot.services.agent.orchestrator.PolicyService",
              return_value=_policy_mock()),
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Cancel my tennis booking")

    assert turn.pending_action_id is None
    assert len(store.propose_calls) == 0
    assert "tennis" in turn.reply.lower()
    assert "no" in turn.reply.lower() or "don't have" in turn.reply.lower()


# ── PROPOSE: one candidate ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_propose_cancel_one_candidate_writes_pending_action():
    """1 matching booking → pending action written with booking_id, confirm prompt returned."""
    b = _booking()
    fc = AgentResponse(function_call=("cancel", {"sport": "tennis"}), text=None)
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.orchestrator.list_my_bookings",
              return_value={"items": [b], "next_cursor": None}),
        patch("sport_slot.services.agent.orchestrator.PolicyService",
              return_value=_policy_mock()),
        patch("sport_slot.services.agent.orchestrator.cancel_booking",
              new_callable=AsyncMock) as mock_cancel,
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Cancel tennis")

    assert turn.pending_action_id is not None
    assert len(store.propose_calls) == 1
    _, action_type, params = store.propose_calls[0]
    assert action_type == "cancel"
    assert params == {"booking_id": b["id"]}
    mock_cancel.assert_not_called()
    assert "confirm" in turn.reply.lower() or "sure" in turn.reply.lower()


@pytest.mark.asyncio
async def test_propose_cancel_reply_includes_facility_date_start():
    """Confirm prompt includes facility name, date, and start time."""
    b = _booking()
    fc = AgentResponse(function_call=("cancel", {"sport": "tennis"}), text=None)
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.orchestrator.list_my_bookings",
              return_value={"items": [b], "next_cursor": None}),
        patch("sport_slot.services.agent.orchestrator.PolicyService",
              return_value=_policy_mock()),
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Cancel tennis")

    assert "Tennis Court 1" in turn.reply
    assert b["date"] in turn.reply
    assert b["start"] in turn.reply


# ── PROPOSE: many candidates ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_propose_cancel_many_candidates_no_pending_action_disambiguation():
    """2+ matching bookings → disambiguation NL list returned, no pending action."""
    b1 = _booking(booking_id="bk-1", days_ahead=2, start="09:00")
    b2 = _booking(booking_id="bk-2", days_ahead=4, start="14:00")
    fc = AgentResponse(function_call=("cancel", {"sport": "tennis"}), text=None)
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.orchestrator.list_my_bookings",
              return_value={"items": [b1, b2], "next_cursor": None}),
        patch("sport_slot.services.agent.orchestrator.PolicyService",
              return_value=_policy_mock()),
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Cancel tennis")

    assert turn.pending_action_id is None
    assert len(store.propose_calls) == 0
    assert "2" in turn.reply
    assert b1["date"] in turn.reply
    assert b2["date"] in turn.reply


# ── PROPOSE: date_hint narrows ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_propose_cancel_date_hint_selects_single_from_many():
    """date_hint provided → narrows multiple candidates to one → pending action written."""
    b1 = _booking(booking_id="bk-1", days_ahead=2, start="09:00")
    b2 = _booking(booking_id="bk-2", days_ahead=4, start="14:00")
    target_date = b1["date"]
    fc = AgentResponse(
        function_call=("cancel", {"sport": "tennis", "date_hint": target_date}),
        text=None,
    )
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.orchestrator.list_my_bookings",
              return_value={"items": [b1, b2], "next_cursor": None}),
        patch("sport_slot.services.agent.orchestrator.PolicyService",
              return_value=_policy_mock()),
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Cancel tennis on that date")

    assert turn.pending_action_id is not None
    _, _, params = store.propose_calls[0]
    assert params == {"booking_id": b1["id"]}


# ── PROPOSE: error paths ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_propose_cancel_missing_sport_returns_safe_reply():
    """Cancel tool called with no sport → safe reply, no pending action."""
    fc = AgentResponse(function_call=("cancel", {}), text=None)
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.orchestrator.list_my_bookings",
              return_value={"items": [], "next_cursor": None}),
        patch("sport_slot.services.agent.orchestrator.PolicyService",
              return_value=_policy_mock()),
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Cancel something")

    assert turn.pending_action_id is None
    assert len(store.propose_calls) == 0


@pytest.mark.asyncio
async def test_propose_cancel_list_bookings_error_returns_safe_reply():
    """list_my_bookings raises → safe reply, no pending action, cancel_booking NOT called."""
    fc = AgentResponse(function_call=("cancel", {"sport": "tennis"}), text=None)
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.orchestrator.list_my_bookings",
              side_effect=RuntimeError("db down")),
        patch("sport_slot.services.agent.orchestrator.PolicyService",
              return_value=_policy_mock()),
        patch("sport_slot.services.agent.orchestrator.cancel_booking",
              new_callable=AsyncMock) as mock_cancel,
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Cancel tennis")

    assert turn.pending_action_id is None
    mock_cancel.assert_not_called()
    assert "couldn't" in turn.reply.lower() or "try again" in turn.reply.lower()


@pytest.mark.asyncio
async def test_propose_cancel_policy_error_returns_safe_reply():
    """PolicyService raises → safe reply, no pending action."""
    b = _booking()
    fc = AgentResponse(function_call=("cancel", {"sport": "tennis"}), text=None)
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.orchestrator.list_my_bookings",
              return_value={"items": [b], "next_cursor": None}),
        patch("sport_slot.services.agent.orchestrator.PolicyService",
              side_effect=RuntimeError("policy unavailable")),
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Cancel tennis")

    assert turn.pending_action_id is None
    assert len(store.propose_calls) == 0


@pytest.mark.asyncio
async def test_propose_cancel_store_propose_error_returns_safe_reply():
    """store.propose raises → safe reply, no pending_action_id."""
    b = _booking()
    fc = AgentResponse(function_call=("cancel", {"sport": "tennis"}), text=None)

    class _FailStore:
        async def propose(self, *a, **k):
            raise RuntimeError("redis down")
        async def consume(self, *a, **k):
            return None

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.orchestrator.list_my_bookings",
              return_value={"items": [b], "next_cursor": None}),
        patch("sport_slot.services.agent.orchestrator.PolicyService",
              return_value=_policy_mock()),
    ):
        turn = await run_agent(CTX, _firestore_client(), _FailStore(), "Cancel tennis")

    assert turn.pending_action_id is None
    assert "couldn't" in turn.reply.lower() or "try again" in turn.reply.lower()


# ── EXECUTE: happy path ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_cancel_calls_cancel_booking_with_stored_id_and_source_agent():
    """Consume returns cancel action → cancel_booking called ONCE with stored booking_id
    + source='agent'. Vertex NOT called."""
    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "cancel", {"booking_id": "bk-test-1"})

    cancel_result = {
        "id": "bk-test-1", "status": "cancelled",
        "facility_id": "f-tennis1", "date": _future_date(3), "start": "10:00",
    }

    with (
        patch("sport_slot.services.agent.orchestrator.cancel_booking",
              return_value=cancel_result) as mock_cancel,
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock) as mock_gen,
    ):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    mock_cancel.assert_called_once()
    call = mock_cancel.call_args
    assert call.args[2] == "bk-test-1"       # booking_id
    assert call.kwargs.get("source") == "agent"
    mock_gen.assert_not_called()
    assert "cancelled" in reply.lower()


@pytest.mark.asyncio
async def test_execute_cancel_reply_includes_facility_and_date():
    """Confirmation reply includes facility name (or id), date, and start."""
    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "cancel", {"booking_id": "bk-1"})
    date_str = _future_date(3)
    cancel_result = {
        "id": "bk-1", "status": "cancelled",
        "facility_id": "f-tennis1", "date": date_str, "start": "10:00",
    }

    with patch("sport_slot.services.agent.orchestrator.cancel_booking",
               return_value=cancel_result):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert date_str in reply
    assert "10:00" in reply
    assert "tennis" in reply.lower() or "f-tennis1" in reply.lower()


# ── EXECUTE: ApiError paths ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_cancel_409_already_cancelled():
    """cancel_booking raises 409 → "already cancelled" NL reply."""
    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "cancel", {"booking_id": "bk-1"})

    with patch("sport_slot.services.agent.orchestrator.cancel_booking",
               side_effect=ApiError(409, "ALREADY_CANCELLED", "already cancelled")):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert "already" in reply.lower() and "cancelled" in reply.lower()


@pytest.mark.asyncio
async def test_execute_cancel_422_too_late():
    """cancel_booking raises 422 → "too late / window passed" NL reply."""
    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "cancel", {"booking_id": "bk-1"})

    with patch("sport_slot.services.agent.orchestrator.cancel_booking",
               side_effect=ApiError(422, "CANCELLATION_TOO_LATE", "too late")):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert "late" in reply.lower() or "window" in reply.lower() or "passed" in reply.lower()


@pytest.mark.asyncio
async def test_execute_cancel_404_not_found():
    """cancel_booking raises 404 → "not found" NL reply."""
    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "cancel", {"booking_id": "bk-1"})

    with patch("sport_slot.services.agent.orchestrator.cancel_booking",
               side_effect=ApiError(404, "BOOKING_NOT_FOUND", "not found")):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert "couldn't find" in reply.lower() or "not found" in reply.lower()


@pytest.mark.asyncio
async def test_execute_cancel_other_api_error_generic_fallback():
    """Unknown ApiError status → generic "wasn't able" fallback."""
    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "cancel", {"booking_id": "bk-1"})

    with patch("sport_slot.services.agent.orchestrator.cancel_booking",
               side_effect=ApiError(500, "INTERNAL", "internal")):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert "wasn't able" in reply.lower() or "try again" in reply.lower()


# ── EXECUTE: expired / missing ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_cancel_expired_action_does_not_call_cancel_booking():
    """consume returns None → cancel_booking NOT called, safe expired reply."""
    store = FakePendingActionStore()  # empty

    with patch("sport_slot.services.agent.orchestrator.cancel_booking",
               new_callable=AsyncMock) as mock_cancel:
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, "no-such-id")

    mock_cancel.assert_not_called()
    assert "expired" in reply.lower() or "please ask again" in reply.lower()


# ── GATE INTEGRITY ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_propose_turn_never_calls_cancel_booking():
    """The message (propose) path NEVER calls cancel_booking, regardless of tool output."""
    b = _booking()
    fc = AgentResponse(function_call=("cancel", {"sport": "tennis"}), text=None)
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.orchestrator.list_my_bookings",
              return_value={"items": [b], "next_cursor": None}),
        patch("sport_slot.services.agent.orchestrator.PolicyService",
              return_value=_policy_mock()),
        patch("sport_slot.services.agent.orchestrator.cancel_booking",
              new_callable=AsyncMock) as mock_cancel,
    ):
        await run_agent(CTX, _firestore_client(), store, "Cancel tennis")

    mock_cancel.assert_not_called()


@pytest.mark.asyncio
async def test_execute_cancel_turn_makes_no_vertex_call():
    """The execute (confirm) path makes NO Vertex/generate calls."""
    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "cancel", {"booking_id": "bk-1"})
    cancel_result = {
        "id": "bk-1", "status": "cancelled",
        "facility_id": "f-tennis1", "date": _future_date(3), "start": "10:00",
    }

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock) as mock_gen,
        patch("sport_slot.services.agent.orchestrator.cancel_booking",
              return_value=cancel_result),
    ):
        await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    mock_gen.assert_not_called()


# ── SOURCE / AUDIT differentiation ───────────────────────────────────────────

def test_cancel_booking_source_agent_writes_agent_booking_cancelled():
    """cancel_booking(source='agent') writes event_type 'agent.booking_cancelled'."""
    from sport_slot.services.bookings import cancel_booking

    booking = {
        "id": "f1_2027-06-20_10:00", "uid": CTX.uid, "status": "confirmed",
        "date": "2027-06-20", "start": "10:00", "facility_id": "f1",
    }

    with (
        patch("sport_slot.services.bookings.BookingRepository.get",
              side_effect=[booking, {**booking, "status": "cancelled"}]),
        patch("sport_slot.services.bookings.BookingRepository.update"),
        patch("sport_slot.services.bookings.AuditRepository.write_event") as mock_audit,
    ):
        cancel_booking(CTX, _firestore_client(), booking["id"], source="agent")

    assert mock_audit.call_args.args[0] == "agent.booking_cancelled"


def test_cancel_booking_source_default_writes_booking_cancelled():
    """cancel_booking() with default source writes 'booking.cancelled' (manual path unchanged)."""
    from sport_slot.services.bookings import cancel_booking

    booking = {
        "id": "f1_2027-06-20_10:00", "uid": CTX.uid, "status": "confirmed",
        "date": "2027-06-20", "start": "10:00", "facility_id": "f1",
    }

    with (
        patch("sport_slot.services.bookings.BookingRepository.get",
              side_effect=[booking, {**booking, "status": "cancelled"}]),
        patch("sport_slot.services.bookings.BookingRepository.update"),
        patch("sport_slot.services.bookings.AuditRepository.write_event") as mock_audit,
    ):
        cancel_booking(CTX, _firestore_client(), booking["id"])

    assert mock_audit.call_args.args[0] == "booking.cancelled"
