import os
import time
import threading
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, year, month, dayofmonth, date_trunc
from pyspark.sql.types import StringType, IntegerType, StructType, StructField, TimestampType

def main():
    project_id = os.environ.get("GCP_PROJECT_ID", "dezoomfinal")
    credentials_path = os.environ.get("GCP_CREDENTIALS_PATH", "/app/dprof-dezoomfinal-b4d188529d18.json")
    storage_type = os.environ.get("STORAGE_PREFERENCE", "GCP")
    temp_bucket = os.environ.get("TEMP_BUCKET_NAME", f"{project_id}-bq-staging")
    kafka_bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
    num_partitions = int(os.environ.get("SPARK_NUM_PARTITIONS", "10"))
    dataset = os.environ.get("GCP_DATASET", "voting_data")

    spark = (
        SparkSession.builder
        .appName("Real-time Voter Analytics")
        .config("spark.sql.caseSensitive", "true")
        .config("spark.hadoop.google.cloud.auth.service.account.enable", "true")
        .config("spark.hadoop.google.cloud.auth.service.account.json.keyfile", credentials_path)
        .config("spark.bigquery.projectId", project_id)
        .config("spark.bigquery.tempGcsBucket", temp_bucket)
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0")
        .config("spark.streaming.stopGracefullyOnShutdown", "true")
        .config("spark.default.parallelism", str(num_partitions))
        .config("spark.sql.shuffle.partitions", str(num_partitions))
        .config("spark.memory.fraction", "0.8")
        .config("spark.memory.storageFraction", "0.3")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .getOrCreate()
    )

    voter_schema = StructType([
        StructField("voter_id", StringType(), True),
        StructField("name", StringType(), True),
        StructField("age", IntegerType(), True),
        StructField("gender", StringType(), True),
        StructField("state", StringType(), True),
        StructField("county", StringType(), True),
        StructField("registration_date", StringType(), True),
        StructField("precinct", StringType(), True)
    ])

    vote_schema = StructType([
        StructField("vote_id", StringType(), True),
        StructField("voter_id", StringType(), True),
        StructField("candidate", StringType(), True),
        StructField("candidate_image", StringType(), True),
        StructField("timestamp", StringType(), True),
        StructField("polling_station", StringType(), True),
        StructField("voted_at", StringType(), True)
    ])

    spark.createDataFrame([], voter_schema).createOrReplaceTempView("voters")
    spark.createDataFrame([], vote_schema).createOrReplaceTempView("votes")

    voters_stream = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", kafka_bootstrap_servers)
        .option("subscribe", "voters")
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .load()
        .selectExpr("CAST(value AS STRING)")
        .select(from_json(col("value"), voter_schema).alias("data"))
        .select("data.*")
        .repartition(num_partitions, "state")
    )

    votes_stream = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", kafka_bootstrap_servers)
        .option("subscribe", "votes")
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .load()
        .selectExpr("CAST(value AS STRING)")
        .select(from_json(col("value"), vote_schema).alias("data"))
        .select("data.*")
        .withColumn("voted_at", col("voted_at").cast(TimestampType()))
        .repartition(num_partitions, "candidate")
    )

    def update_view(df, view_name, key_col, repartition_col, spark):
        if not df.isEmpty():
            df = df.dropDuplicates([key_col])
            try:
                current = spark.sql(f"SELECT * FROM {view_name}")
                merged = current.join(df, key_col, "left_anti").union(df)
            except Exception:
                merged = df
            merged.repartition(num_partitions, repartition_col).createOrReplaceTempView(view_name)

    def process_votes(df, spark, project_id, dataset, num_partitions):
        if df.isEmpty(): return
        update_view(df, "votes", "vote_id", "candidate", spark)
        run_analytics(spark, project_id, dataset, num_partitions)

    def run_analytics(spark, project_id, dataset, num_partitions):
        spark.sql("""
            SELECT *,
            CASE
                WHEN age < 25 THEN '18-24'
                WHEN age BETWEEN 25 AND 34 THEN '25-34'
                WHEN age BETWEEN 35 AND 44 THEN '35-44'
                WHEN age BETWEEN 45 AND 54 THEN '45-54'
                WHEN age BETWEEN 55 AND 64 THEN '55-64'
                ELSE '65+'
            END AS age_group
            FROM voters
        """).repartition(num_partitions, "state", "age_group").createOrReplaceTempView("voters_enriched")

        demographic = spark.sql("""
            SELECT
                v.age, v.gender, v.state,
                COUNT(*) AS total_voters,
                COUNT(DISTINCT vt.voter_id) AS voters_who_voted,
                COUNT(vt.vote_id) AS total_votes,
                COUNT(DISTINCT vt.voter_id) / COUNT(*) AS participation_rate
            FROM voters v
            LEFT JOIN votes vt ON v.voter_id = vt.voter_id
            GROUP BY v.age, v.gender, v.state
        """)

        candidate_totals = spark.sql("""
            SELECT candidate, COUNT(*) AS total_votes,
            COUNT(*) / (SELECT COUNT(*) FROM votes) * 100 AS vote_percentage
            FROM votes GROUP BY candidate
        """)

        regional_turnout = spark.sql("""
            SELECT v.state AS region,
            COUNT(DISTINCT v.voter_id) AS eligible_voters,
            COUNT(DISTINCT votes.voter_id) AS actual_voters,
            COUNT(DISTINCT votes.voter_id) / COUNT(DISTINCT v.voter_id) * 100 AS turnout_percentage
            FROM voters v
            LEFT JOIN votes ON v.voter_id = votes.voter_id
            GROUP BY v.state
        """)

        hourly_trends = spark.sql("""
            SELECT DATE_TRUNC('HOUR', voted_at) AS hour, candidate, COUNT(*) AS votes
            FROM votes GROUP BY hour, candidate
        """)

        write_analytics(demographic, "demographic_analysis", project_id, dataset, ["state", "gender"])
        write_analytics(candidate_totals, "candidate_totals", project_id, dataset, ["candidate"])
        write_analytics(regional_turnout, "regional_turnout", project_id, dataset, ["region"])
        write_analytics(hourly_trends, "hourly_trends", project_id, dataset, ["hour"], "hour")

        print("[Analytics] Tables written to BigQuery.")

    def write_analytics(df, table, project_id, dataset, cluster_fields=None, time_field=None):
        options = {
            "project": project_id,
            "dataset": dataset,
            "table": table,
            "writeMethod": "direct"
        }
        if cluster_fields:
            options["clustering_fields"] = ",".join(cluster_fields)
        if time_field:
            options["partitionField"] = time_field
            options["partitionType"] = "DAY"

        (df.write
            .format("bigquery")
            .options(**options)
            .mode("append")
            .save()
        )

    def monitor():
        while True:
            try:
                vc = spark.sql("SELECT COUNT(*) FROM voters").collect()[0][0]
                vc2 = spark.sql("SELECT COUNT(*) FROM votes").collect()[0][0]
                print(f"[Monitor] {vc} voters | {vc2} votes")
            except Exception as e:
                print(f"[Monitor Error] {e}")
            time.sleep(60)

    voters_stream.writeStream.foreachBatch(
        lambda df, eid: update_view(df, "voters", "voter_id", "state", spark)
    ).start()

    votes_stream.writeStream.foreachBatch(
        lambda df, eid: process_votes(df, spark, project_id, dataset, num_partitions)
    ).start()

    threading.Thread(target=monitor, daemon=True).start()
    spark.streams.awaitAnyTermination()

if __name__ == "__main__":
    main()
