import base64
from typing import Any

from google.cloud import firestore

from sport_slot.auth.context import TenantContext


def _encode_cursor(doc_id: str) -> str:
    return base64.urlsafe_b64encode(doc_id.encode()).decode()


def _decode_cursor(cursor: str) -> str:
    return base64.urlsafe_b64decode(cursor.encode()).decode()


class TenantRepository:
    """ADR-0004 Layer 2: tenant scoping unbypassable by construction.

    Subclasses set collection_name. All paths derive from the
    TenantContext given at construction (ADR-0008).
    """

    collection_name: str = ""

    def __init__(self, ctx: TenantContext, client: firestore.Client):
        if not ctx.tenant_id:
            raise ValueError("TenantRepository requires a tenant-scoped context")
        if not self.collection_name:
            raise ValueError("collection_name must be set by subclass")
        self._ctx = ctx
        self._client = client

    @property
    def _collection(self):
        return (
            self._client.collection("tenants")
            .document(self._ctx.tenant_id)
            .collection(self.collection_name)
        )

    def get(self, doc_id: str) -> dict[str, Any] | None:
        snap = self._collection.document(doc_id).get()
        return snap.to_dict() if snap.exists else None

    def create(self, doc_id: str, data: dict[str, Any]) -> None:
        self._collection.document(doc_id).create(data)

    def update(self, doc_id: str, data: dict[str, Any]) -> None:
        self._collection.document(doc_id).update(data)

    def delete(self, doc_id: str) -> None:
        self._collection.document(doc_id).delete()

    def list(
        self, limit: int = 20, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Cursor pagination per ADR-0006 Decision 3 (no offsets)."""
        query = self._collection.order_by("__name__").limit(limit + 1)
        if cursor:
            start_ref = self._collection.document(_decode_cursor(cursor))
            query = query.start_after({"__name__": start_ref})
        snaps = list(query.stream())
        has_more = len(snaps) > limit
        snaps = snaps[:limit]
        items = [snap.to_dict() for snap in snaps]
        next_cursor = _encode_cursor(snaps[-1].id) if has_more and snaps else None
        return items, next_cursor


class PlatformRepository:
    """Tenant-agnostic data. platform_admin contexts ONLY (ADR-0008)."""

    collection_name: str = ""

    def __init__(self, ctx: TenantContext, client: firestore.Client):
        if ctx.role != "platform_admin":
            raise PermissionError("PlatformRepository requires platform_admin")
        self._ctx = ctx
        self._client = client

    @property
    def _collection(self):
        return self._client.collection(self.collection_name)

    def get(self, doc_id: str) -> dict[str, Any] | None:
        snap = self._collection.document(doc_id).get()
        return snap.to_dict() if snap.exists else None

    # ── Tenant registry methods (ADR-0008, ADR-0017) ──────────────────────

    def create_tenant(self, tenant_id: str, data: dict[str, Any]) -> None:
        self._client.collection("tenants").document(tenant_id).set(data)

    def get_tenant_by_slug(self, slug: str) -> dict[str, Any] | None:
        snaps = list(
            self._client.collection("tenants")
            .where("slug", "==", slug)
            .limit(1)
            .stream()
        )
        return snaps[0].to_dict() if snaps else None

    def list_tenants(
        self, limit: int = 20, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        col = self._client.collection("tenants")
        query = col.order_by("__name__").limit(limit + 1)
        if cursor:
            start_ref = col.document(_decode_cursor(cursor))
            query = query.start_after({"__name__": start_ref})
        snaps = list(query.stream())
        has_more = len(snaps) > limit
        snaps = snaps[:limit]
        items = []
        for snap in snaps:
            data = snap.to_dict() or {}
            # N+1 acceptable at current scale (~3-4 tenants); fetch tenant-admin emails.
            admin_snaps = list(
                self._client.collection("tenants")
                .document(snap.id)
                .collection("users")
                .where("role", "==", "tenant_admin")
                .stream()
            )
            data["admin_emails"] = [
                s.to_dict().get("email", "") for s in admin_snaps
                if s.to_dict().get("email")
            ]
            items.append(data)
        next_cursor = _encode_cursor(snaps[-1].id) if has_more and snaps else None
        return items, next_cursor
