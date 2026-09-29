import duckdb
from config import get_data_dir


def build_staging() -> None:
    data_dir = get_data_dir()
    # create a pattern to find all json file in folder
    raw_glob = (data_dir / "data" / "raw" / "polisen_events" / "*" / "events_*.json")
    # defind place to save database duckdb
    db_path = data_dir/ "data" / "safecity.duckdb"

    DATETIME_OFFSET_PATTERN = r'[+-]\d{2}:\d{2}$'

    con = duckdb.connect(str(db_path))
    con.execute(f"""
        CREATE OR REPLACE TABLE stage_events AS
        SELECT 
            id::BIGINT AS event_id,
            strptime(datetime, '%Y-%m-%d %H:%M:%S %z') AS published_at,
            name AS title,
            summary,
            url AS url_path,
            type AS event_type,
            location.name AS county_name,
            TRY_CAST(NULLIF(split_part(location.gps, ',', 1), '') AS DOUBLE) AS lat,
            TRY_CAST(NULLIF(split_part(location.gps, ',', 2), '') AS DOUBLE) AS lon,
            strptime(regexp_extract(filename, 'events_(\\d{{8}}T\\d{{6}}Z)', 1),
                     '%Y%m%dT%H%M%SZ') AS ingested_at,
            filename AS source_file,
            strptime(regexp_replace(datetime, '{DATETIME_OFFSET_PATTERN}', ''),
             '%Y-%m-%d %H:%M:%S') AS published_at_local
        FROM read_json('{raw_glob}', format='array', filename=true)
""")
    print(con.execute("""
        SELECT count(*) as rows,
                count(DISTINCT event_id) AS unique_id
        FROM stage_events""").fetchall())
    con.close()

    con = duckdb.connect(str(db_path))
    print(con.execute("""
        SELECT CAST(min(published_at) AS VARCHAR), CAST(max(published_at) AS VARCHAR)
        FROM stage_events
    """).fetchall())
    con.close()

if __name__ == "__main__":
    build_staging()
