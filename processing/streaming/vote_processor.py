# processing/streaming/vote_processor.py
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment, EnvironmentSettings
from pyflink.table.descriptors import Schema, Kafka, Json, Rowtime

def create_kafka_source(env, table_env):
    table_env.execute_sql("""
        CREATE TABLE vote_source (
            vote_id STRING,
            voter_id STRING,
            candidate STRING,
            timestamp TIMESTAMP(3),
            voted_at TIMESTAMP(3),
            precinct STRING,
            WATERMARK FOR voted_at AS voted_at - INTERVAL '5' SECOND
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'votes',
            'properties.bootstrap.servers' = 'kafka:9092',
            'properties.group.id' = 'vote-processor',
            'scan.startup.mode' = 'earliest-offset',
            'format' = 'json'
        )
    """)

def create_sink(table_env):
    # Create a sink table for results
    table_env.execute_sql("""
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
            'properties.bootstrap.servers' = 'kafka:9092',
            'key.format' = 'json',
            'value.format' = 'json'
        )
    """)

def main():
    # Set up the streaming environment
    env = StreamExecutionEnvironment.get_execution_environment()
    settings = EnvironmentSettings.new_instance().in_streaming_mode().build()
    table_env = StreamTableEnvironment.create(env, settings)
    
    # Set up source and sink
    create_kafka_source(env, table_env)
    create_sink(table_env)
    
    # Process votes - count by candidate and precinct in 5-minute tumbling windows
    table_env.execute_sql("""
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
    
    # Execute the job
    env.execute("Vote Stream Processor")

if __name__ == "__main__":
    main()