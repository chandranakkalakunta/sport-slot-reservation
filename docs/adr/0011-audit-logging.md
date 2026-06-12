# ADR-0011: Audit Logging

Status: Accepted | Date: 2026-06-12 | Author: Chandra Nakkalakunta

## Context
Booking mutations need a durable, attributable, tenant-queryable
record (charter Phase 3 controls). Candidate destinations:
BigQuery, Cloud Logging, Firestore.

## Decision
Append-only audit events at /tenants/{tenant_id}/audit/{event_id},
written SYNCHRONOUSLY in the same code path as the mutation.
Event shape: event_id, type (booking.created | booking.cancelled),
actor_uid, actor_role, booking_id, request_id, details (map),
ts (UTC). Structlog remains the separate operational layer.

BigQuery is PROHIBITED in the request path: streaming inserts add
200–300 ms per request, and Cloud Run throttles CPU after the
response under request-based billing, making fire-and-forget
post-response writes unreliable. Reporting access to audit data
arrives later via batch export/federation (ADR-0002) at zero
request-path cost. Cloud Logging alone was rejected: retention-
bounded operational telemetry, not a tenant-owned record.

Synchronous-over-async rationale: an audit record that can be
lost on instance death is not an audit record; one Firestore
create costs ~20–40 ms.

## Consequences
+ Tenant-scoped by construction; queryable for future admin
  activity views; trivially exportable.
− One extra write per mutation (accepted).

## References
ADR-0002, ADR-0008, ADR-0010, Charter (Phase 3 controls).
