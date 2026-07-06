"""Platform-level deletion audit log — top-level collection (ADR-0034 §2).

Written OUTSIDE any tenant's own subtree so the record survives the recursive
delete of the tenant it documents. Pattern mirrors repositories/password_reset.py.
"""

import datetime
import uuid


def write_deletion_log(
    client,
    *,
    tenant_id: str,
    tenant_slug: str,
    tenant_display_name: str,
    actor_uid: str,
    firestore_docs_deleted: int,
    auth_users_deleted: int,
    auth_users_already_absent: int,
) -> None:
    doc_id = uuid.uuid4().hex
    client.collection("platform_deletion_log").document(doc_id).set({
        "tenant_id": tenant_id,
        "tenant_slug": tenant_slug,
        "tenant_display_name": tenant_display_name,
        "actor_uid": actor_uid,
        "firestore_docs_deleted": firestore_docs_deleted,
        "auth_users_deleted": auth_users_deleted,
        "auth_users_already_absent": auth_users_already_absent,
        "deleted_at": datetime.datetime.now(datetime.UTC),
    })
