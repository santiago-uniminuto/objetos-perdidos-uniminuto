# Instrucciones para agentes de IA

Este repositorio se construye como fábrica de software agéntica: cada integrante trabaja con agentes (Claude, ChatGPT, DeepSeek, Qwen, etc.). Todo agente que modifique este repositorio debe seguir estas reglas.

## Idioma y estilo

- Código, nombres de dominio, comentarios, commits y documentación en **español** (sin tildes en identificadores de código).
- Python 3.12, formateado y validado con `ruff`. TypeScript estricto en el frontend.

## Reglas no negociables

1. **Privacidad (Ley 1581/2012).** Nunca exponer datos personales del dueño (nombre, documento, teléfono, correo) en endpoints `/publico/*`, logs, trazas de agentes ni prompts a modelos. Ver ADR-006 y ADR-007.
2. **La IA sugiere, el admin decide.** Ningún agente puede cambiar una coincidencia a `verificada` ni registrar una entrega.
3. **PostgreSQL es la fuente de verdad** (ADR-003). Todo cambio de negocio escribe su evento en `outbox` en la misma transacción (ADR-004).
4. **Secretos fuera del repo.** Nunca escribir contraseñas, claves de API ni el archivo `.env`. Usa `.env.example` con valores de ejemplo.
5. **Solo datos sintéticos** en el repositorio y en pruebas. Nunca datos reales de estudiantes.
6. **Migraciones**, no cambios manuales al esquema: todo cambio de tablas va por Alembic.

## Antes de abrir un Pull Request

```bash
cd backend
ruff check .
pytest
```

Si cambias `docker-compose.yml`: `docker compose --profile core --profile datos --profile escala config -q`.

## Dónde va cada cosa

| Carpeta | Contenido |
| --- | --- |
| `backend/app/modulos/<dominio>/` | Rutas, esquemas, servicios y repositorios de cada dominio |
| `agentes/` | Harness, proveedores IA, agentes y sus herramientas |
| `datos/` | ETL, generador sintético, scripts de Citus, consultas DuckDB |
| `docs/adr/` | Una decisión por archivo; usa `000-plantilla.md` |

Si una tarea exige romper una de estas reglas, detente y pide confirmación a una persona del equipo.
