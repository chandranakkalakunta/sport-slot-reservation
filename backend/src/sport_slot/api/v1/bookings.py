import datetime
import zoneinfo

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.auth.dependency import get_tenant_context
from sport_slot.dependencies import get_firestore_client, get_lock_service
from sport_slot.repositories.bookings import (
    AlreadyBookedError,
    BookingRepository,
    QuotaExceededError,
    create_booking_with_quota,
)
from sport_slot.repositories.facilities import FacilityRepository
from sport_slot.services.availability import compute_slots
from sport_slot.services.lock import LockService, LockUnavailableError
from sport_slot.services.policy import PolicyService

router = APIRouter(prefix="/bookings", tags=["bookings"])


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

    return doc
