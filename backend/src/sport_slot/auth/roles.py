from fastapi import Depends

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.auth.dependency import get_tenant_context


def require_role(*allowed: str):
    """Role gate layered on TenantContext (ADR-0007 §6)."""

    def dep(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if ctx.role not in allowed:
            raise ApiError(403, error_codes.FORBIDDEN_ROLE, "Insufficient role")
        return ctx

    return dep


def require_platform_admin(
    ctx: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    """Platform-admin gate: role=platform_admin AND tenant_id=None (ADR-0014 §5)."""
    if ctx.role != "platform_admin" or ctx.tenant_id is not None:
        raise ApiError(403, error_codes.FORBIDDEN_ROLE, "Platform admin access required")
    return ctx
