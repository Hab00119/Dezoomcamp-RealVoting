.PHONY: up-postgres up-bigquery down start-infra start-processing-postgres start-processing-bigquery start-apps start-monitoring logs clean setup-gcp start-streaming-postgres start-streaming-bigquery start-streaming start-batch start-transform start-dashboard start-orchestration start-all-postgres start-all-bigquery setup-bigquery-tables

# Start everything with PostgreSQL in the correct order with proper delays
up-postgres:
	@echo "Starting infrastructure (Redpanda, PostgreSQL)..."
	docker-compose --profile postgres up -d redpanda-1 redpanda-console postgres
	@echo "Waiting for infrastructure to initialize (20 seconds)..."
	@sleep 20
	
	@echo "Starting monitoring tools (pgweb)..."
	docker-compose --profile postgres up -d pgweb

	@echo "Starting data generator..."
	docker-compose up -d data-generator
	@echo "Waiting for data generation (5 seconds)..."
	@sleep 5
	
	@echo "Starting vote simulator..."
	docker-compose up -d vote-simulator
	
	@echo "Starting processing services (dlt-pipeline-postgres)..."
	docker-compose --profile postgres up -d dlt-pipeline-postgres
	@echo "Waiting for processing services (10 seconds)..."
	@sleep 10
	
	@echo "All services started successfully!"
	@echo "Run 'make logs' to see the logs"

# Start everything with BigQuery in the correct order with proper delays
up-bigquery:
	@echo "Starting infrastructure (Redpanda)..."
	docker-compose --profile bigquery up -d redpanda-1 redpanda-console
	@echo "Waiting for infrastructure to initialize (20 seconds)..."
	@sleep 20

	@echo "Starting data generator..."
	docker-compose up -d data-generator
	@echo "Waiting for data generation (5 seconds)..."
	@sleep 5
	
	@echo "Starting vote simulator..."
	docker-compose up -d vote-simulator
	
	@echo "Starting processing services (dlt-pipeline-bigquery)..."
	docker-compose --profile bigquery up -d dlt-pipeline-bigquery
	@echo "Waiting for processing services (10 seconds)..."
	@sleep 10
	
	@echo "All services started successfully!"
	@echo "Run 'make logs' to see the logs"

# Start a complete PostgreSQL pipeline including all components
start-all-postgres: up-postgres start-streaming-postgres start-batch start-transform start-dashboard start-orchestration
	@echo "Complete PostgreSQL pipeline started!"

# Start a complete BigQuery pipeline including all components
start-all-bigquery: up-bigquery start-streaming-bigquery start-batch start-transform start-dashboard start-orchestration
	@echo "Complete BigQuery pipeline started!"

# Start only infrastructure components
start-infra:
	@echo "Starting Redpanda cluster..."
	docker-compose up -d redpanda-1 redpanda-console
	@echo "Waiting for infrastructure to initialize (20 seconds)..."
	@sleep 20
	@echo "Infrastructure is ready!"

# Start PostgreSQL if needed
start-postgres:
	@echo "Starting PostgreSQL..."
	docker-compose --profile postgres up -d postgres
	@echo "Waiting for PostgreSQL to initialize (10 seconds)..."
	@sleep 10
	@echo "PostgreSQL is ready!"

# Start only PostgreSQL processing component
start-processing-postgres:
	@echo "Starting DLT pipeline for PostgreSQL..."
	docker-compose --profile postgres up -d dlt-pipeline-postgres
	@echo "Processing service started successfully!"

# Start only BigQuery processing component
start-processing-bigquery:
	@echo "Starting DLT pipeline for BigQuery..."
	docker-compose --profile bigquery up -d dlt-pipeline-bigquery
	@echo "Processing service started successfully!"

# Start only application components
start-apps:
	@echo "Starting data generator..."
	docker-compose up -d data-generator
	@echo "Waiting for data generation (5 seconds)..."
	@sleep 5
	@echo "Starting vote simulator..."
	docker-compose up -d vote-simulator
	@echo "Applications started successfully!"

# Start only monitoring tools
start-monitoring:
	@echo "Starting monitoring tools (pgweb & redpanda-console)..."
	docker-compose --profile postgres up -d pgweb
	docker-compose up -d redpanda-console
	@echo "Monitoring tools started successfully!"

submit-flink-job:
	@echo "Submitting PyFlink streaming job..."
	docker-compose --profile streaming exec jobmanager flink run \
		-py /opt/processing/streaming/vote_processor2.py \
		-d  # Run in detached mode
	@echo "Flink job submitted successfully!"

# Start PyFlink streaming processing for PostgreSQL
start-streaming-postgres:
	@echo "Starting PyFlink streaming processor for PostgreSQL..."
	docker-compose --profile streaming up -d jobmanager taskmanager
	@echo "PyFlink streaming processing started successfully!"

# Start alternative streaming processing for BigQuery
start-streaming-bigquery:
	@echo "Starting BigQuery streaming processor..."
	docker-compose --profile bigquery-streaming up -d bigquery-streaming
	@echo "BigQuery streaming processing started successfully!"

# Smart streaming selection based on STORAGE_PREFERENCE
start-streaming:
	@if [ "$(STORAGE_PREFERENCE)" = "GCP" ]; then \
		$(MAKE) start-streaming-bigquery; \
	else \
		$(MAKE) start-streaming-postgres; \
	fi

# Start PySpark batch processing
start-batch:
	@echo "Starting PySpark batch processor..."
	docker-compose --profile batch up -d spark-processor
	@echo "Batch processing started successfully!"

# Start dbt transformations
start-transform:
	@echo "Starting dbt transformations..."
	docker-compose --profile transform up -d dbt
	@echo "Transformations started successfully!"

# Start Streamlit dashboard
start-dashboard:
	@echo "Starting Streamlit dashboard..."
	docker-compose --profile dashboard up -d streamlit
	@echo "Dashboard started successfully at http://localhost:8501"

# Start Kestra orchestration
start-orchestration:
	@echo "Starting Kestra orchestration..."
	docker-compose --profile orchestration up -d kestra
	@echo "Orchestration started successfully at http://localhost:8080"

# Show logs for all services
logs:
	docker-compose logs -f

# Show logs for specific service group
logs-infra:
	docker-compose logs -f redpanda-1 redpanda-console

logs-postgres:
	docker-compose logs -f postgres dlt-pipeline-postgres

logs-bigquery:
	docker-compose logs -f dlt-pipeline-bigquery

logs-apps:
	docker-compose logs -f data-generator vote-simulator

logs-streaming:
	@if [ "$(STORAGE_PREFERENCE)" = "GCP" ]; then \
		docker-compose logs -f bigquery-streaming; \
	else \
		docker-compose logs -f jobmanager taskmanager; \
	fi

logs-bigquery-streaming:
	docker-compose logs -f bigquery-streaming

logs-flink:
	docker-compose logs -f jobmanager taskmanager

logs-batch:
	docker-compose logs -f spark-processor

logs-transform:
	docker-compose logs -f dbt

logs-dashboard:
	docker-compose logs -f streamlit

logs-orchestration:
	docker-compose logs -f kestra

logs-monitoring:
	docker-compose logs -f pgweb redpanda-console

# Stop and remove all containers
down:
	docker-compose down

# Remove volumes and any created data
clean:
	docker-compose down -v
	@echo "Cleaned up all containers and volumes"

# Default parameters for GCP setup
PROJECT_ID ?= 
CREDENTIALS_FILE ?= 
REGION ?= us-central1
DATASET_ID ?= voting_data
ENVIRONMENT ?= dev


# Setup GCP resources using Terraform and the setup script
setup-gcp:
	@if [ -z "$(PROJECT_ID)" ]; then \
		echo "ERROR: PROJECT_ID is required. Usage: make setup-gcp PROJECT_ID=your-project-id CREDENTIALS_FILE=path/to/credentials.json"; \
		exit 1; \
	fi
	@if [ -z "$(CREDENTIALS_FILE)" ]; then \
		echo "ERROR: CREDENTIALS_FILE is required. Usage: make setup-gcp PROJECT_ID=your-project-id CREDENTIALS_FILE=path/to/credentials.json"; \
		exit 1; \
	fi
	@echo "Setting up GCP resources with Terraform..."
	@chmod +x scripts/setup_gcp.sh
	@./scripts/setup_gcp.sh --project-id $(PROJECT_ID) \
		--credentials $(CREDENTIALS_FILE) \
		--region $(REGION) \
		--dataset-id $(DATASET_ID) \
		--environment $(ENVIRONMENT)

# One-command setup and run with BigQuery
bigquery-full-setup: setup-gcp up-bigquery
	@echo "BigQuery setup complete and services running"