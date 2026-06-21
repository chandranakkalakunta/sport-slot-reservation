"""Facility service helpers (ADR-0021 §2)."""

from sport_slot.auth.context import TenantContext
from sport_slot.repositories.facilities import FacilityRepository


def list_facilities(ctx: TenantContext, client) -> list[dict]:
    """Return active facilities for the tenant — used by the agent for matching context."""
    items, _ = FacilityRepository(ctx, client).list(limit=100)
    return [f for f in items if f.get("active", False)]
