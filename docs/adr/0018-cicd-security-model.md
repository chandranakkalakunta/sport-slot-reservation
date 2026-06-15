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
  cloudbuild.builds.editor, firebasehosting.admin,
  serviceusage.serviceUsageConsumer, storage.admin) granted to the
  CI principalSet; plus serviceAccountUser on the runtime SA
  (sa-cloud-run) so CI can deploy a service that RUNS AS the narrow
  runtime identity — least privilege preserved (CI deploys; the
  service runs as the scoped SA).
  - serviceUsageConsumer: required by `gcloud builds submit` to call
    the Service Usage API before queueing a build.
  - storage.admin (project-level): required for `gcloud builds submit`
    to upload the source tarball to the Cloud Build staging bucket
    (sport-slot-dev-cloudbuild). Project-level is broader than strictly
    necessary; tightening to bucket-scoped storage.admin is deferred
    to Phase 9 least-privilege hardening.
- **Cloud Run is deployed via gcloud in CI**, not Terraform-managed
  — the service's image changes every deploy; Terraform managing it
  would create constant drift. Terraform manages the stable infra
  (WIF, IAM); gcloud manages the mutable deploys.
- **Firebase Hosting is deployed via the REST API** (scripts/deploy_hosting_rest.sh),
  not firebase-tools. Finding (Phase 6.2.10, confirmed via --debug): firebase-tools
  15.x cannot consume a WIF external_account ADC credential — its internal token
  manager found "No OAuth tokens found" and crashed on undefined.access_token even
  though the same ADC credential worked for cloudresourcemanager testIamPermissions.
  firebase-tools only understands `firebase login` user tokens or deprecated login:ci
  refresh tokens. Solution: drive the Firebase Hosting REST API directly. SPA rewrites
  + Cloud Run rewrites from firebase.json are passed in the version-create config body
  so deep links don't 404. Local `make deploy-hosting` still uses firebase-tools
  (interactive login works locally).
- **Direct-WIF federated tokens are rejected by the Firebase Hosting REST API** (401
  UNAUTHENTICATED; token was 1484 chars — not a standard OAuth2 access token, confirmed
  Phase 6.2.13). A real OAuth2 access token requires SA impersonation. Exception to the
  no-intermediary-SA rule: the WIF CI principal is granted
  `roles/iam.serviceAccountTokenCreator` on `sa-firebase-admin` and a dedicated
  `google-github-actions/auth@v3` step with `token_format: access_token` mints a
  scoped token before the Hosting deploy. The main WIF auth step (used by gcloud for
  build/run) remains direct (no SA). Fully keyless: no JSON key stored anywhere.
- **Impersonation shifts IAM requirements from principalSet to the SA** (Phase 6.1.3):
  when the REST deploy sends `X-Goog-User-Project: sport-slot-dev`, the API enforces
  `serviceusage.services.use` against the *impersonated SA's* own IAM — not the WIF
  principalSet. The principalSet already had `serviceUsageConsumer` (6.1.1), but
  `sa-firebase-admin` did not. Added `google_project_iam_member.firebase_admin_service_usage_consumer`
  (`roles/serviceusage.serviceUsageConsumer` on the SA email). General rule: any role
  required for REST calls made with the SA-impersonated token must be granted to the SA,
  not just the principalSet.

## Consequences
- Test/prod CI setup = terraform apply with new tfvars + the same
  import (or fresh create if their WIF doesn't exist yet).
- The broader activation of dormant Terraform (SAs, APIs, Firestore,
  Artifact Registry, Redis, VPC — currently imperative/commented) is
  a separate IaC-hardening effort (Phase 9 or its own phase).
- Manual `make deploy-*` targets remain as an escape hatch.
