"""Daily Booking Overview — tenant-admin read-only view (ADR-0022 §3)."""

import datetime

import structlog
from fastapi import APIRouter, Depends

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.auth.roles import require_role
from sport_slot.dependencies import get_firestore_client
from sport_slot.repositories.bookings import BookingRepository
from sport_slot.repositories.user_profiles import UserProfileRepository
from sport_slot.services.availability import compute_slots

# compute_slots' neutralizing params for an admin any-date capacity view:
# we only want its weekly_schedule + slot_duration_minutes geometry (start/end
# times), not its resident-booking-eligibility verdict. An empty booked_starts
# set and a permissive horizon mean every branch in compute_slots still always
# appends the slot (status/bookable/reason are computed either way and simply
# discarded below), so these values are inert w.r.t. which times come back.
_NEUTRAL_BOOKED_STARTS: set[str] = set()
_NEUTRAL_HORIZON_DAYS = 36500
_NEUTRAL_WINDOW_OPEN = "00:00"

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

    Each facility also carries a `slots` list: its full valid slot-start
    geometry for the date (via compute_slots), each entry marked "available",
    "confirmed", or "cancelled" by cross-referencing that facility's own
    bookings for the date — this is what the Grid view's capacity display
    renders. `bookings` (booking events only, no open slots) is unchanged and
    still what the List view renders.
    """
    try:
        target_date = datetime.date.fromisoformat(date)
    except ValueError:
        raise ApiError(422, error_codes.INVALID_DATE, "date must be YYYY-MM-DD")

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
            key=lambda b: (b.get("start", ""), b.get("status") == "confirmed"),
        )
        enriched = []
        booking_by_start: dict[str, dict] = {}
        for b in fac_bookings:
            profile = profiles.get(b.get("uid", ""), {})
            entry = {
                "booking_id": b.get("id"),
                "start": b.get("start"),
                "end": b.get("end"),
                "status": b.get("status"),
                "resident_name": profile.get("display_name"),
                "resident_email": profile.get("email"),
            }
            enriched.append(entry)
            booking_by_start[entry["start"]] = entry

        # Full slot-capacity geometry for Grid — reuses compute_slots' weekly_
        # schedule + slot_duration_minutes expansion rather than re-walking the
        # same ranges independently. Its own status/bookable/reason verdict is
        # discarded (see module-level comment); status here comes only from
        # this facility's actual bookings for the date, so it can distinguish
        # confirmed from cancelled — something compute_slots' plain booked-or-
        # not set cannot.
        geometry = compute_slots(
            fac,
            target_date,
            booked_starts=_NEUTRAL_BOOKED_STARTS,
            now_local=datetime.datetime.combine(target_date, datetime.time.min),
            horizon_days=_NEUTRAL_HORIZON_DAYS,
            window_open=_NEUTRAL_WINDOW_OPEN,
        )
        slots = []
        for g in geometry:
            booking = booking_by_start.get(g["start"])
            slots.append({
                "start": g["start"],
                "end": g["end"],
                "status": booking["status"] if booking else "available",
                "resident_name": booking["resident_name"] if booking else None,
                "resident_email": booking["resident_email"] if booking else None,
            })

        result.append({
            "facility_id": fid,
            "name": fac.get("name"),
            "facility_type_id": fac.get("facility_type_id"),
            "sport": fac.get("sport"),
            "bookings": enriched,
            "slots": slots,
        })

    return {"date": date, "facilities": result}
