# scripts/debug_kafka_bigquery.py
import os
import json
import time
from google.cloud import bigquery
from confluent_kafka import Consumer, Producer, KafkaError
from confluent_kafka.admin import AdminClient

# Configure credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.environ.get("GCP_CREDENTIALS_PATH")
project_id = os.environ.get("GCP_PROJECT_ID", "dezoomfinal")
dataset_id = os.environ.get("GCP_DATASET", "voting_data")
bootstrap_servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')

print(f"=== Debug Tool for Kafka & BigQuery ===")
print(f"BigQuery Project: {project_id}")
print(f"BigQuery Dataset: {dataset_id}")
print(f"Kafka Servers: {bootstrap_servers}")
print(f"Credentials: {os.environ.get('GCP_CREDENTIALS_PATH')}")
print("="*40)

# Check BigQuery
print("\n[1] Testing BigQuery Connection...")
try:
    client = bigquery.Client()
    print("  ✓ BigQuery client created successfully")
    
    # Check dataset
    try:
        dataset_ref = client.dataset(dataset_id)
        dataset = client.get_dataset(dataset_ref)
        print(f"  ✓ Dataset {dataset_id} exists")
    except Exception as e:
        print(f"  ✗ Dataset error: {e}")
    
    # Check table
    try:
        table_ref = dataset_ref.table("vote_counts")
        table = client.get_table(table_ref)
        print(f"  ✓ Table vote_counts exists with schema:")
        for field in table.schema:
            print(f"    - {field.name} ({field.field_type})")
        
        # Count rows
        query = f"SELECT COUNT(*) as count FROM `{project_id}.{dataset_id}.vote_counts`"
        query_job = client.query(query)
        results = query_job.result()
        for row in results:
            print(f"  ✓ Table has {row.count} rows")
    except Exception as e:
        print(f"  ✗ Table error: {e}")
        
except Exception as e:
    print(f"  ✗ BigQuery connection failed: {e}")

# Check Kafka
print("\n[2] Testing Kafka Connection...")
try:
    admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
    topics = admin_client.list_topics(timeout=5)
    
    print("  ✓ Kafka connection successful")
    print("  Available topics:")
    for topic, details in topics.topics.items():
        print(f"    - {topic}")
    
    # Check if our topics exist
    expected_topics = ['votes', 'vote-counts']
    for topic in expected_topics:
        if topic in topics.topics:
            print(f"  ✓ Topic '{topic}' exists")
        else:
            print(f"  ✗ Topic '{topic}' does not exist")
            
    # Check messages in votes topic
    print("\n[3] Checking for messages in 'votes' topic...")
    consumer_conf = {
        'bootstrap.servers': bootstrap_servers,
        'group.id': 'debug-consumer',
        'auto.offset.reset': 'earliest',
        'session.timeout.ms': 6000
    }
    
    consumer = Consumer(consumer_conf)
    consumer.subscribe(['votes'])
    
    msg_count = 0
    start_time = time.time()
    print("  Consuming messages for 5 seconds...")
    
    while time.time() - start_time < 5:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"  ✗ Consumer error: {msg.error()}")
            break
        msg_count += 1
        if msg_count <= 3:  # Show just a few examples
            try:
                value = json.loads(msg.value().decode('utf-8'))
                print(f"  Message {msg_count}: {json.dumps(value)[:100]}...")
            except:
                print(f"  Message {msg_count}: [Failed to decode]")
    
    print(f"  Found {msg_count} messages in the 'votes' topic in 5 seconds")
    consumer.close()
    
except Exception as e:
    print(f"  ✗ Kafka connection failed: {e}")

print("\n=== Debug Complete ===")