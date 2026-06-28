# ADR-0025: Pending Action Store (Redis-backed, single-use, secondary pointer)

## Status

Accepted (Phase 9, slice 2b; extended in slice 6.5c)

## Context

The propose-confirm-execute pattern (ADR-0023) requires that the agent
store proposed actions somewhere between the propose turn and the confirm
turn. The store must satisfy several constraints:

1. **Time-bounded:** proposals must expire automatically (a 30-minute-old
   proposal should not execute if the user replies "yes")
2. **Single-use:** consuming a proposal must atomically remove it, so
   the same proposal cannot be replayed
3. **Per-tenant, per-user scope:** one user's proposal cannot be consumed
   by another user, including across tenants
4. **Cross-instance:** must work across stateless Cloud Run instances
   (the propose turn and confirm turn may hit different instances)
5. **Low latency:** the store is on the agent's critical path; reads
   and writes must be fast
6. **Type-based lookup (added in slice 6.5c):** for stateful disambiguation,
   we need to look up "the latest pending action of a specific type for
   this user" without scanning

The agent supports three action types: `book`, `cancel`, and (later)
`cancel_disambiguation`. Each has different params:

- `book`: `{facility_id, date, start}`
- `cancel`: `{booking_id}`
- `cancel_disambiguation`: `{sport, candidates: [{id, facility_id, date, start, end}]}`

## Options Considered

### Option A — Firestore-Backed Pending Actions

A Firestore collection `agent_pending_actions/{action_id}` with
tenant_id and uid as fields, plus a TTL via a scheduled cleanup job
or Firestore TTL feature.

**Strengths:**
- Persists across Redis failures
- Same database as bookings (one less service dependency)
- Native query support for "all pending actions for user X"

**Weaknesses:**
- Cost: Firestore reads charged per document; agent has hot path with
  ~3-5 reads/writes per propose-confirm cycle
- Latency: Firestore reads in `asia-south1` are ~30-50ms; Redis is ~1-5ms
- TTL: Firestore native TTL has up to 24-hour granularity; not suitable
  for 5-minute pending action lifetime
- Transaction complexity: atomic consume (read + delete) requires
  Firestore transactions; harder semantics than Redis DEL

### Option B — In-Memory (Process-Local)

A Python dict in the agent module, keyed by action_id.

**Strengths:**
- Lowest latency (in-memory)
- No external dependency

**Weaknesses:**
- Doesn't survive process restart (Cloud Run instances cycle frequently)
- Doesn't work across instances: propose on instance A, confirm on
  instance B → confirm fails because instance B has empty dict
- Cloud Run is explicitly designed as a stateless services platform
  (ADR-0001); local state violates this contract

### Option C — Request-Scoped (No Persistence)

Bundle the pending action params into the AgentReply structure. Frontend
sends them back unmodified on the confirm message.

**Strengths:**
- Zero server-side state
- Survives any backend failure
- Clear data flow: propose returns the action; confirm receives it back

**Weaknesses:**
- Server-side state leaks to client; client could tamper with params
  before sending back
- Doesn't survive page refresh in the same way (frontend state is
  ephemeral)
- Replay protection requires another mechanism (HMAC, sequence numbers)
- The "confirm" message becomes a structured payload, not a natural-
  language reply — couples the wire protocol to this implementation
  detail

### Option D — Redis with Primary + Secondary Pointer Keys *(chosen)*

**Primary key:** `agent_pending:{tenant_id}:{uid}:{action_id}` → JSON
payload `{action_type, params}`, with `PX=300000` (5-minute TTL).

**Consume:** atomic GET + DEL (Redis pipeline or Lua script).

**Secondary pointer key (added in slice 6.5c):**
`agent_pending_latest:{tenant_id}:{uid}:{action_type}` → action_id,
same TTL as primary. Enables `get_latest_for_user(action_type)`
without a scan: read the pointer, follow to the primary key.

**Strengths:**
- Native TTL with millisecond granularity
- Atomic consume via DEL semantics
- Per-key scoping prevents cross-user replay
- ~1-5ms latency in `asia-south1` Memorystore
- Secondary pointer enables type-based lookup with one extra read
- Already a Cloud Memorystore dependency (used for distributed locks
  in ADR-0009)

**Weaknesses:**
- Redis dependency: if Redis is down, agent can't propose or confirm
- The pointer key creates dangling references when the primary is
  consumed (acceptable: dangling pointer returns None, treated as
  "no pending disambiguation")
- An additional SET on every propose (the pointer write) — minimal
  cost but worth noting

## Decision

Pending actions are stored in Cloud Memorystore Redis with:

- Primary key: `agent_pending:{tenant_id}:{uid}:{action_id}`, payload
  `{action_type, params}`, TTL 5 minutes
- Secondary pointer key: `agent_pending_latest:{tenant_id}:{uid}:{action_type}`,
  payload `action_id`, TTL 5 minutes
- Consume = atomic GET + DEL on the primary key only (pointer left to
  expire or become dangling)

## Rationale

Redis was chosen primarily for **TTL semantics**. The 5-minute lifetime
of a pending action is fundamental to the agent's safety model: a stale
proposal must not execute. Firestore's coarse TTL granularity (24 hours)
makes it unsuitable; in-memory storage doesn't survive Cloud Run's
stateless model; request-scoped storage opens tampering risk.

The secondary pointer key was added in slice 6.5c to support stateful
cancel disambiguation. When the user has multiple cancellable bookings
matching their query, the agent presents them as a list and stores
the candidates as a `cancel_disambiguation` pending action. On the
next user turn, the agent needs to look up "is there an active
disambiguation for this user?" without scanning Redis. The pointer key
makes this a single GET.

The choice to leave the pointer dangling after consume (rather than
deleting both keys atomically) is a deliberate simplification.
`get_latest_for_user` follows the pointer to the primary key; if the
primary is gone (consumed or expired), the function returns None. The
caller treats None as "no pending action," which is exactly the right
behavior. Adding the pointer to the atomic consume would complicate
the Redis pipeline without buying anything.

The key construction (`agent_pending:{tenant_id}:{uid}:{action_id}`)
enforces scope at the storage layer: a user from tenant A cannot
construct a key that reads tenant B's pending actions. This matches
the ADR-0004 tenant isolation principle.

## Consequences

### Positive

- Single-use, TTL-bounded pending actions match the propose-confirm-execute
  gate's safety requirements (ADR-0023)
- The secondary pointer enables stateful flows (disambiguation) without
  a more complex data model
- Per-tenant, per-user key construction makes cross-tenant replay
  impossible by construction (not by check)
- Reuses existing Redis dependency (no new service)
- Atomic consume prevents replay races

### Negative

- Redis as critical path for the agent (if Redis is down, the agent's
  propose-confirm-execute flow is broken)
- The pointer adds one extra SET per propose
- Dangling pointers exist briefly after consume (harmless but
  technically debt)

### Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Memorystore Redis instance outage | Low | Agent fails closed: returns "I can't process that right now"; manual booking flow still works |
| Memory pressure if many pending actions accumulate | Low | 5-min TTL caps the total set; typical user has 0-1 pending at any time |
| Key construction bug allows cross-user replay | Low | Key includes tenant_id + uid; covered by hermetic tests for scope enforcement |
| Dangling pointer is mistakenly treated as a live action | Negligible | `get_latest_for_user` follows the pointer and verifies the primary; missing primary returns None |
| Race between propose (writing pointer) and consume (deleting primary) | Negligible | Last write wins for the pointer; if a newer propose's pointer overwrites an older one, the consume of the older primary still works by direct action_id |

## Alternatives Rejected

- **Option A (Firestore):** Cost, latency, and coarse TTL all
  disqualifying for the agent's hot path
- **Option B (in-memory):** Violates the stateless services contract
  (ADR-0001); doesn't survive Cloud Run instance cycling
- **Option C (request-scoped):** Server-side state leaking to client;
  tampering risk; couples wire protocol to internal data shape

## References

- PR #28: Initial implementation in slice 2b
- PR #38: Secondary pointer added for stateful disambiguation (slice 6.5c)
- ADR-0009: Slot Locking with Redis (also uses Memorystore)

## Related ADRs

- **ADR-0023** (propose-confirm-execute gate): This ADR specifies the
  storage layer that gate depends on
- **ADR-0004** (tenant isolation): Key construction enforces tenant
  scope at the storage layer
- **ADR-0009** (slot locking): Same Memorystore Redis instance
- **ADR-0026** (deterministic Python guards): Consumes from this
  store; the guards run on the params before execution
