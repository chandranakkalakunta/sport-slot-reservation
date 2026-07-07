# ADR-0022: AI Booking Agent — Guardrails & Safety

- **Status:** Accepted
- **Date:** 2026-06-21
- **Deciders:** Coordinator (Chandra), Strategist
- **Phase:** 9 (AI Booking Agent)
- **Related:** ADR-0021 (agent architecture), ADR-0004 (tenant isolation /
  defense-in-depth), ADR-0007 (JWT authoritative), ADR-0008 (repository
  pattern), ADR-0011 (audit logging)

## Context

The AI Booking Agent (ADR-0021) places a large language model in the request
path of a multi-tenant system that can book and cancel on a resident's behalf.
This introduces new risk surfaces: prompt injection, out-of-scope or abusive
requests, cross-user / cross-tenant data exposure, inappropriate output, silent
mutations from model error, and cost abuse. This ADR defines the guardrail model.

## Decisions

### 1. Organizing principle — authoritative vs advisory guardrails

**Security is enforced by the API and the architecture (authoritative); the LLM
enforces only intent-routing and tone (advisory). The model is never trusted for
anything whose failure would breach security.**

If a guardrail's failure would cause a security breach (cross-user data, exceeded
privilege, unauthorized mutation), it must be enforced structurally — not by a
prompt instruction the model might ignore or be argued out of. We assume the
prompt will eventually be jailbroken and design so that a jailbreak cannot cause
harm.

### 2. Input gating (two layers)

- **Advisory (intent classification + system prompt):** the agent is scoped to
  booking-domain intents. Off-topic requests resolve to `out_of_scope` and
  receive a polite, respectful refusal that redirects to what the agent can do.
  This is the normal-case gate.
- **Authoritative (tool catalog, ADR-0021 §3):** the model can only call the
  registered tools. There is no admin tool, no cross-user tool, no
  arbitrary-query tool. A successful prompt-injection therefore cannot produce
  an out-of-catalog action — there is no function to call — and the in-catalog
  tools each enforce their own authz against the resident's own context. **The
  blast radius of any injection success is bounded by the tool catalog.**

### 3. Prompt-injection resistance

We do not rely on the LLM to resist injection for security. We rely on the agent
being unable to do harm if injected:
- It holds only the resident's own JWT/context, so reads return only the
  resident's data and mutations only affect bookings the API permits.
- There is no admin tool to invoke regardless of what the model is convinced of.
- Tenant isolation is enforced by the repository/Firestore layer (ADR-0004,
  ADR-0008), not by the agent.

The worst outcome of a successful injection is an off-topic or impolite response
(an annoyance, caught by output guarding) — never a privilege or data breach.

### 4. Output guarding

Two sub-concerns of very different weight:

- **Data-scoping (authoritative, heavy):** the agent can never emit data outside
  the resident's authz scope (another resident's bookings, another tenant's
  facilities) because it never receives such data — it only relays results of
  calls made with the resident's own context. This is structurally guaranteed,
  not prompt-enforced.
- **Tone / subject / language (advisory, lighter):** responses must be
  respectful, on-subject (booking domain), and appropriately worded. This is an
  LLM-layer concern with a mild failure mode (an awkward reply, not a breach).

**Output guardrail mechanism (v1):** a cheap, always-on **rules-based check** on
every generated reply — verifies the response is on-subject and contains no data
the turn's tool calls did not legitimately return (a structural leak check), and
applies basic tone/language constraints. If the check fails, the reply is
replaced with a safe canned response rather than emitted. An **optional
LLM-based tone/subject classifier** (a second cheap Flash call) may be enabled
for stronger output validation at the cost of a second Vertex call per turn
(roughly doubling per-turn cost + latency); given the cost posture (ADR-0021 §7)
the default is rules-based-always-on, with the LLM classifier available as a
toggle. (Open: whether to enable the LLM classifier by default for showcase
robustness — Coordinator to decide before slice 1 ships output guarding.)

### 5. Confirm-before-mutate as a safety control

No booking or cancellation executes without a distinct, server-tracked user
confirmation (ADR-0021 §4). This protects against both model error (mis-parsed
intent) and user slips. The confirmation surfaces the resolved action in plain
language so the user verifies exactly what will happen.

### 6. Fail closed on uncertainty

- **Vertex unavailable / errors:** the agent returns a graceful fallback ("I'm
  having trouble right now — please try again or use the booking screen"). Never
  a stack trace or silent hang. The booking UI remains available, so the agent
  being down is degraded, not broken.
- **Un-parseable / garbage model output or ambiguous tool call:** treated as
  `out_of_scope` / a request to rephrase. **The agent never executes an action
  it is uncertain about.** Consistent with the project's fail-closed principle.
- **Domain error from the API** (court full, quota exceeded, outside
  cancellation window): translated into natural language ("That court's booked
  then — want me to check others?"). No blind retry, no hidden failure.
- **Abandoned conversation / disambiguation timeout:** the pending action expires
  with the Redis TTL; nothing executes.

### 7. Abuse / cost protection

An LLM endpoint costs real money per call (Vertex + trial credits). The agent
endpoint (`POST /v1/agent/chat`) is rate-limited **more tightly** than cheap
endpoints. Note: the existing rate limiter is in-memory/per-instance (a known
limitation); for a cost-bearing endpoint this is more pointed, so Redis-backed
rate limiting for the agent endpoint specifically is to be considered even ahead
of the general fix. (Open: per-resident agent call quota — Coordinator to set a
limit.)

### 8. Auditability — differentiated agent actions

Every agent-initiated mutation writes a **distinct** audit event versus the
manual path, reusing the ADR-0011 audit pattern:
- `agent.booking_created` (vs manual `booking_created`)
- `agent.booking_cancelled` (vs manual cancellation event)

The event records that the action was agent-initiated **and** user-confirmed.
This enables: measuring agent adoption, debugging "the agent did X" reports, and
demonstrating full traceability of AI-initiated actions — an accountability
property expected of an AI feature acting on a user's behalf.

## Consequences

- A prompt-injection success cannot breach security; its blast radius is the
  (resident-scoped) tool catalog. This is the central safety property.
- Cross-user / cross-tenant data exposure is structurally impossible, not
  prompt-dependent.
- Always-on rules-based output guarding adds negligible cost; the optional LLM
  classifier roughly doubles per-turn cost when enabled.
- Server-enforced confirmation and fail-closed-on-uncertainty prevent erroneous
  or injected mutations.
- Tighter agent-endpoint rate limiting protects trial credits but inherits the
  in-memory rate-limiter limitation until that is addressed.
- Differentiated audit events give full traceability of agent actions.

## Open questions for ruling before the relevant slice

- §4: enable the LLM-based output classifier by default, or ship rules-based-only
  for v1 and add the classifier later?
- §7: per-resident agent-call quota value; Redis-backed rate limiting for the
  agent endpoint specifically vs. waiting for the general fix.

## References

- ADR-0021 (agent architecture)
- ADR-0004 (tenant isolation, defense-in-depth)
- ADR-0007 (JWT authoritative)
- ADR-0008 (repository pattern, tenant isolation)
- ADR-0011 (audit logging)
