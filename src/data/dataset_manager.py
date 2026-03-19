from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlretrieve

import pandas


@dataclass(frozen=True)
class DatasetSource:
    name: str
    url: str
    file_name: str
    description: str


DATASET_SOURCES = [
    DatasetSource(
        name="NASA POWER Kenya Daily Weather",
        url=(
            "https://power.larc.nasa.gov/api/temporal/daily/point"
            "?parameters=T2M,PRECTOTCORR,RH2M&community=AG&longitude=36.8219"
            "&latitude=-1.2921&start=20180101&end=20251231&format=JSON"
        ),
        file_name="kenya_nasa_weather_daily.json",
        description="Daily weather series for Nairobi area: temperature, rainfall, humidity.",
    ),
    DatasetSource(
        name="World Bank Kenya Cereal Yield",
        url="https://api.worldbank.org/v2/country/KEN/indicator/AG.YLD.CREL.KG?format=json&per_page=20000",
        file_name="worldbank_kenya_cereal_yield.json",
        description="Historical Kenya cereal yield indicator from World Bank API.",
    ),
    DatasetSource(
        name="World Bank Kenya Irrigated Agricultural Land",
        url="https://api.worldbank.org/v2/country/KEN/indicator/AG.LND.IRIG.AG.ZS?format=json&per_page=20000",
        file_name="worldbank_kenya_irrigated_land.json",
        description="Share of agricultural land equipped for irrigation in Kenya.",
    ),
    DatasetSource(
        name="World Bank Kenya Fertilizer Consumption",
        url="https://api.worldbank.org/v2/country/KEN/indicator/AG.CON.FERT.PT.ZS?format=json&per_page=20000",
        file_name="worldbank_kenya_fertilizer.json",
        description="Fertilizer consumption trend for Kenya agriculture policy features.",
    ),
]


def download_all_datasets(raw_dir: str = "data/raw") -> list[dict[str, str]]:
    target = Path(raw_dir)
    target.mkdir(parents=True, exist_ok=True)
    report: list[dict[str, str]] = []

    for source in DATASET_SOURCES:
        output_path = target / source.file_name
        try:
            urlretrieve(source.url, output_path)
            report.append(
                {
                    "name": source.name,
                    "status": "downloaded",
                    "path": str(output_path),
                    "description": source.description,
                }
            )
        except URLError as exc:
            report.append(
                {
                    "name": source.name,
                    "status": f"failed: {exc.reason}",
                    "path": str(output_path),
                    "description": source.description,
                }
            )
    return report


def load_nasa_daily_weather(raw_dir: str = "data/raw") -> Any:
    path = Path(raw_dir) / "kenya_nasa_weather_daily.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    params = payload["properties"]["parameter"]

    df = pandas.DataFrame(
        {
            "date": pandas.to_datetime(list(params["T2M"].keys()), format="%Y%m%d"),
            "temperature_c": list(params["T2M"].values()),
            "rainfall_mm": list(params["PRECTOTCORR"].values()),
            "humidity_pct": list(params["RH2M"].values()),
        }
    )
    return df.sort_values("date").reset_index(drop=True)


def load_worldbank_indicator(file_name: str, value_name: str, raw_dir: str = "data/raw") -> Any:
    path = Path(raw_dir) / file_name
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
    data = []
    for row in rows:
        value = row.get("value")
        if value is None:
            continue
        data.append({"year": int(row["date"]), value_name: float(value)})
    return pandas.DataFrame(data).drop_duplicates("year").sort_values("year").reset_index(drop=True)


def build_real_training_frame(raw_dir: str = "data/raw") -> Any:
    weather = load_nasa_daily_weather(raw_dir)
    weather["year"] = weather["date"].dt.year
    annual_weather = weather.groupby("year", as_index=False).agg(
        {"temperature_c": "mean", "rainfall_mm": "sum", "humidity_pct": "mean"}
    )

    cereal = load_worldbank_indicator("worldbank_kenya_cereal_yield.json", "cereal_yield_kg_per_ha", raw_dir)
    irrig = load_worldbank_indicator("worldbank_kenya_irrigated_land.json", "irrigated_land_pct", raw_dir)
    fert = load_worldbank_indicator("worldbank_kenya_fertilizer.json", "fertilizer_pct", raw_dir)

    df = annual_weather.merge(cereal, on="year", how="inner")
    df = df.merge(irrig, on="year", how="left").merge(fert, on="year", how="left")
    df["irrigated_land_pct"] = df["irrigated_land_pct"].interpolate().bfill().ffill()
    df["fertilizer_pct"] = df["fertilizer_pct"].interpolate().bfill().ffill()
    return df.sort_values("year").reset_index(drop=True)
