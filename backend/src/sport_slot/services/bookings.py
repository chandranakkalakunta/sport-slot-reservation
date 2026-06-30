"""Booking service functions (ADR-0021 §2 agent foundation)."""

import datetime
import zoneinfo

import structlog

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.middleware.request_id import get_request_id
from sport_slot.notifications.tasks import enqueue_notification
from sport_slot.repositories.bookings import (
    AlreadyBookedError,
    AuditRepository,
    BookingRepository,
    QuotaExceededError,
    create_booking_with_quota as _cbrq_default,
)
from sport_slot.repositories.facilities import FacilityRepository
from sport_slot.repositories.user_profiles import UserProfileRepository
from sport_slot.services.availability import compute_slots
from sport_slot.services.facilities import list_facilities
from sport_slot.services.lock import LockService, LockUnavailableError
from sport_slot.services.policy import PolicyService

log = structlog.get_logger()


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
    ctx: TenantContext, client, limit: int = 20, cursor: str | None = None,
    from_date: str | None = None,
) -> dict:
    """Return paginated bookings for the calling user with cancellable annotation.

    from_date (ISO date string): when set, only confirmed bookings on or after
    this date are returned.  The /bookings/mine endpoint passes tenant-local
    today so the backend is the authoritative source for 'upcoming'.
    """
    items, next_cursor = BookingRepository(ctx, client).list_for_uid(
        ctx.uid, limit=limit, cursor=cursor, from_date=from_date
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
    sport = (facility.get("sport") or facility.get("facility_type_id") or "").lower()
    facilities = list_facilities(ctx, client)
    try:
        quota = int(policy.get("max_slots_per_user_per_sport_per_day"))
        _quota_create_fn(repo, booking_id, doc, ctx.uid, date, quota, sport, facilities)
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

    # Best-effort notification (ADR-0019): booking is already committed above;
    # a failure here must never surface as a booking error. Runs for both
    # manual (HTTP router) and agent paths — moving here from the router ensures
    # agent-confirmed bookings also produce emails (6.3 regression fix).
    try:
        profile = UserProfileRepository(ctx, client).get(ctx.uid)
        tenant_snap = client.collection("tenants").document(ctx.tenant_id).get()
        tenant = tenant_snap.to_dict() if tenant_snap.exists else None
        if profile and profile.get("email") and tenant and facility:
            enqueue_notification(
                event_type="booking_confirmed",
                to=profile["email"],
                params={
                    "user_name": profile.get("display_name", ""),
                    "tenant_name": tenant.get("display_name", ""),
                    "facility": facility.get("name", ""),
                    "sport": facility.get("sport", ""),
                    "date": date,
                    "start_time": start,
                    "end_time": doc["end"],
                    "booking_id": booking_id,
                },
            )
    except Exception as exc:  # noqa: BLE001 - best-effort; booking already committed
        log.warning("notification_enqueue_failed", event_type="booking_confirmed",
                    booking_id=booking_id, error=str(exc))

    if slot.get("reason") == "IN_PROGRESS":
        return {**doc, "notice": "Slot already in progress; you have booked the remaining time"}
    return doc


def cancel_booking(
    ctx: TenantContext,
    client,
    booking_id: str,
    *,
    source: str = "manual",  # "manual" → "booking.cancelled"; "agent" → "agent.booking_cancelled"
) -> dict:
    """Orchestrate a cancellation: lookup → ownership check → buffer check → update → audit.

    Behavior is identical to the previous router handler. source param adds the
    ADR-0022 §8 agent audit-differentiation seam (consistent with create_booking).
    Returns the post-update booking doc (or {} if the read-back fails).
    """
    repo = BookingRepository(ctx, client)
    booking = repo.get(booking_id)
    if booking is None:
        raise ApiError(404, error_codes.BOOKING_NOT_FOUND, "Booking not found")
    if booking["uid"] != ctx.uid and ctx.role != "tenant_admin":
        raise ApiError(
            403, error_codes.CANCELLATION_FORBIDDEN,
            "Only the booking owner or a tenant admin may cancel",
        )
    if booking["status"] == "cancelled":
        raise ApiError(409, error_codes.ALREADY_CANCELLED, "Already cancelled")

    policy = PolicyService(ctx, client)
    tz = zoneinfo.ZoneInfo(policy.tenant_timezone())
    now_local = datetime.datetime.now(tz).replace(tzinfo=None)
    buffer_hours = int(policy.get("cancellation_buffer_hours"))
    if not _is_cancellable(booking, now_local, buffer_hours):
        raise ApiError(
            422, error_codes.CANCELLATION_TOO_LATE,
            f"Cancellation closes {buffer_hours}h before the slot",
        )

    cancelled_by = "self" if booking["uid"] == ctx.uid else "tenant_admin"
    repo.update(booking_id, {
        "status": "cancelled",
        "cancelled_at": datetime.datetime.now(datetime.UTC),
        "cancelled_by": cancelled_by,
        "cancelled_by_uid": ctx.uid,
    })
    event_type = "booking.cancelled" if source == "manual" else "agent.booking_cancelled"
    AuditRepository(ctx, client).write_event(
        event_type, ctx.uid, ctx.role, booking_id,
        get_request_id(), {"cancelled_by": cancelled_by},
    )
    return repo.get(booking_id) or {}
