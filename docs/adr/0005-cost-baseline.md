# ADR-0005: Cost Baseline & Budget Alerts

## Status

Accepted — 2026-06-09

## Context

SportBook is a self-funded early-stage product. Cost surprises are the leading cause of side projects failing. Old SportBook (the previous deployment) hit ~₹17,000/month largely due to an unrelated Vertex AI MLOps endpoint left running with `min-instances=1` — costing ~₹15,000/month for an idle ML model. While that specific cost was from another project, it demonstrates how easy it is for cloud costs to escalate without active management.

This ADR establishes clear cost budgets per environment, defines cost-saving strategies, and configures automated alerts and hard limits to prevent overruns. The goal is sustainable development within a disciplined budget while preserving the ability to scale up when real revenue justifies it.

### Requirements

1. **DEV environment budget:** ≤ ₹5,000/month during active development
2. **Per-tenant cost target:** ≤ ₹2,000/month/tenant at production scale (industry-aligned)
3. **Hard limits:** Automated actions when budgets are exceeded
4. **Multi-tier alerting:** Daily dashboard reviews AND weekly summary emails
5. **Cost visibility:** Per-service cost breakdown always available
6. **Scaling strategy:** Clear triggers for when to add capacity vs optimize
7. **DEV/TEST/PROD isolation:** Each environment has its own budget

### Why This ADR Matters Now

Cost decisions made in Phase 0 affect every subsequent phase:

- Service selection (Cloud Run vs always-on alternatives) is shaped by cost
- Environment activation strategy depends on cost ceilings
- Resource sizing (Cloud Run memory, Redis tier) is cost-driven
- Caching strategy is cost-driven (more cache = less Firestore reads)
- Monitoring tier selection is cost-driven

Without this baseline, every future decision risks being made without cost awareness.

## Cost Estimates by Service

### DEV Environment — Target: ≤ ₹5,000/month

The DEV environment runs continuously for active development. All services are sized at minimum cost.

| Service | Configuration | Monthly Cost (₹) |
|---|---|---|
| Cloud Run (backend) | min=0, max=5, 512MB | 100 – 400 |
| Cloud Run (frontend) | min=0, max=3, 256MB | 50 – 200 |
| Firestore | Free tier covers most | 0 – 500 |
| Memorystore Redis | Basic tier, 1GB | 2,500 (fixed) |
| Secret Manager | ~10 secrets | 0 (free tier) |
| Cloud Build | ~50 builds/month | 0 – 200 |
| Cloud Storage | ~5 GB | 50 |
| Artifact Registry | ~10 GB Docker images | 100 |
| Cloud Logging | 50 GB free tier | 0 – 100 |
| Cloud Monitoring | Basic dashboards | 0 (free tier) |
| BigQuery | 1 TB queries free | 0 – 200 |
| Networking | < 1 GB egress | 0 |
| **TOTAL** | | **2,800 – 4,750** |
| **Headroom to ₹5,000** | | **250 – 2,200** |

### The Redis Reality

Memorystore Redis is the largest fixed cost in DEV. It cannot scale to zero because it holds state (distributed locks, cache). Three strategies were considered:

**Option A — Keep Cloud Memorystore Redis running continuously**
- Cost: ₹2,500/month fixed
- Benefit: Realistic cloud testing environment
- Recommended for Phase 2 onwards

**Option B — Delete and recreate Redis for sprints**
- Cost: ₹0 when not in use
- Operational overhead: ~30 minutes per delete/recreate cycle
- Useful during extended breaks (vacation, between phases)

**Option C — Use local Redis (Docker on Mac) for DEV**
- Cost: ₹0
- Caveat: Not realistic — doesn't test cloud connectivity, IAM, networking
- Useful for Phase 0/1 only

**Decision:** 
- Phase 0/1: Local Redis via Docker (₹0)
- Phase 2 onwards: Cloud Memorystore Basic tier (₹2,500/month)
- Delete during extended breaks where no development is planned

### TEST Environment — Activated On-Demand

TEST environment is identical to PROD but only spun up when needed:

| Activation Scenario | Monthly Cost |
|---|---|
| Idle (not active) | ₹0 (deleted) |
| Active for 1 week (validation cycle) | ~₹1,500 |
| Active for full month (rare) | ~₹6,500 |

TEST follows the deploy-validate-destroy pattern. Cost is deliberately variable based on validation needs.

### PROD Environment — Projections at Scale

**Per-tenant target: ≤ ₹2,000/month/tenant**

At 200 tenants (Year 1 target), the per-tenant cost should be well below the target:

| Service | Cost at 200 tenants | % of Total |
|---|---|---|
| Cloud Run (backend) | ₹8,000 | 21% |
| Cloud Run (frontend) | ₹2,000 | 5% |
| Firestore | ₹8,000 | 21% |
| Memorystore Redis (HA tier) | ₹15,000 | 39% |
| Cloud Build | ₹1,000 | 3% |
| BigQuery | ₹2,000 | 5% |
| Storage | ₹500 | 1% |
| Monitoring | ₹500 | 1% |
| Networking | ₹2,000 | 5% |
| **TOTAL** | **₹39,000** | **100%** |
| **Per-tenant cost** | **₹195/month** | |
| **Target** | **≤ ₹2,000/month** | |
| **Margin** | **~90% under target** | |

This 90% margin provides:
- Buffer for unexpected growth
- Capacity for features that increase cost (e.g., AI agent operations)
- Room for high-traffic tenants (large communities)
- Headroom before optimization is needed

### Cost Growth Projections

| Stage | Tenants | Monthly Cost | Per-Tenant |
|---|---|---|---|
| Year 1 Q1 | 10 (alpha) | ₹15,000 | ₹1,500 |
| Year 1 Q3 | 50 | ₹22,000 | ₹440 |
| Year 1 Q4 | 200 | ₹39,000 | ₹195 |
| Year 2 | 500 | ₹70,000 | ₹140 |
| Year 3 | 1,000 | ₹130,000 | ₹130 |
| Year 3 (multi-country) | 2,000 across countries | ₹260,000 | ₹130 |

Cost scales sub-linearly with tenants due to:
- Shared infrastructure (Cloud Run scales efficiently)
- Better cache hit rates at scale
- Per-tenant overhead amortizes
- Reserved discounts for committed use

## Budget Alerts — Multi-Tier Strategy

The alerting strategy uses progressive thresholds with escalating actions. This balances visibility with avoiding alert fatigue.

### DEV Environment Thresholds

```
THRESHOLD 1 — Awareness (50% of budget)
  Trigger:   Monthly cost > ₹2,500
  Action:    Email to admin@chandraailabs.com
  Tone:      Informational
  
THRESHOLD 2 — Caution (75% of budget)
  Trigger:   Monthly cost > ₹3,750
  Action:    Email + SMS
  Tone:      "Approaching budget — review needed"
  
THRESHOLD 3 — Action (100% of budget)
  Trigger:   Monthly cost > ₹5,000
  Action:    Email + SMS + automated actions:
             - Cloud Run min-instances set to 0
             - Non-critical scheduled jobs paused
             - Cost dashboard auto-opens in admin email
  Tone:      "Hard limit reached — automatic action taken"
  
THRESHOLD 4 — Emergency (120% of budget)
  Trigger:   Monthly cost > ₹6,000
  Action:    Page admin immediately:
             - Cloud Run services return 503
             - All non-critical jobs stopped
             - Manual intervention required
  Tone:      "Emergency — budget exceeded by 20%"
```

### PROD Environment Thresholds

PROD thresholds are proportional but more permissive given that high cost likely correlates with high revenue:

```
THRESHOLD 1 — Awareness: 80% of projected monthly cost
THRESHOLD 2 — Caution:   100% of projected monthly cost
THRESHOLD 3 — Action:    120% of projected monthly cost
THRESHOLD 4 — Emergency: 150% of projected monthly cost
```

Per-tenant cost anomaly threshold: > ₹3,000/month/tenant triggers automatic investigation.

## Cost-Saving Strategies

### Strategy 1 — Aggressive min-instances Management

Cloud Run cost is dominated by always-on instances. Strategy:

| Environment | min-instances Strategy |
|---|---|
| DEV | Always 0 (cold starts acceptable) |
| TEST | Always 0 (used only during validation) |
| PROD | Time-based: 1 during 18:00-22:00 IST (booking window), 0 overnight |

Implementation via Cloud Scheduler:
```
Daily 18:00 IST: Set sportbook-api min-instances=1
Daily 22:00 IST: Set sportbook-api min-instances=0
```

Estimated savings: ~₹6,000/month in PROD vs always-on.

### Strategy 2 — Aggressive Caching for Firestore Reads

Firestore charges per read. Most reads are repeatable (slot availability, tenant config, facility list).

Cache strategy:
- Tenant config: 1 hour TTL in Redis
- Facility list: 30 minutes TTL
- Slot availability: 10 seconds TTL (real-time enough)
- User profile: 5 minutes TTL

Estimated effect: 80%+ cache hit rate → 80% reduction in Firestore reads → ~₹6,400/month saved at 200 tenants.

### Strategy 3 — TEST Environment Auto-Destroy

TEST environment uses Terraform to spin up complete infrastructure on demand and destroy when validation complete.

```
make spin-up-test     → Create TEST environment (~20 minutes)
make run-validation   → Run automated validation suite
make destroy-test     → Delete entire TEST environment

Result: TEST costs only what's used during active validation.
```

### Strategy 4 — Free Tier Maximization

Several services have generous free tiers that cover SportBook's DEV usage entirely:

- Firestore: 50K reads, 20K writes, 1GB storage per day FREE
- Cloud Logging: 50 GB per month FREE
- Cloud Monitoring: Basic dashboards FREE
- BigQuery: 1 TB queries per month FREE
- Secret Manager: 6 active secrets and 10K access operations FREE

Architectural choices should maximize use of these free tiers in DEV.

### Strategy 5 — Reserved Discounts for Committed Use

When PROD reaches stable scale (Year 2+), Google offers Committed Use Discounts:

- 1-year commitment: ~25% discount on Cloud Run
- 3-year commitment: ~50% discount on Cloud Run

This is a Phase 8+ optimization. Not relevant during early stages where commitment risk outweighs savings.

## Monitoring & Visibility

### Daily Dashboard

A single Cloud Monitoring dashboard provides cost visibility at a glance:

**Dashboard sections:**
1. Total month-to-date spend (gauge with budget overlay)
2. Daily spend trend (last 30 days)
3. Per-service cost breakdown (pie chart)
4. Per-environment breakdown (DEV/TEST/PROD)
5. Top 5 cost drivers (table)
6. Anomalies detected (last 7 days)

Dashboard accessible at:
```
https://console.cloud.google.com/monitoring/dashboards/custom/sportbook-cost
```

### Weekly Summary Email

Every Monday at 09:00 IST, an automated email is sent to admin@chandraailabs.com containing:

1. Previous week total spend
2. Comparison to same week previous month
3. Top 3 cost increases
4. Any anomalies or alerts triggered
5. Projected month-end total
6. Quick action links (dashboard, billing page, alert config)

Implementation: Cloud Scheduler triggers Cloud Function that queries Cloud Billing API and sends formatted email.

### Per-Service Cost Attribution

All resources tagged with labels:

```
Required labels on every resource:
  environment: dev | test | prod
  service: backend | frontend | scheduler | etc.
  managed-by: terraform
  cost-center: sportbook
  tenant_id: <tenant_id> | shared  (for resources unique to tenant)
```

This enables filtering and grouping costs by any dimension in the billing console.

## Hard Limits — Implementation Details

When Threshold 3 (100% of budget) is reached, automated actions execute:

### DEV Hard Limit Actions

```python
# Triggered by Cloud Monitoring alert via Pub/Sub
def dev_budget_exceeded_handler():
    # 1. Cap Cloud Run scaling
    for service in ['sportbook-api', 'sportbook-frontend']:
        gcloud.run.services.update(
            service, region='asia-south1', project='sportbook-dev',
            args=['--min-instances=0', '--max-instances=2']
        )
    
    # 2. Pause non-critical scheduled jobs
    for job in ['analytics-export', 'log-rotation', 'cache-warmup']:
        gcloud.scheduler.jobs.pause(job)
    
    # 3. Email admin
    send_email(
        to='admin@chandraailabs.com',
        subject='[BUDGET LIMIT] DEV budget reached — automated actions taken',
        body=ACTIONS_TAKEN_TEMPLATE
    )
    
    # 4. Cannot stop: Redis (loses data), Firestore (would break app)
```

### Override Mechanism

Admin can override the budget cap (with explicit confirmation):

```
make override-budget-dev
  ⚠️ This will resume normal operations.
  Type exactly: "override DEV budget for July 2026"
  > _
  
  ✅ Override applied. Next budget cycle resumes normal limits.
```

The override is logged and creates an audit entry.

## Cost Decision Triggers

These rules define WHEN to invest more in infrastructure:

```
TRIGGER: Add Redis caching for slot queries
WHEN: Firestore read cost > ₹5,000/month
WHY: Cache reduces costs by 80%+

TRIGGER: Upgrade Cloud Run instance size
WHEN: P95 latency > 500ms for 3 consecutive days
WHY: User experience degrades

TRIGGER: Add CDN for static assets
WHEN: Frontend egress > 100 GB/month
WHY: CDN cheaper than direct serving at scale

TRIGGER: Migrate to BigQuery for heavy analytics
WHEN: Firestore aggregation queries > 10/day
WHY: Wrong tool for the job

TRIGGER: Commit to 1-year reserved instances
WHEN: Cloud Run cost > ₹20,000/month for 3 consecutive months
WHY: Stable baseline justifies commitment

TRIGGER: Deploy second country
WHEN: Demand in target country justifies investment
WHY: Per-country deployment from ADR-0002
```

These triggers prevent both premature optimization and underinvestment.

## Consequences

### Positive

- **Clear budget visibility** — no surprises about cloud costs
- **Sustainable development** — fits within ₹5,000/month constraint
- **Scalable economics** — per-tenant cost decreases with scale
- **Automated safety net** — hard limits prevent runaway costs
- **Multi-tier alerting** — appropriate response at each threshold
- **Per-service visibility** — quick identification of cost drivers
- **Decision framework** — clear triggers for when to scale up

### Negative

- **Cold start latency in DEV** — min-instances=0 means slower first requests
- **Operational overhead** — must manage budget overrides occasionally
- **Override complexity** — hard limits can interrupt work if poorly tuned
- **Redis fixed cost** — ₹2,500/month always required in cloud DEV

### Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Sudden traffic spike exceeds budget | Medium | Auto-scaling caps prevent runaway, alerts notify quickly |
| Forgot to delete TEST environment | High | Terraform destroy is part of make command |
| Free tier limits change | Low | Quarterly review of pricing |
| Currency fluctuation affects cost | Low | Budgets set in INR, GCP billing in USD ~5-10% variation |
| Cost spike from misconfigured service | Medium | Threshold 1 alert (50%) catches early |

## Alternatives Rejected

### Pure Pay-As-You-Go Without Limits

**Why rejected:** Old SportBook proved that without limits, costs escalate silently. ₹17,000/month surprise demonstrated the danger.

### Soft Alerts Only (No Hard Actions)

**Why rejected:** Coordinator explicitly chose hard limits with auto-actions. Manual response to alerts is unreliable for solo developer.

### No Budget Tracking (Just Watch Invoices)

**Why rejected:** Invoice arrives end of month. Too late to react. Daily/weekly monitoring catches issues in hours, not weeks.

### Aggressive Cost Optimization From Day 1

**Why rejected:** Optimizing too early creates complexity without measurable benefit. Use simple defaults until triggers indicate need for optimization.

## References

- Google Cloud Billing budget alerts: https://cloud.google.com/billing/docs/how-to/budgets
- Cloud Run pricing: https://cloud.google.com/run/pricing
- Firestore pricing: https://cloud.google.com/firestore/pricing
- Cloud Memorystore pricing: https://cloud.google.com/memorystore/pricing
- SaaS cost benchmarks: industry reports indicate infrastructure ~10-20% of revenue

## Related ADRs

- ADR-0001: Tech Stack (Cloud Run choice driven partly by cost)
- ADR-0002: Database Technology (Firestore chosen for cost efficiency)
- ADR-0003: Build Tooling (Make + bash chosen as zero-cost option)
- ADR-0004: Tenant Isolation (logical isolation chosen for cost efficiency)
- Future ADR: Performance & Caching Strategy (cost-driven cache layer)
- Future ADR: Disaster Recovery Plan (backup strategy has cost implications)
