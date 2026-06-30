import pytest
from unittest.mock import MagicMock, patch

from sport_slot.dependencies import get_firestore_client, get_lock_service
from sport_slot.notifications.email.templates import render_booking_confirmed
from sport_slot.repositories.bookings import (
    AlreadyBookedError,
    QuotaExceededError,
)

RESIDENT = {"uid": "u1", "role": "resident", "tenant_id": "t-1",
            "tenant_slug": "demo", "household_id": "h-1"}
AUTH = {"authorization": "Bearer fake"}
HOST = {"host": "demo.sportbook.chandraailabs.com"}
VERIFY = "sport_slot.auth.dependency.fb_auth.verify_id_token"
BOOKED = "sport_slot.api.v1.bookings.BookingRepository.booked_starts"
CREATE = "sport_slot.api.v1.bookings.create_booking_with_quota"
ENQUEUE = "sport_slot.services.bookings.enqueue_notification"

FACILITY = {"id": "f1", "active": True, "slot_duration_minutes": 60,
            "open_time": "06:00", "close_time": "22:00",
            "name": "Court 1", "sport": "Tennis"}
# Wide-horizon policy so a far-future date is cleanly bookable in tests
TENANT = {"policies": {"booking_horizon_days": 3650},
          "timezone": "Asia/Kolkata"}
BODY = {"facility_id": "f1", "date": "2027-01-15", "start": "18:00"}


class FakeLock:
    def __init__(self, token="tok", unavailable=False):
        self._token, self._unavailable = token, unavailable
        self.released = False

    @staticmethod
    def slot_key(*a):
        return ":".join(a)

    async def acquire(self, key, ttl_ms=10_000):
        from sport_slot.services.lock import LockUnavailableError
        if self._unavailable:
            raise LockUnavailableError("down")
        return self._token

    async def release(self, key, token):
        self.released = True


def _client(facility=FACILITY, tenant=TENANT, profile=None):
    client = MagicMock()
    tenant_doc = client.collection.return_value.document.return_value

    def _sub_collection(name):
        col = MagicMock()
        snap = col.document.return_value.get.return_value
        if name == "facilities":
            snap.exists = facility is not None
            snap.to_dict.return_value = facility
        elif name == "users":
            snap.exists = profile is not None
            snap.to_dict.return_value = profile
        return col

    tenant_doc.collection.side_effect = _sub_collection

    ten = tenant_doc.get.return_value
    ten.exists = True
    ten.to_dict.return_value = tenant
    return client


def _wire(client, app_client, lock):
    overrides = app_client._transport.app.dependency_overrides
    overrides[get_firestore_client] = lambda: client
    overrides[get_lock_service] = lambda: lock


async def test_booking_created(make_client):
    lock = FakeLock()
    with patch(VERIFY, return_value=RESIDENT), \
         patch(BOOKED, return_value=set()), \
         patch(CREATE) as create:
        async with make_client() as client:
            _wire(_client(), client, lock)
            resp = await client.post("/api/v1/bookings", json=BODY,
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == "f1_2027-01-15_18:00"
    assert body["status"] == "confirmed" and body["end"] == "19:00"
    create.assert_called_once()
    assert lock.released


async def test_quota_exceeded_409(make_client):
    lock = FakeLock()
    with patch(VERIFY, return_value=RESIDENT), \
         patch(BOOKED, return_value=set()), \
         patch(CREATE, side_effect=QuotaExceededError):
        async with make_client() as client:
            _wire(_client(), client, lock)
            resp = await client.post("/api/v1/bookings", json=BODY,
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 409
    assert resp.json()["code"] == "BOOKING_QUOTA_EXCEEDED"
    assert lock.released


async def test_already_booked_409(make_client):
    lock = FakeLock()
    with patch(VERIFY, return_value=RESIDENT), \
         patch(BOOKED, return_value=set()), \
         patch(CREATE, side_effect=AlreadyBookedError):
        async with make_client() as client:
            _wire(_client(), client, lock)
            resp = await client.post("/api/v1/bookings", json=BODY,
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 409
    assert resp.json()["code"] == "ALREADY_BOOKED"
    assert lock.released


async def test_contended_409(make_client):
    lock = FakeLock(token=None)
    with patch(VERIFY, return_value=RESIDENT), \
         patch(BOOKED, return_value=set()):
        async with make_client() as client:
            _wire(_client(), client, lock)
            resp = await client.post("/api/v1/bookings", json=BODY,
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 409
    assert resp.json()["code"] == "SLOT_CONTENDED"


async def test_lock_unavailable_503(make_client):
    lock = FakeLock(unavailable=True)
    with patch(VERIFY, return_value=RESIDENT), \
         patch(BOOKED, return_value=set()):
        async with make_client() as client:
            _wire(_client(), client, lock)
            resp = await client.post("/api/v1/bookings", json=BODY,
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 503
    assert resp.json()["code"] == "LOCK_UNAVAILABLE"


async def test_booked_slot_rejected_422(make_client):
    lock = FakeLock()
    with patch(VERIFY, return_value=RESIDENT), \
         patch(BOOKED, return_value={"18:00"}):
        async with make_client() as client:
            _wire(_client(), client, lock)
            resp = await client.post("/api/v1/bookings", json=BODY,
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 422
    assert resp.json()["code"] == "SLOT_NOT_BOOKABLE"


async def test_off_grid_start_422(make_client):
    lock = FakeLock()
    with patch(VERIFY, return_value=RESIDENT), \
         patch(BOOKED, return_value=set()):
        async with make_client() as client:
            _wire(_client(), client, lock)
            resp = await client.post("/api/v1/bookings",
                                     json={**BODY, "start": "18:30"},
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 422


async def test_audit_written_on_create(make_client):
    lock = FakeLock()
    with patch(VERIFY, return_value=RESIDENT), \
         patch(BOOKED, return_value=set()), \
         patch(CREATE), \
         patch("sport_slot.api.v1.bookings.AuditRepository.write_event") as audit:
        async with make_client() as client:
            _wire(_client(), client, lock)
            resp = await client.post("/api/v1/bookings", json=BODY,
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 201
    assert audit.call_args.args[0] == "booking.created"
    assert audit.call_args.args[1] == "u1"


async def test_booking_confirmed_enqueues_notification(make_client):
    lock = FakeLock()
    profile = {"email": "jane@example.com", "display_name": "Jane Doe"}
    tenant = {**TENANT, "display_name": "Demo Society"}
    with patch(VERIFY, return_value=RESIDENT), \
         patch(BOOKED, return_value=set()), \
         patch(CREATE), \
         patch(ENQUEUE) as enqueue:
        async with make_client() as client:
            _wire(_client(tenant=tenant, profile=profile), client, lock)
            resp = await client.post("/api/v1/bookings", json=BODY,
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 201
    enqueue.assert_called_once()
    kwargs = enqueue.call_args.kwargs
    assert kwargs["event_type"] == "booking_confirmed"
    assert kwargs["to"] == "jane@example.com"
    assert kwargs["params"] == {
        "user_name": "Jane Doe",
        "tenant_name": "Demo Society",
        "facility": "Court 1",
        "sport": "Tennis",
        "date": "2027-01-15",
        "start_time": "18:00",
        "end_time": "19:00",
        "booking_id": "f1_2027-01-15_18:00",
    }
    # Proves the params are accepted by the real renderer (no 422 at the worker).
    rendered = render_booking_confirmed(**kwargs["params"])
    assert "Court 1" in rendered.html


async def test_booking_succeeds_even_if_enqueue_fails(make_client):
    """Best-effort proof: enqueue failure must never block a confirmed booking."""
    lock = FakeLock()
    profile = {"email": "jane@example.com", "display_name": "Jane Doe"}
    with patch(VERIFY, return_value=RESIDENT), \
         patch(BOOKED, return_value=set()), \
         patch(CREATE), \
         patch(ENQUEUE, side_effect=Exception("Cloud Tasks unavailable")):
        async with make_client() as client:
            _wire(_client(profile=profile), client, lock)
            resp = await client.post("/api/v1/bookings", json=BODY,
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 201
    assert resp.json()["status"] == "confirmed"


async def test_booking_confirmed_skips_enqueue_when_no_profile_email(make_client):
    """No profile/email resolvable → enqueue is skipped, not crashed."""
    lock = FakeLock()
    with patch(VERIFY, return_value=RESIDENT), \
         patch(BOOKED, return_value=set()), \
         patch(CREATE), \
         patch(ENQUEUE) as enqueue:
        async with make_client() as client:
            _wire(_client(profile=None), client, lock)
            resp = await client.post("/api/v1/bookings", json=BODY,
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 201
    enqueue.assert_not_called()


def test_cancelled_document_is_superseded():
    """Lifecycle: create → cancel → rebook must succeed (3.6.1)."""
    from sport_slot.repositories.bookings import create_booking_with_quota

    repo = MagicMock()
    txn = MagicMock()
    repo._client.transaction.return_value = txn

    cancelled_snap = MagicMock()
    cancelled_snap.exists = True
    cancelled_snap.to_dict.return_value = {"status": "cancelled"}

    def fake_transactional(fn):
        def runner(transaction):
            return fn(transaction)
        return runner

    with patch("google.cloud.firestore.transactional", fake_transactional):
        txn.get.side_effect = [iter([]), iter([cancelled_snap])]
        create_booking_with_quota(repo, "b1", {"status": "confirmed"},
                                  "u9", "2026-06-13", quota=1)
    ref = repo._collection.document.return_value
    txn.set.assert_called_once_with(ref, {"status": "confirmed"})
    txn.create.assert_not_called()


# ── 6.6: quota-by-sport ───────────────────────────────────────────────────────

def _fake_transactional(fn):
    def runner(transaction):
        return fn(transaction)
    return runner


def _make_booking_snap(facility_id: str) -> MagicMock:
    snap = MagicMock()
    snap.to_dict.return_value = {"facility_id": facility_id, "status": "confirmed"}
    return snap


def test_quota_cross_sport_does_not_block():
    """A confirmed tennis booking must NOT consume the badminton quota.

    Policy: max_slots_per_user_per_sport_per_day = 1.
    User already has a tennis booking today.
    Attempt to book badminton today must succeed (quota not exceeded).
    """
    from sport_slot.repositories.bookings import create_booking_with_quota

    TENNIS_FAC = {"id": "f-tennis", "sport": "tennis", "active": True}
    BADMINTON_FAC = {"id": "f-badminton", "sport": "badminton", "active": True}

    existing = _make_booking_snap("f-tennis")   # tennis booking already exists
    new_snap = MagicMock()
    new_snap.exists = False                      # no existing badminton doc

    repo = MagicMock()
    txn = MagicMock()
    repo._client.transaction.return_value = txn

    with patch("google.cloud.firestore.transactional", _fake_transactional):
        txn.get.side_effect = [iter([existing]), iter([new_snap])]
        # Must NOT raise — the tennis booking does not count toward badminton quota
        create_booking_with_quota(
            repo, "bk-badminton-new", {"status": "confirmed"},
            "u1", "2027-01-15", quota=1,
            sport="badminton", facilities=[TENNIS_FAC, BADMINTON_FAC],
        )

    txn.create.assert_called_once()  # booking written


def test_quota_same_sport_raises():
    """A confirmed tennis booking DOES consume the tennis quota.

    Policy: max_slots_per_user_per_sport_per_day = 1.
    User already has a tennis booking today.
    Attempt to book another tennis slot must raise QuotaExceededError.
    """
    from sport_slot.repositories.bookings import create_booking_with_quota

    TENNIS_FAC = {"id": "f-tennis", "sport": "tennis", "active": True}

    existing = _make_booking_snap("f-tennis")   # tennis booking already exists

    repo = MagicMock()
    txn = MagicMock()
    repo._client.transaction.return_value = txn

    with patch("google.cloud.firestore.transactional", _fake_transactional):
        txn.get.side_effect = [iter([existing])]
        with pytest.raises(QuotaExceededError):
            create_booking_with_quota(
                repo, "bk-tennis-new", {"status": "confirmed"},
                "u1", "2027-01-15", quota=1,
                sport="tennis", facilities=[TENNIS_FAC],
            )


# ── Bug 1: /bookings/mine endpoint passes from_date ──────────────────────────

async def test_my_bookings_endpoint_passes_from_date(make_client):
    """The /bookings/mine endpoint must call list_my_bookings with a non-None from_date
    (tenant-local today) so confirmed upcoming bookings are returned even when >20
    older/cancelled docs exist in Firestore and would otherwise push them off page 1."""
    upcoming = {
        "id": "b1", "status": "confirmed", "date": "2030-01-01",
        "start": "09:00", "end": "10:00", "facility_id": "f1",
        "uid": "u1", "household_id": "h-1",
        "created_at": None, "cancelled_at": None, "cancellable": True,
    }
    with patch(VERIFY, return_value=RESIDENT), \
         patch("sport_slot.api.v1.bookings.list_my_bookings",
               return_value={"items": [upcoming], "next_cursor": None}) as mock_lmb:
        async with make_client() as client:
            _wire(_client(), client, FakeLock())
            resp = await client.get("/api/v1/bookings/mine", headers={**AUTH, **HOST})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["id"] == "b1"
    _, kwargs = mock_lmb.call_args
    # Endpoint must pass a non-None from_date so the Firestore query has a date filter.
    assert "from_date" in kwargs
    assert kwargs["from_date"] is not None


# ── Bug 2: _filter_cancel_candidates with inactive facility ──────────────────

def test_filter_cancel_finds_booking_on_inactive_facility():
    """Booking on a deactivated court must appear as cancellable when the full
    facility list (active + inactive) is supplied.  Previously, an active-only
    list caused fac=None → continue → n_can=0, n_late=0."""
    import datetime
    from sport_slot.services.agent.orchestrator import _filter_cancel_candidates

    inactive_fac = {"id": "f-tennis", "sport": "tennis", "active": False}
    booking = {
        "id": "b1", "facility_id": "f-tennis",
        "status": "confirmed", "date": "2030-01-15", "start": "10:00",
    }
    # 3 hours before slot; buffer=2h → deadline=08:00 → now=07:00 < deadline → cancellable
    now_local = datetime.datetime(2030, 1, 15, 7, 0)

    # Pre-fix behaviour: empty (active-only) facilities list silently drops the booking
    cancellable, too_late = _filter_cancel_candidates(
        [booking], [], "tennis", None, now_local, buffer_hours=2
    )
    assert len(cancellable) == 0 and len(too_late) == 0

    # Post-fix: inactive facility included → booking found and is cancellable
    cancellable, too_late = _filter_cancel_candidates(
        [booking], [inactive_fac], "tennis", None, now_local, buffer_hours=2
    )
    assert len(cancellable) == 1
    assert cancellable[0]["id"] == "b1"


def test_filter_cancel_respects_buffer_for_inactive_facility_booking():
    """Inactive-facility booking PAST the cancellation buffer must land in
    too_late, not in cancellable — fixing Bug 2 must not introduce false-positives."""
    import datetime
    from sport_slot.services.agent.orchestrator import _filter_cancel_candidates

    inactive_fac = {"id": "f-tennis", "sport": "tennis", "active": False}
    booking = {
        "id": "b1", "facility_id": "f-tennis",
        "status": "confirmed", "date": "2030-01-15", "start": "10:00",
    }
    # 1 hour before slot; buffer=2h → deadline=08:00 → now=09:00 > deadline → NOT cancellable
    now_local = datetime.datetime(2030, 1, 15, 9, 0)

    cancellable, too_late = _filter_cancel_candidates(
        [booking], [inactive_fac], "tennis", None, now_local, buffer_hours=2
    )
    assert len(cancellable) == 0  # past buffer — no false-positive
    assert len(too_late) == 1    # correctly classified
