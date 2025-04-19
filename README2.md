# Dezoomcamp-RealVoting

#Makefile2 and docker-compose222 work so far
## Install terraform
wget -O - https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform

#use
```bash
make bigquery-full-setup PROJECT_ID=dezoomfinal CREDENTIALS_FILE=/workspaces/Dezoomcamp-RealVoting/dprof-dezoomfinal-b4d188529d18.json
STORAGE_PREFERENCE=GCP GCP_PROJECT_ID=dezoomfinal CREDENTIALS_FILE=/workspaces/Dezoomcamp-RealVoting/dprof-dezoomfinal-b4d188529d18.json make start-streaming
#STORAGE_PREFERENCE=GCP GCP_PROJECT_ID=dezoomfinal CREDENTIALS_FILE=/workspaces/Dezoomcamp-RealVoting/dprof-dezoomfinal-b4d188529d18.json make submit-flink-job
STORAGE_PREFERENCE=GCP GCP_PROJECT_ID=dezoomfinal CREDENTIALS_FILE=/workspaces/Dezoomcamp-RealVoting/dprof-dezoomfinal-b4d188529d18.json make start-batch
STORAGE_PREFERENCE=GCP GCP_PROJECT_ID=dezoomfinal CREDENTIALS_FILE=/workspaces/Dezoomcamp-RealVoting/dprof-dezoomfinal-b4d188529d18.json make start-dashboard
```

docker-compose build spark-processor
docker-compose up spark-processor


# Set up GCP resources only, your project-id can be gotten from your dashboard: mine is dezoomfinal
## creds file: /workspaces/Dezoomcamp-RealVoting/dprof-dezoomfinal-b4d188529d18.json
make setup-gcp PROJECT_ID=your-project-id CREDENTIALS_FILE=./path/to/credentials.json

# Set up GCP and start everything in one command (I have been using this)
make bigquery-full-setup PROJECT_ID=your-project-id CREDENTIALS_FILE=./path/to/credentials.json
make bigquery-full-setup PROJECT_ID=dezoomfinal CREDENTIALS_FILE=/workspaces/Dezoomcamp-RealVoting/dprof-dezoomfinal-b4d188529d18.json

# If you've already set up GCP, just start the services
make up-bigquery


## Streaming job with pyflink
check content
```bash
docker-compose --profile streaming exec jobmanager ls -la /opt/processing/streaming/
```

Run the start-streaming command:
```bash
STORAGE_PREFERENCE=GCP GCP_PROJECT_ID=your-project-id make start-streaming
```

STORAGE_PREFERENCE=GCP GCP_PROJECT_ID=dezoomfinal CREDENTIALS_FILE=/workspaces/Dezoomcamp-RealVoting/dprof-dezoomfinal-b4d188529d18.json make start-streaming

If you want to manually submit the job without modifying the Makefile, you can run:
```bash
STORAGE_PREFERENCE=GCP GCP_PROJECT_ID=dezoomfinal docker-compose --profile streaming exec jobmanager flink run -py /opt/processing/streaming/vote_processor2.py
```

# Real-time Voting Data Engineering Project

This project implements a comprehensive data engineering pipeline for processing and analyzing voting data in real-time. The system captures voter registration data and voting events, processes them through batch and streaming components, and makes the analyzed results available for visualization.

## Architecture

The system consists of these main components:

1. **Data Generation**: Kafka producers creating synthetic voter data and vote events
2. **Ingestion**: DLT pipeline consuming from Kafka and loading to PostgreSQL/BigQuery
3. **Storage**: PostgreSQL and GCP (BigQuery/Cloud Storage)
4. **Processing**: PySpark (batch) and PyFlink (streaming) components
5. **Transformation**: dbt modeling layer
6. **Analytics & Dashboard**: Streamlit visualization

## Prerequisites

- Docker and Docker Compose
- Google Cloud Platform account with BigQuery enabled
- Terraform
- Make

## Setup

1. Create a GCP service account with BigQuery and Storage permissions
2. Download the service account key file as `credentials.json` and place it in the project root
3. Update the `terraform/gcp/terraform.tfvars` file with your GCP project ID
4. Run setup:

```bash
make setup
```

## Project Structure

```
├── Makefile                      # Project management commands
├── README.md                     # This file
├── credentials.json              # GCP credentials (not included in repo)
├── data_generator                # Generates synthetic voting data
│   ├── real_vote_simulator.py    # Voting events generator
│   └── voter_generator.py        # Voter registration data generator
├── docker                        # Docker configuration files
│   ├── Dockerfile.generator      # Data generator container
│   ├── Dockerfile.ingestion      # DLT ingestion container
│   ├── Dockerfile.flink          # Flink processor container
│   └── postgres-init.sh          # PostgreSQL initialization script
├── docker-compose.yml            # Container orchestration
├── ingestion                     # Data ingestion components
│   └── dlt_pipeline              # DLT pipeline configuration
│       └── real_dlt.py           # DLT pipeline implementation
├── processing                    # Data processing components
│   ├── batch                     # PySpark batch processing
│   │   ├── spark_batch_processor.py  # Batch processor for historical data
│   │   └── spark_utils.py        # Utility functions for Spark
│   └── streaming                 # PyFlink streaming processing
│       ├── flink_streaming_processor.py  # Real-time processor
│       └── flink_utils.py        # Utility functions for Flink
├── requirements.txt              # Python dependencies
├── scripts                       # Utility scripts
│   └── setup_gcp.sh              # GCP setup script
└── terraform                     # Infrastructure as code
    └── gcp                       # GCP resource definitions
        ├── main.tf               # Terraform main configuration
        ├── variables.tf          # Terraform variables
        ├── terraform.tfvars      # Variable values (not in repo)
        ├── vote_schema.json      # Vote table schema
        └── voter_schema.json     # Voter table schema
```

## Usage

### Start the System

```bash
make start
```

### Stop the System

```bash
make stop
```

### View Logs

```bash
make logs
```

### Manually Run Processing Components

Run the batch processor:
```bash
make run-spark
```

Run the streaming processor:
```bash
make run-flink
```

### Clean Up

Remove all containers and volumes:
```bash
make clean
```

Remove processed data for re-running:
```bash
make clean-processed-data
```

Destroy GCP resources:
```bash
make tf-destroy
```

## Data Flow

1. Data generator produces synthetic voter and vote data to Kafka topics
2. DLT pipeline consumes from Kafka and loads data to PostgreSQL and BigQuery
3. The processing layer consists of:
   - PySpark batch processing for historical analysis
   - PyFlink streaming processing for real-time analytics
4. Results are stored in:
   - BigQuery tables for batch results
   - Kafka topics and Redis for real-time results

## Processing Layer

### Batch Processing (PySpark)

The batch processing component uses PySpark to analyze historical voting data:

- Voter turnout statistics (overall, by age group, by region)
- Hourly and daily trends analysis
- Regional voting patterns
- Handling of late-arriving data with watermarking

### Streaming Processing (PyFlink)

The streaming component uses PyFlink for real-time analysis:

- Real-time vote counting by candidate
- Fraud detection (duplicate votes)
- Anomaly detection (unusual voting patterns)
- Results pushed to Kafka topics and Redis cache

## Next Steps

✅ Step 1: Data Generation and Ingestion
✅ Step 2: Processing Layer (PySpark batch & PyFlink streaming)
⬜ Step 3: Transformation Layer with dbt
⬜ Step 4: Visualization with Streamlit dashboard


#the real processing/batch/voter_analysis_with_dbt.py combines the work of spark with dbt (quick fix to meet up with deadline), the voter_analysis_real is the actual one which separates dbt work from spark's. analytic/dashboard/app_temp is also temporary which used the voter_analysis_with_dbt (app.py is meant to be the main one)

#terrfaform: oldmain and oldvars (didn't create bigquery bucket) but work while the current main and variables.tf create bigquery bucket