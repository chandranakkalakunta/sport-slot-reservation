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
  # firebase-tools 15.x does not reliably consume the WIF external-account
  # ADC (gha-creds JSON). gcloud DOES authenticate correctly via WIF —
  # mint a short-lived access token and hand it to firebase-tools.
  # Keyless: no JSON service-account key, no deprecated login:ci token.
  FIREBASE_TOKEN="$(gcloud auth print-access-token)"
  export FIREBASE_TOKEN
  firebase deploy --only hosting --project "${PROJECT}" --non-interactive || {
    echo "ERROR: firebase deploy failed. Re-run locally with --debug for details:" >&2
    echo "  FIREBASE_TOKEN=\$(gcloud auth print-access-token) firebase deploy --only hosting --project ${PROJECT} --non-interactive --debug" >&2
    exit 1
  }
else
  firebase deploy --only hosting --project "${PROJECT}"
fi

echo "Deployed. Live at https://${PROJECT}.web.app"
echo "API reachable same-origin via /api/** rewrite to Cloud Run."
