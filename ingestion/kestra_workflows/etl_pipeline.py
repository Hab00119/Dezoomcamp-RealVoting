# ingestion/kestra_workflows/etl_pipeline.yml
id: voting_analytics_pipeline
namespace: voting_system
revision: 1

tasks:
  - id: check_data_sources
    type: io.kestra.plugin.scripts.shell.Commands
    commands:
      - echo "Checking Kafka and data sources..."
      - kafka-topics.sh --bootstrap-server kafka:9092 --list
    
  - id: run_batch_processing
    type: io.kestra.plugin.scripts.shell.Commands
    commands:
      - echo "Running PySpark batch processing..."
      - spark-submit /app/processing/batch/voter_analysis.py
    dependsOn:
      - check_data_sources
      
  - id: run_dbt_transforms
    type: io.kestra.plugin.scripts.shell.Commands
    commands:
      - echo "Running dbt transformations..."
      - cd /app/transformation && dbt run
    dependsOn:
      - run_batch_processing
      
  - id: update_dashboard_data
    type: io.kestra.plugin.scripts.shell.Commands
    commands:
      - echo "Refreshing dashboard data..."
      - curl -X POST http://streamlit:8501/api/reload
    dependsOn:
      - run_dbt_transforms