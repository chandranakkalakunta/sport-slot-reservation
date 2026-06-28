# ADR-0024: Output Guard for LLM Hallucination Detection

## Status

Accepted (Phase 9, slice 1b)

## Context

The SlotSense AI Booking Agent uses Vertex AI Gemini 1.5 Pro to generate
natural-language replies in response to user queries. While the model
handles intent extraction and function calling well, it has a documented
failure mode of *hallucinating identifiers* — referring to facility IDs,
booking IDs, or facility names that don't exist for the current tenant.

Examples observed during development:

- User: "What courts are available?" → LLM reply: "We have Tennis Court 5"
  (Tennis Court 5 doesn't exist for this tenant; only Tennis Court 1 and 2 do)
- User: "My bookings" → LLM reply lists a "Cricket Pitch" booking
  (no cricket facilities in this tenant)
- User: "Cancel my badminton booking" → LLM produces a booking_id that
  doesn't match any real booking

The propose-confirm-execute gate (ADR-0023) prevents hallucinated actions
from being executed — but the user still sees the hallucinated text in
the agent's reply, which damages trust and creates confusion.

**Requirements:**

1. Detect when the agent's reply references entities (facility IDs,
   facility names, booking IDs) that don't exist for the current tenant
2. Block such replies from reaching the user
3. Fail closed — if validation cannot complete, do not show the reply
4. Add minimal latency to the agent loop
5. Per-tenant scope (validation is against this tenant's facilities and
   this user's bookings, not globally)

## Options Considered

### Option A — No Guard

Trust the LLM's output. Rely solely on the propose-confirm-execute gate
(ADR-0023) to prevent harm from execution; accept that users may see
hallucinated text in agent replies.

**Strengths:**
- Lowest latency
- Simplest implementation
- No extra LLM cost

**Weaknesses:**
- Damages user trust when hallucinated facility names appear in replies
- "What courts are available?" → reply lists fictional courts → user
  tries to book one → confusion about why the booking proposal mentions
  a different facility
- The gate prevents *execution* of bad state, but doesn't prevent the
  user from seeing the LLM's confabulation

### Option B — Schema Validation Only

Validate that the LLM's output matches the expected response schema
(e.g., is the function call's facility_id a string in the right format?).

**Strengths:**
- Fast (deterministic check, no LLM call)
- Catches structural malformation

**Weaknesses:**
- Schema-valid does not mean semantically valid: `facility_id =
  "f-cricket-pitch"` is structurally fine but might not exist for the
  tenant
- Doesn't catch hallucinated facility names in the natural-language
  response text (which is what users see)

### Option C — Output Classifier with Fail-Closed *(chosen)*

After the LLM produces a reply, a separate Vertex call (the "output
classifier") evaluates whether the reply references only entities that
exist for the current tenant. If it doesn't, or if classification fails
for any reason, the reply is suppressed and a safe fallback message is
shown ("I'm sorry, I can only help with facility availability and
booking queries. Please try rephrasing your question.").

**Strengths:**
- Catches both structural and semantic hallucinations
- The classifier prompt explicitly lists valid facility IDs and user's
  bookings as context, so it can validate against real data
- Fail-closed semantics: when in doubt, suppress
- Separate Vertex call means the classifier prompt can be tuned
  independently of the agent prompt

**Weaknesses:**
- Adds latency (one extra Vertex call per reply that references entities)
- Adds Vertex AI cost (roughly 2x token usage for replies that need
  classification)
- The classifier itself is an LLM and could miss cases (defense in depth,
  not a hard barrier)

### Option D — Frontend-Side Validation Only

The frontend receives the agent's reply, parses it for facility/booking
IDs, validates against the user's cached entity list, and renders
warnings or hides bad replies.

**Strengths:**
- Lower backend cost (no extra Vertex call)
- Backend stays simpler

**Weaknesses:**
- Frontend can be tampered with; bad replies still leave the backend
- Splits responsibility: backend produces; frontend validates → backend
  has no record of what was actually shown
- The natural-language text can hallucinate facility *names* not just
  IDs; the frontend can't validate names without doing fuzzy matching
- Defense in depth: the backend should catch this regardless

## Decision

All natural-language agent replies that reference entity identifiers
pass through an output classifier (a separate Vertex AI call). The
classifier validates that referenced facility IDs and booking IDs exist
for the current tenant. Replies that fail validation, or where the
classifier itself errors, are suppressed and replaced with a safe
fallback message.

## Rationale

The propose-confirm-execute gate (ADR-0023) handles the *execution*
side of LLM safety. The output guard handles the *display* side. Both
layers are necessary because:

- Without the gate, hallucinations cause real state corruption
- Without the guard, hallucinations cause user confusion and erode trust
  in the agent

The fail-closed semantics matter. A classifier that says "I don't know"
is treated as failure, not "probably fine." This is the same safety
posture as ADR-0007 (auth) and ADR-0009 (slot locking) — when in doubt,
refuse rather than proceed.

The latency and cost of an extra Vertex call were considered acceptable
because the cost of a single user-visible hallucination is high (it
becomes a story the user tells about why "the AI doesn't work"). The
classifier prompt is short and uses a smaller context window than the
main agent prompt, so the latency impact is modest (~200-300ms).

## Consequences

### Positive

- Hallucinated facility/booking names don't appear in user-facing replies
- The agent's perceived reliability is much higher than the underlying
  model's raw reliability
- The fallback message ("I can only help with facility availability and
  booking queries") gives the user a clear next step
- Logging the classifier's decisions creates a debugging trail for
  tuning the agent prompt

### Negative

- Every reply pays the classifier latency and cost
- Some legitimate replies might be suppressed (false positives), though
  none have been observed in live testing
- The classifier itself is an LLM and can miss novel hallucinations
- Increases dependency on Vertex AI availability — both LLM calls must
  succeed for a successful agent turn

### Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Classifier blocks a legitimate reply (false positive) | Low | Conservative prompt; fallback message guides user to rephrase |
| Classifier misses a hallucination (false negative) | Medium | Defense in depth: the gate (ADR-0023) prevents bad state; user can dismiss bad proposals |
| Classifier latency cascades into slow UX | Low | Classifier prompt is small; observed ~200-300ms; acceptable for chat UX |
| Vertex outage affects both LLM calls | Medium | Both fail; agent falls back to "I'm having trouble right now" message |

## Alternatives Rejected

- **Option A (no guard):** Damages user trust even when the gate prevents
  execution-side harm. Hallucinated facility names in replies create real
  user confusion.
- **Option B (schema only):** Necessary but not sufficient. Schema-valid
  references can still be semantically wrong.
- **Option D (frontend validation):** Insufficient; backend must catch
  this regardless. Frontend validation is acceptable as a *redundant*
  layer but not as the primary defense.

## References

- PR #24: Read-only AI query agent (slice 1b) — initial output classifier
- PR #25: Diagnostic improvements (slice 1b.1)
- PR #26: PYTHONUNBUFFERED for log visibility (slice 1b.2)
- ADR-0022: AI Booking Agent Guardrails (companion ADR)

## Related ADRs

- **ADR-0022** (guardrails): Specifies the output guard as a core
  guardrail principle
- **ADR-0023** (propose-confirm-execute gate): Operates in tandem;
  the gate handles execution-side safety, this ADR handles display-side
- **ADR-0026** (deterministic Python guards): Another layer of defense;
  Python guards correct LLM mistakes in tool call params before
  proposals are stored
