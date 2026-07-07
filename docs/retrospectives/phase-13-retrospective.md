# Phase 13 Retrospective: Entity Lifecycle Management

**Status:** Complete
**Duration:** ~2 days (July 5-7, 2026)
**PR range:** #94 – #104 (10 PRs, plus 3 direct-to-main bookkeeping commits)
**ADRs added/revised:** ADR-0034 (new, revised twice during the phase)
**Final state:** 410 backend tests at 91% coverage; 314 frontend tests; deletion, deactivation, and permanent-delete now correctly implemented for residents, tenant-admins, tenant-facilities, and tenants themselves

---

## What this phase was

Phase 13 set out to answer a question the project had never actually
answered: when a user, facility, or tenant needs to go away, what
actually happens to their data? Deactivation existed for users since
Phase 5 (ADR-0017), but nothing else in the lifecycle — facility
removal, permanent deletion, tenant wind-down — had ever been properly
designed or built. The Coordinator's framing at the start was blunt and
correct: "delete was never considered and implemented properly, hence I
considered this phase."

The phase's shape changed substantially partway through. It started as
a narrow bug investigation (a reported "deactivate button not working")
and grew, through direct evidence rather than assumption, into a full
redesign of the deletion model: Deactivate and Delete became two
independent, always-available actions for every entity type, instead of
Deactivate-then-a-slow-admin-script-purge. That redesign was driven by a
real incident, not a hypothetical: a deactivated resident's Firebase
Auth account silently blocked re-registration of their own email, with
no UI path to fix it — the exact "unrecoverable stuck state" the
Coordinator wanted to avoid going forward.

This phase also marked a turning point in how Strategist/Worker prompts
get written. A genuine process failure mid-phase — a prompt that skipped
design discussion and shipped with missing template sections — triggered
a direct, unflinching review of what went wrong, and the engineering
protocol itself was revised twice during the phase (v3.1 → v3.5) to
close the gaps that failure exposed, then again to absorb a
comprehensively rewritten version the Coordinator brought in independently,
explicitly because "this update happened because of those continuous
ping-pongs."

## What shipped

### Entity lifecycle, end to end

- **13.0** — Root-caused and fixed a real bug: deactivating a user never
  set the `active` field the frontend's Active-users filter actually
  checked, so deactivated users never left the list. Backend logic was
  otherwise ADR-0017-compliant.
- **13.1** — Wired ADR-0011 audit logging into `deactivate_user` (a real
  compliance gap against already-accepted design). While investigating
  facility deactivation, discovered `cancel_booking` sent **no
  notification on any cancellation, ever** — fixed for all cancellations,
  not just the facility-triggered case that surfaced it, plus a
  `force`/`cancelled_by_override` mechanism so administrative
  cancellations aren't blocked by the resident-protecting cancellation
  buffer.
- **13.2** — Built genuine permanent delete for residents and
  tenant-admins (ADR-0034 §2): a real `DELETE .../permanent` route,
  independent of Deactivate, with a type-to-confirm UI safeguard
  (`ConfirmDialog` gained a reusable `confirmationPhrase` prop).
- **13.3** — A live incident (a stuck, unrecoverable deactivated account)
  drove a real design reversal: facility "Remove" now permanently
  deletes rather than soft-deactivates, and the Users page's Deactivate
  button was hidden entirely (backend untouched, kept for a future
  proper Deactivate+Reactivate design) to stop new stuck accounts from
  being created.
- **13.4** — The phase's highest-risk work: tenant-level cascade delete,
  platform-admin only, using Firestore's `recursive_delete` plus
  independent Firebase Auth cleanup, with a deletion-record stub
  deliberately written to a new top-level collection
  (`platform_deletion_log`) so the audit trail survives the cascade it
  documents. Reviewed line-by-line before merge and verified live
  against real Firestore state after execution — not taken on the
  Worker's report alone.
- **13.5** — Closed out a wide batch of real, user-reported gaps: search
  on the Users and Tenant lists, tenant-admin visibility on the
  platform-admin screen (previously invisible without a circular
  admin-login-to-see-admins problem), a `/version` build-identifier
  endpoint, a shared temp-password modal (previously appended to the
  bottom of a potentially long page), a styled CSV file input, and —
  significantly — the bulk-import endpoint's first-ever test coverage,
  including a partial-failure case and a 500-row limit nobody had asked
  for but the tests caught was worth having.
- **13.7** — Fixed two real production bugs found through live testing,
  not planned work: the bare apex domain (`slotsense.chandraailabs.com`)
  had no DNS record or Load Balancer routing at all, and — once fixed —
  exposed a second bug where signing in from the wrong subdomain (or the
  apex) succeeded silently instead of redirecting to the correct tenant.
  Both collapsed into one unified fix in `AuthContext`.
- **13.8** — A Firebase-specific timing bug: custom claims propagate on
  the *next* token refresh, not immediately, so a fresh sign-in could
  carry a stale token missing `tenant_id`/`tenant_slug`/`role`, causing
  the first API call to 401 with no recovery UI — a silent, permanent
  blank screen. Fixed with a forced refresh post-sign-in and the
  codebase's first-ever error-recovery UI for this class of failure.

### Found and fixed outside the phase's original scope, but before closing it

- **Booking Policies form never fetched saved values** — hardcoded
  `useState` defaults with no `GET /tenant/policies` route ever built.
  Root-caused via direct Firestore inspection proving the *save* worked
  and the *display* never had a way to read it back. Not a regression —
  likely broken since the feature was first built, masked because the
  hardcoded defaults happened to match a new tenant's initial values.
- **13.5's facility mobile fix was necessary but not sufficient.**
  Removing `truncate` stopped names being cut off, but live-device
  testing after "closure" revealed the real, deeper bug underneath:
  `ListRow` (the shared card component used by Facilities, the
  platform-admin Tenant List, and My Bookings) is unconditionally a
  row layout with the action area at a fixed width — with three action
  buttons (Edit/Clone/Remove), the remaining space for the facility
  name was narrow enough to wrap one word per line, an outcome the
  Coordinator correctly refused to accept as client-presentable. The
  fix was applied to `ListRow` itself, not just Facilities' usage of
  it, closing the same latent risk in its other two consumers for the
  same effort. Worth recording plainly: the first fix was verified
  (build-id ancestry, live screenshot) and still turned out to be
  incomplete — "verified deployed" and "actually solves the problem"
  are not always the same question, and this phase needed a second,
  harder look to tell them apart.
- **Terraform drift** — the apex host_rule (from 13.7a) had been applied
  live but never committed to git; a clean `terraform plan` would have
  silently proposed reverting production infrastructure. Caught during
  phase closeout, not before.
- **`/version`'s own Load Balancer routing** — added in 13.5, but never
  added to the LB's path_matcher, so the endpoint built specifically to
  answer "is my fix actually deployed?" was itself unreachable through
  the real domain. Found while trying to use it for exactly that
  purpose.

### Deliberately deferred

- **13.6 (CDN cache-fill investigation)** — a real, reproduced-once
  incident (a cold subdomain path served a 0-byte response after the
  apex-redirect flow) with no confirmed root cause after investigation —
  every test run showed no `Age` header, undermining the working "CDN
  caching" theory without disproving it either. Coordinator's call: not
  currently recurring, not worth continued investigation time against an
  unconfirmed cause. Backlogged, to be revisited if it recurs with
  better evidence available at that time.
- **Deactivate/Reactivate as a proper paired feature** — the Coordinator
  explicitly chose Delete-only simplicity over building Reactivate now,
  accepting that some administrative flexibility (temporarily disabling
  a resident without losing their history) is deferred, not lost.

## Process and protocol evolution

This phase is the reason the engineering protocol looks the way it does
now. Two things happened, worth recording honestly:

1. **A real prompt-quality failure.** Mid-phase, a Worker prompt was
   written directly from an investigation thread, skipping the
   design-discussion-then-approval gate the protocol already specified,
   and shipped without several mandatory template sections (CHANGELOG
   step, STEP FINAL, ERROR HANDLING, the commit trailer). The Coordinator
   caught it by direct comparison against a properly-formed reference
   prompt and asked, correctly, "was the protocol not clear about it?"
   The honest answer was no — the protocol was clear; the gate was
   skipped, not ambiguous. This is recorded here rather than smoothed
   over because the fix that followed (a literal, non-negotiable
   pre-send checklist) only has value if the failure that motivated it
   is remembered accurately.

2. **Continuous back-and-forth as its own root cause.** Later in the
   phase, after several rounds of single-diagnostic-command,
   wait-for-output, ask-the-next-command exchanges, the Coordinator
   brought in an independently-authored, substantially rewritten
   protocol (v3.4) specifically to reduce that friction — consolidated
   asks, text-based verification over screenshots, proactive
   recommendation, token-discipline batching. It was adopted in full,
   the same day, immediately changing how the remainder of the phase's
   diagnostics were conducted (e.g., the multi-command consolidated
   batches used for the LB apex investigation and the policy/facility
   closeout diagnosis).

Both are now embedded as durable protocol sections (§0 self-
certification, §2.1a scoping, §8 token discipline) and as a new §5.30
lesson (a shared-interface change ripples beyond a prompt's named file
scope, and a passing test suite does not prove a project type-checks
cleanly) drawn directly from a real CI failure on PR #100.

## ADR-0034: a design that changed twice, honestly

ADR-0034 is worth calling out specifically because it was revised twice
in one phase, each time for a real reason surfaced by evidence, not
indecision:

- **v1 (2026-07-05):** facility lifecycle (adapted 3-stage pattern) +
  resident-initiated DPDP erasure via full delete.
- **v2 (2026-07-06):** generalized to a direct, independent Delete
  action for every entity type — residents, tenant-admins, *and*
  tenants — after the Coordinator's stated philosophy ("if user is
  deleted, just delete complete data... let's have a simple clean
  solution") made the original deactivate-then-slow-purge model
  unnecessarily complex. This decision also retroactively made
  ADR-0017's never-implemented 90-day PURGE script moot for the
  on-demand case.
- **v3 (13.3, same week):** the facility-specific decision within the
  ADR was further simplified from "deactivate + eventual PURGED stage"
  to "delete only," once the live stuck-account incident made clear
  that deactivate-without-reactivate was actively harmful, not just
  incomplete. The original 3-stage facility design is preserved in the
  ADR only as historical record, explicitly marked as superseded.

ADR-0034 was accepted at phase close (2026-07-07), once all three
decisions were fully built and verified live — not merged-and-assumed,
independently confirmed against real production state (Firestore
inspection for the delete behavior, `build_id` commit-ancestry for the
deploy itself).

## What's next

Phase 13 closes with two new phases already scoped and locked in
sequence, deliberately not started yet:

- **Daily Booking Overview** (tenant-admin, per-day grid across all
  facilities, accessible keyboard-reachable tooltips showing resident
  name/email) — real operational value (dispute resolution, utilization
  visibility) identified mid-phase, correctly kept out of Phase 13
  since it has no lifecycle angle.
- **Voice input/output for the AI Booking Assistant** (speech-to-text,
  translate-at-the-edges design so the Phase 9 agent itself needs zero
  changes, translate back, text-to-speech) — scoped with real technical
  trade-offs (iOS Safari's lack of native speech recognition support
  drove the choice of server-side Cloud STT over the free
  browser-native option) surfaced and decided before any design work
  began.
