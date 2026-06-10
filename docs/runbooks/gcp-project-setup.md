# GCP Project Setup Runbook

This document describes the GCP project setup for SportSlotReservation
DEV environment. Future environments (TEST, PROD) follow the same
pattern with parameterized variables.

## DEV Environment

- **Project ID:** sport-slot-dev
- **Project Number:** 707808711911
- **Region:** asia-south1 (Mumbai)
- **Organization:** chandraailabs.com (833112493322)
- **Billing Account:** 014A8C-586310-DE4575

## Setup Steps Completed (Phase 1.3.1)

1. Project created via `gcloud projects create`
2. Billing account linked
3. Default project set in gcloud config
4. Application Default Credentials (ADC) configured
5. 18 APIs enabled (see project-config.yaml)

## APIs Enabled

Reference: `infrastructure/project-config.yaml`

## Verification Commands

```bash
# Verify project is active
gcloud projects describe sport-slot-dev

# Verify billing is enabled
gcloud billing projects describe sport-slot-dev

# List enabled APIs
gcloud services list --enabled --format="value(config.name)"
```

## Disaster Recovery

If project is accidentally deleted:
1. Project enters 30-day deletion grace period
2. Recover with: `gcloud projects undelete sport-slot-dev`
3. After 30 days, ID is permanently lost

## Related ADRs

- ADR-0001: Tech Stack (Cloud Run, Firestore via GCP)
- ADR-0002: Database Technology (Firestore Native Mode)
- ADR-0005: Cost Baseline (DEV budget ≤₹5K/month)
