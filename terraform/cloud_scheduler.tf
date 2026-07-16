# Cloud Scheduler Invoice Generation Trigger — Phase 15.3
#
# Monthly invoice generation. Decision 4 (locked this sub-phase): ONE
# fixed global generation time for ALL tenants (03:00 on the 1st) —
# does NOT yet honor each tenant's own policies.invoice_generation_time
# field (Phase 15.2). That field is stored but unwired to scheduling
# until a later sub-phase; this is a deliberate, known gap (see
# CHANGELOG), not an oversight.
#
# Cloud Scheduler calls the Cloud Run service's default run.app URL
# directly (the same URL Cloud Tasks already targets via
# SPORTSLOT_WORKER_BASE_URL) — Cloud Scheduler is on Google's
# documented internal-traffic allowlist for `internal-and-cloud-load-
# balancing` ingress, the same category as the already-working Cloud
# Tasks integration. Still verify live after deploy — same "confirm,
# don't assume" discipline that caught the Firebase Hosting internal-
# traffic gap in Phase 8.
#
# cloudscheduler.googleapis.com is already enabled — see apis.tf's
# operational_apis list — no API-enablement resource needed here.

# Cloud Run (sport-slot-api) is now Terraform-managed as
# google_cloud_run_v2_service.sport_slot_api (terraform/cloud_run.tf,
# ADR-0038 Layer 3 / PR-1b) — its URL is read from that resource
# rather than a data source.

# Dedicated identity for Cloud Scheduler's OIDC tokens — a distinct
# trust boundary from sa-tasks-invoker (different caller: Cloud
# Scheduler, not Cloud Tasks), matching this project's one-SA-per-
# trust-boundary convention (sa-cloud-run, sa-firebase-admin,
# sa-tasks-invoker, sa-cloud-build, sa-monitoring are all separate).
# Do NOT reuse sa-tasks-invoker.
resource "google_service_account" "scheduler_invoker" {
  account_id   = "sa-scheduler-invoker"
  display_name = "Cloud Scheduler OIDC invoker for invoice generation"
  project      = var.project_id
}

resource "google_cloud_run_service_iam_member" "scheduler_invoker_run_invoker" {
  project  = var.project_id
  location = var.region
  service  = "sport-slot-api"
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_invoker.email}"
}

# NOTE for Coordinator (apply-time): unlike sa-tasks-invoker (whose
# actAs grant is on sa-cloud-run, the runtime enqueuer), this job is
# created once, statically, by whoever runs `terraform apply` — Cloud
# Scheduler needs no additional per-invocation actAs binding for that.
# If apply fails with a "Permission denied on service account" /
# actAs-style error, it means the applying principal itself lacks
# roles/iam.serviceAccountUser on sa-scheduler-invoker — grant that to
# yourself, not to any service account in this file.

# Monthly invoice generation job (Decision 1, postpaid): a run on day N
# of month M bills all confirmed bookings dated in month M-1. The
# service computes that window itself from "today" at invocation time,
# so the job body needs no explicit period argument.
resource "google_cloud_scheduler_job" "invoice_generation" {
  name        = "invoice-generation-monthly"
  project     = var.project_id
  region      = var.region
  description = "Monthly per-household invoice generation (Phase 15.3)"
  schedule    = "0 3 1 * *"
  # Single global fixed time (Decision 4) — not per-tenant. Coordinator:
  # confirm this timezone matches intent before apply; nothing in this
  # sub-phase's locked decisions specified one, so UTC was chosen as the
  # least-surprising default for a single global schedule.
  time_zone = "Etc/UTC"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.sport_slot_api.uri}/internal/invoicing/generate"

    oidc_token {
      service_account_email = google_service_account.scheduler_invoker.email
      audience              = google_cloud_run_v2_service.sport_slot_api.uri
    }
  }

  retry_config {
    retry_count = 3
  }
}
