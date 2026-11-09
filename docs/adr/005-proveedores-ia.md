# ADR-005: Proveedores de IA intercambiables (chat y embeddings separados)

- **Estado:** aceptada
- **Fecha:** 2026-11-07
- **Responsable:** IA

## Contexto

El curso exige poder usar DeepSeek o Qwen y cambiar de proveedor por configuración. DeepSeek no ofrece API de embeddings; Qwen y Ollama sí.

## Decisión

Dos interfaces: `ChatProvider` y `EmbeddingProvider`, ambas sobre la API compatible con OpenAI. El proveedor, la URL, la clave y el modelo se leen de `.env`. Por defecto: Ollama local (Qwen para chat, bge-m3 para embeddings).

## Consecuencias

- Cambiar de proveedor = cambiar `.env` y reiniciar.
- Cada vector guarda `modelo` y `dimension`; cambiar de modelo de embeddings exige reindexar.
- Costo $0 por defecto.
