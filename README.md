# SportSlotReservation

Multi-tenant Sport Slot Reservation SaaS for Indian residential
communities. Built on Google Cloud Platform with FastAPI, React,
and Firestore.

## Project Status

**Phase 1: Workspace Bootstrap** — In progress

Currently establishing the foundational repository, local
development environment, and GCP project structure. Application
code begins in Phase 2.

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
