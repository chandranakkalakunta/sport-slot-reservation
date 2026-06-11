#!/usr/bin/env bash
# One-time build infra: Artifact Registry repo + Cloud Build
# staging bucket in asia-south1. Coordinator-run. Idempotent.
set -euo pipefail

PROJECT="sport-slot-dev"
REGION="asia-south1"
AR_REPO="sport-slot-repo"
BUCKET="gs://${PROJECT}-cloudbuild"

echo "Setting up build infrastructure in ${PROJECT} (${REGION})"
read -r -p "Type SETUP to proceed: " CONFIRM
[[ "$CONFIRM" == "SETUP" ]] || { echo "Aborted."; exit 1; }

gcloud services enable artifactregistry.googleapis.com \
  cloudbuild.googleapis.com run.googleapis.com --project "$PROJECT"

if gcloud artifacts repositories describe "$AR_REPO" \
     --location="$REGION" --project="$PROJECT" >/dev/null 2>&1; then
  echo "AR repo exists: $AR_REPO"
else
  gcloud artifacts repositories create "$AR_REPO" \
    --repository-format=docker --location="$REGION" \
    --project="$PROJECT" \
    --description="SportSlot container images"
  echo "AR repo created: $AR_REPO"
fi

if gcloud storage buckets describe "$BUCKET" --project="$PROJECT" >/dev/null 2>&1; then
  echo "Staging bucket exists: $BUCKET"
else
  gcloud storage buckets create "$BUCKET" --project="$PROJECT" \
    --location="$REGION" --uniform-bucket-level-access
  echo "Staging bucket created: $BUCKET"
fi
echo "Build infrastructure ready."
