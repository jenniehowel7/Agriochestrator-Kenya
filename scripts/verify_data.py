from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.dataset_manager import build_real_training_frame


def main() -> None:
    base = Path("data/raw")
    nasa = json.loads((base / "kenya_nasa_weather_daily.json").read_text(encoding="utf-8"))
    wb = json.loads((base / "worldbank_kenya_cereal_yield.json").read_text(encoding="utf-8"))

    params = nasa["properties"]["parameter"]
    print("nasa_keys", sorted(params.keys()))
    print("nasa_points", len(params["T2M"]))
    print("wb_meta_total", wb[0]["total"])
    print("wb_first_valid_year", next((r["date"] for r in wb[1] if r.get("value") is not None), None))

    df = build_real_training_frame("data/raw")
    print("training_rows", len(df))
    print("training_cols", list(df.columns))
    print("year_minmax", int(df["year"].min()), int(df["year"].max()))


if __name__ == "__main__":
    main()
