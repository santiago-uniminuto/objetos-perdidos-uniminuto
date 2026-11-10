# Agentes de IA (harness)

**Responsable:** IA · **Diseño:** Fase 4 · **Matcher y notificador:** Fase 5, parte 2 · **Analista:** Fase 5, parte 3 (necesita el lake)

El worker (`python -m harness.worker`, servicio `agentes` de Docker Compose) consume el `outbox` de PostgreSQL: cada agente guarda hasta qué evento procesó (ADR-014).

| Agente | Disparador | Herramientas | Límites |
| --- | --- | --- | --- |
| Matcher | Evento `reporte.creado` / `hallazgo.creado` | anonimizar, normalizar (LLM), vectorizar, buscar candidatos (pgvector), puntuar, explicar (LLM), guardar sugerencias | Solo sugiere; máx. 5 sugerencias y 7 llamadas al LLM por ejecución; 60 s |
| Notificador | Evento `coincidencia.verificada` (la dispara el admin) | consultar consentimiento, enviar correo con plantilla | Sin LLM; sin detalles del objeto; máx. 1 correo por coincidencia y 3 por estudiante al día |
| Analista | Programado (lunes 6:00) o a pedido del admin | consultas DuckDB **predefinidas** sobre la capa gold, pronóstico semanal | Solo lectura; sin SQL libre; máx. 6 herramientas por ejecución |

Cada ejecución guarda su traza en MongoDB (`trazas_agente`): pasos, herramienta, ms, tokens, tipos de datos personales eliminados (nunca los valores) y estado (`ok`, `respaldo`, `limite_excedido`, `error`).

## Ver a los agentes trabajar

```powershell
docker compose logs -f agentes
# últimas trazas
docker compose exec mongo mongosh -u root -p <clave> --authenticationDatabase admin --quiet --eval "db.getSiblingDB('objetos_perdidos').trazas_agente.find({}, {pasos:0}).sort({creado_en:-1}).limit(5)"
# hasta dónde leyó cada agente
docker compose exec postgres psql -U app -d objetos_perdidos -c "SELECT * FROM consumidor_outbox;"
```

Los correos del notificador llegan a Mailpit: http://localhost:8025

### Agente analista

Corre solo cada `ANALISTA_HORAS` (6 h) si el lake tiene datos. Para forzar una corrida ahora:

```powershell
docker compose exec agentes python -m harness.analista
```

El informe se ve en Swagger con `GET /api/v1/analitica/resumen`: `alcance=global` para todas las sedes.

## Estructura

```text
harness/
  nucleo.py         Agente base: herramientas con permiso, presupuesto, trazas
  matcher.py        8 pasos: anonimizar → normalizar → vectorizar → pgvector → puntuar → explicar → sugerir
  notificador.py    correo con plantilla fija, consentimiento, deduplicación
  analista.py       informes por sede: métricas y predicción en código, resumen del LLM verificado (ADR-015)
  lago.py           lectura de las tablas gold del lake (S3 o carpeta local)
  worker.py         consume el outbox con offset por agente y lock en Redis; programa al analista
ia/
  anonimizador.py   quita correos, teléfonos, documentos y nombres (ADR-006)
  esquemas.py       ObjetoNormalizado y Explicacion (validación de la salida del LLM)
  normalizador.py   normalización con LLM (+1 reintento) o heurística de respaldo
  puntaje.py        fórmula del puntaje y umbral de sugerencia
  pronostico.py     predicción semanal con estacionalidad académica + backtest contra la ingenua
  proveedores.py    ChatProvider y EmbeddingProvider (API compatible con OpenAI)
prompts/            prompts versionados del normalizador y el explicador
evaluacion/
  generar_dataset.py  set sintético etiquetado (reproducible con --semilla)
  evaluar.py          compara configuraciones: crudo, heuristica, llm
  datos/              set_matching.json (200 reportes, 350 hallazgos)
tests/              pruebas (no necesitan modelo)
```

## Correr las pruebas

```bash
cd agentes
pip install -r requirements-dev.txt
pytest
```

## Correr la evaluación contra Ollama (en el portátil)

```powershell
cd agentes
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m evaluacion.evaluar --config crudo heuristica          # ~1 min
python -m evaluacion.evaluar --config llm --limite 50           # prueba rápida del LLM
python -m evaluacion.evaluar --config crudo heuristica llm      # completa (~10-20 min)
```

Usa `http://localhost:11434/v1` por defecto (variables `LLM_*` y `EMBEDDING_*` para cambiar de proveedor). Guarda los resultados en `evaluacion/resultados/`.
