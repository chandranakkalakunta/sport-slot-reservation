# Phase 5 Retrospective — Admin & Onboarding

Period: 2026-06-14 · Sub-phases 5.1–5.6
Outcome: Complete multi-tenant admin & onboarding. Superadmin
onboards tenants and their first admin; tenant admins (with forced
first-login password change) configure facilities from a global
catalog, set branding and policies, and manage users (single add,
bulk CSV import, password reset, deactivate); residents book within
their tenant. Validated across multiple real tenants (demo, rvrg,
Honer Homes, Marina) proving isolation.

## What shipped
- ADRs 0014 (admin architecture & identity), 0015 (facility
  catalog), 0016 (user provisioning), 0017 (deletion & retention).
- Platform-admin backend: PlatformRepository's first runtime use
  (open since Phase 2), tenant + user provisioning, require_platform_
  admin, superadmin seed.
- UserProvisioningService: the single user-creation path (generate
  password, Firebase user + claims, profile with must_change_password,
  compensating-delete rollback, audit) + deactivate (soft delete,
  Firebase disable, auto-cancel future bookings) + reset_password.
- Facility catalog (global types) → tenant facility instances.
- Tenant config: branding PATCH, policies PATCH, user CRUD + bulk
  CSV import (per-row results, 500 cap).
- Full UI: platform-admin (tenant list, create tenant, create user),
  tenant-admin (dashboard, facilities, branding, policies, users),
  forced password-change, shared AppHeader, factored CredentialDisplay.

## Issue log (the instructive part)

| # | Symptom | Root cause | Fix | Rule |
|---|---------|-----------|-----|------|
| 1 | Superadmin 403 on every admin call | ADR-0007 strict host-gating in code contradicted ADR-0014's route+role relaxation | Relaxed gating to role-based in dev (5.2.1) | When a new ADR modifies an earlier one, note supersession in BOTH and grep the code for the old rule |
| 2 | Non-demo tenant admins 403 on localhost | dev_tenant_slug pinned all localhost auth to "demo"; non-demo claims mismatched | Removed the pin; unrecognized hosts trust the JWT (5.3.1) | Multi-tenant bugs hide until the SECOND tenant; the first matches every default |
| 3 | create-user 500 in cloud, worked locally | Deployed sa-cloud-run lacked firebaseauth.admin (least privilege); dev impersonates the broader sa-firebase-admin | Granted the role, time-boxed in charter | Deployed runtime SA is less privileged than dev creds by design; verify the runtime SA's permissions, not dev's |
| 4 | Forced password change skipped / looped | Flag checked only in Landing (one route); other routes bypassed it. Then stale profile cache bounced post-change | Moved the gate into the route guards (global); invalidate profile query on success (5.5.1, 5.5.2) | A security gate must be a single unbypassable choke point, not a per-route check |
| 5 | VALIDATION_FAILED hid which field | Envelope swallowed Pydantic detail | Added field detail in dev (5.4b) | Make errors loud in dev; opacity costs round-trips |
| 6 | tenant_admin forced to enter a meaningless flat_number | Shared user model over-applied a resident-only field | flat_number optional for tenant_admin (5.4b) | Walk each role's actual field needs; don't over-share a model |
| 7 | Branding theme wrong for tenant admins in dev | No tenant subdomains on localhost/.web.app; resolution falls back to default | Deferred to Phase 7 (subdomains) after repeated half-fixes | Some "bugs" are environment limitations; stop fixing in dev, fix when the environment is right |

## Missing/under-specified requirements caught mid-flight
- Deletion/retention lifecycle (the whole of ADR-0017 — a core verb absent from the plan).
- Logo in branding; flat_number-not-for-admins; password reset
  (admin-initiated); catalog management; multi-tenant admin.
Each became an explicit decision only because the design was
questioned. Rule: enumerate every entity's full lifecycle (incl.
delete/retain) and full actor matrix at design time.

## Validation quality note
Every real bug (the 403s, the 500, the forced-password bypass) was
found by EXERCISING the system as a real user across multiple
tenants — not by the test suite (which stayed green throughout).
Green tests are necessary, not sufficient. The disciplined
diagnosis (one decisive API/log observation per symptom) turned a
daunting "many issues" pile into a short, precise, fixable list.

## Decisions of note / deferrals
- Synchronous provisioning stays in the main API (ADR-0016);
  migrates to a background job in Phase 7.
- DEFERRED (tracked): branding-in-dev correctness → Phase 7
  (subdomains); UI scalability & UX optimization (table/pagination/
  search/filter, shared list component, admin-resident segregation,
  superadmin tenant-user-management UI, natural ordering) → dedicated
  post-functional-completion phase; multi-tenant admin (one admin →
  many tenants) → Phase 8+ (auth-model change, needs ADR);
  multi-interval/selectable facility hours → own sub-phase (amends
  ADR-0010/0015); self-service email password reset → Phase 7
  (notifications); facility-catalog management UI → when a tenant
  needs a non-seeded sport; GCS logo upload → own sub-phase.

## Carried-forward technical items
- Composite index (uid+sport+date) + per-sport quota fix: the quota
  is currently per-day-total, not per-sport (counts ignore sport).
  Booking-core change — own sub-phase with tests.
- superadmin email admin@sportbook vs ADR-0014 superadmin@ —
  reconciled in this phase (ADR text updated to match the seed).
