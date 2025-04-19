# 🌟 Real-Time Voting Analytics Pipeline

A fully containerized, real-time data pipeline built with Kafka (Redpanda), PySpark, DLT, and BigQuery, visualized through a dynamic Streamlit dashboard. The system simulates real-world voting events, ingests data in real-time, processes it for analytics, and displays it live.

---

## 🌐 Overview

This project demonstrates a simplified real-time data pipeline capable of:

- Generating synthetic voters and casting simulated votes
- Streaming ingestion into BigQuery or PostgreSQL using [DLT](https://github.com/iterative/dlt)
- Performing real-time analytics using PySpark
- Writing results into BigQuery with partitioning and clustering
- Displaying live metrics, turnout rates, and demographic participation on a dashboard

---

## 🔹 Architecture Breakdown

### 1. **Data Generation Layer**

| Component | Description |
|----------|-------------|
| `data_generator/voter_generator.py` | Generates synthetic voters and sends them to Kafka |
| `data_generator/real_vote_simulator.py` | Simulates votes from voters and sends them to Kafka |

### 2. **Ingestion Layer**

| Component | Description |
|----------|-------------|
| `ingestion/dlt_pipeline/real_dlt.py` | Consumes from Kafka and ingests into PostgreSQL or BigQuery using DLT |

> Produces raw `voters` and `votes` tables in your destination.

### 3. **Processing Layer**

| Component | Description |
|----------|-------------|
| `processing/batch/vote_analysis_final.py` | PySpark script that reads the votes and voter data from Kafka in real-time, joins, aggregates, and writes analytics tables to BigQuery |

Analytics tables written:
- `candidate_totals`
- `regional_turnout`
- `hourly_trends`
- `demographic_analysis`

### 4. **Analytics Layer**

| Component | Description |
|----------|-------------|
| `analytics/dashboard/app.py` | Streamlit dashboard pulling from BigQuery, displaying vote stats, regional turnout, demographics, and candidate profiles (including images) |

---

<!--## 🗂️ Workflow Diagram

![Workflow Diagram](https://path.to/your-uploaded-image/workflow-diagram.png)

---
--->

## 🚀 Setup Instructions

### 1. Install Prerequisites

```bash
sudo apt update
sudo apt install make docker.io docker-compose -y
```

### 2. Install Terraform
```bash
wget -O - https://apt.releases.hashicorp.com/gpg | \
    sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
    https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
    sudo tee /etc/apt/sources.list.d/hashicorp.list

sudo apt update && sudo apt install terraform
```
### 3. Create GCP Service Account

1. Go to the [IAM Console](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Create a new service account (e.g., `real-voting-pipeline`)
3. Grant these roles:
   - BigQuery Data Editor
   - Storage Admin
   - BigQuery Job User
4. Create and download a JSON key file
5. Place it at the root of your project (e.g., `./dprof-dezoomfinal-b4d188529d18.json`)

---

## ⚙️ Running the Pipeline

### First Time: Terraform + Data + Ingestion

```bash
make bigquery-full-setup \
    PROJECT_ID=dezoomfinal \
    CREDENTIALS_FILE=./dprof-dezoomfinal-b4d188529d18.json
```
### Start Analytics (PySpark)
```bash
STORAGE_PREFERENCE=GCP \
GCP_PROJECT_ID=dezoomfinal \
CREDENTIALS_FILE=./dprof-dezoomfinal-b4d188529d18.json \
make start-batch
```

### Start Dashboard
```bash
STORAGE_PREFERENCE=GCP \
GCP_PROJECT_ID=dezoomfinal \
CREDENTIALS_FILE=./dprof-dezoomfinal-b4d188529d18.json \
make start-dashboard
```

## 📂️ Project Structure


## 🚧 Components In Use

| Layer         | Tools                           |
|---------------|---------------------------------|
| Messaging     | Kafka (via Redpanda)            |
| Ingestion     | DLT (Kafka ➔ BigQuery/Postgres) |
| Processing    | PySpark (batch analytics)       |
| Visualization | Streamlit + Plotly              |
| Infra         | Docker + Terraform              |


## 📊 Analytics Tables

| Table Name           | Description                                 |
|----------------------|---------------------------------------------|
| demographic_analysis | Age, gender, and state participation stats  |
| candidate_totals     | Vote count and percentage by candidate      |
| regional_turnout     | Eligible vs. actual voters per region/state |
| hourly_trends        | Voting activity aggregated by hour          |

## 🌟 Highlights

- Full local simulation of a national voting system  
- Real-time ingestion & analytics with visual feedback  
- Efficient BigQuery writing with partitioning/clustering  
- Custom dashboard with image-enhanced candidate display  


## 🏛️ Next Steps

| Task                            | Status         |
|---------------------------------|----------------|
| Data generation + DLT ingestion | ✅ Done        |
| PySpark batch analytics         | ✅ Done        |
| Streamlit dashboard             | ✅ Done        |
| Candidate image integration     | ✅ Done        |
| dbt modeling (marts/staging)    | ⏳ In progress |
| PostgreSQL alternative setup    | ⏳ Pending     |
| PyFlink streaming pipeline      | ⏳ Pending     |
| Kestra orchestration workflows  | ⏳ Pending     |


## 📊 Sample Commands (Cheat Sheet)

```bash
# First-time setup: infra + generators + ingestion
make bigquery-full-setup PROJECT_ID=dezoomfinal CREDENTIALS_FILE=./creds.json

# Start analytics
make start-batch

# Start Streamlit dashboard
make start-dashboard

# Manually trigger Spark processor
docker-compose build spark-processor
docker-compose up spark-processor
```

close all docker services using:

```bash
docker rm -f $(docker ps -aq)
docker rmi $(docker images -aq)
```

## 🚫 Legal

This project is for educational purposes only. Do not upload real personal data into this pipeline.

## 🚀 Credits

Built with ❤️ for the DataTalksClub Dezoomcamp Final Project by @hab00119.
