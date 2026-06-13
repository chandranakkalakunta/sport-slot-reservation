import datetime
import zoneinfo

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.auth.dependency import get_tenant_context
from sport_slot.dependencies import get_firestore_client, get_lock_service
from sport_slot.middleware.request_id import get_request_id
from sport_slot.repositories.bookings import (
    AlreadyBookedError,
    AuditRepository,
    BookingRepository,
    QuotaExceededError,
    create_booking_with_quota,
)
from sport_slot.repositories.facilities import FacilityRepository
from sport_slot.services.availability import compute_slots
from sport_slot.services.lock import LockService, LockUnavailableError
from sport_slot.services.policy import PolicyService

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _is_cancellable(booking: dict, now_local: datetime.datetime, buffer_hours: int) -> bool:
    if booking.get("status") != "confirmed":
        return False
    slot_start = datetime.datetime.combine(
        datetime.date.fromisoformat(booking["date"]),
        datetime.time.fromisoformat(booking["start"]),
    )
    deadline = slot_start - datetime.timedelta(hours=buffer_hours)
    return now_local < deadline


class BookingCreate(BaseModel):
    facility_id: str
    date: str
    start: str


@router.post("", status_code=201)
async def create_booking(
    body: BookingCreate,
    ctx: TenantContext = Depends(get_tenant_context),
    client=Depends(get_firestore_client),
    lock: LockService = Depends(get_lock_service),
):
    try:
        target = datetime.date.fromisoformat(body.date)
    except ValueError:
        raise ApiError(422, error_codes.INVALID_DATE, "date must be YYYY-MM-DD")

    facility = FacilityRepository(ctx, client).get(body.facility_id)
    if facility is None or not facility.get("active", False):
        raise ApiError(404, error_codes.FACILITY_NOT_FOUND, "Facility not found")

    policy = PolicyService(ctx, client)
    tz = zoneinfo.ZoneInfo(policy.tenant_timezone())
    now_local = datetime.datetime.now(tz)

    repo = BookingRepository(ctx, client)
    booked = repo.booked_starts(body.facility_id, body.date)
    slots = compute_slots(
        facility, target, booked, now_local,
        int(policy.get("booking_horizon_days")),
        str(policy.get("booking_window_open_time")),
    )
    slot = next((s for s in slots if s["start"] == body.start), None)
    if slot is None:
        raise ApiError(422, error_codes.SLOT_NOT_BOOKABLE, "start is not on the slot grid")
    if not slot["bookable"]:
        raise ApiError(422, error_codes.SLOT_NOT_BOOKABLE, f"Slot not bookable: {slot['reason']}")

    key = LockService.slot_key(ctx.tenant_id, body.facility_id, body.date, body.start)
    try:
        token = await lock.acquire(key)
    except LockUnavailableError:
        raise ApiError(503, error_codes.LOCK_UNAVAILABLE, "Booking temporarily unavailable")
    if token is None:
        raise ApiError(409, error_codes.SLOT_CONTENDED, "Slot is being booked; retry shortly")

    booking_id = f"{body.facility_id}_{body.date}_{body.start}"
    doc = {
        "id": booking_id,
        "uid": ctx.uid,
        "household_id": ctx.household_id,
        "facility_id": body.facility_id,
        "date": body.date,
        "start": body.start,
        "end": slot["end"],
        "status": "confirmed",
        "created_at": datetime.datetime.now(datetime.UTC),
        "cancelled_at": None,
    }
    try:
        quota = int(policy.get("max_slots_per_user_per_sport_per_day"))
        create_booking_with_quota(repo, booking_id, doc, ctx.uid, body.date, quota)
    except QuotaExceededError:
        raise ApiError(409, error_codes.BOOKING_QUOTA_EXCEEDED, "Daily booking quota reached")
    except AlreadyBookedError:
        raise ApiError(409, error_codes.ALREADY_BOOKED, "Slot already booked")
    finally:
        await lock.release(key, token)

    AuditRepository(ctx, client).write_event(
        "booking.created", ctx.uid, ctx.role, booking_id,
        get_request_id(), {"date": body.date, "start": body.start,
                           "facility_id": body.facility_id},
    )
    if slot.get("reason") == "IN_PROGRESS":
        return {**doc, "notice": "Slot already in progress; you have booked the remaining time"}
    return doc


@router.get("/mine")
async def my_bookings(
    limit: int = 20,
    cursor: str | None = None,
    ctx: TenantContext = Depends(get_tenant_context),
    client=Depends(get_firestore_client),
):
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


@router.post("/{booking_id}/cancel")
async def cancel_booking(
    booking_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    client=Depends(get_firestore_client),
):
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
    AuditRepository(ctx, client).write_event(
        "booking.cancelled", ctx.uid, ctx.role, booking_id,
        get_request_id(), {"cancelled_by": cancelled_by},
    )
    return repo.get(booking_id) or {}
