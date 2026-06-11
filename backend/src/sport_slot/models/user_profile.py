import datetime

from pydantic import BaseModel


class UserProfile(BaseModel):
    """Stored at /tenants/{tenant_id}/users/{uid} (ADR-0008)."""

    uid: str
    tenant_id: str
    household_id: str | None = None
    flat_number: str | None = None
    display_name: str
    role: str
    created_at: datetime.datetime
