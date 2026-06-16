"""Tests for platform-admin provisioning endpoints (Phase 5.2)."""
from unittest.mock import MagicMock, patch

import firebase_admin.auth as fb_auth

from sport_slot.dependencies import get_firestore_client

AUTH = {"authorization": "Bearer fake"}
ADMIN_HOST = {"host": "admin.sportbook.chandraailabs.com"}
TENANT_HOST = {"host": "demo.sportbook.chandraailabs.com"}

ADMIN_CLAIMS = {"uid": "sa-1", "role": "platform_admin"}
RESIDENT_CLAIMS = {
    "uid": "u-1", "role": "resident",
    "tenant_id": "t-1", "tenant_slug": "demo", "household_id": "h-1",
}

VERIFY = "sport_slot.auth.dependency.fb_auth.verify_id_token"
CREATE_FB = "sport_slot.services.provisioning.fb_auth.create_user"
CLAIMS_FB = "sport_slot.services.provisioning.fb_auth.set_custom_user_claims"
DELETE_FB = "sport_slot.services.provisioning.fb_auth.delete_user"
UPDATE_FB = "sport_slot.services.provisioning.fb_auth.update_user"
PW_FB = "sport_slot.api.v1.users.fb_auth.update_user"
ENQUEUE_PROV = "sport_slot.services.provisioning.enqueue_notification"


def _mock_client(
    tenant_exists: bool = True,
    tenant_slug: str = "demo",
    profile_exists: bool = True,
    profile_data: dict | None = None,
    slug_taken: bool = False,
):
    """Return a MagicMock Firestore client configured for provisioning paths."""
    client = MagicMock()

    # Tenant doc: collection("tenants").document(id).get()
    tenant_snap = MagicMock()
    tenant_snap.exists = tenant_exists
    tenant_snap.to_dict.return_value = (
        {"slug": tenant_slug, "display_name": "Demo Society"} if tenant_exists else {}
    )
    client.collection.return_value.document.return_value.get.return_value = tenant_snap

    # User profile: collection().document().collection().document().get()
    profile_snap = MagicMock()
    profile_snap.exists = profile_exists
    profile_snap.to_dict.return_value = profile_data or {"uid": "u-1"}
    (client.collection.return_value
     .document.return_value
     .collection.return_value
     .document.return_value
     .get.return_value) = profile_snap

    # Slug uniqueness: collection().where().limit().stream()
    if slug_taken:
        existing_snap = MagicMock()
        existing_snap.to_dict.return_value = {"slug": "demo"}
        client.collection.return_value.where.return_value.limit.return_value.stream.return_value = [existing_snap]
    else:
        client.collection.return_value.where.return_value.limit.return_value.stream.return_value = []

    # list_tenants: collection().order_by().limit().stream()
    client.collection.return_value.order_by.return_value.limit.return_value.stream.return_value = []

    return client


# ── require_platform_admin gate ─────────────────────────────────────────────

async def test_resident_blocked_by_platform_admin_gate(make_client):
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: _mock_client()
            resp = await client.get("/api/v1/admin/tenants", headers={**AUTH, **TENANT_HOST})
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN_ROLE"


async def test_platform_admin_allowed_on_admin_host(make_client):
    with patch(VERIFY, return_value=ADMIN_CLAIMS):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: _mock_client()
            resp = await client.get("/api/v1/admin/tenants", headers={**AUTH, **ADMIN_HOST})
    assert resp.status_code == 200
    assert resp.json()["items"] == []


# ── create_tenant ────────────────────────────────────────────────────────────

async def test_create_tenant_valid(make_client):
    with patch(VERIFY, return_value=ADMIN_CLAIMS):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: _mock_client()
            resp = await client.post(
                "/api/v1/admin/tenants",
                json={"slug": "greenpark", "display_name": "Green Park"},
                headers={**AUTH, **ADMIN_HOST},
            )
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "greenpark"
    assert body["tenant_id"].startswith("t-")


async def test_create_tenant_invalid_slug(make_client):
    with patch(VERIFY, return_value=ADMIN_CLAIMS):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: _mock_client()
            resp = await client.post(
                "/api/v1/admin/tenants",
                json={"slug": "UPPER CASE!", "display_name": "Bad"},
                headers={**AUTH, **ADMIN_HOST},
            )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_SLUG"


async def test_create_tenant_duplicate_slug(make_client):
    with patch(VERIFY, return_value=ADMIN_CLAIMS):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _mock_client(slug_taken=True)
            )
            resp = await client.post(
                "/api/v1/admin/tenants",
                json={"slug": "demo", "display_name": "Demo Dupe"},
                headers={**AUTH, **ADMIN_HOST},
            )
    assert resp.status_code == 409
    assert resp.json()["code"] == "TENANT_SLUG_TAKEN"


# ── create_user ──────────────────────────────────────────────────────────────

async def test_create_user_success(make_client):
    fake_user = MagicMock()
    fake_user.uid = "new-uid-1"
    with patch(VERIFY, return_value=ADMIN_CLAIMS), \
         patch(CREATE_FB, return_value=fake_user), \
         patch(CLAIMS_FB), \
         patch(DELETE_FB):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: _mock_client()
            resp = await client.post(
                "/api/v1/admin/tenants/t-1/users",
                json={
                    "email": "alice@demo.com",
                    "display_name": "Alice",
                    "flat_number": "A-101",
                    "role": "resident",
                },
                headers={**AUTH, **ADMIN_HOST},
            )
    assert resp.status_code == 201
    body = resp.json()
    assert body["uid"] == "new-uid-1"
    assert "temp_password" in body


async def test_create_user_duplicate_email(make_client):
    with patch(VERIFY, return_value=ADMIN_CLAIMS), \
         patch(CREATE_FB, side_effect=fb_auth.EmailAlreadyExistsError("", "", "")):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: _mock_client()
            resp = await client.post(
                "/api/v1/admin/tenants/t-1/users",
                json={
                    "email": "alice@demo.com",
                    "display_name": "Alice",
                    "flat_number": "A-101",
                    "role": "resident",
                },
                headers={**AUTH, **ADMIN_HOST},
            )
    assert resp.status_code == 409
    assert resp.json()["code"] == "USER_EMAIL_TAKEN"


async def test_create_user_profile_failure_triggers_rollback(make_client):
    """Profile write failure → Firebase user deleted (rollback guard)."""
    fake_user = MagicMock()
    fake_user.uid = "new-uid-rollback"

    bad_client = _mock_client()
    (bad_client.collection.return_value
     .document.return_value
     .collection.return_value
     .document.return_value
     .create.side_effect) = Exception("Firestore unavailable")

    with patch(VERIFY, return_value=ADMIN_CLAIMS), \
         patch(CREATE_FB, return_value=fake_user), \
         patch(CLAIMS_FB), \
         patch(DELETE_FB) as mock_delete:
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: bad_client
            resp = await client.post(
                "/api/v1/admin/tenants/t-1/users",
                json={
                    "email": "rollback@demo.com",
                    "display_name": "Rollback",
                    "flat_number": "B-202",
                    "role": "resident",
                },
                headers={**AUTH, **ADMIN_HOST},
            )
    assert resp.status_code == 500
    mock_delete.assert_called_once_with("new-uid-rollback")


async def test_create_user_enqueues_welcome_notification(make_client):
    fake_user = MagicMock()
    fake_user.uid = "new-uid-2"
    with patch(VERIFY, return_value=ADMIN_CLAIMS), \
         patch(CREATE_FB, return_value=fake_user), \
         patch(CLAIMS_FB), \
         patch(DELETE_FB), \
         patch(ENQUEUE_PROV) as enqueue:
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: _mock_client()
            resp = await client.post(
                "/api/v1/admin/tenants/t-1/users",
                json={
                    "email": "bob@demo.com",
                    "display_name": "Bob",
                    "flat_number": "C-303",
                    "role": "resident",
                },
                headers={**AUTH, **ADMIN_HOST},
            )
    assert resp.status_code == 201
    body = resp.json()
    enqueue.assert_called_once()
    kwargs = enqueue.call_args.kwargs
    assert kwargs["event_type"] == "user_welcome"
    assert kwargs["to"] == "bob@demo.com"
    assert kwargs["params"] == {
        "user_name": "Bob",
        "tenant_name": "Demo Society",
        "login_url": "https://demo.sportbook.chandraailabs.com/login",
        "temp_password": body["temp_password"],
    }
    # Proves the params are accepted by the real renderer (no 422 at the worker).
    from sport_slot.notifications.email.templates import render_user_welcome
    rendered = render_user_welcome(**kwargs["params"])
    assert "Bob" in rendered.html


async def test_create_user_succeeds_even_if_enqueue_fails(make_client):
    """Best-effort proof: enqueue failure must never roll back provisioning."""
    fake_user = MagicMock()
    fake_user.uid = "new-uid-3"
    with patch(VERIFY, return_value=ADMIN_CLAIMS), \
         patch(CREATE_FB, return_value=fake_user), \
         patch(CLAIMS_FB), \
         patch(DELETE_FB) as mock_delete, \
         patch(ENQUEUE_PROV, side_effect=Exception("Cloud Tasks unavailable")):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: _mock_client()
            resp = await client.post(
                "/api/v1/admin/tenants/t-1/users",
                json={
                    "email": "carl@demo.com",
                    "display_name": "Carl",
                    "flat_number": "D-404",
                    "role": "resident",
                },
                headers={**AUTH, **ADMIN_HOST},
            )
    assert resp.status_code == 201
    assert resp.json()["uid"] == "new-uid-3"
    mock_delete.assert_not_called()


# ── deactivate_user ──────────────────────────────────────────────────────────

async def test_deactivate_user_success(make_client):
    with patch(VERIFY, return_value=ADMIN_CLAIMS), \
         patch(UPDATE_FB):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _mock_client(profile_exists=True)
            )
            resp = await client.delete(
                "/api/v1/admin/tenants/t-1/users/u-99",
                headers={**AUTH, **ADMIN_HOST},
            )
    assert resp.status_code == 200
    assert resp.json()["status"] == "deactivated"


async def test_deactivate_user_self_forbidden(make_client):
    """Platform admin cannot deactivate themselves."""
    with patch(VERIFY, return_value=ADMIN_CLAIMS), \
         patch(UPDATE_FB):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _mock_client(profile_exists=True)
            )
            # sa-1 is the caller uid from ADMIN_CLAIMS — deactivating self
            resp = await client.delete(
                "/api/v1/admin/tenants/t-1/users/sa-1",
                headers={**AUTH, **ADMIN_HOST},
            )
    assert resp.status_code == 403
    assert resp.json()["code"] == "SELF_DEACTIVATION_FORBIDDEN"


async def test_deactivate_user_not_found(make_client):
    with patch(VERIFY, return_value=ADMIN_CLAIMS), \
         patch(UPDATE_FB):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _mock_client(profile_exists=False)
            )
            resp = await client.delete(
                "/api/v1/admin/tenants/t-1/users/ghost-uid",
                headers={**AUTH, **ADMIN_HOST},
            )
    assert resp.status_code == 404
    assert resp.json()["code"] == "USER_NOT_FOUND"


# ── change-password ──────────────────────────────────────────────────────────

async def test_change_password_success(make_client):
    with patch(VERIFY, return_value=RESIDENT_CLAIMS), \
         patch(PW_FB) as mock_pw:
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: _mock_client()
            resp = await client.post(
                "/api/v1/users/me/change-password",
                json={"new_password": "secureNewPass1!"},
                headers={**AUTH, **TENANT_HOST},
            )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    mock_pw.assert_called_once_with("u-1", password="secureNewPass1!")


async def test_change_password_too_short(make_client):
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: _mock_client()
            resp = await client.post(
                "/api/v1/users/me/change-password",
                json={"new_password": "short"},
                headers={**AUTH, **TENANT_HOST},
            )
    assert resp.status_code == 422
    assert resp.json()["code"] == "WEAK_PASSWORD"


# ── reset-password (admin endpoint) ─────────────────────────────────────────

async def test_platform_admin_reset_password_returns_temp_password(make_client):
    with patch(VERIFY, return_value=ADMIN_CLAIMS), patch(UPDATE_FB):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _mock_client(profile_exists=True)
            )
            resp = await client.post(
                "/api/v1/admin/tenants/t-1/users/u-1/reset-password",
                headers={**AUTH, **ADMIN_HOST},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["uid"] == "u-1"
    assert "temp_password" in body


async def test_platform_admin_reset_password_unknown_user_404(make_client):
    with patch(VERIFY, return_value=ADMIN_CLAIMS):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _mock_client(profile_exists=False)
            )
            resp = await client.post(
                "/api/v1/admin/tenants/t-1/users/ghost/reset-password",
                headers={**AUTH, **ADMIN_HOST},
            )
    assert resp.status_code == 404
    assert resp.json()["code"] == "USER_NOT_FOUND"
