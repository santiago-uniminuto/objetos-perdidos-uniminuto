# Agentes de IA (harness)

**Responsable:** IA · **Diseño:** Fase 4 · **Implementación completa de los agentes:** Fase 5

| Agente | Disparador | Herramientas | Límites |
| --- | --- | --- | --- |
| Matcher | Evento `reporte.creado` / `hallazgo.creado` | anonimizar, normalizar (LLM), vectorizar, buscar candidatos (pgvector), puntuar, explicar (LLM), guardar sugerencias | Solo sugiere; máx. 5 sugerencias y 7 llamadas al LLM por ejecución; 60 s |
| Notificador | Evento `coincidencia.verificada` (la dispara el admin) | consultar consentimiento, enviar correo con plantilla | Sin LLM; sin detalles del objeto; máx. 1 correo por coincidencia y 3 por estudiante al día |
| Analista | Programado (lunes 6:00) o a pedido del admin | consultas DuckDB **predefinidas** sobre la capa gold, pronóstico semanal | Solo lectura; sin SQL libre; máx. 6 herramientas por ejecución |

Cada ejecución guarda su traza en MongoDB (`trazas_agente`).

## Estructura

```text
ia/
  anonimizador.py   quita correos, teléfonos, documentos y nombres (ADR-006)
  esquemas.py       ObjetoNormalizado y Explicacion (validación de la salida del LLM)
  normalizador.py   normalización con LLM (+1 reintento) o heurística de respaldo
  puntaje.py        fórmula del puntaje y umbral de sugerencia
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
