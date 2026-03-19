# AgriOrchestrator Kenya

AgriOrchestrator Kenya is a premium, hackathon-ready Flask web platform for Kenyan smallholder farms. It combines a hierarchical multi-agent engine, OpenAI-powered advisory intelligence, autonomous simulation, and a model lab where you can hot-swap a trained model with a visible model card.

## Why this can win

- Solves a real Kenya problem: low-resilience farming decisions under weather and pest pressure.
- AI-rich design: multi-agent planning + LLM copilot + predictive model layer.
- Demo-friendly: premium landing page, authentication, role-aware user pages, autonomous operations, and decision trace explanations.

## Core Features

- Multi-agent autonomous loop (Perception, Forecast, Reasoning, Action, Optimizer).
- Farm telemetry simulation for Kenya county profiles.
- AI Farm Copilot using your OpenAI API key (live or offline fallback).
- Model Lab with model-card powered details and easy Colab replacement flow.
- Beautiful premium dashboard with charts and operational alerts.
- M-Pesa transaction simulation tab with persistent ledger and payment outcomes.
- Real public dataset pipeline for Kenya weather and agricultural indicators.
- Role-based login with farmer profile management backed by SQLite.
- Offline-first queue for poor-connectivity operations with manual sync flush.
- FastAPI mobile backend for authentication, farmer profiles, and sync operations.
- Universal Flask frontend with responsive landing, auth, dashboard, profiles, payments, data hub, and sync pages.
- Real model lineage visibility (artifact path, hash, model version, trained years, feature list).

## Recent Updates (March 2026)

- Added role-aware access control across all major pages (farmer, officer, admin).
- Added offline-first sync queue workflows for profile and payment operations.
- Added FastAPI mobile backend for auth, farmer management, and sync endpoints.
- Expanded real-data utilities with dataset verification support via `scripts/verify_data.py`.
- Improved model observability with model-card metadata, artifact hash, and lineage surfacing.

## Quick Start

Recommended Python version: 3.11+.

1. Create virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The current dependency set is compatible with modern Python releases including 3.14.

2. Configure environment:

```bash
cp .env.example .env
# set OPENAI_API_KEY in .env (placeholder key is intentionally blank)
```

3. Run the web app:

```bash
flask --app app run --debug
```

4. Download real training datasets into local workspace:

```bash
python scripts/download_datasets.py
```

5. Verify dataset integrity and training frame build:

```bash
python scripts/verify_data.py
```

6. Run mobile API backend:

```bash
python scripts/run_api.py
```

7. Open model details in web app (admin/officer):

```bash
http://127.0.0.1:5000/model-details
```

API base URL: `http://localhost:8000`

Key API endpoints:
- `POST /auth/login`
- `GET /farmers`
- `POST /farmers`
- `PUT /farmers/{profile_id}`
- `POST /sync/enqueue`
- `GET /sync/pending`
- `POST /sync/flush`
- `GET /api/model-details`

Default role accounts:
- `admin / admin123`
- `officer / officer123`
- `farmer / farmer123`

Role-based interface access:
- `farmer`: Dashboard, Profiles (own), Payments
- `officer`: Dashboard, Profiles, Payments, Data Hub, Sync, Model Details
- `admin`: Full access (all officer pages plus system oversight)

## Model Lab and Model Card

How the app fetches model details:
- The predictor first looks for a trained bundle at `models/crop_risk_model.joblib` (or `crop_risk_bundle.joblib`).
- If the bundle contains a `model_card` dict, that metadata is surfaced automatically.
- If not, the app reads `models/model_card.json` (provided) or `crop_risk_model.metadata.json` as a sidecar.
- If no bundle exists, it falls back to the JSON placeholder model but still shows model card metadata when present.

Model details shown to admins/officers:
- artifact path, size, last modified time, SHA256 hash
- model name, version, target, trained years, training rows
- features list and metrics (AUC/F1/Brier) pulled from the model card
- data sources used to train the artifact

Colab replacement flow:
- Open `notebooks/agri_training_research.ipynb`, run training, export `crop_risk_bundle.joblib` plus `model_card.json`.
- Copy both into `models/`.
- Restart the Flask app; the UI will reflect the new version and metrics instantly.

## Notebook

Training and research notebook is included at `notebooks/agri_training_research.ipynb`. You can open directly in Google Colab and run end-to-end.

The notebook now includes:
- real dataset download cells,
- advanced feature engineering from weather and policy indicators,
- temporal validation for realistic forecasting evaluation,
- richer diagnostics and feature-importance outputs,
- artifact export (`crop_risk_bundle.joblib` + `model_card.json`) for direct use in the app.

Dataset source references are listed in `data/raw/SOURCES.md`.

## Project Structure

- `app.py`: Flask application entrypoint and route controller.
- `src/agents/orchestrator.py`: hierarchical autonomous agent loop.
- `src/core/openai_client.py`: OpenAI integration and fallback logic.
- `src/data/simulator.py`: real-weather-first telemetry generator with fallback simulation.
- `src/models/predictor.py`: placeholder/joblib model loading and scoring.
- `templates/model_details.html`: model lineage and metadata view.
- `src/integrations/mpesa_simulator.py`: simulated M-Pesa STK push and ledger.
- `src/data/dataset_manager.py`: curated Kenya dataset source manager.
- `src/data/storage.py`: SQLite auth, farmer profile store, and sync queue.
- `src/api/main.py`: FastAPI backend for mobile clients.
- `scripts/download_datasets.py`: one-command dataset fetch script.
- `templates/`: Jinja templates for landing, auth, and role-aware dashboards (fully redesigned, no AI-generated UI).
- `static/`: CSS and JS assets for premium frontend experience.
- `scripts/run_api.py`: starts FastAPI server.
- `notebooks/agri_training_research.ipynb`: training/research pipeline.

## Pitch Line

An autonomous AI co-pilot that helps Kenyan farmers make better daily decisions on irrigation, pest prevention, and yield risk before losses happen.
