# Terraform Outputs
#
# Outputs expose key resource references for use by:
#   - Cloud Run deployments (Phase 2)
#   - GitHub Actions workflows (Phase 4)
#   - Documentation and runbooks

output "project_id" {
  description = "GCP project ID"
  value       = var.project_id
}

output "project_number" {
  description = "GCP project number"
  value       = var.project_number
}

output "region" {
  description = "GCP region"
  value       = var.region
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}

# Service Account Emails (from data sources)
output "service_account_cloud_run_email" {
  description = "Email of sa-cloud-run (Cloud Run runtime SA)"
  value       = google_service_account.cloud_run.email
}

output "service_account_firebase_admin_email" {
  description = "Email of sa-firebase-admin (Firebase Admin SDK SA)"
  value       = google_service_account.firebase_admin.email
}

output "service_account_cloud_build_email" {
  description = "Email of sa-cloud-build (CI/CD SA)"
  value       = google_service_account.cloud_build.email
}

output "service_account_monitoring_email" {
  description = "Email of sa-monitoring (Observability SA)"
  value       = google_service_account.monitoring.email
}

# Workload Identity Federation (managed resources since Phase 6.1)
output "workload_identity_pool_name" {
  description = "Full resource name of the WIF pool"
  value       = google_iam_workload_identity_pool.github_actions.name
}

output "workload_identity_provider_name" {
  description = "Full resource name of the WIF provider"
  value       = google_iam_workload_identity_pool_provider.github_actions.name
}

# Firestore (no data source available in provider v6 — using locals)
output "firestore_database_name" {
  description = "Firestore database name"
  value       = local.firestore_database_name
}

output "firestore_location" {
  description = "Firestore database location (region-locked at creation)"
  value       = local.firestore_location
}
