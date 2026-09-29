"""
Load static reference tables (currently: Swedish counties) into DuckDB.
These change almost never, so we read them from a checked-in CSV file
instead of calling an API on every pipeline run.
"""
import duckdb
from config import COUNTY_CSV, get_data_dir


def build_ref() -> None:
    db_path = get_data_dir() / "data" / "safecity.duckdb"
    ref_csv = COUNTY_CSV

    con = duckdb.connect(str(db_path))
    con.execute(f"""
        CREATE OR REPLACE TABLE ref_county AS
        SELECT * FROM read_csv('{ref_csv.as_posix()}', header=true)
    """)
    print(con.execute("SELECT count(*) FROM ref_county").fetchone())
    print(con.execute("DESCRIBE ref_county").fetchall())
    con.close()


if __name__ == "__main__":
    build_ref()
    