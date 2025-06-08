#!/bin/bash
docker compose run --quiet-pull --no-deps --rm -v $(pwd):/app app make generate_requirements

gcloud functions deploy check-website-function-http --trigger-http --entry-point=handle_http_request \
--service-account=check-site-update-function@municipal-fairs.iam.gserviceaccount.com \
--gen2 --allow-unauthenticated --region=${GCP_REGION} --runtime=python312 --verbosity=debug \
--set-env-vars="SETTINGS_MODULE=app.settings,GCP_PROJECT_ID=${GCP_PROJECT_ID}" \
--set-secrets "EVENTS_PUBSUB_TOPIC=projects/${GCP_PROJECT_ID}/secrets/EVENTS_PUBSUB_TOPIC:latest,\
CSFU_HTTP_HEADER_NAME=projects/${GCP_PROJECT_ID}/secrets/CSFU_HTTP_HEADER_NAME:latest,\
CSFU_HTTP_HEADER_VALUE=projects/${GCP_PROJECT_ID}/secrets/CSFU_HTTP_HEADER_VALUE:latest,\
CSFU_TARGET_TIMEOUT=projects/${GCP_PROJECT_ID}/secrets/CSFU_TARGET_TIMEOUT:latest,\
CSFU_TARGETS=projects/${GCP_PROJECT_ID}/secrets/CSFU_TARGETS:latest,\
CSFU_WEBHOOK_URL=projects/${GCP_PROJECT_ID}/secrets/CSFU_WEBHOOK_URL:latest,\
CSFU_WEBHOOK_HEADERS=projects/${GCP_PROJECT_ID}/secrets/CSFU_WEBHOOK_HEADERS:latest,\
CSFU_WEBHOOK_RETRY_ATTEMPTS=projects/${GCP_PROJECT_ID}/secrets/CSFU_WEBHOOK_RETRY_ATTEMPTS:latest,\
CSFU_WEBHOOK_RETRY_WAIT=projects/${GCP_PROJECT_ID}/secrets/CSFU_WEBHOOK_RETRY_WAIT:latest,\
CSFU_WEBHOOK_TIMEOUT=projects/${GCP_PROJECT_ID}/secrets/CSFU_WEBHOOK_TIMEOUT:latest,\
CSFU_SNAPSHOTS_KEEP_LAST_DAYS=projects/${GCP_PROJECT_ID}/secrets/CSFU_SNAPSHOTS_KEEP_LAST_DAYS:latest,\
CSFU_PROXY=projects/${GCP_PROJECT_ID}/secrets/CSFU_PROXY:latest" \
&

gcloud functions deploy check-website-function-events --trigger-topic=hourly-trigger --entry-point=handle_event \
--service-account=check-site-update-function@municipal-fairs.iam.gserviceaccount.com \
--gen2 --region=${GCP_REGION} --runtime=python312 --verbosity=debug \
--set-env-vars="SETTINGS_MODULE=app.settings,GCP_PROJECT_ID=${GCP_PROJECT_ID}" \
--set-secrets "EVENTS_PUBSUB_TOPIC=projects/${GCP_PROJECT_ID}/secrets/EVENTS_PUBSUB_TOPIC:latest,\
CSFU_HTTP_HEADER_NAME=projects/${GCP_PROJECT_ID}/secrets/CSFU_HTTP_HEADER_NAME:latest,\
CSFU_HTTP_HEADER_VALUE=projects/${GCP_PROJECT_ID}/secrets/CSFU_HTTP_HEADER_VALUE:latest,\
CSFU_TARGET_TIMEOUT=projects/${GCP_PROJECT_ID}/secrets/CSFU_TARGET_TIMEOUT:latest,\
CSFU_TARGETS=projects/${GCP_PROJECT_ID}/secrets/CSFU_TARGETS:latest,\
CSFU_WEBHOOK_URL=projects/${GCP_PROJECT_ID}/secrets/CSFU_WEBHOOK_URL:latest,\
CSFU_WEBHOOK_HEADERS=projects/${GCP_PROJECT_ID}/secrets/CSFU_WEBHOOK_HEADERS:latest,\
CSFU_WEBHOOK_RETRY_ATTEMPTS=projects/${GCP_PROJECT_ID}/secrets/CSFU_WEBHOOK_RETRY_ATTEMPTS:latest,\
CSFU_WEBHOOK_RETRY_WAIT=projects/${GCP_PROJECT_ID}/secrets/CSFU_WEBHOOK_RETRY_WAIT:latest,\
CSFU_WEBHOOK_TIMEOUT=projects/${GCP_PROJECT_ID}/secrets/CSFU_WEBHOOK_TIMEOUT:latest,\
CSFU_SNAPSHOTS_KEEP_LAST_DAYS=projects/${GCP_PROJECT_ID}/secrets/CSFU_SNAPSHOTS_KEEP_LAST_DAYS:latest,\
CSFU_PROXY=projects/${GCP_PROJECT_ID}/secrets/CSFU_PROXY:latest"
