from unittest.mock import MagicMock, patch

import pytest

from sport_slot.auth.context import TenantContext
from sport_slot.dependencies import get_firestore_client
from sport_slot.services.policy import GLOBAL_DEFAULTS, PolicyService

RESIDENT = {"uid": "u1", "role": "resident", "tenant_id": "t-1",
            "tenant_slug": "demo", "household_id": "h-1"}
ADMIN = {"uid": "a1", "role": "tenant_admin", "tenant_id": "t-1",
         "tenant_slug": "demo", "household_id": "h-0"}
AUTH = {"authorization": "Bearer fake"}
HOST = {"host": "demo.sportbook.chandraailabs.com"}
VERIFY = "sport_slot.auth.dependency.fb_auth.verify_id_token"

VALID = {"name": "Court 1", "sport": "badminton",
         "slot_duration_minutes": 60, "open_time": "06:00",
         "close_time": "22:00"}


def _tenant_doc_client(policies=None, exists=True):
    client = MagicMock()
    snap = client.collection.return_value.document.return_value.get.return_value
    snap.exists = exists
    snap.to_dict.return_value = {"policies": policies or {}}
    return client


def test_policy_default():
    ctx = TenantContext(uid="u", tenant_id="t-1", tenant_slug="demo",
                        role="resident")
    svc = PolicyService(ctx, _tenant_doc_client())
    assert svc.get("booking_horizon_days") == GLOBAL_DEFAULTS["booking_horizon_days"]


def test_policy_override_wins():
    ctx = TenantContext(uid="u", tenant_id="t-1", tenant_slug="demo",
                        role="resident")
    svc = PolicyService(ctx, _tenant_doc_client({"booking_horizon_days": 7}))
    assert svc.get("booking_horizon_days") == 7


def test_policy_unknown_key():
    ctx = TenantContext(uid="u", tenant_id="t-1", tenant_slug="demo",
                        role="resident")
    with pytest.raises(KeyError):
        PolicyService(ctx, _tenant_doc_client()).get("nonsense")


def test_policy_requires_tenant():
    ctx = TenantContext(uid="a", tenant_id=None, tenant_slug=None,
                        role="platform_admin")
    with pytest.raises(ValueError):
        PolicyService(ctx, MagicMock())


def _facility_client(existing=None):
    client = MagicMock()
    col = client.collection.return_value.document.return_value.collection.return_value
    snap = col.document.return_value.get.return_value
    snap.exists = existing is not None
    snap.to_dict.return_value = existing
    return client


async def test_resident_cannot_create_facility(make_client):
    with patch(VERIFY, return_value=RESIDENT):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _facility_client()
            )
            resp = await client.post("/api/v1/facilities",
                                     json=VALID, headers={**AUTH, **HOST})
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN_ROLE"


async def test_admin_creates_facility(make_client):
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _facility_client()
            )
            resp = await client.post("/api/v1/facilities",
                                     json=VALID, headers={**AUTH, **HOST})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Court 1" and body["id"] and body["created_at"]


async def test_create_rejects_bad_window(make_client):
    bad = {**VALID, "open_time": "22:00", "close_time": "06:00"}
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _facility_client()
            )
            resp = await client.post("/api/v1/facilities",
                                     json=bad, headers={**AUTH, **HOST})
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_FAILED"


async def test_get_missing_facility_404(make_client):
    with patch(VERIFY, return_value=RESIDENT):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _facility_client(existing=None)
            )
            resp = await client.get("/api/v1/facilities/nope",
                                    headers={**AUTH, **HOST})
    assert resp.status_code == 404
    assert resp.json()["code"] == "FACILITY_NOT_FOUND"


async def test_resident_cannot_patch(make_client):
    with patch(VERIFY, return_value=RESIDENT):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _facility_client(existing=VALID)
            )
            resp = await client.patch("/api/v1/facilities/abc",
                                      json={"active": False},
                                      headers={**AUTH, **HOST})
    assert resp.status_code == 403
