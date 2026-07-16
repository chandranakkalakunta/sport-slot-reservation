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
#
# Referenced by terraform/outputs.tf. The managed
# google_firestore_database resource itself now lives in
# terraform/backup_dr.tf (ADR-0038, PR-1a) — the commented-out
# template formerly here is superseded and removed (2026-07-16,
# DOC-TRUTH).

locals {
  firestore_database_name = "(default)"
  firestore_location      = var.region # asia-south1 — region-locked at creation
}

# ─── SECURITY RULES (managed via Firebase CLI, not Terraform) ───
#
# Current rules: infrastructure/firestore.rules (deny-all baseline)
# Deployed via:  firebase deploy --only firestore:rules
#
# Tenant-aware rules will be added in Phase 2 per ADR-0004.
