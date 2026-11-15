# Pruebas de carga (Fase 6)

Locust contra la API, con dos perfiles de usuario en la proporción de un día de oficina:

| Perfil | Peso | Qué hace |
|---|---|---|
| `VisitantePortal` | 85 % | Lista objetos por sede (a veces filtra por categoría o fecha), baja a la página 2, abre un detalle, pide catálogos |
| `AdminSede` | 15 % | Listados de reportes y hallazgos, bandeja de coincidencias, analítica y, de vez en cuando, registra un reporte |

**Metas** (el proceso sale con código 1 si no se cumplen):

- RNF-01: p95 de la lectura pública < 300 ms con ≥ 1 M de reportes.
- RNF-03: ≥ 200 peticiones/s con la caché caliente.
- Errores < 1 %.

## Cómo correrla en el portátil (PowerShell)

```powershell
# 0. Una sola vez: Locust en tu .venv
pip install -r pruebas-carga/requirements.txt

# 1. Volumen: 1 millón de reportes sintéticos (~5-10 min)
docker compose run --rm etl python -m sintetico.generar --reportes 1000000 --sedes 12 --limpiar

# 2. Preparar la API para la prueba
#    a) en .env sube el límite del portal, porque todo Locust sale de una sola IP:
#         LIMITE_PUBLICO_POR_MINUTO=1000000
#    b) apaga los agentes: no tiene sentido mandar al LLM los reportes que crea la prueba
docker compose up -d api
docker compose stop agentes

# 3. Admin para el perfil AdminSede (la contraseña se pide por teclado)
docker compose run --rm api python -m app.crear_usuario --email carga@pruebas.uniminuto.edu.co --nombre "Admin carga" --rol admin_sede --sede 1
$env:CARGA_ADMIN_EMAIL = "carga@pruebas.uniminuto.edu.co"
$env:CARGA_ADMIN_CLAVE = "<la que pusiste>"
$env:CARGA_SEDES = "1,2,3,4,5,6,7,8,9,10,11,12"   # las sedes donde el generador puso datos

# 4a. Uso real: 200 usuarios con pausas entre clics, 5 minutos
locust -f pruebas-carga/locustfile.py --host http://localhost:8080 --headless -u 200 -r 20 -t 5m --reset-stats --only-summary --csv pruebas-carga/resultados/portatil-200u
python pruebas-carga/resumir.py pruebas-carga/resultados/portatil-200u "200 usuarios, 5 min, 1 M de reportes, portátil"

# 4b. Capacidad (RNF-03): sin pausas, 100 usuarios, 2 minutos
$env:CARGA_PAUSA = "0"
locust -f pruebas-carga/locustfile.py --host http://localhost:8080 --headless -u 100 -r 25 -t 2m --reset-stats --only-summary --csv pruebas-carga/resultados/portatil-pico-100u
python pruebas-carga/resumir.py pruebas-carga/resultados/portatil-pico-100u "Capacidad: 100 usuarios sin pausas, 2 min, 1 M de reportes, portátil"
Remove-Item Env:CARGA_PAUSA

# 5. Dejar todo como estaba
Get-Content pruebas-carga/limpiar.sql | docker compose exec -T postgres psql -U app -d objetos_perdidos
#    vuelve a poner LIMITE_PUBLICO_POR_MINUTO=60 en .env y:
docker compose up -d api agentes
```

`--reset-stats` borra las estadísticas al terminar la rampa: el arranque en frío (API recién reiniciada, caché vacía, 30 logins a la vez) no contamina el régimen estable. En el portátil, sin esa opción, las primeras 60 peticiones (segundos 0 a 4) tuvieron una mediana de 2,1 s y arrastraron el p99 de toda la corrida, mientras el máximo no volvió a subir en 5 minutos.

En modo capacidad (`CARGA_PAUSA=0`) la meta es RNF-03 (≥ 200 peticiones/s y errores < 1 %). La latencia sube por la cola, lo que es esperable al saturar, y se reporta solo como dato.

Sin `--headless`, Locust abre su panel en http://localhost:8089, con gráficas en vivo. Sirven para capturas del artículo.

Si el perfil admin da 401 en todo, revisa que `CARGA_ADMIN_CLAVE` no lleve los signos `< >`. Locust ya reenvía la cookie `Secure` por `http://localhost`.

`resumir.py` deja una tabla markdown en `pruebas-carga/resultados/<nombre>.md`, lista para el artículo. Los CSV no se suben al repositorio.

## Resultados en el entorno de desarrollo (referencia)

Máquina de **2 CPU y 7 GB**, donde Locust, la API y PostgreSQL compiten por los mismos núcleos, con **300 mil reportes** (2,4 M de filas). Los números oficiales del artículo son los del portátil con 1 M de reportes.

| Escenario | Peticiones/s | p95 lectura pública | Errores |
|---|---:|---:|---:|
| 100 usuarios con pausas reales, 2 min | 42,5 (lo limita la pausa, no el servidor) | 26 ms | 0 % |
| 50 usuarios sin pausas, 90 s | **342,6** | 250 ms | 0 % |

Detalle por ruta: [`resultados/sandbox-100u.md`](resultados/sandbox-100u.md) y [`resultados/sandbox-pico-50u.md`](resultados/sandbox-pico-50u.md).

## Lo que encontraron las pruebas (y se corrigió)

1. **Interbloqueo bajo pico** (primera corrección, completada en el hallazgo 6). Con 50 usuarios sin pausa, la API daba ~320 peticiones/s durante 25 s y luego se congelaba **30 s exactos**. Al final salían errores 500 `PoolTimeout`.
   - Causa: FastAPI corre las rutas síncronas en 40 hilos, pero el pool tenía 10 conexiones. Los 40 hilos quedaban esperando conexión, y las peticiones que ya tenían una no conseguían hilo para terminar y devolverla.
   - Solución: los hilos ahora son iguales a las conexiones (`DB_POOL_MAX`, 20 por defecto), así el bloqueo no puede ocurrir.
   - Resultado: 90 s estables a 343 peticiones/s y 0 errores.
2. **El listado del admin no tenía índice para "lo más reciente de mi sede".** Con 300 mil reportes, la sede principal leía y ordenaba ~100 mil filas por petición.
   - Solución: migración 0009, con índices `(sede_id, creado_en DESC, id DESC)`.
   - Resultado: el listado de hallazgos pasó de un p50 de 180 ms a 11 ms, y el de reportes de 91 ms a 12 ms.
3. **La caché del portal igual pedía conexión a PostgreSQL.** La pedía antes de mirar Redis. Ahora la pide solo si la respuesta no está en caché.

4. **Borrar datos sintéticos no terminaba** (`--limpiar` con 1 M de reportes). Tres llaves foráneas no tenían índice en la tabla que referencia, y el índice de `consentimiento` por estudiante era parcial (solo consentimientos vigentes), así que la verificación de la llave no podía usarlo. Cada estudiante borrado recorría 40 MB.
   - Solución: migración 0010.
   - Resultado: la limpieza de 2,4 M de filas pasó de no terminar en más de 20 minutos a 45 s.

5. **Una ráfaga de logins congelaba la API** (encontrado en el portátil: p99 del portal en 2 s mientras entraban 30 admins). El login bloqueaba la fila del usuario y calculaba argon2 sin soltar ese bloqueo, la conexión ni el hilo. 20 logins a la misma cuenta agotaban todo, y alguien con contraseñas erradas podía provocarlo a propósito.
   - Solución: argon2 se calcula fuera de la base, con su propio límite de hilos (la mitad de los núcleos), y los contadores se actualizan en una sola sentencia atómica.
   - Resultado: con 20 logins por segundo, el portal se queda en un p50 de 13 ms y un p95 de 43 ms (2 CPU). Antes la API se congelaba 30 s.

6. **El interbloqueo de la Fase 6 seguía siendo posible** (visto en el portátil: peticiones de 30 y 60 s y errores 500 en la prueba de capacidad). Igualar hilos y conexiones (hallazgo 1) solo lo hacía menos probable. FastAPI saca la conexión en un hilo y ejecuta la ruta en **otro**, así que había un momento en que la petición tenía conexión pero no hilo.
   - Solución: cada petición toma primero un **cupo** asíncrono, y hay menos cupos que conexiones. Esperar un cupo no ocupa hilo ni conexión.
   - Resultado: con 150 usuarios sin pausa (2 CPU), pasó de 7,4 peticiones/s con 9,5 % de errores y 96 `PoolTimeout` a **368,6 peticiones/s con 0 errores**.

Decisiones en [ADR-021](../docs/adr/021-resultados-fase-6.md).
