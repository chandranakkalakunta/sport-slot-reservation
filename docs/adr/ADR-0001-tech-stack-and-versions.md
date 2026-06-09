# ADR-0001: Tech Stack & Software Versions

**Status:** Accepted  
**Date:** 2026-06-09  
**Deciders:** Chandra Nakkalakunta

## Context

SportSlotReservation is a multi-tenant SaaS platform targeting Indian
residential communities. It must handle concurrent slot bookings,
per-tenant data isolation, mobile-first residents, and operator-facing
admin workflows — all on a budget appropriate for a bootstrapped product.

We need to pin major versions upfront so every phase of the build
targets the same runtime, tooling, and dependency baseline. Drifting
versions mid-build has historically caused silent incompatibilities
between dev and production environments.

## Decision

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend runtime | Python | 3.12 |
| Backend framework | FastAPI | 0.115.x |
| ASGI server | Uvicorn | 0.32.x |
| Data validation | Pydantic | v2 (2.9.x) |
| Frontend framework | React | 18.x |
| Frontend build | Vite | 6.x |
| Frontend language | TypeScript | 5.x |
| UI components | shadcn/ui + Tailwind CSS v4 | latest |
| PWA | vite-plugin-pwa | 0.21.x |
| State / data fetching | TanStack Query | v5 |
| Database | Cloud Firestore (Native Mode) | — |
| Cache + distributed locks | Cloud Memorystore Redis | 7.x |
| Auth | Firebase Auth | — |
| Compute | Cloud Run (serverless) | — |
| IaC | Terraform | 1.9.x |
| CI/CD | GitHub Actions + Workload Identity Federation | — |
| Build interface | Makefile + bash | — |
| Container base | python:3.12-slim (Debian) | — |
| Node.js (build only) | Node.js | 22 LTS |

All Python packages are pinned in `requirements.txt`. Node packages are
pinned via `package-lock.json`. These versions are the project baseline
and must not be silently upgraded — changes require a new ADR or an
explicit version-bump PR.

## Consequences

**Positive**
- Reproducible builds across local, CI, and Cloud Run.
- Python 3.12 brings improved performance and better error messages vs 3.11.
- Pydantic v2 is significantly faster for request validation than v1.
- React 18 + TanStack Query v5 gives a modern, well-supported frontend foundation.
- Vite 6 + TypeScript 5 keeps compile times fast and types strict.

**Negative / risks**
- Pinning requires deliberate maintenance; versions will age.
- Pydantic v2 is a breaking API change from v1 — any copy-pasted v1 patterns must be audited.
- Cloud Memorystore Redis adds cost even at the smallest tier; must be included in budget baseline.

**Neutral**
- FastAPI + Pydantic v2 + Python 3.12 is the current de facto Python async API stack.
- Terraform 1.9.x has stable provider support for all GCP resources needed in this project.
