# Backup & Disaster Recovery — ADR-0038 (PR-1a)
#
# Codifies the live 2026-07-14 stop-gap state (Firestore PITR + delete
# protection, enabled imperatively ahead of this ADR) plus the daily
# backup schedule, tfstate/invoices bucket versioning, and secret shells
# needed for a Terraform-rebuildable project (Layer 3, IAM-TF-CODIFY /
# PR-1b).
#
# Import-only resources below are written to match live state
# field-for-field so `terraform import` + `terraform plan` produces a
# clean plan, not changes. See PR description for the import commands
# (Coordinator-run only — see terraform/firestore.tf and ADR-0038 §Layer 3
# for the Worker/Coordinator division of labor).

# ─── Layer 1: Firestore — database + daily backup schedule ───

resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region # asia-south1

  type                              = "FIRESTORE_NATIVE"
  concurrency_mode                  = "PESSIMISTIC"
  app_engine_integration_mode       = "DISABLED"
  point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_ENABLED"
  delete_protection_state           = "DELETE_PROTECTION_ENABLED"

  # ABANDON, not DELETE: `terraform destroy` must never be able to take
  # the system of record with it. Belt-and-braces with the
  # prevent_destroy guard below.
  deletion_policy = "ABANDON"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_firestore_backup_schedule" "daily" {
  project  = var.project_id
  database = google_firestore_database.default.name

  retention = "604800s" # 7 days

  daily_recurrence {}
}

# ─── Layer 4: GCS — tfstate bucket (import) + invoices bucket lifecycle ───
#
# NOTE (CONTEXT correction, discovered in Step 1 live-state verification):
# sport-slot-dev-tfstate already has versioning_enabled = true and an
# existing lifecycle rule (Delete, num_newer_versions = 30) live — this
# contradicts the original audit premise that "none of the buckets have
# versioning." The block below is written to match that live state
# field-for-field (30, not the originally-planned 10) so the import
# produces a clean plan. See PR description for detail.

resource "google_storage_bucket" "tfstate" {
  name     = "sport-slot-dev-tfstate"
  project  = var.project_id
  location = "ASIA-SOUTH1"

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      num_newer_versions = 30
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

# google_storage_bucket.invoice_exports itself lives in
# terraform/invoice_export.tf (already in state) — versioning, the
# noncurrent-version lifecycle rule, and the prevent_destroy guard are
# added there, not duplicated here.

# ─── Layer 2: Secret Manager — shells only, no versions, no values ───
#
# Per ADR-0038 §Layer 2 / protocol §2.6: Terraform manages secret
# existence and replication only. Values are never read, written, or
# stored here — recovery is runbook-based (see
# docs/runbooks/disaster-recovery.md §Layer 2).

resource "google_secret_manager_secret" "redis_auth" {
  secret_id = "redis-auth"
  project   = var.project_id

  replication {
    user_managed {
      replicas {
        location = "asia-south1"
      }
    }
  }
}

resource "google_secret_manager_secret" "resend_api_key" {
  secret_id = "resend-api-key"
  project   = var.project_id

  replication {
    auto {}
  }
}
