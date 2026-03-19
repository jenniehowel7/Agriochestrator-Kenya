from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path

import numpy as np
import pandas as pd


COUNTY_PROFILES = {
    "Nakuru": {"temp_base": 23.0, "rain_base": 3.0, "humidity": 58.0},
    "Uasin Gishu": {"temp_base": 21.0, "rain_base": 4.0, "humidity": 62.0},
    "Kisumu": {"temp_base": 28.0, "rain_base": 5.0, "humidity": 71.0},
    "Meru": {"temp_base": 22.0, "rain_base": 4.0, "humidity": 66.0},
    "Machakos": {"temp_base": 27.0, "rain_base": 2.0, "humidity": 49.0},
}


@dataclass
class FarmConfig:
    county: str
    crop: str
    area_acres: float
    budget_kes: int


class FarmSimulator:
    """Generates realistic hourly farm telemetry for demo and autonomous loop."""

    def __init__(self, config: FarmConfig, seed: int = 7) -> None:
        self.config = config
        self.rng = np.random.default_rng(seed)

    def generate_history(self, hours: int = 168) -> pd.DataFrame:
        real_data = self._real_weather_history(hours)
        if real_data is not None:
            return real_data

        profile = COUNTY_PROFILES.get(self.config.county, COUNTY_PROFILES["Nakuru"])
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        timestamps = [now - timedelta(hours=h) for h in range(hours)][::-1]

        temp = self._seasonal_wave(hours, profile["temp_base"], 5.0, noise=1.2)
        humidity = self._seasonal_wave(hours, profile["humidity"], 10.0, noise=4.0)
        rain = np.maximum(0, self.rng.normal(profile["rain_base"], 3.0, size=hours))
        soil_moisture = np.clip(40 + np.cumsum((rain * 0.2) - 0.6) + self.rng.normal(0, 2.0, hours), 15, 90)
        ndvi = np.clip(0.4 + (soil_moisture / 100) * 0.5 + self.rng.normal(0, 0.04, hours), 0.1, 0.95)
        pest_risk = np.clip(((humidity - 50) / 100) + self.rng.normal(0.05, 0.08, hours), 0.01, 0.98)

        df = pd.DataFrame(
            {
                "timestamp": timestamps,
                "temperature_c": temp,
                "humidity_pct": humidity,
                "rainfall_mm": rain,
                "soil_moisture": soil_moisture,
                "ndvi": ndvi,
                "pest_risk": pest_risk,
            }
        )
        df["water_stress"] = np.clip((45 - df["soil_moisture"]) / 45, 0, 1)
        return df

    def latest_snapshot(self) -> dict[str, float]:
        frame = self.generate_history(hours=48)
        row = frame.iloc[-1]
        return {
            "temperature_c": float(row["temperature_c"]),
            "humidity_pct": float(row["humidity_pct"]),
            "rainfall_mm": float(row["rainfall_mm"]),
            "soil_moisture": float(row["soil_moisture"]),
            "ndvi": float(row["ndvi"]),
            "pest_risk": float(row["pest_risk"]),
            "forecast_rain_mm": float(frame["rainfall_mm"].tail(12).mean() * 1.8),
        }

    def _seasonal_wave(self, hours: int, base: float, amplitude: float, noise: float) -> np.ndarray:
        x = np.linspace(0, 6 * np.pi, hours)
        values = base + amplitude * np.sin(x) + self.rng.normal(0, noise, size=hours)
        return np.round(values, 2)

    def _real_weather_history(self, hours: int) -> pd.DataFrame | None:
        weather_path = Path("data/raw/kenya_nasa_weather_daily.json")
        if not weather_path.exists():
            return None

        payload = json.loads(weather_path.read_text(encoding="utf-8"))
        params = payload.get("properties", {}).get("parameter", {})
        t2m = params.get("T2M")
        rain = params.get("PRECTOTCORR")
        humidity = params.get("RH2M")
        if not t2m or not rain or not humidity:
            return None

        daily = pd.DataFrame(
            {
                "date": pd.to_datetime(list(t2m.keys()), format="%Y%m%d"),
                "temperature_c": list(t2m.values()),
                "rainfall_mm": list(rain.values()),
                "humidity_pct": list(humidity.values()),
            }
        ).sort_values("date")

        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        start = now - timedelta(hours=hours - 1)
        hourly_index = pd.date_range(start=start, end=now, freq="H")

        expanded = daily.set_index("date").reindex(pd.date_range(daily["date"].min(), daily["date"].max(), freq="D"))
        expanded.index.name = "date"
        expanded = expanded.interpolate().ffill().bfill()
        expanded = expanded.reindex(hourly_index.normalize(), method="nearest")
        expanded = expanded.reset_index(drop=True)

        df = pd.DataFrame(
            {
                "timestamp": hourly_index,
                "temperature_c": expanded["temperature_c"].astype(float).values,
                "humidity_pct": expanded["humidity_pct"].astype(float).values,
                "rainfall_mm": expanded["rainfall_mm"].to_numpy(dtype=float) / 24.0,
            }
        )

        # County-aware offsets so the UI feels specific to each user profile.
        profile = COUNTY_PROFILES.get(self.config.county, COUNTY_PROFILES["Nakuru"])
        temp_offset = profile["temp_base"] - 23.0
        humidity_offset = profile["humidity"] - 58.0
        df["temperature_c"] = df["temperature_c"] + temp_offset * 0.35
        df["humidity_pct"] = df["humidity_pct"] + humidity_offset * 0.4

        # Deterministic agronomic estimations derived from real weather signals.
        rolling_rain = df["rainfall_mm"].rolling(24, min_periods=1).sum()
        df["soil_moisture"] = np.clip(25 + rolling_rain * 1.8 + (df["humidity_pct"] - 45) * 0.3, 15, 90)
        df["ndvi"] = np.clip(0.25 + df["soil_moisture"] * 0.0065 - (df["temperature_c"] - 24).abs() * 0.01, 0.1, 0.95)
        df["pest_risk"] = np.clip((df["humidity_pct"] / 100.0) * 0.7 + (df["temperature_c"] / 40.0) * 0.2, 0.01, 0.98)
        df["water_stress"] = np.clip((45 - df["soil_moisture"]) / 45, 0, 1)
        return df
