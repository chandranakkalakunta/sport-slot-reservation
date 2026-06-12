import datetime
import uuid

from fastapi import APIRouter, Depends

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.auth.dependency import get_tenant_context
from sport_slot.auth.roles import require_role
from sport_slot.dependencies import get_firestore_client
from sport_slot.models.facility import FacilityCreate, FacilityUpdate
from sport_slot.repositories.facilities import FacilityRepository

router = APIRouter(prefix="/facilities", tags=["facilities"])


@router.post("", status_code=201)
async def create_facility(
    body: FacilityCreate,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    fid = uuid.uuid4().hex[:12]
    doc = body.model_dump()
    doc.update(
        {"id": fid, "created_at": datetime.datetime.now(datetime.UTC)}
    )
    FacilityRepository(ctx, client).create(fid, doc)
    return doc


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


@router.patch("/{facility_id}")
async def update_facility(
    facility_id: str,
    body: FacilityUpdate,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    repo = FacilityRepository(ctx, client)
    if repo.get(facility_id) is None:
        raise ApiError(404, error_codes.FACILITY_NOT_FOUND, "Facility not found")
    changes = body.model_dump(exclude_none=True)
    if changes:
        repo.update(facility_id, changes)
    return repo.get(facility_id) or {}
