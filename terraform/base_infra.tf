# Base Infrastructure — Memorystore Redis + Artifact Registry
# (ADR-0038 Layer 3, PR-1b)
#
# Both resources were created imperatively (`gcloud redis instances
# create`, `gcloud artifacts repositories create`) and are absent
# from state. Authored field-for-field from the 2026-07-16 live
# describe output captured in PR-1b Step 1 so import produces a
# clean plan.

resource "google_redis_instance" "sport_slot_redis" {
  name           = "sport-slot-redis"
  project        = var.project_id
  region         = var.region
  location_id    = "asia-south1-c"
  tier           = "BASIC"
  memory_size_gb = 1
  redis_version  = "REDIS_7_0"

  authorized_network      = "projects/${var.project_id}/global/networks/default"
  connect_mode            = "DIRECT_PEERING"
  auth_enabled            = true
  transit_encryption_mode = "DISABLED"

  persistence_config {
    persistence_mode = "DISABLED"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_artifact_registry_repository" "sport_slot_repo" {
  repository_id = "sport-slot-repo"
  project       = var.project_id
  location      = "asia-south1"
  format        = "DOCKER"
  description   = "SportSlot container images"
  mode          = "STANDARD_REPOSITORY"

  lifecycle {
    prevent_destroy = true
  }
}
