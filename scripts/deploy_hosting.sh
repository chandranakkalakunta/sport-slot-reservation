#!/usr/bin/env bash
# Coordinator-run. Builds the PWA and deploys to Firebase Hosting.
# Default domain: https://sport-slot-dev.web.app (custom domain = 4.5b).
set -euo pipefail

PROJECT="${FIREBASE_PROJECT:-sport-slot-dev}"

echo "Building frontend (pnpm build)..."
(cd frontend && pnpm build)

echo "Deploying to Firebase Hosting (project ${PROJECT})..."
echo "Requires: firebase login as admin@chandraailabs.com (or WIF ADC in CI)"
echo "firebase-tools version: $(firebase --version)"
# Skip interactive confirmation in CI (CI=true is set by GitHub Actions).
if [ -z "${CI:-}" ]; then
  read -r -p "Type DEPLOY to proceed: " CONFIRM
  [[ "$CONFIRM" == "DEPLOY" ]] || { echo "Aborted."; exit 1; }
fi

if [ -n "${CI:-}" ]; then
  # Keyless: firebase-tools uses the WIF external_account ADC
  # (GOOGLE_APPLICATION_CREDENTIALS, set by google-github-actions/auth).
  # GOOGLE_CLOUD_PROJECT lets it resolve the project (external_account
  # files embed no project, unlike JSON keys). NO FIREBASE_TOKEN.
  # --debug enabled until CI deploy is confirmed green.
  firebase deploy --only hosting --project "${PROJECT}" --non-interactive --debug
else
  firebase deploy --only hosting --project "${PROJECT}"
fi

echo "Deployed. Live at https://${PROJECT}.web.app"
echo "API reachable same-origin via /api/** rewrite to Cloud Run."
