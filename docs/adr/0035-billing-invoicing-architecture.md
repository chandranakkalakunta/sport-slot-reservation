# ADR-0035: Billing & Invoicing Architecture

Status: Accepted | Date: 2026-07-11 | Author: Chandra Nakkalakunta (Coordinator) + Strategist
**Phase:** 15 (Billing & Invoicing) | **Relates to:** ADR-0008 (repository pattern),
ADR-0010 (deterministic IDs as guards), ADR-0018 (keyless WIF), ADR-0026
(deterministic Python guards over LLM judgment), ADR-0034 (facility lifecycle,
invoice-exclusion carve-out — implemented in this phase, sub-phase 15.7)

## Context

SlotSense had no billing capability at all prior to this phase — facilities
were free to book, and no financial data existed anywhere in the system.
This ADR documents the architectural decisions made while building the
first version: per-facility pricing, monthly invoice generation, resident
and tenant-admin invoice visibility, external-system export, and read-only
agent access to a resident's own billing data.

## Decisions

### 1. Pricing model: flat rate, optional, integer paise

Each facility gets an optional `price_paise: int | None` field — flat per
booking, regardless of slot duration. No dynamic/peak pricing in this
version. Optional and nullable by design: this shipped onto tenants with
existing facilities and residents, and making price mandatory would have
silently started charging people the moment it deployed. A facility with
no price set is simply never billed — not a ₹0 charge, absent entirely
from any invoice's line items.

Money is stored as integer paise everywhere in the backend, never a float
rupee value — standard fintech practice, avoids floating-point rounding
bugs. The frontend accepts rupee input from tenant-admins (supporting
plain whole-number entry like "50", not forcing ".00") and converts before
submission; all display converts back the same way for humans.

### 2. Billing cycle: postpaid, fixed day, admin-configurable time only

An invoice generated on the 1st of month M covers all confirmed bookings
dated in the PREVIOUS calendar month (M-1) — postpaid, matching the
originally-documented (but never built) `billing_cycle_type` concept's
default. The day is fixed at the 1st, not configurable. Only the
generation TIME is tenant-admin configurable (a policy field, default
03:00) — the fuller `billing_cycle_type` (postpaid/prepaid/biweekly) +
anchor-day flexibility that was originally documented was explicitly
decided against for this version, in favor of the simpler fixed-day model.

**Known, accepted gap:** the scheduled Cloud Scheduler job runs on a
SINGLE fixed global time for all tenants — it does not yet honor each
tenant's own configured generation-time policy. That field is stored and
displayed correctly but not wired into the actual trigger mechanism.
Deferred, not forgotten — revisit if per-tenant timing genuinely becomes
necessary in practice.

### 3. Invoices are immutable

Once generated, an invoice document is never updated or deleted by this
system's own logic — only ever created. Deterministic invoice ID
(`{household_id}_{YYYY-MM}`) plus Firestore's `create()` (fails if the
document already exists, rather than `set()`) gives natural, free
idempotency: re-running generation for a period that's already been
processed silently skips households that already have an invoice,
without any extra bookkeeping. This mirrors the same deterministic-ID-
as-guard philosophy already established for booking IDs (ADR-0010).

Corrections to an already-generated invoice are explicitly out of scope
for this version — no adjustment/credit-entry mechanism was built. If a
generated invoice is wrong, the only available remedy today is manual
intervention at the data layer; a proper correction workflow is future
scope, not decided here.

### 4. Payment status: fully external, not tracked

This system generates the bill amount only. Whether or how an invoice
gets paid is never recorded anywhere in SlotSense — that lives entirely
in whatever "next level system" a tenant's community already uses for
settlement (cash, bank transfer, their own accounting process). No
paid/unpaid field exists on the invoice document. This was a deliberate
simplicity choice, consistent with the "no payment gateway, offline
settlement" constraint carried over from the original product
requirements.

### 5. Household-level billing, resolved from bookings directly

Bookings already carry `household_id` at creation time (existing field,
predates this phase) — invoice generation groups by this field directly,
with no user-profile join required for the core charge computation. This
made a real, later-discovered requirement (denormalizing `flat_number`
and `resident_name` onto each invoice/line-item, for admin dispute
resolution) cheap to retrofit: both are resolved once per unique resident
per generation pass (cached, not per-booking) and stored directly on the
invoice, so no runtime profile lookup is ever needed at display time —
correctness holds at any tenant scale, not just the single-digit scale
this project runs at today.

A resident deleted after making a booking leaves that booking's
`resident_name` unresolvable ("Unknown resident") on any invoice
generated afterward — confirmed, accepted behavior, not a bug: attributing
a historical charge to whoever currently occupies that flat, rather than
who actually made the booking, would be actively incorrect for dispute
resolution, not just imprecise.

### 6. GCS export is a summary-level derivative, not the system of record

A monthly CSV + JSON export (household, flat, period, total) lands in a
dedicated, PRIVATE GCS bucket automatically after each tenant's generation
completes, and can be manually re-triggered independent of generation
(e.g., if only the export step failed, invoices are still fine). This
export is explicitly NOT a substitute for the Firestore invoice
documents — it's summary-level only (no line-item detail), and Firestore
remains the actual, complete, durable system of record. The export exists
specifically to feed an external "next level system," not as SlotSense's
own backup mechanism.

Signed URL generation for downloading export files uses keyless
self-impersonation (`roles/iam.serviceAccountTokenCreator` granted to
`sa-cloud-run` on itself, then `google.auth.impersonated_credentials` used
explicitly in code) — the exact same mechanism already established and
working for Firebase Hosting deploy tokens (ADR-0018's keyless CI/CD
philosophy, extended to a second, unrelated purpose within the running
application itself, not just the deploy pipeline).

### 7. Two independent manual recovery triggers

Because "no manual trigger" was identified as a real operational gap
(if the scheduled job fails, there was no way to recover at all), two
separate tenant-admin-facing manual triggers exist: re-run generation for
the caller's own tenant (idempotent, safe to re-run), and re-run export
independently (for when generation succeeded but only the export/GCS step
had a problem). Both strictly scoped to the caller's own tenant — never
accept an arbitrary tenant_id parameter.

### 8. Tenant-admin visibility: latest-only, plus on-demand history and a live current-month preview

Tenant-admins can look up any flat's latest generated invoice
(searchable by flat number), and — after real usage revealed "latest
only" was insufficient for dispute resolution — drill into a flat's last
3 generated periods and a LIVE, unpersisted preview of the current,
still-in-progress month's charges so far. The preview reuses the exact
same charge-computation function the real monthly generator uses
(extracted into a shared function specifically to guarantee this), so a
preview and a real invoice can never silently compute different numbers
for the same underlying bookings — one source of truth, two consumers,
one persists and one doesn't.

### 9. Agent access: read-only, and deterministically routed

Two read-only agent tools (`get_my_invoices`, `get_my_current_month_charges`)
let a resident ask about their own billing in natural language, strictly
scoped to their own `household_id`. Both reuse existing functions with
zero new computation logic.

**A real, live-reproduced reliability problem surfaced after shipping:**
Gemini's own tool-selection judgment for these two tools was genuinely
non-deterministic — identical phrasing worked in one fresh session and
failed in another, with identical system-prompt instructions both times,
and no retry/forced-function-calling/fallback mechanism existed anywhere
in the agent module to catch it. The fix extends this project's own
established principle (ADR-0026, deterministic Python guards over LLM
judgment) to a new case: a conservative, whole-word keyword pre-router
runs BEFORE Gemini is ever called for a turn, and on a high-confidence
match, dispatches directly to the existing tool functions and returns
their already-human-readable response — skipping Vertex entirely for
that turn (both tool-selection AND reply-phrasing), since a Vertex call
made merely to phrase the reply would reintroduce the exact
non-determinism being fixed. Any non-matching message falls through to
the original, completely unchanged Gemini-routed flow. This fix is
scoped narrowly to the two invoice tools; generalizing deterministic
pre-routing to the other four existing tools (`check_availability`,
`list_my_bookings`, `book`, `cancel`, `get_my_preferences`) is an
explicitly separate, undecided future question, not resolved here.

### 10. The ADR-0034 invoice-exclusion carve-out, finally implemented

ADR-0034 flagged, before this phase existed, that permanently deleting a
tenant must not destroy its invoices. Implemented in sub-phase 15.7:
`delete_user_permanently` needed no code change (confirmed it never
touches invoices structurally). `delete_tenant_permanently` was changed
from one blanket `recursive_delete` on the whole tenant document to
dynamically enumerating the tenant's ACTUAL subcollections at runtime
(`DocumentReference.collections()`, never a hardcoded list — a hardcoded
list would silently miss any subcollection added in a future phase and
quietly reintroduce this exact gap), recursively deleting every one
except `invoices`, then deleting the now-childless tenant document
directly. Per Coordinator decision, the tenant document itself is still
fully deleted; invoices survive deliberately orphaned (no parent
document) — Firestore permits querying a subcollection by full path
regardless of whether its parent still exists.

## Consequences

- Real financial data now exists in this system for the first time —
  every future change touching bookings, facilities, or tenant/user
  deletion must be checked against whether it could affect billing
  correctness or the invoice-exclusion carve-out.
- The "single global scheduled time" gap (Decision 2) and the "no
  correction/adjustment mechanism" gap (Decision 3) are both real,
  accepted limitations, not oversights — worth revisiting if actual
  usage at scale makes either one a genuine problem, not before.
- The deterministic pre-Vertex routing pattern (Decision 9) is now a
  second, real instance of ADR-0026's principle in this codebase —
  worth treating as a candidate default (not an automatic one) the next
  time a new agent tool's reliability turns out to matter in practice,
  rather than reaching for it preemptively on every tool regardless of
  need.
- GCS export (Decision 6) must not be treated as a backup strategy by
  anyone reading this later — Backup & Disaster Recovery (a separate,
  not-yet-started ADR) still needs to define a real strategy for
  Firestore itself, invoices included.
