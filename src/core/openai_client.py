from __future__ import annotations

from typing import Any

from openai import OpenAI

from src.core.config import settings


class AdvisoryLLM:
    """Wraps OpenAI calls and falls back to deterministic advice when no key exists."""

    def __init__(self) -> None:
        self.model = settings.openai_model
        self._client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    @property
    def is_live(self) -> bool:
        return self._client is not None

    def farm_advice(self, context: dict[str, Any], user_question: str) -> str:
        if not self._client:
            return self._offline_advice(context, user_question)

        prompt = (
            "You are a senior agronomist for Kenyan smallholder farms. "
            "Give concise and practical recommendations in numbered steps. "
            "Consider cost and water constraints."
        )
        user_payload = (
            f"Farm context: {context}\n"
            f"Question: {user_question}\n"
            "Return: Immediate action, 7-day plan, and risk alerts."
        )
        try:
            response = self._client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_payload},
                ],
                temperature=0.2,
            )
            return response.output_text.strip()
        except Exception as exc:  # pragma: no cover
            return f"Live AI call failed ({exc}). Offline guidance: {self._offline_advice(context, user_question)}"

    def _offline_advice(self, context: dict[str, Any], user_question: str) -> str:
        soil_moisture = context.get("soil_moisture", 50)
        pest_risk = context.get("pest_risk", 0.2)
        rain_mm = context.get("forecast_rain_mm", 0)

        actions = []
        if soil_moisture < 35 and rain_mm < 5:
            actions.append("Start drip irrigation now for 25 to 35 minutes per block.")
        if pest_risk > 0.6:
            actions.append("Deploy integrated pest management: scout leaves and spray bio-pesticide at dusk.")
        if rain_mm > 20:
            actions.append("Delay fertilizer for 24 hours to avoid nutrient runoff.")
        if not actions:
            actions.append("Maintain current schedule and monitor soil moisture every 4 hours.")

        return (
            f"Question: {user_question}\n"
            "1. Immediate action: " + actions[0] + "\n"
            "2. 7-day plan: Track moisture trend, pest incidents, and yield stress index daily.\n"
            "3. Risk alerts: Prioritize water and pest control when risks rise above threshold."
        )
