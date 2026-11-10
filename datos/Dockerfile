FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DUCKDB_TEMP=/tmp/duckdb

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY lago ./lago
COPY sintetico ./sintetico

RUN useradd --create-home --uid 10002 datos && mkdir -p /tmp/duckdb && chown datos /tmp/duckdb
USER datos

# Servicio `etl`. El generador se corre a mano: docker compose run --rm etl python -m sintetico.generar ...
CMD ["python", "-m", "lago.etl"]
