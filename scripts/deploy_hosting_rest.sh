#!/usr/bin/env bash
# Keyless Firebase Hosting deploy via REST API + gcloud access token.
# No firebase-tools, no JSON key, no FIREBASE_TOKEN. WIF-compatible.
# firebase-tools 15.x cannot consume WIF external_account ADC for
# deploys (its token manager only knows user/login:ci tokens), so we
# drive the Hosting REST API directly with a gcloud-minted token.
# Ref: https://firebase.google.com/docs/hosting/api-deploy
set -euo pipefail

cd "$(dirname "$0")/.."

PROJECT="${FIREBASE_PROJECT:-sport-slot-dev}"
SITE="${FIREBASE_SITE:-$PROJECT}"
PUBLIC_DIR="${PUBLIC_DIR:-frontend/dist}"
API="https://firebasehosting.googleapis.com/v1beta1"
UPLOAD_API="https://upload-firebasehosting.googleapis.com/upload"

# Mint the token FROM the ADC (the WIF external_account credential).
# Plain `gcloud auth print-access-token` reads the active-account
# store (empty in CI); the WIF cred lives in ADC.
TOKEN="$(gcloud auth application-default print-access-token)"
[[ -n "$TOKEN" ]] || { echo "ERROR: no gcloud ADC access token (GOOGLE_APPLICATION_CREDENTIALS set?)" >&2; exit 1; }
echo "Access token acquired (len ${#TOKEN})."
AUTH=( -H "Authorization: Bearer ${TOKEN}" -H "X-Goog-User-Project: ${PROJECT}" )

echo "Deploying ${PUBLIC_DIR} -> Hosting site '${SITE}' (project ${PROJECT})"
[[ -d "$PUBLIC_DIR" ]] || { echo "ERROR: '$PUBLIC_DIR' not found (frontend built?)" >&2; exit 1; }

work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
manifest="$work/manifest.json"
printf '{' > "$manifest"
first=1
maplist="$work/maplist.txt"
: > "$maplist"

while IFS= read -r -d '' f; do
  rel="${f#"$PUBLIC_DIR"}"
  [[ "$rel" = /* ]] || rel="/$rel"
  gz="$work/$(printf '%s' "$rel" | sha1sum | cut -d' ' -f1).gz"
  gzip -n -c "$f" > "$gz"
  hash="$(sha256sum "$gz" | cut -d' ' -f1)"
  if [[ $first -eq 1 ]]; then first=0; else printf ',' >> "$manifest"; fi
  esc=$(printf '%s' "$rel" | sed 's/\\/\\\\/g; s/"/\\"/g')
  printf '"%s":"%s"' "$esc" "$hash" >> "$manifest"
  echo "$hash $gz $rel" >> "$maplist"
done < <(find "$PUBLIC_DIR" -type f -print0)

printf '}' >> "$manifest"
echo "Prepared $(wc -l < "$maplist" | tr -d ' ') files."

# ---- CONFIG: read hosting rewrites/headers from firebase.json (SPA!) ----
# Passes the config object (rewrites etc.) to the version-create call so
# the SPA catch-all rewrite {"source":"**","destination":"/index.html"} and
# Cloud Run rewrites are active — without this, deep links return 404.
CONFIG_JSON="$(python3 - <<'PY'
import json, sys
try:
    fb = json.load(open("firebase.json"))
    h = fb.get("hosting", {})
    if isinstance(h, list):
        h = h[0]
    cfg = {}
    for k in ("rewrites", "redirects", "headers", "cleanUrls", "trailingSlash", "appAssociation", "i18n"):
        if k in h:
            cfg[k] = h[k]
    print(json.dumps({"config": cfg}))
except Exception:
    print('{"config":{}}')
PY
)"

ver_resp="$(curl -fsS "${AUTH[@]}" -H "Content-Type: application/json" \
  -X POST "${API}/sites/${SITE}/versions" -d "${CONFIG_JSON}")"
VERSION="$(echo "$ver_resp" | python3 -c 'import sys,json;print(json.load(sys.stdin)["name"])')"
echo "Created version: $VERSION"

pop_resp="$(curl -fsS "${AUTH[@]}" -H "Content-Type: application/json" \
  -X POST "${API}/${VERSION}:populateFiles" -d "{\"files\": $(cat "$manifest")}")"
echo "$pop_resp" | python3 -c \
  'import sys,json;[print(h) for h in (json.load(sys.stdin).get("uploadRequiredHashes") or [])]' \
  > "$work/required.txt" || true
echo "Hosting requests $(wc -l < "$work/required.txt" | tr -d ' ') uploads."

uploadUrl="${UPLOAD_API}/sites/${SITE}/versions/$(basename "$VERSION")/files"
while IFS= read -r need; do
  [[ -z "$need" ]] && continue
  gz="$(awk -v h="$need" '$1==h{print $2; exit}' "$maplist")"
  [[ -n "$gz" ]] || { echo "WARN: no file for hash $need" >&2; continue; }
  curl -fsS "${AUTH[@]}" -H "Content-Type: application/octet-stream" \
    -X POST "${uploadUrl}/${need}" --data-binary "@${gz}" >/dev/null
  echo "  uploaded $need"
done < "$work/required.txt"

curl -fsS "${AUTH[@]}" -H "Content-Type: application/json" \
  -X PATCH "${API}/${VERSION}?update_mask=status" -d '{"status":"FINALIZED"}' >/dev/null
echo "Finalized."

curl -fsS "${AUTH[@]}" -H "Content-Type: application/json" \
  -X POST "${API}/sites/${SITE}/releases?versionName=${VERSION}" -d '{}' >/dev/null
echo "Released to live: https://${SITE}.web.app"
