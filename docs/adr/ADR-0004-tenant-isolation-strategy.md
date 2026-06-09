# ADR-0004: Tenant Isolation Strategy

**Status:** Accepted  
**Date:** 2026-06-09  
**Deciders:** Chandra Nakkalakunta

## Context

SportSlotReservation is a multi-tenant SaaS. Each tenant is one
residential community (e.g., "Prestige Lakeside Habitat, Bengaluru").
Tenants must not see each other's facilities, slots, bookings,
residents, or billing data under any circumstances.

### Isolation models considered

| Model | Description | Trade-offs |
|-------|-------------|------------|
| **Database-per-tenant** | Each tenant gets its own Firestore project or database | Strongest isolation; prohibitive cost and operational overhead at scale |
| **Collection-per-tenant** (logical) | All tenants share one database; `tenant_id` field on every document; enforced in the data access layer | Cost-efficient; scales to thousands of tenants; isolation relies on correct application code |
| **Namespace/prefix-per-tenant** | Firestore collection paths prefixed with tenant ID | Equivalent to logical isolation; Firestore Native Mode naturally supports this via sub-collections under `tenants/{tenant_id}` |

Physical (database-per-tenant) isolation was ruled out: Firestore bills
per project, connection overhead on Cloud Run is non-trivial, and
operational complexity (deployments, index management, backups) grows
linearly with tenant count.

## Decision

Use **logical tenant isolation** via a `TenantScopedRepository` pattern:

### Firestore structure

All tenant data lives under a top-level `tenants/{tenant_id}` document
with sub-collections beneath it:

```
tenants/{tenant_id}                        ← tenant config document
tenants/{tenant_id}/facilities/{id}
tenants/{tenant_id}/slots/{id}
tenants/{tenant_id}/bookings/{id}
tenants/{tenant_id}/users/{id}
tenants/{tenant_id}/flats/{id}
tenants/{tenant_id}/invoices/{id}
```

Every document also carries a `tenant_id` field as a redundant safety
check — this enables collection-group queries and cross-tenant auditing
for platform admins without relying solely on path structure.

### Enforcement: TenantScopedRepository

All data access goes through `TenantScopedRepository`, a base class
that:

1. Accepts `tenant_id` at construction time (injected from the
   authenticated request context — never from user-supplied request body).
2. Scopes every Firestore query to `tenants/{tenant_id}/...`.
3. Validates that documents returned from collection-group queries
   carry a matching `tenant_id` field before returning them.
4. Raises `TenantAccessViolation` if a cross-tenant access is attempted.

No repository may bypass `TenantScopedRepository` to access raw
Firestore collections directly.

### Auth layer enforcement

- Firebase Auth tokens carry a `tenant_id` custom claim, set at
  registration time.
- FastAPI dependency `get_current_tenant()` extracts and validates the
  claim on every authenticated endpoint.
- `tenant_id` is **never** accepted from the request body or query
  parameters — always from the verified token claim.

### Platform admin access

Platform admins (Chandra AI Labs staff) have a separate role that
bypasses tenant scoping. This role is granted only to service accounts
and is never assignable to end users.

## Consequences

**Positive**
- Scales to thousands of tenants with no per-tenant infra cost.
- Single deployment serves all tenants.
- Index management, schema changes, and monitoring apply uniformly.

**Negative / risks**
- Isolation is only as strong as the `TenantScopedRepository`
  implementation — a bug there could expose cross-tenant data.
- A misconfigured collection-group query could return documents across
  tenants if the `tenant_id` filter is omitted.

**Mitigations**
- `TenantScopedRepository` is covered by dedicated unit tests that
  assert cross-tenant queries raise exceptions.
- Code review policy: any Firestore access outside `TenantScopedRepository`
  is a blocking finding.
- Firestore Security Rules provide a secondary enforcement layer,
  independently validating `tenant_id` match against the Auth token claim.
- Penetration test checklist includes tenant-escape attempts before
  each major release.
