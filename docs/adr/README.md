# Architecture Decision Records

This directory contains the Architecture Decision Records (ADRs)
for SportSlotReservation. ADRs capture the reasoning behind
significant architectural choices.

## What Are ADRs?

An Architecture Decision Record documents:
- **Context** — What problem are we solving?
- **Options** — What alternatives were considered?
- **Decision** — What did we choose?
- **Rationale** — Why did we choose it?
- **Consequences** — What does this commit us to?

ADRs are immutable historical records. They are not updated;
superseded ADRs link to their replacements.

## Phase 0 — Foundation Decisions

These ADRs were written before any code was committed,
establishing the architectural foundation.

| ADR | Title | Status | Summary |
|-----|-------|--------|---------|
| [0001](0001-tech-stack.md) | Tech Stack & Software Versions | Accepted | Python 3.12 + FastAPI backend; React 18 + Vite + TypeScript + PWA frontend; Cloud Run with multi-stage Docker; uv + pnpm package managers; stateless architecture mandate |
| [0002](0002-database-technology.md) | Database Technology Selection | Accepted | Cloud Firestore Native Mode; Redis distributed locks for ACID-critical operations; per-country deployments for data sovereignty |
| [0003](0003-build-tooling.md) | Build Tooling Interface | Accepted | Makefile + bash hybrid; self-documenting via `make help`; safety guardrails for destructive operations |
| [0004](0004-tenant-isolation.md) | Tenant Isolation Strategy | Accepted | Logical isolation with 5-layer defense-in-depth; subdomain identification with wildcard DNS; platform admin assigns slugs |
| [0005](0005-cost-baseline.md) | Cost Baseline & Budget Alerts | Accepted | DEV ≤₹5K/month; PROD target ≤₹2K/tenant; 4-tier alert thresholds with hard limits at 100%; daily dashboard + weekly summary |

## Phase 2 — Backend API Foundation

| ADR | Title | Status | Summary |
|-----|-------|--------|---------|
| [0006](0006-api-design-patterns.md) | API Design Patterns | Accepted | URL path versioning (/api/v1/); UPPER_SNAKE error code registry; cursor-based pagination only; split /health + /readyz probes (/healthz is GCP-reserved) |
| [0007](0007-auth-and-authorization.md) | Authentication & Authorization | Accepted | firebase-admin only JWT verification (python-jose prohibited); custom claims as identity source of truth; accepted 1h staleness with selective revocation; no admin tenant bypass; phased rate limiting |
| [0008](0008-data-layout-and-repository-contract.md) | Data Layout & Repository Contract | Accepted | Permanent deny-all Firestore rules; per-tenant subcollection layout /tenants/{id}/...; TenantRepository with construction-time tenant enforcement; PlatformRepository gated to platform_admin; cursor pagination |

## Phase 3 — Booking Engine

| ADR | Title | Status | Summary |
|-----|-------|--------|---------|
| [0009](0009-slot-locking-redis.md) | Slot Locking — Memorystore Redis | Accepted | Memorystore Redis Basic 1 GB; SET NX PX lock on deterministic key; Fail Closed (503 on Redis down, never bypass); LockService interface; VPC egress to Cloud Run |
| [0010](0010-booking-domain-and-policy.md) | Booking Domain Model & Policy Resolution | Accepted | Computed availability (no pre-generated slots); deterministic booking ID as second double-booking guard; PolicyService Tenant Override → Global Default; quota enforcement inside Firestore transaction |
| [0011](0011-audit-logging.md) | Audit Logging | Accepted | Append-only Firestore audit events at /tenants/{id}/audit; synchronous write in mutation path; BigQuery prohibited in request path; Cloud Logging rejected as non-tenant-owned |

## Phase 4 — Frontend PWA

| ADR | Title | Status | Summary |
|-----|-------|--------|---------|
| [0012](0012-frontend-architecture.md) | Frontend Architecture | Accepted | Classic Firebase Hosting (named subdomains, LB wildcard deferred to Phase 7); same-origin API via Hosting rewrites (zero CORS); React 18 + Vite + TS strict + TanStack Query; CSS variables as tenant theming contract; Tailwind rejected |
| [0013](0013-error-presentation-i18n.md) | Error Presentation & i18n Strategy | Accepted | Resolver chain: tenant override → locale catalog → English default → raw code; English-only catalog in Phase 4.3; locale/tenant-override layers designed-for but not built; fail-safe renders the code itself on unmapped entry |

## Phase 5 — Admin & Provisioning

| ADR | Title | Status | Summary |
|-----|-------|--------|---------|
| [0014](0014-admin-architecture-identity.md) | Admin Architecture & Identity | Accepted | Route-gated admin surfaces (/admin/*, /tenant/*) in the existing PWA; seeded first superadmin; generate+force-change credential model; must_change_password flag + forced-reset screen; require_platform_admin dependency |
| [0015](0015-facility-catalog-model.md) | Facility Catalog Model | Accepted | Global platform catalog at /facility_catalog/{type_id} seeded with standard sports; per-tenant facility instances gain facility_type_id; catalog CRUD deferred; creation constraint enforces type selection |
| [0016](0016-user-provisioning.md) | Bulk & Manual User Provisioning | Accepted | Single UserProvisioningService.create_user() for all paths; CSV schema with partial-success import; household_id derived from flat_number; frontend parses CSV (backend stays file-agnostic); 500-row cap |
| [0017](0017-deletion-retention-lifecycle.md) | Deletion, Retention & Lifecycle | Accepted | Three-stage tenant lifecycle ACTIVE→INACTIVE→PURGED; user soft-delete with Firebase Auth disable + cancel future bookings; self-deactivation forbidden; audit trail preserved through INACTIVE period |

## Reading Order

For someone new to the project, read ADRs in numerical order.
Each builds on previous decisions.

## Writing a New ADR

1. Copy `template.md` to `NNNN-short-name.md` (next sequential number)
2. Fill in all sections
3. Set status to "Proposed" initially
4. Open a Pull Request for discussion
5. After discussion, update status to "Accepted" and merge
6. Never modify an accepted ADR — write a superseding one instead

## ADR Statuses

- **Proposed** — Under discussion, not yet decided
- **Accepted** — Decision made and being implemented
- **Superseded by ADR-NNNN** — Replaced by a newer ADR
- **Deprecated** — No longer recommended, but not actively replaced
- **Rejected** — Considered and explicitly not adopted

## Related Documentation

- [Project README](../../README.md) — Project overview
- [Runbooks](../runbooks/) — Operational procedures
- [Diagrams](../diagrams/) — Architecture visualizations (future)
