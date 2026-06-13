from fastapi import APIRouter, Depends

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.dependencies import get_firestore_client

router = APIRouter(prefix="/tenants", tags=["branding"])

# Cosmetic-only fields exposed publicly (no auth). Never include
# anything sensitive — this is readable by anyone with the slug.
_BRANDING_DEFAULTS = {
    "brand_name": "SportSlot",
    "brand_primary_color": "#1a4d8f",
    "brand_secondary_color": "#0f7b6c",
}


@router.get("/{slug}/branding")
async def tenant_branding(slug: str, client=Depends(get_firestore_client)):
    # Look up tenant by slug. Tenants are keyed by tenant_id; slug
    # is a field — query for it.
    query = client.collection("tenants").where("slug", "==", slug).limit(1)
    docs = list(query.stream())
    if not docs:
        raise ApiError(404, error_codes.NOT_FOUND, "Tenant not found")
    data = docs[0].to_dict() or {}
    branding = data.get("branding", {})
    return {
        "slug": slug,
        "brand_name": branding.get("brand_name") or data.get("name") or _BRANDING_DEFAULTS["brand_name"],
        "brand_primary_color": branding.get("brand_primary_color") or _BRANDING_DEFAULTS["brand_primary_color"],
        "brand_secondary_color": branding.get("brand_secondary_color") or _BRANDING_DEFAULTS["brand_secondary_color"],
    }
