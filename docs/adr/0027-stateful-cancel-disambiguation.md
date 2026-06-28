# ADR-0027: Stateful Cancel Disambiguation via Pending Action Store

## Status

Accepted (Phase 9, slice 6.5c)

## Context

When a user asks the agent to cancel a booking and multiple bookings
match the request, the agent must present the candidates and let the
user pick one.

The original implementation (slice 3b) was stateless:

```python
# Original: many candidates → list them, hope the user re-prompts
if n_candidates >= 2:
    lines = [f"You have {n_candidates} upcoming {sport} bookings that can be cancelled:"]
    for i, b in enumerate(candidates, 1):
        lines.append(f"  {i}. {fac_name} — {date} at {start}")
    lines.append("Please tell me which one by specifying the date.")
    return ("\n".join(lines), None, None)
```

The agent listed the candidates and asked the user to re-issue a
fully-specified cancel request. The user's next message was treated
as a fresh query — no memory of the disambiguation.

Live testing during slice 6.5 surfaced multiple failure modes:

- User typed "1" or "2" (referring to the list numbering) → agent
  treated it as a fresh query, didn't understand
- User typed the date the agent had shown ("2026-06-28 at 19:00") →
  the LLM extracted the cancel intent again but the *same disambiguation
  ran again*, producing the same list, in an infinite loop
- User typed "the first one" → not enough information for the LLM to
  resolve

**Key observation:** the agent already had a Redis-backed pending
action store (ADR-0025) for the propose-confirm-execute gate. The
disambiguation problem was structurally similar: state that needs to
survive between two user turns, scoped to a single user, with a TTL.

**Requirements:**

1. When the agent lists disambiguation candidates, the user's next
   message should be interpretable in that context
2. A clear "selection" (date + time matching one candidate) should
   route directly to the cancel propose flow
3. An ambiguous reply (no candidate matches, multiple match, or
   user changed topic) should fall through to the LLM normally
4. The disambiguation state must expire (5-min TTL matching pending
   actions)
5. Per-tenant, per-user scope
6. The implementation should not bloat the architecture — reuse
   existing infrastructure where possible

## Options Considered

### Option A — Keep Stateless Disambiguation

Accept that disambiguation requires the user to fully re-specify the
cancel request. Improve the agent's natural-language reply to teach
users the expected format.

**Strengths:**
- No state to manage
- Simpler architecture

**Weaknesses:**
- Empirically broken: users got stuck in loops during live testing
- Forcing users to type "cancel tennis on 2026-06-28 at 19:00" is
  hostile UX; they shouldn't have to repeat what the agent just told
  them
- The fallback option (tappable buttons in the UI) would require its
  own architectural work; punted to backlog

### Option B — Server-Side State Outside the Pending Action Store

A separate Redis key namespace (`agent_disambig:{tenant}:{uid}`) or
even Firestore for the disambiguation state.

**Strengths:**
- Clean separation: pending actions are for proposals, disambiguation
  is a different concept
- Allows different TTLs if needed

**Weaknesses:**
- New infrastructure for what is fundamentally the same shape of
  data (per-user, per-tenant, TTL-bounded, single-use semantics
  available)
- Two code paths to maintain
- Easy to drift between the two stores' semantics

### Option C — Client-Side State (Bundle Candidates in AgentReply)

The disambiguation list is stored in the frontend's chat thread; on
the next user message, the frontend includes the candidates as part
of the context sent back.

**Strengths:**
- No server-side state for this case
- Frontend already has chat thread state

**Weaknesses:**
- Couples wire protocol to disambiguation as a first-class concept
- The frontend would need to know which messages are "disambiguation
  lists" and which aren't
- Tampering risk: client could modify or forge candidates
- The output guard (ADR-0024) runs server-side; can't classify what
  it doesn't see
- ADR-0025 already documented why client-side state was rejected for
  pending actions; the same logic applies here

### Option D — Extend Pending Action Store with `cancel_disambiguation` Type *(chosen)*

Add a new action type to the existing pending action store. When the
agent enters the disambiguation branch, it stores a `cancel_disambiguation`
pending action with the candidate list. The store's secondary pointer
key (`agent_pending_latest:{tenant}:{uid}:cancel_disambiguation`) makes
the disambiguation retrievable by type without scanning.

On the next user message, the agent checks for an active disambiguation
*before* calling the LLM:

```python
disambig = await store.get_latest_for_user(ctx, "cancel_disambiguation")
if disambig is not None:
    matched = _match_disambig_candidate(user_message, disambig.candidates)
    if matched is not None:
        await store.consume(ctx, disambig.action_id)
        # Route to cancel propose flow for matched booking
        return cancel_propose_flow(matched)
    # No match: fall through to normal LLM processing
```

The matching rule is deliberately conservative: the user's message
must contain *both* the candidate's date *and* its start time as
substrings, and exactly one candidate must match. Zero or multiple
matches fall through.

**Strengths:**
- Reuses existing store; no new infrastructure
- The secondary pointer key (added in this same slice) does exactly
  what's needed — lookup by type
- TTL semantics match (5 minutes is appropriate for disambiguation)
- Per-tenant per-user scope inherited from ADR-0025
- Conservative matching prevents false positives
- Falls through cleanly on ambiguous input

**Weaknesses:**
- Adds a new action type to the store's vocabulary
- The matching logic is substring-based; doesn't handle paraphrase
  (e.g., "the first one" doesn't match)
- A user with multiple unrelated disambiguations could see surprises
  (rare in practice)

## Decision

When the agent enters the cancel-disambiguation branch (multiple
matching candidates), it stores a `cancel_disambiguation` pending
action with the candidate list. The agent checks for this state
before calling the LLM on subsequent user messages; an unambiguous
match (date + start both present, exactly one candidate) consumes the
disambiguation and routes to the cancel propose flow.

## Rationale

The disambiguation problem is structurally identical to the
propose-confirm-execute flow: state that survives between two user
turns, scoped to a single user, with a TTL. The pending action store
(ADR-0025) already solves this shape of problem; reusing it adds
nothing to the architecture's surface area.

The conservative matching rule (date + start both required, exactly
one candidate matches) is deliberate. The cost of a false positive
(wrong booking cancelled) is high. The cost of a false negative (user
has to be more explicit) is low. The rule is biased toward false
negatives.

The fall-through-to-LLM behavior matters. If the user types "cancel
tennis tomorrow at 7" while a disambiguation is active, the matching
rule won't match (no date in the message). Rather than producing
weird behavior, the agent treats the message as a fresh query. The
disambiguation remains active in Redis with its TTL counting down;
if the user comes back to it within 5 minutes with a proper
selection, it still works.

The secondary pointer key in the store (added in the same slice for
this purpose) is what makes type-based lookup possible. Without it,
finding "the latest disambiguation for this user" would require a
scan — and `get_latest_for_user` is on the hot path for every user
message.

## Consequences

### Positive

- Users can select a candidate by typing its date and time (the same
  format the agent showed in the list)
- Live testing confirms the flow works cleanly: "2026-06-28 at 19:00"
  → exact match → cancel proposal → confirm
- The fall-through behavior preserves the agent's general utility
  even when a stale disambiguation is hanging around
- Architecture stays small: one new action type, one new store method,
  one matching function

### Negative

- Users typing "the first one" or "1" don't get matched (acceptable
  v1 limitation; documented for the UX backlog)
- The matching rule is brittle to date format variations (e.g., user
  types "Jun 28" instead of "2026-06-28" — won't match)
- A user might be confused if they intended a fresh cancel and the
  agent routes them to an old disambiguation (very rare in practice)

### Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| False positive: wrong booking cancelled due to ambiguous match | Low | Matching requires both date AND start; exactly one candidate must match |
| User stuck in loop because matching is too strict | Low | Fall-through to LLM means general queries still work; user can simply retype with more detail |
| Stale disambiguation matches a much later message | Low | 5-min TTL; matching is precise enough that random later messages rarely hit |
| Frontend doesn't surface that disambiguation is active | Medium | Future polish (backlog): show a "disambiguation pending" affordance; current state is good enough for v1 |

## Alternatives Rejected

- **Option A (stateless):** Empirically broken; users got stuck in
  loops during live testing
- **Option B (separate state store):** Reinvents the pending action
  store for the same shape of problem
- **Option C (client-side state):** Output guard runs server-side and
  can't classify what it doesn't see; tampering risk

## References

- PR #38: Slice 6.5c implementation
- Live testing screenshots in slice 6.5 round (multi-turn disambiguation
  failures)

## Related ADRs

- **ADR-0025** (pending action store): This ADR extends the store
  with a new action type; the secondary pointer key was added in the
  same slice to support this lookup
- **ADR-0023** (propose-confirm-execute gate): Disambiguation feeds
  into the gate (matched candidate → cancel propose)
- **ADR-0026** (deterministic Python guards): The matching rule
  itself is a deterministic Python layer (LLM is bypassed for the
  selection logic)
