from fastapi import APIRouter, Depends

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.auth.dependency import get_tenant_context
from sport_slot.dependencies import get_firestore_client
from sport_slot.repositories.user_profiles import UserProfileRepository

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_me(
    ctx: TenantContext = Depends(get_tenant_context),
    client=Depends(get_firestore_client),
):
    profile = UserProfileRepository(ctx, client).get(ctx.uid)
    if profile is None:
        raise ApiError(
            404,
            error_codes.USER_PROFILE_NOT_FOUND,
            "Authenticated user has no profile (not provisioned)",
        )
    return profile
