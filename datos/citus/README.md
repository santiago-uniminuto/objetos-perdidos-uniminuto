# Citus (perfil `escala`)

Clúster de 1 coordinador + 2 workers para demostrar sharding. Es una **copia** para pruebas de escala; la fuente de verdad sigue siendo el PostgreSQL del perfil `core` (ADR-003).

## Levantar y preparar

```powershell
docker compose --profile escala up -d --build
# 1. Esquema en el coordinador (mismo SQL que la migración 0001)
Get-Content backend/migraciones/sql/0001_esquema_inicial.sql | docker compose exec -T citus-coordinador psql -U citus -d objetos_perdidos
# 2. Registrar workers y distribuir tablas
Get-Content datos/citus/01-distribuir.sql | docker compose exec -T citus-coordinador psql -U citus -d objetos_perdidos
```

En Linux/macOS usa `cat archivo | docker compose exec -T ...`.

La extensión `vector` debe instalarse también en cada worker: el paso 1 la crea en el coordinador y Citus la propaga al agregar los nodos. Si un worker reporta que falta, ejecuta en él `CREATE EXTENSION vector;`.

## Medir

`02-balance.sql` muestra filas por worker, sedes más cargadas y si una consulta toca un solo shard.

## Apagar

```powershell
docker compose --profile escala down      # conserva datos
docker compose --profile escala down -v   # borra el clúster
```

> Estado: script escrito en la Fase 3 y pendiente de validarse en el portátil (el entorno donde se escribió no tiene Citus).
