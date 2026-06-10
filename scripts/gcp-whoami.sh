#!/usr/bin/env bash
#
# gcp-whoami.sh — Show current gcloud authentication state
#
# Called by: make gcp-whoami

set -euo pipefail

echo "═══════════════════════════════════════════════════════"
echo "GCP Authentication State"
echo "═══════════════════════════════════════════════════════"
echo ""

echo "Active account:"
gcloud config get-value account 2>/dev/null || echo "  (not set)"

echo ""
echo "Active project:"
gcloud config get-value project 2>/dev/null || echo "  (not set)"

echo ""
echo "Application Default Credentials (ADC):"
if gcloud auth application-default print-access-token > /dev/null 2>&1; then
    echo "  ✓ ADC working"
    quota_project=$(python3 -c "
import json, os
adc = os.path.expanduser('~/.config/gcloud/application_default_credentials.json')
try:
    with open(adc) as f:
        print(json.load(f).get('quota_project_id', 'not set'))
except Exception:
    print('unknown')
" 2>/dev/null)
    echo "  Quota project: ${quota_project}"
else
    echo "  ✗ ADC not configured"
    echo "  Run: gcloud auth application-default login"
fi

echo ""
echo "All authenticated accounts:"
gcloud auth list 2>&1 | grep -E "^\*?[[:space:]]" | head -10 || true
