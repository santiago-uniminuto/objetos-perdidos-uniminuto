# Objetos Perdidos y Hallados · UNIMINUTO

Sistema de gestión de objetos perdidos y hallados para la comunidad UNIMINUTO, con emparejamiento asistido por IA (agentes), persistencia políglota y analítica sobre un Data Lake.

Proyecto del curso **Fábricas de Software Agéntica (OPC)** — Ingeniería de Sistemas, UNIMINUTO. Equipo de 4 integrantes; cada uno trabaja como *One Person Company* apoyado por agentes de IA.

## Qué hace

- El **administrador** registra reportes de pérdida, hallazgos y entregas.
- El **público** (sin cuenta) consulta objetos perdidos y hallados **sin datos personales** (Ley 1581 de 2012).
- Un **agente matcher** sugiere coincidencias con puntaje y explicación; el admin siempre confirma.
- Un **agente notificador** avisa al dueño por correo institucional, y un **agente analista** resume zonas, horarios y picos.

## Arquitectura

| Pieza | Tecnología | Rol |
| --- | --- | --- |
| API | FastAPI (Python 3.12) | Monolito modular, contrato OpenAPI en `/api/docs` |
| Web | Next.js | Vista pública + panel admin |
| Relacional | PostgreSQL 16 + pgvector | Fuente de verdad, auditoría, embeddings |
| NoSQL | MongoDB 7 | Atributos por categoría, trazas de agentes |
| Distribuida | Citus 12 | Demo de sharding (perfil `escala`) |
| Data Lake | SeaweedFS (S3) + Parquet + DuckDB | Capas bronze / silver / gold |
| Caché y colas | Redis 7 | Caché, colas de trabajos, idempotencia |
| IA | Ollama (Qwen + bge-m3) vía API compatible con OpenAI | Proveedor cambiable por `.env` |
| Publicación | Caddy + Tailscale Funnel | URL pública HTTPS gratuita |

Las decisiones están en [`docs/adr/`](docs/adr/).

## Requisitos

- Windows 10/11 con **WSL2** y **Docker Desktop**, o Linux con Docker Engine + Compose v2.
- **Git**.
- **Ollama** instalado nativo (usa la GPU si existe). Ver `docs/guias/ollama.md` (próximamente).
- 16 GB de RAM recomendados.

## Arranque rápido

```bash
git clone https://github.com/santiago-uniminuto/objetos-perdidos-uniminuto.git
cd objetos-perdidos-uniminuto
cp .env.example .env        # en PowerShell: Copy-Item .env.example .env
# edita .env y cambia todas las contraseñas

docker compose --profile core up -d --build
```

Luego abre:

| URL | Qué es |
| --- | --- |
| http://localhost:8080 | Entrada principal (Caddy) |
| http://localhost:8080/api/v1/salud | Estado de la API |
| http://localhost:8080/api/docs | Documentación OpenAPI |
| http://localhost:8025 | Mailpit (correos de prueba) |

## Migraciones de base de datos

El esquema se crea con Alembic (SQL explícito en `backend/migraciones/sql/`):

```bash
docker compose --profile core build api
docker compose run --rm api alembic upgrade head      # crear / actualizar el esquema
docker compose run --rm api alembic current           # ver versión aplicada
```

Crear el primer administrador (la contraseña se pide por teclado):

```bash
docker compose run --rm api python -m app.crear_usuario --email admin@uniminuto.edu.co --nombre "Admin Sede" --rol admin_sede --sede 1
docker compose run --rm api python -m app.crear_usuario --email auditor@uniminuto.edu.co --nombre "Auditor" --rol auditor
```

MongoDB crea sus colecciones, validaciones e índices con `infra/mongo/init/01-colecciones.js` la primera vez que se crea su volumen.

## API

Documentación interactiva en `http://localhost:8080/api/docs`. Resumen (`/api/v1`):

| Ruta | Quién | Para qué |
| --- | --- | --- |
| `POST /auth/login`, `POST /auth/logout`, `GET /auth/yo` | Todos | Sesión en cookie httpOnly; bloqueo tras 5 intentos |
| `GET /publico/objetos`, `GET /publico/objetos/{id}` | Público | Perdidos y hallados sin datos personales; 60 consultas/min por IP |
| `GET /catalogos` | Público | Sedes, zonas y categorías |
| `POST /estudiantes`, `GET /estudiantes`, `POST /consentimientos` | Admin | Dueños y consentimiento (Ley 1581); toda lectura se audita |
| `POST /estudiantes/{id}/anonimizar` | Admin | Derecho de supresión |
| `POST /reportes`, `GET /reportes`, `GET /reportes/{id}` | Admin | Reportes de pérdida (POST exige `Idempotency-Key`) |
| `POST /hallazgos`, `GET /hallazgos`, `GET /hallazgos/{id}` | Admin | Hallazgos con vencimiento a 90 días |
| `GET /coincidencias`, `POST /coincidencias/{id}/verificar` y `/rechazar` | Admin | Bandeja de la IA; la decisión es humana |
| `POST /entregas` | Admin | Entrega con verificación; cierra el caso |
| `GET /auditoria` | Auditor | Bitácora de accesos |

## Perfiles de Docker Compose

El portátil anfitrión tiene 16 GB de RAM, así que los servicios se levantan por perfiles:

| Perfil | Servicios | Cuándo |
| --- | --- | --- |
| `core` | postgres, redis, mailpit, api, caddy | Siempre |
| `datos` | mongo, lake (SeaweedFS) | Analítica y trazas |
| `escala` | citus-coordinador, citus-worker-1, citus-worker-2 | Solo pruebas de escala |

```bash
docker compose --profile core --profile datos up -d     # producción
docker compose --profile escala up -d                   # demo de escala
docker compose down                                     # apagar (los datos quedan en volúmenes)
```

Ollama no va en Docker: corre nativo en Windows y los contenedores lo llaman en `host.docker.internal:11434`.

## Publicar con HTTPS

```bash
tailscale funnel --bg 8080
```

Publica `https://<equipo>.<tailnet>.ts.net` con certificado automático. Detalle en ADR-009.

## Estructura

```text
backend/        API FastAPI (módulos, migraciones, pruebas)
frontend/       Next.js
agentes/        Harness y agentes (matcher, notificador, analista)
datos/          ETL, generador sintético, Citus, consultas DuckDB
pruebas-carga/  Locust
infra/          Caddyfile, init de bases, scripts
docs/           ADRs, guías, artículo IEEE
```

## Cómo contribuir

Lee [`CONTRIBUTING.md`](CONTRIBUTING.md). Si trabajas con un agente de IA, el agente debe leer [`AGENTS.md`](AGENTS.md).

## Equipo

| Frente | Responsable |
| --- | --- |
| Backend + PostgreSQL | _pendiente_ |
| Datos (Mongo, lake, Citus, carga) | _pendiente_ |
| IA (harness y agentes) | _pendiente_ |
| Frontend + DevOps | _pendiente_ |
