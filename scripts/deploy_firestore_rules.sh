#!/usr/bin/env bash
# Deploy Firestore Security Rules (Coordinator-run; needs
# firebase login). Guarded per ADR-0003.
set -euo pipefail

PROJECT="sport-slot-dev"
RULES_FILE="infrastructure/firestore.rules"

cd "$(dirname "$0")/.."

if ! command -v firebase >/dev/null 2>&1; then
  echo "ERROR: firebase CLI not found" >&2
  exit 1
fi
if [[ ! -f "$RULES_FILE" ]]; then
  echo "ERROR: $RULES_FILE not found" >&2
  exit 1
fi

echo "About to deploy Firestore rules to project: $PROJECT"
echo "Rules file: $RULES_FILE"
echo
read -r -p "Type DEPLOY to proceed: " CONFIRM
if [[ "$CONFIRM" != "DEPLOY" ]]; then
  echo "Aborted."
  exit 1
fi

firebase deploy --only firestore:rules --project "$PROJECT"
echo "Done. Verify in console: Firestore → Rules tab."
