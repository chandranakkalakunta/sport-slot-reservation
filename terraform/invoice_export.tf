# Invoice CSV/JSON Export — Phase 15.5
#
# Coordinator requirement: a high-level (summary, not full line-item
# detail) CSV/JSON export of each period's invoices, landing in GCS so
# an external "next level system" can pick it up.
#
# This is genuinely NEW, PRIVATE storage — invoices are financial PII,
# so this must NEVER reuse the existing public frontend bucket
# (google_storage_bucket.frontend, load_balancer_backends.tf) or its
# allUsers objectViewer binding. No public IAM binding of any kind is
# granted anywhere in this file, by design.

resource "google_storage_bucket" "invoice_exports" {
  name                        = "sport-slot-dev-invoices"
  project                     = var.project_id
  location                    = "ASIA-SOUTH1"
  uniform_bucket_level_access = true

  labels = var.default_labels
}

# Self-impersonation for signed URLs (keyless architecture): Cloud Run's
# default credentials have no private key to sign a GCS URL with
# directly (blob.generate_signed_url requires one). Mirrors the EXACT
# mechanism already used and working for Firebase Hosting deploy tokens
# (wif_iam.tf's ci_token_creator_firebase) — granting
# serviceAccountTokenCreator so a caller running AS sa-cloud-run can
# mint a short-lived impersonated token for itself, which
# generate_signed_url can then sign with via the IAM SignBlob API.
# Self-referential this time (sa-cloud-run on itself), not cross-SA.
resource "google_service_account_iam_member" "cloud_run_self_token_creator" {
  service_account_id = data.google_service_account.cloud_run.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${data.google_service_account.cloud_run.email}"
}
