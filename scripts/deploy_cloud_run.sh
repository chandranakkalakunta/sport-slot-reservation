#!/usr/bin/env bash
# Deploy to Cloud Run (DEV). Coordinator-run. Guarded.
set -euo pipefail

PROJECT="sport-slot-dev"
REGION="asia-south1"
SERVICE="sport-slot-api"
SA="sa-cloud-run@${PROJECT}.iam.gserviceaccount.com"
TASKS_INVOKER_SA="sa-tasks-invoker@${PROJECT}.iam.gserviceaccount.com"
TASKS_QUEUE="notifications"
IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT}/sport-slot-repo/${SERVICE}"

cd "$(dirname "$0")/.."

TAG="${1:-$(cat .last_image_tag 2>/dev/null || true)}"
if [[ -z "$TAG" ]]; then
  echo "ERROR: no tag given and no .last_image_tag — run build_push.sh first" >&2
  exit 1
fi
IMAGE="${IMAGE_BASE}:${TAG}"

REDIS_INFO=$(gcloud redis instances describe sport-slot-redis \
  --region="$REGION" --project="$PROJECT" --format="value(host,port)") || {
  echo "ERROR: could not describe Redis instance sport-slot-redis in $REGION." >&2
  echo "  (Check the instance exists AND the caller has roles/redis.viewer.)" >&2
  exit 1
}
REDIS_HOST=$(echo "$REDIS_INFO" | cut -f1)
REDIS_PORT=$(echo "$REDIS_INFO" | cut -f2)
if [[ -z "$REDIS_HOST" ]]; then
  echo "ERROR: Redis instance returned empty host — run setup_redis_infra.sh first" >&2
  exit 1
fi

# SPORTSLOT_WORKER_BASE_URL is the worker's own Cloud Tasks OIDC
# audience (auth/tasks_auth.py), so it must come from the service's
# EXISTING URL, not the revision about to be deployed. Cloud Run
# service URLs are stable across revisions, so reading it before this
# deploy is safe. This requires the service to already exist — true
# for every deploy after the first.
WORKER_URL=$(gcloud run services describe "$SERVICE" --project="$PROJECT" \
  --region="$REGION" --format="value(status.url)") || {
  echo "ERROR: could not describe existing service ${SERVICE} for SPORTSLOT_WORKER_BASE_URL." >&2
  echo "  (First-ever deploy? Deploy once without the worker URL, then redeploy.)" >&2
  exit 1
}
if [[ -z "$WORKER_URL" ]]; then
  echo "ERROR: service ${SERVICE} returned an empty URL." >&2
  exit 1
fi

echo "About to deploy ${IMAGE}"
echo "  service=${SERVICE} region=${REGION} sa=${SA}"
echo "  min=0 max=2 mem=512Mi cpu=1 (ADR-0005)"
# Skip interactive confirmation in CI (CI=true is set by GitHub Actions).
if [ -z "${CI:-}" ]; then
  read -r -p "Type DEPLOY to proceed: " CONFIRM
  [[ "$CONFIRM" == "DEPLOY" ]] || { echo "Aborted."; exit 1; }
fi

gcloud run deploy "$SERVICE" \
  --project="$PROJECT" --region="$REGION" \
  --image="$IMAGE" \
  --service-account="$SA" \
  --allow-unauthenticated \
  --min-instances=0 --max-instances=2 \
  --memory=512Mi --cpu=1 \
  --set-env-vars="SPORTSLOT_ENVIRONMENT=development,SPORTSLOT_GCP_PROJECT=${PROJECT},SPORTSLOT_BASE_DOMAIN=sportbook.chandraailabs.com,SPORTSLOT_ADMIN_HOST=admin.sportbook.chandraailabs.com,SPORTSLOT_REDIS_HOST=${REDIS_HOST},SPORTSLOT_REDIS_PORT=${REDIS_PORT},SPORTSLOT_TASKS_QUEUE=${TASKS_QUEUE},SPORTSLOT_TASKS_LOCATION=${REGION},SPORTSLOT_WORKER_BASE_URL=${WORKER_URL},SPORTSLOT_TASKS_INVOKER_SA=${TASKS_INVOKER_SA}" \
  --network=default --subnet=default \
  --vpc-egress=private-ranges-only \
  --set-secrets="SPORTSLOT_REDIS_AUTH=redis-auth:latest,SPORTSLOT_RESEND_API_KEY=resend-api-key:latest"

URL=$(gcloud run services describe "$SERVICE" --project="$PROJECT" \
  --region="$REGION" --format="value(status.url)")
echo "Deployed. Service URL: ${URL}"
