import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import sqlalchemy
from google.cloud import bigquery
from datetime import datetime, timedelta

# Configure page
st.set_page_config(
    page_title="Real-Time Voting Dashboard",
    page_icon="🗳️",
    layout="wide"
)

# Connection setup based on storage type
storage_type = os.environ.get("STORAGE_PREFERENCE", "GCP")

def get_data():
    if storage_type.upper() == "POSTGRES":
        # PostgreSQL connection
        engine = sqlalchemy.create_engine(
            "postgresql://postgres:postgres@postgres:5432/voting_db"
        )
        
        # Get vote statistics
        vote_stats = pd.read_sql(
            "SELECT * FROM vote_statistics", 
            con=engine
        )
        
        # Get candidate totals
        candidate_totals = pd.read_sql(
            "SELECT * FROM candidate_totals",
            con=engine
        )
        
        # Get regional turnout
        regional_turnout = pd.read_sql(
            "SELECT * FROM regional_turnout",
            con=engine
        )
        
        # Get hourly trends
        hourly_trends = pd.read_sql(
            "SELECT * FROM hourly_trends",
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
        project_id = os.environ.get("GCP_PROJECT_ID", "dezoomfinal")
        dataset = os.environ.get("GCP_DATASET", "voting_data")
        
        # Get vote statistics
        vote_stats_query = f"""
            SELECT * FROM `{project_id}.{dataset}.vote_statistics`
        """
        vote_stats = client.query(vote_stats_query).to_dataframe()
        
        # Get candidate totals
        candidate_totals_query = f"""
            SELECT * FROM `{project_id}.{dataset}.candidate_totals`
        """
        candidate_totals = client.query(candidate_totals_query).to_dataframe()
        
        # Get regional turnout
        regional_turnout_query = f"""
            SELECT * FROM `{project_id}.{dataset}.regional_turnout`
        """
        regional_turnout = client.query(regional_turnout_query).to_dataframe()
        
        # Get hourly trends
        hourly_trends_query = f"""
            SELECT * FROM `{project_id}.{dataset}.hourly_trends`
        """
        hourly_trends = client.query(hourly_trends_query).to_dataframe()
        
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
    
    return vote_stats, candidate_totals, regional_turnout, hourly_trends, real_time_votes

# Get data
vote_stats, candidate_totals, regional_turnout, hourly_trends, real_time_votes = get_data()

# Dashboard title
st.title("🗳️ Real-Time Voting Dashboard")

# Top-level metrics
st.header("Election Overview")
col1, col2, col3 = st.columns(3)

try:
    with col1:
        total_votes = candidate_totals["total_votes"].sum()
        st.metric("Total Votes Cast", f"{int(total_votes):,}")

    with col2:
        unique_voters = len(vote_stats["voter_id"].unique())
        st.metric("Unique Voters", f"{unique_voters:,}")

    with col3:
        reporting_regions = len(regional_turnout)
        st.metric("Regions Reporting", reporting_regions)
except Exception as e:
    st.error(f"Error loading metrics: {e}")
    st.warning("Some data might not be available yet. Please run the analytics pipeline first.")

# Candidate standings
st.header("Current Standings")
try:
    fig_standings = px.bar(
        candidate_totals, 
        x="candidate", 
        y="total_votes", 
        text="vote_percentage",
        labels={"total_votes": "Total Votes", "candidate": "Candidate"},
        color="candidate"
    )
    fig_standings.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    st.plotly_chart(fig_standings, use_container_width=True)
except Exception as e:
    st.error(f"Error displaying candidate standings: {e}")

# Real-time vote tracking
st.header("Real-time Vote Tracking (Last Hour)")
try:
    if not real_time_votes.empty and 'candidate' in real_time_votes.columns and 'minute' in real_time_votes.columns:
        pivot_df = real_time_votes.pivot_table(index="minute", columns="candidate", values="votes", fill_value=0)
        
        # Create cumulative sums for each candidate
        for column in pivot_df.columns:
            pivot_df[column] = pivot_df[column].cumsum()
            
        fig = px.line(
            pivot_df,
            labels={"minute": "Time", "value": "Cumulative Votes", "variable": "Candidate"}
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No real-time voting data available for the last hour.")
except Exception as e:
    st.error(f"Error displaying real-time tracking: {e}")

# Regional analysis
st.header("Regional Analysis")
col1, col2 = st.columns(2)

try:
    with col1:
        st.subheader("Voter Turnout by Region")
        fig_turnout = px.bar(
            regional_turnout.sort_values("turnout_percentage", ascending=False),
            x="region",
            y="turnout_percentage",
            labels={"turnout_percentage": "Turnout %", "region": "Region"},
            color="turnout_percentage",
            color_continuous_scale="Viridis"
        )
        fig_turnout.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_turnout, use_container_width=True)

    with col2:
        st.subheader("Actual vs. Eligible Voters by Region")
        fig_voters = go.Figure()
        fig_voters.add_trace(go.Bar(
            x=regional_turnout["region"],
            y=regional_turnout["eligible_voters"],
            name="Eligible Voters"
        ))
        fig_voters.add_trace(go.Bar(
            x=regional_turnout["region"],
            y=regional_turnout["actual_voters"],
            name="Actual Voters"
        ))
        fig_voters.update_layout(barmode='group')
        st.plotly_chart(fig_voters, use_container_width=True)
except Exception as e:
    st.error(f"Error displaying regional analysis: {e}")

# Demographic breakdowns
st.header("Vote Distribution by Demographics")
try:
    # By age group
    if 'age_group' in vote_stats.columns:
        age_votes = vote_stats.groupby("age_group").size().reset_index(name='count')
        age_fig = px.pie(age_votes, values="count", names="age_group", title="Votes by Age Group")
        st.plotly_chart(age_fig)

    # By gender 
    if 'gender' in vote_stats.columns:
        gender_votes = vote_stats.groupby("gender").size().reset_index(name='count')
        gender_fig = px.bar(gender_votes, x="gender", y="count", title="Votes by Gender")
        st.plotly_chart(gender_fig)

    # By region/state and candidate
    if 'region' in vote_stats.columns and 'candidate' in vote_stats.columns:
        region_votes = vote_stats.groupby(["region", "candidate"]).size().reset_index(name='count')
        region_fig = px.bar(
            region_votes, 
            x="region", 
            y="count", 
            color="candidate", 
            title="Votes by Region and Candidate",
            barmode="group"
        )
        st.plotly_chart(region_fig, use_container_width=True)
except Exception as e:
    st.error(f"Error displaying demographic breakdowns: {e}")

# Hourly voting patterns
st.header("Voting Patterns Over Time")
try:
    if not hourly_trends.empty:
        hourly_fig = px.line(
            hourly_trends,
            x="hour",
            y="votes",
            color="candidate",
            title="Votes by Hour",
            labels={"hour": "Time", "votes": "Number of Votes"}
        )
        st.plotly_chart(hourly_fig, use_container_width=True)
except Exception as e:
    st.error(f"Error displaying hourly trends: {e}")

# Add refresh button
if st.button("Refresh Data"):
    st.experimental_rerun()

# Footer with timestamp
st.markdown(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")