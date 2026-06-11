from sport_slot.repositories.base import TenantRepository


class UserProfileRepository(TenantRepository):
    """/tenants/{tenant_id}/users/{uid} (ADR-0008 Decision 4)."""

    collection_name = "users"
