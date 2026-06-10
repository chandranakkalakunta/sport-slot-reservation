# SportSlotReservation

Multi-tenant Sport Slot Reservation SaaS for Indian residential
communities. Built on Google Cloud Platform with FastAPI, React,
and Firestore.

## Project Status

**Phase 1: Workspace Bootstrap** — COMPLETE

All foundational infrastructure is in place:

- GitHub repository with proper structure and ADR documentation
- Local development toolchain installed and verified (13 checks)
- GCP project (sport-slot-dev) with 18 enabled APIs
- 4 service accounts with least-privilege IAM (zero JSON keys)
- Workload Identity Federation for GitHub Actions CI/CD
- Firebase initialized: Email/Password + Google OAuth providers
- Firestore database in Native Mode (asia-south1)
- Terraform foundation with module-ready flat structure
- Existing resources documented as Terraform data sources
- Makefile + bash scripts for daily operations

**Next: Phase 2** — Backend API foundation (FastAPI, repositories, auth middleware)

## Quick Start

After cloning the repository:

```bash
# Verify your development environment
make verify-env

# See all available commands
make help

# Check GCP authentication
make gcp-whoami

# Switch to sport-slot-dev project
make gcp-set-dev
```

See [docs/runbooks/local-development.md](docs/runbooks/local-development.md)
for complete local setup instructions.

## Overview

SportSlotReservation enables residential housing communities in
India to manage shared sports facilities (tennis, badminton,
swimming, cricket nets, etc.) through:

- Per-tenant facility and slot management
- Resident booking with race-condition protection
- Per-flat (household) billing aggregation
- Multi-channel notifications
- AI-powered conversational booking agent

## Architecture

The system is designed to scale from a single tenant to thousands
of tenants across multiple countries with per-country data
sovereignty. See architectural decisions in [docs/adr/](docs/adr/).

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 + FastAPI |
| Frontend | React 18 + Vite + TypeScript (PWA) |
| Database | Cloud Firestore (Native Mode) |
| Cache / Locks | Cloud Memorystore Redis |
| Auth | Firebase Auth (Google OAuth + Email/Password) |
| Compute | Cloud Run (serverless containers) |
| IaC | Terraform |
| CI/CD | GitHub Actions with Workload Identity Federation |
| Build tooling | Makefile + bash hybrid |

## Repository Structure

```
backend/             # FastAPI application
frontend/            # React + Vite + TypeScript PWA
infrastructure/      # Terraform infrastructure-as-code
scripts/             # Bash scripts for operations
docs/                # Documentation
  adr/               # Architecture Decision Records
  runbooks/          # Operational runbooks
  diagrams/          # Architecture diagrams
tests/               # Cross-cutting tests
.github/             # CI/CD workflows
```

## Architecture Decision Records

All major technical decisions are documented as ADRs in
[docs/adr/](docs/adr/). Current ADRs:

- ADR-0001: Tech Stack & Software Versions
- ADR-0002: Database Technology Selection
- ADR-0003: Build Tooling Interface
- ADR-0004: Tenant Isolation Strategy
- ADR-0005: Cost Baseline & Budget Alerts

## License

MIT License. See [LICENSE](LICENSE) file.

## Maintained By

[Chandra AI Labs](https://chandraailabs.com)  
Contact: admin@chandraailabs.com
