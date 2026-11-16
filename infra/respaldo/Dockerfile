# Misma imagen que la base (PostgreSQL 16): pg_dump y pg_restore de la misma versión mayor que el servidor.
FROM pgvector/pgvector:pg16

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-boto3 \
 && rm -rf /var/lib/apt/lists/*

COPY respaldo.py /usr/local/bin/respaldo.py
WORKDIR /respaldos
ENTRYPOINT ["python3", "/usr/local/bin/respaldo.py"]
CMD ["servicio"]
