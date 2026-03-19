from __future__ import annotations

import os
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any

import pandas as pd
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

from src.agents.orchestrator import AgriOrchestrator
from src.core.openai_client import AdvisoryLLM
from src.data.dataset_manager import DATASET_SOURCES, build_real_training_frame, download_all_datasets, load_nasa_daily_weather
from src.data.simulator import FarmConfig, FarmSimulator
from src.data.storage import AppStorage
from src.integrations.mpesa_simulator import MpesaSimulator
from src.models.predictor import CropRiskPredictor


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "agri-orchestrator-secret")

storage = AppStorage()
orchestrator = AgriOrchestrator()
llm = AdvisoryLLM()
predictor = CropRiskPredictor("models/crop_risk_model.json")
mpesa = MpesaSimulator()


def current_user() -> dict[str, Any] | None:
    token = session.get("auth_token")
    if not token:
        return None
    return storage.user_from_token(token)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please login to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def roles_required(*roles: str):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please login to continue.", "warning")
                return redirect(url_for("login"))
            if user.get("role") not in roles:
                flash("You do not have permission to access that page.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def _simulator_from_profile(profile: dict[str, Any] | None = None) -> FarmSimulator:
    if profile is None:
        profile = {
            "county": "Nakuru",
            "crop": "Maize",
            "area_acres": 3.0,
            "budget_kes": 15000,
        }
    config = FarmConfig(
        county=str(profile.get("county", "Nakuru")),
        crop=str(profile.get("crop", "Maize")),
        area_acres=float(profile.get("area_acres", 3.0)),
        budget_kes=int(profile.get("budget_kes", 15000)),
    )
    return FarmSimulator(config)


def _active_profile_for_user(user: dict[str, Any]) -> dict[str, Any] | None:
    profiles = storage.list_farmer_profiles()
    if user["role"] == "farmer":
        own = [p for p in profiles if p.get("owner_user_id") == user["id"]]
        return own[0] if own else None
    return profiles[0] if profiles else None


@app.route("/")
def landing() -> str:
    return render_template(
        "landing.html",
        user=current_user(),
        ai_mode="Live OpenAI" if llm.is_live else "Offline fallback",
        data_mode="Real NASA+WorldBank" if Path("data/raw/kenya_nasa_weather_daily.json").exists() else "Simulation fallback",
    )


@app.route("/login", methods=["GET", "POST"])
def login() -> Any:
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        auth_user = storage.authenticate(username, password)
        if auth_user:
            session["auth_token"] = auth_user.token
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials.", "danger")
    return render_template("login.html", user=current_user())


@app.route("/logout")
def logout() -> Any:
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("landing"))


@app.route("/register", methods=["GET", "POST"])
def register() -> Any:
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "farmer")
        if role not in {"farmer", "officer"}:
            role = "farmer"
        if not username or not password:
            flash("Username and password are required.", "danger")
            return render_template("register.html", user=current_user())
        try:
            storage.create_user(username, password, role)
            flash("Account created. Please login.", "success")
            return redirect(url_for("login"))
        except Exception:
            flash("Username already exists.", "danger")
    return render_template("register.html", user=current_user())


@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard() -> str:
    user = current_user()
    assert user is not None

    ai_mode = "Live OpenAI" if llm.is_live else "Offline fallback"
    data_mode = "Real NASA+WorldBank" if Path("data/raw/kenya_nasa_weather_daily.json").exists() else "Simulation fallback"

    profile = _active_profile_for_user(user)
    simulator = _simulator_from_profile(profile)
    history = simulator.generate_history(168)
    snapshot = simulator.latest_snapshot()
    pending_count = len(storage.list_pending_sync())

    if request.method == "POST":
        action = request.form.get("action")
        if action == "run-cycle":
            trace = orchestrator.run_cycle(snapshot)
            flash(f"Agent cycle completed with priority: {trace.reasoning['priority']}", "success")
        if action == "ask-ai":
            question = request.form.get("question", "")
            answer = llm.farm_advice(snapshot, question or "What should I do next for my farm?")
            session["last_ai_answer"] = answer
            flash("AI recommendation generated.", "success")

    latest = history.iloc[-1]
    snapshot["water_stress"] = max(0.0, (45 - snapshot["soil_moisture"]) / 45)
    risk = predictor.predict_risk(snapshot)
    model_details = predictor.get_model_details()

    chart_data = {
        "labels": history["timestamp"].dt.strftime("%m-%d %H:%M").tail(72).tolist(),
        "soil": history["soil_moisture"].tail(72).round(2).tolist(),
        "pest": history["pest_risk"].tail(72).round(3).tolist(),
        "ndvi": history["ndvi"].tail(72).round(3).tolist(),
    }

    return render_template(
        "dashboard.html",
        user=user,
        profile=profile,
        latest=latest,
        risk=risk,
        chart_data=chart_data,
        last_ai_answer=session.get("last_ai_answer", ""),
        model_details=model_details,
        ai_mode=ai_mode,
        data_mode=data_mode,
        pending_count=pending_count,
    )


@app.route("/profiles", methods=["GET", "POST"])
@login_required
def profiles() -> str:
    user = current_user()
    assert user is not None

    if request.method == "POST":
        profile = {
            "farmer_name": request.form.get("farmer_name", ""),
            "county": request.form.get("county", "Nakuru"),
            "crop": request.form.get("crop", "Maize"),
            "area_acres": float(request.form.get("area_acres", 3.0)),
            "budget_kes": int(request.form.get("budget_kes", 15000)),
            "phone": request.form.get("phone", ""),
        }
        owner_id = user["id"] if user["role"] == "farmer" else None
        profile_id = storage.save_farmer_profile(profile, owner_user_id=owner_id)
        storage.enqueue_sync("upsert_profile", {"profile_id": profile_id, "user_id": user["id"]})
        flash("Farmer profile saved and queued for sync.", "success")

    rows = storage.list_farmer_profiles()
    if user["role"] == "farmer":
        rows = [p for p in rows if p.get("owner_user_id") == user["id"]]

    return render_template("profiles.html", user=user, profiles=rows)


@app.route("/payments", methods=["GET", "POST"])
@login_required
def payments() -> str:
    user = current_user()
    assert user is not None

    if request.method == "POST":
        phone = request.form.get("phone", "254712345678")
        amount = int(request.form.get("amount", 1000))
        purpose = request.form.get("purpose", "Farm Ops")
        offline = request.form.get("offline_mode") == "on"

        if offline:
            queue_id = storage.enqueue_sync("mpesa_payment", {"phone": phone, "amount": amount, "purpose": purpose})
            flash(f"Offline mode enabled. Payment queued with ID {queue_id}.", "warning")
        else:
            tx = mpesa.simulate_stk_push(phone, amount, purpose)
            flash(f"{tx.status}: {tx.message}", "success" if tx.status == "SUCCESS" else "warning")

    summary = mpesa.summary()
    txs = mpesa.list_transactions()[::-1]
    return render_template("payments.html", user=user, summary=summary, transactions=txs)


@app.route("/data-hub", methods=["GET", "POST"])
@login_required
@roles_required("admin", "officer")
def data_hub() -> str:
    user = current_user()
    assert user is not None

    report: list[dict[str, str]] | None = None
    if request.method == "POST":
        report = download_all_datasets("data/raw")
        flash("Dataset refresh complete.", "success")

    weather_preview = None
    training_preview = None
    try:
        weather_preview = load_nasa_daily_weather("data/raw").tail(8).to_dict(orient="records")
        training_preview = build_real_training_frame("data/raw").tail(8).to_dict(orient="records")
    except Exception as exc:
        flash(f"Data preview unavailable: {exc}", "danger")

    return render_template(
        "data_hub.html",
        user=user,
        datasets=DATASET_SOURCES,
        report=report,
        weather_preview=weather_preview,
        training_preview=training_preview,
    )


@app.route("/sync", methods=["GET", "POST"])
@login_required
@roles_required("admin", "officer")
def sync_queue() -> str:
    user = current_user()
    assert user is not None

    if request.method == "POST":
        result = storage.flush_sync_queue()
        flash(f"Processed {result['processed']} queued operations.", "success")

    pending = storage.list_pending_sync()
    return render_template("sync.html", user=user, pending=pending)


@app.route("/api/predict-risk")
@login_required
def predict_risk_api() -> Any:
    user = current_user()
    assert user is not None
    profile = _active_profile_for_user(user)
    simulator = _simulator_from_profile(profile)
    snapshot = simulator.latest_snapshot()
    snapshot["water_stress"] = max(0.0, (45 - snapshot["soil_moisture"]) / 45)
    prediction = predictor.predict_risk(snapshot)
    return jsonify({"timestamp": datetime.now().isoformat(), "prediction": prediction, "snapshot": snapshot})


@app.route("/model-details")
@login_required
@roles_required("admin", "officer")
def model_details() -> str:
    user = current_user()
    assert user is not None
    details = predictor.get_model_details()
    return render_template("model_details.html", user=user, details=details)


@app.route("/api/model-details")
@login_required
@roles_required("admin", "officer")
def model_details_api() -> Any:
    return jsonify(predictor.get_model_details())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
