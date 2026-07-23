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

# Deploy Cloud Run revisions (ADR-0043 WIF-LEAST-PRIV, PR-5b: tightened
# from roles/run.admin). roles/run.developer covers everything
# `scripts/deploy_cloud_run.sh` uses EXCEPT one permission:
# `gcloud run deploy --allow-unauthenticated` calls SetIamPolicy under
# the hood to grant allUsers roles/run.invoker on the service, and
# run.developer does NOT include *.setIamPolicy (verified live,
# 2026-07-21: `gcloud iam roles describe roles/run.developer` lists
# only *.getIamPolicy; roles/run.admin has both get and set). The
# custom role below adds exactly that one missing permission rather
# than granting run.admin's full set (which also covers run jobs/
# instances/workerpools IAM this CI pipeline never touches).
resource "google_project_iam_member" "ci_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = local.github_principal_set
}

resource "google_project_iam_custom_role" "ci_run_set_iam_policy" {
  project     = var.project_id
  role_id     = "ciRunSetIamPolicy"
  title       = "CI Run SetIamPolicy (least-priv)"
  description = "Adds run.services.setIamPolicy to the CI WIF principal — the one permission roles/run.developer lacks that `gcloud run deploy --allow-unauthenticated` needs. Composed with roles/run.developer instead of granting roles/run.admin (ADR-0043 WIF-LEAST-PRIV, PR-5b)."
  permissions = ["run.services.setIamPolicy"]
  stage       = "GA"
}

resource "google_project_iam_member" "ci_run_set_iam_policy" {
  project = var.project_id
  role    = google_project_iam_custom_role.ci_run_set_iam_policy.id
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

# ADR-0043 WIF-LEAST-PRIV, PR-5b: project-level storage.admin
# (ci_storage_admin, removed) tightened to two bucket-scoped grants —
# the only two GCS buckets this CI pipeline actually touches
# (verified against .github/workflows/deploy.yml + scripts/
# build_push.sh, 2026-07-21): the Cloud Build source-staging bucket
# and the frontend static-asset bucket. roles/storage.objectAdmin
# (object CRUD, not bucket-level IAM/lifecycle control) matches the
# role already proven live for sa-cloud-build on the same staging
# bucket (scripts/setup_build_infra.sh).

# `gcloud builds submit --gcs-source-staging-dir` uploads the source
# tarball here (scripts/build_push.sh). Bucket predates Terraform
# (created by setup_build_infra.sh) — bound by literal name, no
# import needed for an IAM-member-only resource.
resource "google_storage_bucket_iam_member" "ci_cloudbuild_staging_object_admin" {
  bucket     = "${var.project_id}-cloudbuild"
  role       = "roles/storage.admin"
  member     = local.github_principal_set
  depends_on = [google_storage_bucket.cloudbuild_staging]
}

# `gcloud storage cp` syncs frontend/dist/ here on every deploy
# (.github/workflows/deploy.yml, "Sync frontend dist to GCS" step) —
# overwrites existing objects (index.html etc.) and creates new
# content-hashed ones, so needs object create+update, not just create.
resource "google_storage_bucket_iam_member" "ci_frontend_bucket_object_admin" {
  bucket = google_storage_bucket.frontend.name
  role   = "roles/storage.objectAdmin"
  member = local.github_principal_set
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
  service_account_id = google_service_account.firebase_admin.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = local.github_principal_set
}

# The Firebase Hosting REST deploy runs as sa-firebase-admin (its
# impersonated token) and sends X-Goog-User-Project=sport-slot-dev,
# so the SA itself needs serviceusage.services.use on the project.
# (The principalSet has this from 6.1.1, but the impersonated SA is
# the effective caller for the Hosting REST API.)
resource "google_project_iam_member" "firebase_admin_service_usage_consumer" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${google_service_account.firebase_admin.email}"
}

# CI must deploy a Cloud Run service that RUNS AS the runtime SA
# (sa-cloud-run). Without this, `gcloud run deploy --service-account`
# is rejected. Least privilege preserved: CI deploys; sa-cloud-run
# is the narrow runtime identity.
resource "google_service_account_iam_member" "ci_act_as_runtime" {
  service_account_id = google_service_account.cloud_run.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.github_principal_set
}

# CONFIRMED (2026-07-21, ADR-0043 PR-5b evidence pass): required.
# scripts/build_push.sh's `gcloud builds submit` explicitly passes
# `--service-account=...sa-cloud-build@...`, so the WIF principal
# must be allowed to act as that SA to submit the build. Was
# previously flagged as unconfirmed; resolved by inspection of the
# live script, not by observing a CI run.
resource "google_service_account_iam_member" "ci_act_as_cloud_build" {
  service_account_id = google_service_account.cloud_build.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.github_principal_set
}
