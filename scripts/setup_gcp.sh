#!/bin/bash
# scripts/setup_gcp.sh
set -e

# Default values
PROJECT_ID=""
CREDENTIALS_FILE=""
REGION="us-central1"
DATASET_ID="voting_data"
ENVIRONMENT="dev"

function print_usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -p, --project-id PROJECT_ID       GCP Project ID (required)"
    echo "  -c, --credentials FILE_PATH       Path to GCP credentials JSON file (required)"
    echo "  -r, --region REGION               GCP region (default: us-central1)"
    echo "  -d, --dataset-id DATASET_ID       BigQuery dataset ID (default: voting_data)"
    echo "  -e, --environment ENV             Environment tag (default: dev)"
    echo "  -h, --help                        Show this help message"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -p|--project-id)
            PROJECT_ID="$2"
            shift 2
            ;;
        -c|--credentials)
            CREDENTIALS_FILE="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -d|--dataset-id)
            DATASET_ID="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: GCP Project ID is required"
    print_usage
    exit 1
fi

if [ -z "$CREDENTIALS_FILE" ]; then
    echo "ERROR: Path to GCP credentials file is required"
    print_usage
    exit 1
fi

# Check if credentials file exists
if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo "ERROR: Credentials file does not exist: $CREDENTIALS_FILE"
    exit 1
fi

# Ensure terraform directory exists
TERRAFORM_DIR="terraform/gcp"
if [ ! -d "$TERRAFORM_DIR" ]; then
    echo "ERROR: Terraform directory not found: $TERRAFORM_DIR"
    echo "Please run this script from the project root directory"
    exit 1
fi

echo "Setting up GCP resources with Terraform..."
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Dataset ID: $DATASET_ID"
echo "Environment: $ENVIRONMENT"
echo "Credentials file: $CREDENTIALS_FILE"

# Create terraform.tfvars file
cat > "$TERRAFORM_DIR/terraform.tfvars" << EOF
project_id = "$PROJECT_ID"
credentials_file = "$CREDENTIALS_FILE"
region = "$REGION"
dataset_id = "$DATASET_ID"
environment = "$ENVIRONMENT"
EOF

echo "Created terraform.tfvars file"

# Initialize and apply Terraform configuration
cd "$TERRAFORM_DIR"

echo "Initializing Terraform..."
terraform init

echo "Planning Terraform changes..."
terraform plan -out=tfplan

echo "Applying Terraform configuration..."
terraform apply tfplan

echo "GCP setup completed successfully!"
echo "BigQuery dataset '$DATASET_ID' has been created with voters and votes tables"
echo ""
echo "To use BigQuery with the DLT pipeline, make sure to:"
echo "1. Set STORAGE_PREFERENCE=GCP in your environment variables"
echo "2. Provide the path to your GCP credentials file"
echo "3. Run 'make up-bigquery' to start the application with BigQuery storage"

#./scripts/setup_gcp.sh --project-id your-project-id --credentials path/to/credentials.json