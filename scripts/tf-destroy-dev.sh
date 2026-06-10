#!/usr/bin/env bash
#
# tf-destroy-dev.sh — Destroy DEV Terraform-managed resources
#
# Called by: make tf-destroy-dev
# DOUBLE-GUARDED — destructive operation

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}/terraform"

# Verify we're targeting DEV (not PROD)
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
if [ "${CURRENT_PROJECT}" != "sport-slot-dev" ]; then
    echo "✗ Current gcloud project is '${CURRENT_PROJECT}', expected 'sport-slot-dev'"
    exit 1
fi

echo "═══════════════════════════════════════════════════════"
echo "DESTRUCTIVE OPERATION"
echo ""
echo "About to DESTROY Terraform-managed resources in:"
echo "    Project:     sport-slot-dev"
echo "    Environment: DEV"
echo ""
echo "Note: This destroys ONLY Terraform-managed resources."
echo "      Phase 1.4.2 data sources will NOT be destroyed."
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Type exactly: 'yes destroy dev environment'"
read -r CONFIRMATION_1
if [ "${CONFIRMATION_1}" != "yes destroy dev environment" ]; then
    echo "✗ Confirmation failed. Aborting."
    exit 1
fi

echo ""
echo "Type the project name to confirm: 'sport-slot-dev'"
read -r CONFIRMATION_2
if [ "${CONFIRMATION_2}" != "sport-slot-dev" ]; then
    echo "✗ Project name mismatch. Aborting."
    exit 1
fi

echo ""
echo "→ Running terraform destroy..."
terraform destroy
