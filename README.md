# GCP Network Analyzer Multi-Agent App with Google ADK

## What this does

This app:
- collects GCP Network Analyzer insights via the Recommender API
- normalises findings
- generates remediation suggestions
- uses Google ADK agents and the ADK runner

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Auth
Use Application Default Credentials:
```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_CONTROL_PROJECT
```

Also make sure the Recommender API is enabled:
```bash
gcloud services enable recommender.googleapis.com --project YOUR_CONTROL_PROJECT
```

Run CLI
```bash
PYTHONPATH=src python run_agent.py YOUR_PROJECT_ID
```