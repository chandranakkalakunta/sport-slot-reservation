# ADR-0034: Facility Lifecycle, Direct Entity Deletion & DPDP-Compliant Erasure

Status: Proposed | Date: 2026-07-05 (revised 2026-07-06) | Author: Chandra Nakkalakunta (Coordinator) + Strategist

**Supersedes/extends:** ADR-0017 (Deletion, Retention & User/Tenant Lifecycle).
ADR-0017 remains accepted and unmodified per protocol §7.1; this ADR adds
decisions ADR-0017 did not cover and revises its stated non-goal around
standalone hard-delete. This ADR is still Proposed (not yet accepted) —
revising it in place ahead of formal sign-off is normal per protocol §7.1
(only *accepted* ADRs are immutable).

## Context

ADR-0017 (Phase 5) defined tenants/users as ACTIVE → INACTIVE → PURGED,
with PURGED reachable only via a slow (90-day), admin-script-gated,
tenant-wide cascade — explicitly not exposed as a standalone per-user
API action. Investigation during Phase 13 (2026-07-06) confirmed via
direct search that **no implementation of this purge script exists
anywhere in the codebase** — it was designed but never built. Deletion,
as a real capability, has never been properly considered or implemented
in this project.

Three gaps identified across two sessions:

1. Facilities have no lifecycle model of their own (addressed below,
   unchanged from the original version of this ADR).
2. A resident exercising a DPDP erasure request needs a fast, user-
   initiated path, not the slow admin-driven tenant cascade.
3. **(New, 2026-07-06) There is no direct, on-demand delete action for
   any entity at all** — not for residents, not for tenant-admins, not
   for tenants. The only theoretical path (tenant PURGE) doesn't exist
   in code, and even if it did, it wouldn't cover an admin wanting to
   delete a single user immediately.

## Decisions

### 1. Facility lifecycle: three-stage pattern, adapted (unchanged from 2026-07-05)

Facilities adopt the ACTIVE → INACTIVE → PURGED shape with two
adaptations: no self-deactivation clause (always an explicit admin
action), and ACTIVE→INACTIVE cancels confirmed future bookings +
notifies affected residents (reusing ADR-0019's notification
architecture), with an explicit requirement that the AI agent and My
Bookings page reflect the new state identically (avoiding a repeat of
the Phase 10 surface-divergence failure, protocol §5.14). PURGED-stage
retention window for facilities remains Phase 14 scope.

**Known current gap, confirmed by investigation (2026-07-06):**
`deactivate_facility` today only sets `active: False` — it does not
cancel bookings, notify residents, or write an audit event. This
ADR's design is not yet implemented; building it is Phase 13's main
remaining sub-phase.

### 2. Direct deletion: a real, independent, on-demand action (NEW, 2026-07-06)

**Supersedes ADR-0017's stance that standalone hard-delete is not
exposed via API.** Coordinator decision: every entity type — resident,
tenant-admin, and tenant itself — gets a direct **Delete** action,
independent of and not gated behind Deactivate:

- **Immediate, not time-delayed.** No 90-day wait, no prior
  deactivation required. An admin (or, for residents exercising DPDP
  rights, the resident themselves) can delete an active entity
  directly.
- **Complete data removal, with one carve-out.** Deleting an entity
  removes all of its personal/operational data completely — profile,
  booking history, household linkage, everything — **except invoice
  records**, which are retained per the Phase 15 statutory-retention
  carve-out already flagged in the original version of this ADR.
  Coordinator's stated rationale: past booking history and other
  operational data create no compliance or business value once an
  entity is being deleted; keep deletion clean and complete rather
  than partial.
- **Applies uniformly** to residents, tenant-admins, and tenants — one
  rule, not different rules per entity type. Deleting a tenant deletes
  everything under it (users, facilities, bookings — except invoices),
  the same way a tenant PURGE was originally envisioned, just
  triggered on demand instead of via a slow cascade script.
  **De facto replaces ADR-0017's 90-day PURGE mechanism as the primary
  deletion path** — that mechanism was never implemented, and this
  decision makes building it unnecessary for the "delete on request"
  case. A slower, unattended cleanup mechanism (e.g., auto-purging
  something deactivated-but-never-deleted after N days) remains a
  separate, still-open question for Phase 14, not resolved here.
- **Deactivate is retained, unchanged, as the separate soft option.**
  Nothing about ADR-0017's deactivate behavior (status flip, Firebase
  Auth disable, booking cancellation, self-deactivation forbidden,
  audit trail) changes. Delete and Deactivate are now two independent,
  always-available actions — an admin can delete an active entity
  without deactivating it first, or deactivate without ever deleting.
- **Thin audit stub survives deletion** (carried forward from the
  2026-07-05 version): a minimal record of the deletion event itself
  (who/when/what-was-removed, no PII) is retained for operational
  accountability, regardless of which entity type was deleted.

### 3. Resident-initiated DPDP erasure is now just a special case of Decision 2

The original version of this ADR treated resident DPDP erasure as a
distinct mechanism from admin-initiated deletion. With Decision 2 now
in place, they collapse into the same mechanism: a DPDP erasure request
simply triggers the same Delete action, self-initiated by the resident
rather than by an admin. No separate code path is needed — the access-
control question (who is allowed to trigger delete on which entity) is
the only remaining distinction, not the deletion mechanism itself.

### 4. Implementation-vs-design audit is in-scope for Phase 13, not a gate (unchanged)

Confirmed this session: `deactivate_user` was missing its `active`
field write (fixed, sub-phase 13.0, PR #94) and its ADR-0011 audit
event (sub-phase 13.1, drafted). Both were implementation gaps against
already-accepted design, not new design questions.

## Consequences

- Deletion becomes a real, usable capability for the first time in the
  project — closing a gap the Coordinator identifies as never having
  been properly considered.
- The design is simpler than the original ADR-0017 model: one uniform
  delete rule across entity types, instead of tenant-specific PURGE
  cascades plus a separate resident-erasure mechanism.
- ADR-0017's 90-day PURGE script is no longer worth building for the
  "delete on request" case; whether an *unattended* cleanup mechanism
  is still needed for entities that are deactivated but never
  explicitly deleted is deferred to Phase 14 as an open question.
- Immediate, ungated hard-delete on active entities is a real
  operational risk (no undo) that ADR-0017's original design was
  explicitly trying to avoid via the deactivate-first/delayed-purge
  model. This ADR accepts that risk deliberately, per Coordinator
  judgment that the operational simplicity is worth it at current
  scale — worth re-examining if the product grows to a scale where
  accidental deletion becomes a materially bigger risk.
- Phase 15 inherits the same invoice carve-out obligation as before,
  now generalized: invoice records survive *any* deletion (admin- or
  resident-triggered), not just DPDP erasure specifically.

## References

ADR-0011 (audit logging), ADR-0017 (deletion/retention/lifecycle model —
extended, not superseded, by this ADR), ADR-0019 (notification
architecture), protocol §5.14 (surface divergence), protocol §7.1 (ADRs
never modified in place once accepted).

