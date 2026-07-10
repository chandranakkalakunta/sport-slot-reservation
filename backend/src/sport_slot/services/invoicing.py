"""Monthly invoice generation (Phase 15.3).

Postpaid billing (Decision 1): an invoice generated on day N of month M
covers ALL confirmed bookings dated within the PREVIOUS calendar month
(M-1). Zero-total households are skipped entirely — no invoice document
is created for a household with no eligible (confirmed + priced-facility)
bookings in the period, and no Rs.0 invoice is ever written (Decision 2).
Payment status is NOT tracked anywhere in this module (Decision 3) — this
generates the bill amount only. Invoices are immutable: this module only
ever creates a new invoice document, never updates one (Decision 6).

KNOWN GAP (Decision 4): this runs on a single global fixed schedule
(Cloud Scheduler, 03:00 on the 1st) for ALL tenants — it does NOT yet
honor each tenant's own policies.invoice_generation_time (Phase 15.2).
That field is stored but unused by scheduling until a later sub-phase.

Booking documents already carry household_id directly (set at booking
creation, services/bookings.py) — no user-profile lookup/join is needed
to group bookings by household.

Tenant listing uses direct client.collection() calls rather than a
TenantContext-bound repository (mirrors services/tenants.py's pattern for
operations that span all tenants rather than belonging to one tenant's
own request). Per-tenant work then builds a synthetic system TenantContext
to reuse BookingRepository/InvoiceRepository — those classes only require
ctx.tenant_id to be set, so this is a legitimate reuse, not a bypass of
any role check (this endpoint is guarded entirely by verify_scheduler_oidc).
"""

import datetime

import structlog

from sport_slot.auth.context import TenantContext
from sport_slot.repositories.bookings import BookingRepository
from sport_slot.repositories.invoices import InvoiceRepository

log = structlog.get_logger()

_SYSTEM_UID = "system:invoice-generator"


def _previous_month_range(today: datetime.date) -> tuple[str, str, str]:
    """Return (period_start, period_end, period_label) for the calendar month before `today`."""
    first_of_this_month = today.replace(day=1)
    last_day_prev_month = first_of_this_month - datetime.timedelta(days=1)
    period_start = last_day_prev_month.replace(day=1)
    period_end = last_day_prev_month
    period_label = period_start.strftime("%Y-%m")
    return period_start.isoformat(), period_end.isoformat(), period_label


def _list_active_tenants(client) -> list[dict]:
    query = client.collection("tenants").where("status", "==", "active")
    return [snap.to_dict() for snap in query.stream()]


def _priced_facilities(client, tenant_id: str) -> dict[str, dict]:
    """facility_id -> {"name", "price_paise"}, excluding facilities with no price set.

    A booking against a facility absent from this dict contributes nothing to
    any invoice — it is not a Rs.0 line item, it is simply skipped entirely.
    """
    fac_col = client.collection("tenants").document(tenant_id).collection("facilities")
    out: dict[str, dict] = {}
    for snap in fac_col.stream():
        fac = snap.to_dict() or {}
        price = fac.get("price_paise")
        fid = fac.get("id")
        if price is None or not fid:
            continue
        out[fid] = {"name": fac.get("name"), "price_paise": price}
    return out


def generate_invoices(client, *, today: datetime.date | None = None) -> dict:
    """Generate one immutable invoice per household with eligible bookings
    in the previous calendar month, across all active tenants.

    Partial-failure tolerant at both the tenant and household level: one
    tenant's or household's failure is logged loudly (never silenced) and
    does not abort the rest of the batch. Returns a structured summary.
    """
    today = today or datetime.date.today()
    period_start, period_end, period_label = _previous_month_range(today)

    summary: dict = {
        "period": period_label,
        "tenants_processed": 0,
        "households_invoiced": 0,
        "households_skipped": 0,
        "households_failed": [],
    }

    for tenant in _list_active_tenants(client):
        tenant_id = tenant.get("tenant_id")
        if not tenant_id:
            continue
        try:
            _generate_for_tenant(client, tenant_id, tenant.get("slug"),
                                  period_start, period_end, period_label, summary)
            summary["tenants_processed"] += 1
        except Exception as exc:  # noqa: BLE001 - one tenant's failure must not abort the batch
            log.error("invoice_generation_tenant_failed",
                      tenant_id=tenant_id, period=period_label, error=str(exc))

    log.info("invoice_generation_complete", **summary)
    return summary


def _generate_for_tenant(
    client, tenant_id: str, tenant_slug: str | None,
    period_start: str, period_end: str, period_label: str, summary: dict,
) -> None:
    ctx = TenantContext(
        uid=_SYSTEM_UID, tenant_id=tenant_id, tenant_slug=tenant_slug,
        role="system", household_id=None,
    )
    priced = _priced_facilities(client, tenant_id)
    bookings = BookingRepository(ctx, client).list_confirmed_in_range(period_start, period_end)

    by_household: dict[str, list[dict]] = {}
    for booking in bookings:
        fac = priced.get(booking.get("facility_id", ""))
        if fac is None:
            continue  # unpriced (or unknown) facility — excluded entirely
        household_id = booking.get("household_id")
        if not household_id:
            continue
        by_household.setdefault(household_id, []).append({
            "booking_id": booking.get("id"),
            "facility_id": booking.get("facility_id"),
            "facility_name": fac["name"],
            "date": booking.get("date"),
            "price_paise": fac["price_paise"],
        })

    invoice_repo = InvoiceRepository(ctx, client)
    for household_id, line_items in by_household.items():
        try:
            total_paise = sum(item["price_paise"] for item in line_items)
            if total_paise == 0:
                summary["households_skipped"] += 1
                log.info("invoice_generation_household_zero_total_skipped",
                         tenant_id=tenant_id, household_id=household_id, period=period_label)
                continue

            invoice_id = f"{household_id}_{period_label}"
            doc = {
                "invoice_id": invoice_id,
                "tenant_id": tenant_id,
                "household_id": household_id,
                "period": period_label,
                "period_start": period_start,
                "period_end": period_end,
                "line_items": line_items,
                "total_paise": total_paise,
                "generated_at": datetime.datetime.now(datetime.UTC),
            }
            created = invoice_repo.create_if_absent(invoice_id, doc)
            if created:
                summary["households_invoiced"] += 1
            else:
                summary["households_skipped"] += 1
                log.info("invoice_generation_household_already_invoiced",
                         tenant_id=tenant_id, household_id=household_id, period=period_label)
        except Exception as exc:  # noqa: BLE001 - one household's failure must not block others
            summary["households_failed"].append({
                "tenant_id": tenant_id, "household_id": household_id, "reason": str(exc),
            })
            log.error("invoice_generation_household_failed",
                      tenant_id=tenant_id, household_id=household_id,
                      period=period_label, error=str(exc))
