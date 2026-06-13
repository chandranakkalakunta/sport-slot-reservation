# ADR-0016: Bulk & Manual User Provisioning

Status: Accepted | Date: 2026-06-14 | Author: Chandra Nakkalakunta

## Context
Creating tenant admins, residents (manual), and residents (bulk
CSV) should share one mechanism rather than three divergent paths.

## Decisions

### 1. Shared provisioning service
A single UserProvisioningService.create_user(tenant_id, email,
display_name, flat_number, role, household_id?) is the ONLY path
that creates users — called by create-tenant-admin, manual add, and
per-row by CSV import. It generates the password, creates the
Firebase user + custom claims, writes the profile with
must_change_password=true, writes an audit event (ADR-0011), and
returns { uid, temp_password }.

### 2. CSV schema
email*, display_name*, flat_number*, role (default resident;
tenant_admin allowed), household_id (optional). (* = required.)

### 3. Household derivation
If household_id is blank, derive "h-" + flat_number (a flat is a
household). Explicit values are honored for edge cases.

### 4. Per-row, partial-success import
Each row is validated and created independently. A results report
returns per row: { row, email, status: created|failed,
temp_password?, reason? }. Duplicate email, missing required field,
or invalid role fails that row with a reason; others proceed. Not
all-or-nothing.

### 5. Endpoints
POST /api/v1/admin/tenants/{id}/users (single/manual) and
POST /api/v1/admin/tenants/{id}/users/bulk (accepts parsed rows as
JSON). The FRONTEND parses the CSV file; the backend stays
file-format-agnostic and unit-testable with JSON. Tenant-admin or
platform-admin gated.

### 6. Bulk safety
Import caps at 500 rows/request to stay within Firebase Auth
creation rate limits; larger imports chunk client-side. Limit is
configurable.

## Consequences
+ One provisioning code path, uniformly audited and credentialed.
+ Partial success: one bad row doesn't fail a large upload.
− Frontend owns CSV parsing (keeps the backend clean/testable).
− Bulk Firebase creation is broadly sequential; large imports take
  time (mitigated by the cap + per-row reporting).

## References
ADR-0007, ADR-0011 (audit), ADR-0014 (credential model).
