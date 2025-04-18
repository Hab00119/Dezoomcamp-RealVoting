# processing/batch/voter_analysis.py
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, when, sum, avg

def main():
    # Initialize Spark session
    spark = SparkSession.builder \
        .appName("Voter Analysis") \
        .config("spark.sql.caseSensitive", "true") \
        .getOrCreate()
    
    # Read data from PostgreSQL or BigQuery (configurable via environment variables)
    storage_type = os.environ.get("STORAGE_PREFERENCE", "POSTGRES")
    
    if storage_type == "POSTGRES":
        # Read from PostgreSQL
        voters_df = spark.read \
            .format("jdbc") \
            .option("url", "jdbc:postgresql://postgres:5432/voting_db") \
            .option("dbtable", "voters") \
            .option("user", "postgres") \
            .option("password", "postgres") \
            .load()
            
        votes_df = spark.read \
            .format("jdbc") \
            .option("url", "jdbc:postgresql://postgres:5432/voting_db") \
            .option("dbtable", "votes") \
            .option("user", "postgres") \
            .option("password", "postgres") \
            .load()
    else:
        # Read from BigQuery
        project_id = os.environ.get("GCP_PROJECT_ID")
        dataset = os.environ.get("GCP_DATASET", "voting_data")
        
        voters_df = spark.read \
            .format("bigquery") \
            .option("table", f"{project_id}:{dataset}.voters") \
            .load()
            
        votes_df = spark.read \
            .format("bigquery") \
            .option("table", f"{project_id}:{dataset}.votes") \
            .load()
    
    # Register as temp views for SQL operations
    voters_df.createOrReplaceTempView("voters")
    votes_df.createOrReplaceTempView("votes")
    
    # Process data - demographic analysis of voting patterns
    demographic_analysis = spark.sql("""
        SELECT 
            v.age_group,
            v.gender,
            v.region,
            COUNT(*) as total_voters,
            COUNT(DISTINCT vt.voter_id) as voters_who_voted,
            COUNT(vt.vote_id) as total_votes,
            COUNT(DISTINCT vt.voter_id) / COUNT(*) as participation_rate
        FROM 
            voters v
        LEFT JOIN 
            votes vt ON v.voter_id = vt.voter_id
        GROUP BY 
            v.age_group, v.gender, v.region
        ORDER BY 
            v.region, v.age_group, v.gender
    """)
    
    # Write results to storage (same as source for simplicity)
    if storage_type == "POSTGRES":
        demographic_analysis.write \
            .format("jdbc") \
            .option("url", "jdbc:postgresql://postgres:5432/voting_db") \
            .option("dbtable", "demographic_analysis") \
            .option("user", "postgres") \
            .option("password", "postgres") \
            .mode("overwrite") \
            .save()
    else:
        demographic_analysis.write \
            .format("bigquery") \
            .option("table", f"{project_id}:{dataset}.demographic_analysis") \
            .mode("overwrite") \
            .save()

if __name__ == "__main__":
    main()