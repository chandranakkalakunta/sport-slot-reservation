"""Tenant-level service operations (ADR-0034 §2)."""

import structlog

import firebase_admin.auth as fb_auth

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.repositories.platform_deletion_log import write_deletion_log

log = structlog.get_logger()


def delete_tenant_permanently(client, *, tenant_id: str, caller_uid: str) -> dict:
    """Cascade-delete an entire tenant and all its Firebase Auth users.

    Deletion order (per ADR-0034 §2):
      1. Confirm tenant exists; capture name/slug BEFORE any destructive step.
      2. Enumerate all user UIDs in `tenants/{id}/users` (read-only — must happen
         before recursive_delete destroys the subcollection).
      3. `client.recursive_delete(ref)` wipes the entire Firestore subtree.
      4. For each enumerated uid: delete Firebase Auth user, tolerating
         UserNotFoundError per the Phase 13.3 pattern.
      5. Write a stub to the top-level `platform_deletion_log` collection with
         no PII beyond uid references and the deletion counts.

    No invoice collection exists yet (Phase 15 unbuilt). When Phase 15 ships,
    this function must be updated to exclude invoice records from the recursive
    delete per ADR-0034's carve-out — do not delete invoices.
    """
    tenant_ref = client.collection("tenants").document(tenant_id)
    tenant_snap = tenant_ref.get()
    if not tenant_snap.exists:
        raise ApiError(404, error_codes.NOT_FOUND, f"Tenant {tenant_id!r} not found")

    tenant_data = tenant_snap.to_dict() or {}
    tenant_slug = tenant_data.get("slug", "")
    tenant_display_name = tenant_data.get("display_name", tenant_slug)

    # Enumerate user UIDs BEFORE recursive_delete — the subcollection is gone after.
    user_uids = [
        snap.id
        for snap in client.collection("tenants").document(tenant_id)
        .collection("users").stream()
    ]

    firestore_docs_deleted = client.recursive_delete(tenant_ref)

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
