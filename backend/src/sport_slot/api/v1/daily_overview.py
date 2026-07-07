"""Daily Booking Overview — tenant-admin read-only view (ADR-0022 §3)."""

import structlog
from fastapi import APIRouter, Depends

from sport_slot.auth.context import TenantContext
from sport_slot.auth.roles import require_role
from sport_slot.dependencies import get_firestore_client
from sport_slot.repositories.bookings import BookingRepository
from sport_slot.repositories.user_profiles import UserProfileRepository

log = structlog.get_logger()

router = APIRouter(prefix="/tenant/overview", tags=["daily-overview"])


@router.get("/daily")
async def daily_booking_overview(
    date: str,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    """Return every facility (sorted alphabetically) with its confirmed and
    cancelled bookings for the requested date.

    Each booking entry includes the resident's display_name and email, joined
    from their user profile.  Profile lookups are N+1 (one per unique resident
    uid on the day) — acceptable at current tenant scale; see list_tenants() in
    repositories/base.py for the same documented trade-off.
    """
    # Load all facilities for the tenant.
    fac_col = (
        client.collection("tenants")
        .document(ctx.tenant_id)
        .collection("facilities")
    )
    facilities: list[dict] = [snap.to_dict() for snap in fac_col.stream()]
    # Alphabetical by name — scoped to this endpoint only.
    facilities.sort(key=lambda f: (f.get("name") or "").lower())

    # Load all bookings for the requested date.
    all_bookings = BookingRepository(ctx, client).list_for_date(date)

    # Collect unique resident uids; fetch profiles (N+1, one per uid).
    unique_uids = {b["uid"] for b in all_bookings if b.get("uid")}
    profile_repo = UserProfileRepository(ctx, client)
    profiles: dict[str, dict] = {}
    for uid in unique_uids:
        p = profile_repo.get(uid)
        if p:
            profiles[uid] = p

    # Index bookings by facility_id.
    bookings_by_facility: dict[str, list[dict]] = {}
    for booking in all_bookings:
        fid = booking.get("facility_id", "")
        bookings_by_facility.setdefault(fid, []).append(booking)

    result = []
    for fac in facilities:
        fid = fac.get("id", "")
        fac_bookings = sorted(
            bookings_by_facility.get(fid, []),
            key=lambda b: b.get("start", ""),
        )
        enriched = []
        for b in fac_bookings:
            profile = profiles.get(b.get("uid", ""), {})
            enriched.append({
                "booking_id": b.get("id"),
                "start": b.get("start"),
                "end": b.get("end"),
                "status": b.get("status"),
                "resident_name": profile.get("display_name"),
                "resident_email": profile.get("email"),
            })
        result.append({
            "facility_id": fid,
            "name": fac.get("name"),
            "facility_type_id": fac.get("facility_type_id"),
            "sport": fac.get("sport"),
            "bookings": enriched,
        })

    return {"date": date, "facilities": result}
