# ADR-0002: Database Technology Selection

## Status

Accepted — 2026-06-09

## Context

SportBook is a multi-tenant SaaS platform for Indian residential community sports facility management. We must select a database technology that supports our functional requirements, scales to projected growth, fits within the cost constraints of an early-stage product, and provides appropriate resilience characteristics for production use.

This ADR documents not just the decision but the analysis and reasoning behind it, including the data sovereignty architecture, ACID handling pattern, and scaling strategy. Future engineers reading this should understand why this decision was made, what alternatives were considered, and what trade-offs were accepted.

### Requirements Driving This Decision

1. **Functional fit:** Must support multi-tenant data model with strict tenant isolation
2. **Cost optimality:** Must minimize ongoing operational cost during early-stage growth
3. **Scalability:** Must scale from 1 tenant to thousands of tenants without architectural rewrite
4. **Resilience:** Must be zonal-failure agnostic with strong RTO/RPO characteristics
5. **Response time:** Must meet industry-standard usability requirements (sub-200ms typical)
6. **Operational simplicity:** Must be maintainable by a solo developer initially
7. **Data sovereignty:** Must support per-country deployments for global expansion (DPDP Act, GDPR)

### Critical Question — Do We Actually Need ACID Compliance?

A traditional RDBMS provides ACID transactions for every operation. The question we asked was: do we actually NEED that everywhere?

We catalogued every entity in SportBook and its consistency requirements:

| Entity | Volume | Consistency Need |
|---|---|---|
| Tenants | ~200 docs | Eventual OK (slow-changing config) |
| Tenant config | ~200 docs | Eventual OK (cached heavily) |
| Tenant branding | ~200 docs | Eventual OK |
| Users/Residents | ~1M docs | Eventual OK |
| Households/Flats | ~200K docs | Eventual OK |
| Facilities | ~1.6K docs | Eventual OK |
| Sport types | ~1.2K docs | Eventual OK |
| Slots (availability) | High volume | Eventual OK for reads, cached heavily |
| **Bookings** | ~31M/year | **STRONG ACID needed (race condition risk)** |
| Invoices | ~2.4M/year | Strong (financial, immutable once generated) |
| Audit logs | ~100M/year | Append-only, strong |
| Notifications | ~50M/year | Eventual OK |
| Analytics | Aggregations | Run on BigQuery anyway |

**Key insight:** ACID consistency is only critical for ONE operation — booking creation. Everything else operates fine with eventual consistency. This realisation opened the door to NoSQL with a distributed lock pattern for the one operation that needs strict guarantees.

### Scale Projections

Working from realistic assumptions for residential community SaaS:

- **Initial market (Year 1):** ~200 tenants in India, 1,000 units per tenant, 5 residents per unit, 20% active usage
- **Active users:** 200,000
- **Bookings per day:** ~86,000
- **Peak booking rate:** ~43 bookings/second at 20:00 IST window opening
- **Storage growth:** ~50 GB in year 1, ~200 GB by year 3
- **Annual data volume:** ~31 million bookings, ~2.4 million invoices

We deliberately chose 20% active usage instead of the optimistic 30% as the planning baseline. Even at 30%, the load remains well within the capacity envelope discussed below.

### Long-Term Global Scaling Vision

The product strategy includes potential international expansion (UAE, Singapore, UK, others). This affects database choice because:

- **Data sovereignty:** Indian DPDP Act, EU GDPR, Singapore PDPA all require local data residency
- **Latency:** Global users need regional database access
- **Compliance:** Mixing data from multiple jurisdictions creates audit complexity

We decided early that the architecture must support **per-country deployments** rather than a single global database. This is the standard pattern used by SaaS companies operating globally (Slack, Zoom, Notion).

## Options Considered

### Option A — Cloud Firestore (Native Mode)

Google's serverless NoSQL document database with automatic multi-zone replication, strong consistency for single-document operations, and multi-document transaction support up to 500 documents.

**Strengths:**
- Truly serverless — no infrastructure to manage
- Pay-per-operation pricing — extremely cost-friendly at low to medium scale
- Strong consistency for single-document operations
- Multi-document transactions supported (up to 500 docs per transaction)
- Multi-zone replication built-in by default (no configuration required)
- Real-time listeners useful for live slot availability updates
- Excellent Python SDK with mature documentation
- Battle-tested at massive scale (Spotify, Lyft, Twitch)
- Built-in regional failover with sub-minute recovery
- No connection pool management
- Logical multi-tenancy via tenant_id field on every document

**Weaknesses:**
- NoSQL paradigm — requires denormalization (no JOINs)
- Schema-less — application must enforce structure (Pydantic in our case)
- Complex queries limited — no GROUP BY, no aggregations, no window functions
- Composite indexes must be pre-declared
- 1 write per second per document limit (the "hot document" problem)
- Per-operation pricing can surprise at very large scale
- ACID guarantees limited to single document or small transactions

**Projected Cost at SportBook India Scale (200K active residents):**
- Reads (~30M cached / ~10M actual per day): ~$60/month
- Writes (~250K per day): ~$15/month
- Storage (~50 GB): ~$10/month
- **Total: ~$85/month (~₹7,000/month)**

### Option B — Cloud SQL PostgreSQL with Row-Level Security

Managed PostgreSQL service with RLS for tenant isolation, full ACID transactions, complete SQL capabilities, and mature ecosystem.

**Strengths:**
- Full ACID transactions for every operation
- Industry-standard SQL with full query capabilities
- Complex queries trivial (JOINs, GROUP BY, window functions, CTEs)
- Mature ecosystem (ORMs, migration tools, monitoring)
- Row-Level Security enforces tenant isolation at the database layer
- Familiar to most developers
- Excellent for financial aggregations and billing reports
- Easy schema evolution with migrations
- Mature observability tools (pgAdmin, pg_stat_statements)

**Weaknesses:**
- Not serverless — pay 24/7 even when idle
- Minimum production cost is significant
- Connection pool management complexity (PGBouncer required at scale)
- Read replicas need explicit configuration and maintenance
- Manual failover configuration for HA
- Backups need scheduled configuration
- More operational overhead — DB tuning, vacuum, index maintenance
- Cold start issues when accessed from Cloud Run (connection establishment)
- Vertical scaling has limits; horizontal sharding is complex

**Projected Cost at SportBook India Scale:**
- Tier db-custom-2-7680 (recommended for prod): $250/month
- Storage (500 GB SSD): $50/month
- HA replica (zonal HA): $250/month
- Backups: $20/month
- **Total: ~$570/month (~₹47,000/month)**
- DEV environment (minimal): ~₹1,200/month

### Option C — Cloud Spanner (Considered but Ruled Out by Coordinator)

Globally distributed, strongly consistent relational database with horizontal scaling.

**Why ruled out:** Minimum cost is ~$1,000/month even for minimal usage. Designed for problems we don't have (global strong consistency, multi-continent transactions). Massive overkill for SportBook's scale and budget.

### Option D — AlloyDB (Considered but Ruled Out by Coordinator)

PostgreSQL-compatible database optimized for analytical and transactional workloads.

**Why ruled out:** Designed for migrating from existing PostgreSQL workloads. We have no PostgreSQL compatibility requirements. Higher cost than Cloud SQL without commensurate benefit for our use case.

## Decision

**Cloud Firestore (Native Mode)** as the primary database for SportBook.

### Supporting Architectural Patterns

The Firestore decision is supported by two complementary architectural patterns:

1. **Distributed Lock Pattern for ACID-Critical Operations**
   - Cloud Memorystore Redis is used as a distributed lock store
   - Booking creation acquires a lock before reading slot availability
   - Only one Cloud Run instance can hold the lock at a time
   - Firestore transactions provide atomic writes within the locked operation
   - This combination provides ACID-equivalent guarantees for booking creation

2. **Per-Country Deployment Architecture**
   - Each country gets its own complete deployment (GCP project + Firestore + Redis)
   - Data residency satisfied by design
   - Independent scaling per country
   - Independent failure domains
   - Same codebase, parameterized Terraform variables per country

## Rationale

### Why Firestore Wins for SportBook

We chose Firestore based on a structured analysis against our requirements:

| Requirement | Firestore | Cloud SQL | Winner |
|---|---|---|---|
| Cost optimal | ~₹7K/month | ~₹47K/month | **Firestore** (85% savings) |
| Highly scalable | Scales automatically | Requires sharding | **Firestore** |
| Zonal failure resistant | Multi-zone default | Needs HA setup | **Firestore** |
| Better RTO/RPO | Built-in multi-region | Configured replication | **Firestore** |
| Response time | Sub-100ms typical | Sub-50ms typical | Cloud SQL (marginally) |
| ACID for bookings | Via distributed lock | Native | Cloud SQL |
| Multi-tenant isolation | Logical (tenant_id) | RLS | Both equivalent |
| Operational overhead | None | Significant | **Firestore** |

Firestore wins on 6 of 8 dimensions, ties on 1, and loses only on raw response time (where the difference is invisible to users) and native ACID (where the distributed lock pattern compensates).

### The ACID Question Resolved

The one apparent weakness of Firestore — limited ACID guarantees — is resolved by the distributed lock pattern. This is not a workaround but the industry-standard pattern for high-concurrency booking systems:

- **Uber** uses distributed locks for ride matching
- **Airbnb** uses distributed locks for room availability
- **Lyft** uses distributed locks for driver assignment
- **Banking systems** use similar patterns for transaction processing

Combined with Firestore's native multi-document transactions, the distributed lock provides the strict isolation needed for booking creation while keeping everything else simple and cheap.

### Cost Justification

For an early-stage product, the 85% cost difference is decisive. At ~₹40K/month savings, this translates to ~₹5L/year that can be reinvested into development, infrastructure for additional countries, or sustaining the business through the early growth phase. Cloud SQL only becomes preferable when the developer cost of working around Firestore's NoSQL limitations exceeds the operational cost savings — which we judge to be well above SportBook's foreseeable scale.

### Operational Simplicity

SportBook starts as a solo-developer project. Operating a production PostgreSQL HA setup (with PGBouncer, read replicas, backup verification, vacuum tuning, and connection management) while simultaneously building features is not realistic for a single developer. Firestore is genuinely set-and-forget. This operational simplicity is itself a major architectural value.

### Resilience by Default

Firestore's automatic multi-zone replication provides excellent resilience without any configuration. RTO for a zonal failure is measured in seconds, with no data loss. Cloud SQL would require explicit HA configuration, regular failover testing, and ongoing operational vigilance to achieve similar guarantees.

## Distributed Lock Pattern — Detailed Design

### How It Works

For the critical booking creation flow, the system uses Redis as a distributed lock store:

```
Step 1: Acquire lock
  Redis: SET lock:slot-{slot_id} = {request_uuid}
         NX (only set if key doesn't exist)
         EX 10 (auto-expire after 10 seconds)
  Result: Either "lock acquired" or "lock already held"

Step 2: If lock acquired, proceed:
  - Read slot from Firestore (verify still available)
  - Read user's daily booking count
  - Validate against household quota
  - Validate against tenant policy
  - Write booking to Firestore (atomic transaction)
  - Update slot status atomically

Step 3: Release lock
  Redis: DELETE lock:slot-{slot_id}
         (with Lua script to verify our UUID matches —
          prevents accidentally releasing someone else's lock)

Step 4: If lock NOT acquired:
  - Return 409 Conflict to client immediately
  - Client message: "Slot just got booked, please try another"
```

### Concurrent Booking Scenario

```
20:00:00.000 — Booking window opens
20:00:00.012 — Resident A clicks "Book Tennis Court B, 7pm"
20:00:00.014 — Resident B clicks "Book Tennis Court B, 7pm"
20:00:00.018 — Resident C clicks "Book Tennis Court B, 7pm"

All three requests reach Cloud Run within 18ms.
Cloud Run scales to 3 instances to handle them.

Instance 1 (handling A): SET lock:slot-123 ... → SUCCESS
Instance 2 (handling B): SET lock:slot-123 ... → FAILS (already exists)
Instance 3 (handling C): SET lock:slot-123 ... → FAILS (already exists)

Instance 1 continues: reads slot, validates, writes booking, releases lock.
Total time: ~50-100ms.

Instances 2 and 3: return 409 immediately to clients.
Clients show: "That slot was just booked. Please try another time."

Result: Exactly one booking. No double-bookings possible.
```

### Redis Failure Handling

**What if Redis is unavailable?**

We chose the **fail-closed** policy:

- If Redis is unreachable, the booking endpoint returns 503 Service Unavailable
- Users see clear messaging: "Booking system is temporarily unavailable. Please try again in a few minutes."
- Read operations (browsing facilities, viewing past bookings, checking schedules) continue to work because they don't require Redis
- Only write operations that need consistency guarantees are blocked

This is the same approach taken by banks, payment processors, and ride-sharing services. The principle: data integrity is more important than uptime for critical operations.

**Mitigation strategies layered:**

1. **Memorystore HA tier in production:** Automatic failover to replica in different zone, ~30 second recovery, ~50% cost premium
2. **Application-side retry with backoff:** 3 retries at 100ms, 300ms, 1s before failing — handles transient failures
3. **Cloud Monitoring alerts:** Page admin within 1 minute of Redis health degradation
4. **Disaster recovery runbook:** New Redis instance spun up via Terraform if needed, ~10 minute total recovery

**Real-world impact:**

Memorystore Redis SLA is 99.9% (43 minutes/month maximum downtime). Reality is typically 99.95-99.99% (5-22 minutes/month). During those minutes:
- Reads continue normally (Firestore is independent)
- Writes pause with clear user messaging
- Most outages auto-recover in under 1 minute
- Manual recovery available if needed

We judge this acceptable for residential community sports booking. Far better than allowing double-bookings.

## Global Scaling and Multi-Country Architecture

### Firestore Capacity Headroom

Firestore Native Mode limits per database:

- 10,000 writes per second sustained
- Burst capacity up to 50,000 writes per second
- 1 write per second per individual document (the hot document constraint)
- Unlimited storage (pay per GB)
- 200 composite indexes maximum

For SportBook scale scenarios:

| Scenario | Active Users | Peak Writes/sec | Firestore Capacity Used | Verdict |
|---|---|---|---|---|
| Year 1 (India only) | 200,000 | 43 | 0.4% | Trivial |
| Year 2 (multi-region) | 2,000,000 | 430 | 4.3% | Comfortable |
| Year 3+ (massive) | 10,000,000 | 2,150 | 21.5% | Still fine |
| Theoretical max | 50,000,000 | 10,000 | 100% | Would need sharding |

The capacity headroom is enormous. We would hit business limits (total addressable market) long before technical limits.

### Per-Country Deployment Strategy

Rather than scale a single global database, SportBook uses independent per-country deployments:

```
                    ┌─ Global Platform ─┐
                    │  admin.chandra      │
                    │   ailabs.com        │
                    │  (cross-country     │
                    │   reporting only)   │
                    └─────────┬──────────┘
                              │
                              │ BigQuery federation
                              │ for global metrics
                              ▼
      ┌─────────────┬─────────────┬─────────────┐
      │             │             │             │
   ┌──┴────┐    ┌───┴────┐    ┌─────┴────┐    ┌───┴────┐
   │ INDIA │    │  UAE   │    │ SINGAPORE │    │  UK   │
   ├───────┤    ├────────┤    ├──────────┤    ├───────┤
   │ Cloud │    │ Cloud  │    │  Cloud   │    │ Cloud │
   │  Run  │    │  Run   │    │   Run    │    │  Run  │
   │       │    │        │    │          │    │       │
   │ Fires │    │ Fires  │    │  Fires   │    │ Fires │
   │ tore  │    │ tore   │    │  tore    │    │ tore  │
   │       │    │        │    │          │    │       │
   │ Redis │    │ Redis  │    │  Redis   │    │ Redis │
   └───────┘    └────────┘    └──────────┘    └───────┘
```

Each deployment:

- Independent GCP project (e.g., sportbook-prod-india, sportbook-prod-uae)
- Regional Firestore in that country's region
- Country-specific Cloud Run services
- Country-specific Redis instance
- Same codebase, same Docker images
- Parameterized Terraform variables for region-specific values
- Country-specific compliance configurations (DPDP, GDPR, PDPA)

### Cross-Country Reporting

While operational data stays in-country, the platform admin needs global visibility:

- Each country's Firestore exports nightly to BigQuery in same region
- BigQuery federated queries aggregate across countries for global reports
- No operational data movement, only aggregated analytics
- Compliance maintained — raw data never leaves the country

### Phased Rollout

The architecture supports growth without architectural rewrites:

```
Year 1 — India only
  asia-south1, single deployment
  ~200 tenants, ~₹10K/month total

Year 2 — Expansion to 1 additional country
  India + (UAE or Singapore)
  2 independent deployments
  ~500 tenants total, ~₹30K/month total

Year 3+ — Multi-country growth
  Each new country = new deployment
  Independent scaling, independent costs
  Linear cost scaling
```

This is exactly how Slack, Zoom, Notion, and other global SaaS products handle international expansion. The architecture is proven.

## Consequences

### Positive

- **85% cost reduction** vs Cloud SQL during early stage (~₹40K/month savings)
- **Zero database operational overhead** — no DBA work needed
- **Built-in multi-zone resilience** — no HA configuration required
- **Automatic scaling** — no capacity planning, no manual sharding
- **Real-time capabilities** — live slot availability updates supported natively
- **Strong consistency where needed** — single-document operations are strongly consistent
- **Battle-tested at scale** — used by major SaaS companies
- **Architecture supports global expansion** — per-country deployments straightforward
- **Aligned with serverless principles** — fits perfectly with Cloud Run stateless services
- **Same database used in Old SportBook** — proven to work for this use case

### Negative

- **Denormalization required** — must duplicate data across documents (e.g., tenant_name in every booking)
- **No JOINs** — cross-collection queries require multiple round trips or BigQuery
- **Limited aggregations** — counting, summing requires either client-side aggregation or BigQuery
- **Schema enforcement in application** — Pydantic models must be the source of truth for structure
- **Composite indexes need declaration** — query patterns must be considered upfront
- **Hot document risk** — must architect to avoid >1 write/sec on any single document
- **Less familiar than SQL** for developers from traditional backgrounds

### Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Hot document on global counters | Medium | Use distributed counter pattern (sharding) |
| Composite index limit (200) hit | Low | Design query patterns minimally; monitor usage |
| Redis outage stops bookings | Low | HA tier in PROD, retry logic, monitoring, fail-closed policy |
| NoSQL learning curve | Medium | Mitigated by prior Firestore experience |
| Complex reports need workaround | High | Architected via BigQuery from Phase 4 onwards |

## Alternatives Rejected

### Cloud SQL PostgreSQL with RLS

**Why rejected:** 7x higher cost (~₹47K vs ~₹7K/month), significant operational overhead, requires explicit HA configuration, and provides ACID benefits only needed for booking creation (which we handle elegantly with distributed locks). The cost difference alone makes this infeasible for an early-stage product.

### Cloud Spanner

**Why rejected:** Minimum cost (~$1,000/month) is prohibitive. Designed for problems we don't have (global strong consistency, multi-continent ACID transactions). Massive overkill.

### AlloyDB

**Why rejected:** Designed for PostgreSQL migration workloads. We have no PostgreSQL compatibility needs. Higher cost than Cloud SQL without offsetting benefits.

### MongoDB / DocumentDB

**Why rejected:** Adds operational complexity that Firestore eliminates. No clear advantage over Firestore for our use case. Would require third-party hosting or self-management.

## References

- Cloud Firestore documentation: https://cloud.google.com/firestore/docs
- Firestore quotas and limits: https://cloud.google.com/firestore/quotas
- Cloud Memorystore Redis: https://cloud.google.com/memorystore/docs/redis
- Distributed locking pattern: https://redis.io/docs/manual/patterns/distributed-locks/
- India Digital Personal Data Protection Act: https://www.meity.gov.in/data-protection-framework
- Companies using Firestore at scale: Spotify (engineering blog), Lyft (data infrastructure case studies)
- Multi-region SaaS architecture patterns: AWS Well-Architected Framework, Google Cloud Architecture Center

## Related ADRs

- ADR-0001: Tech Stack & Software Versions (chose Python + FastAPI, supports Firestore)
- ADR-0004 (planned): Tenant Isolation Strategy (will detail tenant_id approach)
- ADR-0005 (planned): Cost Baseline (uses these projections)
- Future ADR: Distributed Lock Implementation Details (will detail Redis pattern)
