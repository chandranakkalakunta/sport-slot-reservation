"""Public auth endpoints — no tenant context required (ADR-0020 A2).

/auth/forgot-password: enumeration-safe, fail-closed cooldown, branded email.
/auth/forgot-password/confirm: single-use token consume, password set, sessions revoked.
"""

import datetime
import hashlib

import structlog
from fastapi import APIRouter, Depends, Request
from firebase_admin import auth as fb_auth
from pydantic import BaseModel, EmailStr

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.auth.password_policy import validate_password
from sport_slot.config import get_settings
from sport_slot.dependencies import get_firestore_client, get_redis_client
from sport_slot.middleware.request_id import get_request_id
from sport_slot.notifications.tasks import enqueue_notification
from sport_slot.ratelimit import limiter
from sport_slot.repositories.bookings import AuditRepository
from sport_slot.repositories.password_reset import ResetTokenInvalid, consume_reset_token
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


_INVALID_MSG = "This reset link is invalid or has expired."


class ConfirmResetBody(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password/confirm")
async def confirm_reset(
    body: ConfirmResetBody,
    fs=Depends(get_firestore_client),
):
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    ref = fs.collection("password_reset_tokens").document(token_hash)

    # (a) cheap non-authoritative pre-check — avoids HIBP round-trip on junk tokens
    snap = ref.get()
    if not snap.exists:
        raise ApiError(400, error_codes.RESET_TOKEN_INVALID, _INVALID_MSG)
    pre = snap.to_dict() or {}
    if pre.get("used") or pre["expires_at"] <= datetime.datetime.now(datetime.UTC):
        raise ApiError(400, error_codes.RESET_TOKEN_INVALID, _INVALID_MSG)

    # (b) validate password BEFORE consuming the token
    result = await validate_password(body.new_password)
    if not result.ok:
        raise ApiError(422, error_codes.WEAK_PASSWORD, " ".join(result.errors))

    # (c) authoritative atomic single-use consume (transactional re-check)
    try:
        info = consume_reset_token(fs, token_hash)
    except ResetTokenInvalid:
        raise ApiError(400, error_codes.RESET_TOKEN_INVALID, _INVALID_MSG)

    uid = info["uid"]
    tenant_id = info["tenant_id"]

    # (d) set the password — token already consumed; failure is the safe direction
    fb_auth.update_user(uid, password=body.new_password)

    # (e) best-effort post-steps — password is already set; never fail the 200
    try:
        fb_auth.revoke_refresh_tokens(uid)
    except Exception:
        log.warning("reset_revoke_failed", uid=uid)

    try:
        (
            fs.collection("tenants")
            .document(tenant_id)
            .collection("users")
            .document(uid)
            .update({"must_change_password": False})  # nosec B105
        )
    except Exception:
        log.warning("reset_flag_clear_failed", uid=uid)

    try:
        AuditRepository(
            TenantContext(
                uid=uid,
                tenant_id=tenant_id,
                tenant_slug=None,
                role="resident",
                household_id=None,
            ),
            fs,
        ).write_event(
            "auth.password_reset_completed",
            uid,
            "",
            "",
            get_request_id(),
            {"via": "self_service"},
        )
    except Exception:
        log.warning("reset_audit_failed", uid=uid)

    return {"status": "ok", "message": "Password has been reset."}
