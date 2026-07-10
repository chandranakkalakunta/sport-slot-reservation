from google.api_core.exceptions import AlreadyExists

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
