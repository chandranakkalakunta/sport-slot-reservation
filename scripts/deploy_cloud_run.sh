#!/usr/bin/env bash
# Deploy to Cloud Run (DEV). Coordinator-run. Guarded.
set -euo pipefail

PROJECT="sport-slot-dev"
REGION="asia-south1"
SERVICE="sport-slot-api"
SA="sa-cloud-run@${PROJECT}.iam.gserviceaccount.com"
IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT}/sport-slot-repo/${SERVICE}"

cd "$(dirname "$0")/.."

TAG="${1:-$(cat .last_image_tag 2>/dev/null || true)}"
if [[ -z "$TAG" ]]; then
  echo "ERROR: no tag given and no .last_image_tag — run build_push.sh first" >&2
  exit 1
fi
IMAGE="${IMAGE_BASE}:${TAG}"

echo "About to deploy ${IMAGE}"
echo "  service=${SERVICE} region=${REGION} sa=${SA}"
echo "  min=0 max=2 mem=512Mi cpu=1 (ADR-0005)"
read -r -p "Type DEPLOY to proceed: " CONFIRM
[[ "$CONFIRM" == "DEPLOY" ]] || { echo "Aborted."; exit 1; }

gcloud run deploy "$SERVICE" \
  --project="$PROJECT" --region="$REGION" \
  --image="$IMAGE" \
  --service-account="$SA" \
  --allow-unauthenticated \
  --min-instances=0 --max-instances=2 \
  --memory=512Mi --cpu=1 \
  --set-env-vars="SPORTSLOT_ENVIRONMENT=development,SPORTSLOT_GCP_PROJECT=${PROJECT},SPORTSLOT_BASE_DOMAIN=sportbook.chandraailabs.com,SPORTSLOT_ADMIN_HOST=admin.sportbook.chandraailabs.com"

URL=$(gcloud run services describe "$SERVICE" --project="$PROJECT" \
  --region="$REGION" --format="value(status.url)")
echo "Deployed. Service URL: ${URL}"
