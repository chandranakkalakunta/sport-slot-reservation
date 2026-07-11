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

CORRECTION (Phase 15.3 fix, denormalization): each line item and invoice
document previously had no human-readable resident/flat identity — only
household_id, an internal code not guaranteed derivable from flat_number
(the bulk-import path allows an explicit household_id override). Resolved
HERE, once per unique resident per tenant generation pass (never at
display time — the entire point is that every future read is a single
complete document fetch, with no lookup regardless of tenant size), via
a local uid -> profile cache. Each line item gains resident_uid/
resident_name (a missing/deleted profile falls back to "Unknown resident",
never a crash); each invoice gains flat_number, sourced from the first
resident encountered for that household — acceptable since flat_number is
expected to be consistent within a household.

Tenant listing uses direct client.collection() calls rather than a
TenantContext-bound repository (mirrors services/tenants.py's pattern for
operations that span all tenants rather than belonging to one tenant's
own request). Per-tenant work then builds a synthetic system TenantContext
to reuse BookingRepository/InvoiceRepository — those classes only require
ctx.tenant_id to be set, so this is a legitimate reuse, not a bypass of
any role check (this endpoint is guarded entirely by verify_scheduler_oidc).

EXTRACTION (Phase 15.4c, protocol §5.14 — one source of truth): the core
per-household grouping/pricing/resident-resolution logic used to live
inline in `_generate_for_tenant`. It is now `_compute_household_charges`,
called identically by `_generate_for_tenant` (which persists the result)
AND by `preview_current_month_charge` (which computes the SAME thing for
the current, not-yet-invoiced month and returns it unpersisted, for a
tenant-admin's live "what would this household's bill be so far" lookup).
Neither path duplicates the other's computation — they call the same
function, so a real invoice and its preview can never silently drift
apart.

EXPORT (Phase 15.5): `_generate_for_tenant` now also uploads a CSV/JSON
summary export (services/invoice_export.py) after a tenant's households
finish processing — success or per-household failure, since a partial
batch is still worth exporting as-is. Export failure is logged loudly but
never raised, so it can never turn a successful generation run into a
reported failure (same non-blocking philosophy as the notification
enqueue in services/bookings.py). `regenerate_for_tenant` is a thin,
tenant-scoped wrapper around `_generate_for_tenant` for a tenant-admin's
manual re-trigger (closes the "15.3b" gap: previously, a failed scheduled
run had no recovery path at all) — it defaults to the previous calendar
month, same as the scheduled job, and — because it calls the same
`_generate_for_tenant` — also auto-exports on completion, exactly like
the scheduled path.
"""

import datetime

import structlog

from sport_slot.auth.context import TenantContext
from sport_slot.repositories.bookings import BookingRepository
from sport_slot.repositories.invoices import InvoiceRepository
from sport_slot.repositories.user_profiles import UserProfileRepository
from sport_slot.services.invoice_export import export_invoices_for_period

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


def _current_month_range(today: datetime.date) -> tuple[str, str, str]:
    """Return (period_start, period_end, period_label) for the CURRENT,
    still-in-progress calendar month — first of this month through today
    (Phase 15.4c preview). Unlike `_previous_month_range`, this is never
    used for real invoice generation, only the live preview."""
    period_start = today.replace(day=1)
    period_label = period_start.strftime("%Y-%m")
    return period_start.isoformat(), today.isoformat(), period_label


def _month_range_for_period(period_label: str) -> tuple[str, str]:
    """Return (period_start, period_end) for an explicit "YYYY-MM" label
    (Phase 15.5 manual regeneration with an explicit period). Stdlib-only,
    matching `_previous_month_range`'s own approach — no date library
    dependency for a single month-end calculation."""
    year, month = (int(p) for p in period_label.split("-"))
    start = datetime.date(year, month, 1)
    next_month_first = datetime.date(year + 1, 1, 1) if month == 12 else datetime.date(year, month + 1, 1)
    end = next_month_first - datetime.timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _list_active_tenants(client) -> list[dict]:
    query = client.collection("tenants").where("status", "==", "active")
    return [snap.to_dict() for snap in query.stream()]


def _resolve_profile(profile_repo: UserProfileRepository, cache: dict, uid: str) -> dict | None:
    """Fetch uid's profile, caching so a resident with multiple bookings in
    the period costs exactly one Firestore read, not one per booking."""
    if uid not in cache:
        cache[uid] = profile_repo.get(uid)
    return cache[uid]


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


def _compute_household_charges(
    client, ctx: TenantContext, tenant_id: str, period_start: str, period_end: str,
) -> dict[str, dict]:
    """Core per-household charge computation (Phase 15.4c extraction) —
    the ONE place that groups confirmed bookings by household, resolves
    prices and resident identity, and builds line items. Shared,
    identically, by the real monthly generator (`_generate_for_tenant`,
    which persists the result) and the live current-month preview
    (`preview_current_month_charge`, which does not) — see module
    docstring. Returns household_id -> {"line_items", "total_paise",
    "flat_number"}; does NOT skip zero-total households or persist
    anything — that stays with each caller.
    """
    priced = _priced_facilities(client, tenant_id)
    bookings = BookingRepository(ctx, client).list_confirmed_in_range(period_start, period_end)

    profile_repo = UserProfileRepository(ctx, client)
    profile_cache: dict[str, dict | None] = {}
    # flat_number source of record per household: the first RESOLVABLE
    # resident encountered while iterating bookings — one representative
    # value is sufficient since flat_number is expected to be consistent
    # per household. CORRECTION (production bug): a household must not
    # get stuck on "Unknown flat" just because the FIRST booking's
    # resident happened to be unresolvable (e.g. a deleted account) —
    # keep checking subsequent bookings in the same household until one
    # actually resolves. Only unresolved if EVERY resident in it is.
    household_flat: dict[str, str | None] = {}

    by_household: dict[str, list[dict]] = {}
    for booking in bookings:
        fac = priced.get(booking.get("facility_id", ""))
        if fac is None:
            continue  # unpriced (or unknown) facility — excluded entirely
        household_id = booking.get("household_id")
        if not household_id:
            continue
        uid = booking.get("uid")
        profile = _resolve_profile(profile_repo, profile_cache, uid) if uid else None
        resident_name = (profile or {}).get("display_name") or "Unknown resident"
        if household_flat.get(household_id) is None:
            resolved_flat = (profile or {}).get("flat_number")
            if resolved_flat is not None:
                household_flat[household_id] = resolved_flat
        by_household.setdefault(household_id, []).append({
            "booking_id": booking.get("id"),
            "facility_id": booking.get("facility_id"),
            "facility_name": fac["name"],
            "date": booking.get("date"),
            "price_paise": fac["price_paise"],
            "resident_uid": uid,
            "resident_name": resident_name,
        })

    return {
        household_id: {
            "line_items": items,
            "total_paise": sum(item["price_paise"] for item in items),
            "flat_number": household_flat.get(household_id),
        }
        for household_id, items in by_household.items()
    }


def preview_current_month_charge(
    client, ctx: TenantContext, tenant_id: str, household_id: str,
    *, today: datetime.date | None = None,
) -> dict:
    """LIVE, unpersisted preview (Phase 15.4c) of one household's CURRENT,
    still-in-progress month — for a tenant-admin resolving a dispute
    before that month's real invoice has even generated. Calls the exact
    same `_compute_household_charges` the real generator uses, just with
    the current month's date range, and writes NOTHING to Firestore.
    A household with nothing eligible yet this month gets a zero-total,
    empty-line-items result — never raises, never treated as an error.
    """
    today = today or datetime.date.today()
    period_start, period_end, period_label = _current_month_range(today)
    charges = _compute_household_charges(client, ctx, tenant_id, period_start, period_end)
    charge = charges.get(household_id, {"line_items": [], "total_paise": 0, "flat_number": None})
    return {
        "household_id": household_id,
        "period": period_label,
        "period_start": period_start,
        "period_end": period_end,
        "flat_number": charge["flat_number"],
        "line_items": charge["line_items"],
        "total_paise": charge["total_paise"],
        "preview": True,
    }


def _generate_for_tenant(
    client, tenant_id: str, tenant_slug: str | None,
    period_start: str, period_end: str, period_label: str, summary: dict,
) -> None:
    ctx = TenantContext(
        uid=_SYSTEM_UID, tenant_id=tenant_id, tenant_slug=tenant_slug,
        role="system", household_id=None,
    )
    charges = _compute_household_charges(client, ctx, tenant_id, period_start, period_end)

    invoice_repo = InvoiceRepository(ctx, client)
    for household_id, charge in charges.items():
        try:
            total_paise = charge["total_paise"]
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
                "flat_number": charge["flat_number"],
                "period": period_label,
                "period_start": period_start,
                "period_end": period_end,
                "line_items": charge["line_items"],
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

    try:
        export_invoices_for_period(client, tenant_id, period_label)
    except Exception as exc:  # noqa: BLE001 - export failure must never turn a successful generation into a failure
        log.error("invoice_export_failed", tenant_id=tenant_id, period=period_label, error=str(exc))


def regenerate_for_tenant(
    client, ctx: TenantContext, *, period_label: str | None = None,
    today: datetime.date | None = None,
) -> dict:
    """Tenant-admin manual re-trigger (Phase 15.5 — closes the "15.3b" gap:
    previously, a failed scheduled generation run had NO recovery path at
    all). Scoped STRICTLY to ctx.tenant_id — this function has no
    parameter for any other tenant, by construction, not just convention.
    Defaults to the previous calendar month (same period the scheduled
    job would cover) when period_label is omitted. Calls
    `_generate_for_tenant` directly — identical computation, persistence,
    and automatic export to the scheduled path, so a manual re-run behaves
    exactly like the real one.
    """
    if period_label is None:
        today = today or datetime.date.today()
        period_start, period_end, period_label = _previous_month_range(today)
    else:
        period_start, period_end = _month_range_for_period(period_label)

    summary: dict = {
        "tenant_id": ctx.tenant_id,
        "period": period_label,
        "households_invoiced": 0,
        "households_skipped": 0,
        "households_failed": [],
    }
    _generate_for_tenant(client, ctx.tenant_id, ctx.tenant_slug,
                          period_start, period_end, period_label, summary)
    return summary
