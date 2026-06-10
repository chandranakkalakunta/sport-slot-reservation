#!/usr/bin/env bash
#
# tf-plan.sh — Show Terraform execution plan
#
# Called by: make tf-plan

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}/terraform"

echo "→ Running terraform plan..."
terraform plan
