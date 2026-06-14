# ADR-0014: Admin Architecture & Identity

Status: Accepted | Date: 2026-06-14 | Author: Chandra Nakkalakunta

## Context
Phase 5 introduces two admin surfaces — platform admin (superadmin)
and tenant admin — plus a uniform user-provisioning model. ADR-0007
defined platform_admin as a role valid only with tenant_id=null and
no tenant bypass.

## Decisions

### 1. Admin surfaces are routes, not separate apps
Platform admin lives under /admin/*, tenant admin under /tenant/*,
both within the existing PWA — role-gated client-side and enforced
server-side. DEV relaxes ADR-0007's host-based platform_admin
restriction to route+role gating; dedicated-host hardening is
deferred to Phase 9 and recorded as an accepted exposure in the
charter.

### 2. First superadmin is seeded
A platform admin cannot be self-created (bootstrapping paradox).
A seed script (seed_platform_admin.py) creates the first one:
Firebase user, role=platform_admin, tenant_id=null, custom claims.
Same pattern as the demo users.

### 3. Uniform credential model — generate + force-change
Every user-creation path (superadmin→tenant-admin, tenant-admin→
resident, manual add, CSV import) GENERATES a temporary password,
returns it once to the creator, and sets must_change_password=true
on the profile. No creator ever sets a password directly.

### 4. Forced change-on-first-login
Firebase has no native must-change flag, so a must_change_password
boolean on the profile doc carries it. The frontend checks it
immediately post-login and routes to a forced change-password
screen, blocking other navigation until cleared. Backend exposes
POST /api/v1/users/me/change-password; success clears the flag.
No email dependency (email-based invites deferred to Phase 7).

### 5. Platform-admin endpoint gating
A require_platform_admin dependency (role platform_admin, tenant_id
null) gates platform endpoints — distinct from require_role, which
operates within a tenant.

## Consequences
+ One provisioning model, four call sites; no weak admin-chosen
  passwords.
− A forced-reset screen + flag to maintain.
− Route-based (not host-based) admin gating is a temporary DEV
  posture, logged for Phase 9.

## References
ADR-0007 (auth/roles), ADR-0011 (audit), ADR-0012 (frontend),
Charter (accepted exposures).

> Amendment (2026-06-14): Password reset. Admin-initiated reset is
> available now — a tenant-admin (own tenant, any user incl. peer
> admins) or platform-admin (any tenant) regenerates a temporary
> password and sets must_change_password=true; the new temp password
> is returned once for the admin to distribute. Self-service
> email-based forgot-password is deferred to Phase 7 (notifications).
> Voluntary change-password (logged-in user) uses the existing
> /users/me/change-password endpoint.
