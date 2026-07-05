from unittest.mock import MagicMock, patch

from sport_slot.dependencies import get_firestore_client

ADMIN = {"uid": "a1", "role": "tenant_admin", "tenant_id": "t-1",
         "tenant_slug": "demo", "household_id": "h-0"}
RESIDENT = {"uid": "u1", "role": "resident", "tenant_id": "t-1",
            "tenant_slug": "demo", "household_id": "h-1"}
AUTH = {"authorization": "Bearer fake"}
HOST = {"host": "demo.slotsense.chandraailabs.com"}
VERIFY = "sport_slot.auth.dependency.fb_auth.verify_id_token"

_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_SCHEDULE_6_22 = {day: [{"start": "06:00", "end": "22:00"}] for day in _DAYS}

CATALOG_ITEM = {"type_id": "badminton", "name": "Badminton", "sport": "badminton"}
NEW_FAC_BODY = {
    "facility_type_id": "badminton",
    "name": "Court 1",
    "weekly_schedule": _SCHEDULE_6_22,
    "slot_duration_minutes": 60,
}
EXISTING_FAC = {
    "id": "abc123456789",
    "facility_type_id": "badminton",
    "sport": "badminton",
    "name": "Court 1",
    "weekly_schedule": _SCHEDULE_6_22,
    "slot_duration_minutes": 60,
    "description": None,
    "active": True,
}


def _catalog_mock(items=None):
    """Client for GET /facility-catalog — shallow stream."""
    client = MagicMock()
    snaps = []
    for item in (items or [CATALOG_ITEM]):
        s = MagicMock()
        s.to_dict.return_value = item
        snaps.append(s)
    client.collection.return_value.stream.return_value = snaps
    return client


def _create_mock(cat_exists=True):
    """Client for POST /tenant/facilities — catalog lookup + tenant write."""
    client = MagicMock()
    cat_snap = client.collection.return_value.document.return_value.get.return_value
    cat_snap.exists = cat_exists
    cat_snap.to_dict.return_value = CATALOG_ITEM
    return client


def _list_mock(facs=None):
    """Client for GET /tenant/facilities — deep stream."""
    client = MagicMock()
    snaps = []
    for f in (facs or [EXISTING_FAC]):
        s = MagicMock()
        s.to_dict.return_value = f
        snaps.append(s)
    (client.collection.return_value.document.return_value
     .collection.return_value.stream.return_value) = snaps
    return client


def _ref_mock(existing=None, updated=None):
    """Client for PATCH/DELETE — deep get + update."""
    client = MagicMock()
    fac_snap = MagicMock()
    fac_snap.exists = existing is not None
    fac_snap.to_dict.return_value = updated if updated is not None else existing
    ref = (client.collection.return_value.document.return_value
           .collection.return_value.document.return_value)
    ref.get.return_value = fac_snap
    return client


async def test_catalog_list_returns_seeded_types(make_client):
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _catalog_mock()
            )
            resp = await c.get("/api/v1/facility-catalog", headers={**AUTH, **HOST})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["type_id"] == "badminton"
    assert items[0]["sport"] == "badminton"


async def test_create_facility_valid_type_201_sport_copied(make_client):
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _create_mock()
            )
            resp = await c.post("/api/v1/tenant/facilities",
                                json=NEW_FAC_BODY, headers={**AUTH, **HOST})
    assert resp.status_code == 201
    body = resp.json()
    assert body["facility_type_id"] == "badminton"
    assert body["sport"] == "badminton"
    assert body["active"] is True
    assert len(body["id"]) == 12


async def test_create_facility_unknown_type_422(make_client):
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _create_mock(cat_exists=False)
            )
            bad = {**NEW_FAC_BODY, "facility_type_id": "unknown-sport"}
            resp = await c.post("/api/v1/tenant/facilities",
                                json=bad, headers={**AUTH, **HOST})
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_FAILED"


async def test_list_tenant_facilities_returns_items(make_client):
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _list_mock()
            )
            resp = await c.get("/api/v1/tenant/facilities",
                               headers={**AUTH, **HOST})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["name"] == "Court 1"


async def test_patch_facility_updates_name(make_client):
    updated = {**EXISTING_FAC, "name": "Court A"}
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _ref_mock(EXISTING_FAC, updated)
            )
            resp = await c.patch("/api/v1/tenant/facilities/abc123",
                                 json={"name": "Court A"},
                                 headers={**AUTH, **HOST})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Court A"


async def test_deactivate_facility_sets_active_false(make_client):
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _ref_mock(EXISTING_FAC)
            )
            resp = await c.delete("/api/v1/tenant/facilities/abc123456789",
                                  headers={**AUTH, **HOST})
    assert resp.status_code == 200
    assert resp.json() == {"id": "abc123456789", "active": False}


async def test_resident_cannot_create_facility_tenant_admin_required(make_client):
    with patch(VERIFY, return_value=RESIDENT):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _create_mock()
            )
            resp = await c.post("/api/v1/tenant/facilities",
                                json=NEW_FAC_BODY, headers={**AUTH, **HOST})
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN_ROLE"
