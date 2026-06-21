import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.auth.dependency import get_tenant_context
from sport_slot.auth.roles import require_role
from sport_slot.dependencies import get_firestore_client
from sport_slot.repositories.bookings import BookingRepository  # noqa: F401 — test patch compat
from sport_slot.repositories.facilities import FacilityRepository
from sport_slot.services.availability import get_availability

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
class FacilityCreate(BaseModel):
    facility_type_id: str
    name: str
    open_time: str          # "06:00"
    close_time: str         # "22:00"
    slot_duration_minutes: int
    description: str | None = None


class FacilityUpdate(BaseModel):
    name: str | None = None
    open_time: str | None = None
    close_time: str | None = None
    slot_duration_minutes: int | None = None
    description: str | None = None


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
        "open_time": body.open_time,
        "close_time": body.close_time,
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
async def deactivate_facility(
    facility_id: str,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    ref = (client.collection("tenants").document(ctx.tenant_id)
           .collection("facilities").document(facility_id))
    if not ref.get().exists:
        raise ApiError(404, error_codes.NOT_FOUND, "Facility not found")
    ref.update({"active": False})
    return {"id": facility_id, "active": False}
