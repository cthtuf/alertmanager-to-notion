# Variables to be configured
variable "project_id" {
  type = string
}

variable "settings_module" {
  type    = string
  default = "app.settings"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "csfu_targets" {
  type    = string
}

variable "csfu_target_timeout" {
  type    = string
  default = "10"
}

variable "csfu_webhook_url" {
  type    = string
}

variable "csfu_webhook_headers" {
  type    = string
}

variable "csfu_webhook_retry_attempts" {
  type    = string
  default = "5"
}

variable "csfu_webhook_retry_wait" {
  type    = string
  default = "5"
}

variable "csfu_webhook_timeout" {
  type    = string
  default = "10"
}

variable "csfu_proxy" {
  type    = string
  default = ""
}

variable "csfu_http_header_name" {
  type    = string
}

variable "csfu_http_header_value" {
  type    = string
}

variable "db_timezone" {
  type    = string
}

variable "csfu_snapshots_keep_last_days" {
  type    = string
  default = "5"
}

variable "events_pubsub_topic" {
  type    = string
  default = "csfu-topic"
}
