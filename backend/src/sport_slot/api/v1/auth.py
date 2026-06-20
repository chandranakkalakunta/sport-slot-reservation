"""Public auth endpoints — no tenant context required (ADR-0020 A2).

/auth/forgot-password: enumeration-safe, fail-closed cooldown, branded email.
"""

import structlog
from fastapi import APIRouter, Depends, Request
from firebase_admin import auth as fb_auth
from pydantic import BaseModel, EmailStr

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.config import get_settings
from sport_slot.dependencies import get_firestore_client, get_redis_client
from sport_slot.middleware.request_id import get_request_id
from sport_slot.notifications.tasks import enqueue_notification
from sport_slot.ratelimit import limiter
from sport_slot.repositories.bookings import AuditRepository
from sport_slot.services.lock import LockUnavailableError
from sport_slot.services.password_reset import enforce_cooldown, mint_and_store_token

log = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["auth"])

_UNIFORM_OK = {"status": "ok", "message": "If an account exists, a reset link was sent."}


class ForgotPasswordBody(BaseModel):
    email: EmailStr


@router.post("/forgot-password")
@limiter.limit("5/hour")
async def forgot_password(
    request: Request,
    body: ForgotPasswordBody,
    settings=Depends(get_settings),
    fs=Depends(get_firestore_client),
    redis=Depends(get_redis_client),
):
    try:
        proceed = await enforce_cooldown(redis, body.email, settings.reset_cooldown_seconds)
    except LockUnavailableError as exc:
        raise ApiError(503, error_codes.LOCK_UNAVAILABLE, "Service temporarily unavailable") from exc

    if not proceed:
        return _UNIFORM_OK

    try:
        user = fb_auth.get_user_by_email(body.email)
    except fb_auth.UserNotFoundError:
        return _UNIFORM_OK

    if user.disabled:
        return _UNIFORM_OK

    claims = user.custom_claims or {}
    tenant_id = claims.get("tenant_id")
    if not tenant_id:
        return _UNIFORM_OK

    tenant_snap = fs.collection("tenants").document(tenant_id).get()
    tenant_name = ""
    if tenant_snap.exists:
        tenant_name = (tenant_snap.to_dict() or {}).get("display_name", "")

    user_name = user.display_name or "there"

    raw = mint_and_store_token(fs, user.uid, tenant_id, settings.reset_token_ttl_seconds)

    enqueue_notification(
        event_type="password_reset",
        to=body.email,
        params={
            "user_name": user_name,
            "tenant_name": tenant_name,
            "reset_url": f"{settings.reset_continue_url}?token={raw}",
        },
    )

    AuditRepository(
        TenantContext(
            uid=user.uid,
            tenant_id=tenant_id,
            tenant_slug=claims.get("tenant_slug"),
            role=claims.get("role", "resident"),
            household_id=None,
        ),
        fs,
    ).write_event(
        "auth.password_reset_requested",
        user.uid,
        claims.get("role", "resident"),
        "",
        get_request_id(),
        {"via": "self_service"},
    )

    return _UNIFORM_OK
