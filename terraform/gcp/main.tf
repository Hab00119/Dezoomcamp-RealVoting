// terraform/gcp/main.tf
provider "google" {
  project     = var.project_id
  region      = var.region
  credentials = file(var.credentials_file)
}

// Create BigQuery dataset
resource "google_bigquery_dataset" "voting_dataset" {
  dataset_id                  = var.dataset_id
  friendly_name               = "Voting Data"
  description                 = "Dataset for real-time voting data"
  location                    = var.location
  default_table_expiration_ms = null
  delete_contents_on_destroy  = var.delete_contents_on_destroy

  labels = {
    environment = var.environment
  }
}

// Create GCS bucket for BigQuery staging
resource "google_storage_bucket" "bq_staging" {
  name          = var.temp_bucket_name
  location      = var.temp_bucket_location
  force_destroy = true

  uniform_bucket_level_access = true

  labels = {
    environment = var.environment
  }
}

// Attach IAM binding so BigQuery can write to the bucket
resource "google_storage_bucket_iam_member" "bq_writer" {
  bucket = google_storage_bucket.bq_staging.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:finalproj@dezoomfinal.iam.gserviceaccount.com"
}