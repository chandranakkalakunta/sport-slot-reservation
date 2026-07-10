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


async def test_create_facility_without_price_stores_no_price_paise(make_client):
    """Backward compatibility: omitting price_paise stores it as None (not 0)."""
    client = _create_mock()
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.post("/api/v1/tenant/facilities",
                                json=NEW_FAC_BODY, headers={**AUTH, **HOST})
    assert resp.status_code == 201
    body = resp.json()
    assert body["price_paise"] is None
    written_doc = (client.collection.return_value.document.return_value
                   .collection.return_value.document.return_value.set.call_args.args[0])
    assert written_doc["price_paise"] is None


async def test_create_facility_with_price_stores_integer_paise(make_client):
    client = _create_mock()
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            body_with_price = {**NEW_FAC_BODY, "price_paise": 5050}
            resp = await c.post("/api/v1/tenant/facilities",
                                json=body_with_price, headers={**AUTH, **HOST})
    assert resp.status_code == 201
    body = resp.json()
    assert body["price_paise"] == 5050
    written_doc = (client.collection.return_value.document.return_value
                   .collection.return_value.document.return_value.set.call_args.args[0])
    assert written_doc["price_paise"] == 5050


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


async def test_patch_facility_updates_price_paise(make_client):
    updated = {**EXISTING_FAC, "price_paise": 5050}
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _ref_mock(EXISTING_FAC, updated)
            )
            resp = await c.patch("/api/v1/tenant/facilities/abc123",
                                 json={"price_paise": 5050},
                                 headers={**AUTH, **HOST})
    assert resp.status_code == 200
    assert resp.json()["price_paise"] == 5050


async def test_delete_facility_permanently_removes_document(make_client):
    """(a) Facility Remove deletes the Firestore doc — not just sets active:False.

    RED: before Phase 13.3 the handler calls ref.update({"active": False}), so
         body has "active" key and ref.delete() is never called.
    GREEN: body has status="deleted" and no "active" key; ref.delete() called once.
    """
    client = _ref_mock(EXISTING_FAC)
    fac_ref = (client.collection.return_value.document.return_value
               .collection.return_value.document.return_value)
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.delete("/api/v1/tenant/facilities/abc123456789",
                                  headers={**AUTH, **HOST})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "abc123456789"
    assert body["status"] == "deleted"
    assert "active" not in body
    assert body["bookings_cancelled"] == 0
    fac_ref.delete.assert_called_once()
    fac_ref.update.assert_not_called()


def _deactivate_with_bookings_mock(booking_snaps=None):
    """Mock Firestore client for deactivate_facility tests that need bookings query.

    Separates the facilities and bookings sub-collections so the mock returns the
    right data from each without conflicts (MagicMock chaining would otherwise
    return the same object for .collection("facilities") and .collection("bookings")).
    """
    client = MagicMock()

    fac_snap = MagicMock()
    fac_snap.exists = True
    fac_snap.to_dict.return_value = EXISTING_FAC

    fac_ref = MagicMock()
    fac_ref.get.return_value = fac_snap

    fac_col = MagicMock()
    fac_col.document.return_value = fac_ref

    bk_query = MagicMock()
    bk_query.where.return_value = bk_query
    bk_query.stream.return_value = booking_snaps or []

    bk_col = MagicMock()
    bk_col.where.return_value = bk_query

    def _sub_col(name):
        if name == "facilities":
            return fac_col
        if name == "bookings":
            return bk_col
        return MagicMock()

    tenant_doc = MagicMock()
    tenant_doc.collection.side_effect = _sub_col

    tenant_col = MagicMock()
    tenant_col.document.return_value = tenant_doc

    client.collection.return_value = tenant_col
    return client


def _booking_snap(booking_id, facility_id="abc123456789", uid="u1"):
    snap = MagicMock()
    snap.to_dict.return_value = {
        "id": booking_id,
        "uid": uid,
        "facility_id": facility_id,
        "date": "2026-08-15",
        "start": "09:00",
        "status": "confirmed",
    }
    snap.id = booking_id
    return snap


async def test_delete_facility_cancels_future_bookings_and_writes_audit(make_client):
    """(a) Two-sided — RED/GREEN for Phase 13.3 permanent facility delete.

    RED:  cancelled_by_override was 'facility_deactivated', event_type was
          'facility.deactivated', body had 'active' key.
    GREEN: cancelled_by_override='facility_deleted', event_type='facility.deleted',
           body has status='deleted' and no 'active' key; bookings_cancelled correct.
    """
    CANCEL = "sport_slot.api.v1.facilities.cancel_booking"
    AUDIT = "sport_slot.api.v1.facilities.AuditRepository.write_event"

    snaps = [
        _booking_snap("abc123456789_2026-08-15_09:00"),
        _booking_snap("abc123456789_2026-08-15_10:00"),
    ]

    with patch(VERIFY, return_value=ADMIN), \
         patch(CANCEL) as mock_cancel, \
         patch(AUDIT) as mock_audit:
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _deactivate_with_bookings_mock(snaps)
            )
            resp = await c.delete("/api/v1/tenant/facilities/abc123456789",
                                  headers={**AUTH, **HOST})

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "abc123456789"
    assert body["status"] == "deleted"
    assert "active" not in body
    assert body["bookings_cancelled"] == 2

    # cancel_booking called with the new reason string
    assert mock_cancel.call_count == 2
    for c_call in mock_cancel.call_args_list:
        assert c_call.kwargs.get("force") is True
        assert c_call.kwargs.get("cancelled_by_override") == "facility_deleted"

    # Audit event uses new event_type and details
    mock_audit.assert_called_once()
    audit_kwargs = mock_audit.call_args.kwargs
    assert audit_kwargs["event_type"] == "facility.deleted"
    assert audit_kwargs["details"]["bookings_cancelled"] == 2
    assert audit_kwargs["details"]["facility_id"] == "abc123456789"


async def test_delete_facility_with_no_future_bookings_writes_zero_count(make_client):
    """Facility with no confirmed future bookings: count=0, audit still written."""
    CANCEL = "sport_slot.api.v1.facilities.cancel_booking"
    AUDIT = "sport_slot.api.v1.facilities.AuditRepository.write_event"

    with patch(VERIFY, return_value=ADMIN), \
         patch(CANCEL) as mock_cancel, \
         patch(AUDIT) as mock_audit:
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _deactivate_with_bookings_mock([])  # empty stream
            )
            resp = await c.delete("/api/v1/tenant/facilities/abc123456789",
                                  headers={**AUTH, **HOST})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "deleted"
    assert "active" not in body
    assert body["bookings_cancelled"] == 0
    mock_cancel.assert_not_called()
    mock_audit.assert_called_once()
    assert mock_audit.call_args.kwargs["details"]["bookings_cancelled"] == 0


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
