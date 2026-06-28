# Phase 9 Retrospective: SlotSense AI Booking Agent

**Status:** Complete
**Duration:** ~6 weeks calendar; ~4 weeks of intensive development (June 2026)
**PR range:** #22 – #40 (19 PRs)
**ADRs added:** 0021 – 0027 (7 architectural decision records)
**Final state:** 364 backend tests at 91.12% coverage; 107 frontend tests; agent live at `/assistant` route on `sport-slot-dev.web.app`

---

## What this phase was

Phase 9 built the **AI booking agent for SlotSense** — a conversational
assistant residents of multi-tenant residential communities can talk to in
natural language to check court availability, make and cancel bookings,
and ask about their usual times. The agent uses Vertex AI Gemini 1.5 Pro
for natural language understanding and function calling, runs on the
existing FastAPI/Cloud Run backend, and shows up to users as a chat
interface at `/assistant` on the React PWA frontend.

The phase was deliberately ambitious. Building a production AI agent that
mutates real state (bookings, cancellations) without falling into the
common failure modes (hallucinated facility IDs, ambiguous time
interpretation, race conditions, leaked tenant data) requires getting a
lot of things right at once. Phase 9 made the architectural commitments
and the operational discipline necessary to do this safely.

It also represented a deliberate choice on the project roadmap: Phase 8
(production hardening — CMEK, VPC service controls, MFA enforcement, pen
testing, DPDP formalization) was originally scheduled before Phase 9 but
was deferred. The agent demonstrated more technical breadth, was more
central to the SlotSense product story, and (honestly) was a more
interesting build than security hardening on a system that wasn't yet in
production. Phase 8 remains a real deliverable for the project's
transition out of dev — but the agent had higher leverage *now*.

This retrospective is written for someone evaluating the project from
outside — a portfolio reader, a hiring manager, a future collaborator —
who wants to understand not just what shipped but how it came together
and what the build process taught. The lessons captured in the
**live-testing rounds** chapter (the second half of this document) were
hard-won and shape the engineering protocol that future projects will
inherit.

---

## What shipped

### Capabilities

The agent supports three core operations through function calling, plus
two read-only utilities and a preference layer:

- `check_availability` — list bookable slots for a facility on a date
- `book` — propose a booking (does not mutate state on its own)
- `cancel` — propose a cancellation (does not mutate state on its own)
- `list_my_bookings` — read-only listing of the user's upcoming bookings
- `get_my_preferences` — return the user's "usual court" for a sport,
  used to fill gaps in ambiguous requests

Mutations (book, cancel) go through a propose-confirm-execute gate:
the agent stores a structured pending action in Redis, returns a
proposal card to the user, and only executes after explicit confirmation
consuming the pending action.

### Architectural commitments

The agent embodies seven architectural commitments, each captured as an
ADR:

- **ADR-0021** establishes the overall agent architecture (function
  calling, two-turn pattern, tenant scoping).
- **ADR-0022** establishes the guardrails (output classifier,
  fail-closed semantics, hallucination prevention).
- **ADR-0023** (Propose-Confirm-Execute Gate) is the foundational
  safety property: the LLM never directly mutates state.
- **ADR-0024** (Output Guard) extends the gate to the display side: a
  separate Vertex call validates that entities referenced in the
  agent's natural-language reply actually exist for the current tenant.
- **ADR-0025** (Pending Action Store) chooses Redis as the storage
  layer for proposals, with TTL-bounded single-use semantics and a
  secondary pointer key supporting type-based lookup.
- **ADR-0026** (Deterministic Python Guards) captures the meta-pattern
  that emerged across multiple slices: where the LLM is unreliable
  (temporal reasoning, exact filtering, quota arithmetic), Python
  code is authoritative.
- **ADR-0027** (Stateful Cancel Disambiguation) extends the pending
  action store with a new action type, enabling multi-step
  conversational flows where the user selects between alternatives.

Together, these ADRs document not just what the agent does but why — and
why alternatives were rejected. They are the architectural reference for
anyone working on the agent in the future.

### User-facing surface

- A chat interface at `/assistant` (route added in slice 5b)
- Proposal cards rendering structured booking/cancellation data with
  Confirm and Cancel buttons
- Per-tab thread persistence via `sessionStorage` (survives navigation,
  resets on tab close — appropriate for v1)
- A peer card on the Facilities page directing residents to the agent
- Suggested-prompt chips on the empty state ("What's my usual court?",
  "Book my usual tennis slot tomorrow", etc.) to anchor first-time users
- Typing indicator while the agent is processing
- PWA-first design: 100dvh, keyboard-aware flex layout, 44pt tap
  targets for touch reliability

### Phase 9 by slice

Phase 9 shipped in 16 slices across 19 pull requests:

| Slice | Scope | PR |
|-------|-------|----|
| 1a | Extract availability + my-bookings into service layer | #23 |
| 1b | Read-only AI query agent (foundation) | #24 |
| 1b.1 | Structlog stdout wiring + date anchor | #25 |
| 1b.2 | `PYTHONUNBUFFERED=1` for Cloud Run log visibility | #26 |
| 2a | Extract `create_booking` into service layer | #27 |
| 2b | Booking via propose-confirm-execute gate | #28 |
| 3a | Extract `cancel_booking` into service layer | #29 |
| 3b | Agent cancel via propose-confirm-execute gate | #30 |
| 4 | Preference-aware replies and gap-filling | #31 |
| 4.1 | System prompt tuning for tool-routing reliability | #32 |
| 5a | `pending_action_summary` on `AgentReply` | #33 |
| 5b | Chat UI for the booking assistant | #34 |
| 6 (6.1+6.2) | Agent polish: AM/PM display + recent_context | #35 |
| 6.3 | Notification fix + SlotSense branding + ambiguous time | #36 |
| 6.4 | Error mapping by code + propose-time quota + cancel differentiation | #37 |
| 6.5 | list_my_bookings limit + AM/PM Python guard + stateful disambig | #38 |
| 6.6 | Per-sport quota at execute time | #39 |
| 6.7 | MyBookings page upcoming filter | #40 |

The first eleven slices (1a through 5b) built the agent's core capabilities.
The last seven (6.1 through 6.7) were discovered through live testing —
the **live-testing rounds**, which the next chapter unpacks in detail.

---

## Live-testing rounds: what they taught us

The first eleven slices of Phase 9 followed an original plan. Each shipped
with hermetic tests passing, CI green, deploy successful, and the new
capability nominally working. Then live testing began — and surfaced bug
after bug.

This wasn't a sign of bad work. The hermetic tests covered what they were
designed to cover. The bugs were of a *different kind* — they emerged from
combinations of realistic data, real LLM behavior, real timezone math, and
real user input patterns that hermetic tests, by their nature of mocking
the LLM and using curated fixtures, couldn't catch.

Each live-testing round became a slice of its own. By slice 6.7, the agent
had absorbed seven rounds of bug discovery and the lessons they produced.
This chapter groups those lessons by *theme* rather than by chronology,
because the real value isn't "here's what slice 6.4 fixed" — it's "here's
what slice 6.4 revealed about how production AI agents fail."

### Lesson 1: Service-layer dispatch unification

When a feature applies to multiple code paths, it must live where all paths
converge — not in the code path it was first written into.

**The story (slice 6.3):** the original notification implementation
(Phase 7.1.3) added `enqueue_notification` calls inside the HTTP router
handler for booking creation. This worked because at that time, booking
creation only happened through one path: the HTTP API.

When the agent was added in slice 2b, it bypassed the router and called
`create_booking` directly as a service function (correctly so — the
agent shouldn't go through HTTP to itself). But the `enqueue_notification`
call stayed in the router. Agent-driven bookings stopped sending
confirmation emails. Nobody noticed during slice 2b's hermetic tests
because the tests didn't assert on notification side effects. Nobody
noticed in slice 2b's live testing because the live test didn't check
the user's inbox.

It was discovered three slices later (slice 6.3), in a multi-pass live
test where the absence of confirmation emails finally registered as
strange. The fix was small in code terms — move the `enqueue_notification`
call into `services/bookings.py::create_booking` — but the lesson was
larger:

**Anything that should apply to all callers of a function must live in
the function, not above it.** If you find yourself thinking "the agent
path needs this too," ask whether the feature belongs in the service
layer where both paths can reach it. The router is a *thin presentation
layer*; cross-cutting concerns (notifications, audit logs, quota
checks) belong below it.

This lesson surfaced again in slice 6.6 (per-sport quota): the
execute-time quota check in `create_booking_with_quota` was missing a
sport filter, while the propose-time quota check (added later in slice
6.4b) had it. The two checks disagreed — proposals succeeded that
later failed at execute. Same fundamental pattern: a check that should
apply uniformly across all callers had drifted between layers.

### Lesson 2: Defense in depth for safety-critical checks

When a check enforces a real safety property, do it at multiple layers.
The propose-confirm-execute gate inherits this discipline; the polish
rounds extended it.

**The story (slices 6.4b and 6.6):** the per-sport per-day quota is a
real product constraint. A user with quota=1 for tennis should not be
able to book two tennis courts on the same day. Originally, this was
enforced in one place: the Firestore transaction in
`create_booking_with_quota`.

The problem: the agent's propose-confirm-execute flow goes
propose → display proposal card to user → user confirms → execute.
If the only quota check was at execute time, a user could see a
proposal card promising a booking that would fail when they clicked
Confirm. This happened during slice 6.4 live testing — the user got an
"already booked" message right after confirming a proposal, which was
confusing and felt like the system was lying.

The fix (slice 6.4b): add a *propose-time* quota check in
`_dispatch_book`. It counts the user's confirmed same-sport same-day
bookings and refuses the proposal at propose time if the limit is
already reached. The execute-time check stays in place — it's the
correctness backstop. The propose-time check is the UX layer that
prevents the user from confirming something that would fail.

Two layers, both required:

- **Propose-time** check: best-effort, UX-focused. Reads policy and
  counts current bookings. Catches the common case before the user
  commits.
- **Execute-time** check (slice 6.6): atomic inside the Firestore
  transaction. Catches the race where a user gains a booking between
  propose and confirm. Authoritative.

This pattern (UX-focused early check + correctness-focused late check)
extends naturally: it's the same as `is_cancellable` for the cancel
flow, and the same as facility availability checks. Wherever a real
constraint exists, defense in depth means checking it both at the
moment the user expresses intent and at the moment the system commits
state.

**The corollary that bit us in slice 6.6:** when adding the
propose-time check (slice 6.4b), I correctly counted by sport. When
the older execute-time check was inspected later (slice 6.6), it was
counting by *date only* — not by sport. Bug. The fix required passing
sport and facilities into the Firestore transaction. The deeper lesson:
when adding a defense-in-depth layer, verify that the existing layers
already enforce what you think they enforce. They may not.

### Lesson 3: LLM unreliability ceilings → Python guards

LLMs are excellent at intent extraction. They are unreliable at:
temporal reasoning, exact filtering, arithmetic, and edge-case logic.
Building a production agent means knowing which is which and using
deterministic code where unreliability is unacceptable.

**The story (slice 6.5b):** a user typed "book tennis at 09" at around
6 PM. The LLM interpreted "09" as 09:00 — 9 AM that same day — which
was nine hours in the past. The agent dutifully tried to book a slot
that didn't exist (or rather, existed only in history) and produced an
unhelpful "that slot isn't available: PAST" message.

The instinct is to fix this in the prompt: "If the user says a time
and AM that time is in the past today, interpret as PM." We tried this
(slice 6.3's ambiguous-time rule). It helped for some cases but the
model still got it wrong roughly 10% of the time.

This isn't a prompt engineering problem. It's a *capability ceiling*.
The LLM doesn't have reliable temporal reasoning. Adding more prompt
rules doesn't fix it because the model isn't *understanding the rule
incorrectly* — it's failing to apply correct rules consistently across
varied input.

The fix (slice 6.5b): a **Python guard** in `_dispatch_book`. Before
the proposal is stored, the code checks: if the start time's hour is
less than 12 and the resulting datetime is in the past (in the tenant
timezone), advance the start by 12 hours and log the adjustment. The
LLM still does the intent extraction; the Python is authoritative for
the temporal correction.

This pattern recurs across the agent's design:

- **Cancel candidate filtering** is a pure Python function
  (`_filter_cancel_candidates`). The LLM never selects which booking
  to cancel; it identifies the *sport and time hint*, and Python does
  the rest.
- **Quota counting** is Python (in two places now, propose-time and
  execute-time). The LLM never tries to do arithmetic over the user's
  bookings.
- **Disambiguation matching** (slice 6.5c) is Python substring matching
  against stored candidates. The LLM never tries to interpret "the
  first one" or "the 19:00 one" against an unknown list.

The principle, formalized in ADR-0026: **let the LLM do natural
language understanding; let Python do anything that needs to be
deterministically correct.** Wherever the cost of LLM unreliability is
high (a wrong booking, a wrong cancellation, a wrong quota count),
there's a Python guard. The prompt does the first 90%; the Python
guard catches the remaining 10% where LLM behavior would otherwise
slip through.

### Lesson 4: State management for multi-step conversational flows

A conversation that requires the user to "pick one" between alternatives
needs state. Stateless implementations sound elegant but break in
predictable ways.

**The story (slice 6.5c):** when a user said "cancel my tennis" and had
two upcoming tennis bookings, the agent listed them and asked the user
to specify which one. The original implementation (slice 3b) was
stateless — the agent had no memory of the disambiguation. The user's
next message was treated as a fresh query.

This produced infinite loops. The user typed "1" (referring to the
list). Agent: fresh query, "I don't understand 1." User typed "the
19:00 one." Agent: fresh query, "What would you like me to do?" User
typed "2026-06-28 at 19:00" verbatim from the agent's list. Agent: the
LLM re-extracted the cancel intent, re-ran the disambiguation, showed
the same list again.

The fix (slice 6.5c): when entering the disambiguation branch, store a
`cancel_disambiguation` pending action with the candidate list. On the
next user message — *before* calling the LLM — check for an active
disambiguation. If the user's message contains exactly one candidate's
date and start time as substrings, treat it as a selection and route
directly to the cancel propose flow. If zero or multiple match, fall
through to normal LLM processing.

This required extending the pending action store (ADR-0025) with a new
action type and a secondary pointer key for type-based lookup. The
infrastructure was already there for the propose-confirm-execute flow;
extending it for disambiguation didn't require new infrastructure,
just a new pattern of use. Captured as ADR-0027.

The conservative matching rule (date AND start both required, exactly
one candidate matches) is deliberately biased toward false negatives.
A false positive would cancel the wrong booking — high cost. A false
negative just makes the user type more specifically — low cost. The
matching is a *guarded* path; the LLM fall-through is the *safe*
default.

### Lesson 5: Pagination + filter interactions

When a paginated query is followed by a presentation-layer filter, the
filter sees only the page — not the full dataset. If the page is
ordered by something other than the filter criterion, future data may
be invisible.

**The story (slice 6.5a):** when the agent dispatched
`list_my_bookings`, it called the service with `limit=10` (the LLM's
default, capped at 20). The service queried Firestore ordered by
document ID. The agent then filtered the results in Python to
"upcoming + confirmed" (date ≥ today, status === "confirmed").

In hermetic tests with curated fixtures, this worked perfectly. In live
testing with realistic data, a user with 15+ past bookings (across the
project's history) saw a curious behavior: "my bookings" returned "you
have no upcoming bookings" even immediately after confirming a new
booking.

The diagnosis took inspecting the `agent_bookings_dispatched`
structured logs to see the underlying count. The query was returning 10
results — all 10 were past confirmed bookings (because document IDs
encoded facility+date+start, and past bookings sorted first
alphabetically). The filter then correctly removed them, producing an
empty list. The user's newly-confirmed booking *existed* in Firestore
but was at position 25 in the document-ID ordering, never fetched.

The fix (slice 6.5a): change the agent's `list_my_bookings` dispatch
to use `limit=100`. The underlying service stays the same; only the
agent's call site changes. The presentation-layer filter now sees
enough rows to find the user's future bookings.

The deeper lesson: **a presentation-layer filter requires that the
underlying query return enough rows for the filter to find what it's
looking for.** If the query returns the "wrong page" relative to the
filter's needs, results disappear from view. Two principled fixes
exist:

1. Change the query ordering so the relevant rows come first (requires
   a Firestore composite index — more operational overhead)
2. Fetch more rows so the filter sees the relevant ones (what we did —
   no schema change, no new index)

The retrospective on this isn't that the choice was wrong; it's that
the *interaction* between pagination and filtering wasn't surfaced by
the hermetic tests. The tests mocked the service to return curated
items; the realistic-data pattern (many past + few future) never
appeared in the test fixtures.

A note on test design: hermetic tests work best when fixtures cover the
"happy path" and the "obvious failure modes." Realistic-data patterns
— what a real user's data looks like after months of use — are an
emergent property of live systems and rarely appear in fixtures unless
specifically engineered to. This is one of the irreducible reasons
live testing matters.

### Lesson 6: Error mapping by semantic code, not transport code

When the same transport-level identifier (HTTP status) can mean
multiple distinct application-level conditions, the error handler must
discriminate on the application-level code — not the transport.

**The story (slice 6.4a):** the agent's confirm-time error handler
originally mapped errors by HTTP status:

```python
if exc.status_code == 409:
    return "That slot was just taken — would you like me to check other times?"
```

But `create_booking` raises three different `ApiError` codes that all
share status 409:

- `SLOT_CONTENDED` — another user is currently booking this slot
- `BOOKING_QUOTA_EXCEEDED` — the user has reached their per-sport
  per-day limit
- `ALREADY_BOOKED` — the slot is already booked

The status-only handler collapsed all three into "slot was just taken,"
which was misleading for the quota case (the slot is fine; the user's
limit is the issue) and incorrect for the already-booked case (the
slot isn't *contended*; it's *taken*).

A user hitting their quota got told to "check other times" and went
into a fruitless retry loop. A user trying to book a slot they already
had got the same confusing message.

The fix (slice 6.4a): map on `exc.code`, not `exc.status_code`. Seven
distinct branches for the seven known codes, each producing a tailored
message. `BOOKING_QUOTA_EXCEEDED` includes the sport name.
`ALREADY_BOOKED` includes the facility, date, and time. Unknown codes
log a structured warning and fall through to a generic message.

The deeper lesson: **the transport code (HTTP status) is for clients
to know how to handle the response shape. The application code is for
the application to know what actually happened.** Mapping
application-level user messages on transport-level codes loses
information that the application has and the user needs.

This isn't novel — the project already had this pattern for the
non-agent surfaces via `error_codes.py` and the frontend's
`messageForCode`. The agent was a late adopter. But the bug surfaced
the principle clearly enough to be worth capturing.

### Lesson 7: Frontend-backend data alignment

When two surfaces show "the same data" but compute it differently, the
user is confused before any other concern matters.

**The story (slice 6.7):** the agent's `list_my_bookings` dispatch
filtered to upcoming + confirmed (slice 6.1b). The frontend's
`MyBookings.tsx` page filtered to confirmed only — past bookings
remained visible with a "Cancellation closed" tag.

For most of Phase 9 this was fine because the live-test user didn't
have many past bookings. By slice 6.7 the accumulated history meant
the page showed 6 past bookings cluttering the view above the 2
relevant upcoming ones. The agent said "you have 2 upcoming bookings."
The page showed 8. The user was understandably confused about which
was correct.

The fix (slice 6.7): align the frontend with the agent. Filter
`MyBookings.tsx` to `b.status === "confirmed" && b.date >= today`.
The two surfaces now agree.

This is the smallest of the live-testing slices in terms of code
change — about 20 lines. But the lesson is large: **when the same
data appears in multiple surfaces, the user's mental model is
"this is one thing, shown two ways."** Divergence between the
surfaces breaks that model. Either surface might be "correct" in some
sense, but the user can't tell which.

The discipline going forward: when a new surface for an existing data
type is added, explicitly verify that its filtering, sorting, and
formatting match the canonical surface — or that the divergence is
deliberate and surfaced in the UX.

---

## Protocol-level lessons (consolidated)

The live-testing rounds chapter taught lessons about *building agents*.
Underneath them are lessons about *engineering protocol* — about how the
work itself should be organized to surface these problems early and
handle them well. These lessons feed into the Three-Agent Engineering
Protocol (the private methodology document maintained separately from
this project repo), but they belong in the project retrospective too
because they emerged from Phase 9 specifically.

**1. Hermetic tests are necessary but not sufficient.** They cover
correctness for the inputs the engineer thinks to test. They do not cover
the emergent failure modes of real LLM behavior, realistic data volumes,
timezone interactions across instances, and user-input patterns. Live
testing is not optional; it's where a different class of bugs lives.

**2. Live testing has a discoverable cadence.** Phase 9 settled into a
pattern: ship a slice, declare done, live-test in the browser, find
2-5 issues per round. Some rounds revealed real correctness bugs
(slices 6.3, 6.4, 6.5, 6.6); others surfaced UX rough edges (slices
6.1, 6.2, 6.7). Treating each round as a planned step — rather than as
"oops more bugs" — made the pattern manageable.

**3. Slice cadence held under sustained pressure.** Each slice was
scoped to one PR, with hermetic tests, CI gates, branch protection,
and live verification before merge. The cadence didn't slow over the
seven live-testing rounds. This validates the slice-based development
discipline as a sustainable rhythm, not just an early-phase one.

**4. The propose-confirm-execute gate carried the safety properties.**
Across 19 PRs and 16 slices, the foundational gate (ADR-0023) absorbed
every new behavior without breaking. New features (preferences,
disambiguation, error mapping, propose-time quota) layered on top of
the gate; they extended its surface without violating its semantics.
This is what good foundational architecture looks like — it carries
weight without needing to be revisited.

**5. Service-layer is the right place for cross-cutting concerns.**
Slice 6.3 surfaced this for notifications; slice 6.6 surfaced it for
quota. The principle: if a behavior applies to all callers of a
function, it lives in the function. The HTTP router is for transport
concerns (auth, request shaping); the service layer is for application
concerns (audit, notifications, policy enforcement).

**6. Defense in depth for safety-critical checks.** Propose-time and
execute-time quota checks together cover the UX (no proposal you can't
fulfill) and the correctness (atomic enforcement under contention).
Both layers, with the same semantics, agreeing on the answer.

**7. LLM capability ceilings are real and don't yield to prompt
engineering alone.** Temporal reasoning, exact filtering, arithmetic,
edge cases — when the LLM is unreliable on these, more prompt rules
don't fix it. The principled response is to do that work in
deterministic code (ADR-0026). The LLM does what it's good at (intent
extraction, NLU); Python does what it has to be right about.

**8. Multi-step conversational flows need server-side state.** Stateless
disambiguation sounds appealing but breaks in predictable ways. The
state must live somewhere with the right TTL, scope, and access
semantics. Reusing existing infrastructure (the pending action store
from ADR-0025) is preferable to inventing new infrastructure.

**9. Error mapping should be on application codes, not transport
codes.** When the application produces multiple distinct conditions
that share a transport identifier, the handler must discriminate at
the application level. This applies to internal callers (the agent
calling the booking service) as much as to external clients (the
frontend calling the API).

**10. Pagination and presentation-layer filters interact in
non-obvious ways.** If the filter assumes the query is comprehensive,
and the query is paginated, the assumption can silently fail when
realistic data exceeds the page size. Either the filter has to be
moved into the query, or the query has to fetch enough rows to make
the filter's assumption valid.

**11. Surface alignment matters.** When the same data appears in
multiple places — page, agent, notification — the user's mental model
treats it as one thing shown multiple ways. Divergence between the
surfaces is a worse user experience than either surface alone, because
the user can't tell which is correct.

These eleven lessons are now part of the engineering protocol applied
to subsequent projects. They were paid for in real time during Phase 9
live testing; they remain valuable for any future AI agent build, and
for production systems generally.

---

## Metrics

| Metric | Value |
|--------|-------|
| Total PRs in Phase 9 | 19 (#22 – #40) |
| Slices delivered | 16 |
| Live-testing rounds | 7 (slices 6.1 – 6.7) |
| ADRs added | 7 (0021 – 0027) |
| Backend test count | 364 (from ~190 entering Phase 9) |
| Backend test coverage | 91.12% (well above 90% gate) |
| Frontend test count | 107 (chat UI tests added) |
| Coverage non-negotiable raised | 80% → 90% during Phase 9 |
| Tools exposed via function calling | 5 |
| Vertex AI calls per user turn (typical) | 2 (intent + output classifier) |
| Pending action TTL | 5 minutes |
| Cloud Run cold-start latency | acceptable for chat UX (~200-500ms first turn) |
| Average agent latency (warm) | ~1-2s per turn |

---

## What's deferred

The following capabilities were considered and deliberately deferred. None
are blockers for v1; each represents a real future enhancement.

**Voice mode.** A constrained classifier for voice-driven booking flow
with fail-closed semantics on UNCLEAR audio. Probable Phase 10 candidate.

**Multi-turn conversation history.** The agent currently has lightweight
recent-context (slice 6.2) but no real conversation history. A Redis-backed
or Firestore-backed history with token-window management is a meaningful
expansion. Probable Phase 10+ work.

**Server-persisted chat history.** sessionStorage gives per-tab persistence;
real cross-device continuity would require backend-side conversation
records. Pairs naturally with the multi-turn history work.

**Push notifications via PWA.** Booking confirmations could deliver via
push instead of (or in addition to) email. Requires service-worker
integration and per-tenant push credential management.

**Tappable disambiguation buttons.** Currently the user disambiguates by
typing the date+time matching the agent's list. Buttons rendering each
candidate would improve UX. Adds frontend complexity but is well-scoped
(~60-80 lines).

**Multilingual affirmative parsing.** Hindi (haan, theek hai, ji), Telugu
(avunu, sare, kaadu) recognition for confirmation. Naturally pairs with
voice mode.

**24-hour → 12-hour in agent's natural-language replies.** Structured
fields in proposal cards already render 12-hour AM/PM (slice 6.1a). The
agent's narrative replies still use 24-hour internally. Cosmetic.

**Fuzzy facility name matching (Levenshtein or similar).** Only worth
implementing if usage data shows residents commonly mistype facility
names. Currently no signal warrants it.

**MyBookings "Show past bookings" toggle.** The current filter is binary;
some users may want history. Backlog if requested.

A broader category: most of the deferred work is *user-facing polish*
on a system whose core architecture is solid. The agent's safety
properties (propose-confirm-execute gate, output guard, deterministic
guards) hold regardless of which surface polish gets added.

---

## Honest reflections

A few things from this phase that are worth being explicit about, in the
spirit of honest retrospective writing rather than promotional retrospective
writing.

**The polish rounds caught bugs that would have shipped.** Without the
discipline of live-testing each slice and treating discoveries as their
own slices, the agent would have shipped with: a notification regression,
misleading error messages, infinite-loop disambiguation, a wrong-by-day-not-
by-sport quota, and a `list_my_bookings` that confidently reported "no
upcoming bookings" to users who had several. None of these were caught by
hermetic tests. All of them would have shipped without the live-testing
discipline.

**The architecture held.** Across seven live-testing rounds adding real
behavior to the agent, the foundational propose-confirm-execute gate
(ADR-0023) absorbed every change without breaking. Every new behavior was
expressible as either an additional guard before the gate (the AM/PM
guard, the propose-time quota check) or as an extension of the gate's
storage layer (stateful disambiguation). The pattern was designed early
and proved load-bearing.

**The "is this an ADR or a bug fix?" judgment matters.** During the
docs ceremony for Phase 9 closure, three candidate ADRs were initially
drafted for the polish-round work: error mapping by code, stateful
disambiguation, and per-sport quota filtering. Two of these (error
mapping and per-sport quota) were ultimately rejected as ADRs and moved
to this retrospective as bug-fix narratives. They weren't decisions a
different team would deliberately deliberate; they were corrections of
the implementation to match the policy's intent. Only the stateful
disambiguation work was a genuine architectural decision (where to put
the state — store extension vs. new infrastructure vs. client-side).
This is the discipline of what an ADR is *for*: a decision worth
encoding, not just a thing that happened.

**Some things would be done differently with hindsight.** The agent's
natural-language replies still use 24-hour time; structured fields use
12-hour. That divergence would have been worth resolving earlier. The
agent's chat UI is per-tab session-scoped; cross-device persistence
would have been worth scoping at slice 5b rather than deferring. The
output guard is fail-closed but doesn't differentiate "classifier
errored" from "classifier said unsafe"; that differentiation would be
useful for observability. None of these are blockers — they're just
honest acknowledgments that decisions made under time pressure are
sometimes worth revisiting later.

**The build was meaningfully helped by clear scope.** Phase 9's
charter (build an AI agent for SlotSense, with multi-tenant scoping,
safe mutations, and a chat UI) was specific enough to anchor decisions
and broad enough to encompass the seven live-testing rounds. Looser
scope would have been worse — the seven rounds could have been seven
different projects' worth of feature creep. Tighter scope would have
been worse too — slice 4 (preferences) and slice 5b (chat UI) both
emerged as essential mid-build, and a tighter charter would have
deferred them.

---

## References

### Pull requests

- #22: ADRs 0021 + 0022 (Phase 9 charter)
- #23: Slice 1a — service-layer extraction
- #24: Slice 1b — read-only agent foundation
- #25: Slice 1b.1 — logging diagnostics
- #26: Slice 1b.2 — `PYTHONUNBUFFERED`
- #27: Slice 2a — create_booking extraction
- #28: Slice 2b — propose-confirm-execute booking
- #29: Slice 3a — cancel_booking extraction
- #30: Slice 3b — propose-confirm-execute cancel
- #31: Slice 4 — preference-aware replies
- #32: Slice 4.1 — system prompt tuning
- #33: Slice 5a — pending_action_summary
- #34: Slice 5b — chat UI
- #35: Slices 6.1 + 6.2 — agent polish
- #36: Slice 6.3 — notification fix + branding
- #37: Slice 6.4 — error mapping + propose-time quota
- #38: Slice 6.5 — limit fix + AM/PM guard + stateful disambig
- #39: Slice 6.6 — per-sport quota at execute time
- #40: Slice 6.7 — MyBookings upcoming filter

### Phase 9 ADRs

- **ADR-0021** — AI Booking Agent Architecture
- **ADR-0022** — AI Booking Agent Guardrails
- **ADR-0023** — Propose-Confirm-Execute Gate
- **ADR-0024** — Output Guard for LLM Hallucination Detection
- **ADR-0025** — Pending Action Store (Redis-backed, single-use, secondary pointer)
- **ADR-0026** — Deterministic Python Guards over LLM Judgment
- **ADR-0027** — Stateful Cancel Disambiguation

### Related documents

- `docs/REQUIREMENTS.md` — canonical project requirements, reconciled
  during Phase 9 closure (PR #41)
- `docs/SLOTSENSE_ARTICLE.md` — publishable portfolio article on
  chandraailabs.com
- `CHANGELOG.md` — slice-level changes, fully detailed for Phase 9

### Engineering protocol

The Three-Agent Engineering Protocol — the methodology used to build
this project — is maintained as a private document outside this repo.
The eleven protocol-level lessons captured above feed into the
protocol's v3 revision (a separate work item).

---

## Document history

- **2026-06-28:** Initial drafting and commit as part of Phase 9
  administrative closure (docs Session A). Author: Chandra Nakkalakunta
  with AI assistance (Claude Opus 4.7).
