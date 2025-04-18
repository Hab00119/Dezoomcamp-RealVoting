# analytics/dashboard/app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import os
import sqlalchemy
from google.cloud import bigquery

# Configure page
st.set_page_config(
    page_title="Real-Time Voting Dashboard",
    page_icon="🗳️",
    layout="wide"
)

# Connection setup based on storage type
storage_type = os.environ.get("STORAGE_PREFERENCE", "POSTGRES")

def get_data():
    if storage_type == "POSTGRES":
        # PostgreSQL connection
        engine = sqlalchemy.create_engine(
            "postgresql://postgres:postgres@postgres:5432/voting_db"
        )
        
        # Get vote statistics
        vote_stats = pd.read_sql(
            "SELECT * FROM vote_statistics", 
            con=engine
        )
        
        # Get real-time vote counts
        real_time_votes = pd.read_sql(
            """
            SELECT 
                candidate, 
                COUNT(*) as votes, 
                DATE_TRUNC('minute', voted_at) as minute
            FROM votes
            WHERE voted_at > NOW() - INTERVAL '1 hour'
            GROUP BY candidate, DATE_TRUNC('minute', voted_at)
            ORDER BY minute
            """, 
            con=engine
        )
        
    else:
        # BigQuery connection
        client = bigquery.Client()
        project_id = os.environ.get("GCP_PROJECT_ID")
        dataset = os.environ.get("GCP_DATASET", "voting_data")
        
        # Get vote statistics
        vote_stats_query = f"""
            SELECT * FROM `{project_id}.{dataset}.vote_statistics`
        """
        vote_stats = client.query(vote_stats_query).to_dataframe()
        
        # Get real-time vote counts
        real_time_query = f"""
            SELECT 
                candidate, 
                COUNT(*) as votes, 
                TIMESTAMP_TRUNC(voted_at, MINUTE) as minute
            FROM `{project_id}.{dataset}.votes`
            WHERE voted_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
            GROUP BY candidate, TIMESTAMP_TRUNC(voted_at, MINUTE)
            ORDER BY minute
        """
        real_time_votes = client.query(real_time_query).to_dataframe()
    
    return vote_stats, real_time_votes

# Get data
vote_stats, real_time_votes = get_data()

# Dashboard title
st.title("🗳️ Real-Time Voting Dashboard")

# Overall metrics
st.header("Voting Overview")
col1, col2, col3 = st.columns(3)

with col1:
    total_votes = vote_stats["vote_count"].sum()
    st.metric("Total Votes Cast", f"{total_votes:,}")

with col2:
    unique_voters = len(vote_stats["voter_id"].unique())
    st.metric("Unique Voters", f"{unique_voters:,}")

with col3:
    precincts = len(vote_stats["precinct"].unique())
    st.metric("Precincts Reporting", precincts)

# Real-time vote tracking
st.header("Real-time Vote Tracking")
fig = px.line(
    real_time_votes.pivot(index="minute", columns="candidate", values="votes"),
    labels={"minute": "Time", "value": "Votes", "variable": "Candidate"}
)
st.plotly_chart(fig, use_container_width=True)

# Demographic breakdowns
st.header("Vote Distribution by Demographics")

# By age group
age_votes = vote_stats.groupby("age_group").agg({"vote_count": "sum"}).reset_index()
age_fig = px.pie(age_votes, values="vote_count", names="age_group", title="Votes by Age Group")
st.plotly_chart(age_fig)

# By gender
gender_votes = vote_stats.groupby("gender").agg({"vote_count": "sum"}).reset_index()
gender_fig = px.bar(gender_votes, x="gender", y="vote_count", title="Votes by Gender")
st.plotly_chart(gender_fig)

# By region/state
region_votes = vote_stats.groupby(["region", "candidate"]).agg({"vote_count": "sum"}).reset_index()
region_fig = px.bar(
    region_votes, 
    x="region", 
    y="vote_count", 
    color="candidate", 
    title="Votes by Region and Candidate",
    barmode="group"
)
st.plotly_chart(region_fig, use_container_width=True)