from fastapi import APIRouter, Depends

from sport_slot.auth.context import TenantContext
from sport_slot.auth.dependency import get_tenant_context
from sport_slot.dependencies import get_firestore_client

router = APIRouter(tags=["facility-catalog"])


@router.get("/facility-catalog")
async def list_facility_catalog(
    ctx: TenantContext = Depends(get_tenant_context),
    client=Depends(get_firestore_client),
):
    items = [d.to_dict() for d in client.collection("facility_catalog").stream()]
    return {"items": items}
