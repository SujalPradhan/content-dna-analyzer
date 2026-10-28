#!/usr/bin/env bash
# Deploy the Content DNA API + web app to Google Cloud Run (scales to zero; free tier covers a demo).
#
#   ./scripts/deploy_cloudrun.sh            # first run: creates secrets from .env, then deploys
#   ./scripts/deploy_cloudrun.sh            # later runs: just redeploys the current code
#
# Secrets live in Secret Manager, never in the image: API_KEY (LLM Foundry) from .env, and a demo access code that
# the web app asks for before it spends LLM credit. Reads (demos, scorecards, frames) stay open.
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT=$(gcloud config get-value project 2>/dev/null)
REGION=${REGION:-us-central1}
SERVICE=${SERVICE:-content-dna}
PAGES_ORIGIN=${PAGES_ORIGIN:-https://sujalpradhan.github.io}
NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
SA="$NUMBER-compute@developer.gserviceaccount.com"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com --quiet

if ! gcloud secrets describe dna-api-key >/dev/null 2>&1; then
  grep -E '^API_KEY=' .env | head -1 | cut -d= -f2- | tr -d '"'"'"'\n' |
    gcloud secrets create dna-api-key --replication-policy=automatic --data-file=-
fi
if ! gcloud secrets describe dna-access-code >/dev/null 2>&1; then
  printf %s "cda-$(openssl rand -hex 3)" | gcloud secrets create dna-access-code --replication-policy=automatic --data-file=-
fi
for s in dna-api-key dna-access-code; do
  gcloud secrets add-iam-policy-binding "$s" --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor --quiet >/dev/null
done

# One instance with CPU always on: analyses run in background threads after the request returns, and job state is
# in that instance's memory/disk. Uploads are capped at 30 MB (Cloud Run's HTTP/1 request limit is 32 MiB).
gcloud run deploy "$SERVICE" --source . --region "$REGION" --allow-unauthenticated \
  --memory 2Gi --cpu 2 --no-cpu-throttling --min-instances 0 --max-instances 1 --timeout 900 \
  --set-secrets API_KEY=dna-api-key:latest,DNA_ACCESS_CODE=dna-access-code:latest \
  --set-env-vars DNA_BUDGET_USD=15,DNA_MAX_UPLOAD_MB=30,DNA_CORS_ORIGINS=$PAGES_ORIGIN --quiet

URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')
echo
echo "API + app:   $URL"
echo "Health:      $(curl -s "$URL/api/config")"
echo "Access code: $(gcloud secrets versions access latest --secret=dna-access-code)"
