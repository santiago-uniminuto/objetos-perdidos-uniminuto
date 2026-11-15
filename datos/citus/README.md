# Citus (perfil `escala`)

Clúster de 1 coordinador y 2 workers para demostrar el sharding por sede (ADR-012). Es una **copia** para pruebas de escala y analítica: la fuente de verdad sigue siendo el PostgreSQL del perfil `core` (ADR-003, ADR-021).

> **Estado:** validado en la Fase 6 con Citus 12.1.6 y PostgreSQL 16 (coordinador y 2 workers, compilados desde el código fuente en el entorno de desarrollo). El esquema completo, migraciones 0001 a 0009, se distribuye sin errores, y el generador sintético carga por COPY sin cambios.

## Levantar, distribuir y cargar (PowerShell)

```powershell
$env:COMPOSE_PROFILES = "core,datos,escala"      # para esta terminal
docker compose up -d --build

# 1. Esquema completo en el coordinador (las mismas migraciones de Alembic que usa la API)
docker compose run --rm -e DATABASE_URL=postgresql://citus@citus-coordinador:5432/objetos_perdidos api alembic upgrade head

# 2. Registrar workers y distribuir las tablas
Get-Content datos/citus/01-distribuir.sql | docker compose exec -T citus-coordinador psql -U citus -d objetos_perdidos

# 3. Mismos datos sintéticos que en el PostgreSQL normal (misma semilla = mismas filas)
docker compose run --rm -e DATABASE_URL=postgresql://citus@citus-coordinador:5432/objetos_perdidos etl python -m sintetico.generar --reportes 1000000 --sedes 12

# 4. Balance entre workers y poda de shards
Get-Content datos/citus/02-balance.sql | docker compose exec -T citus-coordinador psql -U citus -d objetos_perdidos

# 5. PostgreSQL vs. Citus con las mismas consultas (el PostgreSQL normal debe tener los mismos datos sintéticos)
docker compose run --rm etl python citus/comparar.py --repeticiones 30 > pruebas-carga/resultados/citus-portatil.md
```

Dentro de la red de Docker, los nodos confían entre sí (`trust`), así que la URL no lleva contraseña. Desde fuera solo se expone el coordinador, en `127.0.0.1:5433`.

## Resultados en el entorno de desarrollo (referencia)

Datos: 300 mil reportes, 286 mil hallazgos, 161 mil coincidencias y 151 mil entregas en cada motor. Citus tiene 2 workers y 32 shards por tabla, en una máquina de **2 CPU** donde los tres nodos comparten núcleos. Tabla completa en [`pruebas-carga/resultados/citus-sandbox.md`](../../pruebas-carga/resultados/citus-sandbox.md).

| Consulta | PostgreSQL p50 | Citus p50 | Shards que toca |
|---|---:|---:|---:|
| Portal: últimos 25 de una sede | 0,5 ms | 6,6 ms | 1 |
| Matcher: candidatos de una sede | 0,8 ms | 4,7 ms | 1 |
| Bandeja del admin (join co-ubicado) | 18,2 ms | **13,2 ms** | 1 |
| Analítica global por sede y mes | 80 ms | 366 ms | 32 |

Carga: PostgreSQL tardó 74 s en recibir 2,4 M de filas y Citus 80 s.

**Cómo leerlo (para el artículo):**
- **La distribución por sede funciona.** Toda consulta de una sede toca 1 shard en 1 worker ("Task Count: 1"), y los joins entre tablas de la misma sede se resuelven en ese mismo worker, sin mover datos.
- **En una sola máquina Citus no puede ganar en velocidad bruta.** Cada consulta suma un salto coordinador → worker (~5 ms), y las globales reparten 32 tareas sobre 2 CPU. La bandeja sí es más rápida porque cada shard es más pequeño que la tabla entera.
- **La ganancia real aparece con workers en máquinas distintas.** Cada sede usaría la CPU, la RAM y el disco de su nodo, y las consultas globales correrían en paralelo de verdad. Eso es lo que ADR-012 proyecta para 68 sedes.
- **Sede caliente.** Con la distribución de Zipf del generador, la sede 1 tiene el 35 % de los reportes. Si un worker se satura, `isolate_tenant_to_new_shard` la saca a un shard propio (comentado en `02-balance.sql`).

## Hallazgos de la validación

1. **Llaves foráneas entre tablas que se distribuyen.** Citus no distribuye una tabla mientras otra tabla todavía local tenga una llave hacia ella. `01-distribuir.sql` quita esas 3 llaves, distribuye y las vuelve a crear entre tablas co-ubicadas.
2. **Llave entre sedes.** La llave `coincidencia → reporte` usa `reporte_sede_id` (ADR-020). Citus no la admite, así que se quita y la garantizan la API y el matcher.
3. **Vistas.** Al distribuir, Citus recrea las vistas solo en el coordinador. El script las garantiza al final.
4. **La API no corre tal cual sobre Citus.** Al correr la suite de integración contra el coordinador fallan 20 de 40 pruebas. 5 de esas fallas vienen de un ayudante de las pruebas (`test_esquema.py` inserta con una subconsulta) y 15 de la API:

   | Consulta de la API | Pruebas | Por qué Citus la rechaza |
   |---|---:|---|
   | Portal: listado y detalle (`publico.py`) | 5 | las fotos públicas salen de `foto_objeto`, que es una tabla local unida a una distribuida |
   | Detalle del reporte (`reportes.py`) | 4 | la sede de custodia lo lee si tiene una coincidencia: join entre sedes distintas, que no va por la columna de distribución |
   | Bandeja de coincidencias (`coincidencias.py`) | 3 | fotos (tabla local) y reporte de otra sede (`reporte_sede_id`) |
   | Ver una foto (`fotos.py`) | 2 | tabla local unida a coincidencias distribuidas |
   | Registrar entrega (`entregas.py`) | 1 | `FOR UPDATE` sobre un join entre sedes |

   Por eso Citus queda como **copia de escala y analítica**, no como base de la API (ADR-021). Adaptar la API implicaría distribuir `foto_objeto` y resolver los cruces entre sedes en dos pasos (primero la sede, después el join co-ubicado). Es trabajo para una versión de producción con varias máquinas.

## Apagar

```powershell
docker compose --profile escala down      # conserva los datos
docker compose --profile escala down -v   # borra el clúster
```
