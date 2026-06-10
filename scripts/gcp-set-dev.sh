#!/usr/bin/env bash
#
# gcp-set-dev.sh — Switch gcloud config to sport-slot-dev project
#
# Called by: make gcp-set-dev

set -euo pipefail

echo "→ Setting gcloud project to sport-slot-dev..."
gcloud config set project sport-slot-dev

echo "→ Setting ADC quota project..."
gcloud auth application-default set-quota-project sport-slot-dev 2>&1 \
    | grep -v "^$" || true

echo ""
echo "✓ Switched to sport-slot-dev"
echo ""
bash "$(dirname "${BASH_SOURCE[0]}")/gcp-whoami.sh"
