"""Phase 13.4 tests: tenant permanent delete (platform-admin only, ADR-0034 §2).

Phase 15.7 correction: recursive_delete is no longer called once on the whole
tenant document — it's called once PER dynamically-enumerated subcollection,
excluding `invoices` (ADR-0034's carve-out), followed by a plain delete of
the now-childless tenant document itself. The fixture and the two tests that
asserted the old single-call mechanism are updated accordingly; the OUTCOME
for non-invoice data (auth cleanup, deletion-log stub, 403/404 gates) is
unchanged and asserted identically to before.
"""
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
    subcollection_counts: dict[str, int] | None = None,
):
    """Mock Firestore client for tenant permanent-delete.

    `subcollection_counts` maps {collection_name: recursive_delete count} and
    represents the tenant's ACTUAL subcollections as dynamically enumerated
    via `tenant_ref.collections()` — never a hardcoded list. Defaults to a
    realistic set that always includes `invoices`, which the production code
    must never pass to `recursive_delete`.
    """
    client = MagicMock()

    tenant_snap = MagicMock()
    tenant_snap.exists = tenant_exists
    tenant_snap.to_dict.return_value = {
        "slug": "acme",
        "display_name": "ACME Corp",
    }

    if subcollection_counts is None:
        subcollection_counts = {"bookings": 30, "users": 2, "facilities": 10, "invoices": 5}
    # The production code always reads tenant_ref.collection("users").stream()
    # for uid enumeration — ensure it's always present and iterable, even if
    # a test's subcollection_counts omits it.
    subcollection_counts = {"users": 0, **subcollection_counts}

    # Each subcollection is its own CollectionReference-shaped mock with a
    # real `.id` — the production code only ever reads `.id` to decide
    # whether to skip it, never assumes/hardcodes which names exist.
    sub_refs = {}
    for name in subcollection_counts:
        ref = MagicMock()
        ref.id = name
        sub_refs[name] = ref

    uids = user_uids if user_uids is not None else ["u-1", "u-2"]
    user_snaps = []
    for uid in uids:
        s = MagicMock()
        s.id = uid
        user_snaps.append(s)
    if "users" in sub_refs:
        sub_refs["users"].stream.return_value = user_snaps

    tenant_ref = MagicMock()
    tenant_ref.get.return_value = tenant_snap
    tenant_ref.collections.return_value = list(sub_refs.values())
    tenant_ref.collection.side_effect = lambda name: sub_refs.get(name, MagicMock())

    tenants_col = MagicMock()
    tenants_col.document.return_value = tenant_ref

    log_col = MagicMock()

    def _collection_side_effect(name):
        if name == "tenants":
            return tenants_col
        if name == "platform_deletion_log":
            return log_col
        return MagicMock()

    client.collection.side_effect = _collection_side_effect

    def _recursive_delete_side_effect(ref):
        return subcollection_counts.get(ref.id, 0)

    client.recursive_delete.side_effect = _recursive_delete_side_effect
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
    """(b) GREEN: recursive_delete called on each non-invoice subcollection;
    tenant doc itself deleted directly; all Auth users removed;
    platform_deletion_log stub written with correct counts; no PII in stub.
    """
    client = _delete_tenant_mock(
        user_uids=["u-1", "u-2"],
        subcollection_counts={"bookings": 50, "users": 2, "facilities": 47, "invoices": 5},
    )
    tenant_ref = client.collection("tenants").document("t-abc")

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
    # 50 (bookings) + 2 (users) + 47 (facilities) + 1 (tenant doc itself) — invoices' 5 excluded.
    assert body["firestore_docs_deleted"] == 100
    assert body["auth_users_deleted"] == 2
    assert body["auth_users_already_absent"] == 0

    # recursive_delete called once per non-invoice subcollection — never on
    # the whole tenant document, never on invoices.
    assert client.recursive_delete.call_count == 3
    called_ids = {call.args[0].id for call in client.recursive_delete.call_args_list}
    assert called_ids == {"bookings", "users", "facilities"}
    assert "invoices" not in called_ids

    # The tenant document itself is deleted directly (plain .delete(), not recursive_delete).
    tenant_ref.delete.assert_called_once()

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
    assert kw["firestore_docs_deleted"] == 100
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
    client = _delete_tenant_mock(
        user_uids=["u-1", "u-missing"],
        subcollection_counts={"bookings": 5, "users": 2, "invoices": 3},
    )

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


# ── Phase 15.7: ADR-0034 invoice-exclusion carve-out ─────────────────────────

async def test_delete_tenant_permanently_never_recursive_deletes_invoices(make_client):
    """The core carve-out guarantee: recursive_delete must NEVER be called
    with the invoices collection, even though it IS one of the tenant's real,
    dynamically-enumerated subcollections."""
    client = _delete_tenant_mock(
        subcollection_counts={"bookings": 10, "users": 2, "invoices": 999},
    )

    with patch(VERIFY, return_value=ADMIN_CLAIMS), \
         patch(DELETE_FB), patch(WRITE_LOG):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.delete(
                "/api/v1/admin/tenants/t-abc/permanent",
                headers={**AUTH, **ADMIN_HOST},
            )

    assert resp.status_code == 200
    called_ids = {call.args[0].id for call in client.recursive_delete.call_args_list}
    assert "invoices" not in called_ids
    # The 999-count invoices collection must never have contributed to the total.
    assert resp.json()["firestore_docs_deleted"] == 10 + 2 + 1  # bookings + users + tenant doc


async def test_delete_tenant_permanently_deletes_bare_tenant_document():
    """The tenant document itself is genuinely deleted (not a soft-delete) —
    per Coordinator's locked decision, only invoices survive."""
    from sport_slot.services.tenants import delete_tenant_permanently

    client = _delete_tenant_mock(subcollection_counts={"bookings": 1, "invoices": 1})
    tenant_ref = client.collection("tenants").document("t-abc")

    with patch(DELETE_FB), patch(WRITE_LOG):
        delete_tenant_permanently(client, tenant_id="t-abc", caller_uid="sa-1")

    tenant_ref.delete.assert_called_once()


async def test_delete_tenant_permanently_handles_a_hypothetical_future_subcollection():
    """PROOF this is dynamic enumeration, not a disguised hardcoded list: a
    subcollection ("waitlists") that exists in NONE of this codebase's known
    collection names, and appears in no hardcoded list anywhere, is still
    correctly recursive-deleted. A hardcoded-list implementation (e.g.
    checking only "bookings"/"users"/"facilities"/"audit") would silently
    skip this collection entirely and fail this assertion — recursive_delete
    would never be called for it, and its 77 documents would leak.
    """
    from sport_slot.services.tenants import delete_tenant_permanently

    client = _delete_tenant_mock(
        subcollection_counts={
            "bookings": 10, "users": 2, "facilities": 5, "audit": 3,
            "invoices": 8, "waitlists": 77,  # hypothetical, unknown-to-any-list collection
        },
    )

    with patch(DELETE_FB), patch(WRITE_LOG):
        result = delete_tenant_permanently(client, tenant_id="t-abc", caller_uid="sa-1")

    called_ids = {call.args[0].id for call in client.recursive_delete.call_args_list}
    assert "waitlists" in called_ids  # the hypothetical collection WAS deleted
    assert "invoices" not in called_ids
    # 10 + 2 + 5 + 3 + 77 (all non-invoice) + 1 (tenant doc) = 98
    assert result["firestore_docs_deleted"] == 98


async def test_delete_tenant_permanently_enumerates_users_before_deleting_them():
    """User UIDs are still enumerated BEFORE any deletion happens, same as
    today — the 'users' subcollection's uids must be captured even though
    it's later itself recursive-deleted."""
    from sport_slot.services.tenants import delete_tenant_permanently

    client = _delete_tenant_mock(
        user_uids=["u-1", "u-2", "u-3"],
        subcollection_counts={"bookings": 1, "users": 3, "invoices": 1},
    )

    with patch(DELETE_FB) as mock_del_fb, patch(WRITE_LOG):
        result = delete_tenant_permanently(client, tenant_id="t-abc", caller_uid="sa-1")

    assert result["auth_users_deleted"] == 3
    assert mock_del_fb.call_count == 3
