import os
import json
import time
import logging
from datetime import datetime
from google.cloud import bigquery
from confluent_kafka import Consumer, Producer, KafkaError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('bigquery-streaming')

# BigQuery setup
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.environ.get("GCP_CREDENTIALS_PATH")
project_id = os.environ.get("GCP_PROJECT_ID", "dezoomfinal")
dataset_id = os.environ.get("GCP_DATASET", "voting_data")

logger.info(f"Starting BigQuery streaming processor. Project: {project_id}, Dataset: {dataset_id}")
logger.info(f"Using credentials from: {os.environ.get('GCP_CREDENTIALS_PATH')}")

# Create BigQuery client
try:
    client = bigquery.Client()
    logger.info("Successfully created BigQuery client")
except Exception as e:
    logger.error(f"Failed to create BigQuery client: {e}")
    raise

# Kafka setup
bootstrap_servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'redpanda-1:29092')
logger.info(f"Connecting to Kafka at: {bootstrap_servers}")

consumer_conf = {
    'bootstrap.servers': bootstrap_servers,
    'group.id': 'bq-vote-processor',
    'auto.offset.reset': 'earliest'
}

producer_conf = {
    'bootstrap.servers': bootstrap_servers
}

try:
    consumer = Consumer(consumer_conf)
    producer = Producer(producer_conf)
    logger.info("Successfully created Kafka consumer and producer")
except Exception as e:
    logger.error(f"Failed to create Kafka clients: {e}")
    raise

# Window size in seconds (5 minutes)
WINDOW_SIZE = 300
current_window = {}
last_window_time = int(time.time() // WINDOW_SIZE) * WINDOW_SIZE

def delivery_report(err, msg):
    if err is not None:
        logger.error(f"Message delivery failed: {err}")
    else:
        logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}]")

def process_message(msg):
    global current_window, last_window_time

    # Parse message
    try:
        raw_value = msg.value()
        logger.debug(f"Processing raw message: {raw_value[:100]}...")

        data = json.loads(raw_value.decode('utf-8'))
        candidate = data.get('candidate')
        raw_ts = data.get('timestamp', time.time())

        # Normalize timestamp to an integer epoch
        try:
            if isinstance(raw_ts, str):
                # Parse ISO‑8601 strings like "2025-04-18T06:29:23.967804"
                dt = datetime.fromisoformat(raw_ts)
                timestamp = int(dt.timestamp())
            else:
                # Already numeric (int, float, etc.)
                timestamp = int(float(raw_ts))
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid timestamp format: {raw_ts} ({e})")
            return

        logger.debug(f"Parsed message: candidate={candidate}, timestamp={timestamp}")

        # Calculate window (using integer division)
        window_time = (timestamp // WINDOW_SIZE) * WINDOW_SIZE

        # If we've moved to a new window, flush the old one
        if window_time > last_window_time:
            logger.info(f"Moving to new window: {window_time} (from {last_window_time})")
            flush_window(last_window_time)
            # The current_window will be cleared in flush_window after successful processing
            last_window_time = window_time

        # Update counts
        window_key = f"{window_time}_{candidate}"
        current_window[window_key] = current_window.get(window_key, 0) + 1
        logger.debug(f"Updated count for {window_key}: {current_window[window_key]}")

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}, message value: {msg.value()}")
    except Exception as e:
        logger.error(f"Error processing message: {e}")

def flush_window(window_time):
    if not current_window:
        logger.info("No data to flush for current window")
        return
    
    # Insert to BigQuery
    rows_to_insert = []
    
    logger.info(f"Flushing window {window_time} with {len(current_window)} entries")
    
    for window_key, count in current_window.items():
        window_ts, candidate = window_key.split("_", 1)
        
        rows_to_insert.append({
            "window_start": int(window_ts),
            "window_end": int(window_ts) + WINDOW_SIZE,
            "window_start_time": datetime.fromtimestamp(int(window_ts)).isoformat(),
            "window_end_time": datetime.fromtimestamp(int(window_ts) + WINDOW_SIZE).isoformat(),
            "candidate": candidate,
            "vote_count": count
        })
    
    # Insert to BigQuery
    table_id = f"{project_id}.{dataset_id}.vote_counts"
    logger.info(f"Inserting {len(rows_to_insert)} rows to BigQuery table {table_id}")
    
    try:
        errors = client.insert_rows_json(table_id, rows_to_insert)
        if errors:
            logger.error(f"Errors inserting to BigQuery: {errors}")
        else:
            logger.info(f"Successfully inserted {len(rows_to_insert)} rows to BigQuery")
            
            # Also produce to Kafka for consistency with PyFlink approach
            for row in rows_to_insert:
                kafka_row = row.copy()
                # Convert datetime strings to timestamps for Kafka
                kafka_row.pop("window_start_time", None)
                kafka_row.pop("window_end_time", None)
                try:
                    producer.produce(
                        'vote-counts', 
                        json.dumps(kafka_row).encode('utf-8'),
                        callback=delivery_report
                    )
                except Exception as e:
                    logger.error(f"Error producing to Kafka: {e}")
            
            producer.flush()
            logger.info("Successfully flushed messages to Kafka")
            
            # IMPORTANT FIX: Clear current_window after successful processing
            current_window.clear()
            logger.info("Cleared window data after successful processing")
        
    except Exception as e:
        logger.error(f"Error during flush operation: {e}")

def ensure_table_exists():
    """Create vote_counts table if it doesn't exist"""
    table_id = f"{project_id}.{dataset_id}.vote_counts"
    schema = [
        bigquery.SchemaField("window_start", "INTEGER"),
        bigquery.SchemaField("window_end", "INTEGER"),
        bigquery.SchemaField("window_start_time", "TIMESTAMP"),
        bigquery.SchemaField("window_end_time", "TIMESTAMP"),
        bigquery.SchemaField("candidate", "STRING"),
        bigquery.SchemaField("vote_count", "INTEGER"),
    ]
    
    try:
        client.get_table(table_id)
        logger.info(f"Table {table_id} already exists")
    except Exception as e:
        logger.info(f"Table {table_id} does not exist, creating: {e}")
        try:
            table = bigquery.Table(table_id, schema=schema)
            table = client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            raise

def list_topics():
    """List available Kafka topics for debugging"""
    try:
        from confluent_kafka.admin import AdminClient
        admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
        topics = admin_client.list_topics().topics
        logger.info(f"Available Kafka topics: {list(topics.keys())}")
        return list(topics.keys())
    except ImportError:
        logger.warning("AdminClient not available, topic listing will not work")
        return []

def main():
    try:
        # Ensure the table exists
        ensure_table_exists()
        
        # Subscribe to votes topic
        consumer.subscribe(['votes'])
        logger.info("Subscribed to 'votes' topic")
        
        logger.info("BigQuery streaming processor started, consuming from 'votes' topic...")
        
        # Process count for logging only
        msg_count = 0
        last_log_time = time.time()
        
        while True:
            msg = consumer.poll(1.0)
            
            if msg is None:
                # No message, check if we need to flush the current window
                current_time = time.time()
                
                # Log stats periodically
                if current_time - last_log_time > 60:
                    logger.info(f"Processed {msg_count} messages in the last minute")
                    last_log_time = current_time
                    msg_count = 0
                
                # Check if we need to flush the window
                if current_time - last_window_time > WINDOW_SIZE and current_window:
                    logger.info("Flushing window due to time elapsed")
                    flush_window(last_window_time)
                    # No need to clear current_window here as it's handled in flush_window
                continue
                
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logger.debug(f"Reached end of partition for {msg.topic()}/{msg.partition()}")
                    continue
                else:
                    logger.error(f"Consumer error: {msg.error()}")
                    break
            
            msg_count += 1
            process_message(msg)
            
    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        # Flush final window before shutting down
        if current_window:
            logger.info("Flushing final window before shutdown")
            flush_window(last_window_time)
        logger.info("Closing consumer")
        consumer.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        # raise