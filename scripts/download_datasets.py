from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.dataset_manager import download_all_datasets


if __name__ == "__main__":
    print("Downloading datasets into data/raw ...")
    report = download_all_datasets("data/raw")
    pprint(report)
