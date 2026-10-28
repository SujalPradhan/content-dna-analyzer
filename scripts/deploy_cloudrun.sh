#!/usr/bin/env bash
# Deploy the Content DNA API + web app to Google Cloud Run (scales to zero; free tier covers a demo).
#
#   ./scripts/deploy_cloudrun.sh            # first run: creates secrets from .env, then deploys
#   ./scripts/deploy_cloudrun.sh            # later runs: just redeploys the current code
#
# API_KEY (LLM Foundry, from .env) lives in Secret Manager, never in the image. The public demo needs no login:
# spending is admitted up front (DAILY_VIDEOS new videos and DAILY_BUDGET dollars a day, PER_HOUR per visitor), so an
# admitted run always finishes. The count lives in a GCS bucket because Cloud Run loses its disk when it scales to zero.
# The demos are static files on GitHub Pages and never reach this server.
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT=$(gcloud config get-value project 2>/dev/null)
REGION=${REGION:-us-central1}
SERVICE=${SERVICE:-content-dna}
PAGES_ORIGIN=${PAGES_ORIGIN:-https://sujalpradhan.github.io}
DAILY_BUDGET=${DAILY_BUDGET:-1}
DAILY_VIDEOS=${DAILY_VIDEOS:-5}
PER_HOUR=${PER_HOUR:-3}
NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
SA="$NUMBER-compute@developer.gserviceaccount.com"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com --quiet

if ! gcloud secrets describe dna-api-key >/dev/null 2>&1; then
  grep -E '^API_KEY=' .env | head -1 | cut -d= -f2- | tr -d '"'"'"'\n' |
    gcloud secrets create dna-api-key --replication-policy=automatic --data-file=-
fi
gcloud secrets add-iam-policy-binding dna-api-key --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor --quiet >/dev/null
BUCKET="content-dna-state-$NUMBER"
gcloud storage buckets describe "gs://$BUCKET" >/dev/null 2>&1 ||
  gcloud storage buckets create "gs://$BUCKET" --location="$REGION" --uniform-bucket-level-access --quiet
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member="serviceAccount:$SA" --role=roles/storage.objectAdmin --quiet >/dev/null

# One instance with CPU always on: analyses run in background threads after the request returns, and job state is
# in that instance's memory/disk. Uploads are capped at 30 MB (Cloud Run's HTTP/1 request limit is 32 MiB).
gcloud run deploy "$SERVICE" --source . --region "$REGION" --allow-unauthenticated \
  --memory 2Gi --cpu 2 --no-cpu-throttling --min-instances 0 --max-instances 1 --timeout 900 \
  --set-secrets API_KEY=dna-api-key:latest \
  --set-env-vars DNA_BUDGET_USD=15,DNA_DAILY_BUDGET_USD=$DAILY_BUDGET,DNA_DAILY_VIDEOS=$DAILY_VIDEOS,DNA_PAID_PER_IP_HOUR=$PER_HOUR,DNA_STATE_BUCKET=$BUCKET,DNA_MAX_UPLOAD_MB=30,DNA_CORS_ORIGINS=$PAGES_ORIGIN --quiet

URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')
echo
echo "API + app:   $URL"
echo "Health:      $(curl -s "$URL/api/config")"
