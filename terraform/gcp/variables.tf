// terraform/gcp/variables.tf
variable "project_id" {
  description = "The GCP project ID to deploy resources"
  type        = string
}

variable "credentials_file" {
  description = "Path to the GCP service account credentials JSON file"
  type        = string
}

variable "region" {
  description = "The GCP region to deploy resources"
  type        = string
  default     = "US"
}

variable "location" {
  description = "The BigQuery dataset location"
  type        = string
  default     = "US"
}

variable "dataset_id" {
  description = "The BigQuery dataset ID"
  type        = string
  default     = "voting_data"
}

variable "environment" {
  description = "Environment label for resources (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "delete_contents_on_destroy" {
  description = "Whether to delete the contents of the dataset when destroying"
  type        = bool
  default     = false
}

// New variable for GCS staging bucket, with a sensible default
variable "temp_bucket_name" {
  description = "Name for the GCS bucket used as temporary staging for BigQuery writes (must be globally unique)"
  type        = string
  default     = "dezoomfinal-bq-staging"
}

// Location for the staging bucket (defaults to the same region)
variable "temp_bucket_location" {
  description = "Location for the GCS staging bucket"
  type        = string
  default     = "US"
}