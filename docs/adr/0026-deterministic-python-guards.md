# ADR-0026: Deterministic Python Guards over LLM Judgment

## Status

Accepted (Phase 9, pattern emerged across slices 3b, 6.4b, 6.5b, 6.6)

## Context

The SlotSense AI Booking Agent uses Vertex AI Gemini 1.5 Pro for natural
language understanding and function calling. The LLM is capable at
intent extraction (parsing "book tennis tomorrow at 9 PM" into a
structured tool call) but has documented unreliability in several
domains:

- **Temporal reasoning:** "Is 9 AM today in the past?" — the model
  often answers literally instead of contextually
- **Exact filtering:** "Which of these bookings is in the cancellation
  window?" — the model may include past-cutoff bookings if asked
  imprecisely
- **Arithmetic and counting:** "How many tennis bookings does this user
  have on this date?" — the model can miscount or include irrelevant
  rows
- **Boundary cases:** edge conditions in date math, timezone handling,
  and policy interpretation are not reliably handled

These unreliability ceilings emerged in Phase 9 testing across several
slices:

- Slice 6.5b: "book tennis at 09" → LLM picks 09:00 even when 09:00 today
  is already past (user meant 21:00)
- Slice 3b: cancel candidate filtering needed deterministic windowing,
  not LLM judgment
- Slice 6.4b: quota check needed to count user's bookings precisely, by
  exact sport, on the exact date
- Slice 6.6: per-sport quota counting required facility lookups and
  sport resolution that LLM cannot reliably perform

**Key insight from polish-round testing:** prompt-only fixes don't
solve LLM unreliability. Even with explicit rules in the system prompt
("If AM is in the past, interpret as PM"), the model ignores the rule
~10% of the time. Hermetic tests can't catch this because they mock
the LLM. The failures only surface in live testing with realistic
prompts and realistic data.

**Requirements:**

1. The agent must handle edge cases (past-AM, boundary times, exact
   quota math) deterministically
2. LLM capabilities should be used where they're strong (intent
   extraction, NLU) and bypassed where they're weak (math, filtering,
   temporal reasoning)
3. Guards must be testable in hermetic tests (mocked LLM input,
   verified Python output)
4. The pattern must be applicable to future features, not just the
   ones identified in Phase 9

## Options Considered

### Option A — Trust the LLM Entirely

Improve the system prompt with more rules, examples, and few-shot
demonstrations. Use the largest available model. Accept that the
remaining failure rate is the cost of using LLMs.

**Strengths:**
- Simplest architecture: one Vertex call, no Python logic
- The prompt is the only thing to maintain
- Scales naturally as models improve over time

**Weaknesses:**
- Empirically: even with explicit rules in the prompt, slice 6.5b
  showed the model ignored the "AM-past → PM" rule ~10% of the time
- Larger models are more expensive and slower
- Some failure modes (temporal reasoning, exact counting) are not
  reliably fixed by prompt engineering at any model size
- Hard to test (hermetic tests mock the LLM; live failures only
  surface in real usage)

### Option B — Pre-Process the User Message

Run a Python NLU layer before sending to the LLM: parse intent, extract
entities, resolve timestamps. Send a structured input to the LLM.

**Strengths:**
- Removes ambiguity before LLM sees the message
- Deterministic at the parsing stage

**Weaknesses:**
- Doubles the work: re-implements what the LLM is actually good at
  (intent extraction)
- Brittle: every variation of "tomorrow at 9" needs a Python parser
- Loses LLM's strength on conversational nuance
- Doesn't help with the specific failures observed (those are in the
  LLM's tool-call params, not in the user's input)

### Option C — Pre-Process the LLM Output (Guards on Tool Call Params) *(chosen)*

Let the LLM handle intent extraction and produce a tool call. Before
the tool executes (or before the proposal is stored), Python guards
inspect and correct the tool call params:

- **AM-past → PM guard:** if the LLM picked a start time in the past
  for today's date and the hour is < 12, advance to hour+12
- **Cancel candidate filter:** Python performs the exact filtering
  (sport match, date in 7-day window, within cancellation buffer);
  LLM never selects candidates
- **Quota check:** Python counts user's bookings for the sport+date,
  not the LLM
- **Per-sport quota in transaction:** Python looks up each booking's
  facility and resolves sport; LLM never sees this counting logic

**Strengths:**
- Uses LLM for what it's good at (intent extraction, NLU)
- Bypasses LLM for what it's weak at (math, filtering, temporal
  reasoning)
- Each guard is small, testable, deterministic
- Composable: new guards can be added without changing LLM prompts
- Logged: each guard emits a structured event when it fires (debugging
  trail for tuning)

**Weaknesses:**
- More code paths to maintain (each guard is logic that has to be
  written and tested)
- The LLM is doing "guess what the user wants" and the Python is doing
  "validate and correct" — two layers to debug
- Requires forethought: identifying which behaviors need guards is
  itself a design exercise

## Decision

Where LLM behavior is unreliable (temporal reasoning, exact filtering,
quota calculation, boundary conditions), the agent uses deterministic
Python code as the authoritative logic. The LLM is responsible for
intent extraction; Python guards validate and, when necessary, correct
the LLM's tool call params before execution.

Specific applications in Phase 9:

1. **AM-past → PM advancement** (slice 6.5b, `_dispatch_book`):
   If the LLM-provided start time on the requested date is in the past
   (tenant timezone) and the hour is < 12, advance to hour+12. Logged
   as `agent_book_am_past_advanced_to_pm`.

2. **Cancel candidate filtering** (slice 3b, `_filter_cancel_candidates`):
   Python performs exact filtering by sport, date window, and
   cancellation buffer. The LLM never sees the booking list and never
   selects which booking to cancel.

3. **Propose-time quota check** (slice 6.4b, `_dispatch_book`):
   Python counts user's confirmed same-sport same-date bookings against
   the per-sport quota policy. Refuses the proposal at propose time;
   the execute-time check (in `create_booking_with_quota`) is a
   defense-in-depth backup.

4. **Per-sport quota in transaction** (slice 6.6,
   `create_booking_with_quota`): The execute-time quota check filters
   by sport via facility lookups, not just by date. Tennis bookings
   don't count against the badminton quota.

## Rationale

This ADR captures a **pattern** rather than a single decision. The
pattern was forced by empirical evidence: prompt-only fixes did not
solve the temporal reasoning failure (slice 6.5b), and the polish
round of testing kept surfacing cases where the LLM produced
plausible-but-wrong tool call params.

The underlying principle: **LLMs and deterministic code should be
combined according to their strengths.** LLMs are excellent at
understanding "what did the user mean?" but unreliable at "what is
the right answer?" Where the right answer can be computed
deterministically — given the LLM's interpretation of intent — the
Python guard is the authoritative layer.

This also makes the agent more testable. Each guard has hermetic
tests that mock the LLM input and verify the Python output. The
LLM's contribution is decoupled from the safety/correctness logic.

The pattern is meta-architectural: it will apply to future features.
When a new agent capability is being designed and an LLM-only approach
is being considered, the question to ask is "is there an edge case
where the LLM might be wrong, and can the right answer be computed
deterministically?" If yes, add a guard.

## Consequences

### Positive

- The agent handles edge cases reliably regardless of LLM variation
- Failure modes are testable in hermetic tests (mocked LLM output,
  verified Python correction)
- Each guard is small, focused, and reviewable
- Structured logging on guard firings creates a debugging trail
- The pattern scales: future capabilities can add their own guards

### Negative

- More code paths to maintain (one prompt + many guards instead of
  just one prompt)
- The LLM and the Python layer can disagree in subtle ways; when they
  do, the Python wins — which is the right safety property but can be
  surprising to debug
- Identifying *which* behaviors need guards is itself a design exercise

### Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| A guard's logic is wrong → corrects an LLM that was right | Low | Hermetic tests verify guard logic; live testing surfaces edge cases |
| A new failure mode is not caught by any guard | Medium | Pattern is "discover via live testing, add guards as found"; each new guard documented in CHANGELOG |
| Two guards interact unexpectedly | Low | Each guard is local to a tool call's params; they don't share state |
| Guard logging volume becomes noisy | Low | Use structured logging (jsonPayload); filter on event name in queries |

## Alternatives Rejected

- **Option A (trust the LLM):** Empirically inadequate. Phase 9 live
  testing showed prompt-only fixes leave ~10% failure rate on temporal
  reasoning even with explicit rules.
- **Option B (pre-process user message):** Re-implements what the LLM
  is good at; doesn't fix the actual failure modes (which are in tool
  call params, not in user input).

## References

- PR #28 (slice 2b): Initial cancel filter pattern
- PR #37 (slice 6.4): Propose-time quota check
- PR #38 (slice 6.5): AM-past → PM guard + stateful disambiguation
  (also a deterministic logic layer)
- PR #39 (slice 6.6): Per-sport quota in transaction
- Phase 9 retrospective: discusses the pattern's emergence in detail

## Related ADRs

- **ADR-0021** (agent architecture): Establishes the agent's overall
  approach; this ADR refines it
- **ADR-0023** (propose-confirm-execute gate): The gate is where the
  guards operate (between propose and execute)
- **ADR-0024** (output guard): A specific kind of guard, focused on
  the natural-language output rather than tool call params
- **ADR-0025** (pending action store): The guards run on params before
  they're stored in the pending action
