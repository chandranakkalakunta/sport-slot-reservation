# SportSlot Reservation — Roadmap

## Phase status

| Phase | Title | Status |
|-------|-------|--------|
| 1 | Infrastructure Foundation | ✓ Complete |
| 2 | Backend Foundation | ✓ Complete |
| 3 | Booking Core | ✓ Complete |
| 4 | Frontend Core | ✓ Complete |
| 5 | Admin & Onboarding | ✓ Complete |
| 6 | CI/CD | ✓ Complete |
| 7 | Notifications & Self-Service | Next |
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

## Phase 6 — CI/CD ✓ Complete

Shipped:
- GitHub Actions pipeline: pr-gates (ruff, bandit, pytest ≥90%, ESLint,
  Vitest, pnpm build) + deploy-on-main (Cloud Run + Firebase Hosting)
- Workload Identity Federation (WIF) — keyless, no JSON keys anywhere
- Firebase Hosting via REST API + SA-impersonated OAuth2 token
  (firebase-tools incompatible with WIF external_account ADC)
- Branch protection on main: PR + passing gates required
- All CI IAM in version-controlled Terraform (`wif_iam.tf`)

## Phase 6 deferrals (tracked)

| Item | Deferred to |
|------|-------------|
| storage.admin tighten to bucket-scoped on sport-slot-dev-cloudbuild | Phase 9 (least-privilege hardening) |
| detect-secrets pre-commit hook | Phase 9 |
| Smoke test hitting live service URL | Phase 9 |
| Secret Manager integration in CI (no new secrets needed in Phase 6) | Phase 9 if new secrets added |
| deploy_hosting.sh CI branch cleanup (vestigial; CI uses REST script) | Phase 9 cleanup |

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
