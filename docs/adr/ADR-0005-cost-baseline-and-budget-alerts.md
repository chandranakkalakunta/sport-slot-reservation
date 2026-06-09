# ADR-0005: Cost Baseline & Budget Alerts

**Status:** Accepted  
**Date:** 2026-06-09  
**Deciders:** Chandra Nakkalakunta

## Context

SportSlotReservation is bootstrapped. There is no VC runway to absorb
a runaway GCP bill. A misconfigured Cloud Run concurrency setting, an
accidental Spanner instance, or a forgotten test environment left
running can generate costs that are painful or unrecoverable at this
stage.

We need to:
1. Establish a realistic cost baseline for the development and early
   production environment.
2. Wire budget alerts before any GCP infrastructure is provisioned.
3. Define what happens when thresholds are breached.

## Decision

### Cost baseline (development environment, single tenant)

Estimates assume `asia-south1` (Mumbai) region, low traffic (< 1,000
bookings/day), and no sustained load.

| Service | Configuration | Estimated monthly cost |
|---------|--------------|----------------------|
| Cloud Firestore | < 50K reads/day, < 10K writes/day, < 1 GB storage | ~$2–5 |
| Cloud Memorystore Redis | Basic tier, 1 GB, `redis-m1-medium` | ~$25–30 |
| Cloud Run (backend) | Min instances: 0, max: 3, 512 MB, 1 vCPU | ~$5–15 (on demand) |
| Firebase Auth | < 10K MAU | Free tier |
| Firebase Hosting | < 10 GB transfer | Free tier |
| Cloud Storage | < 5 GB (build artifacts, exports) | ~$1 |
| BigQuery | < 10 GB storage, < 1 TB queries/month | ~$2–5 |
| Secret Manager | < 10 secrets, < 10K accesses/month | ~$1 |
| Cloud Build / Artifact Registry | < 120 build-minutes/day | ~$3–5 |
| Networking / egress | Minimal cross-region traffic | ~$1–3 |
| **Total dev estimate** | | **~$40–65 / month** |

Redis is the dominant cost. Consider stopping the Memorystore instance
overnight during active development to reduce to ~$15–20/month.

### Budget alerts (Terraform-managed)

Three alert thresholds are wired via `google_billing_budget` Terraform
resource before any infrastructure is deployed:

| Threshold | Action |
|-----------|--------|
| 50% of monthly budget | Email notification to `admin@chandraailabs.com` |
| 80% of monthly budget | Email notification + Slack alert (if configured) |
| 100% of monthly budget | Email notification; manual review required |

Initial monthly budget: **₹6,000 (~$72 USD)** for the development
environment.

Budget alerts are **informational** — GCP does not auto-shutdown
services on threshold breach. Manual intervention is required.

### Cost controls in infrastructure

The following controls are applied in Terraform from day one:

- Cloud Run: `min-instances = 0` in dev; never set `min-instances > 1`
  without a documented justification.
- Cloud Run: `max-instances = 10` hard cap; prevents runaway scale.
- Memorystore: Basic tier only in dev; no HA replica until production.
- BigQuery: Cost controls via `maximum_bytes_billed` on all query jobs.
- No Cloud Spanner, Cloud SQL, or Cloud Bigtable provisioned without
  an explicit ADR revision.
- All GCS buckets have lifecycle rules: delete objects older than 90
  days in `tmp/` prefixes; archive after 30 days in `exports/`.

### What to do when an alert fires

1. Run `gcloud billing budgets describe` to see current spend breakdown.
2. Check for accidental resource creation: `gcloud asset search-all-resources --project=$PROJECT_ID`.
3. Check Cloud Run request volume for traffic anomalies.
4. Check Firestore read/write metrics in Cloud Monitoring.
5. If cause is unclear, set Cloud Run `max-instances = 0` as an
   emergency brake (kills all traffic) while investigating.

## Consequences

**Positive**
- Budget alerts prevent financial surprises during active development.
- Terraform-managed budgets means alerts are version-controlled,
  not configured through a GUI that might be forgotten.
- Cost baseline gives a reality check before production launch.

**Negative / risks**
- Redis dominates the dev cost regardless of usage — it cannot be
  reduced below ~$25/month on the smallest Memorystore tier.
- Budget alerts are notification-only; a runaway job can still exceed
  the budget if not caught quickly.

**Mitigations**
- Alert email goes to `admin@chandraailabs.com` which is monitored daily.
- Redis instance can be stopped manually during idle development periods
  (Memorystore supports stop/start on Basic tier instances).
- A weekly `cost_report.sh` script queries the billing export in BigQuery
  and prints a per-service breakdown.
