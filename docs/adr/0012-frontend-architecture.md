# ADR-0012: Frontend Architecture

Status: Accepted | Date: 2026-06-13 | Author: Chandra Nakkalakunta

## Context
Phase 4 builds the resident PWA. Hosting must serve per-tenant
subdomains; the stack is fixed by ADR-0001 (React 18 + Vite + TS,
PWA-first). Verification against current Firebase documentation
(2026-06) found a constraint that reshapes hosting.

## Decisions

### 1. Hosting: classic Firebase Hosting now; LB wildcard at Phase 7
Classic Firebase Hosting does NOT support wildcard custom domains
and caps each apex at 20 subdomains (SSL minting limits). DEV
therefore uses NAMED subdomains (demo.sportbook.chandraailabs.com
etc.) — an accepted, documented constraint. Production wildcard
(*.sportbook) arrives in Phase 7 with the Global External Load
Balancer that Cloud Armor requires anyway: one piece of
infrastructure provides WAF, wildcard certificate, and host
routing. Firebase App Hosting (which supports wildcards) was
evaluated and rejected for now: SSR-oriented product; our PWA is
static.

### 2. API routing: same-origin via Hosting rewrites
firebase.json rewrites /api/** (and /health, /readyz) to the
sport-slot-api Cloud Run service. Same-origin eliminates CORS
entirely. VERIFY-ITEM for 4.2/4.5: how the original Host survives
the rewrite (expected: X-Forwarded-Host) and the middleware
provenance rule — X-Forwarded-Host is client-spoofable on direct
run.app calls, so the tenant cross-check update must not blindly
trust it; the JWT remains the tenant source of truth.

### 3. Stack
React 18 + Vite + TypeScript (strict). Server state: TanStack
Query. Client state: React context (auth, tenant) — no store
library until something demands one. Routing: React Router.
Testing: vitest + Testing Library. Lint: ESLint 9 flat config.
PWA: vite-plugin-pwa (manifest + service worker).

### 4. Theming: CSS variables as the tenant contract
Per-tenant branding (requirements) applies at runtime from the
tenant document. The mechanism is CSS custom properties set on
:root; therefore styling uses plain CSS modules + variables.
Tailwind rejected: compile-time theme tokens fight runtime tenant
switching.

### 5. Auth scope (v1)
Sign-in only (Email/Password + Google) against seeded users.
Registration ships with the invite-code backend (later phase) —
no placeholder signup.

## Consequences
+ Zero CORS surface; one hosting product until scale demands the LB.
− Tenant onboarding in DEV requires a console/DNS step per named
  subdomain (acceptable: DEV has single-digit tenants).
− Wildcard remains unproven until Phase 7 (accepted; LB design is
  well-trodden).

## References
ADR-0001, ADR-0004 (Layer 3), ADR-0007, Charter; Firebase Hosting
custom-domain documentation (20-subdomain cap), Firebase App
Hosting wildcard announcement.
