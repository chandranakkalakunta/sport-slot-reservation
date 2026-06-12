#!/usr/bin/env bash
# One-time: Memorystore Redis + AUTH secret + IAM (ADR-0009).
# Coordinator-run. Idempotent. Cost: Basic 1GB ≈ ₹2.5–3K/month.
set -euo pipefail

PROJECT="sport-slot-dev"
REGION="asia-south1"
INSTANCE="sport-slot-redis"
SECRET="redis-auth"
SA_RUN="sa-cloud-run@${PROJECT}.iam.gserviceaccount.com"

echo "Provisioning Memorystore Redis (Basic, 1GB, ${REGION})"
echo "NOTE: always-on cost ~Rs.2,500-3,000/month (trial-funded)."
read -r -p "Type SETUP to proceed: " CONFIRM
[[ "$CONFIRM" == "SETUP" ]] || { echo "Aborted."; exit 1; }

gcloud services enable redis.googleapis.com \
  secretmanager.googleapis.com --project "$PROJECT"

if gcloud redis instances describe "$INSTANCE" --region="$REGION" \
     --project="$PROJECT" >/dev/null 2>&1; then
  echo "Redis instance exists: $INSTANCE"
else
  gcloud redis instances create "$INSTANCE" \
    --project="$PROJECT" --region="$REGION" \
    --tier=basic --size=1 --redis-version=redis_7_0 \
    --network=default --enable-auth
  echo "Redis instance created."
fi

HOST=$(gcloud redis instances describe "$INSTANCE" --region="$REGION" \
  --project="$PROJECT" --format="value(host)")
PORT=$(gcloud redis instances describe "$INSTANCE" --region="$REGION" \
  --project="$PROJECT" --format="value(port)")
AUTH=$(gcloud redis instances get-auth-string "$INSTANCE" \
  --region="$REGION" --project="$PROJECT" --format="value(authString)")

if ! gcloud secrets describe "$SECRET" --project="$PROJECT" >/dev/null 2>&1; then
  gcloud secrets create "$SECRET" --project="$PROJECT" \
    --replication-policy="user-managed" --locations="$REGION"
  echo "Secret created: $SECRET"
fi
printf '%s' "$AUTH" | gcloud secrets versions add "$SECRET" \
  --project="$PROJECT" --data-file=-
echo "AUTH string stored in Secret Manager (new version)."

gcloud secrets add-iam-policy-binding "$SECRET" --project="$PROJECT" \
  --member="serviceAccount:${SA_RUN}" \
  --role="roles/secretmanager.secretAccessor" >/dev/null
echo "secretAccessor granted to ${SA_RUN}."

echo "Redis ready: host=${HOST} port=${PORT}"
echo "Deploy script will discover host/port automatically."
