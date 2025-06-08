#!/bin/bash
set -e

docker compose run --quiet-pull --no-deps --rm -v $(pwd):/app app make generate_requirements

# Deploy HTTP-triggered function for Alertmanager webhook
GCF_HTTP_FN=alertmanager-to-notion-webhook
GCF_EVENT_FN=alertmanager-to-notion-handler

# Get next values from your terraform.tfvars and terraform output
EVENTS_PUBSUB_TOPIC=alertmanager-events
GCF_SA=alert-manager-to-notion@${GCP_PROJECT_ID}.iam.gserviceaccount.com

# HTTP function (webhook)
gcloud functions deploy $GCF_HTTP_FN \
  --trigger-http \
  --entry-point=handle_http_request \
  --service-account=$GCF_SA \
  --gen2 --allow-unauthenticated \
  --region=${GCP_REGION} \
  --runtime=python312 --verbosity=debug \
  --set-env-vars="SETTINGS_MODULE=app.settings,GCP_PROJECT_ID=${GCP_PROJECT_ID}" \
  --set-secrets "EVENTS_PUBSUB_TOPIC=projects/${GCP_PROJECT_ID}/secrets/EVENTS_PUBSUB_TOPIC:latest,\
AM2N_NOTION_TOKEN=projects/${GCP_PROJECT_ID}/secrets/AM2N_NOTION_TOKEN:latest,\
AM2N_NOTION_DB_ID=projects/${GCP_PROJECT_ID}/secrets/AM2N_NOTION_DB_ID:latest,\
AM2N_HTTP_HEADER_NAME=projects/${GCP_PROJECT_ID}/secrets/AM2N_HTTP_HEADER_NAME:latest,\
AM2N_HTTP_HEADER_VALUE=projects/${GCP_PROJECT_ID}/secrets/AM2N_HTTP_HEADER_VALUE:latest"

# PubSub event function (handler)
gcloud functions deploy $GCF_EVENT_FN \
  --trigger-topic=${EVENTS_PUBSUB_TOPIC} \
  --entry-point=handle_event \
  --service-account=$GCF_SA \
  --gen2 \
  --region=${GCP_REGION} \
  --runtime=python312 --verbosity=debug \
  --set-env-vars="SETTINGS_MODULE=app.settings,GCP_PROJECT_ID=${GCP_PROJECT_ID}" \
  --set-secrets "EVENTS_PUBSUB_TOPIC=projects/${GCP_PROJECT_ID}/secrets/EVENTS_PUBSUB_TOPIC:latest,\
AM2N_NOTION_TOKEN=projects/${GCP_PROJECT_ID}/secrets/AM2N_NOTION_TOKEN:latest,\
AM2N_NOTION_DB_ID=projects/${GCP_PROJECT_ID}/secrets/AM2N_NOTION_DB_ID:latest,\
AM2N_HTTP_HEADER_NAME=projects/${GCP_PROJECT_ID}/secrets/AM2N_HTTP_HEADER_NAME:latest,\
AM2N_HTTP_HEADER_VALUE=projects/${GCP_PROJECT_ID}/secrets/AM2N_HTTP_HEADER_VALUE:latest"
