from pydantic import BaseModel, ConfigDict


class TenantContext(BaseModel):
    """Immutable per-request identity + tenancy (ADR-0004 Layer 3, ADR-0007)."""

    model_config = ConfigDict(frozen=True)

    uid: str
    tenant_id: str | None
    tenant_slug: str | None
    role: str
    household_id: str | None = None
