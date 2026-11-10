# ADR-015: Agente analista con números en código y verificación de cifras del LLM

- **Estado:** aceptada
- **Fecha:** 2026-11-10
- **Responsable:** IA / Datos

## Contexto

El proyecto pide un agente que convierta el Data Lake en información útil para el administrador. Un modelo de 3 B parámetros en el portátil (qwen2.5:3b) redacta bien en español, pero calcula mal y puede inventar cifras con total seguridad. Un informe con números falsos es peor que no tener informe.

## Decisión

1. **El LLM nunca calcula.** Las métricas (tasa de recuperación, días típicos, zonas y franjas críticas, precisión del matching) y la predicción se calculan en Python a partir de las tablas gold del lake.
2. **Predicción explicable:** `λ = nivel × factor(clase de semana)`, con clases vacaciones, inicio, normal y parciales (semanas 8 y 16), e intervalo del 90 % de la Poisson. Cada informe trae un *backtest* de 12 semanas contra la línea base ingenua (media de 4 semanas); si el modelo no gana, el resumen lo dice.
3. **El LLM solo redacta** 4-6 frases con el JSON de hechos, que contiene solo agregados, sin texto libre ni datos personales.
4. **Verificación de cifras:** todo número mayor que 10 en el resumen debe aparecer en los hechos, igual o redondeado. Si no, se reintenta una vez. Si vuelve a fallar, o si el LLM no responde o se pasa del presupuesto, el resumen sale de una **plantilla fija** y la traza queda en estado `respaldo`.
5. Corre dentro del worker de agentes **por reloj** (`ANALISTA_HORAS`, 6 h por defecto), no por eventos del outbox. Solo arranca cuando no hay eventos pendientes. Un *advisory lock* de PostgreSQL evita informes duplicados.
6. Los informes se guardan en `informe_analitica`, uno global y uno por sede. Se sirven en `GET /api/v1/analitica/resumen`: el admin ve el de su sede o el global; el auditor ve cualquiera.

## Consecuencias

- Con 100 000 reportes sintéticos, el backtest global dio un error absoluto medio de 32 pérdidas por semana, frente a 197 de la ingenua (−84 %). Esto es esperable porque el generador tiene estacionalidad académica; con datos reales hay que volver a medirlo.
- Las fechas de los semestres son un **supuesto** (`datos/lago/calendario.py`) hasta tener el calendario oficial.
- La verificación de cifras se puede mostrar en la sustentación: la traza tiene el paso `verificar_cifras` con los números rechazados.
- Si el lake no está levantado (perfil `datos` apagado), el analista registra el error y lo reintenta a los 5 minutos, sin afectar al matcher ni al notificador.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
| --- | --- |
| Que el LLM lea las tablas y calcule (text-to-SQL) | Un modelo 3B se equivoca en agregaciones; no es verificable |
| Prophet / ARIMA | Dependencias pesadas y poco explicables con ~100 semanas de historia; no capturan los parciales sin regresores |
| Resumen solo con plantilla | Funciona (es el respaldo), pero no cumple el objetivo de un agente que interprete |
