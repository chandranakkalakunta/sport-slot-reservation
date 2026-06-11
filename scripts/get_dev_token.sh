#!/usr/bin/env bash
# Exchange email+password for a Firebase ID token (dev use).
# Usage: SPORTSLOT_WEB_API_KEY=... ./scripts/get_dev_token.sh EMAIL PASSWORD
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 EMAIL PASSWORD" >&2
  exit 1
fi
if [[ -z "${SPORTSLOT_WEB_API_KEY:-}" ]]; then
  echo "ERROR: SPORTSLOT_WEB_API_KEY not set" >&2
  exit 1
fi

RESPONSE=$(curl -s -X POST \
  "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${SPORTSLOT_WEB_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$1\",\"password\":\"$2\",\"returnSecureToken\":true}")

TOKEN=$(printf '%s' "$RESPONSE" | python3 -c \
  "import sys,json;d=json.load(sys.stdin);print(d.get('idToken',''))")

if [[ -z "$TOKEN" ]]; then
  echo "ERROR: no idToken in response:" >&2
  printf '%s\n' "$RESPONSE" >&2
  exit 1
fi
printf '%s\n' "$TOKEN"
