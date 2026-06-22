import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sport_slot.auth.context import TenantContext
from sport_slot.auth.dependency import get_tenant_context
from sport_slot.dependencies import get_firestore_client, get_lock_service
from sport_slot.notifications.tasks import enqueue_notification
from sport_slot.repositories.bookings import (
    AuditRepository,  # noqa: F401 — test patch compat (test_cancellation.py)
    BookingRepository,  # noqa: F401 — test patch compat (test_cancellation.py)
    create_booking_with_quota,  # noqa: F401 — test patch compat: tests mock at this module path
)
from sport_slot.repositories.facilities import FacilityRepository
from sport_slot.repositories.user_profiles import UserProfileRepository
from sport_slot.services.bookings import (
    cancel_booking as _svc_cancel_booking,
    create_booking as _svc_create_booking,
    list_my_bookings,
)
from sport_slot.services.lock import LockService

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
    return _svc_cancel_booking(ctx, client, booking_id)
