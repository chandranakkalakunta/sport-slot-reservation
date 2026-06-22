import datetime
import zoneinfo

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.auth.dependency import get_tenant_context
from sport_slot.dependencies import get_firestore_client, get_lock_service
from sport_slot.middleware.request_id import get_request_id
from sport_slot.notifications.tasks import enqueue_notification
from sport_slot.repositories.bookings import (
    AuditRepository,
    BookingRepository,
    create_booking_with_quota,  # noqa: F401 — test patch compat: tests mock at this module path
)
from sport_slot.repositories.facilities import FacilityRepository
from sport_slot.repositories.user_profiles import UserProfileRepository
from sport_slot.services.bookings import (
    _is_cancellable,
    create_booking as _svc_create_booking,
    list_my_bookings,
)
from sport_slot.services.lock import LockService
from sport_slot.services.policy import PolicyService

router = APIRouter(prefix="/bookings", tags=["bookings"])
log = structlog.get_logger()


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
    # Pass the router-level name so tests can patch
    # "sport_slot.api.v1.bookings.create_booking_with_quota" and intercept it.
    result = await _svc_create_booking(
        ctx, client, lock, body.facility_id, body.date, body.start,
        _quota_create_fn=create_booking_with_quota,
    )

    # Best-effort notification (ADR-0019): booking is already committed above;
    # a failure here must never surface as a booking error.
    try:
        facility = FacilityRepository(ctx, client).get(body.facility_id)
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
                    "date": body.date,
                    "start_time": body.start,
                    "end_time": result["end"],
                    "booking_id": result["id"],
                },
            )
    except Exception as exc:  # noqa: BLE001 - best-effort; booking already committed
        log.warning("notification_enqueue_failed", event_type="booking_confirmed",
                    booking_id=result["id"], error=str(exc))

    return result


@router.get("/mine")
async def my_bookings(
    limit: int = 20,
    cursor: str | None = None,
    ctx: TenantContext = Depends(get_tenant_context),
    client=Depends(get_firestore_client),
):
    return list_my_bookings(ctx, client, limit=limit, cursor=cursor)


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
