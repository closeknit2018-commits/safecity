FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY county.csv .

CMD ["sh", "-c", "\
    python src/extract_polisen.py && \
    python src/build_staging.py && \
    python src/build_ref.py && \
    python src/build_clean.py && \
    python src/push_to_postgres.py \
"]

