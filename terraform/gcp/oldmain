# terraform/gcp/main.tf
provider "google" {
  project     = var.project_id
  region      = var.region
  credentials = file(var.credentials_file)
}

# Create BigQuery dataset
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

