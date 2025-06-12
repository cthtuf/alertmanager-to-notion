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

variable "am2n_notion_token" {
  type = string
}

variable "am2n_incidents_db_id" {
  type = string
}

variable "am2n_shifts_db_id" {
  type = string
}

variable "am2n_shifts_support_enabled" {
  type = string
}

variable "am2n_http_header_name" {
  type = string
}

variable "am2n_http_header_value" {
  type = string
}

variable "events_pubsub_topic" {
  type    = string
  default = "events-topic"
}
