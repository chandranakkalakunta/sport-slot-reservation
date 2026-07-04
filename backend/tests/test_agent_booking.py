"""Hermetic tests for the agent booking propose→confirm→execute gate (Slice 2b).

ALL Vertex calls are mocked — ZERO real network/Vertex/Redis calls.
create_booking is mocked at the orchestrator binding.

Mock targets:
  - sport_slot.services.agent.vertex_client.generate
  - sport_slot.services.agent.vertex_client.classify_output
  - sport_slot.services.agent.orchestrator.create_booking
  - sport_slot.services.agent.orchestrator.get_availability
  - sport_slot.services.agent.orchestrator._write_preference_memory
  - FakePendingActionStore (in-memory, no Redis)

Tests:
  - PROPOSE: valid facility + bookable slot → pending action written, create_booking NOT called
  - PROPOSE hallucination: invalid facility_id → no pending action, create_booking NOT called
  - PROPOSE unbookable: slot not bookable → no pending action, create_booking NOT called
  - EXECUTE happy: consume → create_booking called with stored params + source="agent"
  - EXECUTE expired: consume returns None → create_booking NOT called
  - EXECUTE scope: different uid → consume returns None (key mismatch) → no execution
  - GATE INTEGRITY: propose path never calls create_booking; execute path never calls Vertex
  - SOURCE/AUDIT: source="agent" → "agent.booking_created"; default → "booking.created"
  - residents-only: non-resident → 403

Note: hermetic tests prove plumbing + the gate. Live model routing and the real
propose→confirm→book round-trip are validated in slice 2b.V.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sport_slot.auth.context import TenantContext
from sport_slot.services.agent.orchestrator import run_agent, run_agent_confirm
from sport_slot.services.agent.vertex_client import AgentResponse

# ── fixtures ──────────────────────────────────────────────────────────────────

CTX = TenantContext(uid="u1", tenant_id="t-1", tenant_slug="demo",
                    role="resident", household_id="h-1")

CTX_OTHER = TenantContext(uid="u-other", tenant_id="t-1", tenant_slug="demo",
                          role="resident", household_id="h-2")

_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
FACILITY = {
    "id": "f-court1", "name": "Tennis Court 1", "sport": "tennis",
    "active": True, "slot_duration_minutes": 60,
    "weekly_schedule": {day: [{"start": "08:00", "end": "12:00"}] for day in _DAYS},
}

POLICY_SNAP = {
    "timezone": "UTC",
    "policies": {
        "booking_horizon_days": 3650,
        "booking_window_open_time": "00:00",
        "max_slots_per_user_per_sport_per_day": 5,
        "cancellation_buffer_hours": 1,
    },
}

BOOKABLE_SLOT = {"start": "09:00", "end": "10:00", "bookable": True}
TAKEN_SLOT = {"start": "09:00", "end": "10:00", "bookable": False, "reason": "BOOKED"}

AVAIL_BOOKABLE = {"facility_id": "f-court1", "date": "2027-01-15", "slots": [BOOKABLE_SLOT]}
AVAIL_TAKEN = {"facility_id": "f-court1", "date": "2027-01-15", "slots": [TAKEN_SLOT]}


def _firestore_client():
    client = MagicMock()
    fac_doc = MagicMock()
    fac_doc.to_dict.return_value = FACILITY
    fac_doc.id = FACILITY["id"]
    (client.collection.return_value.document.return_value
     .collection.return_value.order_by.return_value.limit.return_value
     .stream.return_value) = [fac_doc]
    fac_snap = (client.collection.return_value.document.return_value
                .collection.return_value.document.return_value.get.return_value)
    fac_snap.exists = True
    fac_snap.to_dict.return_value = FACILITY
    ten_snap = client.collection.return_value.document.return_value.get.return_value
    ten_snap.exists = True
    ten_snap.to_dict.return_value = POLICY_SNAP
    return client


class FakePendingActionStore:
    """In-memory store: no Redis, no TTL. Scoped by tenant_id + uid + action_id."""

    def __init__(self):
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

    async def get_latest_for_user(self, ctx: TenantContext, action_type: str):
        return None  # booking tests have no disambiguation scenarios


class FakeLock:
    async def acquire(self, key, ttl_ms=10_000):
        return "tok"
    async def release(self, key, token):
        pass
    @staticmethod
    def slot_key(*args):
        return ":".join(args)


# ── PROPOSE: happy path ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_propose_book_valid_slot_writes_pending_action():
    """Book tool call with valid facility + bookable slot → pending action written,
    create_booking NOT called, response carries pending_action_id."""
    fc = AgentResponse(
        function_call=("book", {"facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"}),
        text=None,
    )
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=AVAIL_BOOKABLE),
        patch("sport_slot.services.agent.orchestrator.create_booking",
              new_callable=AsyncMock) as mock_create,
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Book court tomorrow at 9am")

    # Pending action written
    assert len(store.propose_calls) == 1
    _, action_type, params = store.propose_calls[0]
    assert action_type == "book"
    assert params == {"facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"}

    # create_booking NOT called on propose
    mock_create.assert_not_called()

    # Response carries pending_action_id
    assert turn.pending_action_id is not None
    assert turn.pending_action_id == "pending-001"

    # Reply is a confirmation prompt
    assert "confirm" in turn.reply.lower() or "book" in turn.reply.lower()


@pytest.mark.asyncio
async def test_propose_book_reply_includes_facility_name_and_slot():
    """Confirm prompt contains facility name, date, and start time."""
    fc = AgentResponse(
        function_call=("book", {"facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"}),
        text=None,
    )
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=AVAIL_BOOKABLE),
        patch("sport_slot.services.agent.orchestrator.create_booking",
              new_callable=AsyncMock),
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Book court 1 at 9am")

    assert "Tennis Court 1" in turn.reply
    assert "2027-01-15" in turn.reply
    assert "09:00" in turn.reply


# ── PROPOSE: hallucination guard ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_propose_book_hallucinated_facility_id_no_pending_action():
    """Hallucinated facility_id → no pending action written, create_booking NOT called."""
    fc = AgentResponse(
        function_call=("book", {"facility_id": "FAKE-XYZ", "date": "2027-01-15", "start": "09:00"}),
        text=None,
    )
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.agent.orchestrator.get_availability") as mock_avail,
        patch("sport_slot.services.agent.orchestrator.create_booking",
              new_callable=AsyncMock) as mock_create,
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Book FAKE-XYZ")

    # No pending action written
    assert len(store.propose_calls) == 0
    assert turn.pending_action_id is None
    # get_availability NOT called (guard fires before it)
    mock_avail.assert_not_called()
    # create_booking NOT called
    mock_create.assert_not_called()


# ── PROPOSE: unbookable slot ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_propose_book_unbookable_slot_no_pending_action():
    """Slot not bookable → no pending action written, create_booking NOT called."""
    fc = AgentResponse(
        function_call=("book", {"facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"}),
        text=None,
    )
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=AVAIL_TAKEN),
        patch("sport_slot.services.agent.orchestrator.create_booking",
              new_callable=AsyncMock) as mock_create,
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Book court at 9am")

    assert len(store.propose_calls) == 0
    assert turn.pending_action_id is None
    mock_create.assert_not_called()


# ── EXECUTE: happy path ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_confirm_calls_create_booking_with_stored_params_and_source_agent():
    """Consume returns book action → create_booking called ONCE with EXACTLY stored
    params + source='agent'. Positive control: patched create_booking is reached."""
    store = FakePendingActionStore()
    # Pre-populate the pending action for CTX
    stored_params = {"facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"}
    action_id = await store.propose(CTX, "book", stored_params)

    booking_result = {
        "id": "f-court1_2027-01-15_09:00", "status": "confirmed",
        "facility_id": "f-court1", "date": "2027-01-15", "start": "09:00", "end": "10:00",
    }

    with (
        patch("sport_slot.services.agent.orchestrator.create_booking",
              new_callable=AsyncMock, return_value=booking_result) as mock_create,
        patch("sport_slot.services.agent.orchestrator._write_preference_memory"),
    ):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    # create_booking called exactly once with the stored params + source="agent"
    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args
    assert call_kwargs.args[3] == "f-court1"     # facility_id
    assert call_kwargs.args[4] == "2027-01-15"   # date
    assert call_kwargs.args[5] == "09:00"        # start
    assert call_kwargs.kwargs.get("source") == "agent"

    # NL success reply
    assert "f-court1" in reply or "tennis court" in reply.lower() or "booked" in reply.lower()


@pytest.mark.asyncio
async def test_execute_confirm_preference_memory_write_called():
    """Preference memory is called with the correct facility_id and start_time."""
    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "book", {
        "facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"
    })
    captured = []

    def _capture(ctx, client, fid, start):
        captured.append((fid, start))

    with (
        patch("sport_slot.services.agent.orchestrator.create_booking",
              new_callable=AsyncMock, return_value={"id": "x", "status": "confirmed",
                                                    "end": "10:00"}),
        patch("sport_slot.services.agent.orchestrator._write_preference_memory",
              side_effect=_capture),
    ):
        await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert captured == [("f-court1", "09:00")]


# ── EXECUTE: expired / missing ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_expired_action_does_not_call_create_booking():
    """consume returns None (expired/missing) → create_booking NOT called → safe reply."""
    store = FakePendingActionStore()  # empty — nothing to consume

    with (
        patch("sport_slot.services.agent.orchestrator.create_booking",
              new_callable=AsyncMock) as mock_create,
    ):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, "no-such-id")

    mock_create.assert_not_called()
    assert "expired" in reply.lower() or "please ask again" in reply.lower()


# ── EXECUTE: scope isolation ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_different_uid_cannot_consume_pending_action():
    """A pending action written for CTX (uid=u1) cannot be consumed by CTX_OTHER (uid=u-other).

    The key is scoped by tenant+uid, so CTX_OTHER gets a miss → create_booking NOT called.
    """
    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "book", {
        "facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"
    })

    with (
        patch("sport_slot.services.agent.orchestrator.create_booking",
              new_callable=AsyncMock) as mock_create,
    ):
        # CTX_OTHER tries to execute with the action_id from CTX
        reply = await run_agent_confirm(
            CTX_OTHER, _firestore_client(), FakeLock(), store, action_id
        )

    mock_create.assert_not_called()
    assert "expired" in reply.lower() or "please ask again" in reply.lower()

    # Original action still unconsumed
    remaining = await store.consume(CTX, action_id)
    assert remaining is not None


# ── GATE INTEGRITY ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_propose_turn_never_executes_create_booking():
    """The message (propose) path NEVER calls create_booking, regardless of tool output."""
    fc = AgentResponse(
        function_call=("book", {"facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"}),
        text=None,
    )
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=AVAIL_BOOKABLE),
        patch("sport_slot.services.agent.orchestrator.create_booking",
              new_callable=AsyncMock) as mock_create,
    ):
        # This is the propose (message) path
        await run_agent(CTX, _firestore_client(), store, "Book court 1 at 9am")

    mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_execute_turn_makes_no_vertex_call():
    """The execute (confirm) path makes NO Vertex/generate calls."""
    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "book", {
        "facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"
    })

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock) as mock_gen,
        patch("sport_slot.services.agent.orchestrator.create_booking",
              new_callable=AsyncMock, return_value={"id": "x", "status": "confirmed",
                                                    "end": "10:00"}),
        patch("sport_slot.services.agent.orchestrator._write_preference_memory"),
    ):
        await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    mock_gen.assert_not_called()


# ── SOURCE / AUDIT differentiation ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_booking_source_agent_writes_agent_event():
    """create_booking(source='agent') writes event_type 'agent.booking_created'."""
    from sport_slot.services.bookings import create_booking

    with (
        patch("sport_slot.services.bookings.BookingRepository.booked_starts",
              return_value=set()),
        patch("sport_slot.services.bookings.AuditRepository.write_event") as mock_audit,
    ):
        await create_booking(
            CTX, _firestore_client(), FakeLock(),
            "f-court1", "2027-01-15", "09:00",
            source="agent",
        )

    assert mock_audit.call_args.args[0] == "agent.booking_created"


@pytest.mark.asyncio
async def test_create_booking_source_default_writes_booking_created():
    """create_booking() with default source writes 'booking.created' (manual path unchanged)."""
    from sport_slot.services.bookings import create_booking

    with (
        patch("sport_slot.services.bookings.BookingRepository.booked_starts",
              return_value=set()),
        patch("sport_slot.services.bookings.AuditRepository.write_event") as mock_audit,
    ):
        await create_booking(
            CTX, _firestore_client(), FakeLock(),
            "f-court1", "2027-01-15", "09:00",
        )

    assert mock_audit.call_args.args[0] == "booking.created"


# ── residents-only gate ───────────────────────────────────────────────────────

async def test_agent_query_non_resident_blocked(make_client):
    """Non-resident role → 403 FORBIDDEN_ROLE before any agent logic runs."""
    from unittest.mock import AsyncMock, MagicMock
    from sport_slot.dependencies import get_firestore_client, get_lock_service, get_redis_client

    admin_claims = {
        "uid": "u-admin", "role": "tenant_admin",
        "tenant_id": "t-1", "tenant_slug": "demo", "household_id": "h-1",
    }
    redis_mock = AsyncMock()

    with patch("sport_slot.auth.dependency.fb_auth.verify_id_token", return_value=admin_claims):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: MagicMock()
            client._transport.app.dependency_overrides[get_redis_client] = lambda: redis_mock
            client._transport.app.dependency_overrides[get_lock_service] = lambda: MagicMock()
            resp = await client.post(
                "/api/v1/agent/query",
                json={"message": "hello"},
                headers={
                    "Authorization": "Bearer fake",
                    "Host": "demo.sportbook.chandraailabs.com",
                },
            )

    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN_ROLE"


# ── PendingActionStore unit tests (Redis mocked) ──────────────────────────────

@pytest.mark.asyncio
async def test_pending_action_store_propose_sets_key_with_ttl():
    """propose() writes main key + latest-pointer key, both with 5-min TTL."""
    from sport_slot.services.agent.pending_actions import PendingActionStore

    redis = AsyncMock()
    store = PendingActionStore(redis)
    action_id = await store.propose(CTX, "book", {"facility_id": "f1"})

    assert len(action_id) == 32  # uuid4 hex
    assert redis.set.call_count == 2  # main key + latest pointer

    calls = redis.set.call_args_list
    # Main key
    main_key = calls[0].args[0]
    assert main_key.startswith(f"agent_pending:{CTX.tenant_id}:{CTX.uid}:")
    assert calls[0].kwargs["px"] == 300_000
    # Latest-pointer key
    latest_key = calls[1].args[0]
    assert latest_key == f"agent_pending_latest:{CTX.tenant_id}:{CTX.uid}:book"
    assert calls[1].kwargs["px"] == 300_000


@pytest.mark.asyncio
async def test_pending_action_store_consume_reads_deletes_and_returns():
    """consume() reads, deletes (single-use), and returns the stored dict."""
    from sport_slot.services.agent.pending_actions import PendingActionStore

    redis = AsyncMock()
    payload = '{"action_type": "book", "params": {"facility_id": "f1"}}'
    redis.get.return_value = payload.encode()
    store = PendingActionStore(redis)

    result = await store.consume(CTX, "some-id")
    assert result == {"action_type": "book", "params": {"facility_id": "f1"}}
    redis.delete.assert_called_once()


@pytest.mark.asyncio
async def test_pending_action_store_consume_miss_returns_none():
    """consume() returns None when the key is missing (expired or never written)."""
    from sport_slot.services.agent.pending_actions import PendingActionStore

    redis = AsyncMock()
    redis.get.return_value = None
    store = PendingActionStore(redis)

    result = await store.consume(CTX, "missing-id")
    assert result is None
    redis.delete.assert_not_called()


@pytest.mark.asyncio
async def test_pending_action_store_consume_redis_error_returns_none():
    """consume() returns None (fail closed) when Redis raises."""
    from sport_slot.services.agent.pending_actions import PendingActionStore

    redis = AsyncMock()
    redis.get.side_effect = RuntimeError("connection refused")
    store = PendingActionStore(redis)

    result = await store.consume(CTX, "some-id")
    assert result is None


def test_pending_action_store_key_scope():
    """_key encodes tenant_id and uid so different residents get different keys."""
    from sport_slot.services.agent.pending_actions import PendingActionStore

    ctx_b = TenantContext(uid="u-other", tenant_id="t-1", tenant_slug="demo",
                          role="resident", household_id="h-2")
    key_a = PendingActionStore._key(CTX, "abc")
    key_b = PendingActionStore._key(ctx_b, "abc")
    assert key_a != key_b
    assert CTX.uid in key_a
    assert ctx_b.uid in key_b


# ── run_agent_confirm error paths ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_confirm_409_returns_slot_taken_message():
    """create_booking raises 409 ApiError → 'slot taken' NL reply."""
    from sport_slot.api.errors import ApiError

    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "book", {
        "facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"
    })

    with patch("sport_slot.services.agent.orchestrator.create_booking",
               new_callable=AsyncMock,
               side_effect=ApiError(409, "SLOT_CONTENDED", "contended")):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert "taken" in reply.lower() or "available times" in reply.lower()


@pytest.mark.asyncio
async def test_execute_confirm_422_returns_unavailable_message():
    """create_booking raises 422/SLOT_NOT_BOOKABLE → slot-specific 'can't be booked' NL reply."""
    from sport_slot.api.errors import ApiError

    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "book", {
        "facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"
    })

    with patch("sport_slot.services.agent.orchestrator.create_booking",
               new_callable=AsyncMock,
               side_effect=ApiError(422, "SLOT_NOT_BOOKABLE", "not bookable")):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert "can't be booked" in reply.lower() or "right now" in reply.lower()


@pytest.mark.asyncio
async def test_execute_confirm_503_returns_system_unavailable_message():
    """create_booking raises 503 ApiError → 'temporarily unavailable' NL reply."""
    from sport_slot.api.errors import ApiError

    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "book", {
        "facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"
    })

    with patch("sport_slot.services.agent.orchestrator.create_booking",
               new_callable=AsyncMock,
               side_effect=ApiError(503, "LOCK_UNAVAILABLE", "unavailable")):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert "temporarily unavailable" in reply.lower()


@pytest.mark.asyncio
async def test_execute_confirm_other_api_error_returns_generic_message():
    """Unknown ApiError status → generic fallback."""
    from sport_slot.api.errors import ApiError

    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "book", {
        "facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"
    })

    with patch("sport_slot.services.agent.orchestrator.create_booking",
               new_callable=AsyncMock,
               side_effect=ApiError(500, "INTERNAL", "internal error")):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert "wasn't able" in reply.lower() or "try again" in reply.lower()


@pytest.mark.asyncio
async def test_execute_confirm_unknown_action_type_returns_fallback():
    """Pending action with unknown action_type → safe fallback."""
    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "transfer", {"booking_id": "bk-1"})

    reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert "sorry" in reply.lower() or "ask again" in reply.lower()


@pytest.mark.asyncio
async def test_execute_confirm_preference_write_failure_does_not_fail_booking():
    """Preference memory write failure is best-effort: booking still confirmed."""
    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "book", {
        "facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"
    })

    with patch("sport_slot.services.agent.orchestrator.create_booking",
               new_callable=AsyncMock, return_value={"id": "x", "status": "confirmed",
                                                     "end": "10:00"}), \
         patch("sport_slot.services.agent.orchestrator._write_preference_memory",
               side_effect=RuntimeError("profile db down")):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert "booked" in reply.lower()


# ── _write_preference_memory unit tests ───────────────────────────────────────

def test_write_preference_memory_updates_correct_sport_field():
    """_write_preference_memory calls update with dot-path for the sport key."""
    from sport_slot.services.agent.orchestrator import _write_preference_memory

    client = _firestore_client()
    with patch("sport_slot.services.agent.orchestrator.UserProfileRepository.update") as mock_upd:
        _write_preference_memory(CTX, client, "f-court1", "09:00")

    mock_upd.assert_called_once()
    uid_arg, data_arg = mock_upd.call_args.args
    assert uid_arg == CTX.uid
    assert "preferences.last_booked.tennis" in data_arg
    assert data_arg["preferences.last_booked.tennis"] == {
        "facility_id": "f-court1", "start_time": "09:00"
    }


def test_write_preference_memory_noop_when_facility_missing():
    """_write_preference_memory does nothing if FacilityRepository.get returns None."""
    from sport_slot.services.agent.orchestrator import _write_preference_memory

    with patch("sport_slot.services.agent.orchestrator.FacilityRepository.get",
               return_value=None), \
         patch("sport_slot.services.agent.orchestrator.UserProfileRepository.update") as mock_upd:
        _write_preference_memory(CTX, MagicMock(), "f-court1", "09:00")

    mock_upd.assert_not_called()


# ── 6.3: agent-path notification regression ───────────────────────────────────

@pytest.mark.asyncio
async def test_create_booking_source_agent_enqueues_notification():
    """create_booking(source='agent') enqueues a booking_confirmed notification.

    Regression guard: before 6.3 the enqueue_notification call lived only in
    the HTTP router handler, so agent-confirmed bookings never produced emails.
    """
    from sport_slot.services.bookings import create_booking

    profile = {"email": "jane@example.com", "display_name": "Jane Doe"}

    with (
        patch("sport_slot.services.bookings.BookingRepository.booked_starts",
              return_value=set()),
        patch("sport_slot.services.bookings.AuditRepository.write_event"),
        patch("sport_slot.services.bookings.UserProfileRepository.get",
              return_value=profile),
        patch("sport_slot.services.bookings.enqueue_notification") as mock_enqueue,
    ):
        await create_booking(
            CTX, _firestore_client(), FakeLock(),
            "f-court1", "2027-01-15", "09:00",
            source="agent",
        )

    mock_enqueue.assert_called_once()
    kwargs = mock_enqueue.call_args.kwargs
    assert kwargs["event_type"] == "booking_confirmed"
    assert kwargs["to"] == "jane@example.com"
    assert kwargs["params"]["date"] == "2027-01-15"
    assert kwargs["params"]["start_time"] == "09:00"
    assert kwargs["params"]["end_time"] == "10:00"


# ── _dispatch_book error paths ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_propose_book_avail_check_exception_returns_safe_reply():
    """get_availability raises → safe reply, no pending action, create_booking not called."""
    fc = AgentResponse(
        function_call=("book", {"facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"}),
        text=None,
    )
    store = FakePendingActionStore()

    with patch("sport_slot.services.agent.vertex_client.generate",
               new_callable=AsyncMock, return_value=fc), \
         patch("sport_slot.services.agent.vertex_client.classify_output",
               new_callable=AsyncMock, return_value=True), \
         patch("sport_slot.services.agent.orchestrator.get_availability",
               side_effect=RuntimeError("service unavailable")), \
         patch("sport_slot.services.agent.orchestrator.create_booking",
               new_callable=AsyncMock) as mock_create:
        turn = await run_agent(CTX, _firestore_client(), store, "Book court")

    mock_create.assert_not_called()
    assert len(store.propose_calls) == 0
    assert turn.pending_action_id is None
    assert "couldn't verify" in turn.reply.lower() or "try again" in turn.reply.lower()


@pytest.mark.asyncio
async def test_propose_book_store_propose_exception_returns_safe_reply():
    """store.propose raises Redis error → safe reply, no pending_action_id."""
    fc = AgentResponse(
        function_call=("book", {"facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"}),
        text=None,
    )

    class _FailStore:
        async def propose(self, *a, **k):
            raise RuntimeError("redis down")
        async def consume(self, *a, **k):
            return None

    with patch("sport_slot.services.agent.vertex_client.generate",
               new_callable=AsyncMock, return_value=fc), \
         patch("sport_slot.services.agent.vertex_client.classify_output",
               new_callable=AsyncMock, return_value=True), \
         patch("sport_slot.services.agent.orchestrator.get_availability",
               return_value=AVAIL_BOOKABLE), \
         patch("sport_slot.services.agent.orchestrator.create_booking",
               new_callable=AsyncMock) as mock_create:
        turn = await run_agent(CTX, _firestore_client(), _FailStore(), "Book court")

    mock_create.assert_not_called()
    assert turn.pending_action_id is None


# ── _dispatch_readonly error / edge paths ─────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_readonly_avail_exception_returns_error_json():
    """get_availability raises inside _dispatch_readonly → error JSON returned to Turn 2."""
    from sport_slot.services.agent.vertex_client import AgentResponse as AR
    fc = AR(function_call=("check_availability",
                           {"facility_id": "f-court1", "date": "2027-01-15"}), text=None)
    text_resp = AR(function_call=None, text="Sorry, couldn't check.")

    with patch("sport_slot.services.agent.vertex_client.generate",
               new_callable=AsyncMock, side_effect=[fc, text_resp]), \
         patch("sport_slot.services.agent.vertex_client.classify_output",
               new_callable=AsyncMock, return_value=True), \
         patch("sport_slot.services.agent.orchestrator.get_availability",
               side_effect=RuntimeError("backend down")):
        store = FakePendingActionStore()
        turn = await run_agent(CTX, _firestore_client(), store, "Is court free?")

    assert turn.reply == "Sorry, couldn't check."


# ── pending_action_summary (Slice 5a) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_propose_book_returns_structured_summary():
    """Successful book propose → turn.pending_action_summary contains all fields."""
    fc = AgentResponse(
        function_call=("book", {"facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"}),
        text=None,
    )
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=AVAIL_BOOKABLE),
        patch("sport_slot.services.agent.orchestrator.create_booking",
              new_callable=AsyncMock),
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Book court")

    s = turn.pending_action_summary
    assert s is not None
    assert s["action_type"] == "book"
    assert s["facility_id"] == "f-court1"
    assert s["facility_name"] == "Tennis Court 1"
    assert s["sport"] == "tennis"
    assert s["date"] == "2027-01-15"
    assert s["start"] == "09:00"
    assert s["end"] == "10:00"


@pytest.mark.asyncio
async def test_propose_book_hallucination_returns_no_summary():
    """Hallucinated facility_id → turn.pending_action_summary is None."""
    fc = AgentResponse(
        function_call=("book", {"facility_id": "FAKE-XYZ", "date": "2027-01-15", "start": "09:00"}),
        text=None,
    )
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.agent.orchestrator.get_availability"),
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Book FAKE-XYZ")

    assert turn.pending_action_summary is None
    assert turn.pending_action_id is None


@pytest.mark.asyncio
async def test_propose_book_unbookable_slot_returns_no_summary():
    """Unbookable slot → turn.pending_action_summary is None."""
    fc = AgentResponse(
        function_call=("book", {"facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"}),
        text=None,
    )
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=AVAIL_TAKEN),
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Book court")

    assert turn.pending_action_summary is None
    assert turn.pending_action_id is None


def test_agent_reply_model_includes_pending_action_summary_field():
    """AgentReply serialises pending_action_summary: populated and None both work."""
    from sport_slot.api.v1.agent import AgentReply

    with_summary = AgentReply(
        reply="Book Tennis Court 1 on 2027-01-15 at 09:00 — confirm?",
        pending_action_id="abc123",
        pending_action_summary={
            "action_type": "book", "facility_id": "f-court1",
            "facility_name": "Tennis Court 1", "sport": "tennis",
            "date": "2027-01-15", "start": "09:00", "end": "10:00",
        },
    )
    data = with_summary.model_dump()
    assert data["pending_action_summary"]["action_type"] == "book"
    assert data["pending_action_summary"]["facility_name"] == "Tennis Court 1"

    without_summary = AgentReply(reply="Sure!", pending_action_id=None)
    assert without_summary.model_dump()["pending_action_summary"] is None


# ── 6.4(a): error-code mapping in run_agent_confirm ──────────────────────────

@pytest.mark.asyncio
async def test_confirm_book_slot_contended_returns_contended_message():
    """SLOT_CONTENDED → 'just taken' message."""
    from sport_slot.api import error_codes as ec
    from sport_slot.api.errors import ApiError

    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "book", {
        "facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"
    })
    with patch("sport_slot.services.agent.orchestrator.create_booking",
               new_callable=AsyncMock,
               side_effect=ApiError(409, ec.SLOT_CONTENDED, "contended")):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert "just taken" in reply.lower() or "other available times" in reply.lower()


@pytest.mark.asyncio
async def test_confirm_book_quota_exceeded_returns_quota_message_with_sport():
    """BOOKING_QUOTA_EXCEEDED → 'daily booking limit' with sport name in reply."""
    from sport_slot.api import error_codes as ec
    from sport_slot.api.errors import ApiError

    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "book", {
        "facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"
    })
    with patch("sport_slot.services.agent.orchestrator.create_booking",
               new_callable=AsyncMock,
               side_effect=ApiError(409, ec.BOOKING_QUOTA_EXCEEDED, "quota exceeded")):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert "daily booking limit" in reply.lower()
    assert "tennis" in reply.lower()


@pytest.mark.asyncio
async def test_confirm_book_already_booked_returns_facility_and_time():
    """ALREADY_BOOKED → facility name + date + time in reply."""
    from sport_slot.api import error_codes as ec
    from sport_slot.api.errors import ApiError

    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "book", {
        "facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"
    })
    with patch("sport_slot.services.agent.orchestrator.create_booking",
               new_callable=AsyncMock,
               side_effect=ApiError(409, ec.ALREADY_BOOKED, "already booked")):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert "already booked" in reply.lower()
    assert "2027-01-15" in reply
    assert "09:00" in reply


@pytest.mark.asyncio
async def test_confirm_book_lock_unavailable_returns_temporary_message():
    """LOCK_UNAVAILABLE → 'temporarily unavailable' reply."""
    from sport_slot.api import error_codes as ec
    from sport_slot.api.errors import ApiError

    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "book", {
        "facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"
    })
    with patch("sport_slot.services.agent.orchestrator.create_booking",
               new_callable=AsyncMock,
               side_effect=ApiError(503, ec.LOCK_UNAVAILABLE, "unavailable")):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert "temporarily unavailable" in reply.lower()


@pytest.mark.asyncio
async def test_confirm_book_unknown_error_code_returns_generic():
    """Unknown error code → generic 'something went wrong' fallback."""
    from sport_slot.api.errors import ApiError

    store = FakePendingActionStore()
    action_id = await store.propose(CTX, "book", {
        "facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"
    })
    with patch("sport_slot.services.agent.orchestrator.create_booking",
               new_callable=AsyncMock,
               side_effect=ApiError(500, "INTERNAL", "internal error")):
        reply = await run_agent_confirm(CTX, _firestore_client(), FakeLock(), store, action_id)

    assert "something went wrong" in reply.lower() or "try again" in reply.lower()


# ── 6.4(b): propose-time quota check in _dispatch_book ───────────────────────

@pytest.mark.asyncio
async def test_propose_book_quota_at_limit_refuses_without_writing_pending():
    """quota=1 and user has 1 confirmed tennis booking on same date →
    propose-time check fires; no pending action written, create_booking NOT called."""
    fc = AgentResponse(
        function_call=("book", {"facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"}),
        text=None,
    )
    store = FakePendingActionStore()
    existing = {
        "id": "f-court1_2027-01-15_08:00", "uid": CTX.uid,
        "facility_id": "f-court1", "date": "2027-01-15",
        "start": "08:00", "end": "09:00", "status": "confirmed",
    }
    policy_inst = MagicMock()
    policy_inst.tenant_timezone.return_value = "UTC"
    policy_inst.get.return_value = "1"  # quota_limit = 1

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=AVAIL_BOOKABLE),
        patch("sport_slot.services.agent.orchestrator.PolicyService",
              return_value=policy_inst),
        patch("sport_slot.services.agent.orchestrator.list_my_bookings",
              return_value={"items": [existing], "next_cursor": None}),
        patch("sport_slot.services.agent.orchestrator.create_booking",
              new_callable=AsyncMock) as mock_create,
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Book another tennis slot")

    assert turn.pending_action_id is None
    assert len(store.propose_calls) == 0
    mock_create.assert_not_called()
    assert "daily booking limit" in turn.reply.lower()
    assert "tennis" in turn.reply.lower()


@pytest.mark.asyncio
async def test_propose_book_quota_below_limit_proceeds_normally():
    """quota=2, user has 1 confirmed booking → quota check passes, pending action written."""
    fc = AgentResponse(
        function_call=("book", {"facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"}),
        text=None,
    )
    store = FakePendingActionStore()
    existing = {
        "id": "f-court1_2027-01-15_08:00", "uid": CTX.uid,
        "facility_id": "f-court1", "date": "2027-01-15",
        "start": "08:00", "end": "09:00", "status": "confirmed",
    }
    policy_inst = MagicMock()
    policy_inst.tenant_timezone.return_value = "UTC"
    policy_inst.get.return_value = "2"  # quota_limit = 2

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=AVAIL_BOOKABLE),
        patch("sport_slot.services.agent.orchestrator.PolicyService",
              return_value=policy_inst),
        patch("sport_slot.services.agent.orchestrator.list_my_bookings",
              return_value={"items": [existing], "next_cursor": None}),
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Book tennis at 9am")

    assert turn.pending_action_id is not None
    assert len(store.propose_calls) == 1


@pytest.mark.asyncio
async def test_propose_book_quota_policy_error_falls_through_to_propose():
    """PolicyService.get() raises in quota check → exception caught, proposal proceeds normally."""
    fc = AgentResponse(
        function_call=("book", {"facility_id": "f-court1", "date": "2027-01-15", "start": "09:00"}),
        text=None,
    )
    store = FakePendingActionStore()
    policy_inst = MagicMock()
    policy_inst.tenant_timezone.return_value = "UTC"
    policy_inst.get.side_effect = RuntimeError("policy db down")

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=AVAIL_BOOKABLE),
        patch("sport_slot.services.agent.orchestrator.PolicyService",
              return_value=policy_inst),
        patch("sport_slot.services.agent.orchestrator.create_booking",
              new_callable=AsyncMock),
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Book tennis at 9am")

    # Policy error in quota check is caught; proposal still proceeds
    assert turn.pending_action_id is not None
    assert len(store.propose_calls) == 1


# ── 6.5(b): AM-past → PM guard in _dispatch_book ─────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_book_am_past_advances_to_pm():
    """LLM sends start=09:00 for a date in the past → AM/PM guard advances to 21:00.

    The pending action must carry the advanced start, not the original 09:00.
    Using a definitively past date (2020-01-15) to trigger the guard without
    needing to mock datetime.
    """
    fc = AgentResponse(
        function_call=("book", {"facility_id": "f-court1", "date": "2020-01-15", "start": "09:00"}),
        text=None,
    )
    store = FakePendingActionStore()
    pm_slot = {"start": "21:00", "end": "22:00", "bookable": True}
    avail_pm = {"facility_id": "f-court1", "date": "2020-01-15", "slots": [pm_slot]}

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=avail_pm),
        patch("sport_slot.services.agent.orchestrator.list_my_bookings",
              return_value={"items": [], "next_cursor": None}),
        patch("sport_slot.services.agent.orchestrator.create_booking",
              new_callable=AsyncMock),
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Book court at 9am")

    assert turn.pending_action_id is not None
    _, _, params = store.propose_calls[0]
    assert params["start"] == "21:00"  # advanced from 09:00
    assert params["facility_id"] == "f-court1"


@pytest.mark.asyncio
async def test_dispatch_book_am_future_not_advanced():
    """LLM sends start=09:00 for a future date → 09:00 is not past → no advancement."""
    fc = AgentResponse(
        function_call=("book", {"facility_id": "f-court1", "date": "2030-01-15", "start": "09:00"}),
        text=None,
    )
    store = FakePendingActionStore()

    with (
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=fc),
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
        patch("sport_slot.services.agent.orchestrator.get_availability",
              return_value=AVAIL_BOOKABLE),
        patch("sport_slot.services.agent.orchestrator.list_my_bookings",
              return_value={"items": [], "next_cursor": None}),
        patch("sport_slot.services.agent.orchestrator.create_booking",
              new_callable=AsyncMock),
    ):
        turn = await run_agent(CTX, _firestore_client(), store, "Book court at 9am")

    assert turn.pending_action_id is not None
    _, _, params = store.propose_calls[0]
    assert params["start"] == "09:00"  # not advanced
