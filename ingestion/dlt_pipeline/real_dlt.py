# ingestion/dlt_pipeline/real_dlt.py
import os
import json
import time
import signal
import logging
import traceback
import threading
from kafka import KafkaConsumer
from dlt.destinations import postgres, bigquery
#from dlt.destinations.bigquery import bigquery

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('dlt-pipeline')

# Global flag for graceful shutdown
running = True

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    global running
    logger.info("Shutdown signal received, stopping pipeline...")
    running = False

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

class DestinationConfig:
    """Class to handle destination configuration and setup"""
    
    @staticmethod
    def get_destination_config():
        """Get destination configuration based on storage preference"""
        storage_preference = os.environ.get('STORAGE_PREFERENCE', 'postgres').upper()
        
        if storage_preference == 'GCP':
            return BigQueryConfig.get_config()
        else:
            return PostgresConfig.get_config()

class PostgresConfig:
    """PostgreSQL specific configuration"""
    
    @staticmethod
    def get_config():
        """Get PostgreSQL connection configuration"""
        pg_host = os.environ.get('POSTGRES_HOST', 'localhost')
        pg_port = os.environ.get('POSTGRES_PORT', '5432')
        pg_db = os.environ.get('POSTGRES_DB', 'voting_db')
        pg_user = os.environ.get('POSTGRES_USER', 'postgres')
        pg_password = os.environ.get('POSTGRES_PASSWORD', 'postgres')
        pg_schema = os.environ.get('POSTGRES_SCHEMA', 'public')
        
        connection_string = f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
        logger.info(f"Using PostgreSQL destination with host {pg_host}")
        
        return 'postgres', connection_string, pg_schema

class BigQueryConfig:
    """BigQuery specific configuration"""
    
    @staticmethod
    def get_config():
        """Get BigQuery connection configuration"""
        # Check if GCP credentials file path is provided
        gcp_project_id = os.environ.get('GCP_PROJECT_ID')
        gcp_dataset = os.environ.get('GCP_DATASET', 'voting_data')
        gcp_creds_path = os.environ.get('GCP_CREDENTIALS_PATH')
        
        if not gcp_project_id:
            logger.warning("GCP_PROJECT_ID not set, attempting to infer from credentials")
        
        if gcp_creds_path and os.path.exists(gcp_creds_path):
            # Load GCP credentials from file
            with open(gcp_creds_path, 'r') as f:
                gcp_creds = json.load(f)
                
            if not gcp_project_id and 'project_id' in gcp_creds:
                gcp_project_id = gcp_creds['project_id']
                logger.info(f"Using project ID from credentials: {gcp_project_id}")
                
            logger.info(f"Using BigQuery destination with credentials from {gcp_creds_path}")
            return 'bigquery', {
                'credentials': gcp_creds,
                'project_id': gcp_project_id,
                'dataset': gcp_dataset
            }, gcp_dataset
        else:
            # If credentials file is not provided, try to use application default credentials
            logger.info("GCP credentials file not found, using application default credentials")
            return 'bigquery', {
                'project_id': gcp_project_id,
                'dataset': gcp_dataset
            }, gcp_dataset

class DLTPipeline:
    """DLT pipeline manager for loading data from Kafka to destination"""
    
    def __init__(self, pipeline_name, table_name):
        """Initialize DLT pipeline with name and target table"""
        self.pipeline_name = pipeline_name
        self.table_name = table_name
        
        # Get destination configuration
        self.destination_type, self.destination_config, self.dataset_name = DestinationConfig.get_destination_config()
        logger.info(f"Setting up pipeline '{pipeline_name}' for table '{table_name}' with destination: {self.destination_type}")
        
        # Create DLT pipeline
        import dlt
        
        # Set the appropriate destination
        if self.destination_type == 'bigquery':
            dest = bigquery(**self.destination_config)
        else:
            dest = postgres(self.destination_config)
        
        # Create pipeline with incremental loading
        self.pipeline = dlt.pipeline(
            pipeline_name=pipeline_name,
            destination=dest,
            dataset_name=self.dataset_name,
            #full_refresh=True  # This will recreate the schema when needed
        )
        
        # Kafka configuration
        self.bootstrap_servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:29092')
        self.topic_type = "VOTES" if table_name.lower() == "votes" else "VOTERS"
        self.topic = os.environ.get(f'KAFKA_{self.topic_type}_TOPIC', self.topic_type.lower())
        
        # Batch configuration
        self.batch_size = int(os.environ.get('BATCH_SIZE', '1000'))
        self.max_batch_interval_seconds = int(os.environ.get('MAX_BATCH_INTERVAL_SECONDS', '500')) #flush at even if records not up to batch size
        
    def create_consumer(self, group_id_prefix):
        """Create Kafka consumer for the pipeline's topic"""
        # Use a consistent group_id for offset tracking between restarts
        # But allow multiple instances with different IDs if needed
        instance_id = os.environ.get('INSTANCE_ID', '')
        group_id = f"{group_id_prefix}-{instance_id}" if instance_id else group_id_prefix
        
        logger.info(f"Creating Kafka consumer for topic '{self.topic}' with group '{group_id}'")
        
        # Create consumer without timeout to enable continuous processing
        consumer = KafkaConsumer(
            self.topic,
            bootstrap_servers=[self.bootstrap_servers],
            auto_offset_reset='earliest',  # Start from earliest unprocessed message
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            group_id=group_id,
            enable_auto_commit=True,  # Automatically commit offsets
            auto_commit_interval_ms=15000,  # Commit every 15 seconds
        )
        
        return consumer
    
    def process_batch(self, batch):
        """Process a batch of records with DLT"""
        if not batch:
            return
        
        logger.info(f"Processing batch of {len(batch)} records for table '{self.table_name}'")
        
        try:
            # Run the pipeline with the batch data
            info = self.pipeline.run(
                batch,
                table_name=self.table_name,
                write_disposition='append'
            )
            
            logger.info(f"Successfully loaded batch. Load info: {info}")
            
            # Check for errors
            if hasattr(info, 'load_packages') and info.load_packages:
                if hasattr(info.load_packages, 'failed_rows_count') and info.load_packages.failed_rows_count > 0:
                    logger.warning(f"Failed to load {info.load_packages.failed_rows_count} rows")
        except Exception as e:
            logger.error(f"Error processing batch: {str(e)}")
            logger.error(traceback.format_exc())
    
    def run_continuous_ingest(self, group_id_prefix):
        """Continuously ingest data from Kafka to the destination"""
        global running
        
        logger.info(f"Starting continuous ingestion for {self.table_name}")
        consumer = self.create_consumer(group_id_prefix)
        
        logger.info(f"Batch configuration: size={self.batch_size}, interval={self.max_batch_interval_seconds}s")
        
        batch_buffer = []
        last_flush_time = time.time()
        
        # Main ingestion loop
        try:
            while running:
                # Poll for messages with a timeout to avoid blocking indefinitely
                messages = consumer.poll(timeout_ms=1000, max_records=self.batch_size)
                
                current_time = time.time()
                time_since_last_flush = current_time - last_flush_time
                
                if messages:
                    # Process received messages
                    for tp, msgs in messages.items():
                        for msg in msgs:
                            # Add message to the batch buffer
                            batch_buffer.append(msg.value)
                            
                            # If batch is full, process it
                            if len(batch_buffer) >= self.batch_size:
                                self.process_batch(batch_buffer)
                                batch_buffer = []
                                last_flush_time = time.time()
                
                # Also flush if max time has passed since last flush
                if batch_buffer and time_since_last_flush >= self.max_batch_interval_seconds:
                    logger.info(f"Time-based flush after {time_since_last_flush:.1f}s with {len(batch_buffer)} records")
                    self.process_batch(batch_buffer)
                    batch_buffer = []
                    last_flush_time = time.time()
                    
                # Small sleep to prevent CPU spinning when idle
                if not messages:
                    time.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"Error in continuous ingestion: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            # Process any remaining records in the buffer
            if batch_buffer:
                logger.info(f"Processing {len(batch_buffer)} remaining records before shutdown")
                self.process_batch(batch_buffer)
                
            # Clean up resources
            logger.info("Closing Kafka consumer")
            consumer.close()

def test_components():
    """Test basic components before starting continuous ingestion"""
    # Test Kafka connection
    bootstrap_servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:29092')
    logger.info(f"Testing Kafka connection to {bootstrap_servers}")
    
    try:
        consumer = KafkaConsumer(
            bootstrap_servers=[bootstrap_servers],
            group_id='test-group',
            consumer_timeout_ms=5000
        )
        
        topics = consumer.topics()
        logger.info(f"Available Kafka topics: {topics}")
        consumer.close()
        
        # Test database connection based on preference
        destination_type, _, _ = DestinationConfig.get_destination_config()
        if destination_type == 'postgres':
            import psycopg2
            pg_host = os.environ.get('POSTGRES_HOST', 'localhost')
            pg_port = os.environ.get('POSTGRES_PORT', '5432')
            pg_db = os.environ.get('POSTGRES_DB', 'voting_db')
            pg_user = os.environ.get('POSTGRES_USER', 'postgres')
            pg_password = os.environ.get('POSTGRES_PASSWORD', 'postgres')
            
            conn = psycopg2.connect(
                host=pg_host,
                port=pg_port,
                dbname=pg_db,
                user=pg_user,
                password=pg_password
            )
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            logger.info("PostgreSQL connection test successful")
        elif destination_type == 'bigquery':
            # Try to test BigQuery connection
            from google.cloud import bigquery as bq
            gcp_creds_path = os.environ.get('GCP_CREDENTIALS_PATH')
            
            if gcp_creds_path:
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = gcp_creds_path
                
            client = bq.Client()
            # Just try to list datasets to verify connection
            list(client.list_datasets(max_results=1))
            logger.info("BigQuery connection test successful")
        
        # Test DLT installation
        import dlt
        logger.info(f"DLT version: {dlt.__version__}")
        
        return True
    except Exception as e:
        logger.error(f"Component tests failed: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main entry point for the continuous ingestion service"""
    logger.info("Starting real-time DLT ingestion service")
    
    # Test components first
    if not test_components():
        logger.error("Component tests failed. Exiting.")
        return
    
    # Get configuration for which data to ingest
    ingest_voters = os.environ.get('INGEST_VOTERS', 'true').lower() == 'true'
    ingest_votes = os.environ.get('INGEST_VOTES', 'true').lower() == 'true'
    
    threads = []
    
    # Start ingestion processes
    if ingest_voters:
        voters_pipeline = DLTPipeline('voters_pipeline', 'voters')
        voters_thread = threading.Thread(
            target=voters_pipeline.run_continuous_ingest,
            args=('dlt-voters-group',),
            daemon=True
        )
        voters_thread.start()
        threads.append(voters_thread)
        logger.info("Started voters ingestion thread")
    
    if ingest_votes:
        votes_pipeline = DLTPipeline('votes_pipeline', 'votes')
        votes_thread = threading.Thread(
            target=votes_pipeline.run_continuous_ingest,
            args=('dlt-votes-group',),
            daemon=True
        )
        votes_thread.start()
        threads.append(votes_thread)
        logger.info("Started votes ingestion thread")
    
    # Keep main thread alive to allow the ingestion to continue
    logger.info("Ingestion service is running. Press Ctrl+C to stop.")
    try:
        while running and any(t.is_alive() for t in threads):
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, stopping service...")
    
    # Wait for a clean shutdown
    logger.info("Waiting for ingestion to complete (max 30 seconds)...")
    shutdown_start = time.time()
    while time.time() - shutdown_start < 30 and any(t.is_alive() for t in threads):
        time.sleep(1)
    
    logger.info("DLT ingestion service stopped")

if __name__ == "__main__":
    main()