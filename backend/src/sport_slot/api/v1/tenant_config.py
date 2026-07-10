"""Tenant-admin configuration endpoints: branding, policies, user management."""
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.auth.roles import require_role
from sport_slot.dependencies import get_firestore_client
from sport_slot.middleware.request_id import get_request_id
from sport_slot.services.provisioning import ProvisioningError, UserProvisioningService

router = APIRouter(tags=["tenant-config"])

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _provisioning_error(e: ProvisioningError) -> ApiError:
    # ProvisioningError IS-AN ApiError; return as-is for the registered handler.
    return e


# ── STEP 1: Branding ──────────────────────────────────────────────────────────

class BrandingPatch(BaseModel):
    brand_name: str | None = None
    brand_primary_color: str | None = None
    brand_secondary_color: str | None = None
    brand_logo_url: str | None = None


@router.patch("/tenant/branding")
async def update_branding(
    body: BrandingPatch,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    for key in ("brand_primary_color", "brand_secondary_color"):
        if key in updates and not _HEX.match(updates[key]):
            raise ApiError(422, error_codes.VALIDATION_FAILED,
                           f"{key} must be a hex color like #1a4d8f")
    if "brand_logo_url" in updates:
        u = updates["brand_logo_url"]
        if not (u.startswith("http://") or u.startswith("https://")):
            raise ApiError(422, error_codes.VALIDATION_FAILED,
                           "brand_logo_url must be an http(s) URL")
    ref = client.collection("tenants").document(ctx.tenant_id)
    # Merge into the nested branding map without clobbering siblings.
    existing = (ref.get().to_dict() or {}).get("branding", {})
    existing.update(updates)
    ref.update({"branding": existing})
    return {"branding": existing}


# ── STEP 2: Policies ─────────────────────────────────────────────────────────

class PoliciesPatch(BaseModel):
    booking_horizon_days: int | None = None
    booking_window_open_time: str | None = None
    cancellation_buffer_hours: int | None = None
    max_slots_per_user_per_sport_per_day: int | None = None
    invoice_generation_time: str | None = None


@router.get("/tenant/policies")
async def get_policies(
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    ref = client.collection("tenants").document(ctx.tenant_id)
    policies = (ref.get().to_dict() or {}).get("policies", {})
    return {"policies": policies}


@router.patch("/tenant/policies")
async def update_policies(
    body: PoliciesPatch,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "booking_horizon_days" in updates and updates["booking_horizon_days"] < 1:
        raise ApiError(422, error_codes.VALIDATION_FAILED, "booking_horizon_days must be >= 1")
    if "cancellation_buffer_hours" in updates and updates["cancellation_buffer_hours"] < 0:
        raise ApiError(422, error_codes.VALIDATION_FAILED, "cancellation_buffer_hours must be >= 0")
    if ("max_slots_per_user_per_sport_per_day" in updates
            and updates["max_slots_per_user_per_sport_per_day"] < 1):
        raise ApiError(422, error_codes.VALIDATION_FAILED, "max_slots must be >= 1")
    if ("booking_window_open_time" in updates
            and not _HHMM.match(updates["booking_window_open_time"])):
        raise ApiError(422, error_codes.VALIDATION_FAILED, "booking_window_open_time must be HH:MM")
    if ("invoice_generation_time" in updates
            and not _HHMM.match(updates["invoice_generation_time"])):
        raise ApiError(422, error_codes.VALIDATION_FAILED, "invoice_generation_time must be HH:MM")
    ref = client.collection("tenants").document(ctx.tenant_id)
    existing = (ref.get().to_dict() or {}).get("policies", {})
    existing.update(updates)
    ref.update({"policies": existing})
    return {"policies": existing}


# ── STEP 3: Tenant user management ───────────────────────────────────────────

class TenantUserCreate(BaseModel):
    email: str
    display_name: str
    flat_number: str | None = None
    role: str = "resident"
    household_id: str | None = None


@router.post("/tenant/users", status_code=201)
async def create_tenant_user(
    body: TenantUserCreate,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    svc = UserProvisioningService(client, ctx.uid, ctx.role)
    try:
        return svc.create_user(
            ctx.tenant_id, body.email, body.display_name, body.flat_number,
            body.role, body.household_id, get_request_id())
    except ProvisioningError as e:
        raise _provisioning_error(e)


@router.get("/tenant/users")
async def list_tenant_users(
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    users = (client.collection("tenants").document(ctx.tenant_id)
             .collection("users").stream())
    # Never expose secrets; return profile fields only.
    return {"items": [u.to_dict() for u in users]}


@router.delete("/tenant/users/{uid}")
async def deactivate_tenant_user(
    uid: str,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    svc = UserProvisioningService(client, ctx.uid, ctx.role)
    try:
        return svc.deactivate_user(ctx.tenant_id, uid, get_request_id())
    except ProvisioningError as e:
        raise _provisioning_error(e)


@router.delete("/tenant/users/{uid}/permanent")
async def delete_tenant_user_permanently(
    uid: str,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    svc = UserProvisioningService(client, ctx.uid, ctx.role)
    try:
        return svc.delete_user_permanently(ctx.tenant_id, uid, get_request_id())
    except ProvisioningError as e:
        raise _provisioning_error(e)


@router.post("/tenant/users/{uid}/reset-password")
async def tenant_reset_password(
    uid: str,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    svc = UserProvisioningService(client, ctx.uid, ctx.role)
    try:
        return svc.reset_password(ctx.tenant_id, uid, get_request_id())
    except ProvisioningError as e:
        raise _provisioning_error(e)


# ── STEP 4: Bulk import ───────────────────────────────────────────────────────

class BulkRow(BaseModel):
    email: str
    display_name: str
    flat_number: str | None = None
    role: str = "resident"
    household_id: str | None = None


class BulkRequest(BaseModel):
    rows: list[BulkRow]


@router.post("/tenant/users/bulk")
async def bulk_create_users(
    body: BulkRequest,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    if len(body.rows) > 500:
        raise ApiError(422, error_codes.VALIDATION_FAILED,
                       "Bulk import capped at 500 rows per request")
    svc = UserProvisioningService(client, ctx.uid, ctx.role)
    results = []
    for i, row in enumerate(body.rows):
        try:
            created = svc.create_user(
                ctx.tenant_id, row.email, row.display_name, row.flat_number,
                row.role, row.household_id, get_request_id())
            results.append({"row": i + 1, "email": row.email,
                            "status": "created", "temp_password": created["temp_password"]})
        except ProvisioningError as e:
            results.append({"row": i + 1, "email": row.email,
                            "status": "failed", "reason": e.code})
        except Exception:  # noqa: BLE001 - one bad row must not abort the batch
            results.append({"row": i + 1, "email": row.email,
                            "status": "failed", "reason": "UNKNOWN"})
    created_n = sum(1 for r in results if r["status"] == "created")
    return {"total": len(results), "created": created_n,
            "failed": len(results) - created_n, "results": results}
