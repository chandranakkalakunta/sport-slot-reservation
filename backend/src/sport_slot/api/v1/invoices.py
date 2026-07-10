from fastapi import APIRouter, Depends

from sport_slot.auth.context import TenantContext
from sport_slot.auth.dependency import get_tenant_context
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
