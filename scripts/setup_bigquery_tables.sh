#!/bin/bash
# scripts/setup_bigquery_tables.sh

set -e  # Exit on error

PROJECT_ID=$1
DATASET_ID=$2
CREDENTIALS_FILE=$3

if [ -z "$PROJECT_ID" ] || [ -z "$DATASET_ID" ]|| [ -z "$CREDENTIALS_FILE" ]; then
  echo "Error: Missing required parameters"
  echo "Usage: $0 PROJECT_ID DATASET_ID"
  exit 1
fi

echo "======================================"
echo "Setting up BigQuery tables"
echo "Project ID: $PROJECT_ID"
echo "Dataset ID: $DATASET_ID"
echo "Credential File: $CREDENTIALS_FILE"
echo "======================================"

# Set credentials
export GOOGLE_APPLICATION_CREDENTIALS="$CREDENTIALS_FILE"

# Check for credentials
if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
  echo "Warning: GOOGLE_APPLICATION_CREDENTIALS not set"
  echo "Will use default application credentials if available"
fi



# Check if we can access BigQuery
echo "Testing BigQuery access..."
if ! bq ls &>/dev/null; then
  echo "Error: Cannot access BigQuery. Check your credentials and permissions."
  exit 1
fi

# Check if the dataset exists, create if it doesn't
echo "Checking if dataset exists..."
if ! bq ls -d "$PROJECT_ID:$DATASET_ID" &>/dev/null; then
  echo "Creating dataset $DATASET_ID in project $PROJECT_ID..."
  bq mk --dataset "$PROJECT_ID:$DATASET_ID"
else
  echo "Dataset $DATASET_ID already exists."
fi

# Create vote_counts table if it doesn't exist
echo "Creating vote_counts table..."
bq query --project_id=$PROJECT_ID --use_legacy_sql=false "
CREATE TABLE IF NOT EXISTS \`$PROJECT_ID.$DATASET_ID.vote_counts\` (
  window_start INT64,
  window_end INT64,
  window_start_time TIMESTAMP,
  window_end_time TIMESTAMP,
  candidate STRING,
  vote_count INT64
);"

echo "Verifying vote_counts table..."
if bq show "$PROJECT_ID:$DATASET_ID.vote_counts" &>/dev/null; then
  echo "√ vote_counts table exists"
  echo "Table schema:"
  bq show --schema "$PROJECT_ID:$DATASET_ID.vote_counts"
else
  echo "Error: vote_counts table was not created successfully"
  exit 1
fi

echo "======================================"
echo "BigQuery setup completed successfully!"
echo "======================================"