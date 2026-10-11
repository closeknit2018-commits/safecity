
## `README.md`

# SafeCity Analytics

A daily-updating data platform built on **real, public, live police event data** from
[polisen.se](https://polisen.se/api/events) — Sweden's open police events API.
Built as a hands-on data engineering learning project: ingestion, data quality,
a Postgres warehouse, a public API, containerization, and CI/CD, end to end.

## Architecture


polisen.se/api/events
        │  HTTPS
        ▼
  extract_polisen.py  ──▶  raw JSON (immutable, partitioned by date)
        │
        ▼
  build_staging.py (DuckDB)  ──▶  stage_events
        │
        ▼
  build_ref.py (DuckDB)  ──▶  ref_county (21 Swedish counties)
        │
        ▼
  build_clean.py (DuckDB)  ──▶  cleansed_events / quarantine_events
        │
        ▼
  push_to_postgres.py (upsert)  ──▶  Neon Postgres (permanent, cumulative)
        │
        ├──▶  src/api.py (FastAPI)  ──▶  public read API
        └──▶  Power BI report  ──▶  map + filters + hourly breakdown


The whole pipeline runs **automatically every day** via GitHub Actions
(`.github/workflows/pipeline.yml`), packaged as a Docker image so it runs
identically locally and in CI.

## Data quality rules

Applied in `build_clean.py`, bad rows are quarantined with a reason, never
silently dropped:

1. Deduplication by `event_id` (the API's 500-event window repeats old events)
2. `published_at` cannot be in the future
3. `event_time` (parsed from the title) cannot be after `published_at`
4. `county_name` must exist in the reference table (`ref_county`)
5. Unparsable titles are quarantined, not discarded

## Project structure


safecity-analytics/
├── src/
│   ├── extract_polisen.py      # fetch + save raw JSON (atomic write)
│   ├── build_staging.py        # DuckDB: raw -> stage_events
│   ├── build_ref.py             # DuckDB: load county.csv -> ref_county
│   ├── build_clean.py           # DuckDB: stage -> cleansed/quarantine
│   ├── push_to_postgres.py      # upsert cleansed_events into Postgres
│   ├── config.py                # shared path/env helpers
│   └── api.py                    # FastAPI read endpoints
├── tests/
│   └── test_build_clean.py       # pytest, in-memory DuckDB, no real DB touched
├── county.csv                    # static reference data (21 Swedish counties)
├── Dockerfile
├── requirements.txt
├── .github/workflows/pipeline.yml  # daily cron (03:00 UTC) + manual trigger
└── .env.example


## Running it yourself

### Prerequisites
- Python 3.12+
- Docker Desktop
- A Postgres database (local, or a free [Neon](https://neon.tech) project)

### Setup
```bash
git clone https://github.com/<your-username>/safecity.git
cd safecity
cp .env.example .env     # then fill in your real DATA_DIR / PG_* values
pip install -r requirements.txt
```

### Run the pipeline manually
```bash
python src/extract_polisen.py
python src/build_staging.py
python src/build_ref.py
python src/build_clean.py
python src/push_to_postgres.py
```

### Run via Docker (same image used in CI)
```bash
docker build -t safecity-pipeline .
docker run --rm --env-file .env -e DATA_DIR=/app/data -v "$(pwd)/data:/app/data" safecity-pipeline
```

### Run the tests
```bash
python -m pytest -v
```

### Run the API locally
```bash
uvicorn src.api:app --reload
```
Then open `http://127.0.0.1:8000/docs` for interactive API docs.

**Endpoints:**
- `GET /health`
- `GET /events/latest?limit=50`
- `GET /events/by-county`
- `GET /events/by-hour`

## Automation

`.github/workflows/pipeline.yml` runs the Docker image on a daily schedule
(`cron: "0 3 * * *"`, 03:00 UTC), using GitHub Secrets for database credentials.
A manual **Run workflow** button is also available for on-demand runs.

## Power BI report

`safecity-report.pbix` connects directly to the Postgres warehouse (Import mode).
To use it: open in Power BI Desktop, update the data source credentials to your
own database, then **Refresh**.

## Known limitations (v1)

- Raw JSON archives are not persisted between GitHub Actions runs (ephemeral
  runner) — only the final cleansed table in Postgres accumulates long-term.
- The source API only ever returns the 500 most recent events, so polling
  frequency matters; daily polling is safe at the current event rate
  (~35 new events/day).
- `location.gps` from the source API is a county centroid, not the exact
  event location — the map is intentionally county-level (choropleth), not
  point-level.


