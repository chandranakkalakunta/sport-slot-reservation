# Cloud Armor WAF Policies — Phase 8b.5
#
# Two separate policies are required because GCP enforces a hard split:
#   - google_compute_backend_service  → CLOUD_ARMOR policy (security_policy attr)
#   - google_compute_backend_bucket   → CLOUD_ARMOR_EDGE policy (edge_security_policy attr)
#
# ALL rules are in preview = true (log-only, non-blocking). Base L3/L4 DDoS
# protection is already provided by the Global HTTPS LB automatically.
# This phase adds L7 WAF inspection only (ADR-0032).
#
# Rate limiting and Adaptive Protection are explicitly deferred — see ADR-0032.

# ── API backend: CLOUD_ARMOR policy ──

resource "google_compute_security_policy" "api" {
  name    = "slotsense-api-armor"
  project = var.project_id
  type    = "CLOUD_ARMOR"

  # Default rule: allow all — preview-only rollout; no default-deny at this stage.
  # GCP does not permit preview=true on the mandatory default rule (priority 2147483647).
  rule {
    priority = 2147483647
    action   = "allow"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "default allow — preview mode, non-enforcing"
  }

  # CRS 4.22 SQLi WAF rule (preview, log-only).
  rule {
    priority = 1000
    action   = "deny(403)"
    preview  = true
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('sqli-v422-stable', {'sensitivity': 1})"
      }
    }
    description = "SQLi CRS 4.22 sensitivity 1 — preview only"
  }

  # CRS 4.22 XSS WAF rule (preview, log-only).
  rule {
    priority = 2000
    action   = "deny(403)"
    preview  = true
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('xss-v422-stable', {'sensitivity': 1})"
      }
    }
    description = "XSS CRS 4.22 sensitivity 1 — preview only"
  }
}

# ── Frontend backend bucket: CLOUD_ARMOR_EDGE policy ──

resource "google_compute_security_policy" "frontend_edge" {
  name    = "slotsense-frontend-edge-armor"
  project = var.project_id
  type    = "CLOUD_ARMOR_EDGE"

  # CLOUD_ARMOR_EDGE does not support preconfigured WAF expressions (evaluatePreconfiguredWaf
  # is only valid on CLOUD_ARMOR type — confirmed via API error on apply attempt).
  # Policy contains only the mandatory default rule. Custom CEL-based edge rules are
  # deferred as a deliberate future addition.

  # Default rule: allow all — no default-deny at this stage.
  # GCP does not permit preview=true on the mandatory default rule (priority 2147483647).
  rule {
    priority = 2147483647
    action   = "allow"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "default allow"
  }
}
