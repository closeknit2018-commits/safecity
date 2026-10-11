"""
FastAPI service that reads the latest data from Postgres (Neon in
production, local Postgres for testing) and exposes it over HTTP.
"""
import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

load_dotenv()

app = FastAPI(title="SafeCity API")


def get_connection():
    """Open a fresh connection for one request"""
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT"),
        dbname=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        sslmode=os.getenv("PG_SSLMODE", "prefer"),
    )


@app.get("/health")
def health():
    """Basic check: is the API up, and can it reach the database?"""
    conn = get_connection()
    conn.close()
    return {"status": "ok"}


@app.get("/events/latest")
def latest_events(limit: int = 50):
    """Most recent events by event_time, newest first."""
    if limit > 500:
        raise HTTPException(400, "limit must be 500 or less")
    conn = get_connection()
    # RealDictCursor: each row comes back as a dict {column_name: value}
    # instead of a plain tuple - so it can be returned as JSON directly.
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT event_id, event_time, event_type, county_name, title
        FROM cleansed_events
        ORDER BY event_time DESC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return {"count": len(rows), "events": rows}


@app.get("/events/by-county")
def events_by_county():
    """Event count per county - the data the choropleth map needs."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT county_name, count(*) AS event_count
        FROM cleansed_events
        GROUP BY county_name
        ORDER BY event_count DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return {"counties": rows}


@app.get("/events/by-hour")
def events_by_hour():
    """Event count per hour of day - the data the time heatmap needs."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT EXTRACT(HOUR FROM event_time)::INT AS hour_of_day, count(*) AS event_count
        FROM cleansed_events
        GROUP BY hour_of_day
        ORDER BY hour_of_day
    """)
    rows = cur.fetchall()
    conn.close()
    return {"hours": rows}