# ADR-0023: Propose-Confirm-Execute Gate for the AI Booking Agent

## Status

Accepted (Phase 9, slice 2b)

## Context

The SlotSense AI Booking Agent (Phase 9) lets residents perform booking
operations through natural-language conversation. Booking and cancellation
are state-mutating operations with real consequences: an erroneous booking
consumes a real time slot, an erroneous cancellation loses a reservation
the user wanted to keep.

The agent uses Vertex AI Gemini 1.5 Pro for natural language understanding
and function calling. While the model is capable, it has known failure modes:

- **Hallucination** of facility or booking IDs
- **Misinterpretation** of ambiguous user input (e.g., "book tennis at 9"
  could be 9 AM or 9 PM)
- **Goal drift** in longer conversations — the model loses track of which
  action the user originally requested
- **Confabulation** of state — the model "remembers" bookings that don't
  exist

Any of these failure modes, if allowed to directly mutate persistent state,
results in a real defect visible to the user. The cost of getting this
wrong is high: a falsely-booked slot that the user didn't request is hard
to undo (other users may have seen the unavailability and made other plans);
a falsely-cancelled booking is similarly hard to recover.

**Requirements:**

1. Mutations must require explicit, unambiguous user confirmation
2. The confirmed action must be deterministically the same as the proposed
   action (no re-interpretation between proposal and execution)
3. The pattern must work across stateless Cloud Run instances
4. Confirmation must time out (a 30-minute-old proposal should not
   suddenly execute if the user replies "yes")
5. Per-tenant, per-user scope is mandatory (one user's pending action
   cannot be consumed by another user)

## Options Considered

### Option A — Direct Execution

LLM produces a tool call; backend immediately mutates state. The agent's
reply confirms what happened ("Booked Tennis Court 1 at 9 PM").

**Strengths:**
- Single round trip; lowest latency
- Simplest code path
- Matches the "function calling" mental model of most LLM frameworks

**Weaknesses:**
- Any LLM error mutates real state with no opportunity to dispute
- User has no chance to catch misinterpreted ambiguity before the action
  is irreversible
- Hallucination of facility IDs → bookings against nonexistent or
  wrong facilities
- No audit trail of intent vs. execution

### Option B — Single Confirmation Prompt (free-text)

Agent proposes the action in natural language and asks "Should I proceed?"
User replies yes/no/modify. Backend re-interprets the user's reply via
another LLM call.

**Strengths:**
- One layer of user safety
- Conversational and natural

**Weaknesses:**
- The "yes" reply is ambiguous: LLM might interpret it as confirmation of
  a different action, especially in longer conversations
- Backend state could change between propose and confirm (e.g., another
  user booked the slot); the "yes" path doesn't surface this cleanly
- Re-interpreting the user's reply with the LLM means the executed action
  could drift from the proposed action

### Option C — Propose-Confirm-Execute with Structured Pending Action *(chosen)*

The agent stores a structured pending action in Redis with a unique ID
when it makes a proposal. The user confirms by referencing the pending
action ID (via a tappable button in the UI). The backend executes from
the stored structured params, never re-interpreting the user's reply
or the original message.

**Strengths:**
- The executed action is *exactly* the proposed action — no LLM
  re-interpretation in between
- Pending action TTL (5 minutes) automatically invalidates stale proposals
- Single-use semantics (consume = read + delete atomically) prevents
  replay
- Per-tenant, per-user key construction prevents cross-user replay
- Structured params can be validated at execute time (defense in depth)
- Frontend can render a structured proposal card (facility name, date,
  time clearly visible) instead of relying on the agent's natural-language
  summary

**Weaknesses:**
- Extra round trip (propose, then confirm)
- Redis dependency for state
- The frontend must handle the pending_action_id correctly (don't lose
  it, don't replay it)

## Decision

The AI Booking Agent uses a propose-confirm-execute pattern for all
state-mutating operations. The agent never directly mutates state in
response to a user message.

## Rationale

The propose-confirm-execute gate is the *foundational safety property*
for the agent. It separates the LLM's role (intent extraction, natural
language understanding) from the backend's role (action execution).

The key insight: with the gate in place, even an LLM that hallucinates
50% of the time produces no real harm. The hallucinated action goes into
the pending store; the user sees it in the proposal card; they either
confirm (the agent guessed right) or dismiss (the agent guessed wrong).
Either way, no incorrect state is committed.

Every other safety property of the agent — output guard, deterministic
Python guards, quota checks at propose time — *layers on top of* this
foundational gate. Without it, none of those other properties prevent
harm; with it, they refine the user experience.

This decision was made early in Phase 9 (slice 2b) and held throughout
the build. Later slices (3b cancellation, 6.4 error mapping, 6.5
disambiguation) all assume and extend this pattern.

## Consequences

### Positive

- Hallucinations and ambiguity get caught at the proposal stage, not at
  execution
- Audit trail is clean: every state mutation has a confirmed proposal ID
  associated with it
- The frontend renders structured proposal cards, which display the
  proposed action in unambiguous terms (12-hour AM/PM, facility name,
  not just facility ID)
- TTL semantics mean stale proposals can't accidentally execute
- The pattern extends cleanly to multi-step flows (slice 6.5c added
  stateful disambiguation using the same Redis-backed store)

### Negative

- Two round trips per mutation (propose → confirm)
- Redis dependency: if Redis is down, the agent can't propose or confirm
  (currently fails closed)
- Frontend complexity: must track pending_action_id state and disable
  the confirm button when the 5-minute TTL expires

### Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| User dismisses a proposal that was correct, has to re-prompt | Medium | UI is forgiving; previous message is in chat history |
| Pending action ID leaks via logs | Low | Action IDs are random uuid4; tenant+uid scope makes leakage low-value |
| Two users somehow target the same action_id | Negligible | uuid4 collision space is enormous; key construction adds tenant+uid scope |
| Race between confirm and TTL expiry | Low | 5-minute TTL gives ample buffer; expiry returns a clear "this proposal has expired" message |

## Alternatives Rejected

- **Option A (direct execution):** Insufficient safety. Any LLM failure
  becomes a real defect.
- **Option B (free-text confirmation):** The "yes" path can be hijacked by
  conversational drift. The LLM re-interpreting user's confirmation
  reintroduces the failure modes the gate is meant to prevent.

## References

- PR #28: Initial implementation in slice 2b
- PR #30: Extended to cancel in slice 3b
- PR #33: Added `pending_action_summary` to `AgentReply` (slice 5a)
- PR #38: Stateful disambiguation extends the store (slice 6.5c)
- ADR-0021: AI Booking Agent Architecture (high-level)
- ADR-0022: AI Booking Agent Guardrails (companion to this ADR)

## Related ADRs

- **ADR-0021** (agent architecture): This ADR specifies the
  propose-confirm-execute pattern as a core architectural element
- **ADR-0022** (agent guardrails): The output guard works in concert
  with this gate — output guard catches hallucinated content in
  proposals; the gate ensures hallucinated content can't auto-execute
- **ADR-0024** (output guard): Stacks on top of this gate
- **ADR-0025** (pending action store): Implements the storage layer
  this gate depends on
- **ADR-0026** (deterministic Python guards): Operates on the
  pending action params before execution
