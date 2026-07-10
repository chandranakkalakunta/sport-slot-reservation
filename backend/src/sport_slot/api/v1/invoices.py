from fastapi import APIRouter, Depends

from sport_slot.auth.context import TenantContext
from sport_slot.auth.dependency import get_tenant_context
from sport_slot.auth.roles import require_role
from sport_slot.dependencies import get_firestore_client
from sport_slot.repositories.invoices import InvoiceRepository

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("/mine")
async def my_invoices(
    ctx: TenantContext = Depends(get_tenant_context),
    client=Depends(get_firestore_client),
):
    """Caller's own household's invoices only (Phase 15.4) — scoped strictly
    to ctx.household_id, never another household's. See
    InvoiceRepository.list_for_household for the None-household_id guard."""
    items = InvoiceRepository(ctx, client).list_for_household(ctx.household_id)
    return {"items": items}


@router.get("/tenant/latest")
async def tenant_latest_invoices(
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    """Tenant-admin only (Phase 15.4b): latest invoice per household across
    the whole tenant, for quickly looking up any resident's current billing
    status by flat. Latest-only, no history drill-down (Coordinator decision).
    Needs zero profile lookups — flat_number/resident_name are already
    denormalized onto every invoice at generation time (15.3 correction)."""
    items = InvoiceRepository(ctx, client).list_latest_per_household()
    return {"items": items}
