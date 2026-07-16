# Cloud Run Service — sport-slot-api (ADR-0038 Layer 3, PR-1b)
#
# ADR-0038 D7 ownership model: Terraform owns existence/shape (SA,
# scaling ceiling, ingress, VPC egress, secret wiring, resource
# limits). CI (cloud_build via `gcloud run deploy`) owns revisions —
# the container image and the deploy-client annotations/labels gcloud
# rewrites on every release. Those fields are excluded via
# lifecycle.ignore_changes below so CI deploys never show as drift
# and `terraform apply` never rolls back a live image.
#
# Authored field-for-field from the 2026-07-16 live export
# (`gcloud run services describe sport-slot-api --region=asia-south1
# --format=export`) captured in PR-1b Step 1. maxScale is 2 live —
# codified as 2. Raising it is PR-3 scope; this PR changes no live
# value.
#
# NOTE for Coordinator: this is the import most likely to show
# residual plan diffs (v2 resource field sprawl vs the Knative-style
# export view). Any diff the staged plan reveals gets reported back
# verbatim and fixed in this file to match live — never by changing
# live.

resource "google_cloud_run_v2_service" "sport_slot_api" {
  name     = "sport-slot-api"
  project  = var.project_id
  location = var.region

  ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account                  = google_service_account.cloud_run.email
    timeout                          = "300s"
    max_instance_request_concurrency = 80

    scaling {
      max_instance_count = 2 # live value — do not raise here, see PR-3
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = "default"
        subnetwork = "default"
      }
    }

    containers {
      image = "asia-south1-docker.pkg.dev/sport-slot-dev/sport-slot-repo/sport-slot-api:faa1695"

      ports {
        name           = "http1"
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        startup_cpu_boost = true
      }

      startup_probe {
        failure_threshold = 1
        period_seconds    = 240
        timeout_seconds   = 240
        tcp_socket {
          port = 8080
        }
      }

      env {
        name  = "SPORTSLOT_ENVIRONMENT"
        value = "development"
      }
      env {
        name  = "SPORTSLOT_GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "SPORTSLOT_BASE_DOMAIN"
        value = "slotsense.chandraailabs.com"
      }
      env {
        name  = "SPORTSLOT_ADMIN_HOST"
        value = "admin.slotsense.chandraailabs.com"
      }
      env {
        name  = "SPORTSLOT_REDIS_HOST"
        value = google_redis_instance.sport_slot_redis.host
      }
      env {
        name  = "SPORTSLOT_REDIS_PORT"
        value = tostring(google_redis_instance.sport_slot_redis.port)
      }
      env {
        name  = "SPORTSLOT_TASKS_QUEUE"
        value = "notifications"
      }
      env {
        name  = "SPORTSLOT_TASKS_LOCATION"
        value = var.region
      }
      env {
        name  = "SPORTSLOT_WORKER_BASE_URL"
        value = "https://sport-slot-api-yw2l7pv63a-el.a.run.app"
      }
      env {
        name  = "SPORTSLOT_TASKS_INVOKER_SA"
        value = "sa-tasks-invoker@${var.project_id}.iam.gserviceaccount.com"
      }
      env {
        name  = "SPORTSLOT_SCHEDULER_INVOKER_SA"
        value = "sa-scheduler-invoker@${var.project_id}.iam.gserviceaccount.com"
      }
      env {
        name  = "SPORTSLOT_CLOUD_RUN_SA_EMAIL"
        value = google_service_account.cloud_run.email
      }
      env {
        name  = "BUILD_ID"
        value = "faa1695f06a676818f70341a7747777d0a3010c5"
      }
      env {
        name = "SPORTSLOT_REDIS_AUTH"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.redis_auth.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "SPORTSLOT_RESEND_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.resend_api_key.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    prevent_destroy = true
    ignore_changes = [
      client,
      client_version,
      template[0].containers[0].image,
      template[0].containers[0].env,
      template[0].annotations,
      template[0].labels,
      annotations,
      labels,
    ]
  }
}
