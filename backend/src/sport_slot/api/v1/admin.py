"""Platform-admin API endpoints (ADR-0014 §5)."""
import datetime
import re
import uuid

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.auth.roles import require_platform_admin
from sport_slot.dependencies import get_firestore_client
from sport_slot.middleware.request_id import get_request_id
from sport_slot.repositories.base import PlatformRepository
from sport_slot.services.provisioning import ProvisioningError, UserProvisioningService


def _provisioning_error(e: ProvisioningError) -> ApiError:
    return e

router = APIRouter(prefix="/admin", tags=["admin"])

_SLUG_RE = re.compile(r"^[a-z0-9-]{3,30}$")
_BULK_LIMIT = 500


class CreateTenantBody(BaseModel):
    slug: str
    display_name: str


class CreateUserBody(BaseModel):
    email: str
    display_name: str
    flat_number: str | None = None
    role: str = "resident"
    household_id: str | None = None


@router.post("/tenants", status_code=201)
async def create_tenant(
    body: CreateTenantBody,
    ctx: TenantContext = Depends(require_platform_admin),
    client=Depends(get_firestore_client),
):
    if not _SLUG_RE.match(body.slug):
        raise ApiError(422, error_codes.INVALID_SLUG, "Slug must match [a-z0-9-]{3,30}")
    repo = PlatformRepository(ctx, client)
    if repo.get_tenant_by_slug(body.slug):
        raise ApiError(409, error_codes.TENANT_SLUG_TAKEN, f"Slug {body.slug!r} is already taken")
    tenant_id = f"t-{uuid.uuid4().hex[:12]}"
    repo.create_tenant(tenant_id, {
        "tenant_id": tenant_id,
        "slug": body.slug,
        "display_name": body.display_name,
        "created_by": ctx.uid,
        "created_at": datetime.datetime.now(datetime.UTC),
        "status": "active",
    })
    return {"tenant_id": tenant_id, "slug": body.slug}


@router.get("/tenants")
async def list_tenants(
    limit: int = 20,
    cursor: str | None = None,
    ctx: TenantContext = Depends(require_platform_admin),
    client=Depends(get_firestore_client),
):
    repo = PlatformRepository(ctx, client)
    items, next_cursor = repo.list_tenants(limit=limit, cursor=cursor)
    return {"items": items, "next_cursor": next_cursor}


@router.post("/tenants/{tenant_id}/users", status_code=201)
async def create_user(
    tenant_id: str,
    body: CreateUserBody,
    ctx: TenantContext = Depends(require_platform_admin),
    client=Depends(get_firestore_client),
):
    svc = UserProvisioningService(client)
    result = svc.create_user(
        tenant_id=tenant_id,
        email=body.email,
        display_name=body.display_name,
        flat_number=body.flat_number,
        role=body.role,
        household_id=body.household_id,
    )
    return result


@router.post("/tenants/{tenant_id}/users/bulk", status_code=200)
async def bulk_create_users(
    tenant_id: str,
    body: dict = Body(...),
    ctx: TenantContext = Depends(require_platform_admin),
    client=Depends(get_firestore_client),
):
    rows = body.get("rows", [])
    if len(rows) > _BULK_LIMIT:
        raise ApiError(
            422, error_codes.VALIDATION_FAILED, f"Import exceeds {_BULK_LIMIT}-row limit"
        )
    svc = UserProvisioningService(client)
    results = []
    for i, row in enumerate(rows):
        try:
            result = svc.create_user(
                tenant_id=tenant_id,
                email=row.get("email", ""),
                display_name=row.get("display_name", ""),
                flat_number=row.get("flat_number", ""),
                role=row.get("role", "resident"),
                household_id=row.get("household_id"),
            )
            results.append({
                "row": i + 1,
                "email": row.get("email"),
                "status": "created",
                **result,
            })
        except ApiError as exc:
            results.append({
                "row": i + 1,
                "email": row.get("email"),
                "status": "failed",
                "reason": exc.message,
            })
        except Exception as exc:
            results.append({
                "row": i + 1,
                "email": row.get("email"),
                "status": "failed",
                "reason": str(exc),
            })
    return {"results": results}


@router.post("/tenants/{tenant_id}/users/{uid}/reset-password")
async def admin_reset_password(
    tenant_id: str, uid: str,
    ctx: TenantContext = Depends(require_platform_admin),
    client=Depends(get_firestore_client),
):
    svc = UserProvisioningService(client, ctx.uid, ctx.role)
    try:
        return svc.reset_password(tenant_id, uid, get_request_id())
    except ProvisioningError as e:
        raise _provisioning_error(e)


@router.delete("/tenants/{tenant_id}/users/{uid}", status_code=200)
async def deactivate_user(
    tenant_id: str,
    uid: str,
    ctx: TenantContext = Depends(require_platform_admin),
    client=Depends(get_firestore_client),
):
    svc = UserProvisioningService(client, caller_uid=ctx.uid)
    svc.deactivate_user(tenant_id=tenant_id, target_uid=uid)
    return {"status": "deactivated"}
