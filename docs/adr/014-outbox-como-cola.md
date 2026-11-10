# ADR-014: El outbox de PostgreSQL es la cola de los agentes (sin ARQ)

- **Estado:** aceptada (reemplaza la parte de colas de ADR-002)
- **Fecha:** 2026-11-10
- **Responsable:** IA / Datos

## Contexto

ADR-002 planeó colas en Redis con ARQ. Al implementar los agentes, los eventos ya existen de forma durable en la tabla `outbox` (ADR-004), escritos en la misma transacción que el cambio de negocio. Copiarlos a una cola de Redis agrega una pieza que puede perder trabajos si Redis se reinicia, y otro paso que sincronizar.

## Decisión

Cada consumidor (`matcher`, `notificador`, y luego `etl`) lee el `outbox` en orden y guarda en `consumidor_outbox` el último id procesado. Un worker (`python -m harness.worker`) recorre los consumidores en bucle. Redis solo se usa para:

- un lock por consumidor (`SET NX` con vencimiento), para que dos copias del worker no procesen lo mismo;
- contar reintentos (3 por evento; luego se registra y se avanza);
- la memoria del notificador (1 correo por coincidencia, 3 por estudiante al día).

## Consecuencias

- **Durable:** si el worker o Redis se caen, el trabajo pendiente sigue en PostgreSQL y se retoma desde el offset.
- **Al menos una vez:** un evento puede procesarse dos veces; por eso el matcher usa `ON CONFLICT DO NOTHING` y el notificador deduplica. Hay pruebas que rebobinan el offset para comprobarlo.
- **Orden:** un evento que falla bloquea a su consumidor hasta 3 intentos, para no saltarse eventos.
- **Latencia:** sondeo cada 2 s (configurable con `AGENTES_INTERVALO`); suficiente frente a la meta de sugerencias en < 30 s.
- Una dependencia menos (ARQ) y una cola que se puede consultar con SQL en la sustentación.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
| --- | --- |
| ARQ / Celery sobre Redis | Copia de eventos que ya son durables; posible pérdida si Redis se reinicia |
| `LISTEN/NOTIFY` de PostgreSQL | Se pierde la notificación si el worker no está escuchando; igual hace falta el offset |
| Kafka / Debezium | Demasiada RAM para el portátil (ver ADR-004) |
