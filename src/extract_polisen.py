import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from config import get_data_dir

API_URL = "https://polisen.se/api/events"
SOURCE = "polisen_events"

def extract_polisen_events(params: dict | None = None) -> Path:
    """Retrieve the latest police events by region and save them as raw JSON"""

    response = requests.get(API_URL, params=params, timeout=10)
    response.raise_for_status() 
    events = response.json()
    if not isinstance(events, list):
        raise ValueError(f"Expected a list, got {type(events).__name__}")

    now = datetime.now(timezone.utc)
    OUT_DIR = get_data_dir() / "data" /"raw" / "polisen_events" /f"ingest_date={now:%Y-%m-%d}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE = OUT_DIR / f"events_{now:%Y%m%dT%H%M%SZ}.json"

    # Creates a temporary file name
    tmp_file  = OUT_FILE.with_suffix(".tmp")
    # All writing is done to the .tmp file. If the script dies here, only half a .tmp file remains. 
    # The real .json file doesn't exist, so no one can read something broken.
    tmp_file.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    # Renames .tmp to .json
    tmp_file.replace(OUT_FILE)

    print(f"Get {len(events)} events {OUT_FILE}")
    return OUT_FILE

if __name__ == "__main__":
    extract_polisen_events()
    