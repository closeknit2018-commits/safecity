import json
import duckdb

def create_connection():
    con = duckdb.connect(":memory:")
    
def load_dataset(raw_data):
    if raw_data.endwith(".json"):
        return f"read_json('{raw_data}')"
    else:
        raise ValueError(f"Not support the format: '{raw_data}'")


def transform_dataset(con, raw_data, output_name):
    
