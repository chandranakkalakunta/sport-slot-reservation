# ADR-0017: Deletion, Retention & User/Tenant Lifecycle

Status: Accepted | Date: 2026-06-14 | Author: Chandra Nakkalakunta

## Context
Phase 5 introduces user deactivation and tenant management. We
need a clear, auditable lifecycle model that prevents accidental
data loss while allowing controlled wind-down of tenants or users.
Permanent hard-delete operations on live systems are a liability:
they cannot be undone, audit trails disappear, and foreign
references break silently.

## Decisions

### 1. Three-stage lifecycle for tenants — ACTIVE → INACTIVE → PURGED
Tenant documents carry a `status` field with three allowed values:
- **ACTIVE** — fully operational, all features available.
- **INACTIVE** — soft-deleted; bookings blocked; data retained;
  read-only audit access preserved. Set via platform-admin
  deactivation. Recorded with `deactivated_at` timestamp.
- **PURGED** — hard-deleted by a privileged background job after
  a configurable retention window (default 90 days from
  INACTIVE). Purge is irreversible and must be explicitly
  triggered by a platform-admin script — never triggered by a
  user-facing API call.

Tenant transition rules: ACTIVE→INACTIVE is reversible (re-activate
via platform admin). INACTIVE→PURGED is one-way and gated behind
a separate confirmation step in the purge script.

### 2. User deactivation — soft delete with status + Firebase disable
User documents carry a `status` field (`active` | `inactive`) and
an optional `deactivated_at` timestamp. On deactivation:
1. Profile doc is updated: `status="inactive"`, `deactivated_at=<now>`.
2. Firebase Auth user is disabled (`firebase_admin.auth.update_user(uid, disabled=True)`),
   invalidating all active tokens immediately.
3. All confirmed future bookings for the user are cancelled
   (best-effort; booking docs updated in-place).

User hard-delete is deferred to the PURGED tenant cleanup path
(a tenant purge removes all subcollection data including users).
Standalone user hard-delete is not exposed via API.

### 3. Self-deactivation is forbidden
A user (including a tenant_admin) cannot deactivate their own
account via the API. This prevents accidental lock-out and
ensures at least one active admin always exists. Error:
`SELF_DEACTIVATION_FORBIDDEN` (HTTP 403).

### 4. Audit trail on every lifecycle transition
Every ACTIVE→INACTIVE transition (user or tenant) writes an audit
event per ADR-0011. The event survives in Firestore for the full
retention window even when the user record is soft-deleted.

### 5. No point-in-time restore in v1
PURGED data is permanently gone. Backup + restore via Firestore
managed backups is the recovery path. This is an accepted risk
documented in the security charter.

## Consequences
+ Soft delete gives a recovery window before data is gone.
+ Firebase Auth disable immediately blocks token refresh — no
  stale-session attack surface.
+ Audit trail is preserved through the INACTIVE period.
− Two-stage (INACTIVE + PURGE script) adds operational complexity.
− Cancel-on-deactivate is best-effort; a Firestore transaction
  spanning unbounded bookings is impractical, so cancellation
  is a sequential scan (acceptable for v1 scale).

## References
ADR-0008 (data layout, subcollection structure), ADR-0011
(audit logging), ADR-0014 (admin architecture, seeded admin).
