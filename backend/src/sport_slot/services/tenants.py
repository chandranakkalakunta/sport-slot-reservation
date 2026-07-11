"""Tenant-level service operations (ADR-0034 §2)."""

import structlog

import firebase_admin.auth as fb_auth

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.repositories.platform_deletion_log import write_deletion_log

log = structlog.get_logger()


def delete_tenant_permanently(client, *, tenant_id: str, caller_uid: str) -> dict:
    """Cascade-delete a tenant and all its Firebase Auth users — EXCEPT its
    invoices, which survive per ADR-0034's carve-out (Phase 15.7).

    Deletion order (per ADR-0034 §2, updated for the invoice carve-out):
      1. Confirm tenant exists; capture name/slug BEFORE any destructive step.
      2. Enumerate all user UIDs in `tenants/{id}/users` (read-only — must
         happen before any subcollection is destroyed).
      3. Dynamically enumerate the tenant's ACTUAL subcollections via
         `tenant_ref.collections()` — never a hardcoded list, which would
         silently miss any subcollection added in a future phase and
         quietly reintroduce this exact gap. Recursively delete every one
         EXCEPT `invoices`.
      4. Delete the now-childless tenant document itself directly (a plain
         `.delete()`, not `recursive_delete` — nothing should remain beneath
         it except the deliberately-preserved `invoices` subcollection,
         which sits alongside it in Firestore's structure, not literally
         "inside" the document in a way a plain document delete would touch).
      5. For each enumerated uid: delete Firebase Auth user, tolerating
         UserNotFoundError per the Phase 13.3 pattern.
      6. Write a stub to the top-level `platform_deletion_log` collection with
         no PII beyond uid references and the deletion counts.

    Invoices are deliberately left orphaned (no parent tenant document) —
    Firestore permits querying a subcollection by full path regardless of
    whether its parent document still exists. Locked Coordinator decision:
    the tenant document itself is still fully deleted; only invoices survive.
    """
    tenant_ref = client.collection("tenants").document(tenant_id)
    tenant_snap = tenant_ref.get()
    if not tenant_snap.exists:
        raise ApiError(404, error_codes.NOT_FOUND, f"Tenant {tenant_id!r} not found")

    tenant_data = tenant_snap.to_dict() or {}
    tenant_slug = tenant_data.get("slug", "")
    tenant_display_name = tenant_data.get("display_name", tenant_slug)

    # Enumerate user UIDs BEFORE any subcollection is destroyed.
    user_uids = [
        snap.id
        for snap in client.collection("tenants").document(tenant_id)
        .collection("users").stream()
    ]

    # Dynamically enumerate the tenant's ACTUAL subcollections — never a
    # hardcoded list (e.g. "bookings, users, facilities, audit"), which would
    # silently miss any subcollection added in a future phase and quietly
    # reintroduce this exact gap.
    firestore_docs_deleted = 0
    for sub_collection in tenant_ref.collections():
        if sub_collection.id == "invoices":
            continue  # ADR-0034 carve-out — invoices survive, deliberately orphaned
        firestore_docs_deleted += client.recursive_delete(sub_collection)

    # Now-childless except for the deliberately-preserved `invoices` sibling
    # subcollection — a plain document delete, not recursive_delete.
    tenant_ref.delete()
    firestore_docs_deleted += 1

    auth_deleted = 0
    auth_already_absent = 0
    for uid in user_uids:
        try:
            fb_auth.delete_user(uid)
            auth_deleted += 1
        except fb_auth.UserNotFoundError:
            log.warning("delete_tenant_permanently_auth_user_already_absent",
                        tenant_id=tenant_id, uid=uid)
            auth_already_absent += 1

    write_deletion_log(
        client,
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        tenant_display_name=tenant_display_name,
        actor_uid=caller_uid,
        firestore_docs_deleted=firestore_docs_deleted,
        auth_users_deleted=auth_deleted,
        auth_users_already_absent=auth_already_absent,
    )

    return {
        "tenant_id": tenant_id,
        "status": "deleted",
        "firestore_docs_deleted": firestore_docs_deleted,
        "auth_users_deleted": auth_deleted,
        "auth_users_already_absent": auth_already_absent,
    }
