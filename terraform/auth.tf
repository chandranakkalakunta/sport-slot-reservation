# Firebase Auth — Email/Password sign-in provider
# (Environment Provisioning Spec GAP 2.2)
#
# `firebase projects:addfirebase` enables Firebase Auth on a project
# but does NOT enable any sign-in provider. Without Email/Password
# turned on, backend/scripts/seed_platform_admin.py fails with
# CONFIGURATION_NOT_FOUND ("No auth provider found") — discovered
# live during DR drill Pass 1. This codifies that one console/gcloud
# step so a rebuilt environment doesn't need it done by hand.
#
# GCIP-upgrade risk (verified before authoring, not assumed):
#   - google_identity_platform_config's REST calls target
#     identitytoolkit.googleapis.com/v2 (confirmed by inspecting the
#     pinned hashicorp/google 6.50.0 provider binary's embedded API
#     paths) — the same API that already backs standard Firebase Auth
#     and is already enabled (apis.tf core_apis). The distinct
#     identityplatform.googleapis.com API does not appear anywhere in
#     the provider binary, so this resource cannot be enabling it.
#   - Live confirmation: GET .../v2/projects/sport-slot-dev/config
#     returns "subtype": "FIREBASE_AUTH" (not "IDENTITY_PLATFORM"),
#     i.e. sport-slot-dev is already on this same config surface
#     without ever having been upgraded to a GCIP billing tier.
#   No identityplatform.googleapis.com entry is added to apis.tf —
#   it is not required.
#
# sport-slot-dev already has a live Config object (Firebase Auth was
# enabled there via `firebase projects:addfirebase` + manual console
# provider toggle, pre-dating Terraform management of this resource).
# This is a per-project singleton — Terraform's Create path calls a
# distinct :initializeAuth RPC, not a plain update, so applying this
# resource against sport-slot-dev WITHOUT first importing the
# existing object is not a verified no-op.
#
# REQUIRED one-time Coordinator action before the next `terraform
# plan`/`apply` against sport-slot-dev:
#   terraform import google_identity_platform_config.auth sport-slot-dev
# After import, `terraform plan` must show no changes (email/password
# sign-in is already enabled live with password_required = true,
# matching the config below field-for-field). New environments (no
# pre-existing Config object) need no import — Create initializes it
# fresh, which is the intended use of :initializeAuth.
resource "google_identity_platform_config" "auth" {
  project = var.project_id

  sign_in {
    email {
      enabled           = true
      password_required = true
    }
  }

  depends_on = [google_project_service.enabled_apis]
}
