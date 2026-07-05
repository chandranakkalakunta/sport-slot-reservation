import datetime
from unittest.mock import MagicMock, patch

from sport_slot.dependencies import get_firestore_client, get_lock_service

RESIDENT = {"uid": "u1", "role": "resident", "tenant_id": "t-1",
            "tenant_slug": "demo", "household_id": "h-1"}
OTHER = {"uid": "u2", "role": "resident", "tenant_id": "t-1",
         "tenant_slug": "demo", "household_id": "h-2"}
ADMIN = {"uid": "a1", "role": "tenant_admin", "tenant_id": "t-1",
         "tenant_slug": "demo", "household_id": "h-0"}
AUTH = {"authorization": "Bearer fake"}
HOST = {"host": "demo.slotsense.chandraailabs.com"}
VERIFY = "sport_slot.auth.dependency.fb_auth.verify_id_token"
GET = "sport_slot.api.v1.bookings.BookingRepository.get"
UPDATE = "sport_slot.api.v1.bookings.BookingRepository.update"

TENANT = {"policies": {}, "timezone": "Asia/Kolkata"}


def _booking(uid="u1", status="confirmed", days_ahead=5):
    date = (datetime.date.today()
            + datetime.timedelta(days=days_ahead)).isoformat()
    return {"id": f"f1_{date}_18:00", "uid": uid, "status": status,
            "date": date, "start": "18:00", "facility_id": "f1"}


def _client():
    client = MagicMock()
    ten = client.collection.return_value.document.return_value.get.return_value
    ten.exists = True
    ten.to_dict.return_value = TENANT
    return client


def _wire(app_client):
    overrides = app_client._transport.app.dependency_overrides
    overrides[get_firestore_client] = lambda: _client()
    overrides[get_lock_service] = lambda: MagicMock()


async def test_owner_cancels(make_client):
    booking = _booking()
    cancelled = {**booking, "status": "cancelled"}
    with patch(VERIFY, return_value=RESIDENT), \
         patch(GET, side_effect=[booking, cancelled]), \
         patch(UPDATE) as update:
        async with make_client() as client:
            _wire(client)
            resp = await client.post(f"/api/v1/bookings/{booking['id']}/cancel",
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 200
    changes = update.call_args.args[1]
    assert changes["status"] == "cancelled"
    assert changes["cancelled_by"] == "self"


async def test_admin_cancels_with_attribution(make_client):
    booking = _booking(uid="u1")
    with patch(VERIFY, return_value=ADMIN), \
         patch(GET, side_effect=[booking, {**booking, "status": "cancelled"}]), \
         patch(UPDATE) as update:
        async with make_client() as client:
            _wire(client)
            resp = await client.post(f"/api/v1/bookings/{booking['id']}/cancel",
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 200
    changes = update.call_args.args[1]
    assert changes["cancelled_by"] == "tenant_admin"
    assert changes["cancelled_by_uid"] == "a1"


async def test_other_resident_forbidden(make_client):
    with patch(VERIFY, return_value=OTHER), \
         patch(GET, return_value=_booking(uid="u1")):
        async with make_client() as client:
            _wire(client)
            resp = await client.post("/api/v1/bookings/x/cancel",
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 403
    assert resp.json()["code"] == "CANCELLATION_FORBIDDEN"


async def test_too_late_422(make_client):
    booking = _booking(days_ahead=0)  # today 18:00; tests run "now"
    # Force lateness regardless of wall clock: buffer 9999h
    tenant = {"policies": {"cancellation_buffer_hours": 9999},
              "timezone": "Asia/Kolkata"}
    client_mock = MagicMock()
    ten = client_mock.collection.return_value.document.return_value.get.return_value
    ten.exists = True
    ten.to_dict.return_value = tenant
    with patch(VERIFY, return_value=RESIDENT), \
         patch(GET, return_value=booking):
        async with make_client() as client:
            overrides = client._transport.app.dependency_overrides
            overrides[get_firestore_client] = lambda: client_mock
            overrides[get_lock_service] = lambda: MagicMock()
            resp = await client.post(f"/api/v1/bookings/{booking['id']}/cancel",
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 422
    assert resp.json()["code"] == "CANCELLATION_TOO_LATE"


async def test_already_cancelled_409(make_client):
    with patch(VERIFY, return_value=RESIDENT), \
         patch(GET, return_value=_booking(status="cancelled")):
        async with make_client() as client:
            _wire(client)
            resp = await client.post("/api/v1/bookings/x/cancel",
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 409
    assert resp.json()["code"] == "ALREADY_CANCELLED"


async def test_missing_404(make_client):
    with patch(VERIFY, return_value=RESIDENT), patch(GET, return_value=None):
        async with make_client() as client:
            _wire(client)
            resp = await client.post("/api/v1/bookings/x/cancel",
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 404


async def test_my_bookings_lists(make_client):
    items = [_booking(), _booking(days_ahead=6)]
    with patch(VERIFY, return_value=RESIDENT), \
         patch("sport_slot.api.v1.bookings.BookingRepository.list_for_uid",
               return_value=(items, None)) as lst:
        async with make_client() as client:
            _wire(client)
            resp = await client.get("/api/v1/bookings/mine",
                                    headers={**AUTH, **HOST})
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2
    assert lst.call_args.args[0] == "u1"


async def test_audit_written_on_cancel(make_client):
    booking = _booking()
    with patch(VERIFY, return_value=RESIDENT), \
         patch(GET, side_effect=[booking, {**booking, "status": "cancelled"}]), \
         patch(UPDATE), \
         patch("sport_slot.api.v1.bookings.AuditRepository.write_event") as audit:
        async with make_client() as client:
            _wire(client)
            resp = await client.post(f"/api/v1/bookings/{booking['id']}/cancel",
                                     headers={**AUTH, **HOST})
    assert resp.status_code == 200
    assert audit.call_args.args[0] == "booking.cancelled"


# ── cancellable flag on /bookings/mine ────────────────────────────────────

LIST = "sport_slot.api.v1.bookings.BookingRepository.list_for_uid"


async def test_my_bookings_cancellable_true_far_future(make_client):
    items = [_booking(days_ahead=5)]
    with patch(VERIFY, return_value=RESIDENT), patch(LIST, return_value=(items, None)):
        async with make_client() as client:
            _wire(client)
            resp = await client.get("/api/v1/bookings/mine", headers={**AUTH, **HOST})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["cancellable"] is True


async def test_my_bookings_cancellable_false_past_buffer(make_client):
    items = [_booking(days_ahead=0)]
    # Buffer 9999h ensures slot is past deadline regardless of wall clock.
    tenant = {"policies": {"cancellation_buffer_hours": 9999}, "timezone": "Asia/Kolkata"}
    client_mock = MagicMock()
    ten = client_mock.collection.return_value.document.return_value.get.return_value
    ten.exists = True
    ten.to_dict.return_value = tenant
    with patch(VERIFY, return_value=RESIDENT), patch(LIST, return_value=(items, None)):
        async with make_client() as client:
            overrides = client._transport.app.dependency_overrides
            overrides[get_firestore_client] = lambda: client_mock
            overrides[get_lock_service] = lambda: MagicMock()
            resp = await client.get("/api/v1/bookings/mine", headers={**AUTH, **HOST})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["cancellable"] is False
