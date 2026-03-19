from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib


class CropRiskPredictor:
    """Loads a placeholder model artifact and exposes a stable predict API."""

    def __init__(self, artifact_path: str = "models/crop_risk_model.json") -> None:
        requested_path = Path(artifact_path)
        self.artifact_path = self._resolve_artifact_path(requested_path)
        self.model: Any | None = None
        self.model_bundle: dict[str, Any] | None = None
        self.metadata: dict[str, Any] | None = None
        self.model_type = "heuristic"
        self.loaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._load_artifact()
        self._load_metadata(requested_path)

    def _resolve_artifact_path(self, requested_path: Path) -> Path:
        if requested_path.exists():
            return requested_path

        # Prefer a trained joblib model when available.
        joblib_path = requested_path.with_suffix(".joblib")
        if joblib_path.exists():
            return joblib_path

        # Fallback to placeholder JSON model.
        json_path = requested_path.with_suffix(".json")
        return json_path

    def _load_artifact(self) -> None:
        if not self.artifact_path.exists():
            return

        if self.artifact_path.suffix == ".joblib":
            payload = joblib.load(self.artifact_path)
            if isinstance(payload, dict) and "model" in payload:
                self.model_bundle = payload
                self.model = payload["model"]
            else:
                self.model = payload
            self.model_type = "joblib"
            return

        if self.artifact_path.suffix == ".json":
            with self.artifact_path.open("r", encoding="utf-8") as handle:
                self.model = json.load(handle)
            self.model_type = "json"

    def _load_metadata(self, requested_path: Path) -> None:
        """Load model card metadata from bundle or sidecar file for richer UI."""

        # Prefer embedded metadata from a joblib bundle.
        if self.model_bundle and isinstance(self.model_bundle.get("model_card"), dict):
            self.metadata = self.model_bundle.get("model_card")
            return

        candidates = [
            requested_path.with_suffix(".metadata.json"),
            Path("models/model_card.json"),
        ]

        for candidate in candidates:
            if candidate.exists():
                try:
                    self.metadata = json.loads(candidate.read_text(encoding="utf-8"))
                    return
                except json.JSONDecodeError:
                    continue

    def predict_risk(self, features: dict[str, float]) -> dict[str, float | str]:
        if self.model_type == "joblib" and self.model is not None:
            feature_order = ["soil_moisture", "temperature_c", "humidity_pct", "pest_risk", "ndvi"]
            if self.model_bundle and isinstance(self.model_bundle.get("features"), list):
                feature_order = [str(f) for f in self.model_bundle["features"]]

            vector = [[features.get(name, 0.0) for name in feature_order]]
            score = float(self.model.predict_proba(vector)[0][1])
            return self._format_result(score, "joblib")

        if self.model_type == "json" and isinstance(self.model, dict):
            w = self.model.get("weights", {})
            bias = float(self.model.get("bias", 0.0))
            linear = (
                float(w.get("soil_moisture", -0.03)) * features.get("soil_moisture", 50)
                + float(w.get("temperature_c", 0.02)) * features.get("temperature_c", 25)
                + float(w.get("humidity_pct", 0.01)) * features.get("humidity_pct", 60)
                + float(w.get("pest_risk", 0.9)) * features.get("pest_risk", 0.2)
                + float(w.get("ndvi", -0.8)) * features.get("ndvi", 0.6)
                + bias
            )
            score = 1 / (1 + (2.71828 ** (-linear)))
            return self._format_result(float(score), "json-placeholder")

        score = min(0.95, max(0.05, features.get("pest_risk", 0.2) + features.get("water_stress", 0.2) * 0.7))
        return self._format_result(float(score), "heuristic")

    def _format_result(self, score: float, source: str) -> dict[str, float | str]:
        level = "Low"
        if score >= 0.67:
            level = "High"
        elif score >= 0.4:
            level = "Medium"
        return {
            "risk_score": round(score, 3),
            "risk_level": level,
            "model_source": source,
        }

    def get_model_details(self) -> dict[str, Any]:
        details: dict[str, Any] = {
            "artifact_path": str(self.artifact_path),
            "model_type": self.model_type,
            "loaded_at": self.loaded_at,
            "artifact_exists": self.artifact_path.exists(),
            "artifact_sha256": self._artifact_sha256(),
            "artifact_size_kb": self._artifact_size_kb(),
            "artifact_mtime": self._artifact_mtime(),
            "bundle_features": None,
            "bundle_version": None,
            "trained_years": None,
            "metrics": None,
            "training_rows": None,
            "model_name": None,
            "target": None,
        }

        if self.model_bundle:
            details["bundle_features"] = self.model_bundle.get("features")
            details["bundle_version"] = self.model_bundle.get("version")
            details["trained_years"] = self.model_bundle.get("trained_years")

        if self.metadata:
            details.update(
                {
                    "model_name": self.metadata.get("model_name"),
                    "bundle_version": self.metadata.get("version", details.get("bundle_version")),
                    "trained_years": self.metadata.get("trained_years", details.get("trained_years")),
                    "bundle_features": self.metadata.get("features", details.get("bundle_features")),
                    "metrics": self.metadata.get("metrics"),
                    "training_rows": self.metadata.get("training_rows"),
                    "target": self.metadata.get("target"),
                    "data_sources": self.metadata.get("data_sources"),
                }
            )

        if self.model_type == "json" and isinstance(self.model, dict):
            details["json_weights"] = self.model.get("weights")
            details["json_bias"] = self.model.get("bias")

        return details

    def _artifact_sha256(self) -> str | None:
        if not self.artifact_path.exists():
            return None
        digest = hashlib.sha256(self.artifact_path.read_bytes()).hexdigest()
        return digest

    def _artifact_size_kb(self) -> int | None:
        if not self.artifact_path.exists():
            return None
        return int(self.artifact_path.stat().st_size / 1024)

    def _artifact_mtime(self) -> str | None:
        if not self.artifact_path.exists():
            return None
        return datetime.fromtimestamp(self.artifact_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
