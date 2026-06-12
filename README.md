# SportSlotReservation

Multi-tenant Sport Slot Reservation SaaS for Indian residential
communities. Built on Google Cloud Platform with FastAPI, React,
and Firestore.

## Project Status

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Workspace Bootstrap | ✅ COMPLETE |
| **Phase 2** | Backend API Foundation | ✅ COMPLETE |
| **Phase 3** | Booking Engine | ⬜ Planned |
| **Phase 4** | Frontend PWA | ⬜ Planned |
| **Phase 5** | CI/CD Pipeline | ⬜ Planned |

## Architecture

```mermaid
flowchart TD
    subgraph Client["Client Layer"]
        B[Browser / Mobile PWA]
    end

    subgraph Auth["Firebase Auth"]
        FA[Firebase Auth\nEmail + Google OAuth]
    end

    subgraph Run["Cloud Run — FastAPI"]
        direction TB
        MW1[RequestIdMiddleware]
        MW2[EnvelopeRateLimitMiddleware\nslowapi · 30 req/min per token]
        DEP[JWT Dependency\nfirebase-admin verify_id_token]
        TEN[TenantContext\nuid · tenant_id · role]
        API["/api/v1/users/me\n/healthz · /readyz"]
        REPO[TenantRepository\n/tenants/{tid}/users/{uid}]
        MW1 --> MW2 --> DEP --> TEN --> API --> REPO
    end

    subgraph FS["Cloud Firestore"]
        direction TB
        T1["/tenants/greenpark/users/…"]
        T2["/tenants/bluehills/users/…"]
    end

    subgraph CICD["CI/CD"]
        GH[GitHub Actions]
        CB[Cloud Build\ncloudbuild.yaml]
        AR[Artifact Registry\nasia-south1]
        CR[Cloud Run Deploy\nsa-cloud-run]
        GH --> CB --> AR --> CR
    end

    B -->|"HTTPS + Bearer JWT"| Run
    B -->|"sign-in"| FA
    FA -->|"ID token"| B
    DEP -->|"verify_id_token"| FA
    REPO --> FS
```

**Tenant isolation — 5 layers (ADR-0004):**

1. Firestore Security Rules — permanent deny-all (no client path)
2. `TenantRepository` — construction-time `tenant_id` enforcement
3. JWT × subdomain cross-check in auth dependency (ADR-0007)
4. Integration tests asserting cross-tenant 403
5. CI architecture gate (`test_architecture.py`)

## Quick Start

```bash
# Verify local toolchain (13 checks)
make verify-env

# GCP authentication (one-time)
gcloud auth application-default login
gcloud auth application-default set-quota-project sport-slot-dev

# Install backend dependencies
make install

# Run backend dev server  (uses PYTHONPATH=src automatically)
make run-dev

# Run tests with coverage
make test

# See all commands
make help
```

See [docs/runbooks/local-development.md](docs/runbooks/local-development.md) for the full runbook.

## Overview

SportSlotReservation enables residential housing communities in
India to manage shared sports facilities (tennis, badminton,
swimming, cricket nets, etc.) through:

- Per-tenant facility and slot management
- Resident booking with race-condition protection (Redis distributed lock)
- Per-flat (household) billing aggregation
- Multi-channel notifications
- AI-powered conversational booking agent (Phase 6+)

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 + FastAPI 0.115 |
| Frontend | React 18 + Vite + TypeScript (PWA) |
| Database | Cloud Firestore Native Mode (asia-south1) |
| Cache / Locks | Cloud Memorystore Redis (Phase 3) |
| Auth | Firebase Auth (Google OAuth + Email/Password) |
| Rate Limiting | slowapi (in-process) → Redis → Cloud Armor |
| Compute | Cloud Run (min=0/max=2, non-root container) |
| Container Build | Cloud Build + Artifact Registry |
| IaC | Terraform |
| CI/CD | GitHub Actions + Workload Identity Federation |
| Package manager | uv (src-layout) |
| Build interface | Makefile + bash scripts |

## Repository Structure

```
backend/             # FastAPI application (src-layout)
  src/sport_slot/    # Application package
    api/             # Routers, error codes, error handlers
    auth/            # JWT dependency, TenantContext
    middleware/      # RequestId
    repositories/    # TenantRepository, PlatformRepository
  tests/             # pytest suite (31 tests, 89% coverage)
  Dockerfile         # Multi-stage: uv builder → slim runtime
  cloudbuild.yaml    # Cloud Build config
  pyproject.toml     # uv / pytest / ruff / bandit config
frontend/            # React + Vite + TypeScript PWA (Phase 4)
infrastructure/      # Firebase rules, IAM config
terraform/           # Module-ready flat Terraform
scripts/             # Coordinator-run bash scripts
docs/
  adr/               # Architecture Decision Records (0001–0008)
  runbooks/          # Operational runbooks
  security/          # Security charter
  retrospectives/    # Phase retrospectives
.github/             # CI/CD workflow stubs
```

## Architecture Decision Records

All major technical decisions are documented in [docs/adr/](docs/adr/).

| ADR | Title | Status |
|-----|-------|--------|
| [0001](docs/adr/0001-tech-stack-and-software-versions.md) | Tech Stack & Software Versions | Accepted |
| [0002](docs/adr/0002-database-technology-selection.md) | Database Technology Selection | Accepted |
| [0003](docs/adr/0003-build-tooling-interface.md) | Build Tooling Interface | Accepted |
| [0004](docs/adr/0004-tenant-isolation-strategy.md) | Tenant Isolation Strategy | Accepted |
| [0005](docs/adr/0005-cost-baseline-and-budget-alerts.md) | Cost Baseline & Budget Alerts | Accepted |
| [0006](docs/adr/0006-api-design-patterns.md) | API Design Patterns | Accepted |
| [0007](docs/adr/0007-authentication-and-authorization.md) | Authentication & Authorization | Accepted |
| [0008](docs/adr/0008-data-layout-and-repository-contract.md) | Data Layout & Repository Contract | Accepted |

## Security

See [docs/security/charter.md](docs/security/charter.md) for the full security charter.
Key decisions: zero static credentials (org policy enforced), Firebase Admin SDK JWT
verification only (python-jose prohibited — CVE-2024-33663/CVE-2024-33664), permanent
deny-all Firestore rules, non-root Docker runtime, no PII in logs.

## License

MIT License. See [LICENSE](LICENSE) file.

## Maintained By

[Chandra AI Labs](https://chandraailabs.com)  
Contact: admin@chandraailabs.com
