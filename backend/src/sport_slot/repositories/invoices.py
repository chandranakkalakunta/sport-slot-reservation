from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore

from sport_slot.repositories.base import TenantRepository


class InvoiceRepository(TenantRepository):
    """/tenants/{tenant_id}/invoices/{id} (ADR-0010 §2 deterministic-ID pattern).

    Immutable — create() only, no update/delete path exists or is planned
    for this sub-phase. Deterministic ID {household_id}_{YYYY-MM} +
    Firestore create() (fails if the document already exists) gives
    natural idempotency for re-running the generation job after a
    partial failure, with zero extra bookkeeping.
    """

    collection_name = "invoices"

    def create_if_absent(self, invoice_id: str, data: dict) -> bool:
        """Create the invoice; return False (no-op) if one already exists for this period."""
        try:
            self._collection.document(invoice_id).create(data)
            return True
        except AlreadyExists:
            return False

    def list_for_household(self, household_id: str | None, limit: int = 24) -> list[dict]:
        """Caller's own household's invoices, most-recent-period-first (Phase 15.4).

        Guards against a missing household_id explicitly — returns empty
        rather than issuing a Firestore query, since a `None`/absent
        household_id must never resolve to "match everything".
        Requires the (household_id, period) composite index
        (infrastructure/firestore.indexes.json).
        """
        if not household_id:
            return []
        query = (
            self._collection
            .where("household_id", "==", household_id)
            .order_by("period", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        return [snap.to_dict() for snap in query.stream()]
