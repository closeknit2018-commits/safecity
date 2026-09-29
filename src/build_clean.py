# Step 3: Turn stage_events into cleansed_event(clean) 
# and create 2 table cleansed_events and quarantine_events(faulty data needs to be isolated.)

import duckdb

# This string is used to extract time from article titles 
# (e.g., "24 september 12.26, ..."):
# Group 1 (\d{1,2}): Day (24) 
# Group 2 (\w+): Month name in Swedish (september) 
# Group 3 (\d{1,2}): Hour (12) 
# Group 4 (\d{2}): Minute (26)

TITLE_PATERN = r'^(\d{1,2}) (\w+) (\d{1,2})\.(\d{2}),'

"""The intermediate steps are written as WITH (CTE) inside ONE SQL statement,
read top to bottom like a multi-step recipe.
"""
PARSE_STEPS_SQL = f"""
    --deduplicate keep only the latest row per event_id
    WITH dedup AS(
            SELECT *, 
            ROW_NUMBER() OVER(PARTITION BY event_id ORDER BY ingested_at DESC) AS row_num
            FROM stage_events),
        dedup_ok AS(
            SELECT * EXCLUDE(row_num)
            FROM dedup WHERE row_num = 1),
    
    --extract day/month/hour/minute from title using regex
        split_title AS(
            SELECT *,
            regexp_extract(title, '{TITLE_PATERN}', 1) AS day_str,
            regexp_extract(title, '{TITLE_PATERN}', 2) AS month_name,
            regexp_extract(title, '{TITLE_PATERN}', 3) AS hour_str,
            regexp_extract(title, '{TITLE_PATERN}', 4) AS minute_str
            FROM dedup_ok),

    --convert Swedish month name from title to number, and compute event year 
    --if the title's month is later than the publish month, the event was last year)
        with_month_year AS(
            SELECT *,
                CASE lower(month_name)
                    WHEN 'januari'   THEN 1  WHEN 'februari' THEN 2
                    WHEN 'mars'      THEN 3  WHEN 'april'    THEN 4
                    WHEN 'maj'       THEN 5  WHEN 'juni'     THEN 6
                    WHEN 'juli'      THEN 7  WHEN 'augusti'  THEN 8
                    WHEN 'september' THEN 9  WHEN 'oktober'  THEN 10
                    WHEN 'november'  THEN 11 WHEN 'december' THEN 12
                    ELSE NULL
                END AS month_num
            FROM split_title),

        with_event_year AS(
            SELECT *,
                CASE
                    WHEN month_num > month(published_at_local)
                        THEN year(published_at_local) - 1
                    ELSE year(published_at_local)
                END AS event_year
            FROM with_month_year),

    --combine into one real timestamp 
        with_event_time AS(
        SELECT *,
        make_timestamp(
            event_year, month_num,
            TRY_CAST(day_str AS INT),
            TRY_CAST(hour_str AS INT),
            TRY_CAST(minute_str AS INT), 0
            ) AS event_time
        FROM with_event_year),

    
    -- county_name must exist in ref_county
    -- LEFT JOIN retains all left-hand lines
    -- if not a match, ref.county_code will be NULL
        with_ref_check AS(
            SELECT e.*,
            r.county_code
            FROM with_event_time e
            LEFT JOIN ref_county r
                ON e.county_name = r.county_name)

    SELECT * FROM with_ref_check
"""

# con: an duckdb connection. The caller decides which database this is 
# the real one when run as a script, an in-memory one in tests.
def build_cleansed(con) -> None:
    
    # published time should not be in the future
    # drop rows where the title could not be parsed (month_num IS NULL)
    con.execute(f"""
        CREATE OR REPLACE TABLE cleansed_events AS {PARSE_STEPS_SQL}
        WHERE month_num IS NOT NULL
        AND published_at <= now() + INTERVAL 5 MINUTE   
        AND event_time <= published_at_local + INTERVAL 5 MINUTE
        AND county_code IS NOT NULL 
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE quarantine_events AS
        SELECT 
            event_id, title, published_at,
            CASE
                WHEN month_num IS NULL THEN 'unparsable_title'
                WHEN published_at > now() + INTERVAL 5 MINUTE THEN 'future_timestamp'
                WHEN event_time > published_at_local + INTERVAL 5 MINUTE THEN 'event_time_after_published'
                ELSE 'unknown_county'
            END AS reason
        FROM ({PARSE_STEPS_SQL})
        WHERE month_num IS NULL 
        OR published_at > now() + INTERVAL 5 MINUTE
        OR event_time > published_at_local + INTERVAL 5 MINUTE
        OR county_code IS NULL
    """)

def run_for_real_database():
    from config import get_data_dir
    db_path = get_data_dir() / "data" / "safecity.duckdb"
    con = duckdb.connect(str(db_path))

    build_cleansed(con)
    print("cleansed_events   :", con.execute("SELECT count(*) FROM cleansed_events").fetchone()[0])
    print("quarantine_events :", con.execute("SELECT count(*) FROM quarantine_events").fetchone()[0])
    con.close()
  
    # con = duckdb.connect(str(db_path))
    # rows = con.execute("""
    #     SELECT event_id, title,
    #         CAST(published_at_local AS VARCHAR) AS published_local,
    #         CAST(event_time AS VARCHAR) AS event_time
    #     FROM cleansed_events
    #     WHERE event_time > published_at_local + INTERVAL 5 MINUTE
    # """).fetchall()
    # for r in rows:
    #     print(r)
    # con.close()

if __name__ == "__main__":
    run_for_real_database()

