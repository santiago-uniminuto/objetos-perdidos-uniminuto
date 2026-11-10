# Datos: ETL, Data Lake y datos sintéticos

**Responsable:** Datos · **Fase:** 5 (parte 3)

```
PostgreSQL ──outbox──► ETL (servicio `etl`) ──► MongoDB `eventos`   (consulta operativa de eventos)
                                            └─► lake bronze/        (Parquet crudo, solo se agrega)
                                                   │ DuckDB cada ETL_TRANSFORMAR_MINUTOS
                                                   ▼
                                                silver/  (deduplicado, una fila por entidad, catálogos)
                                                gold/    (agregados para el tablero y el agente analista)
```

| Carpeta | Contenido |
|---|---|
| `lago/almacen.py` | Acceso al lake con pyarrow: S3 (SeaweedFS) si hay `S3_ENDPOINT`, carpeta local si no |
| `lago/etl.py` | Consumidor `etl` del outbox (ADR-004/014): bronze + Mongo, offset en `consumidor_outbox` |
| `lago/transformar.py` | SQL DuckDB de silver y gold |
| `lago/calendario.py` | Semanas del semestre y parciales (**supuesto**: cambiar por el calendario oficial) |
| `sintetico/generar.py` | Generador reproducible de ≥ 1 M de reportes multi-sede (COPY) |
| `citus/` | Distribución y balance en Citus (ADR-012) |

## Capas del lake

| Capa | Ruta | Qué tiene |
|---|---|---|
| bronze | `bronze/eventos/fecha=AAAA-MM-DD/` | Eventos del outbox tal cual, un archivo por lote (se compactan solos) |
| silver | `silver/reportes/anio=/mes=/`, `silver/hallazgos/...`, `silver/coincidencias/`, `silver/catalogos/` | Una fila por objeto: categoría, zona, sede, si se recuperó y en cuántos días |
| gold | `gold/kpi_recuperacion_mensual`, `gold/mapa_calor_zona_hora`, `gold/serie_semanal`, `gold/calidad_matching` | Agregados listos para graficar y predecir |

Ninguna capa tiene datos personales: el outbox solo lleva ids, categoría, zona, fecha y hora
(una prueba de integración lo verifica). Silver y gold se **reconstruyen completas** desde bronze,
así que son idempotentes: si algo sale mal, se borran y se regeneran.

## Uso con Docker (portátil)

`etl` depende de `postgres` (perfil core), así que **todo** comando de compose necesita los dos
perfiles activos. Lo más cómodo es `COMPOSE_PROFILES=core,datos` en `.env` (ya viene en
`.env.example`); si no, agrega `--profile core --profile datos` a cada comando, también a `run` y `logs`.

```powershell
docker compose up -d --build
docker compose logs -f etl                       # "bronze: N eventos" / "silver/gold reconstruidas"

# Datos sintéticos (el generador solo inserta en PostgreSQL; el ETL los lleva al lake)
docker compose run --rm etl python -m sintetico.generar --reportes 100000 --sedes 12          # ~30 s
docker compose run --rm etl python -m sintetico.generar --reportes 1000000 --sedes 12 --limpiar  # ~5 min
docker compose run --rm etl python -m sintetico.generar --solo-limpiar   # borra lo sintético de PostgreSQL
```

Medido en el entorno de desarrollo: 100 000 reportes son **833 000 filas** en 26 s, y el ETL
(bronze + silver + gold de 367 000 eventos) tarda ~10 s. 1 M de reportes ≈ 8 M de filas.

- Lo sintético se reconoce por `descripcion LIKE '%(sintético)'`, documentos `SIN…`, actas `SIN-…`
  y `modelo_embedding = 'sintetico'`. Todos los nombres salen de una lista fija.
- El matcher y el notificador **no** procesan lo sintético (serían millones de llamadas al LLM y
  correos): el generador mueve sus offsets al final del outbox. El ETL sí lo procesa.
- `--limpiar` borra de PostgreSQL, no del lake. Para empezar de cero el lake:
  `docker compose stop etl`, borrar el bucket desde la consola de SeaweedFS (o `docker volume rm`
  del volumen `lake_datos`), poner `UPDATE consumidor_outbox SET ultimo_id = 0 WHERE consumidor = 'etl'`
  y volver a arrancar `etl`.
- Mongo borra eventos con más de 1 año (índice TTL), así que los sintéticos viejos no se quedan ahí;
  en el lake sí quedan.
- Con 16 GB de RAM: `DUCKDB_MEMORIA=2GB` (en `.env`) hace que DuckDB use disco en vez de agotar la memoria.

## Patrones del generador

Están puestos a propósito, para que la analítica y el agente analista tengan algo que encontrar:

- Más pérdidas entre semana, casi nada en vacaciones y **×1,8 en semanas de parciales** (8 y 16).
- Horas pico a media mañana y en la tarde; Aulas, Biblioteca y Cafeterías concentran más casos.
- Tasa de recuperación por categoría: documentos 72 %, electrónicos 62 % … otros 30 %.
- Días hasta la entrega con distribución exponencial (mediana ≈ 3 días, máximo 60).
- Sedes de tamaño desigual (Zipf), para medir el balance de shards en Citus.
- 1 de cada 5 recuperados tuvo antes una sugerencia equivocada que el admin rechazó; así
  `gold/calidad_matching` muestra una precisión realista (~0,83).

## Sin Docker (desarrollo)

```bash
cd datos
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql://app:app@localhost:5432/objetos_perdidos LAGO_LOCAL=./lago-local
python -m sintetico.generar --reportes 5000 --sedes 4
python -m lago.etl --una-vez          # procesa todo, transforma y termina
pytest -q                             # pruebas del lake
PRUEBAS_INTEGRACION=1 pytest -q tests/integracion   # generador + ETL + silver/gold contra PostgreSQL
```

Para mirar el lake: `duckdb -c "SELECT * FROM './lago-local/gold/kpi_recuperacion_mensual/*.parquet' LIMIT 10"`.
