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
locust -f pruebas-carga/locustfile.py --host http://localhost:8080 --headless -u 200 -r 20 -t 5m --csv pruebas-carga/resultados/portatil-200u
python pruebas-carga/resumir.py pruebas-carga/resultados/portatil-200u "200 usuarios, 5 min, 1 M de reportes, portátil"

# 4b. Capacidad (RNF-03): sin pausas, 100 usuarios, 2 minutos
$env:CARGA_PAUSA = "0"
locust -f pruebas-carga/locustfile.py --host http://localhost:8080 --headless -u 100 -r 25 -t 2m --csv pruebas-carga/resultados/portatil-pico-100u
python pruebas-carga/resumir.py pruebas-carga/resultados/portatil-pico-100u "Capacidad: 100 usuarios sin pausas, 2 min, 1 M de reportes, portátil"
Remove-Item Env:CARGA_PAUSA

# 5. Dejar todo como estaba
Get-Content pruebas-carga/limpiar.sql | docker compose exec -T postgres psql -U app -d objetos_perdidos
#    vuelve a poner LIMITE_PUBLICO_POR_MINUTO=60 en .env y:
docker compose up -d api agentes
```

Sin `--headless`, Locust abre su panel en http://localhost:8089, con gráficas en vivo. Sirven para capturas del artículo.

`resumir.py` deja una tabla markdown en `pruebas-carga/resultados/<nombre>.md`, lista para el artículo. Los CSV no se suben al repositorio.

## Resultados en el entorno de desarrollo (referencia)

Máquina de **2 CPU y 7 GB**, donde Locust, la API y PostgreSQL compiten por los mismos núcleos, con **300 mil reportes** (2,4 M de filas). Los números oficiales del artículo son los del portátil con 1 M de reportes.

| Escenario | Peticiones/s | p95 lectura pública | Errores |
|---|---:|---:|---:|
| 100 usuarios con pausas reales, 2 min | 42,5 (lo limita la pausa, no el servidor) | 26 ms | 0 % |
| 50 usuarios sin pausas, 90 s | **342,6** | 250 ms | 0 % |

Detalle por ruta: [`resultados/sandbox-100u.md`](resultados/sandbox-100u.md) y [`resultados/sandbox-pico-50u.md`](resultados/sandbox-pico-50u.md).

## Lo que encontraron las pruebas (y se corrigió)

1. **Interbloqueo bajo pico.** Con 50 usuarios sin pausa, la API daba ~320 peticiones/s durante 25 s y luego se congelaba **30 s exactos**. Al final salían errores 500 `PoolTimeout`.
   - Causa: FastAPI corre las rutas síncronas en 40 hilos, pero el pool tenía 10 conexiones. Los 40 hilos quedaban esperando conexión, y las peticiones que ya tenían una no conseguían hilo para terminar y devolverla.
   - Solución: los hilos ahora son iguales a las conexiones (`DB_POOL_MAX`, 20 por defecto), así el bloqueo no puede ocurrir.
   - Resultado: 90 s estables a 343 peticiones/s y 0 errores.
2. **El listado del admin no tenía índice para "lo más reciente de mi sede".** Con 300 mil reportes, la sede principal leía y ordenaba ~100 mil filas por petición.
   - Solución: migración 0009, con índices `(sede_id, creado_en DESC, id DESC)`.
   - Resultado: el listado de hallazgos pasó de un p50 de 180 ms a 11 ms, y el de reportes de 91 ms a 12 ms.
3. **La caché del portal igual pedía conexión a PostgreSQL.** La pedía antes de mirar Redis. Ahora la pide solo si la respuesta no está en caché.

Decisiones en [ADR-021](../docs/adr/021-resultados-fase-6.md).
