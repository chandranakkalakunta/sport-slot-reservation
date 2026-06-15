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

# In CI: FIREBASE_ACCESS_TOKEN is a real OAuth2 token minted by auth@v3
# via SA impersonation (sa-firebase-admin). Direct-WIF federated tokens
# are rejected by the Firebase Hosting REST API (401 UNAUTHENTICATED).
# Locally: falls back to gcloud auth print-access-token (interactive login).
if [[ -n "${FIREBASE_ACCESS_TOKEN:-}" ]]; then
  TOKEN="$FIREBASE_ACCESS_TOKEN"
else
  TOKEN="$(gcloud auth print-access-token)"
fi
[[ -n "$TOKEN" ]] || { echo "ERROR: no access token (CI: FIREBASE_ACCESS_TOKEN set? Local: gcloud auth login?)" >&2; exit 1; }
echo "Access token acquired (len ${#TOKEN})."
AUTH=( -H "Authorization: Bearer ${TOKEN}" -H "X-Goog-User-Project: ${PROJECT}" )

# Wrapper: prints HTTP status + response body on >=400 so failures are
# diagnosable rather than a terse curl exit code.
api() {
  local method="$1" url="$2"; shift 2
  local body http
  body="$(curl -sS -w $'\n%{http_code}' "${AUTH[@]}" -X "$method" "$url" "$@")" || {
    echo "ERROR: curl transport failure: $method $url" >&2; return 1; }
  http="$(printf '%s' "$body" | tail -n1)"
  body="$(printf '%s' "$body" | sed '$d')"
  if [[ "$http" -ge 400 ]]; then
    echo "ERROR: $method $url -> HTTP $http" >&2
    echo "$body" >&2
    return 1
  fi
  printf '%s' "$body"
}

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

# ---- CONFIG: translate firebase.json (CLI syntax) → REST API Version.config ----
# firebase.json uses CLI fields (source/destination); REST API requires glob/path.
# Without this translation the version-create returns 400 INVALID_ARGUMENT.
# Result: SPA catch-all {"glob":"**","path":"/index.html"} + Cloud Run rewrites.
CONFIG_JSON="$(python3 - <<'PY'
import json
def translate(h):
    cfg={}
    rw=[]
    for r in h.get("rewrites",[]):
        item={}
        if "source" in r: item["glob"]=r["source"]
        elif "regex" in r: item["regex"]=r["regex"]
        if "destination" in r: item["path"]=r["destination"]
        elif "function" in r: item["function"]=r["function"]
        elif "run" in r: item["run"]=r["run"]
        rw.append(item)
    if rw: cfg["rewrites"]=rw
    rd=[]
    for r in h.get("redirects",[]):
        item={}
        if "source" in r: item["glob"]=r["source"]
        elif "regex" in r: item["regex"]=r["regex"]
        if "destination" in r: item["location"]=r["destination"]
        if "type" in r: item["statusCode"]=r["type"]
        rd.append(item)
    if rd: cfg["redirects"]=rd
    hd=[]
    for r in h.get("headers",[]):
        item={}
        if "source" in r: item["glob"]=r["source"]
        elif "regex" in r: item["regex"]=r["regex"]
        item["headers"]=r.get("headers",[])
        hd.append(item)
    if hd: cfg["headers"]=hd
    for k in ("cleanUrls","trailingSlash","appAssociation","i18n"):
        if k in h: cfg[k]=h[k]
    return cfg
try:
    fb=json.load(open("firebase.json"))
    h=fb.get("hosting",{})
    if isinstance(h,list): h=h[0]
    print(json.dumps({"config":translate(h)}))
except Exception:
    print('{"config":{}}')
PY
)"

ver_resp="$(api POST "${API}/sites/${SITE}/versions" \
  -H "Content-Type: application/json" -d "${CONFIG_JSON}")"
VERSION="$(printf '%s' "$ver_resp" | python3 -c 'import sys,json;print(json.load(sys.stdin)["name"])')"
echo "Created version: $VERSION"

pop_resp="$(api POST "${API}/${VERSION}:populateFiles" \
  -H "Content-Type: application/json" -d "{\"files\": $(cat "$manifest")}")"
printf '%s' "$pop_resp" | python3 -c \
  'import sys,json;[print(h) for h in (json.load(sys.stdin).get("uploadRequiredHashes") or [])]' \
  > "$work/required.txt" || true
echo "Hosting requests $(wc -l < "$work/required.txt" | tr -d ' ') uploads."

uploadUrl="${UPLOAD_API}/sites/${SITE}/versions/$(basename "$VERSION")/files"
while IFS= read -r need; do
  [[ -z "$need" ]] && continue
  gz="$(awk -v h="$need" '$1==h{print $2; exit}' "$maplist")"
  [[ -n "$gz" ]] || { echo "WARN: no file for hash $need" >&2; continue; }
  up_body="$(curl -sS -w $'\n%{http_code}' "${AUTH[@]}" \
    -H "Content-Type: application/octet-stream" \
    -X POST "${uploadUrl}/${need}" --data-binary "@${gz}")" || {
    echo "ERROR: curl transport failure uploading $need" >&2; exit 1; }
  up_http="$(printf '%s' "$up_body" | tail -n1)"
  if [[ "$up_http" -ge 400 ]]; then
    echo "ERROR: upload $need -> HTTP $up_http" >&2
    printf '%s' "$up_body" | sed '$d' >&2
    exit 1
  fi
  echo "  uploaded $need"
done < "$work/required.txt"

api PATCH "${API}/${VERSION}?update_mask=status" \
  -H "Content-Type: application/json" -d '{"status":"FINALIZED"}' >/dev/null
echo "Finalized."

api POST "${API}/sites/${SITE}/releases?versionName=${VERSION}" \
  -H "Content-Type: application/json" -d '{}' >/dev/null
echo "Released to live: https://${SITE}.web.app"
