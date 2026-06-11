# ADR-0008: Data Layout & Repository Contract

Status: Accepted | Date: 2026-06-11 | Author: Chandra Nakkalakunta

## Context
ADR-0004 Layer 2 requires tenant scoping enforced in code.
Phase 2.4 implements the repository layer and must fix the
Firestore data layout and the role of Security Rules (Layer 1)
given that all data access flows through the backend Admin SDK,
which bypasses Security Rules by design.

## Decisions

### 1. Security Rules are permanently deny-all
The frontend never reads Firestore directly; it uses Firebase
only for Auth. Therefore client-side rules have one job: ensure
no client SDK, leaked web config, or future mistake can touch
Firestore. Rules are deny-all, version-controlled at
infrastructure/firestore.rules, deployed via guarded
script. Direct client reads are PROHIBITED — adding them would
bypass API versioning, quotas, rate limits, and audit logging,
and requires a superseding ADR.

### 2. Layout: per-tenant subcollections
All tenant data lives under /tenants/{tenant_id}/<collection>/.
First collection: /tenants/{tenant_id}/users/{uid}.
Isolation is structural: queries physically cannot span tenants
without a deliberate collection-group query. Trade-off accepted:
cross-tenant reporting needs collection-group indexes; heavy
reporting goes to BigQuery federation (ADR-0002).

### 3. Repository contract
- TenantRepository requires a TenantContext WITH tenant_id at
  construction; collection paths derive from ctx.tenant_id.
  Tenant scoping is unbypassable by construction.
- PlatformRepository (tenant-agnostic data, e.g. the tenants
  registry) constructs ONLY with role=platform_admin context;
  anything else raises. Explicit, greppable, CI-checkable.
- Route handlers NEVER import google.cloud.firestore; only
  repositories do. Enforced by static analysis in Phase 5
  (ADR-0004 Layer 5).
- List operations use cursor pagination per ADR-0006 Decision 3.

### 4. First domain model: UserProfile
uid, tenant_id, household_id, flat_number, display_name, role,
created_at. Chosen to support /api/v1/users/me (sub-phase 2.5),
proving the full vertical slice.

## Alternatives considered
- Tenant-aware client rules: rejected; implies direct client
  reads, which are prohibited above.
- Root collections + tenant_id field: rejected; isolation
  becomes a per-query discipline instead of a structural fact.

## Consequences
+ Layer 1 becomes simple and absolute; Layer 2 unbypassable by
  construction.
− Collection-group indexes needed later for admin reporting.
− Repository base classes add indirection (accepted; this is
  the isolation seam).

## References
ADR-0002, ADR-0004 (Layers 1/2/5), ADR-0006 (pagination),
ADR-0007 (TenantContext), Security Charter (Secure by Default,
Fail Closed).
