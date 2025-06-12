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

resource "google_service_account" "alertmanager_to_notion_function_sa" {
  account_id   = "alert-manager-to-notion"
  display_name = "Service Account for AlertManager to Notion Function"
  depends_on = [
    google_project_service.cloudrun_api,
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

# Roles for the functions service account
resource "google_project_iam_member" "function_sa_roles" {
  project = var.project_id
  member  = "serviceAccount:${google_service_account.alertmanager_to_notion_function_sa.email}"
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

resource "google_pubsub_topic" "events_topic" {
  name = var.events_pubsub_topic

  depends_on = [
    google_project_service.pubsub_api,
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

resource "google_cloudfunctions2_function" "alertmanager_to_notion_handler" {
  name     = "alertmanager-to-notion-handler"
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
        bucket = google_storage_bucket.am2n_bucket.name
        object = google_storage_bucket_object.am2n_archive.name
      }
    }
  }

  service_config {
    available_memory      = "256M"
    service_account_email = google_service_account.alertmanager_to_notion_function_sa.email
    environment_variables = {
      GCP_PROJECT_ID  = var.project_id
      SETTINGS_MODULE = "app.settings"
    }
    ingress_settings = "ALLOW_INTERNAL_ONLY"

    secret_environment_variables {
      key        = "EVENTS_PUBSUB_TOPIC"
      secret     = google_secret_manager_secret.events_pubsub_topic.secret_id
      version    = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key        = "AM2N_NOTION_TOKEN"
      secret     = google_secret_manager_secret.am2n_notion_token.secret_id
      version    = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key        = "AM2N_INCIDENTS_DB_ID"
      secret     = google_secret_manager_secret.am2n_incidents_db_id.secret_id
      version    = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key        = "AM2N_SHIFTS_DB_ID"
      secret     = google_secret_manager_secret.am2n_shifts_db_id.secret_id
      version    = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key        = "AM2N_SHIFTS_ENABLED"
      secret     = google_secret_manager_secret.am2n_shifts_support_enabled.secret_id
      version    = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key        = "AM2N_HTTP_HEADER_NAME"
      secret     = google_secret_manager_secret.am2n_http_header_name.secret_id
      version    = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key        = "AM2N_HTTP_HEADER_VALUE"
      secret     = google_secret_manager_secret.am2n_http_header_value.secret_id
      version    = "latest"
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
    google_secret_manager_secret.am2n_notion_token,
    google_secret_manager_secret.am2n_incidents_db_id,
    google_secret_manager_secret.am2n_shifts_db_id,
    google_secret_manager_secret.am2n_shifts_support_enabled,
    google_secret_manager_secret.am2n_http_header_name,
    google_secret_manager_secret.am2n_http_header_value,
    google_secret_manager_secret.events_pubsub_topic,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_cloudfunctions2_function" "alertmanager_to_notion_webhook" {
  name     = "alertmanager-to-notion-webhook"
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
        bucket = google_storage_bucket.am2n_bucket.name
        object = google_storage_bucket_object.am2n_archive.name
      }
    }
  }

  service_config {
    available_memory      = "256M"
    service_account_email = google_service_account.alertmanager_to_notion_function_sa.email
    ingress_settings      = "ALLOW_ALL"
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
      key    = "AM2N_NOTION_TOKEN"
      secret = google_secret_manager_secret.am2n_notion_token.secret_id
      version = "latest"
      project_id = var.project_id
    }

        secret_environment_variables {
      key        = "AM2N_INCIDENTS_DB_ID"
      secret     = google_secret_manager_secret.am2n_incidents_db_id.secret_id
      version    = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key        = "AM2N_SHIFTS_DB_ID"
      secret     = google_secret_manager_secret.am2n_shifts_db_id.secret_id
      version    = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key        = "AM2N_SHIFTS_ENABLED"
      secret     = google_secret_manager_secret.am2n_shifts_support_enabled.secret_id
      version    = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "AM2N_HTTP_HEADER_NAME"
      secret = google_secret_manager_secret.am2n_http_header_name.secret_id
      version = "latest"
      project_id = var.project_id
    }

    secret_environment_variables {
      key    = "AM2N_HTTP_HEADER_VALUE"
      secret = google_secret_manager_secret.am2n_http_header_value.secret_id
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
    google_secret_manager_secret.am2n_http_header_name,
    google_secret_manager_secret.am2n_http_header_value,
    google_secret_manager_secret.am2n_notion_token,
    google_secret_manager_secret.am2n_incidents_db_id,
    google_secret_manager_secret.am2n_shifts_db_id,
    google_secret_manager_secret.am2n_shifts_support_enabled,
    google_secret_manager_secret.events_pubsub_topic,
    null_resource.wait_for_one_minute,
  ]
}

data "archive_file" "am2n_sources_archive" {
  type        = "zip"
  source_dir  = "${path.module}/../"
  output_path = "${path.module}/am2n_sources_archive.zip"

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

resource "google_storage_bucket" "am2n_bucket" {
  name     = "am2n_code_bucket-${var.project_id}"
  location = var.region
}

resource "google_storage_bucket_object" "am2n_archive" {
  name         = "am2n.zip"
  bucket       = google_storage_bucket.am2n_bucket.name
  source       = data.archive_file.am2n_sources_archive.output_path
  content_type = "application/zip"
}

resource "google_cloud_run_service_iam_member" "function_invoker" {
  service  = google_cloudfunctions2_function.alertmanager_to_notion_webhook.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
  depends_on = [
    google_cloudfunctions2_function.alertmanager_to_notion_webhook,
  ]
}

# Google Secret Manager Secrets
resource "google_secret_manager_secret" "am2n_http_header_name" {
  secret_id = "AM2N_HTTP_HEADER_NAME"
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
resource "google_secret_manager_secret_version" "am2n_http_header_name_version" {
  secret      = google_secret_manager_secret.am2n_http_header_name.id
  secret_data = var.am2n_http_header_name
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "am2n_http_header_value" {
  secret_id = "AM2N_HTTP_HEADER_VALUE"
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
resource "google_secret_manager_secret_version" "am2n_http_header_value_version" {
  secret      = google_secret_manager_secret.am2n_http_header_value.id
  secret_data = var.am2n_http_header_value
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "am2n_notion_token" {
  secret_id = "AM2N_NOTION_TOKEN"
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
resource "google_secret_manager_secret_version" "am2n_notion_token_version" {
  secret      = google_secret_manager_secret.am2n_notion_token.id
  secret_data = var.am2n_notion_token
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "am2n_incidents_db_id" {
  secret_id = "AM2N_INCIDENTS_DB_ID"
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
resource "google_secret_manager_secret_version" "am2n_incidents_db_id_version" {
  secret      = google_secret_manager_secret.am2n_incidents_db_id.id
  secret_data = var.am2n_incidents_db_id
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "am2n_shifts_db_id" {
  secret_id = "AM2N_SHIFTS_DB_ID"
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
resource "google_secret_manager_secret_version" "am2n_shifts_db_id_version" {
  secret      = google_secret_manager_secret.am2n_shifts_db_id.id
  secret_data = var.am2n_shifts_db_id
  depends_on = [
    google_project_service.secret_manager_api,
    null_resource.wait_for_one_minute,
  ]
}

resource "google_secret_manager_secret" "am2n_shifts_support_enabled" {
  secret_id = "AM2N_SHIFTS_SUPPORT_ENABLED"
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
resource "google_secret_manager_secret_version" "am2n_shifts_support_enabled_version" {
  secret      = google_secret_manager_secret.am2n_shifts_support_enabled.id
  secret_data = var.am2n_shifts_support_enabled
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
