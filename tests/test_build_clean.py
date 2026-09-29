"""
Tests for build_cleansed(). We never touch the real database here -
each test gets a fresh, empty, in-memory DuckDB (":memory:"),
so tests run fast and can never corrupt real data.
"""
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from build_clean import build_cleansed


@pytest.fixture
# Creates a new empty database in memory for each test
def con():
    connection = duckdb.connect(":memory:")
    connection.execute("""
        CREATE TABLE ref_county AS
        SELECT  '01' AS county_code,
                'Stockholms län' AS county_name
    """)  
    yield connection
    connection.close()

# Insert a list of rows into stage_events, so each test can describe its input data as Python dicts
def make_stage_events(con, rows:list[dict]):
    con.execute("""
        CREATE TABLE stage_events(
            event_id BIGINT, published_at TIMESTAMPTZ, published_at_local TIMESTAMP,
            title TEXT, summary TEXT, url_path TEXT, event_type TEXT,
            county_name TEXT, lat DOUBLE, lon DOUBLE,
            ingested_at TIMESTAMP, source_file TEXT
        )
    """)

    for r in rows:
        con.execute("""
            INSERT INTO stage_events VALUES(
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [  
            r["event_id"], r["published_at"], r["published_at_local"],
            r["title"], "x", "/x", "Trafikkontroll",
            r.get("county_name", "Stockholms län"), 59.3, 18.0,
            r["published_at_local"], "test.json",
    ])

#  A well-formed row should end up in cleansed_events, not quarantine
def test_normal_row_is_cleaned(con):
    make_stage_events(con, [{"event_id": 1,
        "published_at": "2026-09-24 12:35:36+02",
        "published_at_local": "2026-09-24 12:35:36",
        "title": "24 september 12.26, Trafikkontroll, Sundsvall",
        }])
    build_cleansed(con)
    assert con.execute("SELECT count(*) FROM cleansed_events").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM quarantine_events").fetchone()[0] == 0

# Event on Dec 31, published Jan 1 - event_year must roll back by 1,
# otherwise event_time would land in the future
def test_year_boundary_case(con):
    make_stage_events(con, [{
        "event_id": 2,
        "published_at": "2026-01-01 00:10:00+01",
        "published_at_local": "2026-01-01 00:10:00",
        "title": "31 december 23.55, Rattfylleri, Alvesta",  
    }])
    build_cleansed(con)
    row = con.execute("SELECT event_time FROM cleansed_events WHERE event_id =2").fetchone()
    assert row is not None, "row was wrongly quarantined"
    assert str(row[0]).startswith("2025-12-31")

# A title claiming a time later than the publish time is impossible
# must be quarantined
def test_event_time_after_published_is_quarantined(con):
    make_stage_events(con, [{
        "event_id": 3,
        "published_at": "2026-09-18 06:27:30+02",
        "published_at_local": "2026-09-18 06:27:30",
        "title": "18 september 22.07, Rattfylleri, Alvesta",
    }])
    build_cleansed(con)
    assert con.execute("SELECT count(*) FROM cleansed_events").fetchone()[0] == 0
    reason = con.execute("SELECT reason FROM quarantine_events WHERE event_id = 3").fetchone()[0]
    assert reason == "event_time_after_published"

# A county name that doesn't exist in ref_county must be caught
def test_unknown_county_is_quarantined(con):
    make_stage_events(con, [{
        "event_id": 4,
        "published_at": "2026-09-24 12:00:00+02",
        "published_at_local": "2026-09-24 12:00:00",
        "title": "24 september 12.00, Övrigt, Nowhere",
        "county_name": "Uppsalaaa",  # Uppsalaaa not a real county
    }])
    build_cleansed(con)
    assert con.execute("SELECT count(*) FROM cleansed_events").fetchone()[0] == 0
    reason = con.execute("SELECT reason FROM quarantine_events WHERE event_id = 4").fetchone()[0]
    assert reason == "unknown_county"


# A title that doesn't match the expected format at all must be quarantined with a reason
def test_unparsable_title_is_quarantined(con):
    make_stage_events(con, [{
         "event_id": 5,
        "published_at": "2026-09-24 12:00:00+02",
        "published_at_local": "2026-09-24 12:00:00",
        "title": "This is not a Polisen-style title at all",
    }])
    build_cleansed(con)
    assert con.execute("SELECT count(*) FROM cleansed_events").fetchone()[0]==0
    reason = con.execute("SELECT reason FROM quarantine_events WHERE event_id=5").fetchone()[0]
    assert reason == "unparsable_title"


def test_future_timestamp_is_quarantined(con):
    make_stage_events(con, [{
         "event_id": 1,
        "published_at": "2099-01-01 12:35:36+01",
        "published_at_local": "2099-01-01 12:35:36",
        "title": "1 januari 12.26, Trafikkontroll, Sundsvall",
    }])
    build_cleansed(con)
    assert con.execute("SELECT count(*) FROM cleansed_events").fetchone()[0]==0
    reason = con.execute("SELECT reason FROM quarantine_events WHERE event_id=1").fetchone()[0]
    assert reason == "future_timestamp"


