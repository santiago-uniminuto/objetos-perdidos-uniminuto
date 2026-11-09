# ADR-006: Minimización de datos hacia la IA

- **Estado:** aceptada
- **Fecha:** 2026-11-07
- **Responsable:** IA / Backend

## Contexto

Ley 1581 de 2012 (protección de datos personales). Si se usa un proveedor externo (DeepSeek, Qwen cloud), enviar datos personales sería una transferencia internacional.

## Decisión

A cualquier modelo solo se le envía la descripción del objeto, categoría, zona y fecha. Antes de cada llamada, un filtro elimina patrones de documento de identidad, teléfono, correo y nombres propios registrados del dueño.

## Consecuencias

- Una prueba automatizada verifica que el texto enviado no contiene datos personales.
- Con Ollama local los datos no salen del equipo, pero el filtro se aplica igual.
