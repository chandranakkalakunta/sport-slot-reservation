#!/usr/bin/env bash
#
# tf-init.sh — Initialize Terraform with remote state
#
# Called by: make tf-init

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}/terraform"

echo "→ Initializing Terraform..."
terraform init -upgrade=false

echo "✓ Terraform initialized"
