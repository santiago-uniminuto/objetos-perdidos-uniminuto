# ADR-013: Umbral de sugerencia 0,65 y penalización por color contradictorio

- **Estado:** aceptada (a confirmar con el set humano en la Fase 6)
- **Fecha:** 2026-11-09
- **Responsable:** IA

## Contexto

Primera evaluación real en el portátil (RTX 3050), set sintético de 200 reportes y 350 hallazgos (150 distractores), `bge-m3` + `qwen2.5:3b`. Resultado: `agentes/evaluacion/resultados/20261109-1450.json`.

| Métrica | crudo | heuristica | llm |
| --- | --- | --- | --- |
| recall@1 | 0,620 | 0,915 | 0,855 |
| recall@5 | 0,885 | 1,000 | 0,980 |
| MRR | 0,736 | 0,953 | 0,905 |
| recall@5 en casos difíciles | 0,718 | 1,000 | 0,962 |
| Precisión con umbral 0,55 | — | 0,299 | 0,303 |
| Sugerencias por reporte (0,55) | — | 3,33 | 3,19 |
| Fuga de datos personales | 0 | 0 | 0 |
| Inyecciones obedecidas | — | — | 0 |
| JSON inválido tras reintento | — | — | 3,6 % |
| Normalización p95 | — | 1,5 ms | 1.973 ms |

Barrido de umbral de la configuración `llm`:

| Umbral | Precisión | Cobertura | Sugerencias/reporte |
| --- | --- | --- | --- |
| 0,55 | 0,303 | 0,965 | 3,19 |
| 0,60 | 0,373 | 0,910 | 2,44 |
| **0,65** | **0,512** | **0,855** | **1,67** |
| 0,70 | 0,618 | 0,775 | 1,25 |
| 0,75 | 0,776 | 0,675 | 0,87 |

Con 0,55 el admin recibe 3 sugerencias por reporte y 7 de cada 10 son distractores (mismo tipo de objeto, otro color o marca).

## Decisión

1. **Umbral de sugerencia: 0,65.** Es el menor umbral que cumple las metas de precisión ≥ 0,50 y ≤ 3 sugerencias por reporte, conservando la mayor cobertura posible (0,855). Se prefiere cobertura sobre precisión porque el admin siempre revisa: una sugerencia de más le cuesta segundos, una coincidencia que no se sugiere puede dejar un objeto sin dueño.
2. **Penalización ×0,8 cuando los colores conocidos no comparten ninguno**, igual que la de marca (×0,7). Con el vectorizador de prueba subió la precisión con umbral 0,65 de 0,61 a 0,76 sin bajar la cobertura. Debe confirmarse con bge-m3 + Qwen.

## Consecuencias

- Hay que repetir la evaluación con la penalización de color (la caché de normalizaciones la hace rápida) y, si cambia el punto óptimo, actualizar este ADR.
- En el set sintético la heurística supera al LLM porque el set usa el mismo vocabulario que la heurística. **La decisión de usar el LLM en producción se toma con el set humano**: si allí tampoco lo supera, se usa la heurística y el LLM solo explica.
- `crudo` (solo búsqueda vectorial) queda como línea base del artículo: la normalización + fórmula sube recall@1 de 0,62 a 0,86–0,92.
