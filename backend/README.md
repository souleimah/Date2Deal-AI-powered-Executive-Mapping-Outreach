# Backend Directory

This directory contains the Python backend for Date2Deal.

## Structure

- `orchestrator-all.py` - Main orchestrator for processing entire companies
- `orchestrator-for-one-person.py` - Orchestrator for single profile processing
- `profile_orchestrator_agent.py` - Profile orchestration logic
- `final_report_agent.py` - Report generation agent
- `linkedin/` - LinkedIn scrapers & summarizers
- `youtube/` - YouTube scrapers

## Setup

```bash
cd back
python -m venv venv
source venv/bin/activate   # (Linux/Mac)
# venv\Scripts\activate    # (Windows)
pip install -r requirements.txt
```

## Usage

```bash
# Run the backend with FastAPI
# Note: Python module names should use underscores, not hyphens
# If using orchestrator-all.py, run it directly:
python orchestrator-all.py
# Or use uvicorn with underscore-named modules:
# uvicorn orchestrator_all:app --reload --port 8000
```
