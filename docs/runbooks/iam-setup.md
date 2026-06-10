# IAM and Workload Identity Federation Setup

## Overview

SportSlotReservation uses 4 service accounts with least-privilege
IAM roles. GitHub Actions authenticate via Workload Identity
Federation (WIF) — no static credentials are stored.

## Service Accounts

| Name | Email | Purpose |
|------|-------|---------|
| sa-cloud-run | sa-cloud-run@sport-slot-dev.iam.gserviceaccount.com | Runtime for Cloud Run services |
| sa-firebase-admin | sa-firebase-admin@sport-slot-dev.iam.gserviceaccount.com | Firebase Admin SDK |
| sa-cloud-build | sa-cloud-build@sport-slot-dev.iam.gserviceaccount.com | CI/CD deployments |
| sa-monitoring | sa-monitoring@sport-slot-dev.iam.gserviceaccount.com | Observability |

## Workload Identity Federation

**No JSON keys are used.** GitHub Actions authenticate to GCP using
OIDC tokens that GCP federates with our Workload Identity Pool.

### How It Works

1. GitHub Action runs in our repository
2. GitHub generates OIDC token with claims (repo, branch, actor)
3. Action presents token to GCP Workload Identity Pool
4. GCP verifies token signature and matches our attribute conditions
5. GCP issues short-lived (1 hour) credentials for sa-cloud-build
6. Action uses credentials to deploy

### Security Restrictions

WIF authentication is restricted to:
- Repository: chandranakkalakunta/sport-slot-reservation
- Branch: refs/heads/main only

Pull request branches CANNOT deploy. Only merged main commits.

## Permission Growth Plan

Permissions are added incrementally per phase:
- Phase 1.3.2: Baseline operational permissions (this phase)
- Phase 1.3.3: Firebase + Firestore access added
- Phase 2: Redis access added
- Phase 5: Pub/Sub publishing for notifications

## Verification Commands

```bash
# List all SportBook service accounts
gcloud iam service-accounts list \
  --filter="email:sa-*@sport-slot-dev.iam.gserviceaccount.com"

# Check WIF pool exists
gcloud iam workload-identity-pools list --location=global

# View permissions granted to a service account
gcloud projects get-iam-policy sport-slot-dev \
  --flatten="bindings[].members" \
  --filter="bindings.members:sa-cloud-run@sport-slot-dev.iam.gserviceaccount.com" \
  --format="value(bindings.role)"
```

## Disaster Recovery

### If a service account is accidentally deleted:
1. Service accounts have 30-day soft delete
2. Recover: `gcloud iam service-accounts undelete <UNIQUE_ID>`
3. Find unique ID from Cloud Logging audit logs

### If WIF pool is misconfigured:
1. GitHub Actions deployments will fail with auth error
2. Re-run Phase 1.3.2 Steps 10-12
3. Verify with: `gcloud iam workload-identity-pools describe`

## Related ADRs

- ADR-0001: Tech Stack (stateless architecture, no static keys)
- ADR-0004: Tenant Isolation (5-layer defense uses IAM as Layer 1)
