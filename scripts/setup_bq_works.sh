#!/bin/bash
# scripts/setup_bigquery_tables.sh

PROJECT_ID=$1
DATASET_ID=$2

# Create vote_counts table if it doesn't exist
bq query --project_id=$PROJECT_ID --use_legacy_sql=false "
CREATE TABLE IF NOT EXISTS \`$PROJECT_ID.$DATASET_ID.vote_counts\` (
  window_start INT64,
  window_end INT64,
  candidate STRING,
  vote_count INT64
);"

echo "BigQuery tables created successfully."