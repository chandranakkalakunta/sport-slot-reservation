# Phase 6.1 — Terraform import commands (run from terraform/ dir)
# Run AFTER `make tf-init`, BEFORE `make tf-apply-dev`.
# These adopt the existing (Phase-1, gcloud-created) WIF resources
# into Terraform management without recreating them.

terraform import google_iam_workload_identity_pool.github_actions \
  projects/sport-slot-dev/locations/global/workloadIdentityPools/github-actions-pool

terraform import google_iam_workload_identity_pool_provider.github_actions \
  projects/sport-slot-dev/locations/global/workloadIdentityPools/github-actions-pool/providers/github-actions-provider

# After import, `make tf-plan` should show:
#   - NO changes to the pool/provider (they match the imported state)
#   - NEW: the 6 IAM bindings in wif_iam.tf (these don't exist yet)
# Eyeball the plan: the pool/provider must show no destructive change.
# The IAM bindings are additive. Then `make tf-apply-dev`.
