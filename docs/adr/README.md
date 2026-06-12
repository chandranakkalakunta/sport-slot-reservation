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
