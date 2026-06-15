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

# --non-interactive: required in CI (no TTY); firebase-tools will hang or
# emit "unexpected error" without it when stdin is not a terminal.
# --project: explicit to avoid ADC project inference failures in CI.
firebase deploy --only hosting --project "${PROJECT}" --non-interactive

echo "Deployed. Live at https://${PROJECT}.web.app"
echo "API reachable same-origin via /api/** rewrite to Cloud Run."
