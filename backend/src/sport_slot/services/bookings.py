"""Booking service functions (ADR-0021 §2 agent foundation)."""

import datetime
import zoneinfo

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.middleware.request_id import get_request_id
from sport_slot.repositories.bookings import (
    AlreadyBookedError,
    AuditRepository,
    BookingRepository,
    QuotaExceededError,
    create_booking_with_quota as _cbrq_default,
)
from sport_slot.repositories.facilities import FacilityRepository
from sport_slot.services.availability import compute_slots
from sport_slot.services.lock import LockService, LockUnavailableError
from sport_slot.services.policy import PolicyService


def _is_cancellable(booking: dict, now_local: datetime.datetime, buffer_hours: int) -> bool:
    if booking.get("status") != "confirmed":
        return False
    slot_start = datetime.datetime.combine(
        datetime.date.fromisoformat(booking["date"]),
        datetime.time.fromisoformat(booking["start"]),
    )
    deadline = slot_start - datetime.timedelta(hours=buffer_hours)
    return now_local < deadline


def list_my_bookings(
    ctx: TenantContext, client, limit: int = 20, cursor: str | None = None
) -> dict:
    """Return paginated bookings for the calling user with cancellable annotation."""
    items, next_cursor = BookingRepository(ctx, client).list_for_uid(
        ctx.uid, limit=limit, cursor=cursor
    )
    policy = PolicyService(ctx, client)
    tz = zoneinfo.ZoneInfo(policy.tenant_timezone())
    now_local = datetime.datetime.now(tz).replace(tzinfo=None)
    buffer_hours = int(policy.get("cancellation_buffer_hours"))
    annotated = [
        {**item, "cancellable": _is_cancellable(item, now_local, buffer_hours)}
        for item in items
    ]
    return {"items": annotated, "next_cursor": next_cursor}


async def create_booking(
    ctx: TenantContext,
    client,
    lock: LockService,
    facility_id: str,
    date: str,
    start: str,
    *,
    _quota_create_fn=_cbrq_default,  # seam: callers may pass a patchable ref (see api/v1/bookings.py)
    source: str = "manual",  # "manual" → "booking.created"; "agent" → "agent.booking_created"
) -> dict:
    """Orchestrate a booking: validate slot, acquire lock, write with quota, audit.

    Lock semantics: acquired before the Firestore write; released in a finally
    block that wraps create_booking_with_quota so the lock is freed on EVERY
    path — success, QuotaExceededError, AlreadyBookedError, or unexpected exception.
    Audit is written AFTER the finally (lock already released), so a slow audit
    write never extends the lock window.
    """
    try:
        target = datetime.date.fromisoformat(date)
    except ValueError:
        raise ApiError(422, error_codes.INVALID_DATE, "date must be YYYY-MM-DD")

    facility = FacilityRepository(ctx, client).get(facility_id)
    if facility is None or not facility.get("active", False):
        raise ApiError(404, error_codes.FACILITY_NOT_FOUND, "Facility not found")

    policy = PolicyService(ctx, client)
    tz = zoneinfo.ZoneInfo(policy.tenant_timezone())
    now_local = datetime.datetime.now(tz)

    repo = BookingRepository(ctx, client)
    booked = repo.booked_starts(facility_id, date)
    slots = compute_slots(
        facility, target, booked, now_local,
        int(policy.get("booking_horizon_days")),
        str(policy.get("booking_window_open_time")),
    )
    slot = next((s for s in slots if s["start"] == start), None)
    if slot is None:
        raise ApiError(422, error_codes.SLOT_NOT_BOOKABLE, "start is not on the slot grid")
    if not slot["bookable"]:
        raise ApiError(422, error_codes.SLOT_NOT_BOOKABLE, f"Slot not bookable: {slot['reason']}")

    key = LockService.slot_key(ctx.tenant_id, facility_id, date, start)
    try:
        token = await lock.acquire(key)
    except LockUnavailableError:
        raise ApiError(503, error_codes.LOCK_UNAVAILABLE, "Booking temporarily unavailable")
    if token is None:
        raise ApiError(409, error_codes.SLOT_CONTENDED, "Slot is being booked; retry shortly")

    booking_id = f"{facility_id}_{date}_{start}"
    doc = {
        "id": booking_id,
        "uid": ctx.uid,
        "household_id": ctx.household_id,
        "facility_id": facility_id,
        "date": date,
        "start": start,
        "end": slot["end"],
        "status": "confirmed",
        "created_at": datetime.datetime.now(datetime.UTC),
        "cancelled_at": None,
    }
    try:
        quota = int(policy.get("max_slots_per_user_per_sport_per_day"))
        _quota_create_fn(repo, booking_id, doc, ctx.uid, date, quota)
    except QuotaExceededError:
        raise ApiError(409, error_codes.BOOKING_QUOTA_EXCEEDED, "Daily booking quota reached")
    except AlreadyBookedError:
        raise ApiError(409, error_codes.ALREADY_BOOKED, "Slot already booked")
    finally:
        await lock.release(key, token)

    # Audit written after lock release — slow audit never extends the lock window.
    event_type = "booking.created" if source == "manual" else "agent.booking_created"
    AuditRepository(ctx, client).write_event(
        event_type, ctx.uid, ctx.role, booking_id,
        get_request_id(), {"date": date, "start": start, "facility_id": facility_id},
    )

    if slot.get("reason") == "IN_PROGRESS":
        return {**doc, "notice": "Slot already in progress; you have booked the remaining time"}
    return doc
