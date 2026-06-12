from sport_slot.repositories.base import TenantRepository


class FacilityRepository(TenantRepository):
    """/tenants/{tenant_id}/facilities/{id} (ADR-0010 §2)."""

    collection_name = "facilities"
