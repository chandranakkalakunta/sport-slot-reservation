"""Tests for Phase 5.4b: branding, policies, user management, bulk import."""
from unittest.mock import MagicMock, patch

import firebase_admin.auth as fb_auth

from sport_slot.dependencies import get_firestore_client

ADMIN = {
    "uid": "a1", "role": "tenant_admin", "tenant_id": "t-1",
    "tenant_slug": "demo", "household_id": "h-0",
}
RESIDENT = {
    "uid": "u1", "role": "resident", "tenant_id": "t-1",
    "tenant_slug": "demo", "household_id": "h-1",
}
AUTH = {"authorization": "Bearer fake"}
HOST = {"host": "demo.sportbook.chandraailabs.com"}
VERIFY = "sport_slot.auth.dependency.fb_auth.verify_id_token"
CREATE_FB = "sport_slot.services.provisioning.fb_auth.create_user"
CLAIMS_FB = "sport_slot.services.provisioning.fb_auth.set_custom_user_claims"
DELETE_FB = "sport_slot.services.provisioning.fb_auth.delete_user"
UPDATE_FB = "sport_slot.services.provisioning.fb_auth.update_user"


def _tenant_client(branding=None, policies=None):
    """Mock for branding/policies — shallow get on tenant doc."""
    client = MagicMock()
    snap = client.collection.return_value.document.return_value.get.return_value
    snap.exists = True
    snap.to_dict.return_value = {
        "branding": branding or {},
        "policies": policies or {},
    }
    return client


def _prov_client(tenant_slug="demo", profile_exists=True, profile_data=None):
    """Mock for provisioning paths (mirrors test_admin_provisioning._mock_client)."""
    client = MagicMock()
    tenant_snap = MagicMock()
    tenant_snap.exists = True
    tenant_snap.to_dict.return_value = {"slug": tenant_slug}
    client.collection.return_value.document.return_value.get.return_value = tenant_snap

    profile_snap = MagicMock()
    profile_snap.exists = profile_exists
    profile_snap.to_dict.return_value = profile_data or {"uid": "u-99"}
    (client.collection.return_value
     .document.return_value
     .collection.return_value
     .document.return_value
     .get.return_value) = profile_snap
    return client


def _list_users_client(users=None):
    """Mock for GET /tenant/users — deep stream."""
    client = MagicMock()
    snaps = []
    for u in (users or [{"uid": "u-1", "email": "a@b.com"}]):
        s = MagicMock()
        s.to_dict.return_value = u
        snaps.append(s)
    (client.collection.return_value.document.return_value
     .collection.return_value.stream.return_value) = snaps
    return client


# ── Branding ─────────────────────────────────────────────────────────────────

async def test_branding_valid_patch_merges(make_client):
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _tenant_client(branding={"brand_name": "Old"})
            )
            resp = await c.patch(
                "/api/v1/tenant/branding",
                json={"brand_name": "New Name", "brand_primary_color": "#aabbcc"},
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 200
    b = resp.json()["branding"]
    assert b["brand_name"] == "New Name"
    assert b["brand_primary_color"] == "#aabbcc"


async def test_branding_bad_hex_422(make_client):
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _tenant_client()
            )
            resp = await c.patch(
                "/api/v1/tenant/branding",
                json={"brand_primary_color": "not-a-hex"},
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_FAILED"


async def test_branding_bad_logo_url_422(make_client):
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _tenant_client()
            )
            resp = await c.patch(
                "/api/v1/tenant/branding",
                json={"brand_logo_url": "ftp://nothttp.com/logo.png"},
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_FAILED"


async def test_branding_partial_update_preserves_siblings(make_client):
    existing = {"brand_name": "Keep", "brand_primary_color": "#111111"}
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _tenant_client(branding=existing)
            )
            resp = await c.patch(
                "/api/v1/tenant/branding",
                json={"brand_name": "Updated"},
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 200
    b = resp.json()["branding"]
    assert b["brand_name"] == "Updated"
    assert b["brand_primary_color"] == "#111111"  # sibling preserved


# ── Policies ─────────────────────────────────────────────────────────────────

async def test_policies_valid_patch_merges(make_client):
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _tenant_client()
            )
            resp = await c.patch(
                "/api/v1/tenant/policies",
                json={"booking_horizon_days": 14, "cancellation_buffer_hours": 2},
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 200
    p = resp.json()["policies"]
    assert p["booking_horizon_days"] == 14
    assert p["cancellation_buffer_hours"] == 2


async def test_policies_horizon_zero_422(make_client):
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _tenant_client()
            )
            resp = await c.patch(
                "/api/v1/tenant/policies",
                json={"booking_horizon_days": 0},
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_FAILED"


async def test_policies_negative_buffer_422(make_client):
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _tenant_client()
            )
            resp = await c.patch(
                "/api/v1/tenant/policies",
                json={"cancellation_buffer_hours": -1},
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_FAILED"


async def test_policies_bad_time_format_422(make_client):
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _tenant_client()
            )
            resp = await c.patch(
                "/api/v1/tenant/policies",
                json={"booking_window_open_time": "9am"},
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_FAILED"


# ── Tenant users ──────────────────────────────────────────────────────────────

async def test_create_resident_with_flat_number_201(make_client):
    fake_user = MagicMock()
    fake_user.uid = "new-uid-1"
    with patch(VERIFY, return_value=ADMIN), \
         patch(CREATE_FB, return_value=fake_user), \
         patch(CLAIMS_FB), patch(DELETE_FB):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _prov_client()
            )
            resp = await c.post(
                "/api/v1/tenant/users",
                json={"email": "bob@demo.com", "display_name": "Bob",
                      "flat_number": "B-202", "role": "resident"},
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 201
    body = resp.json()
    assert body["uid"] == "new-uid-1"
    assert "temp_password" in body


async def test_create_tenant_admin_without_flat_number_201(make_client):
    """STEP 5 fix: tenant_admin does not require flat_number."""
    fake_user = MagicMock()
    fake_user.uid = "admin-uid-1"
    with patch(VERIFY, return_value=ADMIN), \
         patch(CREATE_FB, return_value=fake_user), \
         patch(CLAIMS_FB), patch(DELETE_FB):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _prov_client()
            )
            resp = await c.post(
                "/api/v1/tenant/users",
                json={"email": "newadmin@demo.com", "display_name": "New Admin",
                      "role": "tenant_admin"},
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 201
    assert resp.json()["uid"] == "admin-uid-1"


async def test_create_resident_without_flat_number_422(make_client):
    """STEP 5 fix: resident creation without flat_number must fail."""
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _prov_client()
            )
            resp = await c.post(
                "/api/v1/tenant/users",
                json={"email": "noflatresident@demo.com",
                      "display_name": "No Flat", "role": "resident"},
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_FAILED"


async def test_list_tenant_users_returns_items(make_client):
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _list_users_client()
            )
            resp = await c.get("/api/v1/tenant/users", headers={**AUTH, **HOST})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["uid"] == "u-1"


async def test_deactivate_tenant_user_soft_deletes(make_client):
    with patch(VERIFY, return_value=ADMIN), patch(UPDATE_FB):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _prov_client(profile_exists=True)
            )
            resp = await c.delete(
                "/api/v1/tenant/users/u-99",
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 200
    assert resp.json()["status"] == "deactivated"


async def test_tenant_user_create_resident_blocked_for_resident_caller(make_client):
    with patch(VERIFY, return_value=RESIDENT):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _prov_client()
            )
            resp = await c.post(
                "/api/v1/tenant/users",
                json={"email": "x@demo.com", "display_name": "X",
                      "flat_number": "A-1", "role": "resident"},
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN_ROLE"


# ── Bulk import ───────────────────────────────────────────────────────────────

async def test_bulk_mixed_rows_per_row_report(make_client):
    good_user = MagicMock()
    good_user.uid = "good-uid"
    with patch(VERIFY, return_value=ADMIN), \
         patch(CREATE_FB, side_effect=[
             good_user,
             fb_auth.EmailAlreadyExistsError("", "", ""),
         ]), \
         patch(CLAIMS_FB), patch(DELETE_FB):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _prov_client()
            )
            resp = await c.post(
                "/api/v1/tenant/users/bulk",
                json={"rows": [
                    {"email": "ok@demo.com", "display_name": "OK",
                     "flat_number": "A-1", "role": "resident"},
                    {"email": "dup@demo.com", "display_name": "Dup",
                     "flat_number": "A-2", "role": "resident"},
                ]},
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["created"] == 1
    assert body["failed"] == 1
    created = next(r for r in body["results"] if r["status"] == "created")
    failed = next(r for r in body["results"] if r["status"] == "failed")
    assert "temp_password" in created
    assert failed["reason"] == "USER_EMAIL_TAKEN"


async def test_bulk_over_500_rows_422(make_client):
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _prov_client()
            )
            rows = [{"email": f"u{i}@demo.com", "display_name": f"U{i}",
                     "flat_number": f"A-{i}", "role": "resident"}
                    for i in range(501)]
            resp = await c.post(
                "/api/v1/tenant/users/bulk",
                json={"rows": rows},
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_FAILED"


# ── VALIDATION_FAILED detail ─────────────────────────────────────────────────

async def test_validation_failed_includes_field_detail(make_client):
    """STEP 6: 422 envelope now includes a 'detail' array with loc+msg."""
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            # Send an empty body to POST /tenant/users — email and display_name required
            resp = await c.post(
                "/api/v1/tenant/users",
                json={},
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "VALIDATION_FAILED"
    assert "detail" in body
    assert isinstance(body["detail"], list)
    assert len(body["detail"]) >= 1
    assert "loc" in body["detail"][0]
    assert "msg" in body["detail"][0]
