import firebase_admin.auth as fb_auth
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.auth.dependency import get_tenant_context
from sport_slot.auth.password_policy import validate_password
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


class ChangePasswordBody(BaseModel):
    new_password: str


@router.post("/me/change-password")
async def change_password(
    body: ChangePasswordBody,
    ctx: TenantContext = Depends(get_tenant_context),
    client=Depends(get_firestore_client),
):
    result = await validate_password(body.new_password)
    if not result.ok:
        raise ApiError(422, error_codes.WEAK_PASSWORD, " ".join(result.errors))
    fb_auth.update_user(ctx.uid, password=body.new_password)
    if ctx.tenant_id:
        (
            client.collection("tenants")
            .document(ctx.tenant_id)
            .collection("users")
            .document(ctx.uid)
            .update({"must_change_password": False})  # nosec B105 - Firestore field name, not a credential
        )
    return {"status": "ok"}
