# ADR-0006: API Design Patterns

## Status

Accepted — 2026-06-11 | Author: Chandra Nakkalakunta

## Context

Phase 2 builds the FastAPI backend foundation. Conventions for
versioning, errors, pagination, and health probes must be fixed
before the first endpoint exists, so every later endpoint is
consistent. Consumers are our own React PWA and (Phase 7) the
AI booking agent.

## Decisions

### 1. Versioning: URL path

All API routes live under /api/v1/. Breaking changes require
/api/v2/, never in-place changes. Chosen over header-based
versioning for cacheability and debuggability.

### 2. Error envelope

Every non-2xx response returns:
{ "code": "<REGISTRY_CODE>", "message": "<human readable>",
  "request_id": "<uuid4>", "timestamp": "<ISO-8601 UTC>" }
- code: flat, namespaced UPPER_SNAKE string, e.g.
  AUTH_INVALID_TOKEN, TENANT_MISMATCH, BOOKING_QUOTA_EXCEEDED,
  VALIDATION_FAILED. No numeric codes (HTTP status carries the
  class). No nesting.
- All codes live in a single registry module
  (backend/src/sport_slot/api/error_codes.py, created in 2.3);
  adding a code requires adding it there. Enables future
  frontend localization keyed on code.
- request_id is generated per request by middleware and echoed
  in a response header on ALL responses (success included).

### 3. Pagination: cursor-based only

List endpoints accept ?limit= and ?cursor= (opaque, base64-
encoded Firestore start_after token) and return
{ "items": [...], "next_cursor": "<token|null>" }.
Offset pagination is prohibited: Firestore offset(n) reads and
bills every skipped document, violating the ADR-0005 cost
ceiling at scale.

### 4. Health endpoints: split liveness/readiness

- GET /health — liveness. Process is up. No dependency calls.
- GET /readyz — readiness. Verifies Firestore reachability.
Both OUTSIDE /api/v1/ (infrastructure probes are not versioned
API surface). Prevents Cloud Run restart loops when a
dependency blips (liveness stays green while readiness drops).

Amended 2026-06-12: /healthz is a reserved path on Cloud Run,
intercepted by Google's frontend; liveness moved to /health.

## Alternatives Considered

- RFC 7807 Problem Details: richer, machine-parseable; rejected
  for now as heavier than needed for a first-party consumer.
  Our envelope can be wrapped into 7807 later without breaking
  the code registry.
- Offset pagination: rejected on Firestore cost mechanics.
- Single /health endpoint: rejected; conflates probe semantics.

## Consequences

### Positive

- Every endpoint consistent from day one; frontend error
  handling keyed on stable codes.
- Pagination scales within cost baseline.

### Negative

- Cursor tokens are more work than offsets for the frontend.
- Error code registry requires discipline (CI check in Phase 5).

## References

- ADR-0002 (Firestore)
- ADR-0005 (cost baseline)
- Security Charter §Phase 2 (request ID tracing)

## Related ADRs

- ADR-0002: Database Technology (Firestore — informs pagination choice)
- ADR-0005: Cost Baseline (prohibits offset pagination)
- ADR-0007: Auth & Authorization (request_id flows through auth middleware)
