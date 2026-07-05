# Load Balancer Backends — Phase 8b.2
#
# GCS bucket (frontend static assets) + backend bucket with SPA 404→200 catch-all;
# Cloud Run serverless NEG + backend service for the API. Both backends are
# consumed by the URL map in load_balancer_routing.tf.
#
# The GCS bucket is intentionally public-read (allUsers objectViewer) — it stores
# only pre-built frontend assets with no PII. uniform_bucket_level_access is
# required so the public IAM binding applies uniformly (per ADR-0031 Decision 2).
#
# SPA catch-all: Vite builds a single index.html; every client-side route (e.g.
# /dashboard, /facilities/abc) maps to a GCS key that does not exist, so GCS
# returns 404. The URL map's defaultCustomErrorResponsePolicy (set in
# load_balancer_routing.tf) intercepts those 404s and re-serves /index.html
# with HTTP 200, replicating Firebase Hosting's "source: **" catch-all rewrite.

# ── GCS bucket (stores frontend/dist/ output uploaded in Phase 8b.2b CI step) ──

resource "google_storage_bucket" "frontend" {
  name                        = "sport-slot-dev-frontend"
  project                     = var.project_id
  location                    = "ASIA-SOUTH1"
  uniform_bucket_level_access = true

  labels = var.default_labels
}

# allUsers objectViewer — deliberate, public static web assets, no PII.
resource "google_storage_bucket_iam_member" "frontend_public_read" {
  bucket = google_storage_bucket.frontend.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# ── Frontend backend bucket (LB attachment, CDN enabled) ──

resource "google_compute_backend_bucket" "frontend" {
  name        = "slotsense-frontend-bucket"
  project     = var.project_id
  bucket_name = google_storage_bucket.frontend.name
  enable_cdn  = true
}

# ── Cloud Run serverless NEG + API backend service ──

# Serverless NEG is REGIONAL; the backend service referencing it is GLOBAL.
resource "google_compute_region_network_endpoint_group" "api_neg" {
  name                  = "slotsense-api-neg"
  project               = var.project_id
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = "sport-slot-api"
  }
}

resource "google_compute_backend_service" "api" {
  name                  = "slotsense-api-backend"
  project               = var.project_id
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  enable_cdn            = false

  backend {
    group = google_compute_region_network_endpoint_group.api_neg.id
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }
}
