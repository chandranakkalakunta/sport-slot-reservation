# Firestore Database
#
# ═══════════════════════════════════════════════════════════════
# DOCUMENTATION OF EXISTING RESOURCES (Phase 1.4.2 — Option C)
# ═══════════════════════════════════════════════════════════════
#
# Firestore Native Mode database created in Phase 1.3.3
# via `gcloud firestore databases create`.
#
# Security rules and indexes are managed via Firebase CLI
# (not Terraform). See infrastructure/firestore.rules.

# ─── LOCALS (active reference) ───
#
# NOTE: google provider v6 does not expose a data source for
# google_firestore_database. Database details are read via gcloud
# or available as outputs from the resource block once imported.
# Using locals to hold known-stable values for now.

locals {
  firestore_database_name = "(default)"
  firestore_location      = var.region # asia-south1 — region-locked at creation
}

# ─── RESOURCE TEMPLATE (uncomment when ready to import) ───

# resource "google_firestore_database" "default" {
#   project                           = var.project_id
#   name                              = "(default)"
#   location_id                       = var.region # asia-south1
#   type                              = "FIRESTORE_NATIVE"
#   concurrency_mode                  = "PESSIMISTIC"
#   app_engine_integration_mode       = "DISABLED"
#   delete_protection_state           = "DELETE_PROTECTION_DISABLED"
#   point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_DISABLED"
#
#   # NOTE for PROD:
#   # When creating production Firestore, set:
#   #   delete_protection_state           = "DELETE_PROTECTION_ENABLED"
#   #   point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_ENABLED"
# }

# ─── SECURITY RULES (managed via Firebase CLI, not Terraform) ───
#
# Current rules: infrastructure/firestore.rules (deny-all baseline)
# Deployed via:  firebase deploy --only firestore:rules
#
# Tenant-aware rules will be added in Phase 2 per ADR-0004.
