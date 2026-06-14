from fastapi import Depends, Request
from firebase_admin import auth as fb_auth

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.config import Settings, get_settings


def _effective_host(request: Request) -> str:
    # Prefer X-Forwarded-Host (set by Firebase Hosting rewrites); fall back to Host.
    xfh = request.headers.get("x-forwarded-host", "")
    raw = xfh.split(",")[0].strip() if xfh else request.headers.get("host", "")
    return raw.split(":")[0].lower()


def _slug_from_host(host: str, settings: Settings) -> str | None:
    # Recognized tenant subdomain → that slug; any other host
    # (localhost, *.web.app, *.run.app) → None, meaning "no host-
    # derived tenant; trust the JWT tenant_slug claim" (ADR-0012 §2,
    # JWT authoritative per ADR-0007). No dev-tenant pin: it would
    # override a valid claim and break every non-default tenant in
    # local dev (5.3.1).
    suffix = "." + settings.base_domain
    if host.endswith(suffix):
        return host.removesuffix(suffix)
    return None


def get_tenant_context(
    request: Request, settings: Settings = Depends(get_settings)
) -> TenantContext:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise ApiError(401, error_codes.AUTH_MISSING_TOKEN, "Missing bearer token")
    token = auth_header.removeprefix("Bearer ").strip()

    try:
        claims = fb_auth.verify_id_token(token)
    except Exception as exc:
        raise ApiError(401, error_codes.AUTH_INVALID_TOKEN, "Token verification failed") from exc

    role = claims.get("role")
    if not role:
        raise ApiError(401, error_codes.AUTH_INVALID_TOKEN, "Token missing provisioned claims")

    host = _effective_host(request)

    # ADR-0014 §1: route+role gating (require_platform_admin) is the
    # authorization layer in DEV. Host-segregation is deferred to Phase 9
    # (see charter accepted exposures). settings.admin_host is preserved
    # for the Phase 9 migration but is not enforced here.
    if role == "platform_admin":
        return TenantContext(
            uid=claims["uid"], tenant_id=None, tenant_slug=None, role=role, household_id=None
        )

    tenant_slug = claims.get("tenant_slug")
    tenant_id = claims.get("tenant_id")
    if not tenant_slug or not tenant_id:
        raise ApiError(401, error_codes.AUTH_INVALID_TOKEN, "Token missing provisioned claims")

    slug = _slug_from_host(host, settings)
    # ADR-0012 §2: enforce only when the host resolves to a recognized tenant
    # subdomain; unrecognized hosts (*.web.app, *.run.app, localhost) fall back
    # to trusting the JWT tenant_slug claim (JWT is authoritative, ADR-0007).
    if slug is not None and slug != tenant_slug:
        raise ApiError(403, error_codes.TENANT_MISMATCH, "Tenant mismatch")

    return TenantContext(
        uid=claims["uid"],
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        role=role,
        household_id=claims.get("household_id"),
    )
