"""Computed availability (ADR-0010 §1): nothing is pre-generated.

compute_slots is a PURE function — facility config, booked starts,
and the tenant-local clock in; the slot permission matrix out.
Display is soft, enforcement is hard: this marks bookable/reason;
the booking endpoint (3.4) re-enforces via the same PolicyService.
"""

import datetime

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
    open_dt = datetime.datetime.combine(date, _parse_hhmm(facility["open_time"]))
    close_dt = datetime.datetime.combine(date, _parse_hhmm(facility["close_time"]))

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

    slots = []
    cursor = open_dt
    naive_now = now_local.replace(tzinfo=None)
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
