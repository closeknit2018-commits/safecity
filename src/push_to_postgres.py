"""
Read the cleansed_events table from local DuckDB, write it to PostgreSQL.
"""
import os

import duckdb
import psycopg2
from config import get_data_dir
from dotenv import load_dotenv


def push_cleansed_events() -> None:
    load_dotenv()

    # read all clean data from DuckDB (still on this machine)
    duck_con = duckdb.connect(str(get_data_dir() / "data" / "safecity.duckdb"))
    rows = duck_con.execute("""
        SELECT event_id, published_at, published_at_local, title, summary,
            url_path, event_type, county_name, lat, lon,
            ingested_at, source_file, event_time, county_code 
        FROM cleansed_events""").fetchall()
    duck_con.close()
    print(f"Read {len(rows)} rows from DuckDB")

    # open a connection to PostgreSQL (address comes from .env)
    pg_con = psycopg2.connect(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT"),
        dbname=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
    )
    cur = pg_con.cursor()

    # create the table if it doesn't exist yet 
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cleansed_events (
            event_id BIGINT PRIMARY KEY,
            published_at TIMESTAMPTZ,
            published_at_local TIMESTAMP,
            title TEXT,
            summary TEXT,
            url_path TEXT,
            event_type TEXT,
            county_name TEXT,
            lat DOUBLE PRECISION,
            lon DOUBLE PRECISION,
            ingested_at TIMESTAMP,
            source_file TEXT,
            event_time TIMESTAMP,
            county_code TEXT
        )
    """)

    # write ONE ROW AT A TIME with a plain loop
    for row in rows:
        cur.execute("""
            INSERT INTO cleansed_events (
                event_id, published_at, published_at_local, title, summary,
                url_path, event_type, county_name, lat, lon,
                ingested_at, source_file, event_time, county_code
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO UPDATE SET
                published_at = EXCLUDED.published_at,
                published_at_local = EXCLUDED.published_at_local,
                title = EXCLUDED.title,
                summary = EXCLUDED.summary,
                event_type = EXCLUDED.event_type,
                county_name = EXCLUDED.county_name,
                event_time = EXCLUDED.event_time,
                county_code = EXCLUDED.county_code
        """, row)

    # actually save to the databasen
    pg_con.commit()

    cur.execute("SELECT count(*) FROM cleansed_events")
    print("Total rows in Postgres:", cur.fetchone()[0])

    cur.close()
    pg_con.close()


if __name__ == "__main__":
    push_cleansed_events()