# Agentes de IA (harness)

**Responsable:** IA · **Se diseña en:** Fase 4 · **Se construye en:** Fase 5

| Agente | Disparador | Herramientas | Límites |
| --- | --- | --- | --- |
| Matcher | Nuevo reporte o hallazgo | normalizar texto, embeddings, búsqueda pgvector | Solo sugiere; nunca verifica |
| Notificador | Coincidencia verificada por el admin | enviar correo | Sin detalles del objeto en el correo |
| Analista | Programado (diario) | consultas DuckDB a la capa gold | Solo lectura; sin datos personales |

Cada ejecución guarda su traza en MongoDB (entrada, herramientas usadas, salida, tokens, latencia).
