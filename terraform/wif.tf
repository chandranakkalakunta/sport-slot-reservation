# Workload Identity Federation
#
# ═══════════════════════════════════════════════════════════════
# DOCUMENTATION OF EXISTING RESOURCES (Phase 1.4.2 — Option C)
# ═══════════════════════════════════════════════════════════════
#
# WIF allows GitHub Actions to authenticate to GCP without
# service account JSON keys. Created in Phase 1.3.2.

# ─── DATA SOURCES (active references) ───

data "google_iam_workload_identity_pool" "github_actions" {
  workload_identity_pool_id = "github-actions-pool"
}

data "google_iam_workload_identity_pool_provider" "github_actions" {
  workload_identity_pool_id          = "github-actions-pool"
  workload_identity_pool_provider_id = "github-actions-provider"
}

# ─── RESOURCE TEMPLATES (uncomment when ready to import) ───

# Pool: github-actions-pool
# resource "google_iam_workload_identity_pool" "github_actions" {
#   workload_identity_pool_id = "github-actions-pool"
#   display_name              = "GitHub Actions Pool"
#   description               = "Federation pool for GitHub Actions CI/CD"
#   project                   = var.project_id
# }

# Provider: github-actions-provider
# resource "google_iam_workload_identity_pool_provider" "github_actions" {
#   workload_identity_pool_id          = google_iam_workload_identity_pool.github_actions.workload_identity_pool_id
#   workload_identity_pool_provider_id = "github-actions-provider"
#
#   oidc {
#     issuer_uri = "https://token.actions.githubusercontent.com"
#   }
#
#   attribute_mapping = {
#     "google.subject"       = "assertion.sub"
#     "attribute.repository" = "assertion.repository"
#     "attribute.ref"        = "assertion.ref"
#     "attribute.actor"      = "assertion.actor"
#   }
#
#   attribute_condition = "assertion.repository == '${var.github_repository}' && assertion.ref == 'refs/heads/main'"
#
#   project = var.project_id
# }

# Binding: GitHub repo can impersonate sa-cloud-build
# resource "google_service_account_iam_member" "github_actions_impersonate_cloud_build" {
#   service_account_id = data.google_service_account.cloud_build.name
#   role               = "roles/iam.workloadIdentityUser"
#   member             = "principalSet://iam.googleapis.com/projects/${var.project_number}/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/${var.github_repository}"
# }
