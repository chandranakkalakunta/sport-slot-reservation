"""Computed availability (ADR-0010 §1): nothing is pre-generated.

compute_slots is a PURE function — facility config, booked starts,
and the tenant-local clock in; the slot permission matrix out.
Display is soft, enforcement is hard: this marks bookable/reason;
the booking endpoint (3.4) re-enforces via the same PolicyService.

get_availability is the orchestrating service function (ADR-0021 §2):
resolves facility, policy, and booked starts then returns the slot grid.
"""

import datetime
import zoneinfo

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.repositories.bookings import BookingRepository
from sport_slot.repositories.facilities import FacilityRepository
from sport_slot.services.policy import PolicyService

STATUS_AVAILABLE = "available"
STATUS_BOOKED = "booked"
STATUS_PAST = "past"


def _parse_hhmm(value: str) -> datetime.time:
    hour, minute = value.split(":")
    return datetime.time(int(hour), int(minute))


def compute_slots(
    facility: dict,
    date: datetime.date,
    booked_starts: set[str],
    now_local: datetime.datetime,
    horizon_days: int,
    window_open: str,
) -> list[dict]:
    duration = datetime.timedelta(minutes=facility["slot_duration_minutes"])

    today = now_local.date()
    days_ahead = (date - today).days

    if days_ahead > horizon_days:
        date_reason = "BEYOND_HORIZON"
    elif days_ahead == horizon_days and days_ahead > 0 and (
        now_local.time() < _parse_hhmm(window_open)
    ):
        date_reason = "WINDOW_NOT_OPEN"
    else:
        date_reason = None

    # date is already the caller's local date; weekday is derived directly.
    weekday = date.strftime("%A").lower()
    ranges = facility["weekly_schedule"].get(weekday, [])

    slots = []
    naive_now = now_local.replace(tzinfo=None)
    for r in ranges:
        open_dt = datetime.datetime.combine(date, _parse_hhmm(r["start"]))
        close_dt = datetime.datetime.combine(date, _parse_hhmm(r["end"]))
        cursor = open_dt
        while cursor + duration <= close_dt:
            start_s = cursor.strftime("%H:%M")
            end_s = (cursor + duration).strftime("%H:%M")
            if cursor + duration <= naive_now:
                status, bookable, reason = STATUS_PAST, False, "PAST"
            elif start_s in booked_starts:
                status, bookable, reason = STATUS_BOOKED, False, "BOOKED"
            elif date_reason:
                status, bookable, reason = STATUS_AVAILABLE, False, date_reason
            elif cursor <= naive_now < cursor + duration:
                # In progress: bookable remainder, marked so the UI can
                # warn before confirming (3.6 decision).
                status, bookable, reason = STATUS_AVAILABLE, True, "IN_PROGRESS"
            else:
                status, bookable, reason = STATUS_AVAILABLE, True, None
            slots.append(
                {"start": start_s, "end": end_s, "status": status,
                 "bookable": bookable, "reason": reason}
            )
            cursor += duration
    return slots


def get_availability(ctx: TenantContext, client, facility_id: str, date_str: str) -> dict:
    """Orchestrate availability for one facility + date (ADR-0021 §2)."""
    try:
        target = datetime.date.fromisoformat(date_str)
    except ValueError:
        raise ApiError(422, error_codes.INVALID_DATE, "date must be YYYY-MM-DD")

    facility = FacilityRepository(ctx, client).get(facility_id)
    if facility is None or not facility.get("active", False):
        raise ApiError(404, error_codes.FACILITY_NOT_FOUND, "Facility not found")

    policy = PolicyService(ctx, client)
    tz = zoneinfo.ZoneInfo(policy.tenant_timezone())
    now_local = datetime.datetime.now(tz)

    booked = BookingRepository(ctx, client).booked_starts(facility_id, date_str)
    slots = compute_slots(
        facility,
        target,
        booked,
        now_local,
        int(policy.get("booking_horizon_days")),
        str(policy.get("booking_window_open_time")),
    )
    return {"facility_id": facility_id, "date": date_str, "slots": slots}
