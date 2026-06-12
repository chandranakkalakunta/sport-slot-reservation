"""Policy resolution: Tenant Override → Global Default (ADR-0010 §3).

Reads ONLY the caller's own tenant document (ctx-scoped). The doc
is fetched lazily once per service instance (per-request), not
cached across requests. Wall-clock policies are evaluated in the
TENANT's timezone (3.3 decision): timestamps are stored UTC, but
rules like the 20:00 window mean tenant-local wall time.
"""

from sport_slot.auth.context import TenantContext

GLOBAL_DEFAULTS: dict[str, object] = {
    "max_slots_per_user_per_sport_per_day": 1,
    "booking_horizon_days": 1,
    "booking_window_open_time": "20:00",
    "cancellation_buffer_hours": 2,
}

DEFAULT_TIMEZONE = "Asia/Kolkata"


class PolicyService:
    def __init__(self, ctx: TenantContext, client):
        if not ctx.tenant_id:
            raise ValueError("PolicyService requires a tenant-scoped context")
        self._ctx = ctx
        self._client = client
        self._doc: dict | None = None

    def _tenant_doc(self) -> dict:
        if self._doc is None:
            snap = (
                self._client.collection("tenants")
                .document(self._ctx.tenant_id)
                .get()
            )
            self._doc = snap.to_dict() or {} if snap.exists else {}
        return self._doc

    def get(self, key: str):
        if key not in GLOBAL_DEFAULTS:
            raise KeyError(f"Unknown policy key: {key}")
        return self._tenant_doc().get("policies", {}).get(key, GLOBAL_DEFAULTS[key])

    def tenant_timezone(self) -> str:
        return self._tenant_doc().get("timezone", DEFAULT_TIMEZONE)
