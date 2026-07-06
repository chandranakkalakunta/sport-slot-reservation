import datetime
import re
import uuid

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.auth.dependency import get_tenant_context
from sport_slot.auth.roles import require_role
from sport_slot.dependencies import get_firestore_client
from sport_slot.middleware.request_id import get_request_id
from sport_slot.repositories.bookings import AuditRepository, BookingRepository  # noqa: F401 — test patch compat
from sport_slot.repositories.facilities import FacilityRepository
from sport_slot.services.availability import get_availability
from sport_slot.services.bookings import cancel_booking

log = structlog.get_logger()

# ── Reader router (any authenticated user) ─────────────────────────────────
router = APIRouter(prefix="/facilities", tags=["facilities"])


@router.get("")
async def list_facilities(
    limit: int = 20,
    cursor: str | None = None,
    ctx: TenantContext = Depends(get_tenant_context),
    client=Depends(get_firestore_client),
):
    items, next_cursor = FacilityRepository(ctx, client).list(
        limit=limit, cursor=cursor
    )
    return {"items": items, "next_cursor": next_cursor}


@router.get("/{facility_id}")
async def get_facility(
    facility_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    client=Depends(get_firestore_client),
):
    doc = FacilityRepository(ctx, client).get(facility_id)
    if doc is None:
        raise ApiError(404, error_codes.FACILITY_NOT_FOUND, "Facility not found")
    return doc


@router.get("/{facility_id}/availability")
async def facility_availability(
    facility_id: str,
    date: str,
    ctx: TenantContext = Depends(get_tenant_context),
    client=Depends(get_firestore_client),
):
    return get_availability(ctx, client, facility_id, date)


# ── Catalog-based tenant-admin management router (ADR-0015 §2, §5) ─────────

# Reuses the same HH:MM pattern as booking_window_open_time in tenant_config.py.
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class TimeRange(BaseModel):
    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def _hhmm_format(cls, v: str) -> str:
        if not _HHMM.match(v):
            raise ValueError("must be HH:MM (00:00–23:59)")
        return v

    @field_validator("end")
    @classmethod
    def _end_after_start(cls, v: str, info) -> str:
        start = info.data.get("start")
        if start and _HHMM.match(start) and v <= start:
            raise ValueError("end must be after start")
        return v


def _validate_schedule(schedule: dict) -> dict:
    missing = [d for d in _DAYS if d not in schedule]
    extra = [k for k in schedule if k not in _DAYS]
    if missing:
        raise ValueError(f"weekly_schedule missing days: {missing}")
    if extra:
        raise ValueError(f"weekly_schedule has unknown day keys: {extra}")
    for day, ranges in schedule.items():
        for i in range(1, len(ranges)):
            if ranges[i].start < ranges[i - 1].end:
                raise ValueError(
                    f"{day}: ranges must be chronologically ordered and non-overlapping "
                    f"(range {i} start {ranges[i].start!r} overlaps previous end {ranges[i-1].end!r})"
                )
    return schedule


class FacilityCreate(BaseModel):
    facility_type_id: str
    name: str
    weekly_schedule: dict[str, list[TimeRange]]
    slot_duration_minutes: int
    description: str | None = None

    @field_validator("weekly_schedule")
    @classmethod
    def _valid_schedule(cls, v: dict) -> dict:
        return _validate_schedule(v)


class FacilityUpdate(BaseModel):
    name: str | None = None
    weekly_schedule: dict[str, list[TimeRange]] | None = None
    slot_duration_minutes: int | None = None
    description: str | None = None

    @field_validator("weekly_schedule")
    @classmethod
    def _valid_schedule(cls, v: dict | None) -> dict | None:
        if v is None:
            return v
        return _validate_schedule(v)


tenant_facilities_router = APIRouter(prefix="/tenant/facilities", tags=["facilities"])


@tenant_facilities_router.post("", status_code=201)
async def create_facility(
    body: FacilityCreate,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    # Validate the catalog type exists.
    cat = client.collection("facility_catalog").document(body.facility_type_id).get()
    if not cat.exists:
        raise ApiError(422, error_codes.VALIDATION_FAILED,
                       f"Unknown facility_type_id: {body.facility_type_id}")
    facility_id = uuid.uuid4().hex[:12]
    doc = {
        "id": facility_id,
        "facility_type_id": body.facility_type_id,
        "sport": (cat.to_dict() or {}).get("sport"),
        "name": body.name,
        "weekly_schedule": {
            day: [r.model_dump() for r in ranges]
            for day, ranges in body.weekly_schedule.items()
        },
        "slot_duration_minutes": body.slot_duration_minutes,
        "description": body.description,
        "active": True,
    }
    (client.collection("tenants").document(ctx.tenant_id)
     .collection("facilities").document(facility_id).set(doc))
    return doc


@tenant_facilities_router.get("")
async def list_tenant_facilities(
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    facs = (client.collection("tenants").document(ctx.tenant_id)
            .collection("facilities").stream())
    return {"items": [f.to_dict() for f in facs]}


@tenant_facilities_router.patch("/{facility_id}")
async def update_facility(
    facility_id: str, body: FacilityUpdate,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    ref = (client.collection("tenants").document(ctx.tenant_id)
           .collection("facilities").document(facility_id))
    if not ref.get().exists:
        raise ApiError(404, error_codes.NOT_FOUND, "Facility not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    ref.update(updates)
    return ref.get().to_dict()


@tenant_facilities_router.delete("/{facility_id}")
async def delete_facility(
    facility_id: str,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    ref = (client.collection("tenants").document(ctx.tenant_id)
           .collection("facilities").document(facility_id))
    if not ref.get().exists:
        raise ApiError(404, error_codes.NOT_FOUND, "Facility not found")

    today = datetime.date.today().isoformat()
    bookings_col = (client.collection("tenants").document(ctx.tenant_id)
                    .collection("bookings"))
    query = (
        bookings_col
        .where("facility_id", "==", facility_id)
        .where("status", "==", "confirmed")
        .where("date", ">=", today)
    )

    cancelled_count = 0
    failed_ids: list[str] = []
    for snap in query.stream():
        booking_doc = snap.to_dict()
        bid = booking_doc.get("id", snap.id)
        try:
            cancel_booking(ctx, client, bid,
                           force=True, cancelled_by_override="facility_deleted")
            cancelled_count += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("facility_deletion_booking_cancel_failed",
                        booking_id=bid, facility_id=facility_id, error=str(exc))
            failed_ids.append(bid)

    if failed_ids:
        log.warning("facility_deletion_partial_failure",
                    facility_id=facility_id, failed_booking_ids=failed_ids)

    AuditRepository(ctx, client).write_event(
        event_type="facility.deleted",
        actor_uid=ctx.uid,
        actor_role=ctx.role,
        booking_id="-",
        request_id=get_request_id(),
        details={"facility_id": facility_id, "bookings_cancelled": cancelled_count},
    )

    ref.delete()

    return {"id": facility_id, "status": "deleted", "bookings_cancelled": cancelled_count}
