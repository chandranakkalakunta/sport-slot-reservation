# SlotSense — Project Requirements
#
# (Product formerly known as SportSlotReservation; rebranded during
# Phase 9, slice 6.3.)
#
# This document defines WHAT we build.
# Pair with the Three-Agent Engineering Protocol (maintained
# separately as private methodology) which defines HOW.

# ═══════════════════════════════════════════════════════════════
# PROJECT IDENTITY
# ═══════════════════════════════════════════════════════════════

- **Product:** SlotSense (formerly SportSlotReservation)
- **Purpose:** Multi-tenant SaaS for Indian residential community sports facility booking
- **Brand:** Chandra AI Labs (chandraailabs.com)
- **Repo:** github.com/chandranakkalakunta/sport-slot-reservation (public; repo name unchanged for URL stability)
- **Local:** ~/Documents/Learning/Projects/sport-slot-reservation
- **Copyright:** Chandra AI Labs (chandraailabs.com)
- **Commit email:** chandra.n@chandraailabs.com
- **Admin email:** admin@chandraailabs.com (GCP org admin — locked away for emergencies)

# ═══════════════════════════════════════════════════════════════
# DOMAIN MODEL
# ═══════════════════════════════════════════════════════════════

## Multi-Tenant Hierarchy

- **Level 1: Platform Admin** — Global parameters, metrics, tenant onboarding
- **Level 2: Tenant** — Each housing community/society, isolated with custom rules
- **Level 3: Household/Family** — Tied to a physical flat number within a tenant
- **Level 4: Resident/User** — Individual profiles tied to a household

## Tenant Identification

- URL: {tenant-slug}.sportbook.chandraailabs.com
- Wildcard DNS — zero DNS burden on tenants
- Platform admin assigns slugs during onboarding
- JWT is source of truth for tenant identity; URL is for UX

## Per-Tenant Branding

Each tenant gets: logo, favicon, primary/secondary/background colors, font family,
footer text, contact email. Applied via CSS variables based on subdomain.

## User Roles

- **platform_admin** — Full system access
- **tenant_admin** — Manages their tenant (society manager)
- **resident** — Books slots, views own bookings
- **guest** — Limited access (future)
- **tenant_facility_admin** — Manages specific facility (future)
- **resident_household_head** — Manages household members (future)

## Dynamic Policy Engine

Zero-code tenant onboarding. Rules resolve: Tenant Override → Global Default.

Configurable parameters:
- `max_slots_per_user_per_sport_per_day` (integer, default 1)
- `booking_horizon_days` (days in advance, default 1)
- `booking_window_open_time` (e.g., 20:00 IST)
- `cancellation_buffer_hours` (hours before slot, default 2)
- `max_sub_profiles_per_household` (cap, default 5)
- `allow_tenant_profile_bookings` (boolean for renter parity)
- `dynamic_pricing_enabled` (boolean for peak/off-peak)
- `billing_cycle_type` (MONTHLY_POSTPAID | BIWEEKLY | PREPAID)
- `billing_cycle_anchor_day` (day of month/week)
- `active_notification_gateways` (WhatsApp, SMS, Email)
- Dynamic slot durations per facility (not fixed 60 minutes)

# ═══════════════════════════════════════════════════════════════
# CORE WORKFLOWS
# ═══════════════════════════════════════════════════════════════

## User Provisioning
- CSV/API bulk upload by society management
- Self-service resident registration via invite codes
- Invite code format: TENANT-FLATID-RANDOM6 (single-use, 7-day expiry)

## Facility Grid Management
- Dynamic facilities (Badminton Court 1, Tennis Court 2, etc.)
- Custom slot increments per facility
- Profile-based operations

## Booking Engine
- Flash-traffic at booking window open (20:00 IST)
- Redis distributed lock prevents double-booking
- Per-user and per-household quotas prevent slot hoarding (per-sport, per-day; see ADR-0010)
- Quota enforced at both propose-time (UX) and execute-time (correctness)
- Idempotent booking creation

## Pricing Engine
- Flat rates or time-based variations
- Peak hours (weekends/mornings) vs off-peak
- Configurable per tenant

## Post-Paid Billing Ledger
- Immutable transaction ledger per household
- Flat-grouped billing (not per-user)
- Automated statement generation
- No payment gateway initially (offline settlement)

## Notifications
- Email (live via Resend); WhatsApp and SMS planned
- Event-driven: booking confirmation, cancellation, reminders
- Periodic: monthly summary statements
- Per-tenant gateway configuration
- Cloud Tasks + OIDC for reliable async delivery (see ADR-0019)

## AI Booking Agent — SlotSense (Phase 9, shipped)

Production-ready conversational agent for natural-language booking operations.

**Capabilities:**
- Function calling over 5 tools: check_availability, book, cancel, list_my_bookings, get_my_preferences
- Vertex AI Gemini 1.5 Pro as the LLM
- Propose-confirm-execute gate: all mutations require explicit user confirmation; structured pending actions in Redis with 5-min TTL
- Output guard: classifier detects hallucinated facility/booking IDs, fails closed
- Preference memory: per-user, per-sport last-used times stored for "usual court" intent
- Deterministic Python guards override LLM weaknesses:
  - AM-past-→PM advancement (compensates for unreliable LLM temporal reasoning)
  - Cancel candidate filter (exact rule-based matching, not LLM judgment)
  - Quota check at propose time (defense in depth alongside execute-time check)
  - Per-sport quota counting (across facility lookups for accuracy)
- Stateful cancel disambiguation via secondary Redis pointer (multi-candidate selection)
- Error mapping by error_code (not HTTP status) — 7 distinct user-facing messages
- Chat UI on `/assistant` route: sessionStorage thread, proposal cards with Confirm/Cancel buttons, suggested-prompt chips, typing indicator
- PWA-first: 100dvh, keyboard-aware flex, 44pt tap targets

**Architectural decisions:** ADRs 0021 (architecture) and 0022 (guardrails), plus ADRs 0023-0030 for Phase 9 slice-specific decisions (to be written in Phase 9 closure).

**Future capabilities (post-v1):**
- Voice mode with constrained classifier
- Multi-turn conversation history (Redis-backed)
- Server-persisted chat history (cross-device continuity)
- Push notifications via PWA

# ═══════════════════════════════════════════════════════════════
# TECHNOLOGY STACK (per Phase 0 ADRs)
# ═══════════════════════════════════════════════════════════════

## ADR-0001: Tech Stack
- Backend: Python 3.12 + FastAPI
- Frontend: React 18 + Vite + TypeScript + PWA
- Containerization: Multi-stage Dockerfile on Cloud Run
- Python packages: uv
- Node packages: pnpm
- Architecture: Stateless services (mandatory)
- Mobile: PWA-first (current state); React Native if PWA limits ever bind

## ADR-0002: Database
- Cloud Firestore Native Mode (logical tenant isolation)
- Cloud Memorystore Redis (distributed locks, caching, pending actions for agent)
- Per-country deployments for data sovereignty
- BigQuery federation for cross-country reporting

## ADR-0003: Build Tooling
- Makefile (discovery layer) + bash scripts (implementation)
- Self-documenting via `make help`
- Safety guardrails: typed confirmation for destructive ops

## ADR-0004: Tenant Isolation
- 5-layer defense-in-depth:
  1. Firestore Security Rules (database level)
  2. Repository Pattern (code level — TenantContext required)
  3. Auth Middleware (JWT vs URL cross-check)
  4. Automated Tests (cross-tenant access tests)
  5. CI/CD Gates (static analysis blocks raw queries)
- Subdomain identification with wildcard DNS

## ADR-0005: Cost Baseline
- DEV ≤₹5,000/month
- PROD target ≤₹2,000/tenant/month (projected ~₹195 at 200 tenants)
- 4-tier alert thresholds (50/75/100/120%)
- Hard limits at 100%, auto-shutdown at 120%

## Phase 9 additions (Vertex AI)
- Vertex AI Gemini 1.5 Pro for agent LLM
- Token-budgeted prompts with structured tool definitions
- Output classifier as a separate Vertex call (fail-closed)

# ═══════════════════════════════════════════════════════════════
# SECURITY POSTURE
# ═══════════════════════════════════════════════════════════════

## Investment Level: Level 3+ (Match HR RAG + Cloud Armor/WAF)

## Principles
1. Defense-in-Depth — multiple overlapping layers
2. Least Privilege — minimum permissions, grow per phase
3. Secure by Default — deny-all baseline, auth required
4. Zero Static Credentials — ADC + WIF, no JSON keys
5. Privacy by Design — no PII in logs, SHA-256 analytics
6. Fail Closed — deny on failure, not allow
7. Verify, Don't Trust — check every operation

## Per-Phase Security Controls (reconciled to actual project history)
- **Phase 1 (done):** Zero JSON keys, 4 SAs, WIF, deny-all Firestore
- **Phase 2 (done):** Security headers, CORS, rate limiting, PII redaction
- **Phase 3 (done):** Booking quotas, anti-abuse patterns
- **Phase 5 (partial, status corrected 2026-07-16 DOC-TRUTH):** Bandit
  (implemented), pip-audit (implemented, warn-only — CI-AUDIT-RATCHET
  ratchets to blocking), Gitleaks secret scanning (implemented,
  blocking); Binary Auth, KMS signing, container scanning, pnpm audit
  — planned, Phase 17 PR-5
- **Phase 6 (done):** CI/CD pipeline hardening, WIF main-branch-only
- **Phase 7 (done; auth):** Password policy (zxcvbn+HIBP), self-service password reset, forced-password gate
- **Phase 7 (partial; notifications):** 7.1 done (email via Resend); 7.3-7.6 deferred (SMS/WhatsApp, in-app, push, analytics)
- **Phase 8 (deferred):** CMEK, VPC service controls, MFA for admins, pen testing, DPDP formalization — this work is actually landing as Phase 17 (ADR-0038, ADR-0039), not Phase 8; the four hardening items are accepted residuals with revisit triggers, see ADR-0039 (status corrected 2026-07-16, DOC-TRUTH)
- **Phase 9 (done):** Agent guardrails (ADR-0022) — output classifier, propose-confirm gate, hallucination prevention, per-tenant scoping

## Compliance: DPDP Act (India)
- Data stored in India (asia-south1) for Indian residents
- No PII in analytics (SHA-256 hashed IDs only)
- Right to deletion and export
- Breach notification within 72 hours
- Formal DPDP audit pending (Phase 8 deferred)

# ═══════════════════════════════════════════════════════════════
# GCP INFRASTRUCTURE (current state, as of 2026-06-28)
# ═══════════════════════════════════════════════════════════════

- **Org:** chandraailabs.com (ID: 833112493322)
- **Project:** sport-slot-dev (Number: 707808711911)
- **Billing:** 014A8C-586310-DE4575 (free trial, ₹28,710 credits — expires 2026-09-05)
- **Region:** asia-south1 (Mumbai)
- **State bucket:** gs://sport-slot-dev-tfstate (versioned)
- **APIs:** 18+ enabled (core + operational + Vertex AI)
- **Service Accounts:** sa-cloud-run, sa-firebase-admin, sa-cloud-build, sa-monitoring
- **WIF:** github-actions-pool (main branch only → sa-cloud-build)
- **Firebase:** Enabled, Web App, Email+Google auth providers; Hosting deployed via Hosting REST API
- **Firestore:** Native Mode, asia-south1, deny-all rules + tenant-scoped rules
- **Memorystore Redis:** Provisioned for distributed locks and pending actions
- **Cloud Tasks:** Provisioned for notification dispatch (OIDC-authenticated worker)
- **Vertex AI:** Gemini 1.5 Pro (asia-south1)
- **Auth:** ADC pattern (org policy blocks JSON key creation)
- **Terraform:** Module-ready flat, google/google-beta ~>6.0, resources as data sources

**Operational note:** Trial credits expire 2026-09-05. Production deployment plan must exist before the 30-day window opens (i.e., by 2026-08-05).

# ═══════════════════════════════════════════════════════════════
# PHASE ROADMAP (reconciled to actual project history)
# ═══════════════════════════════════════════════════════════════

```
Phase 0:  Foundation Decisions (ADRs 0001-0020)              ✓ COMPLETE
Phase 1:  Workspace Bootstrap                                ✓ COMPLETE
Phase 2:  Backend API Foundation                             ✓ COMPLETE
Phase 3:  Booking Engine                                     ✓ COMPLETE
Phase 4:  Frontend Foundation                                ✓ COMPLETE
Phase 5:  Admin & Provisioning                                ✓ COMPLETE
Phase 6:  CI/CD Pipeline + WIF + Branch Protection           ✓ COMPLETE
Phase 7:  Notifications (7.1) + Auth/Password Reset (7.2)    ◐ PARTIAL
          7.3-7.6 (SMS/WhatsApp, in-app, push, analytics)    — DEFERRED
Phase 8:  Production Networking (LB, wildcard TLS, Armor)    ✓ COMPLETE
Phase 9:  AI Booking Agent (SlotSense)                       ✓ COMPLETE
Phase 10: UI Redesign + PWA Mobile Validation                ✓ COMPLETE
Phase 13: Entity Lifecycle Management                        ✓ COMPLETE
Phase 15: Billing & Invoicing                                ✓ COMPLETE
Phase 16: Voice I/O for the AI Booking Assistant              ✓ COMPLETE
Phase 17: Production Readiness (CMEK, VPC, MFA, pen test —
          now ADR-0039 accepted residuals; backup/DR + TF
          rebuild path shipped, PR-1a/PR-1b)                 IN PROGRESS
```

**STALE (2026-06-28 snapshot, corrected 2026-07-16 DOC-TRUTH):** this
roadmap predates Phases 13/15/16/17 and originally mislabeled Phase 5
as "Binary Authorization + Supply-Chain Security" and Phase 8 as
"Production Readiness" — neither shipped in that slot. See
[`docs/adr/README.md`](adr/README.md) for the current ADR-indexed
phase mapping and `docs/backlog.md` for the canonical tracked-work
record; this file is not actively maintained phase-by-phase.

**Note on phase ordering:** Phases 8 and 9 are intentionally out of numerical
sequence. Phase 9 (the AI agent) was prioritized over Phase 8 (production
security hardening) because the agent demonstrates more technical breadth and
is more central to the SlotSense product story. Phase 8 remains a real
deliverable, gated on the project's transition from dev to production.

**Phase 9 detail:** 16 slices (1a, 1b, 1b.1, 1b.2, 2a, 2b, 3a, 3b, 4, 4.1,
5a, 5b, 5b.1, 5b.2, 6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7) across 14 PRs
(#27-#40). See `docs/retrospectives/phase-9.md` for the comprehensive closure
report.

# ═══════════════════════════════════════════════════════════════
# NON-NEGOTIABLES
# ═══════════════════════════════════════════════════════════════

- Zero manual cloud provisioning (everything scripted)
- Zero credential exposure (Secret Manager or ADC)
- **Minimum 90% test coverage** for merge eligibility (currently 91.12% backend; raised from initial 80% baseline)
- ShellCheck on all bash scripts
- Discussion-first for all tech decisions (ADRs before code)
- Three environments: DEV (active), TEST (on-demand), PROD (later)
- **Co-Authored-By: <Claude model version> trailer in commits.** Convention started with Claude Sonnet 4.6; current usage Claude Opus 4.7. The trailer is preserved historically; new commits reflect the active model version.

# ═══════════════════════════════════════════════════════════════
# DOCUMENT HISTORY
# ═══════════════════════════════════════════════════════════════

- **2026-06-11:** Original requirements document authored (then in `~/Downloads/files 4/`)
- **2026-06-28:** Committed into the repo as `docs/REQUIREMENTS.md` and reconciled against actual project state through Phase 9 closure. Major changes:
  - Renamed product to SlotSense (formerly SportSlotReservation)
  - Reconciled phase roadmap to actual project history (Phase 6 = CI/CD, Phase 7 = Notifications + Auth, Phase 8 = deferred, Phase 9 = AI Agent)
  - Removed historical Phase 2 sub-phase planning (Phase 2 long shipped)
  - Expanded AI Booking Agent section to reflect Phase 9 reality
  - Added Vertex AI, Memorystore Redis, Cloud Tasks to infrastructure
  - Raised coverage minimum from 80% to 90%
  - Added trial credit expiration note (2026-09-05)
  - Updated protocol reference (private methodology, not co-located)
