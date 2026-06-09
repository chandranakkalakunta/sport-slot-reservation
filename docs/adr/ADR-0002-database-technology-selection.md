# ADR-0002: Database Technology Selection

**Status:** Accepted  
**Date:** 2026-06-09  
**Deciders:** Chandra Nakkalakunta

## Context

The platform needs a primary data store that can handle:

1. **Multi-tenancy** — data from thousands of communities in a single
   system, with hard read/write isolation guarantees per tenant.
2. **Variable schema** — tenants configure different facility types,
   slot durations, pricing rules, and flat structures. A rigid relational
   schema would require frequent migrations or wide nullable columns.
3. **Concurrent writes** — booking slot reservation is a race condition
   scenario; multiple residents can attempt the same slot simultaneously.
4. **Global scale with data sovereignty** — future expansion across
   Indian states and SE Asian countries requires per-region data placement.
5. **Operational simplicity** — no DBA; infrastructure managed by a
   single architect.

### Alternatives considered

| Option | Ruled out because |
|--------|------------------|
| Cloud SQL (PostgreSQL) | Schema migrations for every new tenant config change; connection pooling complexity on Cloud Run; no native multi-region writes |
| Cloud Spanner | Cost prohibitive for a bootstrapped product; operational overhead; overkill for expected write throughput |
| MongoDB Atlas | Third-party dependency outside GCP ecosystem; harder IAM integration; egress costs |
| Bigtable | Not suited for ad-hoc queries or hierarchical document data; no native transactions across rows |
| Firestore (Datastore mode) | Lacks strong-consistency queries and collection-group queries needed for tenant-scoped reporting |

## Decision

Use **Cloud Firestore in Native Mode** as the primary database.

- One Firestore database per GCP project (default database).
- All tenant data lives in the same database; tenants are isolated via
  `tenant_id` field on every document (see ADR-0004).
- Firestore collection structure:
  ```
  tenants/{tenant_id}/
  tenants/{tenant_id}/facilities/{facility_id}
  tenants/{tenant_id}/slots/{slot_id}
  tenants/{tenant_id}/bookings/{booking_id}
  tenants/{tenant_id}/users/{user_id}
  tenants/{tenant_id}/flats/{flat_id}
  tenants/{tenant_id}/invoices/{invoice_id}
  ```
- All write operations that must be atomic use Firestore transactions.
- Slot reservation uses a **Redis distributed lock** (see ADR-0001) as
  the first guard before the Firestore transaction, to prevent hot-write
  contention on popular slots.

## Consequences

**Positive**
- Serverless, fully managed — no provisioning, patching, or scaling knobs.
- Native multi-region replication available without schema changes.
- Flexible schema accommodates per-tenant facility config without migrations.
- Real-time listeners available for future live-availability features.
- CMEK encryption supported; meets compliance baseline.
- Collection-group queries enable cross-tenant reporting for platform admins.

**Negative / risks**
- No joins — denormalization required; must be deliberate about read vs. write paths.
- Document size limit (1 MB) and write rate limit (1 write/sec per document) must be
  respected in booking and invoice designs.
- Firestore query model requires composite indexes declared upfront; missing indexes
  produce runtime errors that only surface under load.
- No aggregation functions — counts and sums must be maintained as counter documents
  or computed in BigQuery.

**Mitigations**
- Redis lock prevents write-rate violations on high-traffic slot documents.
- Booking and invoice IDs are deterministic (uuid.uuid5) making all writes idempotent.
- Composite indexes declared in `firestore.indexes.json` and deployed via CI.
