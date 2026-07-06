"""Phase 13.4 tests: tenant permanent delete (platform-admin only, ADR-0034 §2)."""
from unittest.mock import MagicMock, patch

import firebase_admin.auth as fb_auth

from sport_slot.dependencies import get_firestore_client

AUTH = {"authorization": "Bearer fake"}
ADMIN_HOST = {"host": "admin.slotsense.chandraailabs.com"}
TENANT_HOST = {"host": "demo.slotsense.chandraailabs.com"}

ADMIN_CLAIMS = {"uid": "sa-1", "role": "platform_admin"}
TENANT_ADMIN_CLAIMS = {
    "uid": "a-1", "role": "tenant_admin",
    "tenant_id": "t-abc", "tenant_slug": "demo", "household_id": "h-0",
}

VERIFY = "sport_slot.auth.dependency.fb_auth.verify_id_token"
DELETE_FB = "sport_slot.services.tenants.fb_auth.delete_user"
WRITE_LOG = "sport_slot.services.tenants.write_deletion_log"


def _delete_tenant_mock(
    tenant_exists: bool = True,
    user_uids: list[str] | None = None,
    recursive_delete_count: int = 42,
):
    """Mock Firestore client for tenant permanent-delete route.

    Separates the tenant doc lookup, the users subcollection stream, and the
    platform_deletion_log write using side_effect on .collection() so each
    returns the right mock without conflicts.
    """
    client = MagicMock()

    tenant_snap = MagicMock()
    tenant_snap.exists = tenant_exists
    tenant_snap.to_dict.return_value = {
        "slug": "acme",
        "display_name": "ACME Corp",
    }

    tenant_ref = MagicMock()
    tenant_ref.get.return_value = tenant_snap

    # Simulate user uid enumeration — each snap's .id is the uid
    uids = user_uids if user_uids is not None else ["u-1", "u-2"]
    user_snaps = []
    for uid in uids:
        s = MagicMock()
        s.id = uid
        user_snaps.append(s)

    users_col = MagicMock()
    users_col.stream.return_value = user_snaps

    tenant_doc_mock = MagicMock()
    tenant_doc_mock.get.return_value = tenant_snap
    tenant_doc_mock.collection.return_value = users_col

    tenants_col = MagicMock()
    tenants_col.document.return_value = tenant_doc_mock

    log_col = MagicMock()

    def _collection_side_effect(name):
        if name == "tenants":
            return tenants_col
        if name == "platform_deletion_log":
            return log_col
        return MagicMock()

    client.collection.side_effect = _collection_side_effect
    client.recursive_delete.return_value = recursive_delete_count
    return client


# ── Test (a): platform-admin only ────────────────────────────────────────────

async def test_delete_tenant_permanently_forbidden_for_tenant_admin(make_client):
    """(a) RED/GREEN: tenant-admin token must receive 403, not 200.

    Confirms the route is guarded by require_platform_admin, not just any auth.
    """
    with patch(VERIFY, return_value=TENANT_ADMIN_CLAIMS):
        async with make_client() as c:
            # No override needed — auth guard rejects before hitting Firestore.
            resp = await c.delete(
                "/api/v1/admin/tenants/t-abc/permanent",
                headers={**AUTH, **TENANT_HOST},
            )
    assert resp.status_code == 403


# ── Test (b): successful delete ───────────────────────────────────────────────

async def test_delete_tenant_permanently_full_cascade(make_client):
    """(b) GREEN: recursive_delete called on correct ref; all Auth users removed;
    platform_deletion_log stub written with correct counts; no PII in stub.
    """
    client = _delete_tenant_mock(user_uids=["u-1", "u-2"], recursive_delete_count=99)

    with patch(VERIFY, return_value=ADMIN_CLAIMS), \
         patch(DELETE_FB) as mock_del_fb, \
         patch(WRITE_LOG) as mock_log:
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.delete(
                "/api/v1/admin/tenants/t-abc/permanent",
                headers={**AUTH, **ADMIN_HOST},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"] == "t-abc"
    assert body["status"] == "deleted"
    assert body["firestore_docs_deleted"] == 99
    assert body["auth_users_deleted"] == 2
    assert body["auth_users_already_absent"] == 0

    # recursive_delete called with the tenant DocumentReference.
    client.recursive_delete.assert_called_once()
    ref_arg = client.recursive_delete.call_args[0][0]
    # The ref is obtained via client.collection("tenants").document("t-abc").
    assert ref_arg is client.collection("tenants").document("t-abc")

    # Both Auth users deleted.
    assert mock_del_fb.call_count == 2
    mock_del_fb.assert_any_call("u-1")
    mock_del_fb.assert_any_call("u-2")

    # platform_deletion_log stub written once with correct non-PII fields.
    mock_log.assert_called_once()
    kw = mock_log.call_args.kwargs
    assert kw["tenant_id"] == "t-abc"
    assert kw["tenant_slug"] == "acme"
    assert kw["tenant_display_name"] == "ACME Corp"
    assert kw["actor_uid"] == "sa-1"
    assert kw["firestore_docs_deleted"] == 99
    assert kw["auth_users_deleted"] == 2
    assert kw["auth_users_already_absent"] == 0
    # PII fields must NOT be present in the stub.
    assert "email" not in kw
    assert "display_name" not in kw
    assert "user_list" not in kw


# ── Test (c): already-absent Auth user tolerated ─────────────────────────────

async def test_delete_tenant_permanently_tolerates_missing_auth_user(make_client):
    """(c) One uid raises UserNotFoundError → deletion completes; counts accurate.

    RED before Phase 13.4: UserNotFoundError would propagate as 500.
    GREEN: warning logged, auth_users_already_absent=1, stub still written.
    """
    client = _delete_tenant_mock(user_uids=["u-1", "u-missing"], recursive_delete_count=10)

    def _del_side_effect(uid):
        if uid == "u-missing":
            raise fb_auth.UserNotFoundError("not found")

    with patch(VERIFY, return_value=ADMIN_CLAIMS), \
         patch(DELETE_FB, side_effect=_del_side_effect), \
         patch(WRITE_LOG) as mock_log:
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.delete(
                "/api/v1/admin/tenants/t-abc/permanent",
                headers={**AUTH, **ADMIN_HOST},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["auth_users_deleted"] == 1
    assert body["auth_users_already_absent"] == 1

    # Stub still written with accurate counts.
    mock_log.assert_called_once()
    kw = mock_log.call_args.kwargs
    assert kw["auth_users_deleted"] == 1
    assert kw["auth_users_already_absent"] == 1


# ── Test: 404 when tenant not found ──────────────────────────────────────────

async def test_delete_tenant_permanently_404_when_not_found(make_client):
    """Platform-admin attempt on non-existent tenant returns 404."""
    client = _delete_tenant_mock(tenant_exists=False)
    with patch(VERIFY, return_value=ADMIN_CLAIMS), \
         patch(DELETE_FB), patch(WRITE_LOG) as mock_log:
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.delete(
                "/api/v1/admin/tenants/t-ghost/permanent",
                headers={**AUTH, **ADMIN_HOST},
            )
    assert resp.status_code == 404
    client.recursive_delete.assert_not_called()
    mock_log.assert_not_called()
