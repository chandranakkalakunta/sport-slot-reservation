import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sport_slot.auth.context import TenantContext
from sport_slot.auth.dependency import get_tenant_context
from sport_slot.dependencies import get_firestore_client, get_lock_service
from sport_slot.repositories.bookings import (
    AuditRepository,  # noqa: F401 — test patch compat (test_cancellation.py)
    BookingRepository,  # noqa: F401 — test patch compat (test_cancellation.py)
    create_booking_with_quota,  # noqa: F401 — test patch compat: tests mock at this module path
)
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
    return await _svc_create_booking(
        ctx, client, lock, body.facility_id, body.date, body.start,
        _quota_create_fn=create_booking_with_quota,
    )


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
