from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class AgentTrace:
    timestamp: str
    perception: dict[str, Any]
    reasoning: dict[str, Any]
    forecast: dict[str, Any]
    action: dict[str, Any]
    optimizer: dict[str, Any]


class AgriOrchestrator:
    """Hierarchical multi-agent orchestration for autonomous farm decisions."""

    def __init__(self) -> None:
        self.history: list[AgentTrace] = []

    def run_cycle(self, snapshot: dict[str, float]) -> AgentTrace:
        perception = self._perception_agent(snapshot)
        forecast = self._forecast_agent(snapshot)
        reasoning = self._reasoning_agent(perception, forecast)
        action = self._action_agent(reasoning, forecast)
        optimizer = self._optimizer_agent(snapshot, action)

        trace = AgentTrace(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            perception=perception,
            reasoning=reasoning,
            forecast=forecast,
            action=action,
            optimizer=optimizer,
        )
        self.history.append(trace)
        return trace

    def _perception_agent(self, s: dict[str, float]) -> dict[str, Any]:
        water_need = "high" if s["soil_moisture"] < 35 else "normal"
        pest_state = "watch" if s["pest_risk"] > 0.5 else "stable"
        crop_health = "healthy" if s["ndvi"] > 0.58 else "stressed"
        return {
            "water_need": water_need,
            "pest_state": pest_state,
            "crop_health": crop_health,
            "soil_moisture": round(s["soil_moisture"], 2),
            "ndvi": round(s["ndvi"], 2),
        }

    def _forecast_agent(self, s: dict[str, float]) -> dict[str, Any]:
        irrigation_risk = "high" if s["forecast_rain_mm"] < 8 and s["soil_moisture"] < 40 else "moderate"
        disease_risk = "high" if s["humidity_pct"] > 72 and s["temperature_c"] > 27 else "low"
        return {
            "rain_next_24h_mm": round(s["forecast_rain_mm"], 2),
            "irrigation_risk": irrigation_risk,
            "disease_risk": disease_risk,
            "market_price_signal": "positive",
        }

    def _reasoning_agent(self, p: dict[str, Any], f: dict[str, Any]) -> dict[str, Any]:
        steps: list[str] = []
        priority = "monitor"

        if p["water_need"] == "high" and f["rain_next_24h_mm"] < 8:
            priority = "irrigation"
            steps.append("Soil moisture is below healthy threshold and rain forecast is low.")
            steps.append("Prioritize low-pressure drip irrigation to preserve water budget.")

        if p["pest_state"] == "watch" or f["disease_risk"] == "high":
            if priority == "monitor":
                priority = "crop-protection"
            steps.append("Elevated pest/disease signal detected from humidity and field indicators.")
            steps.append("Run scouting workflow and apply preventive treatment in the evening.")

        if not steps:
            steps.append("Conditions are stable. Continue current farm schedule with close monitoring.")

        return {
            "priority": priority,
            "decision_steps": steps,
            "confidence": 0.82 if len(steps) > 1 else 0.73,
        }

    def _action_agent(self, r: dict[str, Any], f: dict[str, Any]) -> dict[str, Any]:
        actions = []
        if r["priority"] == "irrigation":
            actions.append("Activate irrigation block A and B for 30 minutes.")
        if r["priority"] in {"crop-protection", "irrigation"}:
            actions.append("Send SMS alert to farm manager with action checklist.")
        if f["disease_risk"] == "high":
            actions.append("Flag disease scan route for next drone pass.")
        if not actions:
            actions.append("No immediate intervention required.")

        return {
            "planned_actions": actions,
            "estimated_cost_kes": 1400 if "Activate irrigation block A and B for 30 minutes." in actions else 300,
            "expected_impact": "Yield preservation and reduced stress over next 48h.",
        }

    def _optimizer_agent(self, s: dict[str, float], a: dict[str, Any]) -> dict[str, Any]:
        stress = max(0.0, (45 - s["soil_moisture"]) / 45)
        policy_score = round(1 - (stress * 0.6 + s["pest_risk"] * 0.4), 3)
        return {
            "policy_score": policy_score,
            "suggested_update": "Increase scouting frequency to every 6 hours." if s["pest_risk"] > 0.55 else "Keep current policy and retrain model weekly.",
            "execution_cost_kes": a["estimated_cost_kes"],
        }
