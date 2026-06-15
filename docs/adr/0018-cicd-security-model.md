# ADR-0018: CI/CD Security Model — Keyless Deploys via Direct WIF

## Status
Accepted (2026-06-15)

## Context
Phase 6 automates deployment on merge to main. The charter forbids
static service-account keys. Phase 1 created a Workload Identity
Federation pool + provider (via gcloud) restricting authentication
to this repository's main branch; these were documented in
Terraform as data sources but not managed.

## Decision
- **Direct Workload Identity Federation** (no intermediary deploy
  SA): GitHub Actions' OIDC token is granted deploy roles directly
  via a repo-scoped principalSet. Keyless; no secrets to rotate.
- **Provider attribute condition** restricts authentication to
  repository == this repo AND ref == refs/heads/main. PRs (other
  refs) CANNOT authenticate to GCP — they run gates only. Only main
  deploys. Enforced at the identity layer, not just workflow logic.
- **WIF pool + provider are now Terraform-managed** (imported from
  the Phase-1 gcloud-created resources). Per-environment WIF is the
  same Terraform with a different tfvars (test/prod gain their own
  pool/provider when their projects exist) — the reproducibility
  goal.
- **Deploy permissions** (run.admin, artifactregistry.writer,
  cloudbuild.builds.editor, firebasehosting.admin) granted to the
  CI principalSet; plus serviceAccountUser on the runtime SA
  (sa-cloud-run) so CI can deploy a service that RUNS AS the narrow
  runtime identity — least privilege preserved (CI deploys; the
  service runs as the scoped SA).
- **Cloud Run is deployed via gcloud in CI**, not Terraform-managed
  — the service's image changes every deploy; Terraform managing it
  would create constant drift. Terraform manages the stable infra
  (WIF, IAM); gcloud manages the mutable deploys.

## Consequences
- Test/prod CI setup = terraform apply with new tfvars + the same
  import (or fresh create if their WIF doesn't exist yet).
- The broader activation of dormant Terraform (SAs, APIs, Firestore,
  Artifact Registry, Redis, VPC — currently imperative/commented) is
  a separate IaC-hardening effort (Phase 9 or its own phase).
- Manual `make deploy-*` targets remain as an escape hatch.
