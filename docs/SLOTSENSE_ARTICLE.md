---
title: "SlotSense: A Multi-Tenant, AI-First Sports Booking Platform"
date: 2026-06-23
summary: "How I built a production multi-tenant SaaS for residential-community sports booking on GCP — five-layer tenant isolation, a propose-confirm-execute AI agent that never lets the LLM mutate state, zero-key-management security, and PWA delivery. The architectural decisions, the tradeoffs I made on purpose, and what I'd reconsider."
tags: ["Multi-Tenant SaaS", "GCP", "Vertex AI", "AI Agents", "Security Architecture", "PWA"]
---

## The problem

In Indian residential communities, booking shared sports facilities — tennis courts, badminton courts, the cricket nets, the swimming pool — is usually handled through WhatsApp groups, paper rosters, or rudimentary booking apps. Coordination friction is real: residents double-book by accident, courts sit empty because the booking system was offline, admins spend evenings reconciling who-owes-what.

Most communities outsource facility management to third-party operators. **These operators typically take 50–75% of booking revenue.** The previous-generation vendor in this space charged ~75% of booking fees; current vendors have compressed to around 50%. Their genuine operational contribution is modest — a few support people, maintenance coordination — and the real value they capture is the *booking platform itself*, which most communities can't build independently.

This is the gap SlotSense closes. If a community has access to a multi-tenant booking platform purpose-built for residential sports facilities, the case for outsourcing management collapses. Communities can run facility operations through their existing maintenance and admin staff, and the 50–75% revenue cut goes back to either the community treasury or to lower booking fees for residents. The economics matter: for a community with even modest facility revenue (say, ₹50,000/month in booking fees), the gap represents ₹3–4.5 lakh per year in retained value.

SlotSense is built to make that retention possible.

## What this is

SlotSense is a multi-tenant SaaS platform for sports facility booking in residential communities, designed for one-platform-per-country deployment serving thousands of communities, each with thousands of residents. Three architectural commitments make it different from typical booking systems: rigorous tenant isolation, an AI assistant residents can talk to in natural language, and a security model designed for "zero key management" defense-in-depth from day one.

## Architectural decisions worth talking about

### Five-layer tenant isolation

The platform serves many communities (tenants) from one deployment. The risk that makes this hard isn't *performance* — it's the catastrophic outcome where one tenant ever sees another's data. I architected five independent layers of isolation that all have to fail simultaneously for a leak:

1. **Authentication-layer claims** — every Firebase ID token carries a `tenant_id` custom claim, set at user-creation time and validated on every backend request.
2. **API-layer enforcement** — every backend route guards on the JWT's tenant claim before reading anything.
3. **Service-layer scoping** — every Firestore query is scoped by tenant path. There's no API surface that lets a query skip the tenant prefix.
4. **Storage-layer rules** — Firestore Security Rules independently enforce tenant matching, so even if the backend had a bug, the database would refuse the cross-tenant read.
5. **Branding-layer separation** — each tenant has its own slug, theme, and subdomain conventions, so even visual mistakes (a stale cache, a misrouted asset) are tenant-scoped.

The cost of this depth is real — every layer adds verification overhead and code complexity. But the failure mode it protects against (a cross-tenant data leak) is severe enough that depth is the only honest answer. Single-layer isolation is how every multi-tenant SaaS data breach starts.

### Stateless agent with a propose-confirm-execute gate

The platform has an AI booking assistant — residents can say "book my usual tennis slot tomorrow at 7 PM" or "cancel my badminton on Friday." Vertex AI with Gemini 2.5 Flash handles intent extraction, but **the LLM never directly mutates state**.

Instead, the architecture uses a propose-confirm-execute gate: the LLM proposes a booking via a structured tool call, the backend validates it deterministically (does the facility exist? is the slot bookable?), writes a one-time pending action to Redis with a 5-minute TTL, and returns a confirmation prompt to the user. Only when the user explicitly confirms (via a button click) does the backend execute the mutation — with the originally-stored parameters, verbatim, ignoring anything the LLM might have hallucinated on the confirmation turn.

This design has three properties I deliberately optimized for:

- **No LLM-driven mutations.** A model hallucinating a wrong court ID or wrong date can't accidentally book the wrong slot — the deterministic validation catches it before the pending action is written.
- **Replay-safe.** The pending-action store consumes its key on use (GET + DEL), so a replayed confirmation can't double-book.
- **TTL-bound risk.** The 5-minute window means a forgotten proposal expires naturally; the user just asks again.

The agent also tracks user preferences — your usual court, your usual time — so it can gap-fill requests like "book my usual tennis slot tomorrow" without explicit court/time specifications. Preference memory is updated automatically as bookings happen.

This kind of agent-safety design — using the LLM as a structured-input parser, not as a mutation engine — is becoming the standard pattern for production AI integrations. I wanted to demonstrate it in working code.

### Zero-key-management security

Every secret-bearing pattern in the system was deliberately replaced with something that doesn't need a secret:

- **CI/CD authenticates to GCP via Workload Identity Federation** — no service account keys downloaded, no `GOOGLE_APPLICATION_CREDENTIALS` files in CI runners. GitHub Actions exchanges its OIDC token directly for short-lived GCP credentials.
- **Service-to-service authentication uses OIDC.** Cloud Tasks calling worker endpoints sign with their own service account identity; the worker validates the OIDC token. No shared secrets between components.
- **Firebase ID tokens for user auth.** Short-lived (1 hour), JWT-based, refreshed automatically by the client SDK. Refresh tokens never touch the backend — they're a Firebase-to-Google contract.
- **Cloud KMS for any signing keys** — managed key rotation, no key material in code.

The principle: every secret that doesn't exist is a secret that can't leak. The system has *no* long-lived credentials anywhere outside Google's managed services.

This is paired with **principle of least privilege** — each component runs as a service account with the minimum IAM roles it needs for its scope. The Cloud Run backend can write to its tenant's Firestore documents but cannot read another project's resources. The CI deployer can deploy services but cannot read user data. The blast radius of any single compromised component is bounded by what that one identity can do.

### Distributed locking for booking contention

When two residents try to book the same court at the same time, race conditions matter. I used Redis-backed distributed locks (with proper lock-release-on-failure semantics and a TTL backstop) to serialize the contended path: lock the slot, validate availability, write the booking, audit, release. Lock release happens on every code path including exceptions — verified by tests that assert audit ordering after lock release.

The choice of Redis over a Firestore transaction was deliberate: Firestore transactions have read-modify-write limits that don't compose well with the multi-step booking flow (quota check, availability check, write, audit), and Redis gives sub-millisecond lock acquisition that's effectively imperceptible to users while bulletproof under contention.

### PWA-first delivery — one codebase, every device

SlotSense is delivered as a Progressive Web App. The same React/TypeScript codebase serves the desktop web experience and **installs as a native-feeling app on iOS and Android home screens** — with offline detection, app-shell architecture, full-viewport mobile layout (100dvh, keyboard-aware), and 44pt+ tap targets throughout.

This was a deliberate alternative to native iOS/Android development:

- **One codebase, three platforms.** No separate Swift / Kotlin codebases; no separate test pipelines; no separate review-and-release cycles. Updates land everywhere on the next page load.
- **No app store gatekeeping.** Critical for a B2B SaaS where each tenant rolls out independently and updates need to be deployable on demand — not on Apple's or Google's review timeline.
- **Free distribution.** No developer-program fees, no certificates, no provisioning profiles.
- **Genuine mobile UX.** Service workers for offline behavior, install prompts for home-screen placement, full-screen standalone display. Modern PWA capabilities (since iOS 16.4 added push notifications) close most of the historical gap with native apps.

The chat UI for the AI assistant was specifically designed mobile-first — `100dvh` instead of `100vh` for correct iOS keyboard behavior, flex-anchored input bar that tracks the on-screen keyboard, 44pt minimum tap targets on every interactive element. A resident pulling out their phone to book a court works exactly as well as a desktop user.

For B2B SaaS targeting residential communities — where the user base is largely on mobile and the tenant rollout cadence is independent of app-store timelines — PWA is structurally the right delivery model. Native apps remain a future option if a specific platform feature (deep iOS integration, Apple Pay, etc.) becomes necessary, but the PWA model captures 95% of the value at 30% of the cost.

### Three-agent development protocol

This is a meta-architectural decision worth surfacing because it shaped *how* the project was built, not just *what* was built.

I worked with Claude (Anthropic's AI assistant) as a technical partner using a **Three-Agent Protocol**:

- **Strategist** (Claude in conversation) — architectural design, tradeoff analysis, code review, prompt-writing for the Worker
- **Worker** (Claude Code in CLI) — disciplined execution: opens PRs, runs tests, follows specifications
- **Coordinator** (me) — final review, merge authority, deployment, and the architectural decisions that mattered most

Every commit is co-authored with the AI partner. Every architectural decision is captured in an ADR (Architecture Decision Record) before code is written. PR review is rigorous — including security audit, edge case analysis, and test coverage discussion.

This protocol let me ship 20+ ADRs and 35+ merged PRs across nine major phases while maintaining the quality bar I'd expect from a senior engineering team. It's not "AI built my project" — it's "AI is a force multiplier on my architectural judgment, and the protocol ensures the judgment stays mine."

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | React 18 + Vite 6 + TypeScript 5.7 | Modern, fast, PWA-capable. Vite for build speed; TypeScript for compile-time guarantees. |
| Delivery | Progressive Web App (vite-plugin-pwa) | One codebase, every device — desktop web + iOS/Android installable apps |
| Frontend hosting | Firebase Hosting | Free CDN, integrates with Firebase Auth, fast deploys |
| Frontend state | React Query 5 | Server state caching with built-in invalidation; better than Redux for an API-driven app |
| Backend | Python 3.12 + FastAPI + uv | Type-checked APIs, OpenAPI spec by default, async-native. uv for fast dependency resolution. |
| Backend runtime | Cloud Run (asia-south1) | Per-request billing, auto-scaling to zero, native IAM, no server management |
| Database | Firestore (Native mode) | Multi-tenant query patterns work cleanly with security rules; horizontal scale by design |
| Cache + locks | Memorystore Redis | Sub-millisecond access; production-grade managed Redis |
| AI agent | Vertex AI (Gemini 2.5 Flash) | Function-calling support, asia-south1 availability, cost-effective at the volume profile |
| Auth | Firebase Auth + custom JWT claims | Battle-tested, free at tier; custom claims for tenant_id, role, must_change_password |
| Background work | Cloud Tasks + OIDC-signed worker endpoints | Reliable async execution without standing infra; secret-free communication |
| Email | Resend + custom domain via Namecheap | Modern transactional email; clean DKIM/SPF |
| Infrastructure | Terraform | All infrastructure as code; reproducible across environments |
| CI/CD | GitHub Actions + Workload Identity Federation | Keyless deploys; main branch protected |

The deliberate cost-optimization throughout: scale-to-zero on the backend, no managed compute for batch work (Cloud Tasks dispatches one-shot Cloud Run requests), free tiers exploited where they exist (Firebase Auth, Firebase Hosting, Cloud Tasks baseline), Gemini Flash chosen over Pro for routine agent queries, and PWA delivery avoiding native-app development cost entirely. The platform is engineered to remain viable at low tenant counts and scale economically to thousands.

## What I learned

A few things I went into the project assuming and came out the other side reconsidering:

**Stateless agent designs work harder than they look.** I assumed I'd need conversation history for the agent to feel natural. I deliberately chose a single-turn architecture instead to keep the safety properties simple. The cost is some conversational awkwardness ("which date?" "tomorrow." "tomorrow what?"). The benefit is no class of replay attacks, no token-window management, no cross-session state to leak. The right tradeoff for v1 was clear in retrospect; it wasn't obvious going in.

**Defense in depth has compound costs.** Each isolation layer is small in isolation but the testing matrix grows multiplicatively. Five layers of tenant isolation means five places to keep in sync when adding a new feature, five paths to test, five different debug locations when something goes wrong. The discipline is worth it for the security properties — but I now have a real sense of why mature SaaS products often compromise on one or two layers.

**The "right" abstraction often emerges from refactoring, not upfront design.** Several major architectural improvements (the `services/` layer that decouples routers from business logic, the agent's tool dispatcher pattern, the policy service) came from extracting them from cluttered code rather than designing them upfront. I now distrust elegant up-front designs that haven't survived contact with real implementation.

**LLM tool routing reliability has a ceiling.** Even with careful prompt engineering, current LLM tool-routing accuracy on common queries hovers around 80–90% — there's no prompt that gets you to 100%. Production AI integrations have to design around this with graceful fallbacks, retry affordances, and structured-input parsing that doesn't rely on the LLM "getting it right." This shaped how I built the agent's confirm-gate.

## Status

The platform is production-functional. Booking, cancellation, multi-tenant isolation, the AI agent, and notification flows are all live. Phase 9 (the agent) recently closed. Polish items, future scope (voice mode, multi-turn conversation history, push notifications), and operational documentation are in ongoing iteration.

## Code

[https://github.com/chandranakkalakunta/sport-slot-reservation](https://github.com/chandranakkalakunta/sport-slot-reservation) — open-source for the architecture and decisions; the deployment is private to my own dev tenant.
