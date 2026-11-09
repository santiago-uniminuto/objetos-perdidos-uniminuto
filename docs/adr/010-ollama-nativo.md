# ADR-010: Ollama nativo en Windows

- **Estado:** aceptada
- **Fecha:** 2026-11-07
- **Responsable:** IA

## Contexto

El portátil tiene una RTX 3050 Laptop (4 GB VRAM). Pasar la GPU a contenedores en WSL2 añade configuración y fallos.

## Decisión

Ollama se instala directamente en Windows. Los contenedores lo llaman en `http://host.docker.internal:11434/v1`.

## Consecuencias

- La GPU se usa sin configuración extra; no consume RAM de WSL2.
- Con 4 GB de VRAM caben modelos de 3B–4B cuantizados.
- En un PC sin GPU (plan B) Ollama corre en CPU, más lento, o se cambia a un proveedor cloud por `.env`.
