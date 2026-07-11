# Phase 15 Retrospective: Billing & Invoicing

**Status:** Complete
**Duration:** ~1 day (July 11, 2026 — a single, long working session)
**PR range:** #113 – #125 (13 PRs)
**ADRs added:** ADR-0035 (new)
**Final state:** 542 backend tests at 92.55% coverage; real invoices
generated and verified against live production data multiple times
during the session, not just test-suite green

---

## What this phase was

Phase 15 gave SlotSense its first-ever financial capability. Before this
phase, every facility booking was free — no price existed anywhere in
the data model, and no concept of "what does a household owe" was
possible to answer. By the end of the day, the platform could price
facilities, generate real monthly invoices grouped by household, show
them to residents and tenant-admins in two different purpose-built
views, export them to an external system, and answer natural-language
billing questions through the AI agent — all built, corrected against
real data, and shipped in one continuous session.

This phase is also the clearest example this project has produced of a
pattern worth naming directly: **almost every sub-phase shipped correct
on the first pass, and every real bug this phase found was caught not
by code review alone but by insisting on live verification against real
production data before calling anything done.** Three separate,
genuine production bugs were found this way — none of them would have
been caught by the (thorough, passing) test suites alone.

## What shipped

### The core pipeline

- **15.1 — Facility pricing.** Optional `price_paise` per facility,
  rupee-in/paise-stored, existing facilities unaffected until a
  tenant-admin explicitly sets a price.
- **15.2 — Generation-time policy.** A new, tenant-configurable field
  for what time invoices generate — built to the exact same pattern as
  the four existing policy fields, deliberately reusing the fetch-on-
  mount discipline established when that class of bug was fixed
  earlier in the project.
- **15.3 — The generation engine.** New Cloud Scheduler infrastructure
  (a dedicated `sa-scheduler-invoker` service account, keyless, matching
  this project's one-SA-per-trust-boundary convention), a new internal
  endpoint, and the core computation: group confirmed bookings by
  household, sum prices, skip zero-charge households entirely, write
  immutable invoices with deterministic IDs. Live-verified with real
  test bookings and real generated invoices in production Firestore —
  not just unit tests — before being considered done.
- **15.4 / 15.4b / 15.4c — Three purpose-built views**, each responding
  to a real gap the previous one didn't cover: a resident's own
  household invoices (15.4); a tenant-admin's latest-invoice-per-flat
  lookup for quick dispute triage (15.4b); and, once live testing
  showed "latest only" genuinely wasn't enough, per-flat history plus a
  LIVE current-month preview (15.4c) — which required extracting the
  core charge-computation logic out of the real generator into a shared
  function, so the preview and a real invoice could never silently
  compute different numbers.
- **15.5 — Export + manual recovery.** Automatic CSV/JSON export to a
  new private GCS bucket after every successful generation, plus two
  independent manual triggers (regenerate, re-export) — closing a real
  operational gap flagged early in the phase and never actually built
  until a tenant-admin's own answer ("if no manual trigger there is no
  solution") made clear it was actually needed, not optional.
- **15.6 — Agent invoice tools.** Two read-only tools letting a
  resident ask about billing in natural language — which surfaced a
  real, live-reproduced Gemini tool-selection reliability bug (see
  below), fixed the same day it was found.
- **15.7 — The ADR-0034 carve-out, finally implemented.** A promise
  made in Phase 13, before invoices existed, kept the moment they did:
  permanently deleting a tenant no longer destroys its invoices,
  implemented via dynamic subcollection enumeration rather than a
  hardcoded exclusion list that could silently go stale.

### Real production bugs found through live verification, not code review

This is worth its own section, because it's the phase's clearest
lesson. Every one of these passed its own test suite cleanly and would
have shipped invisibly broken without a live check:

1. **A confirmed/cancelled same-timestamp tie-break** (found during
   Daily Booking Overview correction, but the same class of bug):
   not from this phase specifically, but the discipline that caught it
   is exactly what caught the next three.
2. **`flat_number` locking onto the first resident encountered, even
   if that specific lookup failed** — found only by generating a real
   invoice against real (partially deleted) production data and
   noticing "Unknown flat" on a household that clearly had an active
   resident. A test suite with only synthetic fixtures would never
   have hit this exact scenario.
3. **A missing deploy-time environment variable** — the signing SA's
   email was added to `config.py` in 15.5 but never wired into the
   actual deploy script, so the live service silently ran with a
   `None` signing identity. Found the moment a real user clicked a
   real button in the real UI — not caught by any backend test, since
   tests mock the environment entirely.
4. **A missing IAM grant on the new export bucket** — `sa-cloud-run`
   had a signing right but no actual read/write permission on the
   bucket itself. Found the same way: a real click, a real
   `AccessDenied`, not a test failure.
5. **Gemini's own tool-selection non-determinism** — the most
   significant finding of the phase. Identical phrasing, fresh
   sessions, identical instructions: one succeeded, one failed.
   Confirmed via direct reproduction, not assumed from a single
   anecdote. Fixed with a deterministic pre-Vertex keyword router,
   extending this project's own established ADR-0026 principle
   (deterministic Python guards over LLM judgment) to a case it had
   never been applied to before — tool *selection* itself, not just
   post-selection parameter validation.

None of these were process failures. They're the expected, healthy
result of a discipline this project has been building all along:
passing tests are necessary, never sufficient, and the only way to
know a feature genuinely works is to make it work against real data,
in the real deployed environment, and look.

## Design decisions that changed mid-phase, and why that's fine

Two real, Coordinator-driven scope changes happened during this phase,
both captured honestly in ADR-0035 rather than smoothed over:

- **15.4b's "latest only, no history" decision was explicitly
  reversed** into 15.4c's history-plus-live-preview, the moment real
  usage (a genuine "Unknown flat" screenshot) proved the narrower
  version wasn't actually sufficient for the dispute-resolution use
  case it was built for.
- **The manual generation/export triggers ("15.3b") were flagged early,
  deferred, then folded into 15.5** once a direct question — "what
  happens if the scheduled job fails?" — made clear that deferring them
  indefinitely wasn't actually acceptable.

Both are recorded as what they are: real discoveries from real
usage, not scope creep and not indecision.

## What's next

Backup & Disaster Recovery is explicitly next after Voice I/O in the
project's own stated sequencing — and this phase's own retrospective
is a direct argument for why it matters: real financial data now
exists in Firestore for the first time, with no backup/PITR strategy
of any kind defined yet. The GCS export built this phase was
deliberately designed as a summary-level feed for an external system,
not a backup mechanism — worth stating plainly so it's never mistaken
for one later.
