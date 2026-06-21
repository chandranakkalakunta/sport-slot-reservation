# ADR-0021: AI Booking Agent — Architecture

- **Status:** Proposed
- **Date:** 2026-06-21
- **Deciders:** Coordinator (Chandra), Strategist
- **Phase:** 9 (AI Booking Agent)
- **Related:** ADR-0022 (agent guardrails & safety), ADR-0007 (JWT custom
  claims), ADR-0008 (data layout / repository pattern), ADR-0010 (booking
  model), ADR-0011 (audit logging), ADR-0019 (notification/Cloud Tasks infra)

## Context

Phase 9 introduces a natural-language **AI Booking Agent** for residents.
Instead of navigating the UI to search facilities, pick a slot, and confirm,
a resident can say "book the tennis court at 6 PM" and the agent resolves
availability, asks any needed clarifying questions, and — on explicit
confirmation — books via the existing API. The agent also supports cancellation,
availability queries, and booking-count queries, and remembers a resident's
court/time preference across sessions.

The agent is **residents-only**. Tenant admins and platform admins are out of
scope (they have full UI tooling and higher-privilege operations that must not
be reachable through a conversational surface).

This ADR covers architecture: where the agent runs, the model/runtime, how it
authenticates and acts, conversation state and memory, the mutation-safety
protocol, and the scope of billing queries given current data. Safety,
guardrails, and abuse-resistance are covered in ADR-0022.

The agent is an **orchestration layer over the existing API**, not new booking
logic. All booking rules (quota, Redis slot lock, cancellation window, tenant
isolation, audit) remain in the existing service/repository layer where they
are already implemented and tested. The agent's job is: natural language →
intent → (existing) tool call as the resident → natural-language response.

## Decisions

### 1. Endpoint, runtime, and model

A new resident-only endpoint `POST /v1/agent/chat` is added to the existing
Cloud Run service (`sport-slot-api`, asia-south1). It is gated with the
existing `require_role("resident")` dependency. Request:
`{ message: str, conversation_id: str | null }` plus the resident's Firebase
ID token in the `Authorization` header (same as every other API call).
Response: `{ reply: str, conversation_id: str, pending_action: PendingAction |
null }`.

The model is **Gemini Flash-tier via Vertex AI** in `asia-south1`, called via
the Cloud Run service account using Application Default Credentials (ADC). No
API key is introduced — this preserves the project's zero-static-credentials
principle (ADR-0004 / Principle 4): Vertex authenticates through the same SA/ADC
mechanism as the rest of the stack, and requests stay in-project, in-region,
under existing IAM and org policy. Flash-tier is sufficient for intent routing
and function-calling; a heavier model is not warranted for v1.

### 2. Auth model — the agent acts with exactly the resident's privileges

**Invariant: the agent never holds privileges beyond the authenticated
resident's own.** The agent resolves the same `TenantContext` the rest of the
API uses (via the existing `get_tenant_context` dependency, JWT-authoritative
per ADR-0007) and invokes the existing **service-layer functions** with that
context. It does not have a service identity of its own for booking actions and
cannot construct a context for any other user or tenant.

Because the agent calls the same service/repository layer as the routers, all
existing authorization and business rules are inherited automatically: tenant
isolation (ADR-0008 repository pattern + Firestore rules), own-bookings-only
(`BookingRepository.list_for_uid` filters by uid), quota and slot-lock
(`create_booking_with_quota` + Redis lock), and the cancellation window
(`_is_cancellable`). The agent is structurally incapable of acting outside the
resident's scope because it only ever possesses that resident's context.

**Service-layer vs HTTP self-calls:** the agent calls service-layer functions
directly (in-process), reusing the same Pydantic request models the endpoints
use, rather than making HTTP calls to our own service. This avoids a redundant
network hop and JWT re-verification while preserving request validation. This
decision relies on business rules living in the service/repository layer (they
do); any rule that exists only in a router function must be moved to the service
layer or explicitly re-applied by the agent.

### 3. Tool catalog (capability is gated by registered tools)

The agent's entire action surface is a fixed catalog. The function-calling
schema handed to Vertex declares only the tools live in the current slice, so
the model cannot emit a call for a capability that is not yet enabled.

| Intent | Underlying call | Type | Slice |
|---|---|---|---|
| `check_availability` | `GET /facilities`, `/facilities/{id}/availability` | read | 1 |
| `list_my_bookings` / booking-count | `GET /bookings/mine` | read | 1 |
| `book` | `POST /bookings` | mutation (confirm-gated) | 2 |
| `cancel` | find via `/bookings/mine` → `POST /bookings/{id}/cancel` | mutation (confirm-gated) | 3 |
| `out_of_scope` | — (polite refusal) | — | 1 |

No admin, tenant-config, branding, or arbitrary-query tool exists in the
catalog. This bounds the blast radius of any prompt-injection success (see
ADR-0022).

### 4. Mutations: propose → confirm → execute (server-enforced)

State-changing intents (`book`, `cancel`) are **never executed on first turn**.
The agent returns a structured `pending_action` (intent + resolved params) and a
natural-language confirmation prompt. The frontend surfaces the resolved action
in plain terms ("Cancel your Tennis Court 3 booking, Saturday 6 PM?"). The user
confirms; the frontend returns a confirm signal referencing the `pending_action`;
only then does the agent execute via the existing endpoint.

The confirmation is **enforced server-side**: execution requires a distinct,
server-tracked confirmed `pending_action`, not a prompt instruction. A model
that "decides" to skip confirmation cannot, because execution is a separate
request the user must trigger. Prompt-level confirmation language is advisory;
the two-step protocol is authoritative. Pending actions expire (see §5).

### 5. Conversation state vs preference memory (two different stores)

These are distinct concerns with different lifetimes:

- **Conversation state** (within-session, multi-turn context for disambiguation):
  stored in **Redis with a short TTL** (minutes), keyed by `conversation_id`.
  The LLM is stateless across calls; the recent turns are replayed to Vertex on
  each call. Pending actions live here and expire with the conversation.
- **Preference memory** (across sessions, durable, user-visible): stored in
  **Firestore** under the user's profile. v1 scope: `{ sport -> { facility_id,
  start_time } }`, updated on each successful booking. This is the more critical
  store (it is the user-facing "remembers me" feature and must survive
  restarts/redeploys, which Basic-tier Memorystore does not guarantee).

**Memory suggests; confirmation commits.** A remembered court/time is offered as
a default in the confirmation prompt ("Court 3 at 6 PM, your usual — confirm?")
and is trivially overridable in the same turn ("make it 7"). The agent never
auto-books from memory. Remembered time is treated as a default-to-confirm, not
a fixed value, since schedule preferences drift.

### 6. Billing queries — scoped to what exists today

There is currently **no invoice model and no per-slot pricing** in the codebase
(per-slot pricing is a deferred requirement; an invoice/ledger model does not
yet exist). Therefore the only billing-adjacent capability in v1 is a **count**:
"how many bookings did I make this month?", computed from `/bookings/mine`
filtered by date.

Financial queries ("pending amount", "what do I owe", invoice details) are
**out of scope until two prerequisites land**: (a) per-slot pricing, and (b) an
invoice/ledger model. Until then the agent explicitly states billing/amount
information is not yet available rather than computing or fabricating a figure.

### 7. Cost posture

Vertex usage draws from the GCP trial credits (expiring 2026-09-05). To stay
economical and predictable:
- Flash-tier model for orchestration.
- Short conversation-state TTL keeps replayed context windows small.
- A user turn that involves a tool call is at most: user message → Vertex (with
  tools) → tool executes → Vertex (summarize result) → reply (i.e. up to two
  Vertex calls per tool-using turn). No open-ended multi-step agent loop in v1.
- Agent-endpoint rate limiting is tightened relative to cheap endpoints
  (ADR-0022 §abuse).

### 8. Rollout (slices)

1. **Slice 1 — read-only query agent:** `check_availability`, `list_my_bookings`
   / booking-count, `out_of_scope`. Proves the full pipeline (intent → JWT-scoped
   service call → NL response), input/output guardrails, and residents-only
   gating, with zero mutation risk.
2. **Slice 2 — booking:** `book` with propose→confirm→execute; writes preference
   memory; differentiated audit (`agent.booking_created`).
3. **Slice 3 — cancellation:** `cancel` with find→disambiguate→confirm→execute;
   `agent.booking_cancelled`.
4. **Slice 4 — preference suggestion polish** (use stored memory in proposals).
5. **Later — voice input** (speech-to-text in front of the same pipeline; no
   change to agent logic) and billing (gated on pricing + invoice model).

## Consequences

- The agent inherits all existing authz/business rules for free; it cannot
  exceed the resident's own privileges by construction.
- Capability is gated by the registered tool catalog, not by model behavior.
- Server-enforced confirmation prevents silent mutations from model error or
  injection.
- One LLM in the request path introduces per-call cost and latency; mitigated by
  Flash-tier, short context, and rate limiting, but draws trial credits.
- Direct service-layer calls require business rules to remain in the service
  layer (verified per slice), not in routers.
- Preference memory is deliberately narrow (court+time per sport); richer
  modeling is out of scope for v1.
- Billing is limited to counts until pricing + invoice models exist.

## References

- ADR-0022 (agent guardrails & safety)
- ADR-0007 (JWT custom claims; JWT authoritative for tenant)
- ADR-0008 (data layout, repository pattern, tenant isolation)
- ADR-0010 (booking model, quota, deterministic IDs)
- ADR-0011 (audit logging)
- ADR-0019 (notification architecture; Cloud Tasks / Vertex run in-project)
