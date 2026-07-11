import datetime

from fastapi import APIRouter, Depends

from sport_slot.auth.context import TenantContext
from sport_slot.auth.dependency import get_tenant_context
from sport_slot.auth.roles import require_role
from sport_slot.dependencies import get_firestore_client
from sport_slot.repositories.invoices import InvoiceRepository
from sport_slot.services.invoice_export import export_invoices_for_period, signed_export_urls
from sport_slot.services.invoicing import (
    _previous_month_range,
    preview_current_month_charge,
    regenerate_for_tenant,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _resolve_period(period: str | None) -> str:
    """Default to the previous calendar month (same period the scheduled
    generation job would cover) when the caller doesn't specify one."""
    if period is not None:
        return period
    _, _, period_label = _previous_month_range(datetime.date.today())
    return period_label


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


@router.get("/tenant/history")
async def tenant_invoice_history(
    household_id: str,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    """Tenant-admin only (Phase 15.4c): a SPECIFIC household's last 3
    generated invoices, most-recent-first — for dispute-resolution history.
    Unlike /mine, this accepts an arbitrary household_id (any household in
    the admin's own tenant), not ctx.household_id; reuses list_for_household
    (Phase 15.4) unchanged, just with limit=3."""
    items = InvoiceRepository(ctx, client).list_for_household(household_id, limit=3)
    return {"items": items}


@router.get("/tenant/preview")
async def tenant_invoice_preview(
    household_id: str,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    """Tenant-admin only (Phase 15.4c): a LIVE, unpersisted preview of a
    household's CURRENT in-progress month — writes nothing to Firestore.
    Calls the exact same computation the real monthly generator uses
    (services.invoicing.preview_current_month_charge), just against the
    current month, so the preview and a real invoice can never disagree."""
    return preview_current_month_charge(client, ctx, ctx.tenant_id, household_id)


@router.post("/tenant/regenerate")
async def tenant_regenerate_invoices(
    period: str | None = None,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    """Tenant-admin only (Phase 15.5 — closes the "15.3b" gap: previously,
    a failed scheduled generation run had no recovery path at all).
    Manually re-triggers monthly invoice generation for the CALLER'S OWN
    tenant only — scoped via ctx.tenant_id, never an arbitrary tenant_id
    parameter. Defaults to the previous calendar month, same as the
    scheduled job. Also auto-exports on completion, same as the scheduled
    path (regenerate_for_tenant calls the same shared generation core)."""
    return regenerate_for_tenant(client, ctx, period_label=period)


@router.post("/tenant/export")
async def tenant_export_invoices(
    period: str | None = None,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
    client=Depends(get_firestore_client),
):
    """Tenant-admin only (Phase 15.5): manually re-trigger CSV/JSON export
    for the caller's own tenant + period (defaults to previous month) —
    independent of generation, for when only the export step itself
    failed (e.g. files were deleted from GCS but the invoices are fine)."""
    return export_invoices_for_period(client, ctx.tenant_id, _resolve_period(period))


@router.get("/tenant/export/download")
async def tenant_export_download_urls(
    period: str | None = None,
    ctx: TenantContext = Depends(require_role("tenant_admin")),
):
    """Tenant-admin only (Phase 15.5): short-lived (15 min) signed download
    URLs for the caller's own tenant's CSV + JSON export files for `period`
    (defaults to previous month). Uses impersonated credentials — Cloud
    Run's default credentials have no private key to sign a URL with."""
    return signed_export_urls(ctx.tenant_id, _resolve_period(period))
