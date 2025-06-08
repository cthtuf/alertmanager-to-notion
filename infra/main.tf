# Terraform configuration to deploy infrastructure for Google Cloud Function Gen2 and required resources

# Required Providers
provider "google" {
  project = var.project_id
  region  = var.region
}

resource "null_resource" "wait_for_one_minute" {
  provisioner "local-exec" {
    command = "sleep 60"
  }
}

# APIs
resource "google_project_service" "firebase_api" {
  project = var.project_id
  service = "firebase.googleapis.com"
  timeouts {
    create = "5m"
  }
}

resource "google_project_service" "firestore_api" {
  project = var.project_id
  service = "firestore.googleapis.com"
  timeouts {
    create = "5m"
  }
}

resource "google_project_service" "cloudrun_api" {
  project = var.project_id
  service = "run.googleapis.com"
  timeouts {
    create = "5m"
  }
}

resource "google_project_service" "cloudfunctions_api" {
  project = var.project_id
  service = "cloudfunctions.googleapis.com"
  timeouts {
    create = "5m"
  }
}

resource "google_project_service" "eventarc_api" {
  project = var.project_id
  service = "eventarc.googleapis.com"
  timeouts {
    create = "5m"
  }
}

resource "google_project_service" "cloud_build_api" {
  project = var.project_id
  service = "cloudbuild.googleapis.com"
  timeouts {
    create = "5m"
  }
}

resource "google_project_service" "artifact_registry_api" {
  project = var.project_id
  service = "artifactregistry.googleapis.com"
  timeouts {
    create = "5m"
  }
}

resource "google_project_service" "cloud_scheduler_api" {
  project = var.project_id
  service = "cloudscheduler.googleapis.com"
  timeouts {
    create = "5m"
  }
}

resource "google_project_service" "container_registry_api" {
  project = var.project_id
  service = "containerregistry.googleapis.com"
  timeouts {
    create = "5m"
  }
}

resource "google_project_service" "pubsub_api" {
  project = var.project_id
  service = "pubsub.googleapis.com"
  timeouts {
    create = "5m"
  }
  depends_on = [
    google_project_service.container_registry_api,
  ]
}

resource "google_project_service" "cloud_resource_management_api" {
  project = var.project_id
  service = "cloudresourcemanager.googleapis.com"
  timeouts {
    create = "5m"
  }
}

resource "google_project_service" "serviceusage_api" {
  project = var.project_id
  service = "serviceusage.googleapis.com"
  timeouts {
    create = "5m"
  }
}

resource "google_project_service" "secret_manager_api" {
  project = var.project_id
  service = "secretmanager.googleapis.com"
  timeouts {
    create = "5m"
  }
}

resource "google_project_service" "compute_engine_api" {
  project = var.project_id
  service = "compute.googleapis.com"
  timeouts {
    create = "5m"
  }
}

# Service account for GitHub Actions with permissions to deploy Cloud Functions
resource "google_service_account" "gha_sa" {
  account_id   = "github-actions-sa"
  display_name = "GitHub Actions Service Account"
  depends_on = [
    google_project_service.cloudrun_api,
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_project_iam_member" "functions_deploy_roles" {
  for_each = toset([
    "roles/cloudfunctions.developer",
    "roles/iam.serviceAccountUser",
    "roles/viewer",
    "roles/run.admin",
  ])

  project = var.project_id
  member  = "serviceAccount:${google_service_account.gha_sa.email}"
  role    = each.value
}

resource "google_service_account_key" "gha_sa_key" {
  service_account_id = google_service_account.gha_sa.name
  private_key_type   = "TYPE_GOOGLE_CREDENTIALS_FILE"
}

resource "local_file" "gha_sa_key_json" {
  filename = "${path.module}/../config/ghsa.json"
  file_permission = "0440"
  content  = base64decode(google_service_account_key.gha_sa_key.private_key)
}

resource "google_service_account" "check_site_update_function_sa" {
  account_id   = "check-site-update-function"
  display_name = "Service Account for CheckSiteUpdates"
  depends_on = [
    google_project_service.firebase_api,
    google_project_service.firestore_api,
    google_project_service.cloudrun_api,
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

# Roles for the functions service account
resource "google_project_iam_member" "function_sa_roles" {
  project = var.project_id
  member  = "serviceAccount:${google_service_account.check_site_update_function_sa.email}"
  for_each = toset([
    "roles/firebase.admin",
    "roles/cloudfunctions.developer",
    "roles/secretmanager.secretAccessor",
    "roles/logging.logWriter",
    "roles/pubsub.publisher",
    "roles/cloudscheduler.admin",
    "roles/run.admin",
    "roles/iam.serviceAccountUser",
  ])
  role = each.value
}

resource "google_firestore_database" "default" {
  name            = "(default)"
  project         = var.project_id
  location_id     = var.region
  type            = "FIRESTORE_NATIVE"
  deletion_policy = "DELETE"
  depends_on = [
    google_project_service.firestore_api,
  ]
}

# Firestore Index
resource "google_firestore_index" "website_content_index" {
  project       = var.project_id
  collection    = "website_content"  # This is a model in app/models.py
  query_scope   = "COLLECTION"

  fields {
    field_path = "url"
    order      = "ASCENDING"
  }

  fields {
    field_path = "timestamp"
    order      = "DESCENDING"
  }

  fields {
    field_path = "__name__"
    order      = "DESCENDING"
  }

  depends_on = [
    google_firestore_database.default,
  ]
}

resource "google_pubsub_topic" "events_topic" {
  name = var.events_pubsub_topic

  depends_on = [
    google_project_service.pubsub_api,
  ]
}

# Google Cloud Scheduler Job
resource "google_cloud_scheduler_job" "hourly_job" {
  name      = "hourly-check-job"
  schedule  = "0 * * * *" # Каждый час
  time_zone = "UTC"

  pubsub_target {
    topic_name = google_pubsub_topic.events_topic.id
    data       = base64encode("Hourly trigger for website check")  # Specify payload if you need
  }

  depends_on = [
    google_project_service.cloud_scheduler_api,
    google_project_service.pubsub_api,
    google_pubsub_topic.events_topic,
  ]
}

resource "null_resource" "generate_requirements" {
  provisioner "local-exec" {
    command = "docker compose run --quiet-pull --no-deps --rm -v $(pwd):/app app make generate_requirements"
    working_dir = "${path.module}/../"
  }
  triggers = {
    always_run = timestamp()
  }
}

resource "google_cloudfunctions2_function" "check_website_events" {
  name     = "check-website-function-events"
  location = var.region

  build_config {
    runtime     = "python312"
    entry_point = "handle_event"
    environment_variables = {
      GCP_PROJECT_ID = var.project_id
      SETTINGS_MODULE= "app.settings"
    }
    source {
      storage_source {
        bucket = google_storage_bucket.csu_bucket.name
        object = google_storage_bucket_object.csu_archive.name
      }
    }
  }

  service_config {
    available_memory   = "256M"
    service_account_email = google_service_account.check_site_update_function_sa.email
    environment_variables = {
        GCP_PROJECT_ID = var.project_id
        SETTINGS_MODULE = "app.settings"
    }
    ingress_settings = "ALLOW_INTERNAL_ONLY"

    secret_environment_variables {
      key    = "EVENTS_PUBSUB_TOPIC"
      secret = google_secret_manager_secret.events_pubsub_topic.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_HTTP_HEADER_NAME"
      secret = google_secret_manager_secret.csfu_http_header_name.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_HTTP_HEADER_VALUE"
      secret = google_secret_manager_secret.csfu_http_header_value.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_TARGETS"
      secret = google_secret_manager_secret.csfu_targets.secret_id
      version = "latest"
      project_id = var.project_id
    }
    secret_environment_variables {
      key    = "CSFU_TARGET_TIMEOUT"
      secret = google_secret_manager_secret.csfu_target_timeout.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_WEBHOOK_URL"
      secret = google_secret_manager_secret.csfu_webhook_url.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_WEBHOOK_HEADERS"
      secret = google_secret_manager_secret.csfu_webhook_headers.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_WEBHOOK_RETRY_ATTEMPTS"
      secret = google_secret_manager_secret.csfu_webhook_retry_attempts.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_WEBHOOK_RETRY_WAIT"
      secret = google_secret_manager_secret.csfu_webhook_retry_wait.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_WEBHOOK_TIMEOUT"
      secret = google_secret_manager_secret.csfu_webhook_timeout.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_SNAPSHOTS_KEEP_LAST_DAYS"
      secret = google_secret_manager_secret.csfu_snapshots_keep_last_days.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_PROXY"
      secret = google_secret_manager_secret.csfu_proxy.secret_id
      version = "latest"
      project_id = var.project_id
    }
  }

  event_trigger {
    trigger_region = var.region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.events_topic.id
  }

  depends_on = [
    google_project_service.cloud_build_api,
    google_project_service.cloudrun_api,
    google_project_service.cloudfunctions_api,
    google_project_service.pubsub_api,
    google_project_service.eventarc_api,
    google_project_service.artifact_registry_api,
    google_project_service.secret_manager_api,
    google_secret_manager_secret.csfu_http_header_name,
    google_secret_manager_secret.csfu_http_header_value,
    google_secret_manager_secret.csfu_targets,
    google_secret_manager_secret.csfu_webhook_url,
    google_secret_manager_secret.csfu_proxy,
    google_secret_manager_secret.events_pubsub_topic,
    google_secret_manager_secret.csfu_webhook_retry_attempts,
    google_secret_manager_secret.csfu_webhook_retry_wait,
    google_secret_manager_secret.csfu_webhook_timeout,
    google_secret_manager_secret.db_timezone,
    google_secret_manager_secret.csfu_snapshots_keep_last_days,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_cloudfunctions2_function" "check_website_http" {
  name     = "check-website-function-http"
  location = var.region

  build_config {
    runtime     = "python312"
    entry_point = "handle_http_request"
    environment_variables = {
      GCP_PROJECT_ID  = var.project_id
      SETTINGS_MODULE = "app.settings"
    }
    source {
      storage_source {
        bucket = google_storage_bucket.csu_bucket.name
        object = google_storage_bucket_object.csu_archive.name
      }
    }
  }

  service_config {
    available_memory      = "256M"
    service_account_email = google_service_account.check_site_update_function_sa.email
    ingress_settings      = "ALLOW_ALL" # Доступ открыт для всех, можно ограничить
    environment_variables = {
      GCP_PROJECT_ID   = var.project_id
      SETTINGS_MODULE  = "app.settings"
    }
    # Adding secrets as environment variables
    secret_environment_variables {
      key    = "EVENTS_PUBSUB_TOPIC"
      secret = google_secret_manager_secret.events_pubsub_topic.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_HTTP_HEADER_NAME"
      secret = google_secret_manager_secret.csfu_http_header_name.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_HTTP_HEADER_VALUE"
      secret = google_secret_manager_secret.csfu_http_header_value.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_TARGETS"
      secret = google_secret_manager_secret.csfu_targets.secret_id
      version = "latest"
      project_id = var.project_id
    }
    secret_environment_variables {
      key    = "CSFU_TARGET_TIMEOUT"
      secret = google_secret_manager_secret.csfu_target_timeout.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_WEBHOOK_URL"
      secret = google_secret_manager_secret.csfu_webhook_url.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_WEBHOOK_HEADERS"
      secret = google_secret_manager_secret.csfu_webhook_headers.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_WEBHOOK_RETRY_ATTEMPTS"
      secret = google_secret_manager_secret.csfu_webhook_retry_attempts.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_WEBHOOK_RETRY_WAIT"
      secret = google_secret_manager_secret.csfu_webhook_retry_wait.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_WEBHOOK_TIMEOUT"
      secret = google_secret_manager_secret.csfu_webhook_timeout.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_SNAPSHOTS_KEEP_LAST_DAYS"
      secret = google_secret_manager_secret.csfu_snapshots_keep_last_days.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "CSFU_PROXY"
      secret = google_secret_manager_secret.csfu_proxy.secret_id
      version = "latest"
      project_id = var.project_id
    }
  }

  depends_on = [
    google_project_service.cloudrun_api,
    google_project_service.cloudfunctions_api,
    google_project_service.cloud_build_api,
    google_project_service.artifact_registry_api,
    google_project_service.secret_manager_api,
    google_secret_manager_secret.csfu_http_header_name,
    google_secret_manager_secret.csfu_http_header_value,
    google_secret_manager_secret.csfu_targets,
    google_secret_manager_secret.csfu_webhook_url,
    google_secret_manager_secret.csfu_proxy,
    google_secret_manager_secret.events_pubsub_topic,
    google_secret_manager_secret.csfu_webhook_retry_attempts,
    google_secret_manager_secret.csfu_webhook_retry_wait,
    google_secret_manager_secret.csfu_webhook_timeout,
    google_secret_manager_secret.db_timezone,
    google_secret_manager_secret.csfu_snapshots_keep_last_days,
    null_resource.wait_for_one_minute,
  ]
}

data "archive_file" "csu_sources_archive" {
  type        = "zip"
  source_dir  = "${path.module}/../"
  output_path = "${path.module}/csu_sources_archive.zip"

  excludes = [
    ".git",
    "infra",
    "tests",
    "config",
    ".idea",
    ".*_cache",
    "__pycache__",
    "app/__pycache__",
    ".coverage",
    ".editorconfig",
  ]
  depends_on = [
    null_resource.generate_requirements,
  ]
}

resource "google_storage_bucket" "csu_bucket" {
  name     = "csu_code_bucket-${var.project_id}"
  location = var.region
}

resource "google_storage_bucket_object" "csu_archive" {
  name         = "csu_check_website.zip"
  bucket       = google_storage_bucket.csu_bucket.name
  source       = data.archive_file.csu_sources_archive.output_path
  content_type = "application/zip"
}

resource "google_cloud_run_service_iam_member" "function_invoker" {
  service  = google_cloudfunctions2_function.check_website_http.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
  depends_on = [
    google_cloudfunctions2_function.check_website_http,
  ]
}

# Google Secret Manager Secrets
resource "google_secret_manager_secret" "csfu_targets" {
  secret_id = "CSFU_TARGETS"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}
resource "google_secret_manager_secret_version" "target_url_version" {
  secret      = google_secret_manager_secret.csfu_targets.id
  secret_data = var.csfu_targets
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "csfu_target_timeout" {
  secret_id = "CSFU_TARGET_TIMEOUT"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}
resource "google_secret_manager_secret_version" "csfu_target_timeout_version" {
  secret      = google_secret_manager_secret.csfu_target_timeout.id
  secret_data = var.csfu_target_timeout
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "csfu_proxy" {
  secret_id = "CSFU_PROXY"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}
resource "google_secret_manager_secret_version" "csfu_proxy_version" {
  secret      = google_secret_manager_secret.csfu_proxy.id
  secret_data = var.csfu_proxy
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "csfu_http_header_name" {
  secret_id = "CSFU_HTTP_HEADER_NAME"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}
resource "google_secret_manager_secret_version" "csfu_http_header_name_version" {
  secret      = google_secret_manager_secret.csfu_http_header_name.id
  secret_data = var.csfu_http_header_name
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "csfu_http_header_value" {
  secret_id = "CSFU_HTTP_HEADER_VALUE"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}
resource "google_secret_manager_secret_version" "csfu_http_header_value_version" {
  secret      = google_secret_manager_secret.csfu_http_header_value.id
  secret_data = var.csfu_http_header_value
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "csfu_webhook_url" {
  secret_id = "CSFU_WEBHOOK_URL"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}
resource "google_secret_manager_secret_version" "webhook_url_version" {
  secret      = google_secret_manager_secret.csfu_webhook_url.id
  secret_data = var.csfu_webhook_url
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "csfu_webhook_headers" {
  secret_id = "CSFU_WEBHOOK_HEADERS"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}
resource "google_secret_manager_secret_version" "csfu_webhook_headers_version" {
  secret      = google_secret_manager_secret.csfu_webhook_headers.id
  secret_data = var.csfu_webhook_headers
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "csfu_webhook_retry_attempts" {
  secret_id = "CSFU_WEBHOOK_RETRY_ATTEMPTS"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}
resource "google_secret_manager_secret_version" "csfu_webhook_retry_attempts_version" {
  secret      = google_secret_manager_secret.csfu_webhook_retry_attempts.id
  secret_data = var.csfu_webhook_retry_attempts
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "csfu_webhook_retry_wait" {
  secret_id = "CSFU_WEBHOOK_RETRY_WAIT"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}
resource "google_secret_manager_secret_version" "csfu_webhook_retry_wait_version" {
  secret      = google_secret_manager_secret.csfu_webhook_retry_wait.id
  secret_data = var.csfu_webhook_retry_wait
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "csfu_webhook_timeout" {
  secret_id = "CSFU_WEBHOOK_TIMEOUT"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}
resource "google_secret_manager_secret_version" "csfu_webhook_timeout_version" {
  secret      = google_secret_manager_secret.csfu_webhook_timeout.id
  secret_data = var.csfu_webhook_timeout
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "db_timezone" {
  secret_id = "DB_TIMEZONE"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}
resource "google_secret_manager_secret_version" "db_timezone_version" {
  secret      = google_secret_manager_secret.db_timezone.id
  secret_data = var.db_timezone
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "csfu_snapshots_keep_last_days" {
  secret_id = "CSFU_SNAPSHOTS_KEEP_LAST_DAYS"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}
resource "google_secret_manager_secret_version" "csfu_snapshots_keep_last_days_version" {
  secret      = google_secret_manager_secret.csfu_snapshots_keep_last_days.id
  secret_data = var.csfu_snapshots_keep_last_days
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "events_pubsub_topic" {
  secret_id = "EVENTS_PUBSUB_TOPIC"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}
resource "google_secret_manager_secret_version" "events_pubsub_topic_version" {
  secret      = google_secret_manager_secret.events_pubsub_topic.id
  secret_data = var.events_pubsub_topic
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}
