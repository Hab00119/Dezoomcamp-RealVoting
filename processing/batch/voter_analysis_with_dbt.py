import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, when, sum, avg, date_trunc, expr, desc, lit
from pyspark.sql.types import StringType, IntegerType

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

    # --- ANALYTICS QUERIES ---
    
    # 1. Demographic analysis (original)
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
    """)

    # 2. Create age_group categories (replacing dbt transformation)
    voters_enriched = spark.sql("""
        SELECT
            *,
            CASE
                WHEN age < 25 THEN '18-24'
                WHEN age BETWEEN 25 AND 34 THEN '25-34'
                WHEN age BETWEEN 35 AND 44 THEN '35-44'
                WHEN age BETWEEN 45 AND 54 THEN '45-54'
                WHEN age BETWEEN 55 AND 64 THEN '55-64'
                ELSE '65+'
            END AS age_group
        FROM voters
    """)
    voters_enriched.createOrReplaceTempView("voters_enriched")

    # 3. Vote statistics by demographics (replacing dbt marts)
    vote_statistics = spark.sql("""
        SELECT
            v.voter_id,
            v.age_group,
            v.gender,
            v.state AS region,
            v.precinct,
            votes.candidate,
            COUNT(votes.vote_id) AS vote_count,
            votes.voted_at
        FROM voters_enriched v
        JOIN votes ON v.voter_id = votes.voter_id
        GROUP BY 
            v.voter_id, 
            v.age_group, 
            v.gender, 
            v.state, 
            v.precinct, 
            votes.candidate, 
            votes.voted_at
    """)

    # 4. Candidate vote totals
    candidate_totals = spark.sql("""
        SELECT
            candidate,
            COUNT(*) AS total_votes,
            COUNT(*) / (SELECT COUNT(*) FROM votes) * 100 AS vote_percentage
        FROM votes
        GROUP BY candidate
        ORDER BY total_votes DESC
    """)

    # 5. Regional turnout analysis
    regional_turnout = spark.sql("""
        SELECT
            v.state AS region,
            COUNT(DISTINCT v.voter_id) AS eligible_voters,
            COUNT(DISTINCT votes.voter_id) AS actual_voters,
            COUNT(DISTINCT votes.voter_id) / COUNT(DISTINCT v.voter_id) * 100 AS turnout_percentage
        FROM voters v
        LEFT JOIN votes ON v.voter_id = votes.voter_id
        GROUP BY v.state
        ORDER BY turnout_percentage DESC
    """)

    # 6. Hourly vote trends
    hourly_trends = spark.sql("""
        SELECT
            DATE_TRUNC('HOUR', voted_at) AS hour,
            candidate,
            COUNT(*) AS votes
        FROM votes
        GROUP BY DATE_TRUNC('HOUR', voted_at), candidate
        ORDER BY hour
    """)

    # Write results to storage
    dataset = os.environ.get("GCP_DATASET", "voting_data")
    
    # Helper function to write dataframes
    def write_dataframe(df, table_name):
        if storage_type.upper() == "POSTGRES":
            (df.write
                .format("jdbc")
                .option("url", "jdbc:postgresql://postgres:5432/voting_db")
                .option("dbtable", table_name)
                .option("user", "postgres")
                .option("password", "postgres")
                .mode("overwrite")
                .save()
            )
        else:
            (df.write
                .format("bigquery")
                .option("project", project_id)
                .option("dataset", dataset)
                .option("table", table_name)
                .option("writeMethod", "direct") 
                .mode("overwrite")
                .save()
            )

    # Write all analytics tables
    write_dataframe(demographic_analysis, "demographic_analysis")
    write_dataframe(voters_enriched, "voters_enriched")
    write_dataframe(vote_statistics, "vote_statistics")
    write_dataframe(candidate_totals, "candidate_totals")
    write_dataframe(regional_turnout, "regional_turnout")
    write_dataframe(hourly_trends, "hourly_trends")

    # Print completion message
    print("Analytics processing completed successfully!")
    
if __name__ == "__main__":
    main()