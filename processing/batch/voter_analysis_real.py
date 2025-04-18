import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, when, sum, avg

def main():
    # Initialize Spark session with BigQuery configurations
    project_id = os.environ.get("GCP_PROJECT_ID", "dezoomfinal")
    credentials_path = os.environ.get(
        "GCP_CREDENTIALS_PATH", "/app/dprof-dezoomfinal-b4d188529d18.json"
    )

    # Determine storage source
    storage_type = os.environ.get("STORAGE_PREFERENCE", "GCP")

    # Read the bucket name (defaults to <project>‑bq‑staging per your Terraform)
    temp_bucket = os.environ.get("TEMP_BUCKET_NAME", f"{project_id}-bq-staging")

    spark = (
        SparkSession.builder
            .appName("Voter Analysis")
            .config("spark.sql.caseSensitive", "true")
            # enable service-account auth
            .config(
                "spark.hadoop.google.cloud.auth.service.account.enable", "true"
            )
            .config(
                "spark.hadoop.google.cloud.auth.service.account.json.keyfile",
                credentials_path
            )
            # BigQuery connector settings
            .config("spark.bigquery.projectId", project_id)
            .config("spark.bigquery.parentProject", project_id)
            .config("spark.bigquery.tempGcsBucket", temp_bucket)
            .getOrCreate()
    )


    if storage_type.upper() == "POSTGRES":
        # Read from PostgreSQL
        voters_df = (
            spark.read
                .format("jdbc")
                .option("url", "jdbc:postgresql://postgres:5432/voting_db")
                .option("dbtable", "voters")
                .option("user", "postgres")
                .option("password", "postgres")
                .load()
        )
        votes_df = (
            spark.read
                .format("jdbc")
                .option("url", "jdbc:postgresql://postgres:5432/voting_db")
                .option("dbtable", "votes")
                .option("user", "postgres")
                .option("password", "postgres")
                .load()
        )
    else:
        # Read from BigQuery
        dataset = os.environ.get("GCP_DATASET", "voting_data")

        voters_df = (
            spark.read
                .format("bigquery")
                .option("project", project_id)
                .option("dataset", dataset)
                .option("table", "voters")
                .load()
        )
        votes_df = (
            spark.read
                .format("bigquery")
                .option("project", project_id)
                .option("dataset", dataset)
                .option("table", "votes")
                .load()
        )

    # Register as temp views
    voters_df.createOrReplaceTempView("voters")
    votes_df.createOrReplaceTempView("votes")

    # Demographic analysis
    demographic_analysis = spark.sql("""
        SELECT
            v.age,
            v.gender,
            v.state,
            COUNT(*) AS total_voters,
            COUNT(DISTINCT vt.voter_id) AS voters_who_voted,
            COUNT(vt.vote_id) AS total_votes,
            COUNT(DISTINCT vt.voter_id) / COUNT(*) AS participation_rate
        FROM voters v
        LEFT JOIN votes vt
          ON v.voter_id = vt.voter_id
        GROUP BY v.age, v.gender, v.state
        ORDER BY v.state, v.age, v.gender
    """
    )

    # Write results
    if storage_type.upper() == "POSTGRES":
        (demographic_analysis.write
            .format("jdbc")
            .option("url", "jdbc:postgresql://postgres:5432/voting_db")
            .option("dbtable", "demographic_analysis")
            .option("user", "postgres")
            .option("password", "postgres")
            .mode("overwrite")
            .save()
        )
    else:
        (demographic_analysis.write
            .format("bigquery")
            .option("project", project_id)
            .option("dataset", dataset)
            .option("table", "demographic_analysis")
            .option("writeMethod", "direct") 
            .mode("overwrite")
            .save()
        )

if __name__ == "__main__":
    main()
