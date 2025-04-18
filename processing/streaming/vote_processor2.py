# processing/streaming/vote_processor.py
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment, EnvironmentSettings
import os

def create_kafka_source(table_env):
    # Get Kafka bootstrap servers from environment or use default
    kafka_servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'redpanda-1:29092')
    
    table_env.execute_sql(f"""
        CREATE TABLE vote_source (
            vote_id STRING,
            voter_id STRING,
            candidate STRING,
            `timestamp` TIMESTAMP(3),
            voted_at TIMESTAMP(3),
            precinct STRING,
            WATERMARK FOR voted_at AS voted_at - INTERVAL '5' SECOND
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'votes',
            'properties.bootstrap.servers' = '{kafka_servers}',
            'properties.group.id' = 'vote-processor',
            'scan.startup.mode' = 'earliest-offset',
            'format' = 'json'
        )
    """)

def create_sink(table_env, env):
    # Get Kafka bootstrap servers from environment or use default
    kafka_servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'redpanda-1:29092')
    
    # Check storage preference to determine sink type
    storage_preference = os.environ.get('STORAGE_PREFERENCE', 'GCP')
    
    if storage_preference == 'GCP':
        # BigQuery sink for GCP storage preference
        project_id = os.environ.get('GCP_PROJECT_ID')
        dataset = os.environ.get('GCP_DATASET', 'voting_data')
        
        if not project_id:
            raise ValueError("GCP_PROJECT_ID environment variable must be set when using GCP storage")
        
        # Using the improved Google BigQuery connector syntax
        table_env.execute_sql(f"""
            CREATE TABLE vote_counts (
                candidate STRING,
                precinct STRING,
                vote_count BIGINT,
                window_start TIMESTAMP(3),
                window_end TIMESTAMP(3),
                PRIMARY KEY (candidate, precinct, window_start, window_end) NOT ENFORCED
            ) WITH (
                'connector' = 'bigquery',
                'project' = '{project_id}',
                'dataset' = '{dataset}',
                'table' = 'vote_counts',
                'delivery.guarantee' = 'at-least-once',
                'enable.table.creation' = 'true',
                'sink.parallelism' = '32'
            )
        """)
    else:
        # Kafka sink for other storage preferences
        table_env.execute_sql(f"""
            CREATE TABLE vote_counts (
                candidate STRING,
                precinct STRING,
                vote_count BIGINT,
                window_start TIMESTAMP(3),
                window_end TIMESTAMP(3),
                PRIMARY KEY (candidate, precinct, window_start, window_end) NOT ENFORCED
            ) WITH (
                'connector' = 'upsert-kafka',
                'topic' = 'vote-counts',
                'properties.bootstrap.servers' = '{kafka_servers}',
                'key.format' = 'json',
                'value.format' = 'json'
            )
        """)

def main():
    # Set up the streaming environment
    env = StreamExecutionEnvironment.get_execution_environment()
    
    # Enable checkpointing with a longer timeout as recommended for BigQuery
    env.enable_checkpointing(60 * 1000)  # 60 seconds checkpoint interval
    env.get_checkpoint_config().set_checkpoint_timeout(300 * 1000)  # 5 minutes timeout
    
    # Set parallelism based on BigQuery recommendations (max 512 for US/EU, 128 for others)
    region = os.environ.get('GCP_REGION', 'US')
    max_parallelism = 128
    if region.upper() in ['US', 'EU']:
        max_parallelism = 512
    env.set_parallelism(min(32, max_parallelism))  # Use 32 as default, capped by region limit
    
    settings = EnvironmentSettings.new_instance().in_streaming_mode().build()
    table_env = StreamTableEnvironment.create(env, environment_settings=settings)
    
    # Set up source and sink
    create_kafka_source(table_env)
    create_sink(table_env, env)
    
    # Process votes - count by candidate and precinct in 5-minute tumbling windows
    result = table_env.execute_sql("""
        INSERT INTO vote_counts
        SELECT 
            candidate,
            precinct,
            COUNT(*) AS vote_count,
            TUMBLE_START(voted_at, INTERVAL '5' MINUTE) AS window_start,
            TUMBLE_END(voted_at, INTERVAL '5' MINUTE) AS window_end
        FROM vote_source
        GROUP BY 
            candidate,
            precinct,
            TUMBLE(voted_at, INTERVAL '5' MINUTE)
    """)
    
    # For Dataproc, wait for completion
    if os.environ.get('DATAPROC_CLUSTER', None):
        result.wait()
    
    # Execute the job
    env.execute("Vote Stream Processor")

if __name__ == "__main__":
    main()