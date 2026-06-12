"""Policy resolution: Tenant Override → Global Default (ADR-0010 §3).

Reads ONLY the caller's own tenant document (ctx-scoped); this is
not a cross-tenant surface. Defaults live here as a code registry
(versioned, type-checked) — same pattern as error_codes.
"""

from sport_slot.auth.context import TenantContext

GLOBAL_DEFAULTS: dict[str, object] = {
    "max_slots_per_user_per_sport_per_day": 1,
    "booking_horizon_days": 1,
    "booking_window_open_time": "20:00",
    "cancellation_buffer_hours": 2,
}


class PolicyService:
    def __init__(self, ctx: TenantContext, client):
        if not ctx.tenant_id:
            raise ValueError("PolicyService requires a tenant-scoped context")
        self._ctx = ctx
        self._client = client

    def get(self, key: str):
        if key not in GLOBAL_DEFAULTS:
            raise KeyError(f"Unknown policy key: {key}")
        snap = self._client.collection("tenants").document(self._ctx.tenant_id).get()
        overrides = (snap.to_dict() or {}).get("policies", {}) if snap.exists else {}
        return overrides.get(key, GLOBAL_DEFAULTS[key])
