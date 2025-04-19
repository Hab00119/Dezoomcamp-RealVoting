import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from google.cloud import bigquery
from google.oauth2 import service_account
from datetime import datetime

# Set Streamlit page config
st.set_page_config(
    page_title="Real-Time Voting Dashboard",
    page_icon="🗳️",
    layout="wide"
)

# Load BigQuery credentials manually
project_id = os.environ.get("GCP_PROJECT_ID", "dezoomfinal")
dataset = os.environ.get("GCP_DATASET", "voting_data")
credentials_path = os.environ.get("GCP_CREDENTIALS_PATH", "/app/dprof-dezoomfinal-b4d188529d18.json")

credentials = service_account.Credentials.from_service_account_file(credentials_path)
client = bigquery.Client(credentials=credentials, project=project_id)

# Data loading function
def get_data():
    def load_table(table):
        return client.query(f"SELECT * FROM `{project_id}.{dataset}.{table}`").to_dataframe()

    demographic = load_table("demographic_analysis")
    candidate_totals = load_table("candidate_totals")
    regional_turnout = load_table("regional_turnout")
    hourly_trends = load_table("hourly_trends")

    # Load candidate images from votes table
    candidate_images_query = f"""
        SELECT DISTINCT candidate, candidate_image
        FROM `{project_id}.{dataset}.votes`
        WHERE candidate IS NOT NULL AND candidate_image IS NOT NULL
    """
    candidate_images = client.query(candidate_images_query).to_dataframe()

    return demographic, candidate_totals, regional_turnout, hourly_trends, candidate_images

# Fetch data
demographic, candidate_totals, regional_turnout, hourly_trends, candidate_images = get_data()

# Dashboard title
st.title("🗳️ Real-Time Voting Analytics Dashboard")

# Metrics section
st.header("Election Metrics")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Votes", f"{candidate_totals['total_votes'].sum():,}")

with col2:
    st.metric("Candidates", candidate_totals['candidate'].nunique())

with col3:
    st.metric("Regions Reporting", regional_turnout['region'].nunique())

# Candidate Images Section
st.subheader("Meet the Candidates")
cols = st.columns(len(candidate_images))
for i, row in candidate_images.iterrows():
    with cols[i % len(cols)]:
        st.image(row["candidate_image"], width=100)
        st.caption(row["candidate"])

# Candidate standings
st.subheader("Candidate Vote Totals")
fig1 = px.bar(
    candidate_totals,
    x="candidate",
    y="total_votes",
    text="vote_percentage",
    labels={"total_votes": "Total Votes", "candidate": "Candidate"},
    color="candidate"
)
fig1.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
st.plotly_chart(fig1, use_container_width=True)

# Regional turnout analysis
st.subheader("Regional Voter Turnout")
fig2 = px.bar(
    regional_turnout.sort_values("turnout_percentage", ascending=False),
    x="region",
    y="turnout_percentage",
    color="turnout_percentage",
    labels={"turnout_percentage": "Turnout %", "region": "Region"},
    color_continuous_scale="Plasma"
)
fig2.update_layout(coloraxis_showscale=False)
st.plotly_chart(fig2, use_container_width=True)

# Hourly trends
st.subheader("Votes by Hour")
fig3 = px.line(
    hourly_trends,
    x="hour",
    y="votes",
    color="candidate",
    labels={"hour": "Hour", "votes": "Number of Votes"},
    title="Voting Trends Over Time"
)
st.plotly_chart(fig3, use_container_width=True)

# Demographic analysis
st.subheader("Demographic Participation")
col1, col2 = st.columns(2)

with col1:
    by_age = demographic.groupby("age")["participation_rate"].mean().reset_index()
    fig4 = px.line(by_age, x="age", y="participation_rate", title="Participation Rate by Age")
    st.plotly_chart(fig4, use_container_width=True)

with col2:
    by_gender = demographic.groupby("gender")["participation_rate"].mean().reset_index()
    fig5 = px.bar(by_gender, x="gender", y="participation_rate", title="Participation Rate by Gender")
    st.plotly_chart(fig5, use_container_width=True)

# Refresh button
if st.button("🔄 Refresh Data"):
    st.experimental_rerun()

# Footer with timestamp
st.markdown(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
