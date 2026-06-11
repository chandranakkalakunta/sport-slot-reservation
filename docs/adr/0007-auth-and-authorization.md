# ADR-0007: Authentication & Authorization

## Status

Accepted — 2026-06-11 | Author: Chandra Nakkalakunta

## Context

Firebase Auth (Email/Password + Google OAuth) issues ID tokens.
The backend must verify tokens, enforce tenant isolation
(ADR-0004 Layer 3), and authorize by role. Roles in Phase 2:
platform_admin, tenant_admin, resident, guest.

## Decisions

### 1. Token verification: firebase-admin only

JWTs are verified exclusively via firebase_admin.auth
.verify_id_token(). It validates signature against Google's
rotating public keys, expiry, audience, and issuer.
python-jose is PROHIBITED in this codebase: it is effectively
unmaintained and carries CVE history (CVE-2024-33663,
CVE-2024-33664). No hand-rolled JOSE handling.

### 2. Custom claims

Set via Firebase Admin SDK at provisioning/role-change time:
tenant_id, tenant_slug, role, household_id. JWT claims are the
source of truth for identity and tenancy on every request; the
request's subdomain is cross-checked against tenant_slug
(ADR-0004 Layer 3). Mismatch → 403 TENANT_MISMATCH.

### 3. Claims staleness: accepted 1-hour window + selective revocation checks

Firebase ID tokens live up to 1 hour; a role change does not
invalidate outstanding tokens. Accepted risk for standard
requests (Tier 2 threat in a community booking context).
Mitigation: endpoints marked SENSITIVE (role changes, tenant
config mutation, bulk operations, future billing mutations)
verify with check_revoked=True, and role/claim changes call
auth.revoke_refresh_tokens(uid). Re-reading the user's role
from Firestore on every request was rejected: it doubles reads
per request, violating ADR-0005 for marginal benefit.
This window is a DOCUMENTED, ACCEPTED risk — revisit in the
Phase 8 security review.

### 4. platform_admin: no tenant bypass

platform_admin tokens carry tenant_id=null and are valid ONLY
on the dedicated admin host (admin.sportbook.chandraailabs.com),
never on tenant subdomains. The tenant cross-check has NO
"skip if admin" branch. Acting inside a tenant requires a
future explicit, audit-logged impersonation feature (Phase 3+,
separate ADR). Rationale: a wildcard bypass would silently
defeat all five ADR-0004 isolation layers.

### 5. Rate limiting: phased placement

Phase 2: slowapi, in-memory, per-user (uid) and per-IP
baselines — accepted limitation: state resets per instance and
is not shared across instances. Phase 3: Redis-backed limits
(Redis exists for booking locks). Phase 7: Cloud Armor edge
limits. This progression is decided now to avoid re-litigation.

### 6. Authorization model

Role checks via FastAPI dependencies (e.g. require_role(
"tenant_admin")) layered on top of TenantContext. Resource-
level ownership checks (a resident sees only their household's
bookings) live in the repository layer (ADR-0004 Layer 2),
not in route handlers.

## Alternatives Considered

- python-jose / PyJWT manual verification: rejected (security
  surface, maintenance).
- Per-request Firestore role lookup: rejected (cost).
- Session cookies (Firebase session management): rejected for
  v1; PWA uses ID token flow; revisit if web-only UX demands it.

## Consequences

### Positive

- No custom crypto; verification delegated to maintained SDK.
- Tenant isolation has no admin-shaped hole.

### Negative

- Up-to-1-hour stale privileges on non-sensitive endpoints
  (documented, accepted).
- Admin host requires DNS + Firebase authorized-domain entry
  (Phase 2.6/4).

## References

- ADR-0004 (isolation layers)
- ADR-0005 (cost)
- Security Charter §Principles (Least Privilege, Verify Don't Trust, Fail Closed)

## Related ADRs

- ADR-0004: Tenant Isolation Strategy (Layer 3 — middleware cross-check this ADR implements)
- ADR-0005: Cost Baseline (prohibits per-request Firestore role lookup)
- ADR-0006: API Design Patterns (request_id header echoed through auth middleware)
