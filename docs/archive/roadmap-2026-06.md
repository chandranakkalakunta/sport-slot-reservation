> **ARCHIVED 2026-07-16** — `docs/backlog.md` is the canonical tracked-work
> record; `CHANGELOG.md` carries phase progress. This file is a frozen
> snapshot and is not maintained.

# SportSlot Reservation — Roadmap

## Phase status

| Phase | Title | Status |
|-------|-------|--------|
| 1 | Infrastructure Foundation | ✓ Complete |
| 2 | Backend Foundation | ✓ Complete |
| 3 | Booking Core | ✓ Complete |
| 4 | Frontend Core | ✓ Complete |
| 5 | Admin & Onboarding | ✓ Complete |
| 6 | CI/CD | Next |
| 7 | Notifications & Self-Service | Planned |
| 8 | Scalability & Observability | Planned |
| 9 | Security Hardening | Planned |

## Phase 5 deferrals (tracked)

These items were explicitly deferred during Phase 5 and are
assigned to a specific future phase or sub-phase.

| Item | Deferred to |
|------|-------------|
| Branding-in-dev correctness (tenant subdomains on localhost) | Phase 7 (subdomains) |
| Self-service email password reset (forgot password flow) | Phase 7 (notifications) |
| Synchronous provisioning → background job | Phase 7 |
| UI scalability: table/pagination/search/filter, shared list component, admin-resident segregation, superadmin tenant-user-management UI, natural ordering | Dedicated post-functional-completion phase |
| Multi-tenant admin (one admin → many tenants) | Phase 8+ (needs auth-model ADR) |
| Multi-interval / selectable facility hours | Own sub-phase (amends ADR-0010/0015) |
| Facility-catalog management UI | When a tenant needs a non-seeded sport |
| GCS logo upload (currently URL-only) | Own sub-phase |
| Composite index (uid+sport+date) + per-sport quota fix | Booking-core sub-phase with tests |
| Platform-admin host-based hardening (currently route+role in dev) | Phase 9 (per ADR-0014 §1) |

## Phase 6 — CI/CD (next)

Planned scope:
- GitHub Actions pipeline: lint → test → build → deploy
- Workload Identity Federation (WIF) for keyless Cloud Run deploy
- Coverage gate wired to measured baseline
- Smoke test hitting live service URL dynamically
- Secret Manager integration in CI
- detect-secrets pre-commit hook

## Phase 7 — Notifications & Self-Service

- Email notifications (booking confirmation, cancellation, password reset)
- Self-service forgot-password flow
- Tenant subdomain routing (fixes branding-in-dev)
- Provisioning background job (dequeue from Pub/Sub)

## Phase 8 — Scalability & Observability

- Per-prediction/query BigQuery logging
- Drift monitoring on top signal features
- p50/p95/p99 latency tracking
- Multi-tenant admin (auth-model ADR required)

## Phase 9 — Security Hardening

- CMEK on all GCS buckets and BigQuery datasets
- Platform-admin host-based gating (closes ADR-0014 §1 accepted exposure)
- Penetration testing scope
