#!/usr/bin/env bash
#
# tf-apply-dev.sh — Apply Terraform changes to DEV environment
#
# Called by: make tf-apply-dev
# Has safety guardrail per ADR-0003

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}/terraform"

# Verify we're targeting DEV
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
if [ "${CURRENT_PROJECT}" != "sport-slot-dev" ]; then
    echo "✗ Current gcloud project is '${CURRENT_PROJECT}', expected 'sport-slot-dev'"
    echo "  Run: gcloud config set project sport-slot-dev"
    exit 1
fi

echo "═══════════════════════════════════════════════════════"
echo "About to apply Terraform changes to:"
echo "    Project:     sport-slot-dev"
echo "    Environment: DEV"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Type exactly: 'yes apply to dev'"
read -r CONFIRMATION
if [ "${CONFIRMATION}" != "yes apply to dev" ]; then
    echo "✗ Confirmation failed. Aborting."
    exit 1
fi

echo ""
echo "→ Running terraform apply..."
terraform apply
