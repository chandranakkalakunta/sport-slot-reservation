from unittest.mock import MagicMock, patch

from sport_slot.dependencies import get_firestore_client

RESIDENT = {"uid": "u1", "role": "resident", "tenant_id": "t-1",
            "tenant_slug": "demo", "household_id": "h-1"}
AUTH = {"authorization": "Bearer fake"}
HOST = {"host": "demo.slotsense.chandraailabs.com"}
VERIFY = "sport_slot.auth.dependency.fb_auth.verify_id_token"
BOOKED = "sport_slot.api.v1.facilities.BookingRepository.booked_starts"

_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
FACILITY = {
    "id": "f1", "active": True, "slot_duration_minutes": 60,
    "weekly_schedule": {day: [{"start": "06:00", "end": "22:00"}] for day in _DAYS},
}


def _client(facility=FACILITY, tenant=None):
    client = MagicMock()
    fac_snap = (client.collection.return_value.document.return_value
                .collection.return_value.document.return_value
                .get.return_value)
    fac_snap.exists = facility is not None
    fac_snap.to_dict.return_value = facility
    ten_snap = (client.collection.return_value.document.return_value
                .get.return_value)
    ten_snap.exists = True
    ten_snap.to_dict.return_value = tenant or {"policies": {},
                                               "timezone": "Asia/Kolkata"}
    return client


async def test_bad_date_422(make_client):
    with patch(VERIFY, return_value=RESIDENT):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _client()
            )
            resp = await client.get(
                "/api/v1/facilities/f1/availability?date=12-06-2026",
                headers={**AUTH, **HOST})
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_DATE"


async def test_missing_facility_404(make_client):
    with patch(VERIFY, return_value=RESIDENT):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _client(facility=None)
            )
            resp = await client.get(
                "/api/v1/facilities/nope/availability?date=2026-06-12",
                headers={**AUTH, **HOST})
    assert resp.status_code == 404


async def test_happy_path_shape(make_client):
    with patch(VERIFY, return_value=RESIDENT), \
         patch(BOOKED, return_value=set()):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _client()
            )
            resp = await client.get(
                "/api/v1/facilities/f1/availability?date=2026-06-12",
                headers={**AUTH, **HOST})
    assert resp.status_code == 200
    body = resp.json()
    assert body["facility_id"] == "f1" and len(body["slots"]) == 16
    assert {"start", "end", "status", "bookable", "reason"} <= set(
        body["slots"][0]
    )
