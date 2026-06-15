# Workload Identity Federation
#
# Pool and provider were created via gcloud in Phase 1.3.2 and are
# imported into Terraform management in Phase 6.1.
# Import commands: see IMPORT_6.1.md
#
# Attribute condition restricts to this repo + refs/heads/main ONLY.
# PRs cannot authenticate to GCP — they run lint/test gates only.
# This restriction is enforced at the identity layer, not just workflow
# logic (ADR-0018).

resource "google_iam_workload_identity_pool" "github_actions" {
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Federation pool for GitHub Actions CI/CD"
  project                   = var.project_id
}

resource "google_iam_workload_identity_pool_provider" "github_actions" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_actions.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-provider"
  project                            = var.project_id

  attribute_condition = "assertion.repository == '${var.github_repository}' && assertion.ref == 'refs/heads/main'"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
    "attribute.actor"      = "assertion.actor"
  }

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}
