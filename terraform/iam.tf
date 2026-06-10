# IAM Configuration — Service Accounts and Bindings
#
# ═══════════════════════════════════════════════════════════════
# DOCUMENTATION OF EXISTING RESOURCES (Phase 1.4.2 — Option C)
# ═══════════════════════════════════════════════════════════════
#
# The 4 service accounts below were created via `gcloud iam` in
# Phase 1.3.2 and granted roles incrementally through Phase 1.3.3.
#
# Active references (data sources) are below the documentation
# for use by future resources (Cloud Run deployments, etc.)

# ─── DATA SOURCES (active references) ───

data "google_service_account" "cloud_run" {
  account_id = "sa-cloud-run"
  project    = var.project_id
}

data "google_service_account" "firebase_admin" {
  account_id = "sa-firebase-admin"
  project    = var.project_id
}

data "google_service_account" "cloud_build" {
  account_id = "sa-cloud-build"
  project    = var.project_id
}

data "google_service_account" "monitoring" {
  account_id = "sa-monitoring"
  project    = var.project_id
}

# ─── RESOURCE TEMPLATES (uncomment when ready to import) ───

# sa-cloud-run: Runtime SA for Cloud Run services
# resource "google_service_account" "cloud_run" {
#   account_id   = "sa-cloud-run"
#   display_name = "SportBook Cloud Run Runtime"
#   description  = "Runtime SA for Cloud Run services (backend + frontend)"
#   project      = var.project_id
# }
#
# Roles granted (Phase 1.3.2 + 1.3.3):
#   - roles/secretmanager.secretAccessor
#   - roles/logging.logWriter
#   - roles/monitoring.metricWriter
#   - roles/cloudtrace.agent
#   - roles/datastore.user           (added Phase 1.3.3)
#
# Impersonation: sa-cloud-run can impersonate sa-firebase-admin
#   (serviceAccountTokenCreator binding on sa-firebase-admin SA resource)

# sa-firebase-admin: Firebase Admin SDK operations
# resource "google_service_account" "firebase_admin" {
#   account_id   = "sa-firebase-admin"
#   display_name = "SportBook Firebase Admin"
#   description  = "Firebase Admin SDK operations (JWT verify, user mgmt)"
#   project      = var.project_id
# }
#
# Roles granted (Phase 1.3.3):
#   - roles/firebase.admin
#   - roles/datastore.user
#   - roles/iam.serviceAccountTokenCreator
#   - roles/logging.logWriter

# sa-cloud-build: CI/CD via GitHub Actions WIF
# resource "google_service_account" "cloud_build" {
#   account_id   = "sa-cloud-build"
#   display_name = "SportBook Cloud Build (CI/CD)"
#   description  = "CI/CD deployments from GitHub Actions via WIF"
#   project      = var.project_id
# }
#
# Roles granted (Phase 1.3.2):
#   - roles/run.developer
#   - roles/artifactregistry.writer
#   - roles/logging.logWriter
#
# Impersonation: sa-cloud-build impersonates sa-cloud-run for deploys
# WIF binding: GitHub Actions impersonates sa-cloud-build (see wif.tf)

# sa-monitoring: Observability tools
# resource "google_service_account" "monitoring" {
#   account_id   = "sa-monitoring"
#   display_name = "SportBook Observability"
#   description  = "Cloud Monitoring dashboards, alerts, and metrics"
#   project      = var.project_id
# }
#
# Roles granted (Phase 1.3.2):
#   - roles/monitoring.editor
#   - roles/logging.logWriter
