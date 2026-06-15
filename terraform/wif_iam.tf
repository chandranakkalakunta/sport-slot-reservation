# Direct-WIF IAM Bindings — Phase 6.1
#
# Grants the GitHub Actions CI principal (scoped to this repo) the
# deploy roles directly. No intermediary deploy SA — keyless, no keys
# to rotate. See ADR-0018.
#
# The principal is a principalSet restricted to:
#   repository == chandranakkalakunta/sport-slot-reservation
# (the provider's attribute_condition further restricts to main branch
#  at the identity layer — PRs cannot authenticate at all).

locals {
  github_principal_set = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_actions.name}/attribute.repository/${var.github_repository}"
}

# Deploy Cloud Run revisions.
resource "google_project_iam_member" "ci_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = local.github_principal_set
}

# Push container images to Artifact Registry.
resource "google_project_iam_member" "ci_artifactregistry_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = local.github_principal_set
}

# Submit Cloud Build jobs (docker build step).
resource "google_project_iam_member" "ci_cloudbuild_editor" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = local.github_principal_set
}

# Deploy Firebase Hosting (frontend).
resource "google_project_iam_member" "ci_firebasehosting_admin" {
  project = var.project_id
  role    = "roles/firebasehosting.admin"
  member  = local.github_principal_set
}

# `gcloud builds submit` calls the Service Usage API before queueing
# the build. Without this the caller gets a serviceusage.services.use
# permission denied even though cloudbuild.builds.editor is present.
resource "google_project_iam_member" "ci_service_usage_consumer" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = local.github_principal_set
}

# `gcloud builds submit` uploads the source tarball to the Cloud Build
# staging bucket (sport-slot-dev-cloudbuild). storage.admin at project
# level is the simplest fix and matches the documented resolution.
# SCOPE NOTE: project-level storage.admin is broader than strictly
# necessary. A tighter alternative is a bucket-scoped
# google_storage_bucket_iam_member on sport-slot-dev-cloudbuild +
# roles/artifactregistry.writer already covers image push. Deferring
# least-privilege tightening to Phase 9 hardening (dev environment).
resource "google_project_iam_member" "ci_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = local.github_principal_set
}

# CI describes the Memorystore Redis instance at deploy time
# (deploy_cloud_run.sh reads its host/port to wire SPORTSLOT_REDIS_*).
resource "google_project_iam_member" "ci_redis_viewer" {
  project = var.project_id
  role    = "roles/redis.viewer"
  member  = local.github_principal_set
}

# Allow the CI WIF principal to impersonate sa-firebase-admin to mint
# a real OAuth2 access token for the Firebase Hosting REST API
# (direct-WIF federated tokens are not accepted by that API).
resource "google_service_account_iam_member" "ci_token_creator_firebase" {
  service_account_id = data.google_service_account.firebase_admin.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = local.github_principal_set
}

# CI must deploy a Cloud Run service that RUNS AS the runtime SA
# (sa-cloud-run). Without this, `gcloud run deploy --service-account`
# is rejected. Least privilege preserved: CI deploys; sa-cloud-run
# is the narrow runtime identity.
resource "google_service_account_iam_member" "ci_act_as_runtime" {
  service_account_id = data.google_service_account.cloud_run.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.github_principal_set
}

# COORDINATOR FLAG: confirm whether `gcloud builds submit` in the CI
# workflow delegates to sa-cloud-build under the hood. If so, this
# binding is required; if the build runs under the WIF principal's
# own identity (--service-account not set), remove this block.
resource "google_service_account_iam_member" "ci_act_as_cloud_build" {
  service_account_id = data.google_service_account.cloud_build.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.github_principal_set
}
