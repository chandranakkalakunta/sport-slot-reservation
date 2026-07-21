# Cloud Armor WAF Policies — Phase 8b.5
#
# Two separate policies are required because GCP enforces a hard split:
#   - google_compute_backend_service  → CLOUD_ARMOR policy (security_policy attr)
#   - google_compute_backend_bucket   → CLOUD_ARMOR_EDGE policy (edge_security_policy attr)
#
# Base L3/L4 DDoS protection is already provided by the Global HTTPS LB
# automatically. This phase adds L7 WAF inspection only (ADR-0032).
#
# Rate limiting and Adaptive Protection are explicitly deferred — see ADR-0032.
#
# API policy SQLi/XSS rules ENFORCING as of ADR-0043 PR-5c (finding #7),
# gated on the PR-5b preview-log review (docs/reviews/2026-07-21-armor-
# preview-log-review.md): a complete 14-day window found 100% of
# preview-flagged-but-accepted traffic was legitimate /api/v1/agent/voice
# base64-audio payloads false-positiving on the generic CRS body-
# inspection signatures — zero attack traffic. Coordinator decision
# (option 2): a higher-priority allow rule exempts that one path from
# WAF inspection, then the WAF rules flip to enforce — every other path
# gets real SQLi/XSS enforcement immediately. ACCEPTED RESIDUAL: the
# voice path's SQLi/XSS defense is thereby NOT the WAF but field-level
# input validation + safe sinks (Firestore is non-SQL; transcribed text
# validated in code; frontend escapes agent output) — tracked as
# backlog VOICE-INPUT-VALIDATION (Phase 18 launch-gate scope), the
# durable fix for this exempt path.

# ── API backend: CLOUD_ARMOR policy ──

resource "google_compute_security_policy" "api" {
  name    = "slotsense-api-armor"
  project = var.project_id
  type    = "CLOUD_ARMOR"

  # Default rule: allow all — no default-deny at this stage; unmatched
  # traffic falls through to this rule (mandatory, priority 2147483647,
  # cannot itself be preview=true — this is baseline allow, not a WAF
  # inspection rule, so "enforcing" it changes nothing behaviorally).
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

  # Voice path exemption (ADR-0043 PR-5c) — priority 900, LOWER than
  # both WAF rules below (1000/2000), so it evaluates first and
  # short-circuits: Cloud Armor stops at the first matching rule in
  # priority order, so a matching request never reaches the WAF rules
  # at all. Carries base64 audio indistinguishable from SQLi/XSS
  # signatures; defense is field-level validation
  # (VOICE-INPUT-VALIDATION), not WAF. ADR-0043.
  rule {
    priority = 900
    action   = "allow"
    match {
      expr {
        expression = "request.path.matches('/api/v1/agent/voice')"
      }
    }
    description = "Voice path exempt from WAF body inspection — carries base64 audio indistinguishable from SQLi/XSS signatures; defense is field-level validation (VOICE-INPUT-VALIDATION), not WAF. ADR-0043."
  }

  # CRS 4.22 SQLi WAF rule — ENFORCING (ADR-0043 PR-5c; preview-log
  # review clean for every path except voice, which is exempted above).
  rule {
    priority = 1000
    action   = "deny(403)"
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('sqli-v422-stable', {'sensitivity': 1})"
      }
    }
    description = "SQLi CRS 4.22 sensitivity 1 — enforcing"
  }

  # CRS 4.22 XSS WAF rule — ENFORCING (ADR-0043 PR-5c; preview-log
  # review clean for every path except voice, which is exempted above).
  rule {
    priority = 2000
    action   = "deny(403)"
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('xss-v422-stable', {'sensitivity': 1})"
      }
    }
    description = "XSS CRS 4.22 sensitivity 1 — enforcing"
  }
}

# ── Frontend backend bucket: CLOUD_ARMOR_EDGE policy ──

resource "google_compute_security_policy" "frontend_edge" {
  name    = "slotsense-frontend-edge-armor"
  project = var.project_id
  type    = "CLOUD_ARMOR_EDGE"

  # INTENTIONAL PASS-THROUGH (ADR-0043 PR-5c) — not a gap left open,
  # a documented decision: CLOUD_ARMOR_EDGE does not support
  # preconfigured WAF expressions (evaluatePreconfiguredWaf is only
  # valid on CLOUD_ARMOR type — confirmed via API error on a prior
  # apply attempt), so this policy cannot hold the same SQLi/XSS
  # ruleset the api policy now enforces. Policy contains only the
  # mandatory default-allow rule. Custom CEL-based edge rules remain a
  # deliberate future addition, not attempted here.

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
