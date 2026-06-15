#!/usr/bin/env bash
# Coordinator-run. Builds the PWA and deploys to Firebase Hosting.
# Default domain: https://sport-slot-dev.web.app (custom domain = 4.5b).
set -euo pipefail

echo "Building frontend (pnpm build)..."
(cd frontend && pnpm build)

echo "Deploying to Firebase Hosting (project sport-slot-dev)..."
echo "Requires: firebase login as admin@chandraailabs.com (or WIF ADC in CI)"
# Skip interactive confirmation in CI (CI=true is set by GitHub Actions).
if [ -z "${CI:-}" ]; then
  read -r -p "Type DEPLOY to proceed: " CONFIRM
  [[ "$CONFIRM" == "DEPLOY" ]] || { echo "Aborted."; exit 1; }
fi

firebase deploy --only hosting --project sport-slot-dev

echo "Deployed. Live at https://sport-slot-dev.web.app"
echo "API reachable same-origin via /api/** rewrite to Cloud Run."
