import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent 
COUNTY_CSV = PROJECT_ROOT / "county.csv"

def get_data_dir() -> Path:
    load_dotenv()
    DATA_DIR = os.getenv("DATA_DIR")
    if not DATA_DIR:
        raise RuntimeError("DATA_DIR is missing. You can find DATA_DIR in .env file")
    return Path(DATA_DIR)

    