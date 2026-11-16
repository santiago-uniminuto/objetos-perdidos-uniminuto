# ADR-022: Respaldos de PostgreSQL y de las fotos

- **Estado:** aceptada
- **Fecha:** 2026-11-15
- **Responsable:** Equipo completo

## Contexto

El sistema se publica desde un portátil (ADR-009). Un disco dañado, un `docker compose down -v` por error o una migración mal aplicada se llevarían todos los reportes, entregas y actas. Hace falta un respaldo automático, que no dependa de que alguien se acuerde, y una forma probada de restaurarlo.

## Decisión

Un servicio `respaldo` (perfil `core`) hace **un respaldo diario** (`RESPALDO_HORA`, por defecto 02:30) en la carpeta `./respaldos` del proyecto, visible desde Windows para copiarla a una USB o a la nube.

| Qué | Cómo | Por qué |
|---|---|---|
| PostgreSQL | `pg_dump` en formato custom (comprimido), un archivo por día, retención de `RESPALDO_DIAS` (7) | Es la fuente de verdad (ADR-003). Se usa la misma imagen de la base, así `pg_dump` es de la misma versión mayor |
| Fotos (bucket `fotos`) | Espejo exacto en disco: descarga lo nuevo y borra lo que ya no existe | Las fotos no se pueden reconstruir. El espejo respeta su borrado a los 90 días (ADR-018) |
| Lake (bronze/silver/gold) | **No se respalda** | Se reconstruye desde el outbox, que va dentro del dump |
| MongoDB | **No se respalda** | Trazas de agentes y copia de eventos: no es fuente de verdad |

- El dump se escribe a un `.parcial` y se renombra al terminar: un respaldo cortado nunca queda con nombre de válido.
- La retención nunca borra el respaldo más reciente.
- Un fallo (base apagada, disco lleno) se registra y se reintenta al día siguiente: el servicio no se cae.
- `verificar` restaura el último dump en una base temporal, compara conteos con la base viva y la borra. Es la prueba de restauración que se puede repetir cuando se quiera.
- `restaurar` reemplaza la base real solo con `--confirmar` y con la API detenida. Con `--fotos` sube también el espejo al bucket.

## Consecuencias

- Tamaño medido: con 300 mil reportes sintéticos, el dump pesa 131 MB y tarda 21 s. Con 1 M son unos 440 MB por día, ~3 GB con 7 días de retención. Sin los datos sintéticos baja a pocos MB.
- Los respaldos tienen datos personales (estudiantes, documentos): la carpeta `respaldos/` está en `.gitignore`, y si se copia fuera del portátil debe ir a un lugar con acceso restringido (Ley 1581).
- Es un respaldo en el mismo equipo. Protege de errores y de daños de Docker, no de perder el portátil. Por eso se recomienda copiar `respaldos/` a otro lugar cada semana.
