# GCP API Enablement
#
# ═══════════════════════════════════════════════════════════════
# DOCUMENTATION OF EXISTING RESOURCES (Phase 1.4.2 — Option C)
# ═══════════════════════════════════════════════════════════════
#
# The 21 APIs below were enabled via `gcloud services enable` and
# are NOT currently managed by Terraform.
#   - 18 APIs enabled Phase 1.3.1 (Batch 1 + Batch 2)
#   - 2 APIs enabled Phase 8b.1: compute, networksecurity
#   - 1 API  enabled Phase 8b.1 correction: certificatemanager
#
# To bring these under Terraform management in a future phase:
#   1. Uncomment the resource block below
#   2. For each API, run:
#      terraform import google_project_service.enabled_apis[\"SERVICE\"] \
#        sport-slot-dev/SERVICE.googleapis.com
#   3. terraform plan (must show no changes)
#
# For TEST/PROD environments: simply uncomment and terraform apply.

locals {
  # Core infrastructure APIs (enabled Phase 1.3.1 Batch 1)
  # compute + networksecurity added Phase 8b.1 (LB + Cloud Armor)
  # certificatemanager added Phase 8b.1 correction (wildcard cert via DNS auth)
  core_apis = [
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "firestore.googleapis.com",
    "firebase.googleapis.com",
    "identitytoolkit.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "networksecurity.googleapis.com",
    "certificatemanager.googleapis.com",
  ]

  # Operational services APIs (enabled Phase 1.3.1 Batch 2)
  operational_apis = [
    "artifactregistry.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudtrace.googleapis.com",
    "cloudtasks.googleapis.com",
    "redis.googleapis.com",
    "pubsub.googleapis.com",
    "storage.googleapis.com",
  ]

  all_apis = concat(local.core_apis, local.operational_apis)
}

# ─── RESOURCE TEMPLATE (uncomment when ready to import) ───
#
# resource "google_project_service" "enabled_apis" {
#   for_each           = toset(local.all_apis)
#   project            = var.project_id
#   service            = each.value
#   disable_on_destroy = false
#
#   lifecycle {
#     prevent_destroy = true
#   }
# }
