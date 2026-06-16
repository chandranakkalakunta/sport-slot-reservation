# ADR-0001: Tech Stack & Software Versions

## Status

Accepted — 2026-06-09

> **Note (2026-06-16):** The frontend compute decision in this ADR was superseded by ADR-0012 (Firebase Hosting). As-built: one Cloud Run service (backend `sport-slot-api`) + Firebase Hosting (frontend). See ADR-0012.

## Context

We are building SportBook, a production-grade multi-tenant Sport Slot Reservation System on Google Cloud Platform for Indian residential communities. Before any code is written, we need to lock down the technology stack across all dimensions: backend language and framework, frontend framework, containerisation, compute platform, runtime versions, and package managers.

Selection criteria, in priority order:
1. Long-term viability — technology should remain relevant for 3-5 years
2. Maintainability — codebase must be sustainable for a solo developer initially, growing team later
3. Performance — must handle flash-traffic spikes at booking window open times
4. Scalability — must scale from 1 tenant to 100+ tenants without architecture rewrite
5. Suitability for requirements — multi-tenant SaaS with AI booking agent
6. Career alignment — supports AI/ML Architect career direction

## Decision

### Backend
- **Language:** Python 3.12
- **Framework:** FastAPI

### Frontend
- **Framework:** React 18 + Vite + TypeScript
- **Mobile Strategy:** Progressive Web App (PWA) in v1; React Native added in Phase 9+ if user demand justifies it
- **Rendering:** Client-Side Rendering (CSR) — no SEO requirements

### Containerisation
- **Strategy:** Multi-stage Dockerfile for both backend and frontend
- **Backend runtime image:** python:3.12-slim
- **Frontend runtime image:** ~~nginx:alpine~~ — **Superseded by ADR-0012:** the frontend is a static PWA served via Firebase Hosting (no container/runtime image).

### Compute Platform
- **Backend:** Cloud Run (serverless containers)
- **Frontend:** ~~Cloud Run with nginx serving static files~~ — **Superseded by ADR-0012:** served as a static PWA via **Firebase Hosting** (CDN-delivered static assets; no Cloud Run service for the frontend). ADR-0001's "single Cloud Run service" assumption applies to the **backend** (`sport-slot-api`) only.
- **Why not GKE:** Cloud Run is sufficient for SportBook's scale, requires no Kubernetes overhead, scales to zero when idle, and is significantly cheaper to operate

### Runtime Versions (Locked)
- **Python:** 3.12
- **Node.js:** 22 LTS
- **React:** 18

### Package Managers
- **Python:** uv (10-100x faster than pip, modern lockfile-based)
- **Node.js:** pnpm (faster than npm, efficient disk usage via shared store)

### Architectural Principle (Mandatory)
- **Stateless Services:** All backend services follow stateless design
  - No server-side sessions — JWT-based authentication only
  - All state in external stores (Firestore, Redis, Cloud Storage)
  - All endpoints idempotent
  - No local file storage on Cloud Run instances
  - Background work via Cloud Tasks, not in-memory queues
  - This principle is mandatory across all phases

## Rationale

### Why Python + FastAPI for Backend
- Python is the dominant language for AI/ML in 2026, directly relevant for Phase 6 AI booking agent
- FastAPI provides async/await for high concurrency, automatic OpenAPI documentation, and Pydantic-based validation
- Same language end-to-end (API + AI agent) simplifies the architecture
- Aligns with Chandra's career direction toward AI/ML Architect roles
- Cold start of 1-2 seconds acceptable for residential community use case

### Why React + Vite + TypeScript + PWA for Frontend
- React has the largest talent pool, ecosystem, and component libraries in India
- Vite is the fastest modern build tool, drastically improving developer experience
- TypeScript catches errors at compile time, essential for a maintainable codebase
- PWA approach provides 80% of the native app experience with 20% of the effort
- Single codebase serves web and mobile use cases
- React Native upgrade path preserved for future native app development

### Why Multi-stage Dockerfile + Cloud Run
- Multi-stage builds produce smaller, more secure production images
- Cloud Run eliminates Kubernetes operational complexity
- Scale-to-zero matches the bursty traffic pattern of sports bookings
- Pay-per-request pricing is cost-optimal for early-stage products
- HTTPS, custom domains, monitoring all built-in

### Why uv + pnpm Package Managers
- Both significantly faster than traditional alternatives (pip, npm)
- Both produce reproducible lockfiles
- CI/CD pipeline speed materially improved
- Industry adoption increasing rapidly (used by Anthropic, OpenAI, Replit)

### Why Stateless Architecture
- Required for Cloud Run horizontal scaling
- Enables zero-downtime deployments via rolling updates
- Simpler mental model — every request is independent
- Easier to test, debug, and reason about
- Avoids entire classes of bugs (session corruption, instance affinity)

## Consequences

### Positive
- Modern, production-grade tech stack
- Fast development velocity with FastAPI + Vite
- AI agent (Phase 6) integrates naturally with Python ecosystem
- Cost-optimal during early stages (scale to zero on Cloud Run)
- Aligned with industry trends and career goals
- Stateless principle prevents many common issues

### Negative
- Python cold starts (~1-2 seconds) — mitigated by `min-instances=1` in PROD
- PWA on iOS has limitations (no advanced notifications, not in App Store)
- uv and pnpm are newer — minor risk of unexpected issues
- Multi-stage Dockerfiles slightly more complex than single-stage

### Risks and Mitigations
- **Risk:** uv or pnpm has a critical bug
  - **Mitigation:** Both are production-tested at scale; can fall back to pip/npm if needed
- **Risk:** Cloud Run cold starts annoy users
  - **Mitigation:** PROD uses `min-instances=1` during peak hours (18:00-22:00 IST)
- **Risk:** PWA limitations frustrate residents
  - **Mitigation:** React Native upgrade path in Phase 9+

## Alternatives Rejected

### Backend
- **Node.js + NestJS:** Single language across stack appealing, but Python's AI/ML ecosystem is critical for Phase 6
- **Go + Gin:** Excellent performance, but verbosity slows development, weaker AI ecosystem
- **Java + Spring Boot:** Heavy memory footprint, slow cold starts unsuitable for serverless

### Frontend
- **Vue 3:** Smaller talent pool in India, less aligned with React Native migration path
- **Next.js:** SEO benefits don't apply (SportBook requires login), adds unnecessary complexity
- **SvelteKit:** Small community, risky for production SaaS

### Compute Platform
- **GKE:** Massive operational overhead for a use case Cloud Run handles cleanly; ~5-10x more expensive to operate
- **Cloud Functions:** Less flexible than Cloud Run, deprecated in favor of Cloud Run Functions

### Package Managers
- **pip + requirements.txt:** No proper lockfile, slow dependency resolution
- **Poetry:** Excellent but slower than uv; uv is the direction the industry is moving

## References

- FastAPI documentation: https://fastapi.tiangolo.com
- Vite documentation: https://vitejs.dev
- uv documentation: https://github.com/astral-sh/uv
- pnpm documentation: https://pnpm.io
- Cloud Run documentation: https://cloud.google.com/run/docs
- React 18 documentation: https://react.dev
